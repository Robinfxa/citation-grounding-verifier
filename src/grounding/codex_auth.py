"""Application-owned SIWC credentials for local macOS/Linux installations.

This module never imports another application's credentials. Only the public
OAuth endpoints and this application's protected store participate in sign-in.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import fcntl
import hashlib
import inspect
import json
import math
import os
import re
import secrets
import stat
import sys
import tempfile
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, replace
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt

from grounding.contracts import ERRORS
from grounding.diagnostics import operation, request_id

ISSUER = "https://auth.openai.com"
AUTHORIZE_ENDPOINT = ISSUER + "/api/accounts/authorize"
TOKEN_ENDPOINT = ISSUER + "/api/accounts/oauth/token"
DISCOVERY_URL = ISSUER + "/.well-known/openid-configuration"
JWKS_URI = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
USAGE_URL = "https://chatgpt.com/settings/usage"
REQUESTED_SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPES = frozenset({"resource.invoke", "chatgpt.tokens.use.direct"})
CALLBACK_PATH = "/auth/callback"
MAX_AUTH_BYTES = 131_072
MAX_MODEL_BYTES = 1_048_576
MAX_STORE_BYTES = 65_536
_PROFILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_SCOPE = re.compile(r"[A-Za-z0-9._:/-]{1,128}\Z")
_MESSAGES = {
    **{key: value[1] for key, value in ERRORS.items()},
    "invalid_profile": "Profile must use 1–64 lowercase letters, digits, underscores or hyphens.",
    "insecure_store": "Credential storage must be an owner-only directory outside this repository.",
    "store_unavailable": "The application credential store could not be read or updated.",
    "account_mismatch": "Sign-in did not match the selected account registration; credentials were kept.",
    "concurrent_update": "The selected profile changed during sign-in. Repeat sign-in for that profile.",
    "callback_invalid": "The sign-in callback could not be verified. Repeat sign-in.",
    "state_mismatch": "The one-time sign-in state could not be verified. Repeat sign-in.",
    "authorization_denied": "Sign-in was declined. Existing credentials were kept.",
    "login_timeout": "Sign-in timed out. Existing credentials were kept; repeat sign-in.",
    "browser_unavailable": "The system browser could not be opened. Repeat sign-in from a local session.",
    "listener_unavailable": "The local sign-in callback could not be started. Repeat sign-in.",
}
_DIAGNOSTIC_REASONS = frozenset(
    {
        "oauth_invalid_grant",
        "oauth_invalid_client",
        "oauth_access_denied",
        "oauth_invalid_request",
        "oauth_rejected",
        "http_rejected",
        "response_invalid",
        "response_too_large",
        "network_timeout",
        "network_unavailable",
        "jwt_header",
        "jwt_algorithm",
        "jwt_keys_invalid",
        "jwt_key_missing",
        "jwt_key_ambiguous",
        "jwt_key_invalid",
        "jwt_signature",
        "jwt_expired",
        "jwt_not_yet_valid",
        "jwt_audience",
        "jwt_issuer",
        "jwt_missing_claim",
        "jwt_issued_at",
        "jwt_subject",
        "jwt_nonce",
        "jwt_authorized_party",
        "jwt_claims",
    }
)


class AuthError(Exception):
    """Allowlisted diagnostics only, without provider text or exception causes."""

    def __init__(self, code: str, *, diagnostic_reason: str | None = None) -> None:
        self.code = code if code in _MESSAGES else "authentication_failed"
        self.diagnostic_reason = (
            diagnostic_reason
            if isinstance(diagnostic_reason, str) and diagnostic_reason in _DIAGNOSTIC_REASONS
            else None
        )
        super().__init__(_MESSAGES[self.code])


def diagnostic_scope(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        enabled = os.environ.get("GROUNDING_DIAGNOSTICS", "true").lower() not in {"false", "0"}
        with operation(enabled=enabled):
            return await function(*args, **kwargs)

    return wrapped


def emit_diagnostic(
    stage: str,
    outcome: str,
    operation_id: str,
    started: float,
    error_code: str | None = None,
    *,
    http_status: int | None = None,
    reason: str | None = None,
) -> None:
    """One bounded unbuffered local record; a failed sink cannot change the result."""
    if stage not in {
        "auth_login",
        "auth_refresh",
        "auth_logout",
        "auth_models",
        "codex_inference",
        "auth_callback",
        "auth_token_exchange",
        "auth_jwks",
        "auth_id_token",
    }:
        return
    if outcome not in {
        "start",
        "stream_open",
        "success",
        "failure",
        "cancelled",
        "local_only",
        "reauthorizing",
    }:
        return
    if not re.fullmatch(r"[0-9a-f]{32}", operation_id):
        return
    enabled = os.environ.get("GROUNDING_DIAGNOSTICS", "true").lower() not in {"false", "0"}
    with operation(enabled=enabled) as current:
        if not current.enabled:
            return
        record = {
            "request_id": current.request_id,
            "stage": stage,
            "event": {
                "start": "start",
                "stream_open": "provider_attempt",
                "reauthorizing": "progress",
            }.get(outcome, "end"),
            "outcome": "started" if outcome in {"start", "stream_open"} else outcome,
            "elapsed_ms": round(max(0, time.monotonic() - current.started) * 1000, 3),
        }
    if error_code in _MESSAGES:
        record["error_code"] = error_code
    if type(http_status) is int and 100 <= http_status <= 599:
        record["http_status"] = http_status
    if isinstance(reason, str) and reason in _DIAGNOSTIC_REASONS:
        record["reason"] = reason
    try:
        os.write(2, (json.dumps(record, separators=(",", ":")) + "\n").encode())
    except OSError:
        pass


def _string(value: Any, *, limit: int = 16_384) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise AuthError("provider_protocol_error")
    if any(not 33 <= ord(char) <= 126 for char in value):
        raise AuthError("provider_protocol_error")
    return value


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AuthError("provider_protocol_error")
    return float(value)


@dataclass(frozen=True, repr=False)
class Credential:
    issuer: str
    subject: str
    client_id: str
    ext_agent_host_id: str
    id_token: str | None
    access_token: str | None
    refresh_token: str | None
    scopes: tuple[str, ...]
    expires_at: float | None
    saved_at: float
    earliest_refresh_at: float | None = None

    @property
    def plan_enabled(self) -> bool:
        return PLAN_SCOPES.issubset(self.scopes)


class CredentialStore:
    def __init__(self, profile: str | None = None, auth_dir: str | Path | None = None) -> None:
        self.profile = (
            profile if profile is not None else os.environ.get("GROUNDING_AUTH_PROFILE", "default")
        )
        if not _PROFILE.fullmatch(self.profile):
            raise AuthError("invalid_profile")
        location = auth_dir or os.environ.get("GROUNDING_AUTH_DIR")
        self.directory = (
            Path(os.path.abspath(Path(location).expanduser()))
            if location
            else (Path.home() / ".config" / "citation-grounding")
        )
        source_root = Path(__file__).resolve().parents[2]
        project_roots = {source_root} if (source_root / "pyproject.toml").is_file() else set()
        for ancestor in (Path.cwd(), *Path.cwd().parents):
            if (ancestor / "pyproject.toml").is_file() or (ancestor / ".git").exists():
                project_roots.add(ancestor)
                break
        if self.directory in {Path("/"), Path.home(), Path.cwd()} or any(
            self.directory.resolve().is_relative_to(root.resolve()) for root in project_roots
        ):
            raise AuthError("insecure_store")
        self.path = self.directory / f"profile-{self.profile}.json"

    def _check_directory(self, *, create: bool = False) -> bool:
        try:
            if create:
                self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise AuthError("insecure_store")
            if info.st_mode & 0o077:
                raise AuthError("insecure_store")
            return True
        except FileNotFoundError:
            return False
        except OSError:
            raise AuthError("store_unavailable") from None

    @staticmethod
    def _check_file(fd: int) -> None:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise AuthError("insecure_store")

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not self._check_directory():
            return None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            with os.fdopen(fd, "rb") as stream:
                self._check_file(stream.fileno())
                raw = stream.read(MAX_STORE_BYTES + 1)
            if len(raw) > MAX_STORE_BYTES:
                raise AuthError("store_unavailable")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise AuthError("store_unavailable")
            return data
        except FileNotFoundError:
            return None
        except (OSError, ValueError, RecursionError):
            raise AuthError("store_unavailable") from None

    def _atomic_json(self, path: Path, data: dict[str, Any]) -> None:
        temporary = None
        try:
            raw = json.dumps(data, ensure_ascii=True, allow_nan=False).encode()
            if len(raw) > MAX_STORE_BYTES:
                raise AuthError("store_unavailable")
            self._check_directory(create=True)
            fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.directory)
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError):
            raise AuthError("store_unavailable") from None
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass

    @asynccontextmanager
    async def lock(self, timeout_seconds: float = 30) -> AsyncIterator[None]:
        self._check_directory(create=True)
        fd = None
        acquired = False
        try:
            fd = os.open(
                self.directory / ".lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
            )
            self._check_file(fd)
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise AuthError("upstream_timeout") from None
                    await asyncio.sleep(min(0.025, max(0, deadline - time.monotonic())))
            yield
        except OSError:
            raise AuthError("store_unavailable") from None
        finally:
            if fd is not None:
                if acquired:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def host_id(self) -> str:
        data = self._read_json(self.directory / "host.json")
        if data is None:
            value = "urn:uuid:" + str(uuid.uuid4())
            self._atomic_json(self.directory / "host.json", {"ext_agent_host_id": value})
            return value
        try:
            value = data["ext_agent_host_id"]
            if not isinstance(value, str) or not value.startswith("urn:uuid:"):
                raise ValueError
            if uuid.UUID(value[9:]).version != 4:
                raise ValueError
            return value
        except (KeyError, ValueError, AttributeError):
            raise AuthError("store_unavailable") from None

    def load(self) -> Credential | None:
        data = self._read_json(self.path)
        if data is None:
            return None
        try:
            record = Credential(**data)
            if record.issuer != ISSUER or record.client_id == "dynamic_agent_client":
                raise ValueError
            _string(record.subject, limit=512)
            _string(record.client_id, limit=256)
            if (
                not record.ext_agent_host_id.startswith("urn:uuid:")
                or uuid.UUID(record.ext_agent_host_id[9:]).version != 4
            ):
                raise ValueError
            for token in (record.id_token, record.access_token, record.refresh_token):
                if token is not None:
                    _string(token)
            if not isinstance(record.scopes, (list, tuple)) or len(record.scopes) > 64:
                raise ValueError
            if not all(isinstance(item, str) and _SCOPE.fullmatch(item) for item in record.scopes):
                raise ValueError
            _number(record.saved_at)
            for value in (record.expires_at, record.earliest_refresh_at):
                if value is not None:
                    _number(value)
            return replace(record, scopes=tuple(record.scopes))
        except (TypeError, ValueError, AttributeError, AuthError):
            raise AuthError("store_unavailable") from None

    def save(self, record: Credential) -> None:
        """Atomically replace a record; mutation callers must hold this store's lock."""
        self._atomic_json(self.path, asdict(record))

    def status(self) -> dict[str, Any]:
        record = self.load()
        return {
            "profile": self.profile,
            "registered": record is not None,
            "signed_in": record is not None and record.id_token is not None,
            "plan_enabled": bool(record and record.access_token and record.plan_enabled),
            "renewable": bool(record and record.refresh_token),
            "expires_at": record.expires_at if record else None,
            "usage_url": USAGE_URL,
            "quota_remaining": None,
            "quota_reset_at": None,
        }

    @diagnostic_scope
    async def access_token(self, client: httpx.AsyncClient, timeout_seconds: float = 30) -> str:
        operation_id, started = request_id(), time.monotonic()
        refreshing = False
        try:
            async with asyncio.timeout(timeout_seconds), self.lock(timeout_seconds):
                # AIDEV-NOTE: reread under flock; a different process may have rotated
                # the refresh token while this request waited. Never cache token sets.
                record = self.load()
                if record is None or not record.id_token:
                    raise AuthError("not_configured")
                if not record.plan_enabled:
                    raise AuthError("plan_not_authorized")
                if not record.access_token:
                    raise AuthError("authentication_failed")
                now = time.time()
                if record.expires_at is not None and record.expires_at > now + 60:
                    return record.access_token
                if record.earliest_refresh_at and now < record.earliest_refresh_at:
                    if record.expires_at is not None and record.expires_at > now:
                        return record.access_token
                    raise AuthError("upstream_unavailable")
                if not record.refresh_token:
                    raise AuthError("authentication_failed")
                refreshing = True
                emit_diagnostic("auth_refresh", "start", operation_id, started)
                status, body = await request_json(
                    client,
                    "POST",
                    TOKEN_ENDPOINT,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": record.client_id,
                        "refresh_token": record.refresh_token,
                        "resource": RESOURCE,
                    },
                )
                if status != 200:
                    code = oauth_error_code(body)
                    if code in {
                        "invalid_grant",
                        "invalid_refresh_token",
                        "token_expired",
                        "refresh_token_expired",
                        "refresh_token_invalidated",
                        "refresh_token_reused",
                    }:
                        self.save(clear_tokens(record))
                    raise AuthError(http_auth_error(status))
                updated = credential_from_response(
                    body, record.client_id, record.ext_agent_host_id, previous=record
                )
                if body.get("id_token"):
                    metadata = await discovery(client)
                    identity = await verify_id_token(
                        client, metadata, updated.id_token, record.client_id, nonce=None
                    )
                    if identity["sub"] != record.subject:
                        raise AuthError("account_mismatch")
                self.save(updated)
                if not updated.plan_enabled:
                    raise AuthError("plan_not_authorized")
                emit_diagnostic("auth_refresh", "success", operation_id, started)
                return updated.access_token
        except TimeoutError:
            if refreshing:
                emit_diagnostic(
                    "auth_refresh", "failure", operation_id, started, "upstream_timeout"
                )
            raise AuthError("upstream_timeout") from None
        except AuthError as error:
            if refreshing:
                emit_diagnostic("auth_refresh", "failure", operation_id, started, error.code)
            raise
        except asyncio.CancelledError:
            if refreshing:
                emit_diagnostic("auth_refresh", "cancelled", operation_id, started)
            raise


