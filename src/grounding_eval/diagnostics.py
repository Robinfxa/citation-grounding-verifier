"""Evaluation phases using the service's correlation context and JSON field vocabulary."""
from __future__ import annotations

import json
import os
import time

from grounding.contracts import ERRORS
from grounding.diagnostics import Operation

SAFE_ERRORS = set(ERRORS) | {
    "dataset_invalid", "output_exists", "persistence_failed", "run_artifact_invalid",
    "oracle_identity_violation", "invalid_arguments", "implementation_unavailable",
    "cleanup_failed", "source_changed", "request_failures",
    "audit_artifact_invalid",
}


def emit(op: Operation, stage: str, event: str, outcome: str, *,
         error_code: str | None = None, completed: int | None = None,
         requested: int | None = None, approach: str | None = None,
         cleanup_failures: int | None = None, failed_requests: int | None = None,
         source_changed: bool | None = None) -> None:
    if not op.enabled or stage not in {"eval_run", "eval_case", "eval_validate", "eval_report", "eval_save", "eval_cleanup", "semantic_audit"}:
        return
    if event not in {"start", "end"} or outcome not in {"started", "success", "failure"}:
        return
    record = {"request_id": op.request_id, "stage": stage, "event": event,
              "outcome": outcome, "elapsed_ms": round((time.monotonic() - op.started) * 1000, 3)}
    if error_code in SAFE_ERRORS:
        record["error_code"] = error_code
    if approach in {"heuristic", "minimal", "optimized", "jev_minimal", "jev_optimized"}:
        record["approach"] = approach
    if type(source_changed) is bool:
        record["source_changed"] = source_changed
    for key, value in (("completed", completed), ("requested", requested),
                       ("cleanup_failures", cleanup_failures), ("failed_requests", failed_requests)):
        if type(value) is int and 0 <= value <= 1_000_000:
            record[key] = value
    try:
        # Same unbuffered best-effort policy as service diagnostics; no exit-time flush.
        os.write(2, (json.dumps(record, separators=(",", ":")) + "\n").encode())
    except Exception:
        pass
