"""Bounded, single-attempt native TypeSafe Choice decisions; no credential discovery."""

from __future__ import annotations

import json
import math
import re
from typing import Any

import httpx

from grounding import diagnostics
from grounding.contracts import (
    ChoiceDecision,
    DecisionRequest,
    DecisionResult,
    RunStats,
    TokenUsage,
    VerificationError,
)
from grounding.providers import MAX_RESPONSE_BYTES

MODEL = "jev-1.14.0"
PROBABILITY_SUM_TOLERANCE = 0.001
ARGMAX_TOLERANCE = 0.000001
CONFIDENCE_TOLERANCE = 0.02


def _decode(content: bytes) -> tuple[Any, bool]:
    duplicate_keys = False

    def json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal duplicate_keys
        result, seen = {}, set()
        for key, value in pairs:
            if key in seen:
                # AIDEV-NOTE: discard every ambiguous value, including third occurrences.
                # Retain unique sibling counters, then reject the entire response in _parse.
                result.pop(key, None)
                duplicate_keys = True
            else:
                seen.add(key)
                result[key] = value
        return result

    data = json.loads(content.decode("utf-8"), object_pairs_hook=json_object)
    return data, duplicate_keys


def _check_json(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("non_string_json_key")
            _check_json(item)
    elif isinstance(value, list):
        for item in value:
            _check_json(item)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("non_json_value")


def _encode(value: Any) -> bytes:
    _check_json(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _usage(value: Any) -> TokenUsage:
    if not isinstance(value, dict):
        return TokenUsage(complete=False)
    incoming, outgoing = value.get("input_tokens"), value.get("output_tokens")
    valid_input = type(incoming) is int and incoming >= 0
    valid_output = type(outgoing) is int and outgoing >= 0
    # Native usage reports billable input and output, with no cached-token field.
    return TokenUsage(
        input_tokens=incoming if valid_input else 0,
        output_tokens=outgoing if valid_output else 0,
        complete=valid_input and valid_output,
    )


def _probability(value: Any) -> bool:
    return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)


def _parse(
    data: Any, options: dict[str, tuple[str, ...]], requested_model: str, *, duplicate_keys: bool
) -> DecisionResult:
    if not isinstance(data, dict):
        raise VerificationError("provider_protocol_error")
    model = data.get("model")
    if (
        not isinstance(model, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", model) is None
    ):
        model = None
    stats = RunStats(
        provider="typesafe",
        requested_model=requested_model,
        provider_calls=1,
        response_models=(model,) if model else (),
        usage=_usage(data.get("usage")),
    )

    def fail(
        reason: str, *, probability_count: int | None = None, probability_sum: float | None = None
    ) -> None:
        # AIDEV-NOTE: fixed reasons and bounded aggregates exclude response entries and text.
        diagnostics.emit(
            "jev_decision",
            "validation",
            "failure",
            error_code="provider_protocol_error",
            protocol_reason=reason,
            probability_count=probability_count,
            probability_sum=probability_sum,
            probability_sum_tolerance=PROBABILITY_SUM_TOLERANCE,
        )
        raise VerificationError("provider_protocol_error", stats=stats)

    # AIDEV-NOTE: read trustworthy counters before validating decisions or model drift.
    if duplicate_keys:
        fail("duplicate_json_key")
    if model != requested_model:
        fail("returned_model")
    answers = data.get("answers")
    if not isinstance(answers, dict) or answers.keys() != options.keys():
        fail("answer_coverage")
    decisions = {}
    for question_id, criteria in options.items():
        answer = answers[question_id]
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            fail("answer_type")
        choice, confidence = answer.get("choice"), answer.get("confidence")
        probabilities = answer.get("probabilities")
        if not isinstance(choice, str) or choice not in criteria:
            fail("choice_not_declared")
        if not _probability(confidence):
            fail("confidence_invalid")
        if not isinstance(probabilities, dict) or probabilities.keys() != set(criteria):
            fail("probability_keys")
        if not all(_probability(value) for value in probabilities.values()):
            fail("probability_invalid")
        total = math.fsum(probabilities.values())
        if abs(total - 1) > PROBABILITY_SUM_TOLERANCE:
            fail("probability_sum", probability_count=len(probabilities), probability_sum=total)
        if max(probabilities.values()) - probabilities[choice] > ARGMAX_TOLERANCE:
            fail("choice_not_argmax")
        decision = ChoiceDecision(choice, confidence, probabilities)
        # AIDEV-NOTE: tolerance validates the wire; shared gate_score keeps the lower score.
        # Never renormalize probabilities or let parser tolerance relax a routing threshold.
        difference = abs(confidence - decision.derived_confidence)
        # Only absorb floating-point arithmetic at the fixed tolerance boundary;
        # the returned values and shared conservative gate remain untouched.
        if difference > CONFIDENCE_TOLERANCE and not math.isclose(
            difference, CONFIDENCE_TOLERANCE, rel_tol=0, abs_tol=4 * math.ulp(1.0)
        ):
            fail("confidence_formula")
        decisions[question_id] = decision
    return DecisionResult(decisions, usage=stats.usage, model=model)


class JevProvider:
    name = "typesafe"

    def __init__(
        self,
        *,
        model: str = MODEL,
        api_key: str | None = None,
        base_url: str = "https://api.typesafe.ai/v1",
        timeout_seconds: float = 30,
        max_request_bytes: int = 256_000,
        max_question_bytes: int = 128_000,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key.strip() if isinstance(api_key, str) else None
        self._url = base_url.rstrip("/") + "/systemone" if isinstance(base_url, str) else ""
        self._timeout = timeout_seconds
        self._max_request_bytes = max_request_bytes
        self._max_question_bytes = max_question_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=False)

    def _configured(self) -> None:
        key = self._api_key
        valid = self.model == MODEL and bool(key)
        valid &= bool(key and key.isascii() and key.isprintable() and " " not in key)
        valid &= type(self._timeout) in (int, float) and 0 < self._timeout < math.inf
        valid &= type(self._max_request_bytes) is int and self._max_request_bytes > 0
        valid &= type(self._max_question_bytes) is int and self._max_question_bytes > 0
        if valid:
            valid = self._max_question_bytes <= self._max_request_bytes
        try:
            url = httpx.URL(self._url)
            valid &= url.scheme in ("https", "http") and bool(url.host)
            valid &= not (url.userinfo or url.query or url.fragment)
        except (httpx.InvalidURL, ValueError):
            valid = False
        if not valid:
            raise VerificationError("not_configured")

    def _prepare(self, request: DecisionRequest) -> tuple[bytes, dict[str, tuple[str, ...]]]:
        try:
            if not isinstance(request, DecisionRequest) or not isinstance(
                request.state, (str, dict, list)
            ):
                raise ValueError("invalid_state")
            questions = request.questions
            if not isinstance(questions, dict) or not questions:
                raise ValueError("questions_required")
            options = {}
            for question_id, question in questions.items():
                if not isinstance(question_id, str) or not question_id.strip():
                    raise ValueError("invalid_question_id")
                if not isinstance(question, dict) or question.get("type") != "choice":
                    raise ValueError("choice_required")
                if question.keys() - {"type", "instructions", "criteria"}:
                    raise ValueError("unknown_question_field")
                instructions = question.get("instructions")
                if instructions is not None and not isinstance(instructions, (str, dict, list)):
                    raise ValueError("invalid_instructions")
                criteria = question.get("criteria")
                if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255:
                    raise ValueError("invalid_criteria")
                for option, description in criteria.items():
                    if not isinstance(option, str) or not option.strip():
                        raise ValueError("invalid_option")
                    if description is not None and not isinstance(description, (str, dict, list)):
                        raise ValueError("invalid_description")
                options[question_id] = tuple(criteria)
            body = {"model": self.model, "state": request.state, "questions": questions}
            content = _encode(body)
            if len(content) > self._max_request_bytes:
                raise VerificationError("unsupported_capability")
            # AIDEV-NOTE: local byte budgets are not provider token guarantees. Check
            # the full shared state plus each whole question; never trim or split it.
            for question_id, question in questions.items():
                single = {**body, "questions": {question_id: question}}
                if len(_encode(single)) > self._max_question_bytes:
                    raise VerificationError("unsupported_capability")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise VerificationError("invalid_request") from None
        return content, options

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        self._configured()
        content, options = self._prepare(request)
        try:
            async with self._client.stream(
                "POST",
                self._url,
                content=content,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
                follow_redirects=False,
                auth=None,
            ) as response:
                status = response.status_code
                # Error bodies are untrusted and unnecessary for these fixed categories.
                if status in (401, 403):
                    raise VerificationError("authentication_failed")
                if status == 429:
                    raise VerificationError("rate_limited")
                if status in (408, 504):
                    raise VerificationError("upstream_timeout")
                if status == 413:
                    raise VerificationError("unsupported_capability")
                if status >= 500:
                    raise VerificationError("upstream_unavailable")
                if status != 200:
                    raise VerificationError("provider_protocol_error")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise VerificationError("response_too_large")
                    chunks.extend(chunk)
            data, duplicate_keys = _decode(chunks)
        except httpx.TimeoutException:
            raise VerificationError("upstream_timeout") from None
        except (httpx.InvalidURL, httpx.UnsupportedProtocol):
            raise VerificationError("not_configured") from None
        except (ValueError, UnicodeError, RecursionError, httpx.DecodingError):
            raise VerificationError("provider_protocol_error") from None
        except httpx.RequestError:
            raise VerificationError("upstream_unavailable") from None
        # The service owns operation/attempt diagnostics, retries and the shared deadline.
        return _parse(data, options, self.model, duplicate_keys=duplicate_keys)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
