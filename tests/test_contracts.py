import pytest
from pydantic import ValidationError

from grounding.contracts import (
    MAX_CONTEXT_CHARS,
    Citation,
    Claim,
    InvalidReport,
    TokenUsage,
    VerificationReport,
    VerifyRequest,
    validate_report,
)


def report(quote="Café retains 3 replicas.", index=0):
    return VerificationReport(
        claims=[
            Claim(
                claim_text="Café retains 3 replicas.",
                verdict="SUPPORTED",
                reasoning="The source explicitly states the replica count.",
                citations=[Citation(index=index, quote=quote)],
            )
        ]
    )


@pytest.mark.parametrize("index", [True, False, 0.0, "0", -1])
def test_indices_are_strict_nonnegative_integers(index):
    with pytest.raises(ValidationError):
        Citation(index=index, quote="a")


@pytest.mark.parametrize("quote", ["", "  ", "\n\t"])
def test_blank_evidence_is_not_evidence(quote):
    with pytest.raises(ValidationError):
        Citation(index=0, quote=quote)


@pytest.mark.parametrize(
    "quote", ["Cafe\u0301 retains 3 replicas.", "Café retains 3 Replicas.", "Café retains  3 replicas."]
)
def test_quotes_are_not_normalized(quote):
    with pytest.raises(InvalidReport):
        validate_report(report(quote), ["Café retains 3 replicas."])


def test_index_must_identify_the_passage_that_contains_the_quote():
    with pytest.raises(InvalidReport):
        validate_report(report(index=1), ["Café retains 3 replicas.", "Unrelated text."])
    with pytest.raises(InvalidReport):
        validate_report(report(index=1), ["Café retains 3 replicas."])


def test_quote_cannot_cross_passage_boundaries():
    with pytest.raises(InvalidReport):
        validate_report(report(quote="3 replicas."), ["Café retains 3 ", "replicas."])


def test_exact_unicode_and_newline_substrings_are_preserved():
    quote = "😀 café\nthree replicas"
    actual = report(quote=quote)
    assert validate_report(actual, [f"prefix {quote} suffix"]) == actual


@pytest.mark.parametrize("verdict,citations", [("SUPPORTED", []), ("CONTRADICTED", [])])
def test_supported_and_contradicted_require_evidence(verdict, citations):
    with pytest.raises(ValidationError):
        Claim(claim_text="A.", verdict=verdict, reasoning="Evidence.", citations=citations)


def test_unsupported_must_have_no_evidence():
    with pytest.raises(ValidationError):
        Claim(
            claim_text="A.", verdict="UNSUPPORTED", reasoning="Absent.",
            citations=[Citation(index=0, quote="A.")],
        )


def test_input_rejects_coercion_extra_keys_and_oversized_aggregate():
    for value in (
        {"context_passages": [1], "generated_answer": "A"},
        {"context_passages": [], "generated_answer": "A", "secret": "ignored?"},
        {"context_passages": ["a" * 16_000] * 7, "generated_answer": "A"},
    ):
        with pytest.raises(ValidationError):
            VerifyRequest.model_validate(value)
    assert 16_000 * 7 > MAX_CONTEXT_CHARS
    assert VerifyRequest(context_passages=[], generated_answer="").context_passages == []


def test_unknown_usage_remains_unknown_when_added_to_known_usage():
    combined = TokenUsage(10, 2, 3) + TokenUsage(complete=False)
    assert (combined.input_tokens, combined.output_tokens, combined.cached_input_tokens) == (10, 2, 3)
    assert combined.complete is False
