"""Deterministic summaries from saved request records, including resource uncertainty."""
from __future__ import annotations

import math
from collections import Counter
from statistics import median

from grounding_eval.dataset import Case
from grounding_eval.scoring import aggregate, ratio, score_case
from grounding_eval.uncertainty import bootstrap, percentile

LIMITATIONS = [
    "Strict whitespace-only text/alias matching can undercount valid paraphrases; unmatched predictions are retained.",
    "Literal quotation validity and gold-span coverage do not establish semantic entailment.",
    "A gold span must be contained in one returned quote; alternate sufficient quotations may be undercounted.",
    "Bootstrap intervals describe case/family sample sensitivity, not annotation uncertainty or model randomness.",
    "Offline protocol fixtures are not live model measurements. Subscription tokens have no inferred dollar price.",
]


def limitations(cases: list[Case]) -> list[str]:
    real = any(case.provenance.kind == "real_source" for case in cases)
    legacy = any(case.provenance.kind == "original_fixture" for case in cases)
    population = []
    if real:
        population.append("Real public-source English benchmark; answer origins are reported separately. "
                          "Document familiarity and related sources can bias results. AI annotation can share "
                          "model biases; independent and human review states are recorded separately.")
    if legacy:
        population.append("Includes agent-authored fictional fixtures; these are not production accuracy estimates.")
    return population + LIMITATIONS


def slices(cases: dict[str, Case], scores: list[dict]) -> dict:
    """Descriptive slices share cases; do not spend headline bootstrap draws per tag."""
    members: dict[str, dict[str, list[dict]]] = {"category": {}, "tag": {}, "origin": {}}
    for score in scores:
        case = cases[score["case_id"]]
        origin = case.provenance.origin if case.provenance.kind == "real_source" else "original_fixture"
        for dimension, values in (("category", [case.category]), ("tag", sorted(set(case.tags))),
                                  ("origin", [origin])):
            for value in values:
                members[dimension].setdefault(value, []).append(score)
    return {
        dimension: {
            name: {"requested_cases": len(subset),
                   "independent_families": len({score["family_id"] for score in subset}),
                   "failure_inclusive_quality": aggregate(subset),
                   "uncertainty": None,
                   "uncertainty_note": "Descriptive overlapping slice; no per-slice bootstrap."}
            for name, subset in sorted(values.items())
        } for dimension, values in members.items()
    }


