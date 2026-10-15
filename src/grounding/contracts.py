"""Shared boundaries used by the HTTP service, providers and independent evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

Verdict = Literal["SUPPORTED", "CONTRADICTED", "UNSUPPORTED"]
VERDICTS: tuple[Verdict, ...] = ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED")
MAX_PASSAGES = 32
MAX_PASSAGE_CHARS = 16_000
MAX_CONTEXT_CHARS = 96_000
MAX_ANSWER_CHARS = 12_000
MAX_CLAIMS = 64
MAX_BODY_BYTES = 1_048_576


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class VerifyRequest(StrictModel):
    context_passages: list[StrictStr] = Field(max_length=MAX_PASSAGES)
    generated_answer: StrictStr = Field(max_length=MAX_ANSWER_CHARS)

    @model_validator(mode="after")
    def bounded_context(self) -> Self:
        if any(len(passage) > MAX_PASSAGE_CHARS for passage in self.context_passages):
            raise ValueError("passage_too_long")
        if sum(map(len, self.context_passages)) > MAX_CONTEXT_CHARS:
            raise ValueError("context_too_long")
        return self


class Citation(StrictModel):
    index: StrictInt = Field(ge=0)
    quote: StrictStr = Field(min_length=1, max_length=MAX_PASSAGE_CHARS)

    @model_validator(mode="after")
    def nonblank_quote(self) -> Self:
        if not self.quote.strip():
            raise ValueError("blank_quote")
        return self


class Claim(StrictModel):
    claim_text: StrictStr = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    verdict: Verdict
    reasoning: StrictStr = Field(min_length=1, max_length=2_000)
    citations: list[Citation] = Field(max_length=MAX_PASSAGES)

    @model_validator(mode="after")
    def evidence_shape(self) -> Self:
        if not self.claim_text.strip() or not self.reasoning.strip():
            raise ValueError("blank_claim_or_reasoning")
        if self.verdict == "UNSUPPORTED" and self.citations:
            raise ValueError("unsupported_has_citations")
        if self.verdict != "UNSUPPORTED" and not self.citations:
            raise ValueError("evidence_required")
        return self


class VerificationReport(StrictModel):
    claims: list[Claim] = Field(max_length=MAX_CLAIMS)


class InvalidReport(ValueError):
    """Safe positional defect codes; never source text or a raw model response."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(issues))


def validate_report(report: VerificationReport, passages: list[str]) -> VerificationReport:
    """Check request-dependent provenance without normalizing or rewriting quotations."""
    issues: list[str] = []
    for claim_no, claim in enumerate(report.claims):
        for citation_no, citation in enumerate(claim.citations):
            prefix = f"claims[{claim_no}].citations[{citation_no}]"
            # AIDEV-NOTE: bool is an int subclass and Python accepts negative indices.
            if type(citation.index) is not int or not 0 <= citation.index < len(passages):
                issues.append(f"{prefix}.index_out_of_bounds")
            elif not citation.quote.strip() or citation.quote not in passages[citation.index]:
                issues.append(f"{prefix}.quote_not_verbatim")
    if issues:
        raise InvalidReport(issues)
    return report


@dataclass(frozen=True)
class TokenUsage:
    """Known token totals; complete=False means some billable usage is unknown."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    complete: bool = True

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_input_tokens + other.cached_input_tokens,
            self.complete and other.complete,
        )


@dataclass(frozen=True)
class RunStats:
    provider: str = "heuristic"
    requested_model: str | None = None
    response_models: tuple[str, ...] = ()
    provider_calls: int = 0
    retries: int = 0
    repairs: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0


@dataclass(frozen=True)
class VerificationRun:
    report: VerificationReport
    stats: RunStats = field(default_factory=RunStats)


# Safe external messages are selected by code, never constructed from an upstream exception.
ERRORS: dict[str, tuple[int, str, bool]] = {
    "invalid_request": (422, "The request does not satisfy the input contract.", False),
    "body_too_large": (413, "The request body exceeds the configured limit.", False),
    "not_configured": (503, "The selected model provider is not configured.", False),
    "authentication_failed": (503, "The selected provider could not authenticate.", False),
    "upstream_unavailable": (503, "The model provider is temporarily unavailable.", True),
    "rate_limited": (503, "The model provider is currently rate limited.", True),
    "quota_exhausted": (503, "The app's ChatGPT usage limit was reached. Check ChatGPT Settings → Usage.", False),
    "plan_not_authorized": (503, "ChatGPT plan usage has not been authorized for this app.", False),
    "unsupported_capability": (502, "The provider does not support this request capability.", False),
    "response_too_large": (502, "The provider response exceeded the configured limit.", False),
    "upstream_timeout": (504, "The model provider timed out.", True),
    "deadline_exceeded": (504, "The verification operation exceeded its deadline.", False),
    "attempt_budget_exhausted": (503, "The provider attempt budget was exhausted.", False),
    "provider_protocol_error": (502, "The model provider returned an invalid response.", False),
    "model_refused": (502, "The model declined the verification request.", False),
    "model_incomplete": (502, "The model response was incomplete.", False),
    "invalid_model_output": (502, "The model output failed verification checks.", False),
    "internal_error": (500, "The verification operation failed internally.", False),
}


class VerificationError(Exception):
    def __init__(self, code: str, *, stats: RunStats | None = None) -> None:
        status, message, retryable = ERRORS[code]
        self.code = code
        self.status_code = status
        self.message = message
        self.retryable = retryable
        self.stats = stats
        super().__init__(message)


@dataclass(frozen=True)
class StructuredRequest:
    schema_name: str
    schema: dict[str, Any]
    instructions: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(complete=False))
    model: str | None = None


class StructuredProvider(Protocol):
    name: str
    model: str | None

    async def generate(self, request: StructuredRequest) -> ProviderResult: ...

    async def aclose(self) -> None: ...


class Verifier(Protocol):
    name: str

    async def verify(self, request: VerifyRequest) -> VerificationRun: ...

    async def verify_claims(
        self, context_passages: list[str], claims: list[str]
    ) -> VerificationRun: ...

    async def aclose(self) -> None: ...
