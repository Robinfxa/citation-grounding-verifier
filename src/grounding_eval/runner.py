"""Sequential reproducible runs through the public verifier protocol."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, ValidationError

from grounding.config import Settings
from grounding.contracts import (
    ERRORS,
    InvalidReport,
    RunStats,
    StrictModel,
    TokenUsage,
    VerificationError,
    VerificationReport,
    Verifier,
    VerifyRequest,
    validate_report,
)
from grounding.diagnostics import operation
from grounding_eval.dataset import Case, DatasetError, file_hash, load_dataset
from grounding_eval.diagnostics import emit
from grounding_eval.reporting import build_summary, validate_prices
from grounding_eval.scoring import score_case

APPROACHES = ("heuristic", "minimal", "optimized")
TRACKS = ("oracle", "end-to-end")
SCORING_FILES = (
    "grounding/contracts.py", "grounding_eval/dataset.py", "grounding_eval/scoring.py",
    "grounding_eval/uncertainty.py", "grounding_eval/reporting.py",
)


class EvaluationError(ValueError):
    """Safe evaluator error codes, never raw exceptions or user payloads."""


class CleanupFailure(StrictModel):
    approach: Literal["heuristic", "minimal", "optimized"]
    error_code: Literal["internal_error"]


class SavedCompletion(StrictModel):
    records_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    record_count: StrictInt = Field(ge=1)
    cleanup_errors: list[CleanupFailure]
    source_changed_during_run: StrictBool
    stopped_after_quota_exhausted: StrictBool
    status: Literal["COMPLETE", "COMPLETED_WITH_ERRORS"]


class SavedRecord(StrictModel):
    sequence: StrictInt = Field(ge=0)
    request_id: StrictStr = Field(min_length=1)
    case_id: StrictStr
    family_id: StrictStr
    approach: Literal["heuristic", "minimal", "optimized"]
    track: Literal["oracle", "end-to-end"]
    status: Literal["OK", "ERROR", "NOT_RUN"]
    error_code: StrictStr | None
    report: VerificationReport | None
    rejected_report: VerificationReport | None
    elapsed_ms: float | None = Field(ge=0, allow_inf_nan=False)
    attempted: StrictBool
    stats_known: StrictBool
    stats: dict[str, Any]
    score: dict[str, Any]


def completion_status(records: list[dict], *, cleanup_errors: list,
                      source_changed: bool) -> str:
    return ("COMPLETE" if all(r["status"] == "OK" for r in records)
            and not cleanup_errors and not source_changed else "COMPLETED_WITH_ERRORS")


def validate_saved_state(cases: list[Case], config: dict, records: list[dict],
                         completion: SavedCompletion) -> None:
    """Check persisted relationships, not just hashes or editable success flags."""
    lookup = {case.id: case for case in cases}
    if (not config["approaches"] or len(set(config["approaches"])) != len(config["approaches"])
            or any(a not in APPROACHES for a in config["approaches"])
            or not config["tracks"] or len(set(config["tracks"])) != len(config["tracks"])
            or any(t not in TRACKS for t in config["tracks"])):
        raise ValueError("invalid_saved_population")
    expected = {(a, t, case.id) for a in config["approaches"] for t in config["tracks"] for case in cases}
    actual = {(r["approach"], r["track"], r["case_id"]) for r in records}
    if (actual != expected or len(records) != len(expected)
            or len(records) != completion.record_count
            or [case.id for case in cases] != config["case_ids"]
            or len({r["request_id"] for r in records}) != len(records)):
        raise ValueError("invalid_saved_population")
    for sequence, record in enumerate(records):
        case = lookup[record["case_id"]]
        error = record["error_code"]
        expected_status = "OK" if error is None else (
            "NOT_RUN" if not record["attempted"] or error in {"not_configured", "implementation_unavailable"}
            else "ERROR")
        if (record["sequence"] != sequence or record["family_id"] != case.family_id
                or record["status"] != expected_status
                or record["attempted"] != (record["elapsed_ms"] is not None)):
            raise ValueError("invalid_saved_record_state")
        if error is None:
            if not record["attempted"] or record["report"] is None or record["rejected_report"] is not None:
                raise ValueError("invalid_saved_success")
            report = VerificationReport.model_validate(record["report"])
            validate_report(report, case.context_passages)
            if record["track"] == "oracle" and (
                [p.claim_text for p in report.claims] != [g.claim_text for g in case.gold_claims]
            ):
                raise ValueError("invalid_saved_oracle_identity")
        elif (error not in {*ERRORS, "oracle_identity_violation", "implementation_unavailable"}
              or record["report"] is not None):
            raise ValueError("invalid_saved_failure")
        if (record["rejected_report"] is not None) != (error == "oracle_identity_violation"):
            raise ValueError("invalid_saved_rejection")
        expected_score = score_case(case, record["report"]["claims"] if record["report"] else [],
                                    track=record["track"], error=error)
        if record["score"] != expected_score:
            raise ValueError("invalid_saved_score")
    cleanup_approaches = [item.approach for item in completion.cleanup_errors]
    if (len(set(cleanup_approaches)) != len(cleanup_approaches)
            or any(a not in config["approaches"] for a in cleanup_approaches)
            or completion.stopped_after_quota_exhausted != any(r["error_code"] == "quota_exhausted" for r in records)):
        raise ValueError("invalid_saved_completion_metadata")
    # AIDEV-NOTE: completion.json is mutable local metadata, not the source of success.
    # Derive the terminal status from validated records plus typed cleanup/drift facts.
    expected_status = completion_status(records, cleanup_errors=completion.cleanup_errors,
                                        source_changed=completion.source_changed_during_run)
    if completion.status != expected_status:
        raise ValueError("inconsistent_saved_completion_status")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json_text(value), encoding="utf-8")
    temporary.replace(path)


def fingerprints() -> dict:
    src = Path(__file__).resolve().parents[1]
    files = {str(p.relative_to(src)): file_hash(p)
             for package in ("grounding", "grounding_eval")
             for p in sorted((src / package).rglob("*.py"))}
    return {"code_sha256": hashlib.sha256(json_text(files).encode()).hexdigest(),
            "files": files,
            "prompt_files": {name: value for name, value in files.items() if "prompt" in name}}


def public_settings(settings: Settings) -> dict:
    fields = ("provider", "model", "provider_timeout", "operation_timeout", "max_provider_attempts",
              "transport_retries", "retry_delay", "max_output_tokens", "diagnostics")
    result = {name: getattr(settings, name) for name in fields}
    # AIDEV-NOTE: describe the configured adapter's application, not a measured model cap.
    # Codex omits this option. Replay leaves historical scalar settings uninterpreted.
    applied = settings.provider == "openai"
    result["max_output_tokens"] = {
        "requested": settings.max_output_tokens,
        "effective": settings.max_output_tokens if applied else None,
        "application": "applied" if applied else "not_applied",
    }
    result["endpoint_sha256"] = hashlib.sha256(settings.base_url.encode()).hexdigest()
    return result


def unknown_stats(approach: str, settings: Settings) -> RunStats:
    return RunStats(provider="heuristic" if approach == "heuristic" else settings.provider,
                    requested_model=None if approach == "heuristic" else settings.model,
                    usage=TokenUsage(complete=False))


async def run_benchmark(*, dataset_path: Path, output: Path, approaches: list[str],
                        split: str = "test", track: str = "both", seed: int = 20261015,
                        bootstrap_samples: int = 10_000, settings: Settings | None = None,
                        verifiers: dict[str, Verifier] | None = None,
                        prices: dict | None = None) -> dict:
    """The optional verifier mapping is an explicitly labeled offline-test seam only."""
    settings = settings or Settings.from_env()
    if (not approaches or len(set(approaches)) != len(approaches)
            or any(a not in APPROACHES for a in approaches)
            or split not in {"dev", "test", "all", "diagnostic"} or track not in {*TRACKS, "both"}
            or type(seed) is not int or type(bootstrap_samples) is not int or bootstrap_samples < 1):
        raise EvaluationError("invalid_arguments")
    try:
        prices = validate_prices(prices)
    except ValueError:
        raise EvaluationError("invalid_arguments") from None
    cases = load_dataset(dataset_path)
    cases = [c for c in cases if c.split == split or (split == "all" and c.split in {"dev", "test"})]
    if not cases:
        raise DatasetError("empty_selection")
    tracks = list(TRACKS) if track == "both" else [track]
    jobs = [(a, t, c) for c in cases for a in approaches for t in tracks]
    random.Random(seed).shuffle(jobs)
    with operation(enabled=settings.diagnostics, new=True) as op:
        emit(op, "eval_run", "start", "started", requested=len(jobs))
        try:
            output.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            emit(op, "eval_run", "end", "failure", error_code="output_exists")
            raise EvaluationError("output_exists") from None
        except OSError:
            emit(op, "eval_run", "end", "failure", error_code="persistence_failed")
            raise EvaluationError("persistence_failed") from None
        records, clients, initialization_errors, cleanup_errors = [], {}, {}, []
        quota_stopped = False
        try:
            cases_text = "".join(json.dumps(c.model_dump(), ensure_ascii=False, sort_keys=True) + "\n" for c in cases)
            (output / "cases.jsonl").write_text(cases_text, encoding="utf-8")
            config = {
                "format_version": 1, "created_at": datetime.now(UTC).isoformat(),
                "request_id": op.request_id,
                "runtime": {"python": sys.version, "packages": {
                    name: version(name) for name in ("pydantic", "httpx", "fastapi")}},
                "approaches": approaches, "tracks": tracks, "split": split, "seed": seed,
                "bootstrap_samples": bootstrap_samples, "case_ids": [c.id for c in cases],
                "dataset_sha256": file_hash(dataset_path), "selected_cases_sha256": file_hash(output / "cases.jsonl"),
                "fingerprints": fingerprints(), "settings": public_settings(settings), "prices": prices,
                "measurement_kind": "offline_protocol_fixture" if verifiers is not None else "actual_verifier",
                "execution": {"concurrency": 1, "order": "seeded_job_shuffle", "cache": "none",
                              "lifecycle": "one_verifier_per_approach; no_warmup"},
            }
            write_json(output / "config.json", config)
            for approach in approaches:
                try:
                    if verifiers is not None:
                        clients[approach] = verifiers[approach]
                    else:
                        from grounding.verifiers import build_verifier
                        clients[approach] = build_verifier(approach, settings=settings)
                except VerificationError as exc:
                    initialization_errors[approach] = exc.code if exc.code in ERRORS else "internal_error"
                except ImportError:
                    initialization_errors[approach] = "implementation_unavailable"
                except Exception:
                    initialization_errors[approach] = "internal_error"
            with (output / "records.jsonl").open("x", encoding="utf-8") as stream:
                for sequence, (approach, selected_track, case) in enumerate(jobs):
                    with operation(enabled=settings.diagnostics, new=True) as case_op:
                        emit(case_op, "eval_case", "start", "started")
                        started = time.perf_counter()
                        report, rejected, error_code = None, None, initialization_errors.get(approach)
                        stats, stats_known = unknown_stats(approach, settings), False
                        if quota_stopped and approach != "heuristic":
                            error_code = "quota_exhausted"
                            stats = RunStats(provider=settings.provider, requested_model=settings.model)
                            stats_known = True
                        attempted = error_code is None
                        if error_code is None:
                            try:
                                # The service owns its attempt budget; this outer bound also protects the protocol seam.
                                async with asyncio.timeout(settings.operation_timeout):
                                    if selected_track == "oracle":
                                        run = await clients[approach].verify_claims(
                                            list(case.context_passages), [g.claim_text for g in case.gold_claims])
                                    else:
                                        run = await clients[approach].verify(VerifyRequest(
                                            context_passages=list(case.context_passages), generated_answer=case.generated_answer))
                                stats, stats_known = run.stats, True
                                validated = VerificationReport.model_validate(run.report.model_dump())
                                validate_report(validated, case.context_passages)
                                report = validated.model_dump()
                                if selected_track == "oracle" and (
                                    [p["claim_text"] for p in report["claims"]] != [g.claim_text for g in case.gold_claims]
                                ):
                                    rejected, report, error_code = report, None, "oracle_identity_violation"
                            except VerificationError as exc:
                                error_code = exc.code if exc.code in ERRORS else "internal_error"
                                if exc.stats is not None:
                                    stats, stats_known = exc.stats, True
                            except TimeoutError:
                                error_code = "deadline_exceeded"
                            except (ValidationError, InvalidReport):
                                error_code = "invalid_model_output"
                            except Exception:
                                error_code = "internal_error"
                        elapsed_ms = (time.perf_counter() - started) * 1000 if attempted else None
                        if error_code == "quota_exhausted":
                            # AIDEV-NOTE: stop this benchmark's shared LLM population only.
                            # Uncalled jobs retain gold denominators but have no fabricated latency/usage.
                            quota_stopped = True
                        status = "OK" if error_code is None else (
                            "NOT_RUN" if not attempted or error_code in {"not_configured", "implementation_unavailable"} else "ERROR")
                        record = {
                            "sequence": sequence, "request_id": case_op.request_id,
                            "case_id": case.id, "family_id": case.family_id,
                            "approach": approach, "track": selected_track, "status": status,
                            "error_code": error_code, "report": report, "rejected_report": rejected,
                            "elapsed_ms": elapsed_ms, "attempted": attempted,
                            "stats": asdict(stats), "stats_known": stats_known,
                            "score": score_case(case, report["claims"] if report else [],
                                                track=selected_track, error=error_code),
                        }
                        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
                        stream.flush()
                        records.append(record)
                        emit(case_op, "eval_case", "end", "success" if status == "OK" else "failure", error_code=error_code)
            for approach, client in clients.items():
                emit(op, "eval_cleanup", "start", "started", approach=approach)
                try:
                    await asyncio.wait_for(client.aclose(), timeout=settings.operation_timeout)
                except Exception:
                    cleanup_errors.append({"approach": approach, "error_code": "internal_error"})
                    emit(op, "eval_cleanup", "end", "failure", error_code="internal_error", approach=approach)
                else:
                    emit(op, "eval_cleanup", "end", "success", approach=approach)
            clients.clear()
            summary = build_summary(config, records, cases)
            source_changed = fingerprints() != config["fingerprints"]
            completion = {
                "records_sha256": file_hash(output / "records.jsonl"), "record_count": len(records),
                "config_sha256": file_hash(output / "config.json"), "cleanup_errors": cleanup_errors,
                "source_changed_during_run": source_changed,
                "stopped_after_quota_exhausted": quota_stopped,
                "status": completion_status(records, cleanup_errors=cleanup_errors, source_changed=source_changed),
            }
            summary["completion"] = completion
            write_json(output / "summary.json", summary)
            write_json(output / "completion.json", completion)
            terminal_error = ("cleanup_failed" if cleanup_errors else "source_changed" if source_changed
                              else "request_failures" if any(r["status"] != "OK" for r in records) else None)
            emit(op, "eval_run", "end", "success" if completion["status"] == "COMPLETE" else "failure",
                 error_code=terminal_error, completed=len(records), requested=len(jobs),
                 cleanup_failures=len(cleanup_errors), failed_requests=sum(r["status"] != "OK" for r in records),
                 source_changed=source_changed)
            return summary
        except (OSError, UnicodeError):
            emit(op, "eval_save", "end", "failure", error_code="persistence_failed", completed=len(records))
            emit(op, "eval_run", "end", "failure", error_code="persistence_failed", completed=len(records))
            raise EvaluationError("persistence_failed") from None
        finally:
            for approach, client in clients.items():
                emit(op, "eval_cleanup", "start", "started", approach=approach)
                try:
                    await asyncio.wait_for(client.aclose(), timeout=settings.operation_timeout)
                except Exception:
                    emit(op, "eval_cleanup", "end", "failure", error_code="internal_error", approach=approach)
                else:
                    emit(op, "eval_cleanup", "end", "success", approach=approach)


def regenerate_report(output: Path) -> dict:
    """Recompute from complete, internally consistent saved records; never call a verifier."""
    try:
        config = json.loads((output / "config.json").read_text())
        completion = SavedCompletion.model_validate_json((output / "completion.json").read_text())
        if (file_hash(output / "config.json") != completion.config_sha256
                or file_hash(output / "records.jsonl") != completion.records_sha256
                or file_hash(output / "cases.jsonl") != config["selected_cases_sha256"]):
            raise ValueError
        current = fingerprints()["files"]
        # AIDEV-NOTE: preserve original runner fingerprints, but bind replay to the
        # computation modules. Reader/diagnostic repairs need not repeat inference.
        if any(current.get(name) != config["fingerprints"]["files"][name] for name in SCORING_FILES):
            raise ValueError("scorer_version_changed")
        cases = load_dataset(output / "cases.jsonl")
        records = [SavedRecord.model_validate_json(line).model_dump()
                   for line in (output / "records.jsonl").read_text().splitlines()]
        validate_saved_state(cases, config, records, completion)
        summary = build_summary(config, records, cases)
        summary["completion"] = completion.model_dump()
        write_json(output / "summary.json", summary)
        return summary
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        raise EvaluationError("run_artifact_invalid") from None
