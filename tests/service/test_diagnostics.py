import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
from test_verifiers import REQUEST, ScriptedProvider, report

from grounding.app import create_app
from grounding.config import Settings
from grounding.verifiers import build_verifier

ALLOWED = {"request_id", "stage", "event", "outcome", "elapsed_ms", "error_code",
           "provider_calls", "retries", "repairs", "claims"}


def _app(provider, *, enabled=True):
    settings = Settings(model="SECRET_MODEL", retry_delay=0, diagnostics=enabled)
    return create_app(
        verifier=build_verifier("minimal", settings=settings, provider=provider), settings=settings
    )


def _records(raw):
    records = [json.loads(line) for line in raw.splitlines()]
    assert records
    for record in records:
        assert set(record) <= ALLOWED
        assert len(json.dumps(record)) < 512
        assert len(record["request_id"]) == 32
        assert isinstance(record["elapsed_ms"], (int, float))
    return records


async def test_real_http_success_secret_failures_and_recovery_leave_safe_records(capfd):
    secret_error = type("SECRET_TYPE", (RuntimeError,), {})("SECRET_EXCEPTION\n{forged:true}")
    secret_error.add_note("SECRET_NOTE")
    namespace = {"error": secret_error}
    exec(compile("def deep(n):\n if n: return deep(n-1)\n raise error", "SECRET_FILENAME", "exec"), namespace)

    async def fail():
        local_secret = "SECRET_LOCAL"
        assert local_secret
        namespace["deep"](100)

    valid = report(text="SECRET_ANSWER", quote="SECRET_SOURCE")
    provider = ScriptedProvider(valid, fail, report(quote="SECRET_MODEL_OUTPUT"), valid)
    provider.name = "SECRET_PROVIDER"
    provider.model = "SECRET_MODEL"
    app = _app(provider)
    payload = {"context_passages": ["SECRET_SOURCE"], "generated_answer": "SECRET_ANSWER"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = [await client.post("/verify", json=payload) for _ in range(4)]
    raw = capfd.readouterr().err
    assert "SECRET" not in raw and "forged" not in raw
    assert [r.status_code for r in responses] == [200, 500, 502, 200]
    assert "SECRET" not in responses[1].text + responses[2].text
    records = _records(raw)
    ids = {record["request_id"] for record in records}
    assert len(ids) == 4
    assert ids == {response.headers["x-request-id"] for response in responses}
    for request_id in ids:
        group = [r for r in records if r["request_id"] == request_id]
        assert group[0]["stage"] == "http" and group[0]["event"] == "start"
        assert group[-1]["stage"] == "http" and group[-1]["event"] == "end"
    assert any(r["event"] == "provider_attempt" and r.get("error_code") == "internal_error" for r in records)
    assert any(r["event"] == "validation" and r.get("error_code") == "invalid_model_output" for r in records)
    evidence = Path(".multi-subflow/service")
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "consumer-diagnostics.jsonl").write_text(raw)
    (evidence / "consumer-outcomes.json").write_text(json.dumps({
        "command": "uv run --no-sync pytest tests/service/test_diagnostics.py -q",
        "http_statuses": [r.status_code for r in responses],
        "error_codes": [r.json()["error"]["code"] for r in responses[1:3]],
        "record_count": len(records), "secret_found": False,
    }, indent=2) + "\n")


async def test_disabled_diagnostics_preserve_public_result(capfd):
    results = []
    for enabled in (False, True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app(ScriptedProvider(report()), enabled=enabled)),
            base_url="http://test",
        ) as client:
            response = await client.post("/verify", json=REQUEST.model_dump())
        results.append(response.json())
        raw = capfd.readouterr().err
        if enabled:
            _records(raw)
        else:
            assert raw == ""
    assert results[0] == results[1]


async def test_parallel_http_requests_keep_correlation_isolated(capfd):
    async def delayed():
        from grounding.contracts import ProviderResult
        await asyncio.sleep(0.005)
        return ProviderResult(json.dumps(report()))

    app = _app(ScriptedProvider(delayed, delayed))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*[
            client.post("/verify", json=REQUEST.model_dump()) for _ in range(2)
        ])
    records = _records(capfd.readouterr().err)
    ids = {response.headers["x-request-id"] for response in responses}
    assert len(ids) == 2
    for request_id in ids:
        group = [r for r in records if r["request_id"] == request_id]
        assert [r["outcome"] for r in group if r["event"] == "end"] == ["success", "success"]
        assert len([r for r in group if r["event"] == "provider_attempt"]) == 2


def test_broken_stderr_sink_preserves_actual_process_exit_and_http_success():
    code = '''
import asyncio, json, os
import httpx
from grounding.app import create_app
from grounding.config import Settings
read_fd, write_fd = os.pipe()
os.close(read_fd)
os.dup2(write_fd, 2)
os.close(write_fd)
async def main():
    app = create_app(settings=Settings(approach="heuristic", diagnostics=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/verify", json={"context_passages":["Oak stores 7 blocks."],"generated_answer":"Oak stores 7 blocks."})
        print(json.dumps({"status":response.status_code,"report":response.json()}))
asyncio.run(main())
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == 200
    assert data["report"]["claims"][0]["verdict"] == "SUPPORTED"
    assert result.stderr == ""
