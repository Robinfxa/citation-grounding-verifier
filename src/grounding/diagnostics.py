"""Small, local, payload-free JSON diagnostics shared by HTTP and library consumers."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from grounding.contracts import ERRORS


@dataclass(frozen=True)
class Operation:
    request_id: str
    started: float
    enabled: bool


_current: ContextVar[Operation | None] = ContextVar("grounding_operation", default=None)
_STAGES = {
    "http", "verification", "extraction", "judgment", "minimal", "heuristic",
    "jev_judgment", "jev_evidence", "jev_decision", "fallback",
}
_EVENTS = {"start", "end", "provider_attempt", "validation", "repair", "retry", "routing"}
_OUTCOMES = {"started", "success", "failure", "cancelled"}
_PROTOCOL_REASONS = {
    "duplicate_json_key", "returned_model", "answer_coverage", "answer_type",
    "choice_not_declared", "confidence_invalid", "probability_keys",
    "probability_invalid", "probability_sum", "choice_not_argmax", "confidence_formula",
}
_ROUTING_REASONS = {
    "label_uncertain", "unsupported_reason_uncertain", "candidate_missing",
    "quote_uncertain", "quote_disagreement",
}


@contextmanager
def operation(*, enabled: bool, new: bool = False) -> Iterator[Operation]:
    current = _current.get()
    if current is not None and not new:
        yield current
        return
    current = Operation(uuid.uuid4().hex, time.monotonic(), enabled)
    token = _current.set(current)
    try:
        yield current
    finally:
        _current.reset(token)


def request_id() -> str:
    current = _current.get()
    return current.request_id if current else uuid.uuid4().hex


def emit(
    stage: str,
    event: str,
    outcome: str,
    *,
    error_code: str | None = None,
    provider_calls: int | None = None,
    retries: int | None = None,
    repairs: int | None = None,
    claims: int | None = None,
    routing_reason: str | None = None,
    protocol_reason: str | None = None,
) -> None:
    current = _current.get()
    if current is None or not current.enabled:
        return
    if stage not in _STAGES or event not in _EVENTS or outcome not in _OUTCOMES:
        return
    record = {
        "request_id": current.request_id,
        "stage": stage,
        "event": event,
        "outcome": outcome,
        "elapsed_ms": round((time.monotonic() - current.started) * 1_000, 3),
    }
    if error_code in ERRORS:
        record["error_code"] = error_code
    if routing_reason in _ROUTING_REASONS:
        record["routing_reason"] = routing_reason
    if isinstance(protocol_reason, str) and protocol_reason in _PROTOCOL_REASONS:
        record["protocol_reason"] = protocol_reason
    for key, value in (
        ("provider_calls", provider_calls), ("retries", retries),
        ("repairs", repairs), ("claims", claims),
    ):
        if type(value) is int and 0 <= value <= 1_000_000:
            record[key] = value
    try:
        # AIDEV-NOTE: unbuffered writes avoid a later interpreter-flush failure.
        # A permanently blocked synchronous sink is intentionally not time-bounded.
        os.write(2, (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8"))
    except Exception:
        # Diagnostics are best effort; never replace the consumer's real outcome.
        pass
