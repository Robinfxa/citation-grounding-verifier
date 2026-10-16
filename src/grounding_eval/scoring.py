"""Verdict-blind alignment and conservative quote-set scoring.

Neither exact claim matches nor quoted-span coverage prove semantic entailment.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from grounding.contracts import VERDICTS
from grounding_eval.dataset import Case, GoldClaim, normalize

SCORER_VERSION = "2"


def ratio(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def prf(correct: int, predicted: int, gold: int) -> dict:
    return {"precision": ratio(correct, predicted), "recall": ratio(correct, gold),
            "f1": ratio(2 * correct, predicted + gold)}


def literal_valid(citation: dict, passages: list[str]) -> bool:
    index, quote = citation.get("index"), citation.get("quote")
    return (type(index) is int and 0 <= index < len(passages)
            and isinstance(quote, str) and bool(quote.strip()) and quote in passages[index])


def unique_citations(prediction: dict) -> list[dict]:
    result, seen = [], set()
    for citation in prediction.get("citations", []):
        key = (citation.get("index"), citation.get("quote"))
        if key not in seen:
            result.append(citation)
            seen.add(key)
    return result


def evidence_covered(gold: GoldClaim, prediction: dict, passages: list[str]) -> bool:
    citations = unique_citations(prediction)
    if gold.verdict == "UNSUPPORTED":
        return not citations
    if not citations or not all(literal_valid(c, passages) for c in citations):
        return False
    # AIDEV-NOTE: compare returned quote text, never the complete referenced passage.
    # Each exact gold span must be contained in a returned quotation at the same index.
    return any(all(any(c["index"] == need.index and need.quote in c["quote"]
                       for c in citations) for need in group) for group in gold.evidence_sets)


def score_case(case: Case, predictions: list[dict], *, track: str = "end-to-end",
               error: str | None = None) -> dict:
    """Score one requested case, preserving gold denominators after any failure."""
    if track not in {"oracle", "end-to-end"}:
        raise ValueError("unknown_track")
    rejected = []
    if not error and track == "oracle" and (
        [p["claim_text"] for p in predictions] != [g.claim_text for g in case.gold_claims]
    ):
        error = "oracle_identity_violation"
        rejected = predictions
    if error:
        predictions = []
    lookup = {normalize(text): i for i, g in enumerate(case.gold_claims)
              for text in [g.claim_text, *g.aliases]}
    matched: dict[int, int] = {}
    extras, duplicates = [], []
    seen_texts = set()
    for pno, prediction in enumerate(predictions):
        text_key = normalize(prediction["claim_text"])
        gno = lookup.get(text_key)
        if text_key in seen_texts or (gno is not None and gno in matched):
            duplicates.append(pno)
        seen_texts.add(text_key)
        # AIDEV-NOTE: first unused text match wins without reading labels or evidence.
        # A duplicate remains an FP even if its label would score better than the first.
        if gno is not None and gno not in matched:
            matched[gno] = pno
        else:
            extras.append(pno)
    confusion: Counter[tuple[str, str]] = Counter()
    correct_by_label: Counter[str] = Counter()
    label_correct = evidence_correct = evidence_non_u = false_support = matched_non_s = 0
    pairs = []
    for gno, gold in enumerate(case.gold_claims):
        pno = matched.get(gno)
        if pno is None:
            confusion[gold.verdict, "ERROR" if error else "MISSING"] += 1
            continue
        prediction = predictions[pno]
        matched_non_s += gold.verdict != "SUPPORTED"
        false_support += gold.verdict != "SUPPORTED" and prediction["verdict"] == "SUPPORTED"
        label_ok = prediction["verdict"] == gold.verdict
        evidence_ok = label_ok and evidence_covered(gold, prediction, case.context_passages)
        confusion[gold.verdict, prediction["verdict"]] += 1
        label_correct += label_ok
        evidence_correct += evidence_ok
        evidence_non_u += evidence_ok and gold.verdict != "UNSUPPORTED"
        if label_ok:
            correct_by_label[gold.verdict] += 1
        pairs.append({"gold_id": gold.id, "prediction_index": pno,
                      "label_correct": label_ok, "gold_evidence_covered": evidence_ok})
    for pno in extras:
        confusion["EXTRA", predictions[pno]["verdict"]] += 1
    citation_total = citation_valid = citation_relevant = quote_characters = 0
    reverse = {pno: gno for gno, pno in matched.items()}
    for pno, prediction in enumerate(predictions):
        gold = case.gold_claims[reverse[pno]] if pno in reverse else None
        for citation in unique_citations(prediction):
            citation_total += 1
            valid = literal_valid(citation, case.context_passages)
            citation_valid += valid
            quote_characters += len(citation.get("quote", ""))
            if (valid and gold and prediction["verdict"] == gold.verdict
                    and any(citation["index"] == q.index and q.quote in citation["quote"]
                            for group in gold.evidence_sets for q in group)):
                citation_relevant += 1
    gold_n, pred_n = len(case.gold_claims), len(predictions)
    return {
        "case_id": case.id, "family_id": case.family_id, "track": track, "error": error,
        "counts": {
            "gold": gold_n, "predicted": pred_n, "matched": len(matched),
            "omitted": gold_n - len(matched), "extra": len(extras), "duplicate": len(duplicates),
            "gold_non_supported": sum(g.verdict != "SUPPORTED" for g in case.gold_claims),
            "matched_non_supported": matched_non_s,
            "false_support": false_support,
            "label_correct": label_correct, "evidence_correct": evidence_correct,
            "gold_non_unsupported": sum(g.verdict != "UNSUPPORTED" for g in case.gold_claims),
            "evidence_correct_non_unsupported": evidence_non_u,
            "predicted_non_unsupported": sum(p["verdict"] != "UNSUPPORTED" for p in predictions),
            "citation_total": citation_total, "citation_literal_valid": citation_valid,
            "citation_gold_relevant": citation_relevant, "citation_characters": quote_characters,
            "requested": 1, "succeeded": int(error is None),
            "exact": int(error is None and gold_n == pred_n == evidence_correct
                         and citation_total == citation_valid == citation_relevant),
        },
        "labels": {v: {"gold": sum(g.verdict == v for g in case.gold_claims),
                        "predicted": sum(p["verdict"] == v for p in predictions),
                        "correct": correct_by_label[v]} for v in VERDICTS},
        "confusion": {row: {col: confusion[row, col] for col in (*VERDICTS, "MISSING", "ERROR")}
                      for row in (*VERDICTS, "EXTRA")},
        "matches": pairs,
        "missing_gold_ids": [g.id for i, g in enumerate(case.gold_claims) if i not in matched],
        "unmatched_predictions": [{"prediction_index": i, **predictions[i]} for i in extras],
        "rejected_predictions": rejected,
        "duplicate_prediction_indices": duplicates,
    }


def aggregate(scores: list[dict]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    labels = {v: Counter() for v in VERDICTS}
    confusion = {v: Counter() for v in (*VERDICTS, "EXTRA")}
    errors: Counter[str] = Counter()
    for score in scores:
        counts.update(score["counts"])
        for v in VERDICTS:
            labels[v].update(score["labels"][v])
        for v in confusion:
            confusion[v].update(score["confusion"][v])
        if score["error"]:
            errors[score["error"]] += 1
    per_class = {v: prf(labels[v]["correct"], labels[v]["predicted"], labels[v]["gold"])
                 for v in VERDICTS}
    f1s = [per_class[v]["f1"]["value"] for v in VERDICTS]
    return {
        "counts": dict(counts), "per_class": per_class,
        "macro_f1": sum(f1s) / len(f1s) if all(f is not None for f in f1s) else None,
        "macro_f1_note": "Fixed three-class mean; null if any class has no gold or prediction.",
        "confusion": {row: dict(value) for row, value in confusion.items()},
        "errors": dict(sorted(errors.items())),
        "strict_decomposition": prf(counts["matched"], counts["predicted"], counts["gold"]),
        "false_support_rate": ratio(counts["false_support"], counts["gold_non_supported"]),
        "false_support_note": "C/U gold matched to SUPPORTED, divided by all C/U gold. "
                              "Missing/error claims remain in the denominator, never count as false support; "
                              "read with judgment coverage and request failures.",
        "non_supported_judgment_coverage": ratio(counts["matched_non_supported"], counts["gold_non_supported"]),
        "extraction_diagnostics": {
            "omitted_gold": counts["omitted"], "extra_predictions": counts["extra"],
            "duplicate_predictions": counts["duplicate"],
            "note": "Duplicates are repeated normalized text or a second alias for an already matched gold. "
                    "Merges, splits and scope loss require the separate semantic audit.",
        },
        "joint_label": prf(counts["label_correct"], counts["predicted"], counts["gold"]),
        "joint_evidence": prf(counts["evidence_correct"], counts["predicted"], counts["gold"]),
        "oracle_accuracy": ratio(counts["label_correct"], counts["gold"]),
        "case_exact": ratio(counts["exact"], counts["requested"]),
        "request_success": ratio(counts["succeeded"], counts["requested"]),
        "literal_citation_validity": ratio(counts["citation_literal_valid"], counts["citation_total"]),
        "gold_evidence_coverage": ratio(counts["evidence_correct_non_unsupported"], counts["gold_non_unsupported"]),
        "prediction_gold_evidence_coverage": ratio(counts["evidence_correct_non_unsupported"], counts["predicted_non_unsupported"]),
        "gold_relevant_citation_precision": ratio(counts["citation_gold_relevant"], counts["citation_total"]),
        "quote_characters_per_covered_non_unsupported_claim": ratio(
            counts["citation_characters"], counts["evidence_correct_non_unsupported"]),
    }


def primary_values(scores: list[dict]) -> dict[str, float | None]:
    """Only sufficient statistics, for efficient stdlib bootstrap resampling."""
    totals = Counter()
    labels = {v: Counter() for v in VERDICTS}
    for s in scores:
        totals.update(s["counts"])
        for v in VERDICTS:
            labels[v].update(s["labels"][v])
    denominator = totals["gold"] + totals["predicted"]
    class_f1 = [2 * x["correct"] / (x["gold"] + x["predicted"])
                if x["gold"] + x["predicted"] else None for x in labels.values()]
    return {
        "joint_evidence_f1": 2 * totals["evidence_correct"] / denominator if denominator else None,
        "joint_label_f1": 2 * totals["label_correct"] / denominator if denominator else None,
        "strict_decomposition_f1": 2 * totals["matched"] / denominator if denominator else None,
        "macro_f1": sum(class_f1) / 3 if all(v is not None for v in class_f1) else None,
        "case_exact": totals["exact"] / totals["requested"] if totals["requested"] else None,
    }