def clear_tokens(record: Credential) -> Credential:
    return replace(
        record,
        id_token=None,
        access_token=None,
        refresh_token=None,
        scopes=(),
        expires_at=None,
        earliest_refresh_at=None,
        saved_at=time.time(),
    )


def http_auth_error(status: int) -> str:
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "upstream_unavailable"
    return "authentication_failed"


def oauth_error_code(body: dict[str, Any]) -> str | None:
    value = body.get("error")
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("code"), str):
        return value["code"]
    return None


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    allow_empty: bool = False,
    diagnostic_stage: str | None = None,
    max_bytes: int = MAX_AUTH_BYTES,
) -> tuple[int, dict[str, Any]]:
    operation_id, started = request_id(), time.monotonic()
    status = None

    def diagnose(outcome, code=None, reason=None):
        if diagnostic_stage is not None:
            emit_diagnostic(
                diagnostic_stage,
                outcome,
                operation_id,
                started,
                code,
                http_status=status,
                reason=reason,
            )

    diagnose("start")
    try:
        async with client.stream(
            method, url, data=data, headers=headers, follow_redirects=False
        ) as response:
            status = response.status_code
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                if len(raw) + len(chunk) > max_bytes:
                    raise AuthError(
                        "provider_protocol_error", diagnostic_reason="response_too_large"
                    )
                raw.extend(chunk)
            if not raw and allow_empty:
                diagnose("success" if status == 200 else "failure")
                return response.status_code, {}
            try:
                body = json.loads(raw)
            except (ValueError, RecursionError):
                if response.status_code != 200:
                    diagnose(
                        "failure",
                        reason=(
                            "oauth_rejected"
                            if diagnostic_stage == "auth_token_exchange"
                            else "http_rejected"
                        ),
                    )
                    return response.status_code, {}
                raise AuthError(
                    "provider_protocol_error", diagnostic_reason="response_invalid"
                ) from None
            if not isinstance(body, dict):
                raise AuthError("provider_protocol_error", diagnostic_reason="response_invalid")
            if status == 200:
                diagnose("success")
            else:
                reason = (
                    {
                        "invalid_grant": "oauth_invalid_grant",
                        "invalid_client": "oauth_invalid_client",
                        "access_denied": "oauth_access_denied",
                        "invalid_request": "oauth_invalid_request",
                    }.get(oauth_error_code(body), "oauth_rejected")
                    if diagnostic_stage == "auth_token_exchange"
                    else "http_rejected"
                )
                diagnose("failure", reason=reason)
            return response.status_code, body
    except AuthError as error:
        diagnose("failure", error.code, error.diagnostic_reason or "response_invalid")
        raise
    except httpx.TimeoutException:
        diagnose("failure", "upstream_timeout", "network_timeout")
        raise AuthError("upstream_timeout") from None
    except httpx.HTTPError:
        diagnose("failure", "upstream_unavailable", "network_unavailable")
        raise AuthError("upstream_unavailable") from None
    except asyncio.CancelledError:
        diagnose("cancelled")
        raise


