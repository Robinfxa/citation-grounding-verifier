"""Explicit subprocess-only network/browser substitutes; never used by production."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit


def model_catalog_payload(size: int) -> bytes:
    body = {
        "models": [
            {
                "slug": f"fixture-model-{index}",
                "display_name": f"Offline model {index}",
                "visibility": "list" if index < 7 else "hidden",
            }
            for index in range(9)
        ]
    }
    body["models"][0]["capabilities"] = "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"
    encoded = json.dumps(body, separators=(",", ":")).encode()
    body["models"][0]["capabilities"] += "x" * (size - len(encoded))
    encoded = json.dumps(body, separators=(",", ":")).encode()
    assert len(encoded) == size
    return encoded


def install() -> None:
    phase_path = os.environ.get("PROVIDER_PROBE_PHASE_FILE")

    def phase(name):
        if phase_path:
            with Path(phase_path).open("a") as stream:
                stream.write(json.dumps({"phase": name, "time": time.monotonic()}) + "\n")

    phase("hook_start")
    import httpx
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    import grounding.codex_auth as auth

    phase("imports_ready")

    scenario = os.environ.get("PROVIDER_PROBE_SCENARIO", "success")
    original_client = httpx.AsyncClient
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    phase("key_ready")
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    key.update(kid="cli-fixture", use="sig", alg="RS256")
    pending = {}
    token_calls = 0
    browser_calls = 0
    marker = "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"

    def transport(request):
        nonlocal token_calls
        if scenario == "network_failure":
            raise httpx.ConnectError(marker)
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": auth.ISSUER,
                    "authorization_endpoint": auth.AUTHORIZE_ENDPOINT,
                    "token_endpoint": auth.TOKEN_ENDPOINT,
                    "jwks_uri": auth.JWKS_URI,
                    "revocation_endpoint": auth.ISSUER + "/api/accounts/oauth/revoke",
                },
            )
        if request.url.path.endswith("jwks.json"):
            if scenario == "jwks_rejected":
                return httpx.Response(403, json={"detail": marker})
            return httpx.Response(200, json={"keys": [key]})
        if request.url.path.endswith("/token"):
            token_calls += 1
            phase("token_exchange")
            form = parse_qs(request.content.decode())
            if scenario == "token_rejected" or (
                scenario == "invalid_grant_recovery" and token_calls == 1
            ):
                return httpx.Response(
                    400, json={"error": "invalid_grant", "error_description": marker}
                )
            body = {
                "access_token": "synthetic-cli-access",
                "refresh_token": "synthetic-cli-refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": auth.REQUESTED_SCOPES,
            }
            if form["grant_type"] == ["refresh_token"]:
                counter = os.environ.get("PROVIDER_PROBE_COUNTER")
                if counter:
                    with Path(counter).open("a") as stream:
                        stream.write("refresh\n")
                    time.sleep(0.15)
                body.update(
                    access_token="synthetic-rotated-access",
                    refresh_token="synthetic-rotated-refresh",
                )
            else:
                now = int(time.time())
                body["id_token"] = jwt.encode(
                    {
                        "iss": auth.ISSUER,
                        "aud": form["client_id"][0],
                        "sub": "synthetic-account",
                        "iat": now,
                        "exp": now + 3600,
                        "nonce": "synthetic-wrong-nonce"
                        if scenario == "jwt_nonce"
                        else pending["nonce"][0],
                    },
                    signing_key,
                    algorithm="RS256",
                    headers={"kid": "cli-fixture"},
                )
                if scenario == "missing_scope":
                    body = {"id_token": body["id_token"], "scope": "openid profile email"}
            return httpx.Response(200, json=body)
        if request.url.path == "/v1/models":
            if scenario == "large_catalog":
                return httpx.Response(200, content=model_catalog_payload(568_595))
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "slug": "fixture-model",
                            "display_name": "Offline fixture model",
                            "visibility": "list",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/revoke"):
            return (
                httpx.Response(503, json={"detail": marker})
                if scenario == "revocation_failure"
                else (httpx.Response(200))
            )
        raise AssertionError("Offline fixture received an unexpected endpoint")

    class OfflineClient(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(transport)
            super().__init__(*args, **kwargs)

    async def browser(url):
        nonlocal browser_calls
        browser_calls += 1
        phase("browser_substitute")
        pending.clear()
        pending.update(parse_qs(urlsplit(url).query))
        selected = pending["client_id"][0]
        params = {
            "state": pending["state"][0],
            "code": f"synthetic-cli-code-{browser_calls}",
            "client_id": "oaiapp_test" if selected == "dynamic_agent_client" else selected,
        }
        if scenario == "callback_denied":
            params["error"] = "access_denied"
        async with original_client(trust_env=False, timeout=2) as local:
            response = await local.get(pending["redirect_uri"][0] + "?" + urlencode(params))
        assert response.status_code in {200, 400}
        phase("callback_received")
        return True

    httpx.AsyncClient = OfflineClient
    auth._system_browser = browser
    original_main = auth.main

    def main():
        phase("main_enter")
        try:
            return original_main()
        finally:
            phase("main_exit")

    auth.main = main
    if os.environ.get("PROVIDER_PROBE_FAIL_SINK") == "1":
        original_write = os.write

        def write(fd, value):
            if fd == 2:
                raise OSError(marker)
            return original_write(fd, value)

        os.write = write
    phase("hook_ready")
