"""Sequential reproducible runs through the public verifier protocol."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import shutil
import sys
import time
from collections import Counter
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
from grounding_eval.provenance import (
    SHA256,
    LayoutEntry,
    Manifest,
    manifest_path,
    relative_file,
    strict_json,
    verify_manifest,
)
from grounding_eval.reporting import build_summary, validate_prices
from grounding_eval.scoring import SCORER_VERSION, score_case

APPROACHES = ("heuristic", "minimal", "optimized")
TRACKS = ("oracle", "end-to-end")
SCORING_FILES = (
    "grounding/contracts.py", "grounding_eval/dataset.py", "grounding_eval/scoring.py",
    "grounding_eval/uncertainty.py", "grounding_eval/reporting.py",
    "grounding_eval/provenance.py", "grounding_eval/repeated.py",
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
    stopped_after_attempt_budget_exhausted: StrictBool
    provider_attempts_charged: StrictInt = Field(ge=0)
    status: Literal["COMPLETE", "COMPLETED_WITH_ERRORS"]


class SavedUsage(StrictModel):
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    cached_input_tokens: StrictInt = Field(ge=0)
    complete: StrictBool


class SavedStats(StrictModel):
    provider: StrictStr
    requested_model: StrictStr | None
    response_models: list[StrictStr]
    provider_calls: StrictInt = Field(ge=0)
    retries: StrictInt = Field(ge=0)
    repairs: StrictInt = Field(ge=0)
    usage: SavedUsage
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class SnapshotFile(StrictModel):
    path: StrictStr
    sha256: SHA256


class DatasetSnapshot(SnapshotFile):
    manifest_path: StrictStr | None
    manifest_sha256: SHA256 | None
    selected_manifest_sha256: SHA256 | None
    dependencies: list[SnapshotFile]


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
    started_at: StrictStr | None
    attempted: StrictBool
    stats_known: StrictBool
    stats: SavedStats
    provider_attempts_reserved: StrictInt = Field(ge=0)
    provider_attempts_charged: StrictInt = Field(ge=0)
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
    budget = config["max_total_provider_attempts"]
    maximum = config["settings"]["max_provider_attempts"]
    if ((budget is not None and (type(budget) is not int or budget < 0))
            or type(maximum) is not int or maximum < 1
            or type(config["format_version"]) is not int or config["format_version"] != 2
            or config["schema_version"] != "2" or type(config["seed"]) is not int
            or type(config["bootstrap_samples"]) is not int or config["bootstrap_samples"] < 1
            or config["scorer_version"] != SCORER_VERSION):
        raise ValueError("invalid_saved_versions_or_budget")
    expected_jobs = [(a, t, c.id) for c in cases for a in config["approaches"] for t in config["tracks"]]
    random.Random(config["seed"]).shuffle(expected_jobs)
    if [(r["approach"], r["track"], r["case_id"]) for r in records] != expected_jobs:
        raise ValueError("invalid_seeded_job_order")
    planned = [{"sequence": i, "approach": r["approach"], "track": r["track"],
                "case_id": r["case_id"]} for i, r in enumerate(records)]
    if config["execution"]["jobs"] != planned:
        raise ValueError("invalid_saved_job_order")
    charged = 0
    budget_stopped = False
    previous_start = datetime.fromisoformat(config["started_at"])
    if previous_start.tzinfo is None:
        raise ValueError("invalid_saved_start")
    for sequence, record in enumerate(records):
        case = lookup[record["case_id"]]
        error = record["error_code"]
        expected_status = "OK" if error is None else (
            "NOT_RUN" if not record["attempted"] or error in {"not_configured", "implementation_unavailable"}
            else "ERROR")
        if (record["sequence"] != sequence or record["family_id"] != case.family_id
                or record["status"] != expected_status
                or record["attempted"] != (record["elapsed_ms"] is not None)
                or record["attempted"] != (record["started_at"] is not None)):
            raise ValueError("invalid_saved_record_state")
        if record["started_at"] is not None:
            started = datetime.fromisoformat(record["started_at"])
            if started.tzinfo is None or started < previous_start:
                raise ValueError("invalid_saved_start_order")
            previous_start = started
        model_job = record["approach"] != "heuristic"
        reservation = maximum if model_job and record["attempted"] else 0
        actual_charge = (record["stats"]["provider_calls"] if record["stats_known"] else reservation)
        expected_charge = actual_charge if model_job and record["attempted"] else 0
        if (record["provider_attempts_reserved"] != reservation
                or record["provider_attempts_charged"] != expected_charge
                or (model_job and record["stats_known"]
                    and record["stats"]["provider_calls"] > maximum)
                or (model_job and record["attempted"] and budget is not None
                    and (budget_stopped or charged + maximum > budget))):
            raise ValueError("invalid_saved_attempt_budget")
        if not record["attempted"] and record["stats_known"]:
            stats = record["stats"]
            if (any(stats[key] != 0 for key in ("provider_calls", "retries", "repairs", "latency_ms"))
                    or stats["response_models"] or not stats["usage"]["complete"]
                    or any(stats["usage"][key] != 0 for key in (
                        "input_tokens", "output_tokens", "cached_input_tokens"))):
                raise ValueError("invalid_saved_uncalled_usage")
        if model_job and not record["attempted"] and error == "attempt_budget_exhausted":
            if budget is None or charged + maximum <= budget:
                raise ValueError("invalid_saved_budget_stop")
            budget_stopped = True
        charged += expected_charge
        if budget is not None and charged > budget:
            raise ValueError("invalid_saved_budget_overspend")
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
        if json_text(record["score"]) != json_text(expected_score):
            raise ValueError("invalid_saved_score")
    cleanup_approaches = [item.approach for item in completion.cleanup_errors]
    if (len(set(cleanup_approaches)) != len(cleanup_approaches)
            or any(a not in config["approaches"] for a in cleanup_approaches)
            or completion.stopped_after_quota_exhausted != any(r["error_code"] == "quota_exhausted" for r in records)):
        raise ValueError("invalid_saved_completion_metadata")
    if (completion.provider_attempts_charged != charged
            or completion.stopped_after_attempt_budget_exhausted != budget_stopped):
        raise ValueError("invalid_saved_budget_completion")
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


def save_dataset_snapshot(dataset_path: Path, output: Path, all_cases: list[Case],
                          selected: list[Case], manifest: Manifest | None) -> DatasetSnapshot:
    """Retain original bindings and a separately validated selected population."""
    root = output / "dataset"
    root.mkdir()
    snapshot = root / dataset_path.name
    shutil.copyfile(dataset_path, snapshot)
    saved_manifest_path = selected_manifest_hash = saved_manifest_hash = None
    dependencies = []
    if manifest is not None:
        original_manifest_path = manifest_path(dataset_path)
        copied_manifest = root / original_manifest_path.name
        shutil.copyfile(original_manifest_path, copied_manifest)
        saved_manifest_path = str(copied_manifest.relative_to(output))
        saved_manifest_hash = file_hash(copied_manifest)
        names = sorted({name for source in manifest.sources
                        for name in (source.raw_path, source.license_path)})
        for name in names:
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative_file(dataset_path.parent, name), destination)
            dependencies.append(SnapshotFile(path=str(destination.relative_to(output)),
                                             sha256=file_hash(destination)))
        selected_ids = {case.id for case in selected}
        selected_sources = {source_id for case in selected for source_id in case.provenance.source_ids}
        data = manifest.model_dump()
        data.update({
            "dataset_file": "cases.jsonl", "dataset_sha256": file_hash(output / "cases.jsonl"),
            "layout": [LayoutEntry(split=split, category=category, cases=count).model_dump()
                       for (split, category), count in sorted(
                           Counter((c.split, c.category) for c in selected).items())],
            "sources": [{**source.model_dump(), "raw_path": "dataset/" + source.raw_path,
                         "license_path": "dataset/" + source.license_path}
                        for source in manifest.sources if source.id in selected_sources],
            "passage_maps": [mapping.model_dump() for mapping in manifest.passage_maps
                             if mapping.case_id in selected_ids],
        })
        selected_manifest = manifest_path(output / "cases.jsonl")
        write_json(selected_manifest, data)
        selected_manifest_hash = file_hash(selected_manifest)
        verify_manifest(output / "cases.jsonl", selected)
    # AIDEV-NOTE: validate the copied bytes, not just source paths read before setup.
    # This also rejects changes between initial validation and snapshot persistence.
    if ([case.model_dump() for case in load_dataset(snapshot)]
            != [case.model_dump() for case in all_cases]):
        raise DatasetError("dataset_changed_before_run")
    return DatasetSnapshot(path=str(snapshot.relative_to(output)), sha256=file_hash(snapshot),
                           manifest_path=saved_manifest_path, manifest_sha256=saved_manifest_hash,
                           selected_manifest_sha256=selected_manifest_hash, dependencies=dependencies)


def validate_dataset_snapshot(output: Path, config: dict, selected: list[Case]) -> None:
    snapshot = DatasetSnapshot.model_validate(config["dataset_snapshot"])
    path = relative_file(output, snapshot.path)
    if file_hash(path) != snapshot.sha256 or snapshot.sha256 != config["dataset_sha256"]:
        raise ValueError("invalid_dataset_snapshot")
    for dependency in snapshot.dependencies:
        if file_hash(relative_file(output, dependency.path)) != dependency.sha256:
            raise ValueError("invalid_dataset_dependency")
    source_cases = load_dataset(path)
    lookup = {case.id: case for case in source_cases}
    if ([lookup[case.id].model_dump() for case in selected]
            != [case.model_dump() for case in selected]):
        raise ValueError("selected_cases_differ_from_source")
    split = config["split"]
    if split not in {"dev", "test", "all", "diagnostic"}:
        raise ValueError("invalid_saved_split")
    available = [case.id for case in source_cases
                 if case.split == split or (split == "all" and case.split in {"dev", "test"})]
    selection = config["selection"]
    if (set(selection) != {"kind", "requested_case_ids"}
            or not set(config["case_ids"]) <= set(available)
            or (selection["kind"] == "case_ids"
                and selection["requested_case_ids"] != config["case_ids"])
            or (selection["kind"] == "split" and (
                selection["requested_case_ids"] is not None or config["case_ids"] != available))
            or selection["kind"] not in {"case_ids", "split"}):
        raise ValueError("invalid_saved_selection")
    if snapshot.manifest_path is not None:
        if (file_hash(relative_file(output, snapshot.manifest_path)) != snapshot.manifest_sha256
                or relative_file(output, snapshot.manifest_path) != manifest_path(path).resolve()
                or file_hash(manifest_path(output / "cases.jsonl")) != snapshot.selected_manifest_sha256):
            raise ValueError("invalid_manifest_snapshot")
        manifest = verify_manifest(path, source_cases)
        if (config["dataset_version"] != manifest.dataset_version
                or config["annotation_version"] != manifest.annotation_version):
            raise ValueError("invalid_dataset_version")
    elif (any(case.provenance.kind == "real_source" for case in selected)
          or snapshot.manifest_sha256 is not None or snapshot.selected_manifest_sha256 is not None
          or snapshot.dependencies or config["dataset_version"] != "legacy-v1"):
        raise ValueError("missing_manifest_snapshot")


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
                        prices: dict | None = None, case_ids: list[str] | None = None,
                        max_total_provider_attempts: int | None = None) -> dict:
    """The optional verifier mapping is an explicitly labeled offline-test seam only."""
    settings = settings or Settings.from_env()
    if (not approaches or len(set(approaches)) != len(approaches)
            or any(a not in APPROACHES for a in approaches)
            or split not in {"dev", "test", "all", "diagnostic"} or track not in {*TRACKS, "both"}
            or type(seed) is not int or type(bootstrap_samples) is not int or bootstrap_samples < 1
            or (max_total_provider_attempts is not None and (
                type(max_total_provider_attempts) is not int or max_total_provider_attempts < 0))
            or (verifiers is None and any(a != "heuristic" for a in approaches)
                and max_total_provider_attempts is None)
            or (case_ids is not None and (not isinstance(case_ids, list) or not case_ids
                or any(type(value) is not str or not value.strip() for value in case_ids)
                or len(set(case_ids)) != len(case_ids)))):
        raise EvaluationError("invalid_arguments")
    try:
        prices = validate_prices(prices)
    except ValueError:
        raise EvaluationError("invalid_arguments") from None
    all_cases = load_dataset(dataset_path)
    manifest = (verify_manifest(dataset_path, all_cases)
                if any(c.provenance.kind == "real_source" for c in all_cases) else None)
    cases = [c for c in all_cases if c.split == split or (split == "all" and c.split in {"dev", "test"})]
    if case_ids is not None:
        lookup = {case.id: case for case in cases}
        if any(case_id not in lookup for case_id in case_ids):
            raise DatasetError("invalid_case_selection")
        cases = [lookup[case_id] for case_id in case_ids]
    if not cases:
        raise DatasetError("empty_selection")
    tracks = list(TRACKS) if track == "both" else [track]
    jobs = [(a, t, c) for c in cases for a in approaches for t in tracks]
    random.Random(seed).shuffle(jobs)
    with operation(enabled=settings.diagnostics, new=True) as op:
        started_at = datetime.now(UTC).isoformat()
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
        quota_stopped = budget_stopped = False
        attempts_charged = 0
        try:
            cases_text = "".join(json.dumps(c.model_dump(), ensure_ascii=False, sort_keys=True) + "\n" for c in cases)
            (output / "cases.jsonl").write_text(cases_text, encoding="utf-8")
            snapshot = save_dataset_snapshot(dataset_path, output, all_cases, cases, manifest)
            config = {
                "format_version": 2, "schema_version": "2", "scorer_version": SCORER_VERSION,
                "dataset_version": manifest.dataset_version if manifest else "legacy-v1",
                "annotation_version": manifest.annotation_version if manifest else "legacy-v1",
                "created_at": datetime.now(UTC).isoformat(), "started_at": started_at,
                "request_id": op.request_id,
                "runtime": {"python": sys.version, "packages": {
                    name: version(name) for name in ("pydantic", "httpx", "fastapi")}},
                "approaches": approaches, "tracks": tracks, "split": split, "seed": seed,
                "bootstrap_samples": bootstrap_samples, "case_ids": [c.id for c in cases],
                "selection": {"kind": "case_ids" if case_ids is not None else "split",
                              "requested_case_ids": case_ids},
                "max_total_provider_attempts": max_total_provider_attempts,
                "dataset_sha256": snapshot.sha256, "selected_cases_sha256": file_hash(output / "cases.jsonl"),
                "dataset_snapshot": snapshot.model_dump(),
                "fingerprints": fingerprints(), "settings": public_settings(settings), "prices": prices,
                "measurement_kind": "offline_protocol_fixture" if verifiers is not None else "actual_verifier",
                "execution": {"concurrency": 1, "order": "seeded_job_shuffle", "cache": "none",
                              "lifecycle": "one_verifier_per_approach; no_warmup",
                              "budget_policy": "reserve_operation_max_charge_known_calls_else_reservation",
                              "jobs": [{"sequence": i, "approach": a, "track": t, "case_id": c.id}
                                       for i, (a, t, c) in enumerate(jobs)]},
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
                        elif approach != "heuristic" and (budget_stopped or (
                            max_total_provider_attempts is not None
                            and attempts_charged + settings.max_provider_attempts > max_total_provider_attempts
                        )):
                            budget_stopped = True
                            error_code = "attempt_budget_exhausted"
                            stats = RunStats(provider=settings.provider, requested_model=settings.model)
                            stats_known = True
                        attempted = error_code is None
                        job_started_at = datetime.now(UTC).isoformat() if attempted else None
                        reserved = settings.max_provider_attempts if attempted and approach != "heuristic" else 0
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
                        try:
                            stats_data = asdict(stats)
                            stats_data["response_models"] = list(stats_data["response_models"])
                            validated_stats = SavedStats.model_validate(stats_data)
                            if approach != "heuristic" and validated_stats.provider_calls > settings.max_provider_attempts:
                                raise ValueError("invalid_provider_attempt_count")
                        except (TypeError, ValueError, KeyError):
                            stats, stats_known = unknown_stats(approach, settings), False
                            stats_data = asdict(stats)
                            stats_data["response_models"] = list(stats_data["response_models"])
                            error_code, report, rejected = "provider_protocol_error", None, None
                        charged = (stats.provider_calls if stats_known else reserved) if reserved else 0
                        attempts_charged += charged
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
                            "started_at": job_started_at, "provider_attempts_reserved": reserved,
                            "provider_attempts_charged": charged,
                            "stats": stats_data, "stats_known": stats_known,
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
                "stopped_after_attempt_budget_exhausted": budget_stopped,
                "provider_attempts_charged": attempts_charged,
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
        config = strict_json((output / "config.json").read_text())
        completion = SavedCompletion.model_validate(strict_json((output / "completion.json").read_text()))
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
        validate_dataset_snapshot(output, config, cases)
        records = [SavedRecord.model_validate(strict_json(line)).model_dump()
                   for line in (output / "records.jsonl").read_text().splitlines()]
        validate_saved_state(cases, config, records, completion)
        summary = build_summary(config, records, cases)
        summary["completion"] = completion.model_dump()
        write_json(output / "summary.json", summary)
        return summary
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        raise EvaluationError("run_artifact_invalid") from None