async def discovery(client: httpx.AsyncClient) -> dict[str, Any]:
    status, metadata = await request_json(client, "GET", DISCOVERY_URL)
    if status != 200:
        raise AuthError(http_auth_error(status))
    expected = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZE_ENDPOINT,
        "token_endpoint": TOKEN_ENDPOINT,
        "jwks_uri": JWKS_URI,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise AuthError("provider_protocol_error")
    return metadata


@diagnostic_scope
async def verify_id_token(
    client: httpx.AsyncClient,
    metadata: dict[str, Any],
    token: str,
    client_id: str,
    nonce: str | None,
) -> dict[str, Any]:
    status, jwks = await request_json(
        client, "GET", metadata["jwks_uri"], diagnostic_stage="auth_jwks"
    )
    if status != 200:
        raise AuthError(http_auth_error(status))
    operation_id, started = request_id(), time.monotonic()
    emit_diagnostic("auth_id_token", "start", operation_id, started)
    reason = "jwt_header"
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"RS256", "ES256"} or header.get("crit"):
            reason = "jwt_algorithm"
            raise ValueError
        keys = jwks.get("keys")
        if not isinstance(keys, list) or len(keys) > 32:
            reason = "jwt_keys_invalid"
            raise ValueError
        matching = [
            key
            for key in keys
            if isinstance(key, dict)
            and key.get("kid") == header.get("kid")
            and key.get("use", "sig") == "sig"
            and key.get("alg", header["alg"]) == header["alg"]
        ]
        if not isinstance(header.get("kid"), str):
            raise ValueError
        if len(matching) != 1:
            reason = "jwt_key_missing" if not matching else "jwt_key_ambiguous"
            raise ValueError
        reason = "jwt_key_invalid"
        key = jwt.PyJWK.from_dict(matching[0], algorithm=header["alg"]).key
        reason = "jwt_claims"
        claims = jwt.decode(
            token,
            key,
            algorithms=[header["alg"]],
            issuer=ISSUER,
            audience=client_id,
            leeway=5,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
        reason = "jwt_subject"
        _string(claims.get("sub"), limit=512)
        reason = "jwt_claims"
        _number(claims.get("exp"))
        _number(claims.get("iat"))
        if nonce is not None and (
            not isinstance(claims.get("nonce"), str)
            or not secrets.compare_digest(claims["nonce"], nonce)
        ):
            reason = "jwt_nonce"
            raise ValueError
        if "azp" in claims and claims["azp"] != client_id:
            reason = "jwt_authorized_party"
            raise ValueError
        if isinstance(claims["aud"], list) and len(claims["aud"]) > 1:
            if claims.get("azp") != client_id:
                reason = "jwt_authorized_party"
                raise ValueError
        emit_diagnostic("auth_id_token", "success", operation_id, started)
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, AuthError) as error:
        for category, label in (
            (jwt.ExpiredSignatureError, "jwt_expired"),
            (jwt.ImmatureSignatureError, "jwt_not_yet_valid"),
            (jwt.InvalidAudienceError, "jwt_audience"),
            (jwt.InvalidIssuerError, "jwt_issuer"),
            (jwt.InvalidSignatureError, "jwt_signature"),
            (jwt.MissingRequiredClaimError, "jwt_missing_claim"),
            (jwt.InvalidIssuedAtError, "jwt_issued_at"),
            (jwt.exceptions.InvalidSubjectError, "jwt_subject"),
        ):
            if isinstance(error, category):
                reason = label
                break
        emit_diagnostic(
            "auth_id_token",
            "failure",
            operation_id,
            started,
            "authentication_failed",
            reason=reason,
        )
        raise AuthError("authentication_failed", diagnostic_reason=reason) from None


