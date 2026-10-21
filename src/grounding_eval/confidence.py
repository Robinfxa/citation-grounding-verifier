"""Descriptive routing audit and offline development sweeps, never simulated fallback."""
from __future__ import annotations

import math
from collections import Counter

from grounding_eval.scoring import ratio


def automatic_candidate(trace: dict, thresholds: dict) -> tuple[str | None, str]:
    relation = trace["relation"]
    if relation is None:
        return None, "unobserved_relation"
    if relation["gate_score"] < thresholds["label"]:
        return None, "label_uncertain"
    label = relation["choice"]
    if label == "UNSUPPORTED":
        reason = trace["unsupported_reason"]
        if reason is None:
            return None, "unobserved_reason"
        return ((label, "accepted") if reason["gate_score"] >= thresholds["reason"]
                else (None, "unsupported_reason_uncertain"))
    selection, evidence = trace["selection"], trace["evidence"]
    if selection is None:
        return None, "unobserved_selection"
    if selection["choice"] == "NO_ADEQUATE_BUNDLE":
        return None, "candidate_missing"
    if evidence is None:
        return None, "unobserved_quote_check"
    if evidence["gate_score"] < thresholds["evidence"]:
        return None, "quote_uncertain"
    if evidence["choice"] != label:
        return None, "quote_disagreement"
    return label, "accepted"


def thresholds(config: dict) -> dict:
    jev = config["experiment"]["jev"]
    return {name: jev[f"{name}_threshold"] for name in ("label", "evidence", "reason")}


def routing_summary(records: list[dict], cases: dict, *, policy: dict | None = None) -> dict:
    counts = Counter()
    reasons, origins, fallback_outcomes, sweep_routes = Counter(), Counter(), Counter(), Counter()
    for record in records:
        golds = cases[record["case_id"]].gold_claims
        counts["gold"] += len(golds)
        counts["gold_non_supported"] += sum(g.verdict != "SUPPORTED" for g in golds)
        counts["unattempted_cases"] += not record["attempted"]
        traces = record["stats"]["claim_decisions"]
        predictions = record["report"]["claims"] if record["report"] else []
        counts["predictions"] += len(predictions)
        counts["predictions_missing_trace"] += len(set(range(len(predictions))) - {t["claim_id"] for t in traces})
        counts["cases_missing_trace"] += not traces and bool(golds)
        gold_by_id = {g.id: g for g in golds}
        matches = {m["prediction_index"]: gold_by_id[m["gold_id"]] for m in record["score"]["matches"]}
        counts["final_false_support"] += sum(
            p["verdict"] == "SUPPORTED" and matches[i].verdict != "SUPPORTED"
            for i, p in enumerate(predictions) if i in matches)
        counts["traces"] += len(traces)
        for trace in traces:
            index = trace["claim_id"]
            gold = (golds[index] if record["track"] == "oracle" and index < len(golds)
                    else matches.get(index))
            origin = trace["final_origin"]
            origins[origin or "unresolved"] += 1
            if trace["fallback_reason"]:
                reasons[trace["fallback_reason"]] += 1
                fallback_outcomes["success" if record["status"] == "OK" and origin == "llm"
                                  else "unresolved_or_failed"] += 1
            if policy is not None:
                label, route = automatic_candidate(trace, policy)
                sweep_routes[route] += 1
            elif record["status"] == "OK" and origin == "jev" and index < len(predictions):
                label = predictions[index]["verdict"]
            else:
                continue
            if label is None:
                continue
            counts["automatic_decisions"] += 1
            if gold is None:
                counts["automatic_unaligned"] += 1
                continue
            counts["automatic_aligned"] += 1
            counts["automatic_label_errors"] += label != gold.verdict
            counts["automatic_false_support"] += label == "SUPPORTED" and gold.verdict != "SUPPORTED"
    return {
        "counts": dict(counts),
        "automatic_gold_coverage": ratio(counts["automatic_aligned"], counts["gold"]),
        "automatic_prediction_fraction": ratio(counts["automatic_decisions"], counts["predictions"]),
        "conditional_label_error_aligned": ratio(counts["automatic_label_errors"], counts["automatic_aligned"]),
        "strict_automatic_error_including_unaligned": ratio(
            counts["automatic_label_errors"]+counts["automatic_unaligned"], counts["automatic_decisions"]),
        "automatic_false_support_full_non_supported_gold": ratio(
            counts["automatic_false_support"], counts["gold_non_supported"]),
        "final_false_support_full_non_supported_gold": ratio(
            counts["final_false_support"], counts["gold_non_supported"]),
        "fallback_fraction_of_traces": ratio(sum(reasons.values()), counts["traces"]),
        "fallback_reasons": dict(reasons), "fallback_outcomes": dict(fallback_outcomes),
        "final_origins": dict(origins), "sweep_routes": dict(sweep_routes),
        "alignment_note": "Oracle uses direct input identity. End-to-end uses frozen verdict-blind text alignment; "
                          "unaligned and missing traces remain explicit, not semantically certified errors. "
                          "Automatic coverage counts Jev-origin decisions; deterministic empty-context origins are separate.",
    }


def threshold_sweep(config: dict, records: list[dict], cases: list, values: list[float]) -> dict:
    if (not values or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values)
            or len(set(values)) != len(values) or any(c.split != "dev" for c in cases)):
        raise ValueError("development_sweep_only")
    lookup = {case.id: case for case in cases}
    return {"kind": "offline_observed_decision_sweep", "thresholds_varied_together": True,
            "executed_policy": thresholds(config),
            "rows": [{"threshold": value, "groups": {
                f"{approach}/{track}": routing_summary(
                    [r for r in records if r["approach"] == approach and r["track"] == track], lookup,
                    policy={name: value for name in ("label", "evidence", "reason")})
                for approach in config["approaches"] if approach.startswith("jev_")
                for track in config["tracks"]}} for value in values],
            "fallback_results": None, "whole_pipeline_quality": None, "counterfactual_cost": None,
            "limitation": "Only observed decision gates are replayed. Unexecuted evidence checks and fallback "
                          "are not invented; selection on development can bias reported thresholds."}


def comparison_identity(config: dict) -> dict:
    return {key: config[key] for key in ("format_version", "dataset_sha256", "selected_cases_sha256",
            "scorer_version", "fingerprints", "settings", "experiment", "measurement_kind")}


def validate_controlled_comparison(configs: list[dict]) -> None:
    if not configs or any(comparison_identity(c) != comparison_identity(configs[0]) for c in configs):
        raise ValueError("incompatible_controlled_configuration")
