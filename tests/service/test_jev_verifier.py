import asyncio
import json

import pytest
from test_verifiers import REQUEST, ScriptedProvider, extraction, judgment, settings

from grounding.contracts import (
    ChoiceDecision,
    DecisionResult,
    RunStats,
    TokenUsage,
    VerificationError,
    VerifyRequest,
)
from grounding.jev_evidence import NO_ADEQUATE_BUNDLE
from grounding.verifiers import build_verifier


def choice(options, selected, confidence=1.0):
    count = len(options)
    peak = (1 + confidence * (count - 1)) / count
    return ChoiceDecision(selected, confidence, {
        option: peak if option == selected else (1 - peak) / (count - 1)
        for option in options
    })


class Decisions:
    name = "typesafe"
    model = "jev-1.14.0"

    def __init__(self, *steps):
        self.steps = list(steps)
        self.requests = []
        self.closed = False

    async def decide(self, request):
        self.requests.append(request)
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            step = step(request)
        if asyncio.iscoroutine(step):
            step = await step
        if isinstance(step, DecisionResult):
            return step
        answers = {}
        for key, question in request.questions.items():
            options = question["criteria"]
            value = step.get(key, next(iter(options)))
            selected, confidence = value if isinstance(value, tuple) else (value, 1.0)
            answers[key] = choice(options, selected, confidence)
        return DecisionResult(answers, TokenUsage(7, 3, 0), self.model)

    async def aclose(self):
        self.closed = True


def verifier(name="jev_minimal", *, decisions, llm=None, **changes):
    return build_verifier(
        name, settings=settings(**{"jev_fallback": False, **changes}), provider=llm,
        decision_provider=decisions,
    )


async def test_minimal_keeps_rule_compound_and_never_calls_extractor():
    text = "Oak stores 7 blocks and uses checksums."
    decisions = Decisions({}, {})
    llm = ScriptedProvider()
    run = await verifier(decisions=decisions, llm=llm).verify(VerifyRequest(
        context_passages=[text], generated_answer=text,
    ))
    assert [claim.claim_text for claim in run.report.claims] == [text]
    assert not llm.requests
    assert [a.stage for a in run.stats.attempts] == ["jev_judgment", "jev_evidence"]
    assert [a.question_count for a in run.stats.attempts] == [3, 1]
    assert run.stats.provider == "hybrid" and run.stats.requested_model is None
    assert run.stats.claim_decisions[0].final_origin == "jev"


async def test_optimized_reuses_answer_only_extraction_and_tracks_all_attempts():
    llm = ScriptedProvider(extraction(REQUEST.generated_answer))
    decisions = Decisions({}, {})
    run = await verifier("jev_optimized", decisions=decisions, llm=llm).verify(REQUEST)
    assert llm.requests[0].payload == {"generated_answer": REQUEST.generated_answer}
    assert [a.stage for a in run.stats.attempts] == [
        "extraction", "jev_judgment", "jev_evidence",
    ]
    assert run.stats.provider_calls == 3
    assert run.stats.usage == TokenUsage(24, 10)


@pytest.mark.parametrize("name", ["jev_minimal", "jev_optimized"])
async def test_oracle_retains_duplicate_claims_and_skips_extraction(name):
    llm = ScriptedProvider()
    decisions = Decisions({}, {})
    run = await verifier(name, decisions=decisions, llm=llm).verify_claims(
        REQUEST.context_passages, [REQUEST.generated_answer] * 2,
    )
    assert [c.claim_text for c in run.report.claims] == [REQUEST.generated_answer] * 2
    assert [t.claim_id for t in run.stats.claim_decisions] == [0, 1]
    assert not llm.requests
    assert run.stats.provider_calls == 2
    assert [attempt.question_count for attempt in run.stats.attempts] == [6, 2]