def credential_from_response(
    body: dict[str, Any],
    client_id: str,
    host_id: str,
    *,
    subject: str | None = None,
    previous: Credential | None = None,
) -> Credential:
    raw_scope = body.get("scope")
    if raw_scope is None and previous is not None:
        scopes = previous.scopes
    elif isinstance(raw_scope, str) and len(raw_scope) < 4096:
        scopes = tuple(sorted(set(raw_scope.split())))
        if not all(_SCOPE.fullmatch(item) for item in scopes):
            raise AuthError("provider_protocol_error")
    else:
        raise AuthError("provider_protocol_error")
    now = time.time()
    access = body.get("access_token")
    refresh = body.get("refresh_token")
    id_token = body.get("id_token", previous.id_token if previous else None)
    if PLAN_SCOPES.issubset(scopes) or access is not None or previous is not None:
        access = _string(access)
        if str(body.get("token_type", "")).lower() != "bearer":
            raise AuthError("provider_protocol_error")
        expires_in = _number(body.get("expires_in"))
        if not 0 < expires_in <= 366 * 86400:
            raise AuthError("provider_protocol_error")
        expires_at = now + expires_in
    else:
        expires_at = None
    if "offline_access" in scopes or previous is not None:
        refresh = _string(refresh)
    elif refresh is not None:
        refresh = _string(refresh)
    id_token = _string(id_token)
    earliest = body.get("earliest_refresh_at")
    if earliest is not None:
        earliest = _number(earliest)
    return Credential(
        ISSUER,
        subject or previous.subject,
        client_id,
        host_id,
        id_token,
        access,
        refresh,
        scopes,
        expires_at,
        now,
        earliest,
    )