def validate_prices(prices: dict | None) -> dict | None:
    if prices is None:
        return None
    required = {"provider", "model", "currency", "input_per_million", "cached_input_per_million",
                "output_per_million", "source", "as_of"}
    if not isinstance(prices, dict) or set(prices) != required:
        raise ValueError("invalid_price_snapshot")
    for key in ("input_per_million", "cached_input_per_million", "output_per_million"):
        value = prices[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid_price_snapshot")
    for key in ("provider", "model", "currency", "source", "as_of"):
        if not isinstance(prices[key], str) or not prices[key].strip():
            raise ValueError("invalid_price_snapshot")
    if prices["currency"] != "USD":
        raise ValueError("invalid_price_snapshot")
    return prices


def dollar_cost(records: list[dict], prices: dict | None) -> dict:
    providers = {r["stats"]["provider"] for r in records}
    if "codex" in providers:
        return {"value": None, "currency": "USD", "reason": "subscription_usage_not_dollar_cost"}
    if providers == {"heuristic"}:
        return {"value": 0.0, "currency": "USD", "reason": "no_provider_calls_excludes_compute"}
    if not prices:
        return {"value": None, "currency": "USD", "reason": "no_explicit_price_snapshot"}
    if providers != {prices["provider"]} or providers != {"openai"}:
        return {"value": None, "currency": "USD", "reason": "provider_price_mismatch"}
    total = 0.0
    for record in records:
        stats, usage = record["stats"], record["stats"]["usage"]
        if not usage["complete"]:
            return {"value": None, "currency": "USD", "reason": "incomplete_usage"}
        if stats["requested_model"] != prices["model"] or any(
            model != prices["model"] for model in stats["response_models"]
        ):
            return {"value": None, "currency": "USD", "reason": "model_price_mismatch"}
        cached, inputs = usage["cached_input_tokens"], usage["input_tokens"]
        if cached > inputs:
            return {"value": None, "currency": "USD", "reason": "invalid_usage"}
        total += ((inputs - cached) * prices["input_per_million"]
                  + cached * prices["cached_input_per_million"]
                  + usage["output_tokens"] * prices["output_per_million"]) / 1_000_000
    return {"value": total, "currency": "USD", "reason": "measured_usage_explicit_prices"}


def resources(records: list[dict], prices: dict | None) -> dict:
    elapsed = [r["elapsed_ms"] for r in records if r["elapsed_ms"] is not None]
    usage = [r["stats"]["usage"] for r in records]
    complete = all(u["complete"] for u in usage)
    totals = {key: sum(u[key] for u in usage)
              for key in ("input_tokens", "output_tokens", "cached_input_tokens")}
    return {
        "elapsed_ms": {"count": len(elapsed), "sum": sum(elapsed),
                       "median": median(elapsed) if elapsed else None,
                       "p95": percentile(elapsed, .95), "includes_failures": True},
        "attempted_requests": sum(r["attempted"] for r in records),
        "not_attempted_requests": sum(not r["attempted"] for r in records),
        "known_usage": totals, "usage_complete": complete,
        "total_usage": totals if complete else None,
        "requests_with_unknown_usage": sum(not u["complete"] for u in usage),
        "requests_with_unknown_stats": sum(not r["stats_known"] for r in records),
        "provider_calls_known": sum(r["stats"]["provider_calls"] for r in records),
        "retries_known": sum(r["stats"]["retries"] for r in records),
        "repairs_known": sum(r["stats"]["repairs"] for r in records),
        "requests_with_repair": sum(r["stats"]["repairs"] > 0 for r in records),
        "requested_models": sorted({r["stats"]["requested_model"] for r in records if r["stats"]["requested_model"]}),
        "returned_models": sorted({m for r in records for m in r["stats"]["response_models"]}),
        "dollar_cost": dollar_cost(records, prices),
    }


def build_summary(config: dict, records: list[dict], cases: list[Case]) -> dict:
    lookup = {c.id: c for c in cases}
    groups, scores_by_group = {}, {}
    for approach in config["approaches"]:
        for track in config["tracks"]:
            key = f"{approach}/{track}"
            selected = [r for r in records if r["approach"] == approach and r["track"] == track]
            scores = [score_case(lookup[r["case_id"]], r["report"]["claims"] if r["report"] else [],
                                 track=track, error=r["error_code"]) for r in selected]
            statuses = Counter(r["status"] for r in selected)
            status = "NOT_RUN" if statuses["NOT_RUN"] == len(selected) else (
                "COMPLETE" if statuses["OK"] == len(selected) else "PARTIAL_ERRORS")
            scores_by_group[key] = scores
            groups[key] = {
                "status": status, "requested_cases": len(selected), "statuses": dict(statuses),
                "gold_claims": sum(len(lookup[r["case_id"]].gold_claims) for r in selected),
                "request_success": ratio(statuses["OK"], len(selected)),
                "errors": dict(sorted(Counter(r["error_code"] for r in selected if r["error_code"]).items())),
                "quality": None if status == "NOT_RUN" else aggregate(scores),
                "failure_inclusive_quality": aggregate(scores),
                "slices": slices(lookup, scores),
                "uncertainty": None if status == "NOT_RUN" else bootstrap(
                    scores, seed=config["seed"], samples=config["bootstrap_samples"]),
                "resources": resources(selected, config.get("prices") if config["format_version"] != 3 else None),
            }
            if config["format_version"] == 3:
                from grounding_eval.confidence import routing_summary
                from grounding_eval.hybrid import mixed_resources

                groups[key]["resources"] = mixed_resources(selected, config.get("prices"))
                if approach.startswith("jev_"):
                    groups[key]["routing"] = routing_summary(selected, lookup)
    paired = {}
    for track in config["tracks"]:
        optimized, minimal = f"optimized/{track}", f"minimal/{track}"
        if optimized in groups and minimal in groups:
            if any(groups[k]["statuses"].get("NOT_RUN", 0) for k in (optimized, minimal)):
                paired[track] = {"status": "NOT_RUN", "reason": "both_systems_must_measure_the_same_population"}
            else:
                paired[track] = bootstrap(scores_by_group[optimized], paired_scores=scores_by_group[minimal],
                                          seed=config["seed"], samples=config["bootstrap_samples"])
    result = {
        "format_version": config["format_version"], "measurement_kind": config["measurement_kind"],
        "schema_version": config["schema_version"], "dataset_version": config["dataset_version"],
        "annotation_version": config["annotation_version"], "scorer_version": config["scorer_version"],
        "split": config["split"], "dataset_sha256": config["dataset_sha256"],
        "code_sha256": config["fingerprints"]["code_sha256"],
        "groups": groups, "paired_optimized_minus_minimal": paired,
        "limitations": limitations(cases),
    }
    if config["format_version"] == 3:
        result["paired_jev_optimized_minus_jev_minimal"] = {
            track: bootstrap(scores_by_group[f"jev_optimized/{track}"],
                             paired_scores=scores_by_group[f"jev_minimal/{track}"],
                             seed=config["seed"], samples=config["bootstrap_samples"])
            for track in config["tracks"]
            if all(f"{a}/{track}" in groups and not groups[f"{a}/{track}"]["statuses"].get("NOT_RUN")
                   for a in ("jev_minimal", "jev_optimized"))}
        result["comparison_note"] = "Jev oracle variants share one algorithm; differences are sampling/operations, " \
                                    "not extraction gains. Comparisons with old methods change workflow/model/policy."
    return result