@pytest.mark.parametrize("name", ["jev_minimal", "jev_optimized"])
async def test_blank_and_empty_context_do_not_need_decision_calls(name):
    decisions = Decisions()
    llm = ScriptedProvider(extraction(REQUEST.generated_answer))
    instance = verifier(name, decisions=decisions, llm=llm)
    blank = await instance.verify(VerifyRequest(context_passages=[], generated_answer=" "))
    assert blank.report.claims == [] and blank.stats.provider_calls == 0
    empty = await instance.verify(REQUEST.model_copy(update={"context_passages": []}))
    assert empty.report.claims[0].verdict == "UNSUPPORTED"
    assert empty.stats.claim_decisions[0].final_origin == "empty_context"
    assert len(llm.requests) == (name == "jev_optimized")
    oracle = await instance.verify_claims([], [REQUEST.generated_answer])
    assert oracle.stats.provider_calls == 0
    assert oracle.stats.claim_decisions[0].final_origin == "empty_context"
    assert not decisions.requests


async def test_nonfactual_minimal_and_empty_optimized_extraction_skip_judgment():
    for name, answer in (("jev_minimal", "Hello!"), ("jev_optimized", "Hello!")):
        decisions = Decisions()
        llm = ScriptedProvider(extraction())
        run = await verifier(name, decisions=decisions, llm=llm).verify(
            REQUEST.model_copy(update={"generated_answer": answer})
        )
        assert run.report.claims == [] and not decisions.requests
        assert run.stats.provider_calls == (name == "jev_optimized")


async def test_quote_questions_have_only_own_evidence_and_all_tasks_are_visible():
    claims = ["Aster is red.", "Birch is blue."]
    passages = [*claims, "PRIVATE_UNUSED_SOURCE"]
    decisions = Decisions({}, {})
    await verifier(decisions=decisions).verify_claims(passages, claims)
    first, second = decisions.requests
    assert first.state["context_passages"] == passages
    assert all(question["instructions"]["claim_text"] in claims
               for question in first.questions.values())
    assert "PRIVATE_UNUSED_SOURCE" not in json.dumps([second.state, second.questions])
    assert set(second.state) == {"policy_version", "policy"}
    for index, claim in enumerate(claims):
        instructions = second.questions[f"claim_{index}_evidence"]["instructions"]
        assert instructions["claim_text"] == claim
        assert instructions["selected_quotes"] == [{"index": index, "quote": claim}]
        assert claims[1 - index] not in json.dumps(instructions)


async def test_joint_evidence_keeps_distinct_passage_indices():
    passages = ["Cedar is the relay.", "The relay resumes at one."]

    def select_pair(request):
        catalog = {item["id"]: item for item in request.state["window_catalog"]}
        criteria = request.questions["claim_0_selection"]["criteria"]
        pair = next(key for key, value in criteria.items() if isinstance(value, dict)
                    and {catalog[w]["index"] for w in value["window_ids"]} == {0, 1})
        return {"claim_0_selection": pair}

    run = await verifier(decisions=Decisions(select_pair, {})).verify_claims(
        passages, ["Cedar resumes at one."]
    )
    assert [c.index for c in run.report.claims[0].citations] == [0, 1]
    assert [c.quote for c in run.report.claims[0].citations] == passages


async def test_quote_only_missing_antecedent_routes_to_full_context_llm():
    context = ["Maple Relay emits a ping. Cedar Relay pauses at noon. It resumes at one."]
    claim = "Cedar Relay resumes at one."

    def select_incomplete(request):
        catalog = {item["id"]: item for item in request.state["window_catalog"]}
        options = request.questions["claim_0_selection"]["criteria"]
        incomplete = next(key for key, value in options.items() if isinstance(value, dict)
                          and [catalog[window]["quote"] for window in value["window_ids"]]
                          == ["It resumes at one."])
        return {"claim_0_selection": incomplete}

    decisions = Decisions(select_incomplete, {"claim_0_evidence": "UNSUPPORTED"})
    complete = "Cedar Relay pauses at noon. It resumes at one."
    llm = ScriptedProvider({"judgments": [judgment(quote=complete)]})
    run = await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify_claims(context, [claim])
    quote_request = decisions.requests[1]
    assert quote_request.questions["claim_0_evidence"]["instructions"]["selected_quotes"] == [
        {"index": 0, "quote": "It resumes at one."},
    ]
    assert "Cedar Relay pauses" not in json.dumps([quote_request.state, quote_request.questions])
    assert llm.requests[0].payload["context_passages"] == context
    assert run.stats.claim_decisions[0].fallback_reason == "quote_disagreement"
    assert run.stats.claim_decisions[0].final_origin == "llm"
    assert run.report.claims[0].citations[0].quote == complete