@dataclass(repr=False)
class LoginAttempt:
    client_id: str
    redirect_uri: str
    expires_at: float
    state: str = ""
    nonce: str = ""
    verifier: str = ""
    consumed: bool = False

    def __post_init__(self) -> None:
        self.state = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)

    def authorization_url(self, host_id: str, consent: bool = False) -> str:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest())
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": REQUESTED_SCOPES,
            "resource": RESOURCE,
            "ext_agent_host_id": host_id,
            "state": self.state,
            "nonce": self.nonce,
            "code_challenge_method": "S256",
            "code_challenge": challenge.rstrip(b"=").decode(),
        }
        if self.client_id == "dynamic_agent_client":
            params["agent_name_hint"] = "Citation Grounding Verifier"
        if consent:
            params["prompt"] = "consent"
        # AIDEV-NOTE: omit ID/login hints. Returning identity is checked after
        # signature validation, and authorization URLs never carry a stored token.
        return AUTHORIZE_ENDPOINT + "?" + urlencode(params)

    def consume(self, target: str) -> tuple[str, str]:
        if self.consumed or time.monotonic() >= self.expires_at:
            raise AuthError("state_mismatch")
        self.consumed = True
        try:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or parsed.path != CALLBACK_PATH or parsed.fragment:
                raise AuthError("callback_invalid")
            params = parse_qs(
                parsed.query, keep_blank_values=True, max_num_fields=12, strict_parsing=True
            )
            if any(len(items) != 1 for items in params.values()):
                raise AuthError("callback_invalid")
            returned_state = params.get("state", [""])[0]
            if not secrets.compare_digest(returned_state, self.state):
                raise AuthError("state_mismatch")
            if "error" in params:
                raise AuthError("authorization_denied")
            code = _string(params.get("code", [None])[0], limit=4096)
            client_id = params.get("client_id", [None])[0]
            if self.client_id == "dynamic_agent_client":
                client_id = _string(client_id, limit=256)
                if client_id == "dynamic_agent_client":
                    raise AuthError("callback_invalid")
            elif client_id is not None and client_id != self.client_id:
                raise AuthError("account_mismatch")
            else:
                client_id = self.client_id
            return code, client_id
        except (ValueError, UnicodeError):
            raise AuthError("callback_invalid") from None


