from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
from cli_timing import PROCESS_TIMEOUT_SECONDS
from cryptography.hazmat.primitives.asymmetric import rsa
from test_codex_acceptance import METADATA, SCOPES

from grounding.codex_auth import (
    AuthError,
    CredentialStore,
    LoginAttempt,
    login,
    logout,
    models,
    verify_id_token,
)


@pytest.fixture
def flow(oidc):
    issue, jwks = oidc

    async def run(
        store,
        *,
        claims=None,
        callback_client=None,
        state=None,
        error=None,
        response_overrides=None,
        token_status=200,
        scope=SCOPES,
        before_save=None,
    ):
        requests = []
        pending = {}
        browser_calls = 0

        async def transport(request):
            requests.append(request)
            if request.url.path.endswith("openid-configuration"):
                return httpx.Response(200, json=METADATA)
            if request.url.path.endswith("jwks.json"):
                return httpx.Response(200, json=jwks)
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["oaiapp_test"]
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            if before_save:
                await before_save()
            body = {
                "id_token": issue(pending["nonce"][0], **(claims or {})),
                "access_token": "synthetic-new-access",
                "refresh_token": "synthetic-new-refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": scope,
            }
            body.update(response_overrides or {})
            return httpx.Response(200, json=body)

        async def browser(url):
            nonlocal browser_calls
            browser_calls += 1
            pending.clear()
            pending.update(parse_qs(urlsplit(url).query))
            assert "id_token_hint" not in pending and "login_hint" not in pending
            if pending["client_id"][0] != "dynamic_agent_client":
                assert "agent_name_hint" not in pending
            params = {
                "state": state or pending["state"][0],
                "code": f"synthetic-code-{browser_calls}",
            }
            if callback_client is not None:
                params["client_id"] = callback_client
            elif pending["client_id"][0] == "dynamic_agent_client":
                params["client_id"] = "oaiapp_test"
            if error:
                params["error"] = error
            async with httpx.AsyncClient(trust_env=False) as local:
                await local.get(pending["redirect_uri"][0] + "?" + urlencode(params))
            return True

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            result = await login(store, client, open_browser=browser, timeout_seconds=2)
        return result, requests, pending

    return run


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "oaiapp_wrong"},
        {"nonce": "wrong-nonce"},
        {"exp": 1},
        {"iat": int(time.time()) + 3600},
        {"sub": ""},
        {"sub": None},
        {"sub": 7},
        {"aud": ["oaiapp_test", "second-client"]},
        {"azp": "wrong-client"},
    ],
)
async def test_id_token_rejects_invalid_claims(oidc, changes):
    issue, jwks = oidc
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=jwks))
    )
    async with client:
        with pytest.raises(AuthError) as error:
            await verify_id_token(
                client, METADATA, issue("expected", **changes), "oaiapp_test", "expected"
            )
    assert error.value.code == "authentication_failed"


async def test_signature_and_unsigned_tokens_rejected(oidc):
    issue, jwks = oidc
    claims = jwt.decode(issue("nonce"), options={"verify_signature": False})
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    candidates = [
        jwt.encode(claims, wrong_key, algorithm="RS256", headers={"kid": "local-test"}),
        jwt.encode(claims, key="", algorithm="none", headers={"kid": "local-test"}),
        jwt.encode(
            claims,
            key="synthetic-secret-key-32-bytes-long",
            algorithm="HS256",
            headers={"kid": "local-test"},
        ),
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=jwks))
    ) as client:
        for token in candidates:
            with pytest.raises(AuthError):
                await verify_id_token(client, METADATA, token, "oaiapp_test", "nonce")


async def test_returning_sign_in_reuses_registration_and_host(credentials, flow):
    previous = credentials.load()
    result, _, params = await flow(credentials)
    assert result["plan_enabled"]
    assert params["client_id"] == [previous.client_id]
    assert params["ext_agent_host_id"] == [previous.ext_agent_host_id]
    assert credentials.load().subject == previous.subject


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"claims": {"sub": "different-account"}}, "account_mismatch"),
        ({"callback_client": "oaiapp_other"}, "account_mismatch"),
        ({"claims": {"nonce": "wrong"}}, "authentication_failed"),
        ({"state": "wrong-state"}, "state_mismatch"),
        ({"error": "access_denied"}, "authorization_denied"),
        ({"token_status": 400}, "authentication_failed"),
    ],
)
async def test_failed_login_never_replaces_valid_profile(credentials, flow, kwargs, code):
    old = credentials.path.read_bytes()
    with pytest.raises(AuthError) as error:
        await flow(credentials, **kwargs)
    assert error.value.code == code
    assert credentials.path.read_bytes() == old


