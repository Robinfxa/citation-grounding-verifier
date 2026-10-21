import pytest

from grounding.contracts import ChoiceDecision, VerificationError


def test_parser_tolerance_cannot_promote_an_uncertain_distribution():
    probabilities = {"SUPPORTED": 0.8566667, "CONTRADICTED": 0.07166665,
                     "UNSUPPORTED": 0.07166665}
    decision = ChoiceDecision("SUPPORTED", 0.8, probabilities)
    assert decision.derived_confidence == pytest.approx(0.78500005)
    assert decision.gate_score < 0.8
    assert decision.confidence == 0.8
    assert decision.probabilities == probabilities


def test_reported_score_remains_a_gate_when_derived_score_is_higher():
    decision = ChoiceDecision("SUPPORTED", 0.79,
                              {"SUPPORTED": 0.94, "CONTRADICTED": 0.03, "UNSUPPORTED": 0.03})
    assert decision.derived_confidence == pytest.approx(0.91)
    assert decision.gate_score == 0.79


def test_reason_and_relation_use_their_actual_option_counts():
    reason = ChoiceDecision("INSUFFICIENT_EVIDENCE", 0.8,
                            {"INSUFFICIENT_EVIDENCE": 0.9, "UNRESOLVED_CONFLICT": 0.1})
    relation = ChoiceDecision("UNSUPPORTED", 0.8,
                              {"SUPPORTED": 0.05, "CONTRADICTED": 0.05, "UNSUPPORTED": 0.9})
    assert reason.derived_confidence == pytest.approx(0.8)
    assert relation.derived_confidence == pytest.approx(0.85)
    assert reason.gate_score == relation.gate_score == 0.8


def test_abstention_is_an_error_not_a_semantic_verdict():
    error = VerificationError("confidence_unresolved")
    assert error.status_code == 502
    assert not error.retryable
