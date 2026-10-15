from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace

import httpx
import pytest

from grounding.codex_auth import CredentialStore
from grounding.codex_provider import CodexProvider
from grounding.contracts import StructuredRequest, VerificationError

REQUEST = StructuredRequest(
    "result", {"type": "object"}, "synthetic-rules", {"input": "synthetic-input"}
)


def completed(*, text='{"ok":true}', usage=None, content=None):
    return {
        "type": "response.completed",
        "response": {
            "status": "completed",
            "model": "returned-model",
            "usage": usage,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": content or [{"type": "output_text", "text": text}],
                }
            ],
        },
    }


def sse(event, newline="\n"):
    return (
        "event: " + event["type"] + newline + "data: " + json.dumps(event) + newline + newline
    ).encode()


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, *, failure=None, wait=None):
        self.chunks = chunks
        self.failure = failure
        self.wait = wait
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.wait:
            self.wait.set()
            await asyncio.Event().wait()
        if self.failure:
            raise self.failure

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
async def test_split_sse_final_object_uses_shared_parser_and_measured_usage(credentials, newline):
    usage = {"input_tokens": 8, "output_tokens": 5, "input_tokens_details": {"cached_tokens": 3}}
    encoded = b": heartbeat" + newline.encode() * 2 + sse(completed(usage=usage), newline)
    stream = Chunks([encoded[index : index + 1] for index in range(len(encoded))])
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream; charset=utf-8"}, stream=stream
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("visible-model", auth_store=credentials, client=client)
        result = await provider.generate(REQUEST)
    assert json.loads(result.text) == {"ok": True} and result.model == "returned-model"
    assert (
        result.usage.complete and result.usage.input_tokens == 8 and result.usage.output_tokens == 5
    )
    assert result.usage.cached_input_tokens == 3 and len(calls) == 1 and stream.closed


async def test_missing_usage_remains_unknown(credentials):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=sse(completed())
            )
        )
    ) as client:
        result = await CodexProvider("model", auth_store=credentials, client=client).generate(
            REQUEST
        )
    assert not result.usage.complete


@pytest.mark.parametrize("bad_value", ["\ud800", "\udfff", float("nan"), float("inf")])
async def test_invalid_unicode_and_json_numbers_are_safe_protocol_errors_with_terminal_logs(
    credentials, capfd, bad_value
):
    event = completed(text=bad_value if isinstance(bad_value, str) else '{"ok":true}')
    if not isinstance(bad_value, str):
        event["response"]["unexpected_number"] = bad_value
    stream = Chunks([sse(event)])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        )
    ) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert error.value.code == "provider_protocol_error" and stream.closed
    records = [json.loads(line) for line in capfd.readouterr().err.splitlines()]
    assert len(records) == 3 and records[-1]["outcome"] == "failure"
    assert records[-1]["error_code"] == "provider_protocol_error"
    assert len({record["request_id"] for record in records}) == 1


@pytest.mark.parametrize(
    "payload,expected",
    [
        (b"data: {not-json}\n\n", "provider_protocol_error"),
        (b"data: []\n\n", "provider_protocol_error"),
        (b"data: [DONE]\n\n", "provider_protocol_error"),
        (
            b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n',
            "provider_protocol_error",
        ),
        (
            b'data: {"type":"response.incomplete","response":{"status":"incomplete"}}\n\n',
            "model_incomplete",
        ),
        (
            b'data: {"type":"response.refusal.delta","delta":"synthetic-secret"}\n\n',
            "model_refused",
        ),
        (
            b'data: {"type":"response.failed","response":{"error":{"code":"server_error"}}}\n\n',
            "upstream_unavailable",
        ),
        (
            b'data: {"type":"response.failed","response":{"error":{"code":"unknown_secret"}}}\n\n',
            "provider_protocol_error",
        ),
        (
            b'event: response.failed\ndata: {"type":"response.completed","response":{}}\n\n',
            "provider_protocol_error",
        ),
        (b'data: {"type":"response.completed"}\n\n', "provider_protocol_error"),
        (
            b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n',
            "provider_protocol_error",
        ),
        (
            b'data: {"type":"response.completed","response":{"status":"incomplete"}}\n\n',
            "provider_protocol_error",
        ),
        (
            sse(completed(content=[{"type": "refusal", "refusal": "synthetic-secret"}])),
            "model_refused",
        ),
    ],
)
async def test_bad_streams_fail_once_and_close(credentials, payload, expected):
    stream = Chunks([payload])
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert error.value.code == expected and len(calls) == 1 and stream.closed
    assert "synthetic-secret" not in str(error.value) and "unknown_secret" not in str(error.value)
    assert not error.value.retryable


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (429, {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}, "quota_exhausted"),
        (
            503,
            {"error": {"code": "subscription_sharing_usage_unavailable"}},
            "upstream_unavailable",
        ),
        (
            400,
            {
                "error": {
                    "code": "subscription_sharing_unsupported_capability",
                    "param": "text.format",
                }
            },
            "unsupported_capability",
        ),
        (403, {"error": {"code": "subscription_sharing_user_not_eligible"}}, "plan_not_authorized"),
        (401, {"detail": "synthetic-secret"}, "authentication_failed"),
        (403, {"detail": "synthetic-secret"}, "plan_not_authorized"),
        (429, {"error": {"code": "rate_limit_exceeded"}}, "rate_limited"),
        (503, {"detail": "synthetic-secret"}, "upstream_unavailable"),
        (400, {"detail": "synthetic-secret"}, "provider_protocol_error"),
        (403, {"error": {"code": "chatpass_v2_scope_not_authorized"}}, "plan_not_authorized"),
        (
            403,
            {"error": {"code": "subscription_sharing_route_not_supported"}},
            "unsupported_capability",
        ),
        (401, {"error": {"code": "subscription_sharing_invalid_user"}}, "authentication_failed"),
    ],
)
async def test_http_admission_error_categories_and_no_hidden_retry(
    credentials, status, body, expected
):
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert error.value.code == expected and len(calls) == 1
    if expected in {"quota_exhausted", "unsupported_capability"}:
        assert not error.value.retryable