@pytest.mark.parametrize(
    "kwargs,stage,reason,status",
    [
        ({"token_status": 400}, "auth_token_exchange", "oauth_invalid_grant", 400),
        ({"claims": {"nonce": "wrong"}}, "auth_id_token", "jwt_nonce", None),
        ({"claims": {"aud": "wrong"}}, "auth_id_token", "jwt_audience", None),
        ({"claims": {"iss": "https://attacker.invalid"}}, "auth_id_token", "jwt_issuer", None),
        ({"claims": {"exp": 1}}, "auth_id_token", "jwt_expired", None),
    ],
)
async def test_login_authentication_failure_identifies_safe_boundary(
    credentials, flow, capfd, kwargs, stage, reason, status
):
    old = credentials.path.read_bytes()
    with pytest.raises(AuthError) as error:
        await flow(credentials, **kwargs)
    assert error.value.code == "authentication_failed" and credentials.path.read_bytes() == old
    output = capfd.readouterr()
    records = [json.loads(line) for line in output.err.splitlines()]
    identified = [
        record for record in records if record["stage"] == stage and record["outcome"] == "failure"
    ]
    assert len(identified) == (2 if kwargs.get("token_status") == 400 else 1)
    assert all(
        item["reason"] == reason and item.get("http_status") == status for item in identified
    )
    assert records[-1]["stage"] == "auth_login" and records[-1]["outcome"] == "failure"
    assert len({record["request_id"] for record in records}) == 1
    assert "synthetic-" not in output.err + output.out and "eyJ" not in output.err


async def test_jwks_http_rejection_is_distinct_and_redacted(oidc, capfd):
    issue, _ = oidc
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403, json={"detail": "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"}
            )
        )
    ) as client:
        with pytest.raises(AuthError) as error:
            await verify_id_token(client, METADATA, issue("nonce"), "oaiapp_test", "nonce")
    assert error.value.code == "authentication_failed"
    output = capfd.readouterr()
    records = [json.loads(line) for line in output.err.splitlines()]
    assert len(records) == 2 and records[-1]["stage"] == "auth_jwks"
    assert records[-1]["http_status"] == 403 and records[-1]["reason"] == "http_rejected"
    assert "PROVIDER_SECRET_MARKER_DO_NOT_EMIT" not in output.err and "eyJ" not in output.err


def test_auth_diagnostic_metadata_is_allowlisted_and_rejects_injection(capfd):
    from grounding.codex_auth import emit_diagnostic
    from grounding.diagnostics import operation

    marker = "PROVIDER_SECRET_MARKER_DO_NOT_EMIT\nFORGED"
    with operation(enabled=True, new=True) as current:
        emit_diagnostic(
            "auth_id_token",
            "failure",
            current.request_id,
            0,
            "authentication_failed",
            reason=marker,
            http_status=marker,
        )
        emit_diagnostic(
            "auth_id_token",
            "failure",
            current.request_id,
            0,
            "authentication_failed",
            reason={"raw": marker},
            http_status=True,
        )
    output = capfd.readouterr()
    records = [json.loads(line) for line in output.err.splitlines()]
    assert len(records) == 2 and all(
        "reason" not in record and "http_status" not in record for record in records
    )
    assert marker not in output.err and "FORGED" not in output.err


async def test_missing_plan_permission_preserves_identity_only_login(tmp_path, flow):
    store = CredentialStore(auth_dir=tmp_path / "credentials")
    result, _, _ = await flow(
        store,
        scope="openid profile email",
        response_overrides={
            "access_token": None,
            "refresh_token": None,
            "expires_in": None,
            "token_type": None,
        },
    )
    assert result["signed_in"] and not result["plan_enabled"] and not result["renewable"]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("Identity-only login cannot start inference")
        )
    ) as client:
        with pytest.raises(AuthError) as error:
            await store.access_token(client)
    assert error.value.code == "plan_not_authorized"


async def test_concurrent_login_change_is_preserved(credentials, flow):
    async def update():
        async with credentials.lock():
            credentials.save(replace(credentials.load(), access_token="synthetic-other-access"))

    with pytest.raises(AuthError) as error:
        await flow(credentials, before_save=update)
    assert error.value.code == "concurrent_update"
    assert credentials.load().access_token == "synthetic-other-access"


