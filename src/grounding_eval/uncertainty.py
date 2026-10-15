"""Seeded family-cluster percentile intervals without a numeric dependency."""
from __future__ import annotations

import random
from collections import defaultdict

from grounding_eval.scoring import primary_values


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    offset = (len(ordered) - 1) * fraction
    lower = int(offset)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (offset - lower)


def bootstrap(scores: list[dict], *, seed: int, samples: int,
              paired_scores: list[dict] | None = None) -> dict:
    if samples < 1:
        raise ValueError("bootstrap_samples_must_be_positive")
    clusters: dict[str, list[dict]] = defaultdict(list)
    paired: dict[str, dict] = {}
    for score in scores:
        clusters[score["family_id"]].append(score)
    if paired_scores is not None:
        paired = {s["case_id"]: s for s in paired_scores}
        if len(paired) != len(paired_scores) or set(paired) != {s["case_id"] for s in scores}:
            raise ValueError("paired_case_population_mismatch")
        if any(paired[s["case_id"]]["family_id"] != s["family_id"] for s in scores):
            raise ValueError("paired_family_mismatch")
    keys = sorted(clusters)
    rng = random.Random(seed)
    values: dict[str, list[float]] = {k: [] for k in primary_values(scores)}
    for _ in range(samples):
        sampled = [s for _ in keys for s in clusters[rng.choice(keys)]] if keys else []
        metrics = primary_values(sampled)
        other = primary_values([paired[s["case_id"]] for s in sampled]) if paired_scores is not None else None
        for name, value in metrics.items():
            if value is not None and (other is None or other[name] is not None):
                values[name].append(value if other is None else value - other[name])
    intervals = {}
    observed = primary_values(scores)
    other_observed = primary_values(paired_scores) if paired_scores is not None else None
    for name, draws in values.items():
        estimate = observed[name]
        if other_observed is not None:
            estimate = (estimate - other_observed[name]
                        if estimate is not None and other_observed[name] is not None else None)
        intervals[name] = {
            "estimate": estimate,
            "low": percentile(draws, .025), "high": percentile(draws, .975),
            "defined_resamples": len(draws), "undefined_resamples": samples - len(draws),
            "degenerate": bool(draws) and min(draws) == max(draws),
        }
    return {
        "method": "paired_family_percentile" if paired_scores is not None else "family_percentile",
        "confidence": .95, "seed": seed, "samples": samples,
        "unit": "family", "independent_units": len(keys), "intervals": intervals,
        "limitations": "Small synthetic sample sensitivity only; excludes annotation bias and model randomness. "
                      "Degenerate intervals do not demonstrate zero uncertainty. Undefined draws are counted.",
    }
