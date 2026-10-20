"""Explicit format-3 measurements; never reinterpret legacy provider totals as stages."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from grounding.config import Settings
from grounding.contracts import (
    ERRORS,
    MAX_CLAIMS,
    ChoiceDecision,
    RunStats,
    StrictModel,
    VerificationError,
)

JEV_APPROACHES = ("jev_minimal", "jev_optimized")
ALL_APPROACHES = ("heuristic", "minimal", "optimized", *JEV_APPROACHES)
REASONS = ("label_uncertain", "unsupported_reason_uncertain", "candidate_missing",
           "quote_uncertain", "quote_disagreement")
PROVIDERS = ("typesafe", "openai", "codex")


class Usage(StrictModel):
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    cached_input_tokens: StrictInt = Field(ge=0)
    complete: StrictBool

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("invalid_cached_usage")
        return self


class Decision(StrictModel):
    choice: StrictStr
    confidence: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    probabilities: dict[StrictStr, float]
    derived_confidence: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    gate_score: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    threshold: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    passes_threshold: StrictBool | None

    @model_validator(mode="before")
    @classmethod
    def numbers(cls, value):
        if not isinstance(value, dict) or not isinstance(value.get("probabilities"), dict):
            raise ValueError("invalid_choice")
        if any(type(p) not in (int, float) for p in value["probabilities"].values()):
            raise ValueError("invalid_probability")
        return value

    @model_validator(mode="after")
    def coherent(self) -> Self:
        probabilities = self.probabilities
        if (len(probabilities) < 2 or self.choice not in probabilities
                or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values())
                or abs(math.fsum(probabilities.values()) - 1) > .001
                or max(probabilities.values()) - probabilities[self.choice] > .000001):
            raise ValueError("invalid_choice_distribution")
        raw = ChoiceDecision(self.choice, self.confidence, probabilities)
        difference = abs(self.confidence - raw.derived_confidence)
        if ((difference > .02 and not math.isclose(difference, .02, rel_tol=0, abs_tol=4*math.ulp(1.0)))
                or self.derived_confidence != raw.derived_confidence
                or self.gate_score != raw.gate_score
                or self.passes_threshold != (None if self.threshold is None else self.gate_score >= self.threshold)):
            raise ValueError("invalid_derived_choice")
        return self


class Attempt(StrictModel):
    stage: StrictStr = Field(min_length=1, max_length=64)
    provider: Literal["typesafe", "openai", "codex"]
    requested_model: StrictStr | None
    response_models: list[StrictStr]
    outcome: Literal["success", "failure", "cancelled"]
    usage: Usage
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    question_count: StrictInt = Field(ge=0)
    error_code: StrictStr | None
    retry: StrictBool
    repair: StrictBool

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if ((self.outcome == "failure") != (self.error_code is not None)
                or (self.error_code is not None and self.error_code not in ERRORS)
                or (self.provider != "typesafe" and self.question_count)
                or (self.outcome == "success" and self.provider == "typesafe" and (
                    self.requested_model != "jev-1.14.0" or self.response_models != ["jev-1.14.0"]))):
            raise ValueError("invalid_attempt")
        return self


class Trace(StrictModel):
    claim_id: StrictInt = Field(ge=0, lt=MAX_CLAIMS)
    relation: Decision | None
    selection: Decision | None
    unsupported_reason: Decision | None
    evidence: Decision | None
    fallback_reason: Literal["label_uncertain", "unsupported_reason_uncertain", "candidate_missing",
                             "quote_uncertain", "quote_disagreement"] | None
    final_origin: Literal["jev", "llm", "empty_context"] | None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        for value in (self.relation, self.evidence):
            if value and set(value.probabilities) != {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED"}:
                raise ValueError("invalid_relation_options")
        if self.unsupported_reason and set(self.unsupported_reason.probabilities) != {
            "INSUFFICIENT_EVIDENCE", "UNRESOLVED_CONFLICT"
        }:
            raise ValueError("invalid_reason_options")
        return self


class Budget(StrictModel):
    """Per-provider experiment allocations, independent of the stopped pilot."""
    provider_attempts: dict[Literal["typesafe", "openai", "codex"], StrictInt]
    dollar_policy: Literal["measured_only_no_hard_limit"]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if any(n < 0 for n in self.provider_attempts.values()):
            raise ValueError("invalid_provider_allocations")
        return self


def experiment_settings(settings: Settings) -> dict:
    applied = settings.provider == "openai"
    jev = {"model": settings.jev_model, "label_threshold": settings.jev_label_threshold,
           "endpoint_sha256": hashlib.sha256(settings.jev_base_url.encode()).hexdigest(),
           "evidence_threshold": settings.jev_evidence_threshold,
           "reason_threshold": settings.jev_reason_threshold, "fallback": settings.jev_fallback,
           "max_request_bytes": settings.jev_max_request_bytes,
           "max_question_bytes": settings.jev_max_question_bytes}
    llm = {"provider": settings.provider, "model": settings.model,
           "roles": ["answer_only_extraction", "fixed_claim_fallback"],
           "max_output_tokens": {"requested": settings.max_output_tokens,
                                 "effective": settings.max_output_tokens if applied else None,
                                 "application": "applied" if applied else "not_applied"}}
    return {"jev": jev, "llm": llm,
            "policy": {"confidence": "min_returned_derived_v1", "probability_sum_tolerance": .001,
                       "argmax_tolerance": .000001, "confidence_tolerance": .02,
                       "claim_identity": "zero_based_report_order",
                       "methods": {"jev_minimal": "rule_sentences_then_shared_judgment",
                                   "jev_optimized": "answer_only_llm_extraction_then_shared_judgment",
                                   "oracle": "identical_fixed_claim_judgment_no_extraction"},
                       "source_binding": "full_source_fingerprints"}}


def freeze_experiment(settings: Settings, fingerprints: dict) -> dict:
    value = experiment_settings(settings)
    files = fingerprints["files"]
    # Bind exact implementation/question/candidate bytes, including prompts, without
    # inventing a separate policy name that could drift from the actual producer.
    value["policy"]["files"] = {name: digest for name, digest in files.items()
                                 if name.startswith("grounding/")}
    value["policy_sha256"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return value


def validate_experiment(config: dict) -> None:
    experiment = config["experiment"]
    if set(experiment) != {"jev", "llm", "policy", "policy_sha256"}:
        raise ValueError("invalid_experiment")
    unsigned = {k: v for k, v in experiment.items() if k != "policy_sha256"}
    if hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest() != experiment["policy_sha256"]:
        raise ValueError("invalid_policy_fingerprint")
    jev = experiment["jev"]
    allowed = {"model", "endpoint_sha256", "label_threshold", "evidence_threshold", "reason_threshold", "fallback",
               "max_request_bytes", "max_question_bytes"}
    if (set(jev) != allowed or jev["model"] != "jev-1.14.0"
            or experiment["policy"]["files"] != {n: h for n, h in config["fingerprints"]["files"].items()
                                                  if n.startswith("grounding/")}
            or experiment["llm"]["provider"] != config["settings"]["provider"]
            or experiment["llm"]["model"] != config["settings"]["model"]
            or experiment["llm"]["max_output_tokens"] != config["settings"]["max_output_tokens"]):
        raise ValueError("invalid_experiment_binding")
    try:
        Settings(jev_model=jev["model"], jev_label_threshold=jev["label_threshold"],
                 jev_evidence_threshold=jev["evidence_threshold"], jev_reason_threshold=jev["reason_threshold"],
                 jev_fallback=jev["fallback"], jev_max_request_bytes=jev["max_request_bytes"],
                 jev_max_question_bytes=jev["max_question_bytes"])
    except VerificationError:
        raise ValueError("invalid_experiment_settings") from None


def serialize_stats(stats: RunStats, *, format_version: int, jev_settings: dict | None = None) -> dict:
    data = asdict(stats)
    data["response_models"] = list(stats.response_models)
    if format_version == 2:
        # AIDEV-NOTE: explicit stripping preserves strict legacy records after the
        # shared dataclass grows; never relax SavedStats to accept unmeasured fields.
        del data["attempts"], data["claim_decisions"]
    else:
        data["attempts"] = list(data["attempts"])
        data["claim_decisions"] = list(data["claim_decisions"])
        for attempt in data["attempts"]:
            attempt["response_models"] = list(attempt["response_models"])
        for trace, original in zip(data["claim_decisions"], stats.claim_decisions, strict=True):
            for name in ("relation", "selection", "unsupported_reason", "evidence"):
                choice = getattr(original, name)
                if choice is not None:
                    threshold_key = {"relation": "label_threshold", "evidence": "evidence_threshold",
                                     "unsupported_reason": "reason_threshold"}.get(name)
                    threshold = jev_settings[threshold_key] if jev_settings and threshold_key else None
                    trace[name].update(derived_confidence=choice.derived_confidence,
                                       gate_score=choice.gate_score, threshold=threshold,
                                       passes_threshold=None if threshold is None else choice.gate_score >= threshold)
    return data


def validate_attempt_totals(stats: dict) -> None:
    attempts = stats["attempts"]
    if stats["provider"] == "hybrid":
        if (stats["requested_model"] is not None or len(attempts) != stats["provider_calls"]
                or stats["retries"] != sum(a["retry"] for a in attempts)
                or stats["repairs"] < sum(a["repair"] and not a["retry"] for a in attempts)):
            raise ValueError("inconsistent_attempts")
        usage = {key: sum(a["usage"][key] for a in attempts)
                 for key in ("input_tokens", "output_tokens", "cached_input_tokens")}
        if (any(stats["usage"][key] != value for key, value in usage.items())
                or stats["usage"]["complete"] != all(a["usage"]["complete"] for a in attempts)):
            raise ValueError("inconsistent_stage_usage")
    ids = [t["claim_id"] for t in stats["claim_decisions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_claim_trace")


def validate_routing(stats: dict, report: dict | None, experiment: dict, *, approach: str) -> None:
    from grounding_eval.confidence import automatic_candidate, thresholds

    if approach in JEV_APPROACHES and stats["provider"] != "hybrid":
        raise ValueError("invalid_hybrid_identity")
    gates = {"relation": "label_threshold", "evidence": "evidence_threshold",
             "unsupported_reason": "reason_threshold", "selection": None}
    for trace in stats["claim_decisions"]:
        for name, key in gates.items():
            decision = trace[name]
            if decision is not None and decision["threshold"] != (experiment["jev"][key] if key else None):
                raise ValueError("invalid_saved_gate_threshold")
        if report is None:
            continue
        index = trace["claim_id"]
        if index >= len(report["claims"]):
            raise ValueError("invalid_trace_identity")
        if trace["final_origin"] == "jev":
            label, route = automatic_candidate(trace, thresholds({"experiment": experiment}))
            if route != "accepted" or label != report["claims"][index]["verdict"] or trace["fallback_reason"]:
                raise ValueError("inconsistent_automatic_origin")
        if trace["final_origin"] == "llm" and trace["fallback_reason"] is None:
            raise ValueError("missing_fallback_reason")


def validate_price_book(prices: list[dict] | None) -> list[dict] | None:
    from grounding_eval.reporting import validate_prices

    if prices is None:
        return None
    if not isinstance(prices, list):
        raise ValueError("invalid_price_book")
    if any(not isinstance(value, dict) for value in prices):
        raise ValueError("invalid_price_book")
    validated = [validate_prices(value) for value in prices]
    identities = [(p["provider"], p["model"]) for p in validated]
    if (len(identities) != len(set(identities))
            or any(provider not in {"typesafe", "openai"} for provider, _ in identities)):
        raise ValueError("invalid_price_book")
    return validated


def mixed_resources(records: list[dict], prices: list[dict] | None) -> dict:
    from grounding_eval.reporting import resources

    result = resources(records, None)
    stages: dict[tuple, list] = {}
    unknown_records = sum(r["stats"]["provider_calls"] != len(r["stats"]["attempts"])
                          or not r["stats_known"] for r in records)
    for record in records:
        for attempt in record["stats"]["attempts"]:
            key = (attempt["stage"], attempt["provider"], attempt["requested_model"])
            stages.setdefault(key, []).append(attempt)
    subtotal, unknown_cost = 0.0, unknown_records
    stage_rows = []
    for (stage, provider, model), attempts in sorted(stages.items(), key=lambda pair: str(pair[0])):
        known = {key: sum(a["usage"][key] for a in attempts)
                 for key in ("input_tokens", "output_tokens", "cached_input_tokens")}
        complete = all(a["usage"]["complete"] for a in attempts)
        price = next((p for p in prices or [] if (p["provider"], p["model"]) == (provider, model)), None)
        cost, cost_complete = 0.0, True
        for a in attempts:
            priced = (provider != "codex" and price is not None
                      and all(m == model for m in a["response_models"]))
            if not priced:
                cost_complete = False
                continue
            u = a["usage"]
            cost += ((u["input_tokens"]-u["cached_input_tokens"])*price["input_per_million"]
                     + u["cached_input_tokens"]*price["cached_input_per_million"]
                     + u["output_tokens"]*price["output_per_million"])/1_000_000
            cost_complete &= u["complete"]
        subtotal += cost
        unknown_cost += not cost_complete
        stage_rows.append({"stage": stage, "provider": provider, "requested_model": model,
                           "response_models": sorted({m for a in attempts for m in a["response_models"]}),
                           "attempts": len(attempts), "questions": sum(a["question_count"] for a in attempts),
                           "summed_attempt_latency_ms": sum(a["latency_ms"] for a in attempts),
                           "outcomes": dict(Counter(a["outcome"] for a in attempts)),
                           "known_usage": known, "usage_complete": complete,
                           "total_usage": known if complete else None,
                           "known_cost_subtotal_usd": cost,
                           "total_cost_usd": cost if cost_complete else None})
    result.update({"stages": stage_rows, "questions": sum(x["questions"] for x in stage_rows),
                   "records_with_missing_attempts": unknown_records,
                   "dollar_cost": {"currency": "USD", "known_subtotal": subtotal,
                                   "value": None if unknown_cost else subtotal,
                                   "reason": "unknown_or_unpriced_stages" if unknown_cost else "measured_stage_usage"}})
    return result