@pytest.mark.parametrize("reason", ["INSUFFICIENT_EVIDENCE", "UNRESOLVED_CONFLICT"])
async def test_confident_unsupported_has_template_and_no_evidence_round(reason):
    decisions = Decisions({"claim_0_relation": "UNSUPPORTED", "claim_0_unsupported_reason": reason})
    run = await verifier(decisions=decisions).verify(REQUEST)
    claim = run.report.claims[0]
    assert claim.verdict == "UNSUPPORTED" and claim.citations == []
    assert "template" in claim.reasoning
    assert ("conflict" in claim.reasoning) == (reason == "UNRESOLVED_CONFLICT")
    assert run.stats.provider_calls == 1
    assert run.stats.claim_decisions[0].final_origin == "jev"


@pytest.mark.parametrize(("first", "second", "reason"), [
    ({"claim_0_relation": ("SUPPORTED", 0.6)}, None, "label_uncertain"),
    ({"claim_0_relation": "UNSUPPORTED",
      "claim_0_unsupported_reason": ("INSUFFICIENT_EVIDENCE", 0.6)},
     None, "unsupported_reason_uncertain"),
    ({"claim_0_selection": NO_ADEQUATE_BUNDLE}, None, "candidate_missing"),
    ({}, {"claim_0_evidence": ("SUPPORTED", 0.6)}, "quote_uncertain"),
    ({}, {"claim_0_evidence": "UNSUPPORTED"}, "quote_disagreement"),
])
async def test_uncertainty_requires_fallback_or_fails_whole_request(first, second, reason):
    decisions = Decisions(*([first] if second is None else [first, second]))
    with pytest.raises(VerificationError) as caught:
        await verifier(decisions=decisions).verify(REQUEST)
    assert caught.value.code == "confidence_unresolved"
    trace = caught.value.stats.claim_decisions[0]
    assert trace.fallback_reason == reason and trace.final_origin is None
    assert caught.value.stats.provider_calls == (1 if second is None else 2)


async def test_selection_score_is_recorded_but_does_not_gate_acceptance():
    decisions = Decisions({"claim_0_selection": ("B0", 0.01)}, {})
    run = await verifier(decisions=decisions).verify(REQUEST)
    assert run.stats.claim_decisions[0].selection.confidence == 0.01
    assert run.stats.claim_decisions[0].final_origin == "jev"


async def test_lower_derived_confidence_cannot_cross_raw_threshold():
    def rounded(request):
        answers = {key: choice(question["criteria"], next(iter(question["criteria"])))
                   for key, question in request.questions.items()}
        answers["claim_0_relation"] = ChoiceDecision(
            "SUPPORTED", 0.8, {"SUPPORTED": 0.8533333333333334,
                               "CONTRADICTED": 0.0733333333333333,
                               "UNSUPPORTED": 0.0733333333333333},
        )
        return DecisionResult(answers, TokenUsage(7, 3), "jev-1.14.0")

    with pytest.raises(VerificationError) as caught:
        await verifier(decisions=Decisions(rounded)).verify(REQUEST)
    trace = caught.value.stats.claim_decisions[0]
    assert trace.relation.confidence == 0.8
    assert trace.relation.derived_confidence == pytest.approx(0.78)
    assert trace.fallback_reason == "label_uncertain"


