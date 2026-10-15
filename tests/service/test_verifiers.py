import asyncio
import json

import pytest

from grounding.config import Settings
from grounding.contracts import (
    ProviderResult,
    TokenUsage,
    VerificationError,
    VerifyRequest,
)
from grounding.verifiers import build_verifier


class ScriptedProvider:
    name = "scripted"
    model = "fixed-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.closed = False

    async def generate(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return await response()
        text = response if isinstance(response, str) else json.dumps(response)
        return ProviderResult(text, TokenUsage(10, 4), self.model)

    async def aclose(self):
        self.closed = True


def settings(**changes):
    return Settings(model="fixed-model", retry_delay=0, diagnostics=False, **changes)


def extraction(*claims):
    return {"claims": [{"claim_text": c, "answer_quote": c} for c in claims]}


def judgment(claim_id=0, *, verdict="SUPPORTED", quote="Oak stores 7 blocks.", index=0):
    return {
        "claim_id": claim_id,
        "verdict": verdict,
        "reasoning": "The cited passage states the claim.",
        "citations": [] if verdict == "UNSUPPORTED" else [{"index": index, "quote": quote}],
    }


def report(text="Oak stores 7 blocks.", **changes):
    item = judgment(**changes)
    item.pop("claim_id")
    return {"claims": [{"claim_text": text, **item}]}


REQUEST = VerifyRequest(
    context_passages=["Oak stores 7 blocks."], generated_answer="Oak stores 7 blocks."
)


async def test_optimized_answer_only_extraction_and_fixed_ids():
    other = "Oak uses checksums."
    provider = ScriptedProvider(
        extraction(REQUEST.generated_answer, other),
        {"judgments": [judgment(1, verdict="UNSUPPORTED"), judgment(0)]},
    )
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    result = await verifier.verify(
        REQUEST.model_copy(update={"generated_answer": REQUEST.generated_answer + " " + other})
    )
    assert [c.claim_text for c in result.report.claims] == [REQUEST.generated_answer, other]
    assert set(provider.requests[0].payload) == {"generated_answer"}
    assert provider.requests[1].payload["claims"] == [
        {"claim_id": 0, "claim_text": REQUEST.generated_answer},
        {"claim_id": 1, "claim_text": other},
    ]
    assert result.stats.provider_calls == 2
    assert result.stats.usage == TokenUsage(20, 8)


@pytest.mark.parametrize("defect", [[], [judgment(1)], [judgment(), judgment()]])
async def test_id_defects_invalidate_whole_attempt_and_allow_one_repair(defect):
    provider = ScriptedProvider({"judgments": defect}, {"judgments": [judgment()]})
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    result = await verifier.verify_claims(REQUEST.context_passages, [REQUEST.generated_answer])
    assert len(result.report.claims) == 1
    assert result.stats.repairs == 1
    assert result.stats.provider_calls == 2


@pytest.mark.parametrize("name", ["heuristic", "minimal", "optimized"])
async def test_blank_answer_never_calls_model(name):
    provider = ScriptedProvider()
    verifier = build_verifier(name, settings=settings(), provider=provider)
    result = await verifier.verify(VerifyRequest(context_passages=[], generated_answer=" \n"))
    assert result.report.claims == []
    assert result.stats.provider_calls == 0


async def test_extraction_anchor_repair_then_explicit_failure():
    defect = {"claims": [{"claim_text": "Oak stores 7 blocks.", "answer_quote": "invented"}]}
    provider = ScriptedProvider(defect, defect)
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    with pytest.raises(VerificationError, match="failed verification") as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "invalid_model_output"
    assert len(provider.requests) == 2
    assert all("context_passages" not in r.payload for r in provider.requests)


async def test_minimal_never_repairs_bad_quote():
    provider = ScriptedProvider(report(quote="not present"), report())
    verifier = build_verifier("minimal", settings=settings(), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "invalid_model_output"
    assert len(provider.requests) == 1


async def test_empty_context_still_extracts_facts_then_skips_judge():
    provider = ScriptedProvider(extraction("Oak stores 7 blocks.", "Oak uses checksums."))
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    result = await verifier.verify(
        VerifyRequest(context_passages=[], generated_answer="Oak stores 7 blocks. Oak uses checksums.")
    )
    assert [c.verdict for c in result.report.claims] == ["UNSUPPORTED", "UNSUPPORTED"]
    assert result.stats.provider_calls == 1


async def test_retry_attempt_cap_and_usage_unknown_are_shared():
    provider = ScriptedProvider(
        VerificationError("rate_limited"), extraction(REQUEST.generated_answer),
        VerificationError("upstream_unavailable"), {"judgments": [judgment()]},
    )
    verifier = build_verifier("optimized", settings=settings(max_provider_attempts=3), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "attempt_budget_exhausted"
    assert caught.value.stats.provider_calls == 3
    assert not caught.value.stats.usage.complete


async def test_deadline_cancels_provider_and_next_operation_recovers():
    cancelled = asyncio.Event()

    async def stuck():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    provider = ScriptedProvider(stuck, report())
    verifier = build_verifier(
        "minimal", settings=settings(operation_timeout=0.02), provider=provider
    )
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "deadline_exceeded"
    assert cancelled.is_set()
    assert (await verifier.verify(REQUEST)).report.claims[0].verdict == "SUPPORTED"


async def test_heuristic_number_negation_and_conflicting_evidence():
    verifier = build_verifier("heuristic", settings=settings())
    result = await verifier.verify_claims(
        ["Oak stores 9 blocks.", "Oak does not use checksums."],
        ["Oak stores 7 blocks.", "Oak uses checksums.", "Oak encrypts backups."],
    )
    assert [c.verdict for c in result.report.claims] == [
        "CONTRADICTED", "CONTRADICTED", "UNSUPPORTED"
    ]
    conflict = await verifier.verify_claims(
        ["Oak stores 7 blocks.", "Oak stores 9 blocks."], ["Oak stores 7 blocks."]
    )
    assert conflict.report.claims[0].verdict == "UNSUPPORTED"
    assert "conflict" in conflict.report.claims[0].reasoning.lower()


@pytest.mark.parametrize("code", ["model_refused", "model_incomplete", "quota_exhausted",
                                  "plan_not_authorized", "unsupported_capability", "response_too_large"])
async def test_terminal_provider_failures_never_trigger_repair_or_retry(code):
    provider = ScriptedProvider(VerificationError(code), report())
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == code
    assert caught.value.stats.provider_calls == 1
    assert caught.value.stats.repairs == caught.value.stats.retries == 0


async def test_all_repairs_and_transport_retries_share_six_attempt_budget():
    provider = ScriptedProvider(
        VerificationError("rate_limited"), {"claims": "bad"},
        VerificationError("upstream_unavailable"), extraction(REQUEST.generated_answer),
        VerificationError("upstream_timeout"), {"judgments": []},
        {"judgments": [judgment()]},
    )
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "attempt_budget_exhausted"
    assert len(provider.requests) == caught.value.stats.provider_calls == 6


async def test_each_optimized_stage_has_one_repair_and_sources_are_never_rewritten():
    provider = ScriptedProvider(
        "not json", extraction(REQUEST.generated_answer),
        {"judgments": [judgment(quote="wrong")]}, {"judgments": [judgment()]},
    )
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    result = await verifier.verify(REQUEST)
    assert result.stats.repairs == 2 and result.stats.provider_calls == 4
    assert provider.requests[0].payload == {"generated_answer": REQUEST.generated_answer}
    assert provider.requests[1].payload["validation_errors"] == ["schema_invalid"]
    assert provider.requests[2].payload["context_passages"] == REQUEST.context_passages
    assert provider.requests[3].payload["context_passages"] == REQUEST.context_passages
    assert "wrong" not in json.dumps(provider.requests[3].payload)


@pytest.mark.parametrize("name", ["minimal", "optimized"])
async def test_oracle_preserves_repeated_claim_identity_and_has_no_extraction(name):
    provider = ScriptedProvider({"judgments": [judgment(1), judgment(0)]})
    verifier = build_verifier(name, settings=settings(), provider=provider)
    result = await verifier.verify_claims(REQUEST.context_passages, [REQUEST.generated_answer] * 2)
    assert [c.claim_text for c in result.report.claims] == [REQUEST.generated_answer] * 2
    assert len(provider.requests) == 1
    assert "generated_answer" not in provider.requests[0].payload


@pytest.mark.parametrize("name,response", [("minimal", {"claims": []}), ("optimized", {"claims": []})])
async def test_successfully_identified_nonfactual_answer_returns_empty_without_judge(name, response):
    provider = ScriptedProvider(response)
    verifier = build_verifier(name, settings=settings(), provider=provider)
    result = await verifier.verify(VerifyRequest(context_passages=["x"], generated_answer="Thanks!"))
    assert result.report.claims == []
    assert len(provider.requests) == 1


async def test_external_cancellation_stops_budget_without_becoming_error_or_retry():
    started, stopped = asyncio.Event(), asyncio.Event()

    async def waiting():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    provider = ScriptedProvider(waiting)
    verifier = build_verifier("optimized", settings=settings(), provider=provider)
    task = asyncio.create_task(verifier.verify(REQUEST))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set() and len(provider.requests) == 1


async def test_deadline_includes_retry_delay_without_counting_an_unsent_retry():
    provider = ScriptedProvider(VerificationError("rate_limited"), report())
    verifier = build_verifier("minimal", settings=Settings(
        model="fixed-model", retry_delay=1, operation_timeout=0.02, diagnostics=False,
    ), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "deadline_exceeded"
    assert caught.value.stats.provider_calls == 1
    assert caught.value.stats.retries == 0


async def test_budget_exhaustion_does_not_count_an_unsent_repair():
    provider = ScriptedProvider("invalid")
    verifier = build_verifier("optimized", settings=settings(max_provider_attempts=1), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "attempt_budget_exhausted"
    assert caught.value.stats.repairs == 0


async def test_provider_nonretryable_override_survives_operation_error_wrapper():
    failure = VerificationError("upstream_unavailable")
    failure.retryable = False
    provider = ScriptedProvider(failure)
    verifier = build_verifier("minimal", settings=settings(), provider=provider)
    with pytest.raises(VerificationError) as caught:
        await verifier.verify(REQUEST)
    assert caught.value.code == "upstream_unavailable"
    assert caught.value.stats.provider_calls == 1
    assert not caught.value.retryable
