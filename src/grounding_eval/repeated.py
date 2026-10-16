"""Family-paired repeated measurements; repeats never create independent families."""
from __future__ import annotations

import json
from pathlib import Path

from grounding_eval.scoring import aggregate, primary_values
from grounding_eval.uncertainty import bootstrap


def read_repeated_run(path: Path, *, repetition: int) -> dict:
    """Use the saved-artifact guard before consuming any record; never run inference."""
    from grounding_eval.runner import regenerate_report

    regenerate_report(path)
    return {"repetition": repetition,
            "config": json.loads((path / "config.json").read_text()),
            "records": [json.loads(line) for line in (path / "records.jsonl").read_text().splitlines()]}


def _comparable(config: dict) -> dict:
    fields = ("schema_version", "dataset_version", "annotation_version", "scorer_version",
              "dataset_sha256", "fingerprints", "settings", "measurement_kind", "split")
    return {**{key: config[key] for key in fields}, "order_policy": config["execution"]["order"]}


def analyze_repeated(runs: list[dict], *, case_ids: list[str], approach: str, track: str,
                     baseline: str | None = None, seed: int, samples: int) -> dict:
    """Analyze an explicit common subset from verified saved runs, retaining all repeats.

    A full population run followed by two subset runs provides three observations only
    for case_ids. Callers load each run with read_repeated_run; tests may supply frozen
    independent score fixtures directly. No intersection or best-of-N is selected here.
    """
    if (not runs or not isinstance(case_ids, list) or not case_ids
            or any(type(case_id) is not str or not case_id.strip() for case_id in case_ids)
            or len(set(case_ids)) != len(case_ids) or approach == baseline):
        raise ValueError("invalid_repeated_population")
    repetitions = [run["repetition"] for run in runs]
    if (any(type(rep) is not int or rep < 1 for rep in repetitions)
            or len(set(repetitions)) != len(repetitions)):
        raise ValueError("invalid_repeated_population")
    try:
        control = _comparable(runs[0]["config"])
        if any(_comparable(run["config"]) != control for run in runs):
            raise ValueError("incompatible_repeated_configuration")
        pooled, paired, per_repeat, families = [], [], {}, {}
        for run in sorted(runs, key=lambda item: item["repetition"]):
            rep, config, records = run["repetition"], run["config"], run["records"]
            population = config["case_ids"]
            if (len(set(population)) != len(population) or not set(case_ids) <= set(population)
                    or approach not in config["approaches"] or track not in config["tracks"]
                    or (baseline is not None and baseline not in config["approaches"])):
                raise ValueError("repeated_case_population_mismatch")
            indexed = {(r["approach"], r["track"], r["case_id"]): r for r in records}
            expected = {(a, t, case_id) for a in config["approaches"] for t in config["tracks"]
                        for case_id in population}
            if len(indexed) != len(records) or set(indexed) != expected:
                raise ValueError("repeated_record_population_mismatch")

            def selected_scores(method):
                selected = []
                for case_id in case_ids:
                    record = indexed[method, track, case_id]
                    score = record["score"]
                    if (score["case_id"] != case_id or score["track"] != track
                            or score["family_id"] != record["family_id"]
                            or (case_id in families and families[case_id] != score["family_id"])):
                        raise ValueError("repeated_family_or_score_mismatch")
                    families[case_id] = score["family_id"]
                    selected.append({**score, "repetition": rep})
                return selected

            scores = selected_scores(approach)
            other = selected_scores(baseline) if baseline else None
            pooled.extend(scores)
            paired.extend(other or [])
            observed = primary_values(scores)
            other_observed = primary_values(other) if other is not None else None
            per_repeat[str(rep)] = {
                "failure_inclusive_quality": aggregate(scores),
                "baseline_failure_inclusive_quality": aggregate(other) if other is not None else None,
                "paired_delta": {key: value - other_observed[key]
                                 if value is not None and other_observed[key] is not None else None
                                 for key, value in observed.items()} if other_observed is not None else None,
            }
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid_repeated_artifact") from exc
    return {
        "population": {"kind": "preselected_subset", "case_ids": list(case_ids),
                       "cases": len(case_ids), "repetitions": sorted(repetitions),
                       "observations": len(pooled), "independent_families": len(set(families.values())),
                       "source_run_case_counts": [len(run["config"]["case_ids"]) for run in runs]},
        "approach": approach, "baseline": baseline, "track": track,
        "per_repetition": per_repeat,
        "pooled_failure_inclusive_quality": aggregate(pooled),
        "pooled_baseline_failure_inclusive_quality": aggregate(paired) if baseline else None,
        "uncertainty": bootstrap(pooled, paired_scores=paired if baseline else None,
                                 seed=seed, samples=samples),
        "limitations": "Every selected case/repetition stays in its source-family cluster. "
                        "These repetitions measure the stated subset only; usage/cost is not imputed.",
    }
