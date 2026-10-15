import asyncio
import json

import httpx
import pytest
from test_verifiers import REQUEST, ScriptedProvider, report

from grounding.app import create_app
from grounding.config import Settings
from grounding.contracts import MAX_BODY_BYTES
from grounding.verifiers import build_verifier


def client_for(provider, *, name="minimal", **changes):
    settings = Settings(model="fixed-model", retry_delay=0, diagnostics=False, **changes)
    verifier = build_verifier(name, settings=settings, provider=provider)
    app = create_app(verifier=verifier, settings=settings)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://service.test")


async def test_http_only_returns_public_report_and_internal_request_id():
    provider = ScriptedProvider(report())
    async with client_for(provider) as client:
        response = await client.post("/verify", json=REQUEST.model_dump(), headers={"X-Request-ID": "taint"})
    assert response.status_code == 200
    assert response.json() == report()
    assert len(response.headers["x-request-id"]) == 32
    assert response.headers["x-request-id"] != "taint"


@pytest.mark.parametrize("data", [
    {}, {"context_passages": "taint", "generated_answer": "x"},
    {"context_passages": [True], "generated_answer": "x"},
    {"context_passages": [], "generated_answer": "x", "taint": "taint"},
    {"context_passages": ["x"] * 33, "generated_answer": "x"},
    {"context_passages": ["x" * 16_001], "generated_answer": "x"},
    {"context_passages": ["x" * 16_000] * 7, "generated_answer": "x"},
    {"context_passages": [], "generated_answer": "x" * 12_001},
])
async def test_invalid_request_does_not_echo_values_or_call_provider(data):
    provider = ScriptedProvider()
    async with client_for(provider) as client:
        response = await client.post("/verify", json=data)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "taint" not in response.text
    assert not provider.requests


async def test_body_limit_is_measured_in_bytes_even_without_content_length():
    provider = ScriptedProvider()

    async def body():
        yield b'{"generated_answer":"'
        yield b"x" * MAX_BODY_BYTES

    async with client_for(provider) as client:
        response = await client.post("/verify", content=body(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert not provider.requests


@pytest.mark.parametrize("quote,index", [
    ("Cafe\u0301 🛰\n保存 7 项。", 0), ("Café 🛰\n保存 7 项。", True),
    ("Café 🛰\n保存 7 项。", -1), ("Café 🛰\n保存 7 项。", 1),
    ("Café 🛰 保存 7 项。", 0), ("", 0), (" \n", 0),
])
async def test_unicode_and_index_defects_through_real_http_consumer(quote, index):
    provider = ScriptedProvider(report(quote=quote, index=index))
    async with client_for(provider) as client:
        response = await client.post("/verify", json={
            "context_passages": ["Café 🛰\n保存 7 项。"], "generated_answer": "Oak stores 7 blocks."
        })
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_model_output"


async def test_exact_unicode_is_preserved_on_http_success():
    quote = "Café 🛰\n保存 7 项。"
    provider = ScriptedProvider(report(quote=quote))
    async with client_for(provider) as client:
        response = await client.post("/verify", json={
            "context_passages": ["prefix " + quote], "generated_answer": "Oak stores 7 blocks."
        })
    assert response.status_code == 200
    assert response.json()["claims"][0]["citations"][0]["quote"] == quote


async def test_escaped_invalid_unicode_inside_model_json_is_not_an_internal_server_error():
    malformed = report()
    malformed["claims"][0]["reasoning"] = "\ud800"
    provider = ScriptedProvider(malformed)
    async with client_for(provider) as client:
        response = await client.post("/verify", json=REQUEST.model_dump())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_model_output"


async def test_malformed_json_is_safe_and_next_request_succeeds():
    provider = ScriptedProvider(report())
    async with client_for(provider) as client:
        failed = await client.post("/verify", content=b'{"taint":', headers={"Content-Type": "application/json"})
        recovered = await client.post("/verify", json=REQUEST.model_dump())
    assert failed.status_code == 422
    assert "taint" not in failed.text
    assert recovered.status_code == 200


@pytest.mark.parametrize("content", [b"\xff", b"[" * 2_000 + b"]" * 2_000], ids=["utf8", "depth"])
async def test_invalid_json_encoding_or_nesting_is_a_safe_input_error(content):
    async with client_for(ScriptedProvider()) as client:
        response = await client.post("/verify", content=content, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_http_deadline_has_safe_code_and_cancels_work():
    cancelled = asyncio.Event()

    async def hung():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async with client_for(ScriptedProvider(hung), operation_timeout=0.02) as client:
        response = await client.post("/verify", json=REQUEST.model_dump())
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "deadline_exceeded"
    assert cancelled.is_set()


async def test_disconnect_cancels_provider_without_sending_success():
    started, cancelled, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def hung():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    settings = Settings(model="fixed-model", diagnostics=False)
    app = create_app(
        verifier=build_verifier("minimal", settings=settings, provider=ScriptedProvider(hung)),
        settings=settings,
    )
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": json.dumps(REQUEST.model_dump()).encode(), "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "method": "POST", "scheme": "http",
             "path": "/verify", "raw_path": b"/verify", "query_string": b"", "root_path": "",
             "headers": [(b"content-type", b"application/json")], "server": ("local", 80), "client": ("local", 1)}
    task = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(started.wait(), 1)
    disconnected.set()
    await asyncio.wait_for(task, 1)
    assert cancelled.is_set()
    assert not sent
