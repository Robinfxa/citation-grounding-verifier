import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
from test_jev_verifier import choice

from grounding.app import create_app
from grounding.config import Settings
from grounding.jev_provider import JevProvider
from grounding.providers import OpenAIProvider
from grounding.verifiers import build_verifier

ALLOWED_LOG_FIELDS = {
    "request_id", "stage", "event", "outcome", "elapsed_ms", "error_code",
    "provider_calls", "retries", "repairs", "claims", "routing_reason", "protocol_reason",
}


def native_response(body, *, low=False, malformed=False, pair=False):
    answers = {}
    for key, question in body["questions"].items():
        options = question["criteria"]
        selected = next(iter(options))
        if pair and key.endswith("_selection"):
            catalog = {item["id"]: item for item in body["state"]["window_catalog"]}
            selected = next(option for option, value in options.items()
                            if isinstance(value, dict) and {
                                catalog[window]["index"] for window in value["window_ids"]
                            } == {0, 1})
        decision = choice(options, selected, 0.6 if low and key.endswith("_relation") else 1)
        answers[key] = {"type": "choice", **asdict(decision)}
    if malformed:
        answers[next(iter(answers))]["confidence"] = None
    return {"model": "jev-1.14.0", "answers": answers,
            "usage": {"input_tokens": 7, "output_tokens": 3}}


def structured_llm_response(value):
    text = json.dumps(value)
    return {"status": "completed", "model": "SECRET_LLM_MODEL", "output": [{
        "type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }], "usage": {"input_tokens": 10, "output_tokens": 4,
                  "input_tokens_details": {"cached_tokens": 0}}}


def llm_response(claim_id, quote):
    return structured_llm_response({"judgments": [{
        "claim_id": claim_id, "verdict": "SUPPORTED", "reasoning": "The quotation states it.",
        "citations": [{"index": 0, "quote": quote}],
    }]})


async def test_native_http_success_fallback_failure_malformed_and_recovery(capfd):
    source = "SECRET_ITEM stores 7 blocks."
    payload = {"context_passages": [source], "generated_answer": source}
    steps = ["normal", "normal", "low", "low", "malformed", "normal", "normal"]
    wire_calls, llm_calls, budgets = [], [], []

    def jev_wire(request):
        assert request.url == "https://jev.invalid/v1/systemone"
        assert request.headers["Authorization"] == "Bearer SECRET_JEV_KEY"
        body = json.loads(request.content)
        wire_calls.append(body)
        step = steps.pop(0)
        return httpx.Response(200, json=native_response(
            body, low=step == "low", malformed=step == "malformed",
        ))

    def llm_wire(request):
        assert request.url == "https://llm.invalid/v1/responses"
        assert request.headers["Authorization"] == "Bearer SECRET_LLM_KEY"
        body = json.loads(request.content)
        data = json.loads(body["input"][1]["content"])
        llm_calls.append(data)
        assert data == {"context_passages": [source], "claims": [
            {"claim_id": 0, "claim_text": source},
        ]}
        if len(llm_calls) == 2:
            raise httpx.ReadTimeout("SECRET_EXCEPTION", request=request)
        return httpx.Response(200, json=llm_response(0, source))

    config = Settings(approach="jev_minimal", model="SECRET_LLM_MODEL", transport_retries=0,
                      diagnostics=True, jev_fallback=True)
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(jev_wire)) as jev_client,
        httpx.AsyncClient(transport=httpx.MockTransport(llm_wire)) as llm_client,
    ):
        instance = build_verifier("jev_minimal", settings=config, decision_provider=JevProvider(
            api_key="SECRET_JEV_KEY", base_url="https://jev.invalid/v1", client=jev_client,
        ), provider=OpenAIProvider(
            model=config.model, api_key="SECRET_LLM_KEY", base_url="https://llm.invalid/v1",
            client=llm_client,
        ))
        make_budget = instance._budget

        def observed_budget():
            budget = make_budget()
            budgets.append(budget)
            return budget

        instance._budget = observed_budget
        application = create_app(verifier=instance, settings=config)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://consumer.invalid",
        ) as consumer:
            responses = [await consumer.post("/verify", json=payload) for _ in range(5)]
        await instance.aclose()

    statuses = [response.status_code for response in responses]
    assert statuses == [200, 200, 504, 502, 200]
    assert responses[2].json()["error"]["code"] == "upstream_timeout"
    assert responses[3].json()["error"]["code"] == "provider_protocol_error"
    assert "SECRET" not in responses[2].text + responses[3].text
    for response in (responses[0], responses[1], responses[4]):
        assert set(response.json()) == {"claims"}
        assert set(response.json()["claims"][0]) == {
            "claim_text", "verdict", "reasoning", "citations",
        }
        assert response.json()["claims"][0]["citations"] == [{"index": 0, "quote": source}]
    assert len(wire_calls) == 7 and len(llm_calls) == 2 and not steps
    stats = [budget.stats() for budget in budgets]
    assert [item.provider_calls for item in stats] == [2, 2, 2, 1, 2]
    assert stats[2].usage.input_tokens == 7 and not stats[2].usage.complete
    assert stats[3].usage.input_tokens == 7 and stats[3].usage.complete
    assert stats[3].attempts[0].outcome == "failure"
    assert stats[3].attempts[0].error_code == "provider_protocol_error"
    assert stats[1].claim_decisions[0].final_origin == "llm"
    assert stats[2].claim_decisions[0].fallback_reason == "label_uncertain"

    raw = capfd.readouterr().err
    assert "SECRET" not in raw
    logs = [json.loads(line) for line in raw.splitlines()]
    assert logs and all(set(record) <= ALLOWED_LOG_FIELDS for record in logs)
    # Fixed guard labels are diagnostic vocabulary; decision payload fields stay forbidden.
    assert all({"confidence", "probabilities"}.isdisjoint(record) for record in logs)
    assert all(not isinstance(value, (dict, list)) for record in logs for value in record.values())
    protocol_records = [record for record in logs if "protocol_reason" in record]
    assert len(protocol_records) == 1
    protocol_record = protocol_records[0]
    assert type(protocol_record["elapsed_ms"]) in (int, float) and protocol_record["elapsed_ms"] >= 0
    assert protocol_record == {
        "request_id": responses[3].headers["x-request-id"],
        "stage": "jev_decision", "event": "validation", "outcome": "failure",
        "elapsed_ms": protocol_record["elapsed_ms"],
        "error_code": "provider_protocol_error", "protocol_reason": "confidence_invalid",
    }
    ids = {response.headers["x-request-id"] for response in responses}
    assert len(ids) == 5 and {record["request_id"] for record in logs} == ids
    for response in responses:
        group = [record for record in logs
                 if record["request_id"] == response.headers["x-request-id"]]
        assert (group[0]["stage"], group[0]["event"]) == ("http", "start")
        assert (group[-1]["stage"], group[-1]["event"]) == ("http", "end")
    assert len([record for record in logs if record.get("routing_reason") == "label_uncertain"]) == 2
    assert any(record["stage"] == "fallback" and record["outcome"] == "failure"
               and record.get("error_code") == "upstream_timeout" for record in logs)

    root = Path(__file__).resolve().parents[2]
    evidence = root / ".multi-subflow/service/jev"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "consumer-diagnostics.jsonl").write_text(raw)
    (evidence / "consumer-outcomes.json").write_text(json.dumps({
        "probe": "test_jev_http.py::test_native_http_success_fallback_failure_malformed_and_recovery",
        "scope": "Offline actual ASGI /verify; native Jev and OpenAI adapters use HTTPX MockTransport. No inference or credential access.",
        "input": payload,
        "responses": [{"status": response.status_code, "body": response.json(),
                       "request_id": response.headers["x-request-id"]} for response in responses],
        "provider_calls": [item.provider_calls for item in stats],
        "attempts": [[asdict(attempt) for attempt in item.attempts] for item in stats],
        "record_count": len(logs), "secrets_in_logs": False,
        "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [root / "src/grounding/verifiers.py",
                                       root / "src/grounding/jev_verifier.py",
                                       root / "src/grounding/jev_evidence.py",
                                       root / "src/grounding/jev_provider.py",
                                       root / "src/grounding/diagnostics.py", Path(__file__).resolve()]},
    }, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("name", ["jev_minimal", "jev_optimized"])
