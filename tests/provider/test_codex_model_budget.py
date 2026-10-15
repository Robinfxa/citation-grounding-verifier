from __future__ import annotations

import json

import httpx
import pytest
from cli_fixture import model_catalog_payload
from test_codex_stream import Chunks

from grounding.codex_auth import AuthError, models, request_json


@pytest.mark.parametrize("size", [568_595, 1_048_576])
async def test_public_models_accepts_large_valid_catalog_within_own_budget(
    credentials, capfd, size
):
    payload = model_catalog_payload(size)
    stream = Chunks([payload[index : index + 16_384] for index in range(0, len(payload), 16_384)])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        result = await models(credentials, client)
    assert [entry["slug"] for entry in result["models"]] == [
        f"fixture-model-{index}" for index in range(7)
    ]
    assert stream.closed
    captured = capfd.readouterr()
    assert "PROVIDER_SECRET_MARKER_DO_NOT_EMIT" not in captured.out + captured.err
    assert json.loads(captured.err.splitlines()[-1])["outcome"] == "success"


async def test_public_models_rejects_catalog_above_own_budget_and_closes_stream(credentials):
    payload = model_catalog_payload(1_048_577)
    stream = Chunks([payload], failure=AssertionError("Must stop reading after the budget"))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        with pytest.raises(AuthError) as error:
            await models(credentials, client)
    assert error.value.code == "provider_protocol_error"
    assert error.value.diagnostic_reason == "response_too_large" and stream.closed


@pytest.mark.parametrize(
    "path",
    ["/.well-known/openid-configuration", "/.well-known/jwks.json", "/api/accounts/oauth/token"],
)
@pytest.mark.parametrize("size", [131_072, 131_073])
async def test_auth_documents_keep_original_default_response_budget(path, size):
    payload = model_catalog_payload(size)
    stream = Chunks([payload])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        method = "POST" if path.endswith("/token") else "GET"
        if size == 131_072:
            status, body = await request_json(client, method, "https://auth.openai.com" + path)
            assert status == 200 and isinstance(body, dict)
        else:
            with pytest.raises(AuthError) as error:
                await request_json(client, method, "https://auth.openai.com" + path)
            assert (
                error.value.code == "provider_protocol_error"
                and error.value.diagnostic_reason == "response_too_large"
            )
    assert stream.closed