async def _system_browser(url: str) -> bool:
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "webbrowser",
            "-n",
            url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        raise AuthError("browser_unavailable") from None
    try:
        async with asyncio.timeout(10):
            return await process.wait() == 0
    except TimeoutError:
        raise AuthError("browser_unavailable") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@diagnostic_scope
async def login(
    store: CredentialStore,
    client: httpx.AsyncClient,
    *,
    open_browser: Callable[[str], bool | Awaitable[bool]] | None = None,
    timeout_seconds: float = 180,
    consent: bool = False,
) -> dict[str, Any]:
    if not 0 < timeout_seconds <= 600:
        raise AuthError("login_timeout")
    operation_id, started = request_id(), time.monotonic()
    emit_diagnostic("auth_login", "start", operation_id, started)
    connections: set[asyncio.Task] = set()
    server = None
    pending = asyncio.get_running_loop().create_future()
    attempt = None
    retired_state = None

    async def callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        callback_attempt, callback_pending = attempt, pending
        task = asyncio.current_task()
        connections.add(task)
        status_code = 400
        message = "Sign-in could not be verified. Return to the terminal."
        try:
            async with asyncio.timeout(2):
                header = await reader.readuntil(b"\r\n\r\n")
                lines = header.decode("ascii").split("\r\n")
                method, target, version = lines[0].split(" ")
                headers = [line.split(":", 1) for line in lines[1:] if line]
                hosts = [value.strip() for key, value in headers if key.lower() == "host"]
                if (
                    method != "GET"
                    or version not in {"HTTP/1.0", "HTTP/1.1"}
                    or hosts != [urlsplit(callback_attempt.redirect_uri).netloc]
                    or len(target) > 8192
                ):
                    raise AuthError("callback_invalid")
                if urlsplit(target).path != CALLBACK_PATH:
                    status_code = 404
                elif callback_pending.done():
                    status_code = 409
                elif retired_state is not None and parse_qs(
                    urlsplit(target).query,
                    keep_blank_values=True,
                    max_num_fields=12,
                    strict_parsing=True,
                ).get("state") == [retired_state]:
                    status_code = 409
                else:
                    callback_pending.set_result(callback_attempt.consume(target))
                    emit_diagnostic(
                        "auth_callback", "success", operation_id, started, http_status=200
                    )
                    status_code = 200
                    message = "Sign-in callback received. You can close this tab and return to the terminal."
        except AuthError as error:
            if not callback_pending.done():
                callback_pending.set_exception(error)
                emit_diagnostic(
                    "auth_callback", "failure", operation_id, started, error.code, http_status=400
                )
        except (
            ValueError,
            UnicodeError,
            TimeoutError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            if not callback_pending.done():
                callback_pending.set_exception(AuthError("callback_invalid"))
                emit_diagnostic(
                    "auth_callback",
                    "failure",
                    operation_id,
                    started,
                    "callback_invalid",
                    http_status=400,
                )
        finally:
            try:
                body = message.encode("utf-8")
                response = (
                    f"HTTP/1.1 {status_code} Callback\r\nContent-Type: text/plain; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\n"
                    "Content-Security-Policy: default-src 'none'\r\nReferrer-Policy: no-referrer\r\n"
                    "Connection: close\r\n\r\n"
                ).encode() + body
                writer.write(response)
                async with asyncio.timeout(1):
                    await writer.drain()
            except (OSError, TimeoutError):
                pass
            finally:
                writer.close()
                connections.discard(task)

    try:
        async with asyncio.timeout(timeout_seconds):
            metadata = await discovery(client)
            async with store.lock(timeout_seconds):
                host_id = store.host_id()
                previous = store.load()
                if previous and previous.ext_agent_host_id != host_id:
                    raise AuthError("account_mismatch")
            try:
                server = await asyncio.start_server(callback, "127.0.0.1", 0, limit=16_384)
            except OSError:
                raise AuthError("listener_unavailable") from None
            port = server.sockets[0].getsockname()[1]
            selected_client_id = previous.client_id if previous else "dynamic_agent_client"
            # AIDEV-NOTE: invalid_grant discards the code. One fresh authorization
            # keeps its issued client only in this login; identity is not saved
            # until verification. Both attempts share the original total deadline.
            for authorization_index in range(2):
                if authorization_index:
                    pending = asyncio.get_running_loop().create_future()
                attempt = LoginAttempt(
                    selected_client_id,
                    f"http://127.0.0.1:{port}{CALLBACK_PATH}",
                    started + timeout_seconds,
                )
                try:
                    opened = (open_browser or _system_browser)(
                        attempt.authorization_url(host_id, consent)
                    )
                    if inspect.isawaitable(opened):
                        opened = await opened
                except OSError:
                    raise AuthError("browser_unavailable") from None
                if not opened:
                    raise AuthError("browser_unavailable")
                code, issued_client_id = await pending
                status, body = await request_json(
                    client,
                    "POST",
                    TOKEN_ENDPOINT,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": issued_client_id,
                        "code": code,
                        "code_verifier": attempt.verifier,
                        "redirect_uri": attempt.redirect_uri,
                        "resource": RESOURCE,
                    },
                    diagnostic_stage="auth_token_exchange",
                )
                if (
                    status == 400
                    and oauth_error_code(body) == "invalid_grant"
                    and authorization_index == 0
                ):
                    retired_state = attempt.state
                    selected_client_id = issued_client_id
                    code = None
                    emit_diagnostic(
                        "auth_login",
                        "reauthorizing",
                        operation_id,
                        started,
                        http_status=400,
                        reason="oauth_invalid_grant",
                    )
                    continue
                if status != 200:
                    raise AuthError(http_auth_error(status))
                break
            id_token = _string(body.get("id_token"))
            identity = await verify_id_token(
                client, metadata, id_token, issued_client_id, nonce=attempt.nonce
            )
            if previous and (
                identity["sub"] != previous.subject or issued_client_id != previous.client_id
            ):
                raise AuthError("account_mismatch")
            record = credential_from_response(
                body, issued_client_id, host_id, subject=identity["sub"]
            )
            async with store.lock(timeout_seconds):
                if store.load() != previous:
                    raise AuthError("concurrent_update")
                store.save(record)
            emit_diagnostic("auth_login", "success", operation_id, started)
            return store.status()
    except TimeoutError:
        emit_diagnostic("auth_login", "failure", operation_id, started, "login_timeout")
        raise AuthError("login_timeout") from None
    except AuthError as error:
        emit_diagnostic("auth_login", "failure", operation_id, started, error.code)
        raise
    except OSError:
        emit_diagnostic("auth_login", "failure", operation_id, started, "store_unavailable")
        raise AuthError("store_unavailable") from None
    except asyncio.CancelledError:
        emit_diagnostic("auth_login", "cancelled", operation_id, started)
        raise
    finally:
        if server:
            server.close()
            await server.wait_closed()
        for connection in tuple(connections):
            connection.cancel()
        await asyncio.gather(*tuple(connections), return_exceptions=True)
        if not pending.done():
            pending.cancel()
        elif not pending.cancelled():
            pending.exception()


