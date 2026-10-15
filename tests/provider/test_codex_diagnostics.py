from __future__ import annotations

import json
from dataclasses import replace

import httpx
import pytest
from test_codex_acceptance import SCOPES
from test_codex_stream import completed, sse

from grounding.codex_provider import CodexProvider
from grounding.contracts import StructuredRequest, VerificationError
from grounding.diagnostics import operation


async def test_refresh_and_inference_inherit_real_consumer_correlation_without_secrets(
    credentials, capfd
):
    marker = "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"
    credentials.save(replace(credentials.load(), expires_at=0))
    requests = []

    def transport(request):
        requests.append(request)
        if request.url.path.endswith("/token"):
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
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b": comment\n\n" * 500 + sse(completed()),
        )

    with operation(enabled=True, new=True) as consumer:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            result = await CodexProvider(marker, auth_store=credentials, client=client).generate(
                StructuredRequest(marker, {"description": marker}, marker, {"value": marker})
            )
    captured = capfd.readouterr()
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert result.text and len(requests) == 2 and len(records) == 5
    assert {record["stage"] for record in records} == {"auth_refresh", "codex_inference"}
    assert {record["request_id"] for record in records} == {consumer.request_id}
    assert all(record["elapsed_ms"] >= 0 and "event" in record for record in records)
    assert marker not in captured.err + captured.out and "synthetic-" not in captured.err
    assert len(captured.err.encode()) < 2048


async def test_secret_seeded_external_failure_is_diagnosable_and_next_operation_recovers(
    credentials, capfd
):
    marker = "PROVIDER_SECRET_MARKER_DO_NOT_EMIT"
    calls = []

    def transport(request):
        calls.append(request)
        if len(calls) == 1:
            secret_type = type(marker, (httpx.ConnectError,), {})
            exception = secret_type(marker)
            exception.add_note(marker)
            namespace = {"exception": exception, "secret_local": marker}
            exec(compile("raise exception", marker + ".py", "exec"), namespace)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=sse(completed())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("model", auth_store=credentials, client=client)
        with operation(enabled=True, new=True) as failed:
            with pytest.raises(VerificationError) as error:
                await provider.generate(StructuredRequest("x", {}, marker, {"value": marker}))
        with operation(enabled=True, new=True) as recovered:
            result = await provider.generate(StructuredRequest("x", {}, "rules", {}))
    captured = capfd.readouterr()
    records = [json.loads(line) for line in captured.err.splitlines()]
    failure = [record for record in records if record["outcome"] == "failure"]
    assert (
        len(failure) == 1 and failure[0]["error_code"] == error.value.code == "upstream_unavailable"
    )
    assert failure[0]["request_id"] == failed.request_id != recovered.request_id
    assert result.text and records[-1]["outcome"] == "success"
    assert marker not in captured.out + captured.err and "Traceback" not in captured.err


async def test_consumer_disabling_diagnostics_and_broken_sink_preserve_results(
    credentials, capfd, monkeypatch
):
    from grounding import codex_auth

    def transport(request):
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=sse(completed())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("model", auth_store=credentials, client=client)
        with operation(enabled=False, new=True):
            disabled = await provider.generate(StructuredRequest("x", {}, "rules", {}))
        assert capfd.readouterr().err == ""

        def fail(fd, data):
            raise OSError("PROVIDER_SECRET_MARKER_DO_NOT_EMIT")

        monkeypatch.setattr(codex_auth.os, "write", fail)
        enabled = await provider.generate(StructuredRequest("x", {}, "rules", {}))
    assert disabled == enabled and capfd.readouterr().err == ""