async def test_only_unresolved_original_ids_reach_independent_fallback_then_merge():
    claims = ["Oak stores 7 blocks.", "Oak uses checksums.", "Oak is on Earth."]
    decisions = Decisions({"claim_1_relation": ("SUPPORTED", 0.6),
                           "claim_2_relation": ("SUPPORTED", 0.6)}, {})
    llm = ScriptedProvider({"judgments": [judgment(2, verdict="UNSUPPORTED"),
                                        judgment(1, verdict="UNSUPPORTED")]})
    run = await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify_claims(
        REQUEST.context_passages, claims,
    )
    assert llm.requests[0].payload == {"context_passages": REQUEST.context_passages, "claims": [
        {"claim_id": 1, "claim_text": claims[1]}, {"claim_id": 2, "claim_text": claims[2]},
    ]}
    assert [c.claim_text for c in run.report.claims] == claims
    assert [t.final_origin for t in run.stats.claim_decisions] == ["jev", "llm", "llm"]
    assert [a.stage for a in run.stats.attempts] == ["jev_judgment", "jev_evidence", "fallback"]
    assert run.stats.usage == TokenUsage(24, 10)
    assert run.stats.response_models == ("jev-1.14.0", "fixed-model")


async def test_missing_candidates_escalates_instead_of_changing_supported_label():
    context = ["x" * 1_201]
    decisions = Decisions({})
    llm = ScriptedProvider({"judgments": [judgment(verdict="UNSUPPORTED")]})
    run = await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify_claims(
        context, [REQUEST.generated_answer],
    )
    assert "claim_0_selection" not in decisions.requests[0].questions
    assert decisions.requests[0].state["context_passages"] == context
    trace = run.stats.claim_decisions[0]
    assert trace.relation.choice == "SUPPORTED" and trace.final_origin == "llm"
    assert trace.fallback_reason == "candidate_missing"


async def test_fallback_id_and_quote_defects_have_one_repair_then_fail_with_trace():
    for defect in ({"judgments": [judgment(1)]},
                   {"judgments": [judgment(quote="fabricated")]},
                   {"judgments": [judgment(), judgment()]}):
        llm = ScriptedProvider(defect, defect)
        decisions = Decisions({"claim_0_relation": ("SUPPORTED", 0.6)})
        with pytest.raises(VerificationError) as caught:
            await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify(REQUEST)
        assert caught.value.code == "invalid_model_output"
        stats = caught.value.stats
        assert stats.provider_calls == 3 and stats.repairs == 1
        assert [a.repair for a in stats.attempts] == [False, False, True]
        assert [a.outcome for a in stats.attempts] == ["success", "failure", "failure"]
        assert [a.error_code for a in stats.attempts] == [
            None, "invalid_model_output", "invalid_model_output",
        ]
        assert stats.claim_decisions[0].fallback_reason == "label_uncertain"
        assert "validation_errors" in llm.requests[1].payload
        assert "fabricated" not in json.dumps(llm.requests[1].payload)


async def test_fallback_failure_retains_accepted_trace_but_returns_no_partial_report():
    decisions = Decisions({"claim_1_relation": ("SUPPORTED", 0.6)}, {})
    llm = ScriptedProvider(VerificationError("quota_exhausted"))
    with pytest.raises(VerificationError) as caught:
        await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify_claims(
            REQUEST.context_passages, [REQUEST.generated_answer, "Oak uses checksums."],
        )
    assert caught.value.code == "quota_exhausted"
    assert [trace.final_origin for trace in caught.value.stats.claim_decisions] == ["jev", None]
    assert caught.value.stats.provider_calls == 3
    assert not caught.value.stats.usage.complete


async def test_extraction_failure_does_not_switch_to_rule_claims():
    llm = ScriptedProvider("malformed", "malformed")
    decisions = Decisions()
    with pytest.raises(VerificationError) as caught:
        await verifier("jev_optimized", decisions=decisions, llm=llm).verify(REQUEST)
    assert caught.value.code == "invalid_model_output"
    assert caught.value.stats.provider_calls == 2 and not decisions.requests


