"""Three verifiers sharing strict integrity checks and one per-operation budget."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import Field, StrictInt, StrictStr, ValidationError

from grounding import diagnostics, heuristics, prompts
from grounding.config import Settings
from grounding.contracts import (
    MAX_ANSWER_CHARS,
    MAX_CLAIMS,
    MAX_PASSAGES,
    Citation,
    Claim,
    InvalidReport,
    ProviderResult,
    RunStats,
    StrictModel,
    StructuredProvider,
    StructuredRequest,
    TokenUsage,
    Verdict,
    VerificationError,
    VerificationReport,
    VerificationRun,
    VerifyRequest,
    validate_report,
)
from grounding.providers import MAX_RESPONSE_BYTES, OpenAIProvider


class _ExtractedClaim(StrictModel):
    claim_text: StrictStr = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    answer_quote: StrictStr = Field(min_length=1, max_length=MAX_ANSWER_CHARS)


class _Extraction(StrictModel):
    claims: list[_ExtractedClaim] = Field(max_length=MAX_CLAIMS)


class _Judgment(StrictModel):
    claim_id: StrictInt = Field(ge=0, lt=MAX_CLAIMS)
    verdict: Verdict
    reasoning: StrictStr = Field(min_length=1, max_length=2_000)
    citations: list[Citation] = Field(max_length=MAX_PASSAGES)


class _Judgments(StrictModel):
    judgments: list[_Judgment] = Field(max_length=MAX_CLAIMS)


class _OracleClaims(StrictModel):
    claims: list[StrictStr] = Field(max_length=MAX_CLAIMS)


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


@dataclass
class _Budget:
    provider: str
    model: str | None
    started: float = field(default_factory=time.monotonic)
    calls: int = 0
    retries: int = 0
    repairs: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    models: list[str] = field(default_factory=list)

    def measured(self, usage: TokenUsage, models: tuple[str, ...] = ()) -> None:
        self.usage += usage
        for model in models:
            if model not in self.models:
                self.models.append(model)

    def stats(self) -> RunStats:
        return RunStats(
            provider=self.provider, requested_model=self.model, response_models=tuple(self.models),
            provider_calls=self.calls, retries=self.retries, repairs=self.repairs,
            usage=self.usage, latency_ms=(time.monotonic() - self.started) * 1_000,
        )

    def emit(self, stage: str, event: str, outcome: str, *, code: str | None = None) -> None:
        diagnostics.emit(
            stage, event, outcome, error_code=code,
            provider_calls=self.calls, retries=self.retries, repairs=self.repairs,
        )


class _BaseVerifier:
    name: str

    def __init__(self, settings: Settings, provider: StructuredProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider

    async def _run(self, action: Callable[[_Budget], Awaitable[VerificationReport]]) -> VerificationRun:
        budget = _Budget(
            self.provider.name if self.provider else "heuristic",
            self.provider.model if self.provider else None,
        )
        with diagnostics.operation(enabled=self.settings.diagnostics):
            budget.emit("verification", "start", "started")
            try:
                async with asyncio.timeout(self.settings.operation_timeout):
                    report = await action(budget)
            except asyncio.CancelledError:
                budget.emit("verification", "end", "cancelled")
                raise
            except Exception as error:
                if isinstance(error, TimeoutError):
                    code = "deadline_exceeded"
                elif isinstance(error, VerificationError):
                    code = error.code
                else:
                    code = "internal_error"
                budget.emit("verification", "end", "failure", code=code)
                failure = VerificationError(code, stats=budget.stats())
                if isinstance(error, VerificationError):
                    failure.retryable = error.retryable
                raise failure from None
            diagnostics.emit(
                "verification", "end", "success", claims=len(report.claims),
                provider_calls=budget.calls, retries=budget.retries, repairs=budget.repairs,
            )
            return VerificationRun(report, budget.stats())

    async def verify(self, request: VerifyRequest) -> VerificationRun:
        async def action(budget: _Budget) -> VerificationReport:
            if not request.generated_answer.strip():
                return VerificationReport(claims=[])
            return await self._verify(request, budget)
        return await self._run(action)

    async def verify_claims(self, context_passages: list[str], claims: list[str]) -> VerificationRun:
        async def action(budget: _Budget) -> VerificationReport:
            try:
                VerifyRequest(context_passages=context_passages, generated_answer="")
                _OracleClaims(claims=claims)
                if any(not c.strip() or len(c) > MAX_ANSWER_CHARS for c in claims):
                    raise ValueError
            except (ValidationError, ValueError):
                raise VerificationError("invalid_request") from None
            if not claims:
                return VerificationReport(claims=[])
            if not context_passages:
                return _unsupported(claims)
            return await self._judge(context_passages, claims, budget)
        return await self._run(action)

    async def aclose(self) -> None:
        if self.provider:
            await self.provider.aclose()


def _unsupported(claims: list[str]) -> VerificationReport:
    return VerificationReport(claims=[
        Claim(claim_text=c, verdict="UNSUPPORTED", reasoning="No context was supplied.", citations=[])
        for c in claims
    ])


class HeuristicVerifier(_BaseVerifier):
    name = "heuristic"

    async def _verify(self, request: VerifyRequest, budget: _Budget) -> VerificationReport:
        return await self._judge(
            request.context_passages, heuristics.extract_claims(request.generated_answer), budget
        )

    async def _judge(self, passages: list[str], claims: list[str], budget: _Budget) -> VerificationReport:
        report = validate_report(heuristics.judge(passages, claims), passages)
        budget.emit("heuristic", "validation", "success")
        return report


class LLMVerifier(_BaseVerifier):
    def __init__(self, name: str, settings: Settings, provider: StructuredProvider) -> None:
        super().__init__(settings, provider)
        self.name = name

    async def _attempt(self, request: StructuredRequest, stage: str, budget: _Budget) -> ProviderResult:
        for retry in range(self.settings.transport_retries + 1):
            if budget.calls >= self.settings.max_provider_attempts:
                raise VerificationError("attempt_budget_exhausted")
            if retry:
                budget.retries += 1
            budget.calls += 1
            budget.emit(stage, "provider_attempt", "started")
            try:
                async with asyncio.timeout(self.settings.provider_timeout):
                    result = await self.provider.generate(request)
                if not isinstance(result, ProviderResult):
                    raise VerificationError("provider_protocol_error")
            except asyncio.CancelledError:
                budget.measured(TokenUsage(complete=False))
                budget.emit(stage, "provider_attempt", "cancelled")
                raise
            except Exception as error:
                if isinstance(error, TimeoutError):
                    error = VerificationError("upstream_timeout")
                    # AIDEV-NOTE: the outer timer cannot know whether output was
                    # already consumed. Do not resend an ambiguously completed call.
                    error.retryable = False
                if not isinstance(error, VerificationError):
                    error = VerificationError("internal_error")
                if error.stats:
                    budget.measured(error.stats.usage, error.stats.response_models)
                else:
                    budget.measured(TokenUsage(complete=False))
                budget.emit(stage, "provider_attempt", "failure", code=error.code)
                if not error.retryable or retry == self.settings.transport_retries:
                    raise error from None
                if budget.calls >= self.settings.max_provider_attempts:
                    raise VerificationError("attempt_budget_exhausted") from None
                budget.emit(stage, "retry", "started", code=error.code)
                await asyncio.sleep(self.settings.retry_delay)
            else:
                budget.measured(result.usage, (result.model,) if result.model else ())
                budget.emit(stage, "provider_attempt", "success")
                return result
        raise VerificationError("attempt_budget_exhausted")  # Defensive; loop always returns/raises.

    async def _structured(
        self,
        request: StructuredRequest,
        stage: str,
        budget: _Budget,
        validate: Callable[[Any], Any],
    ) -> Any:
        for repair in range(2 if self.name == "optimized" else 1):
            if repair:
                if budget.calls >= self.settings.max_provider_attempts:
                    raise VerificationError("attempt_budget_exhausted")
                budget.repairs += 1
                budget.emit(stage, "repair", "started", code="invalid_model_output")
            result = await self._attempt(request, stage, budget)
            try:
                if len(result.text.encode("utf-8")) > MAX_RESPONSE_BYTES:
                    raise VerificationError("response_too_large")
                value = validate(json.loads(result.text, object_pairs_hook=_json_object))
            except (ValueError, ValidationError, InvalidReport, RecursionError, UnicodeError) as error:
                # AIDEV-NOTE: do not serialize Pydantic errors or prior model output.
                # Only our fixed positional defect codes can enter a repair request.
                issues = list(error.issues)[:8] if isinstance(error, InvalidReport) else ["schema_invalid"]
                budget.emit(stage, "validation", "failure", code="invalid_model_output")
                if self.name != "optimized" or repair == 1:
                    raise VerificationError("invalid_model_output") from None
                request = replace(request, payload={**request.payload, "validation_errors": issues})
            else:
                budget.emit(stage, "validation", "success")
                return value
        raise VerificationError("invalid_model_output")

    async def _verify(self, request: VerifyRequest, budget: _Budget) -> VerificationReport:
        if self.name == "minimal":
            return await self._structured(
                StructuredRequest(
                    "verification_report", VerificationReport.model_json_schema(), prompts.MINIMAL,
                    request.model_dump(),
                ),
                "minimal", budget,
                lambda data: validate_report(VerificationReport.model_validate(data), request.context_passages),
            )

        def extracted(data: Any) -> list[str]:
            value = _Extraction.model_validate(data)
            claims = []
            for index, claim in enumerate(value.claims):
                if not claim.claim_text.strip() or not claim.answer_quote.strip():
                    raise InvalidReport([f"claims[{index}].blank_claim_or_anchor"])
                if claim.answer_quote not in request.generated_answer:
                    raise InvalidReport([f"claims[{index}].anchor_not_verbatim"])
                if claim.claim_text in claims:
                    raise InvalidReport([f"claims[{index}].duplicate_claim"])
                claims.append(claim.claim_text)
            return claims

        claims = await self._structured(
            StructuredRequest(
                "atomic_claims", _Extraction.model_json_schema(), prompts.EXTRACT,
                {"generated_answer": request.generated_answer},
            ),
            "extraction", budget, extracted,
        )
        if not claims:
            return VerificationReport(claims=[])
        if not request.context_passages:
            return _unsupported(claims)
        return await self._judge(request.context_passages, claims, budget)

    async def _judge(self, passages: list[str], claims: list[str], budget: _Budget) -> VerificationReport:
        def judgments(data: Any) -> VerificationReport:
            value = _Judgments.model_validate(data)
            ids = [item.claim_id for item in value.judgments]
            # AIDEV-NOTE: order is irrelevant; exact ID multiplicity and original text are not.
            if len(ids) != len(claims) or set(ids) != set(range(len(claims))):
                raise InvalidReport(["judgments.claim_id_coverage"])
            by_id = {item.claim_id: item for item in value.judgments}
            report = VerificationReport(claims=[
                Claim(claim_text=text, **by_id[index].model_dump(exclude={"claim_id"}))
                for index, text in enumerate(claims)
            ])
            return validate_report(report, passages)

        return await self._structured(
            StructuredRequest(
                "claim_judgments", _Judgments.model_json_schema(),
                prompts.JUDGE if self.name == "optimized" else prompts.MINIMAL_ORACLE,
                {"context_passages": passages, "claims": [
                    {"claim_id": index, "claim_text": text} for index, text in enumerate(claims)
                ]},
            ),
            "judgment", budget, judgments,
        )


def build_verifier(
    name: str, *, settings: Settings | None = None, provider: StructuredProvider | None = None
) -> _BaseVerifier:
    if name not in {"heuristic", "minimal", "optimized"}:
        raise ValueError("Unknown verifier approach.")
    settings = settings or Settings.from_env()
    if name == "heuristic":
        return HeuristicVerifier(settings)
    if provider is None:
        if settings.provider == "codex":
            from grounding.codex_provider import CodexProvider

            provider = CodexProvider(
                model=settings.model, timeout_seconds=settings.provider_timeout,
                profile=settings.auth_profile, auth_dir=settings.auth_dir,
            )
        else:
            provider = OpenAIProvider(
                model=settings.model, api_key=settings.api_key, base_url=settings.base_url,
                timeout_seconds=settings.provider_timeout, max_output_tokens=settings.max_output_tokens,
            )
    return LLMVerifier(name, settings, provider)
