from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from grounding.codex_auth import CredentialStore, login
from grounding.codex_provider import CodexProvider
from grounding.contracts import ProviderResult, StructuredRequest, VerificationError

SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
METADATA = {
    "issuer": "https://auth.openai.com",
    "authorization_endpoint": "https://auth.openai.com/api/accounts/authorize",
    "token_endpoint": "https://auth.openai.com/api/accounts/oauth/token",
    "jwks_uri": "https://auth.openai.com/.well-known/jwks.json",
    "revocation_endpoint": "https://auth.openai.com/api/accounts/oauth/revoke",
}


async def register(store, oidc, *, scope=SCOPES):
    issue, jwks = oidc
    pending = {}

    async def transport(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=METADATA)
        if request.url.path.endswith("jwks.json"):
            return httpx.Response(200, json=jwks)
        if request.url.path.endswith("/token"):
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["oaiapp_test"]
            assert form["resource"] == ["https://api.openai.com/v1"]
            assert form["redirect_uri"] == pending["redirect_uri"]
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"][0].encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            assert pending["code_challenge"] == [challenge]
            return httpx.Response(
                200,
                json={
                    "access_token": "synthetic-access",
                    "refresh_token": "synthetic-refresh",
                    "id_token": issue(pending["nonce"][0]),
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": scope,
                },
            )
        raise AssertionError("Unexpected external boundary")

    async def browser(url):
        pending.update(parse_qs(urlsplit(url).query))
        assert pending["client_id"] == ["dynamic_agent_client"]
        assert "id_token_hint" not in pending
        callback = pending["redirect_uri"][0]
        assert callback.startswith("http://127.0.0.1:") and callback.endswith("/auth/callback")
        async with httpx.AsyncClient(trust_env=False) as loopback:
            response = await loopback.get(
                callback
                + "?"
                + urlencode(
                    {
                        "state": pending["state"][0],
                        "code": "synthetic-code",
                        "client_id": "oaiapp_test",
                    }
                )
            )
            replay = await loopback.get(str(response.request.url))
        assert response.status_code == 200
        assert replay.status_code == 409
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        return await login(store, client, open_browser=browser, timeout_seconds=3)


async def test_public_loopback_login_and_exact_structured_inference(tmp_path, oidc):
    store = CredentialStore(auth_dir=tmp_path / "credentials")
    status = await register(store, oidc)
    assert status["signed_in"] and status["plan_enabled"]
    calls = []
    final = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": '{"ok":true}'}],
            }
        ],
    }

    def transport(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["store"] is False and body["stream"] is True
        assert body["instructions"] == "Return the requested object."
        assert body["text"]["format"]["strict"] is True
        assert body["input"][0]["role"] == "user"
        assert (
            not {"max_output_tokens", "temperature", "tools", "previous_response_id"} & body.keys()
        )
        assert request.headers["authorization"] == "Bearer synthetic-access"
        data = {"type": "response.completed", "response": final}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {json.dumps(data)}\n\n",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider(
            "visible-model",
            auth_store=store,
            client=client,
            parser=lambda data: ProviderResult(text=json.dumps(data)),
        )
        result = await provider.generate(
            StructuredRequest(
                "test_schema", {"type": "object"}, "Return the requested object.", {"data": "hello"}
            )
        )
        await provider.aclose()
        assert not client.is_closed
    assert json.loads(result.text) == final and len(calls) == 1


async def test_scope_missing_retains_identity_and_prevents_network(tmp_path, oidc):
    store = CredentialStore(auth_dir=tmp_path / "credentials")
    status = await register(store, oidc, scope="openid profile email")
    assert status["signed_in"] and not status["plan_enabled"]

    def no_network(request):
        raise AssertionError("Inference must not start without permission")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        provider = CodexProvider("visible-model", auth_store=store, client=client)
        with pytest.raises(VerificationError) as error:
            await provider.generate(StructuredRequest("x", {}, "rules", {}))
    assert error.value.code == "plan_not_authorized"