def test_state_expiry_mismatch_replay_and_duplicate_parameters():
    def attempt():
        return LoginAttempt(
            "dynamic_agent_client", "http://127.0.0.1:1234/auth/callback", time.monotonic() + 5
        )

    current = attempt()
    query = urlencode(
        {"state": current.state, "code": "synthetic-code", "client_id": "oaiapp_test"}
    )
    target = "/auth/callback?" + query
    assert current.consume(target) == ("synthetic-code", "oaiapp_test")
    with pytest.raises(AuthError):
        current.consume(target)
    current = attempt()
    current.expires_at = time.monotonic() - 1
    with pytest.raises(AuthError):
        current.consume(target)
    current = attempt()
    with pytest.raises(AuthError):
        current.consume(
            "/auth/callback?state=wrong&state=duplicate&code=secret&client_id=oaiapp_test"
        )
    current = attempt()
    with pytest.raises(AuthError):
        current.consume("/auth/callback?" + urlencode({"state": current.state, "code": "code"}))


async def test_login_timeout_closes_listener_and_preserves_credentials(credentials, oidc):
    old = credentials.path.read_bytes()
    callbacks = []

    def browser(url):
        callbacks.append(parse_qs(urlsplit(url).query)["redirect_uri"][0])
        return True

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=METADATA))
    ) as client:
        with pytest.raises(AuthError) as error:
            await login(credentials, client, open_browser=browser, timeout_seconds=0.1)
    assert error.value.code == "login_timeout" and credentials.path.read_bytes() == old
    async with httpx.AsyncClient(trust_env=False, timeout=0.1) as local:
        with pytest.raises(httpx.ConnectError):
            await local.get(callbacks[0])


async def test_browser_open_failure_is_distinct_and_keeps_existing_tokens(credentials):
    original = credentials.path.read_bytes()

    def browser(url):
        raise OSError("PROVIDER_SECRET_MARKER_DO_NOT_EMIT")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=METADATA))
    ) as client:
        with pytest.raises(AuthError) as error:
            await login(credentials, client, open_browser=browser, timeout_seconds=1)
    assert error.value.code == "browser_unavailable" and credentials.path.read_bytes() == original


async def test_loopback_bind_failure_is_distinct(credentials, monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("PROVIDER_SECRET_MARKER_DO_NOT_EMIT")

    monkeypatch.setattr(asyncio, "start_server", fail)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=METADATA))
    ) as client:
        with pytest.raises(AuthError) as error:
            await login(credentials, client, open_browser=lambda url: pytest.fail("No listener"))
    assert error.value.code == "listener_unavailable"


def test_non_ascii_and_newline_credentials_fail_before_header_construction(credentials):
    for token in ("synthetic-Ā-token", "synthetic-token\nforged"):
        credentials.save(replace(credentials.load(), access_token=token))
        with pytest.raises(AuthError) as error:
            credentials.load()
        assert error.value.code == "store_unavailable"
        # Restore a valid record without reading the deliberately invalid file.
        data = json.loads(credentials.path.read_bytes())
        data["access_token"] = "synthetic-access"
        credentials._atomic_json(credentials.path, data)


async def test_rotating_refresh_is_serialized_and_reread_between_two_stores(credentials):
    credentials.save(replace(credentials.load(), expires_at=0))
    second = CredentialStore(auth_dir=credentials.directory)
    requests = []

    async def transport(request):
        requests.append(request)
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["refresh_token"]
        assert form["client_id"] == ["oaiapp_test"]
        assert form["refresh_token"] == ["synthetic-refresh"]
        assert form["resource"] == ["https://api.openai.com/v1"] and "scope" not in form
        await asyncio.sleep(0.03)
        return httpx.Response(
            200,
            json={
                "access_token": "synthetic-rotated-access",
                "refresh_token": "synthetic-rotated-refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": SCOPES,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        tokens = await asyncio.gather(credentials.access_token(client), second.access_token(client))
    assert tokens == ["synthetic-rotated-access"] * 2 and len(requests) == 1
    assert second.load().refresh_token == "synthetic-rotated-refresh"
    assert second.load().expires_at > time.time() + 3000


@pytest.mark.parametrize(
    "code,cleared",
    [
        ("invalid_grant", True),
        ("refresh_token_reused", True),
        ("invalid_client", False),
    ],
)
async def test_refresh_terminal_error_policy(credentials, code, cleared):
    credentials.save(replace(credentials.load(), expires_at=0))
    original = credentials.load()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": code, "detail": "synthetic-secret"})
        )
    ) as client:
        with pytest.raises(AuthError):
            await credentials.access_token(client)
    actual = credentials.load()
    assert actual.client_id == original.client_id and actual.subject == original.subject
    assert (actual.refresh_token is None) is cleared