async def test_streaming_quota_error_stops_attempt_and_independent_request_can_recover(credentials):
    calls = []

    def transport(request):
        calls.append(request)
        if len(calls) == 2:
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=sse(completed())
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                sse({"type": "response.output_text.delta", "delta": "partial"})
                + sse(
                    {
                        "type": "response.failed",
                        "response": {
                            "error": {
                                "code": "subscription_sharing_usage_limit_exceeded",
                                "message": "synthetic-secret",
                            }
                        },
                    }
                )
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("model", auth_store=credentials, client=client)
        with pytest.raises(VerificationError) as error:
            await provider.generate(REQUEST)
        assert error.value.code == "quota_exhausted" and not error.value.retryable
        assert len(calls) == 1
        assert (await provider.generate(REQUEST)).text
    assert len(calls) == 2


@pytest.mark.parametrize(
    "limits,payload",
    [
        ({"max_stream_bytes": 32}, b":" + b"x" * 40 + b"\n\n"),
        ({"max_event_bytes": 32}, b"data: " + b"x" * 40),
        ({"max_response_bytes": 32}, sse(completed())),
        ({"max_event_bytes": 32}, b"data: " + b"x" * 20 + b"\ndata: " + b"x" * 20 + b"\n\n"),
    ],
)
async def test_stream_event_and_final_object_size_are_bounded(credentials, limits, payload):
    stream = Chunks([payload])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        )
    ) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client, **limits).generate(
                REQUEST
            )
    assert error.value.code == "response_too_large" and stream.closed


@pytest.mark.parametrize(
    "failure,expected",
    [
        (httpx.ReadError("synthetic-secret"), "upstream_unavailable"),
        (httpx.ReadTimeout("synthetic-secret"), "upstream_timeout"),
        (httpx.RemoteProtocolError("synthetic-secret"), "upstream_unavailable"),
    ],
)
async def test_interrupted_stream_does_not_retry(credentials, failure, expected):
    stream = Chunks(
        [sse({"type": "response.output_text.delta", "delta": "partial"})], failure=failure
    )
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert error.value.code == expected and len(calls) == 1 and stream.closed
    assert not error.value.retryable


async def test_cancelled_stream_is_closed_and_store_lock_is_available(credentials):
    entered = asyncio.Event()
    stream = Chunks([b": keepalive\n\n"], wait=entered)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        )
    ) as client:
        task = asyncio.create_task(
            CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with CredentialStore(auth_dir=credentials.directory).lock(0.1):
        assert stream.closed


async def test_total_timeout_bounds_hanging_stream_and_closes_it(credentials):
    stream = Chunks([b": keepalive\n\n"], wait=asyncio.Event())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        )
    ) as client:
        started = time.monotonic()
        with pytest.raises(VerificationError) as error:
            await CodexProvider(
                "model", timeout_seconds=0.1, auth_store=credentials, client=client
            ).generate(REQUEST)
    assert (
        error.value.code == "upstream_timeout" and stream.closed and time.monotonic() - started < 1
    )
    assert not error.value.retryable


async def test_real_verifier_stops_retrying_after_stream_begins(credentials):
    from grounding.config import Settings
    from grounding.contracts import VerifyRequest
    from grounding.verifiers import build_verifier

    streams = []

    def transport(request):
        stream = Chunks([b": stream opened\n\n"], failure=httpx.ReadError("synthetic-secret"))
        streams.append(stream)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("model", auth_store=credentials, client=client)
        verifier = build_verifier(
            "minimal",
            settings=Settings(
                provider="codex",
                model="model",
                transport_retries=1,
                retry_delay=0,
                diagnostics=False,
            ),
            provider=provider,
        )
        with pytest.raises(VerificationError) as error:
            await verifier.verify(
                VerifyRequest(context_passages=["A is B."], generated_answer="A is B.")
            )
        await verifier.aclose()
    assert error.value.code == "upstream_unavailable"
    assert error.value.stats.provider_calls == 1
    assert len(streams) == 1 and streams[0].closed


async def test_explicit_profile_and_directory_override_process_environment(
    credentials, monkeypatch
):
    monkeypatch.setenv("GROUNDING_AUTH_PROFILE", "wrong")
    monkeypatch.setenv("GROUNDING_AUTH_DIR", "/nonexistent/do-not-use")
    selected = CredentialStore(profile="selected", auth_dir=credentials.directory)
    selected.save(replace(credentials.load(), access_token="synthetic-selected-access"))

    def transport(request):
        assert request.headers["authorization"] == "Bearer synthetic-selected-access"
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=sse(completed())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider(
            "model", profile="selected", auth_dir=credentials.directory, client=client
        )
        assert (await provider.generate(REQUEST)).text


async def test_missing_model_and_missing_auth_are_explicit_and_no_owned_resource_leak(tmp_path):
    provider = CodexProvider(None, auth_dir=tmp_path / "empty")
    with pytest.raises(VerificationError) as error:
        await provider.generate(REQUEST)
    assert error.value.code == "not_configured"
    await provider.aclose()
    assert provider._client.is_closed
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("Missing auth must not reach network")
        )
    ) as client:
        provider = CodexProvider("model", auth_dir=tmp_path / "empty", client=client)
        with pytest.raises(VerificationError) as error:
            await provider.generate(REQUEST)
        assert error.value.code == "not_configured"
        await provider.aclose()
        assert not client.is_closed