@diagnostic_scope
async def models(store: CredentialStore, client: httpx.AsyncClient) -> dict[str, Any]:
    operation_id, started = request_id(), time.monotonic()
    emit_diagnostic("auth_models", "start", operation_id, started)
    try:
        async with asyncio.timeout(30):
            result = await _list_models(store, client)
        emit_diagnostic("auth_models", "success", operation_id, started)
        return result
    except TimeoutError:
        emit_diagnostic("auth_models", "failure", operation_id, started, "upstream_timeout")
        raise AuthError("upstream_timeout") from None
    except AuthError as error:
        emit_diagnostic("auth_models", "failure", operation_id, started, error.code)
        raise
    except asyncio.CancelledError:
        emit_diagnostic("auth_models", "cancelled", operation_id, started)
        raise


async def _list_models(store: CredentialStore, client: httpx.AsyncClient) -> dict[str, Any]:
    token = await store.access_token(client)
    # AIDEV-NOTE: model capability metadata can exceed the auth-document budget;
    # only this catalog gets a larger bounded read, never token/discovery/JWKS.
    status, body = await request_json(
        client,
        "GET",
        RESOURCE + "/models",
        headers={"Authorization": "Bearer " + token},
        max_bytes=MAX_MODEL_BYTES,
    )
    if status != 200:
        raise AuthError(http_auth_error(status))
    entries = body.get("models")
    if not isinstance(entries, list) or len(entries) > 2048:
        raise AuthError("provider_protocol_error")
    visible = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuthError("provider_protocol_error")
        if entry.get("visibility") == "list":
            slug = _string(entry.get("slug"), limit=256)
            name = entry.get("display_name")
            if not isinstance(name, str) or not name or len(name) > 256:
                raise AuthError("provider_protocol_error")
            visible.append({"slug": slug, "display_name": name})
    return {"profile": store.profile, "models": visible}