async def test_temporary_refresh_failure_and_cancel_keep_credentials_and_unlock(credentials):
    credentials.save(replace(credentials.load(), expires_at=0))
    original = credentials.path.read_bytes()
    entered = asyncio.Event()

    async def failing(request):
        return httpx.Response(503, json={"detail": "synthetic-secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(failing)) as client:
        with pytest.raises(AuthError) as error:
            await credentials.access_token(client)
    assert error.value.code == "upstream_unavailable" and credentials.path.read_bytes() == original

    async def suspended(request):
        entered.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=httpx.MockTransport(suspended)) as client:
        task = asyncio.create_task(credentials.access_token(client))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    other = CredentialStore(auth_dir=credentials.directory)
    async with other.lock(0.1):
        assert other.path.read_bytes() == original


async def test_refresh_scope_change_saved_and_blocks_inference(credentials):
    credentials.save(replace(credentials.load(), expires_at=0))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "access_token": "synthetic-new",
                    "refresh_token": "synthetic-next",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid resource.invoke",
                },
            )
        )
    ) as client:
        with pytest.raises(AuthError) as error:
            await credentials.access_token(client)
    assert error.value.code == "plan_not_authorized"
    assert (
        credentials.load().refresh_token == "synthetic-next"
        and not credentials.status()["plan_enabled"]
    )


async def test_earliest_refresh_is_respected(credentials):
    credentials.save(
        replace(
            credentials.load(), expires_at=time.time() + 20, earliest_refresh_at=time.time() + 10
        )
    )

    def no_network(request):
        raise AssertionError("Too early to refresh")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        assert await credentials.access_token(client) == "synthetic-access"