async def test_retry_failure_preserves_known_and_unknown_usage_per_attempt():
    error = VerificationError("upstream_unavailable", stats=RunStats(
        usage=TokenUsage(2, 1, complete=False), response_models=("jev-1.14.0",),
    ))
    decisions = Decisions(error, {}, {})
    run = await verifier(decisions=decisions).verify(REQUEST)
    assert run.stats.usage == TokenUsage(16, 7, complete=False)
    assert run.stats.retries == 1 and run.stats.provider_calls == 3
    assert [a.retry for a in run.stats.attempts] == [False, True, False]
    assert [a.outcome for a in run.stats.attempts] == ["failure", "success", "success"]
    assert run.stats.attempts[0].error_code == "upstream_unavailable"


@pytest.mark.parametrize("code", ["authentication_failed", "quota_exhausted",
                                 "provider_protocol_error", "unsupported_capability"])
async def test_provider_failures_do_not_trigger_semantic_fallback(code):
    decisions = Decisions(VerificationError(code))
    llm = ScriptedProvider()
    with pytest.raises(VerificationError) as caught:
        await verifier(decisions=decisions, llm=llm, jev_fallback=True).verify(REQUEST)
    assert caught.value.code == code and not llm.requests
    assert caught.value.stats.provider_calls == 1
    assert caught.value.stats.attempts[0].outcome == "failure"
    assert not caught.value.stats.usage.complete


async def test_shared_cap_includes_extraction_repair_jev_retry_and_fallback():
    llm = ScriptedProvider("invalid", extraction(REQUEST.generated_answer),
                           {"judgments": []}, {"judgments": [judgment()]})
    decisions = Decisions(VerificationError("upstream_unavailable"),
                           {"claim_0_relation": ("SUPPORTED", 0.6)})
    with pytest.raises(VerificationError) as caught:
        await verifier("jev_optimized", decisions=decisions, llm=llm, jev_fallback=True,
                       max_provider_attempts=5).verify(REQUEST)
    assert caught.value.code == "attempt_budget_exhausted"
    stats = caught.value.stats
    assert stats.provider_calls == 5 and stats.retries == 1 and stats.repairs == 1
    assert [a.stage for a in stats.attempts] == [
        "extraction", "extraction", "jev_judgment", "jev_judgment", "fallback",
    ]
    assert len(llm.requests) == 3 and len(decisions.requests) == 2


async def test_default_cap_allows_sixth_valid_fallback_repair_without_resampling():
    llm = ScriptedProvider("invalid", extraction(REQUEST.generated_answer),
                           {"judgments": []}, {"judgments": [judgment()]})
    decisions = Decisions(VerificationError("upstream_unavailable"),
                           {"claim_0_relation": ("SUPPORTED", 0.6)})
    run = await verifier("jev_optimized", decisions=decisions, llm=llm,
                         jev_fallback=True).verify(REQUEST)
    assert run.stats.provider_calls == 6 and run.stats.repairs == 2 and run.stats.retries == 1
    assert len(llm.requests) == 4 and len(decisions.requests) == 2
    assert run.stats.claim_decisions[0].final_origin == "llm"


async def test_fallback_configuration_preflight_happens_before_jev():
    decisions = Decisions()
    instance = verifier(decisions=decisions, jev_fallback=True)
    try:
        with pytest.raises(VerificationError) as caught:
            await instance.verify(REQUEST)
        assert caught.value.code == "not_configured"
        assert caught.value.stats.provider_calls == 0 and not decisions.requests
    finally:
        await instance.aclose()


