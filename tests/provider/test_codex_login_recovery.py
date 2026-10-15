from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from test_codex_acceptance import METADATA, SCOPES

from grounding.codex_auth import AuthError, CredentialStore, login


@pytest.fixture
def recovery_flow(oidc):
    issue, jwks = oidc

    def build(store, *, failures=((400, "invalid_grant"),), second="success"):
        original = store.path.read_bytes() if store.path.exists() else None
        observed = {"authorizations": [], "forms": [], "replays": [], "opened": asyncio.Event()}
        callbacks = []

        def unchanged():
            assert (store.path.read_bytes() if store.path.exists() else None) == original

        async def transport(request):
            if request.url.path.endswith("openid-configuration"):
                return httpx.Response(200, json=METADATA)
            if request.url.path.endswith("jwks.json"):
                return httpx.Response(200, json=jwks)
            assert str(request.url) == METADATA["token_endpoint"] and request.method == "POST"
            assert request.headers["content-type"] == "application/x-www-form-urlencoded"
            assert "authorization" not in request.headers
            form = parse_qs(request.content.decode(), strict_parsing=True)
            assert set(form) == {
                "grant_type",
                "client_id",
                "code",
                "code_verifier",
                "redirect_uri",
                "resource",
            }
            authorization = observed["authorizations"][-1]
            assert form["grant_type"] == ["authorization_code"]
            assert form["client_id"] == ["oaiapp_test"]
            assert form["code"] == [f"synthetic-code-{len(callbacks)}+/=?&%"]
            assert form["resource"] == authorization["resource"] == ["https://api.openai.com/v1"]
            assert form["redirect_uri"] == authorization["redirect_uri"]
            assert re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", form["code_verifier"][0])
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"][0].encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            assert authorization["code_challenge"] == [challenge]
            observed["forms"].append(form)
            unchanged()
            index = len(observed["forms"]) - 1
            if index < len(failures):
                status, code = failures[index]
                return httpx.Response(
                    status,
                    json={"error": code, "error_description": "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"},
                )
            nonce = observed["authorizations"][0 if second == "old_nonce" else -1]["nonce"][0]
            return httpx.Response(
                200,
                json={
                    "id_token": issue(
                        nonce,
                        sub="other-account" if second == "wrong_account" else "synthetic-account",
                    ),
                    "access_token": "synthetic-new-access",
                    "refresh_token": "synthetic-new-refresh",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": SCOPES,
                },
            )

        async def browser(url):
            unchanged()
            params = parse_qs(urlsplit(url).query)
            observed["authorizations"].append(params)
            count = len(observed["authorizations"])
            if count > 1:
                observed["opened"].set()
                assert params["client_id"] == ["oaiapp_test"]
                assert "agent_name_hint" not in params
                for field in ("state", "nonce", "code_challenge"):
                    assert params[field] != observed["authorizations"][0][field]
                assert (
                    params["ext_agent_host_id"]
                    == observed["authorizations"][0]["ext_agent_host_id"]
                )
                if second == "wait":
                    await asyncio.Event().wait()
                if second == "browser_failure":
                    raise OSError("PROVIDER_SECRET_MARKER_DO_NOT_EMIT")
            callback_params = {"state": params["state"][0], "code": f"synthetic-code-{count}+/=?&%"}
            if count == 1:
                callback_params["client_id"] = "oaiapp_test"
            elif second == "client_mismatch":
                callback_params["client_id"] = "oaiapp_other"
            callback_url = params["redirect_uri"][0] + "?" + urlencode(callback_params)
            async with httpx.AsyncClient(trust_env=False, timeout=2) as local:
                if count == 2:
                    replay = await local.get(callbacks[0])
                    observed["replays"].append(replay.status_code)
                    assert replay.status_code == 409
                response = await local.get(callback_url)
                assert response.status_code == (
                    400 if second == "client_mismatch" and count == 2 else 200
                )
            callbacks.append(callback_url)
            return True

        async def run(*, timeout_seconds=3):
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                return await login(
                    store, client, open_browser=browser, timeout_seconds=timeout_seconds
                )

        return run, observed, unchanged

    return build