def test_atomic_failure_keeps_previous_file_and_owner_permissions(credentials, monkeypatch):
    previous = credentials.path.read_bytes()
    assert stat.S_IMODE(credentials.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(credentials.path.stat().st_mode) == 0o600
    assert stat.S_IMODE((credentials.directory / "host.json").stat().st_mode) == 0o600

    def fail(*args):
        raise OSError("synthetic-secret-from-filesystem")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(AuthError) as error:
        credentials.save(replace(credentials.load(), access_token="synthetic-new"))
    assert error.value.code == "store_unavailable"
    assert credentials.path.read_bytes() == previous
    assert not list(credentials.directory.glob(".pending-*"))


@pytest.mark.parametrize(
    "profile", ["../default", "UPPER", "a/b", "a\\b", ".", "", "a" * 65, "hello\nforged", "á"]
)
def test_profile_path_safety(tmp_path, profile):
    with pytest.raises(AuthError):
        CredentialStore(profile=profile, auth_dir=tmp_path / "credentials")


def test_insecure_permissions_and_symlink_are_rejected(credentials, tmp_path):
    credentials.path.chmod(0o644)
    with pytest.raises(AuthError) as error:
        credentials.status()
    assert error.value.code == "insecure_store"
    credentials.path.chmod(0o600)
    linked = tmp_path / "link"
    linked.symlink_to(credentials.directory, target_is_directory=True)
    with pytest.raises(AuthError):
        CredentialStore(auth_dir=linked).status()


def test_public_checkout_rejects_in_repo_auth_without_private_workflow_markers(
    tmp_path, monkeypatch
):
    project = tmp_path / "public-checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "citation-grounding-verifier"\n')
    assert not (project / "AGENTS.md").exists()
    monkeypatch.chdir(project)
    with pytest.raises(AuthError) as error:
        CredentialStore(auth_dir="tokens")
    assert error.value.code == "insecure_store" and not (project / "tokens").exists()


async def test_profiles_with_same_account_stay_distinct(credentials):
    another = CredentialStore(profile="second", auth_dir=credentials.directory)
    async with another.lock():
        another.save(replace(credentials.load(), client_id="oaiapp_second"))
    assert another.load().subject == credentials.load().subject
    assert another.load().client_id != credentials.load().client_id


@pytest.mark.parametrize(
    "remote_status,expected,calls", [(200, True, 1), (503, False, 2), (400, False, 1)]
)
async def test_logout_revokes_before_clear_and_retains_mapping(
    credentials, remote_status, expected, calls
):
    original = credentials.load()
    revoked = []

    def transport(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=METADATA)
        form = parse_qs(request.content.decode())
        assert form == {
            "token": [original.refresh_token],
            "token_type_hint": ["refresh_token"],
            "client_id": [original.client_id],
        }
        assert credentials.load().refresh_token == original.refresh_token
        revoked.append(request)
        return httpx.Response(remote_status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await logout(credentials, client)
    actual = credentials.load()
    assert result["remote_revocation_confirmed"] is expected and len(revoked) == calls
    assert actual.id_token is actual.access_token is actual.refresh_token is None
    assert (
        actual.client_id == original.client_id
        and actual.ext_agent_host_id == original.ext_agent_host_id
    )
    assert ("action" in result) is (not expected)


async def test_logout_discovery_network_failure_clears_local_tokens(credentials):
    def transport(request):
        raise httpx.ConnectError("synthetic-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await logout(credentials, client)
    assert not result["signed_in"] and result["remote_revocation_confirmed"] is False


async def test_logout_local_write_failure_is_not_reported_as_success(credentials, monkeypatch):
    original = credentials.path.read_bytes()

    def transport(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=METADATA)
        return httpx.Response(200)

    def fail(*args):
        raise AuthError("store_unavailable")

    monkeypatch.setattr(credentials, "save", fail)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(AuthError) as error:
            await logout(credentials, client)
    assert error.value.code == "store_unavailable" and credentials.path.read_bytes() == original


def test_credential_and_pending_transaction_repr_exclude_secrets(credentials):
    assert "synthetic-" not in repr(credentials.load())
    attempt = LoginAttempt(
        "oaiapp_test", "http://127.0.0.1:1234/auth/callback", time.monotonic() + 5
    )
    for value in (attempt.state, attempt.verifier, attempt.nonce):
        assert value not in repr(attempt)


async def test_visible_model_catalog_is_account_scoped(credentials):
    def transport(request):
        assert request.url.path == "/v1/models"
        assert request.headers["authorization"] == "Bearer synthetic-access"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"visibility": "list", "slug": "second", "display_name": "Second model"},
                    {"visibility": "hidden", "slug": "hidden", "display_name": "Hidden"},
                    {"visibility": "list", "slug": "first", "display_name": "First model"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await models(credentials, client)
    assert [model["slug"] for model in result["models"]] == ["second", "first"]


def test_public_cli_status_failure_and_logout_are_secret_free(credentials, tmp_path):
    env = dict(os.environ, GROUNDING_AUTH_DIR=str(credentials.directory))
    hook = tmp_path / "timing-hook"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text("from cli_timing import install\ninstall()\n")
    from pathlib import Path

    env["PYTHONPATH"] = os.pathsep.join([str(hook), str(Path(__file__).parent)])
    phase_file = tmp_path / "plain-cli-phases.jsonl"
    env["PROVIDER_PROBE_PHASE_FILE"] = str(phase_file)
    executable = str(
        __import__("pathlib").Path(__import__("sys").executable).with_name("grounding-auth")
    )
    status = subprocess.run(
        [executable, "status"],
        env=env,
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )
    assert status.returncode == 0 and json.loads(status.stdout)["signed_in"]
    try:
        missing = subprocess.run(
            [executable, "models", "--profile", "missing"],
            env=env,
            capture_output=True,
            text=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        phases = phase_file.read_text() if phase_file.exists() else "before Python startup"
        pytest.fail("Unmodified CLI timeout; safe startup phases: " + phases)
    assert (
        missing.returncode == 1 and json.loads(missing.stdout)["error"]["code"] == "not_configured"
    )
    # A retained registration without tokens signs out locally without any network.
    from grounding.codex_auth import clear_tokens

    credentials.save(clear_tokens(credentials.load()))
    logged_out = subprocess.run(
        [executable, "logout"],
        env=env,
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )
    assert logged_out.returncode == 0 and not json.loads(logged_out.stdout)["signed_in"]
    for output in (status, missing, logged_out):
        assert "synthetic-" not in output.stdout + output.stderr
        assert "Traceback" not in output.stdout + output.stderr