async def test_provider_timeout_is_not_retried_and_operation_can_recover():
    async def stall(_request):
        await asyncio.sleep(10)

    decisions = Decisions(stall, {}, {})
    instance = verifier(decisions=decisions, provider_timeout=0.01)
    with pytest.raises(VerificationError) as caught:
        await instance.verify(REQUEST)
    assert caught.value.code == "upstream_timeout"
    assert caught.value.stats.provider_calls == 1 and caught.value.stats.retries == 0
    assert caught.value.stats.attempts[0].outcome == "failure"
    run = await instance.verify(REQUEST)
    assert run.stats.provider_calls == 2 and run.report.claims[0].verdict == "SUPPORTED"


async def test_cancellation_joins_attempt_and_does_not_dispatch_next_stage():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def stall(_request):
        started.set()
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    decisions = Decisions(stall)
    instance = verifier(decisions=decisions)
    budget = instance._budget()
    instance._budget = lambda: budget
    task = asyncio.create_task(instance.verify(REQUEST))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set() and len(decisions.requests) == 1
    assert budget.attempts[0].outcome == "cancelled"
    assert not budget.attempts[0].usage.complete


async def test_close_releases_both_injected_providers():
    decisions, llm = Decisions(), ScriptedProvider()
    await verifier(decisions=decisions, llm=llm).aclose()
    assert decisions.closed and llm.closed


async def test_operation_deadline_cancels_jev_and_keeps_attempt_accounting():
    async def stall(_request):
        await asyncio.sleep(10)

    decisions = Decisions(stall)
    with pytest.raises(VerificationError) as caught:
        await verifier(decisions=decisions, operation_timeout=0.01).verify(REQUEST)
    assert caught.value.code == "deadline_exceeded"
    assert len(decisions.requests) == 1 and caught.value.stats.provider_calls == 1
    assert caught.value.stats.attempts[0].outcome == "cancelled"


async def test_unconfigured_native_jev_is_checked_without_calling_decider():
    from grounding.jev_verifier import JevVerifier

    decisions = Decisions()
    instance = JevVerifier("jev_minimal", settings(jev_fallback=False), None, decisions,
                           injected_llm=False, injected_decision=False)
    with pytest.raises(VerificationError) as caught:
        await instance.verify(REQUEST)
    assert caught.value.code == "not_configured"
    assert caught.value.stats.provider_calls == 0 and not decisions.requests


@pytest.mark.parametrize(("status", "code"), [
    ({"signed_in": False, "plan_enabled": False}, "not_configured"),
    ({"signed_in": True, "plan_enabled": False}, "plan_not_authorized"),
    ({"signed_in": True, "plan_enabled": True}, None),
])
async def test_codex_preflight_uses_only_safe_selected_app_status(monkeypatch, status, code):
    from grounding.codex_auth import CredentialStore
    from grounding.jev_verifier import JevVerifier

    observed = []

    def safe_status(store):
        observed.append(store.profile)
        return status

    monkeypatch.setattr(CredentialStore, "status", safe_status)
    decisions = Decisions({}, {})
    instance = JevVerifier("jev_minimal", settings(provider="codex"), ScriptedProvider(),
                           decisions, injected_llm=False, injected_decision=True)
    if code:
        with pytest.raises(VerificationError) as caught:
            await instance.verify(REQUEST)
        assert caught.value.code == code and not decisions.requests
    else:
        run = await instance.verify(REQUEST)
        assert run.report.claims[0].verdict == "SUPPORTED"
    assert observed == ["default"]


@pytest.mark.parametrize("source", ["settings", "environment"])
def test_explicit_jev_factory_validates_optional_config_under_minimal_settings(
    monkeypatch, tmp_path, source,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GROUNDING_APPROACH", "minimal")
    monkeypatch.setenv("TYPESAFE_MODEL", "moving-alias")
    config = settings(jev_model="moving-alias") if source == "settings" else None
    with pytest.raises(VerificationError) as caught:
        build_verifier("jev_minimal", settings=config, provider=ScriptedProvider(),
                       decision_provider=Decisions())
    assert caught.value.code == "not_configured"