@pytest.mark.parametrize("registered", [False, True])
async def test_invalid_grant_starts_one_fresh_authorization_with_issued_client(
    tmp_path, credentials, recovery_flow, capfd, registered
):
    store = credentials if registered else CredentialStore(auth_dir=tmp_path / "new-profile")
    run, observed, _ = recovery_flow(store)
    result = await run()
    assert result["signed_in"] and result["plan_enabled"]
    assert len(observed["authorizations"]) == len(observed["forms"]) == 2
    assert observed["replays"] == [409]
    assert observed["forms"][0]["code_verifier"] != observed["forms"][1]["code_verifier"]
    assert store.load().client_id == "oaiapp_test" and store.load().subject == "synthetic-account"
    output = capfd.readouterr()
    records = [json.loads(line) for line in output.err.splitlines()]
    progress = [item for item in records if item["outcome"] == "reauthorizing"]
    assert len(progress) == 1 and progress[0]["event"] == "progress"
    assert progress[0]["stage"] == "auth_login" and progress[0]["reason"] == "oauth_invalid_grant"
    assert len({item["request_id"] for item in records}) == 1
    assert records[-1]["stage"] == "auth_login" and records[-1]["outcome"] == "success"
    assert all(
        marker not in output.err + output.out
        for marker in ("synthetic-", "eyJ", "PROVIDER_SECRET_MARKER_DO_NOT_EMIT")
    )


@pytest.mark.parametrize("registered", [False, True])
async def test_second_invalid_grant_stops_and_preserves_active_profile(
    tmp_path, credentials, recovery_flow, registered
):
    store = credentials if registered else CredentialStore(auth_dir=tmp_path / "new-profile")
    run, observed, unchanged = recovery_flow(store, failures=((400, "invalid_grant"),) * 2)
    with pytest.raises(AuthError) as error:
        await run()
    assert error.value.code == "authentication_failed"
    assert len(observed["authorizations"]) == len(observed["forms"]) == 2
    unchanged()


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (400, "invalid_client", "authentication_failed"),
        (400, "unknown-provider-text", "authentication_failed"),
        (500, "invalid_grant", "upstream_unavailable"),
        (403, "access_denied", "authentication_failed"),
    ],
)
async def test_other_exchange_failures_do_not_open_another_browser(
    credentials, recovery_flow, status, code, expected
):
    run, observed, unchanged = recovery_flow(credentials, failures=((status, code),))
    with pytest.raises(AuthError) as error:
        await run()
    assert error.value.code == expected
    assert len(observed["authorizations"]) == len(observed["forms"]) == 1
    unchanged()


@pytest.mark.parametrize(
    "second,code",
    [
        ("client_mismatch", "account_mismatch"),
        ("old_nonce", "authentication_failed"),
        ("wrong_account", "account_mismatch"),
        ("browser_failure", "browser_unavailable"),
    ],
)
async def test_reauthorization_keeps_binding_and_verification_failures_terminal(
    credentials, recovery_flow, second, code
):
    run, observed, unchanged = recovery_flow(credentials, second=second)
    with pytest.raises(AuthError) as error:
        await run()
    assert error.value.code == code and len(observed["authorizations"]) == 2
    assert len(observed["forms"]) == (1 if second in {"client_mismatch", "browser_failure"} else 2)
    unchanged()


async def test_cancellation_during_reauthorization_closes_listener(credentials, recovery_flow):
    run, observed, unchanged = recovery_flow(credentials, second="wait")
    task = asyncio.create_task(run())
    try:
        async with asyncio.timeout(3):
            await observed["opened"].wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert len(observed["authorizations"]) == 2 and len(observed["forms"]) == 1
    unchanged()
    async with httpx.AsyncClient(trust_env=False, timeout=0.1) as local:
        with pytest.raises(httpx.ConnectError):
            await local.get(observed["authorizations"][-1]["redirect_uri"][0])


async def test_existing_total_login_deadline_covers_reauthorization(credentials, recovery_flow):
    run, observed, unchanged = recovery_flow(credentials, second="wait")
    with pytest.raises(AuthError) as error:
        await run(timeout_seconds=1)
    assert error.value.code == "login_timeout"
    assert len(observed["authorizations"]) == 2 and len(observed["forms"]) == 1
    unchanged()