async def test_native_http_joint_unicode_evidence_keeps_original_indices(name):
    passages = ["杉树是中继站。", "该中继站于一点恢复。"]
    payload = {"context_passages": passages, "generated_answer": "杉树于一点恢复。"}
    bodies, extraction_calls = [], []

    def wire(request):
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json=native_response(body, pair="context_passages" in body["state"]))

    def extract(request):
        body = json.loads(request.content)
        data = json.loads(body["input"][1]["content"])
        extraction_calls.append(data)
        assert data == {"generated_answer": payload["generated_answer"]}
        return httpx.Response(200, json=structured_llm_response({"claims": [{
            "claim_text": payload["generated_answer"], "answer_quote": payload["generated_answer"],
        }]}))

    config = Settings(approach=name, model="SECRET_LLM_MODEL", jev_fallback=False, diagnostics=False)
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(wire)) as provider_client,
        httpx.AsyncClient(transport=httpx.MockTransport(extract)) as llm_client,
    ):
        instance = build_verifier(name, settings=config, decision_provider=JevProvider(
            api_key="synthetic-only", client=provider_client,
        ), provider=OpenAIProvider(
            model=config.model, api_key="synthetic-only", client=llm_client,
        ))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(verifier=instance, settings=config)),
            base_url="http://consumer.invalid",
        ) as consumer:
            response = await consumer.post("/verify", json=payload)
        await instance.aclose()
    assert response.status_code == 200
    assert response.json()["claims"][0]["citations"] == [
        {"index": index, "quote": passage} for index, passage in enumerate(passages)
    ]
    assert bodies[0]["state"]["context_passages"] == passages
    assert set(bodies[1]["state"]) == {"policy_version", "policy"}
    assert len(extraction_calls) == (name == "jev_optimized")