@diagnostic_scope
async def logout(
    store: CredentialStore, client: httpx.AsyncClient, *, timeout_seconds: float = 30
) -> dict[str, Any]:
    operation_id, started = request_id(), time.monotonic()
    emit_diagnostic("auth_logout", "start", operation_id, started)
    try:
        async with store.lock(timeout_seconds):
            record = store.load()
            confirmed = None
            if record and record.refresh_token:
                confirmed = False
                try:
                    async with asyncio.timeout(timeout_seconds):
                        metadata = await discovery(client)
                        endpoint = metadata.get("revocation_endpoint")
                        parsed = urlsplit(endpoint) if isinstance(endpoint, str) else None
                        if (
                            not parsed
                            or parsed.scheme != "https"
                            or parsed.netloc != "auth.openai.com"
                            or parsed.query
                            or parsed.fragment
                            or not parsed.path.startswith("/")
                        ):
                            raise AuthError("provider_protocol_error")
                        for attempt in range(2):
                            try:
                                status, _ = await request_json(
                                    client,
                                    "POST",
                                    endpoint,
                                    data={
                                        "token": record.refresh_token,
                                        "token_type_hint": "refresh_token",
                                        "client_id": record.client_id,
                                    },
                                    allow_empty=True,
                                )
                                if status == 200:
                                    confirmed = True
                                    break
                                if status < 500:
                                    break
                            except AuthError as error:
                                if error.code not in {"upstream_timeout", "upstream_unavailable"}:
                                    break
                            if attempt == 0:
                                await asyncio.sleep(0.2)
                except (AuthError, TimeoutError):
                    pass
            if record:
                store.save(clear_tokens(record))
            result = store.status()
            result["remote_revocation_confirmed"] = confirmed
            if confirmed is False:
                result["action"] = (
                    "Remote revocation was not confirmed. Disconnect the app in ChatGPT Settings."
                )
            emit_diagnostic(
                "auth_logout",
                "local_only" if confirmed is False else "success",
                operation_id,
                started,
            )
            return result
    except AuthError as error:
        emit_diagnostic("auth_logout", "failure", operation_id, started, error.code)
        raise
    except asyncio.CancelledError:
        emit_diagnostic("auth_logout", "cancelled", operation_id, started)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Application-owned Sign in with ChatGPT")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("login", "status", "models", "logout"):
        command = commands.add_parser(name)
        command.add_argument("--profile", default=None)
        command.add_argument("--auth-dir", default=None)
        if name == "login":
            command.add_argument("--timeout-seconds", type=float, default=180)
            command.add_argument(
                "--consent",
                action="store_true",
                help="Explicitly ask again for plan usage permission",
            )
    return parser


async def _run_command(args: argparse.Namespace) -> dict[str, Any]:
    store = CredentialStore(args.profile, args.auth_dir)
    if args.command == "status":
        return store.status()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
        if args.command == "login":
            return await login(
                store, client, timeout_seconds=args.timeout_seconds, consent=args.consent
            )
        if args.command == "models":
            return await models(store, client)
        return await logout(store, client)


def main() -> None:
    args = _parser().parse_args()
    try:
        result = asyncio.run(_run_command(args))
        exit_code = 0
    except AuthError as error:
        result = {"error": {"code": error.code, "message": str(error)}}
        exit_code = 1
    except KeyboardInterrupt:
        result = {"error": {"code": "login_timeout", "message": "Operation cancelled."}}
        exit_code = 130
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
