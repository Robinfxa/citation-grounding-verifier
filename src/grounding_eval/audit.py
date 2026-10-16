"""Offline packets and tamper-evident locks for a bounded, manually judged audit.

No model is called and no semantic relation is inferred by this module.
Run with ``python -m grounding_eval.audit --help``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from grounding.contracts import StrictModel
from grounding.diagnostics import operation
from grounding_eval.diagnostics import emit
from grounding_eval.provenance import strict_json
from grounding_eval.scoring import literal_valid, prf

AUDIT_VERSION = "semantic-audit-1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return strict_json(path.read_text(encoding="utf-8"))


def save_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


class Reviewer(StrictModel):
    id: StrictStr = Field(min_length=1)
    kind: Literal["ai", "human"]
    model: StrictStr | None
    completed_at: StrictStr = Field(min_length=1)
    exposure: Literal["alignment_text_only", "locked_alignment_and_evidence"]


class Relation(StrictModel):
    gold_ids: list[StrictStr]
    prediction_indices: list[StrictInt]
    relation: Literal["equivalent", "merged", "split", "scope_changed", "missing", "extra", "duplicate", "uncertain"]
    reason: StrictStr = Field(min_length=1)


class AlignmentItem(StrictModel):
    item_id: StrictStr
    relations: list[Relation]


class AlignmentReview(StrictModel):
    packet_sha256: StrictStr
    reviewer: Reviewer
    items: list[AlignmentItem]


class Judgment(StrictModel):
    gold_id: StrictStr
    prediction_index: StrictInt = Field(ge=0)
    label: Literal["correct", "incorrect", "uncertain"]
    evidence: Literal["sufficient", "insufficient", "uncertain", "not_applicable"]
    quote_economy: Literal["compact", "redundant", "not_applicable"]
    reason: StrictStr = Field(min_length=1)


class EvidenceItem(StrictModel):
    item_id: StrictStr
    judgments: list[Judgment]


class EvidenceReview(StrictModel):
    packet_sha256: StrictStr
    reviewer: Reviewer
    items: list[EvidenceItem]


def prepare(run_dir: Path, selection: Path, policy: Path, output: Path, seed: int) -> None:
    """Create stage-one input and a separate key that the reviewer must not read."""
    from grounding_eval.runner import regenerate_report

    regenerate_report(run_dir)  # Validate actual saved population and scorer binding first.
    ids = read(selection)
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or not all(isinstance(x, str) for x in ids):
        raise ValueError("invalid_selection")
    cases = {c["id"]: c for c in map(json.loads, (run_dir / "cases.jsonl").read_text().splitlines())}
    records = [r for r in map(json.loads, (run_dir / "records.jsonl").read_text().splitlines())
               if r["track"] == "end-to-end" and r["case_id"] in ids]
    if not set(ids) <= cases.keys() or any(cases[i]["split"] != "test" for i in ids):
        raise ValueError("invalid_selection")
    expected = {(i, a) for i in ids for a in ("heuristic", "minimal", "optimized")}
    if {(r["case_id"], r["approach"]) for r in records} != expected or len(records) != len(expected):
        raise ValueError("incomplete_audit_population")
    random.Random(seed).shuffle(records)
    items, key = [], {}
    for number, record in enumerate(records):
        item_id = f"item-{number:04d}"
        case = cases[record["case_id"]]
        predictions = record["report"]["claims"] if record["report"] else []
        items.append({"item_id": item_id, "answer": case["generated_answer"],
                      "gold_claims": [{"id": g["id"], "text": g["claim_text"]} for g in case["gold_claims"]],
                      "predictions": [{"index": i, "text": p["claim_text"]} for i, p in enumerate(predictions)]})
        key[item_id] = {"case": case, "record": record}
    output.mkdir(parents=True, exist_ok=False)
    save_new(output / "alignment-input.json", {"audit_version": AUDIT_VERSION,
             "policy_sha256": digest(policy), "selection_sha256": digest(selection), "items": items})
    save_new(output / "key.json", {"items": key, "run_files_sha256": {
        name: digest(run_dir / name) for name in ("config.json", "cases.jsonl", "records.jsonl", "completion.json")},
        "module_sha256": digest(Path(__file__)), "policy_sha256": digest(policy)})


def check_alignment(packet: dict, review: AlignmentReview) -> None:
    if review.reviewer.exposure != "alignment_text_only":
        raise ValueError("incorrect_review_exposure")
    items = {x["item_id"]: x for x in packet["items"]}
    if len(review.items) != len(items) or {x.item_id for x in review.items} != items.keys():
        raise ValueError("incomplete_alignment_review")
    for item in review.items:
        gold, predicted = [], []
        for relation in item.relations:
            g, p = len(relation.gold_ids), len(relation.prediction_indices)
            valid = {
                "equivalent": g == p == 1, "scope_changed": g == p == 1,
                "merged": g >= 2 and p == 1, "split": g == 1 and p >= 2,
                "missing": g == 1 and p == 0, "extra": g == 0 and p == 1,
                "duplicate": g == 0 and p == 1, "uncertain": g + p > 0,
            }[relation.relation]
            if not valid or not relation.reason.strip():
                raise ValueError("invalid_relation")
            gold.extend(relation.gold_ids)
            predicted.extend(relation.prediction_indices)
        source = items[item.item_id]
        if (Counter(gold) != Counter(g["id"] for g in source["gold_claims"])
                or Counter(predicted) != Counter(p["index"] for p in source["predictions"])):
            raise ValueError("relation_inventory_not_partitioned")


def lock_alignment(folder: Path, review_path: Path) -> None:
    packet_path = folder / "alignment-input.json"
    review = AlignmentReview.model_validate(read(review_path))
    if review.packet_sha256 != digest(packet_path):
        raise ValueError("packet_changed")
    if read(folder / "key.json")["module_sha256"] != digest(Path(__file__)):
        raise ValueError("audit_module_changed")
    check_alignment(read(packet_path), review)
    save_new(folder / "alignment-locked.json", review.model_dump())
    save_new(folder / "alignment-lock.json", {
        "packet_sha256": digest(packet_path), "review_sha256": digest(folder / "alignment-locked.json"),
        "key_sha256": digest(folder / "key.json"), "module_sha256": digest(Path(__file__))})


def locked(folder: Path) -> tuple[dict, dict, AlignmentReview]:
    lock = read(folder / "alignment-lock.json")
    for filename, field in [("alignment-input.json", "packet_sha256"),
                            ("alignment-locked.json", "review_sha256"), ("key.json", "key_sha256")]:
        if digest(folder / filename) != lock[field]:
            raise ValueError("locked_input_changed")
    if digest(Path(__file__)) != lock["module_sha256"]:
        raise ValueError("audit_module_changed")
    packet = read(folder / "alignment-input.json")
    review = AlignmentReview.model_validate(read(folder / "alignment-locked.json"))
    check_alignment(packet, review)
    return packet, read(folder / "key.json"), review


def evidence_packet(folder: Path, key: dict, review: AlignmentReview) -> dict:
    items = []
    for item in review.items:
        entry = key["items"][item.item_id]
        case, record = entry["case"], entry["record"]
        items.append({"item_id": item.item_id, "context_passages": case["context_passages"],
                      "gold_claims": case["gold_claims"], "relations": [r.model_dump() for r in item.relations],
                      "predictions": record["report"]["claims"] if record["report"] else [],
                      "error_code": record["error_code"]})
    return {"audit_version": AUDIT_VERSION,
            "alignment_lock_sha256": digest(folder / "alignment-lock.json"), "items": items}


def prepare_evidence(folder: Path) -> None:
    _, key, review = locked(folder)
    save_new(folder / "evidence-input.json", evidence_packet(folder, key, review))


def summarize(folder: Path, review_path: Path) -> dict:
    packet, key, alignment = locked(folder)
    evidence_path = folder / "evidence-input.json"
    evidence_input = read(evidence_path)
    review = EvidenceReview.model_validate(read(review_path))
    if (review.packet_sha256 != digest(evidence_path)
            or evidence_input != evidence_packet(folder, key, alignment)
            or review.reviewer.exposure != "locked_alignment_and_evidence"):
        raise ValueError("evidence_binding_invalid")
    reviewed = {x.item_id: x for x in review.items}
    if len(review.items) != len(alignment.items) or set(reviewed) != {x.item_id for x in alignment.items}:
        raise ValueError("incomplete_evidence_review")
    groups = {}
    for item in alignment.items:
        entry = key["items"][item.item_id]
        case, record = entry["case"], entry["record"]
        predictions = record["report"]["claims"] if record["report"] else []
        gold = {g["id"]: g for g in case["gold_claims"]}
        equivalents = {(r.gold_ids[0], r.prediction_indices[0]) for r in item.relations if r.relation == "equivalent"}
        judgments = reviewed[item.item_id].judgments
        if len(judgments) != len(equivalents) or {(j.gold_id, j.prediction_index) for j in judgments} != equivalents:
            raise ValueError("judgments_do_not_match_locked_alignment")
        group = groups.setdefault(record["approach"], {"counts": Counter(), "families": set(), "case_ids": []})
        counts = group["counts"]
        group["families"].add(case["family_id"])
        group["case_ids"].append(case["id"])
        counts.update(gold=len(gold), predicted=len(predictions), equivalent=len(equivalents),
                      cases=1, failed=int(record["error_code"] is not None))
        counts.update({f"relation_{name}": n for name, n in Counter(r.relation for r in item.relations).items()})
        for judgment in judgments:
            p, g = predictions[judgment.prediction_index], gold[judgment.gold_id]
            if judgment.label == "correct" and p["verdict"] != g["verdict"]:
                raise ValueError("correct_label_disagrees_with_frozen_gold")
            label_ok = judgment.label == "correct"
            citations = p["citations"]
            valid = all(literal_valid(c, case["context_passages"]) for c in citations)
            if g["verdict"] == "UNSUPPORTED":
                if judgment.evidence != "not_applicable":
                    raise ValueError("unsupported_evidence_not_applicable")
                evidence_ok = not citations
            else:
                if judgment.evidence == "not_applicable":
                    raise ValueError("non_unsupported_evidence_required")
                evidence_ok = judgment.evidence == "sufficient" and bool(citations) and valid
            counts.update(label_correct=int(label_ok), evidence_correct=int(label_ok and evidence_ok),
                          uncertain_labels=int(judgment.label == "uncertain"),
                          uncertain_evidence=int(judgment.evidence == "uncertain"),
                          redundant_quotes=int(judgment.quote_economy == "redundant"))
    output = {}
    for name, group in groups.items():
        c = group["counts"]
        output[name] = {"counts": dict(c), "source_families": len(group["families"]),
                        "case_ids": sorted(group["case_ids"]),
                        "semantic_decomposition": prf(c["equivalent"], c["predicted"], c["gold"]),
                        "joint_label": prf(c["label_correct"], c["predicted"], c["gold"]),
                        "joint_evidence": prf(c["evidence_correct"], c["predicted"], c["gold"])}
    return {"audit_version": AUDIT_VERSION, "policy_sha256": packet["policy_sha256"],
            "selection_sha256": packet["selection_sha256"], "groups": output,
            "reviewers": {"alignment": alignment.reviewer.model_dump(), "evidence": review.reviewer.model_dump()},
            "scope": "Selected first-run end-to-end cases only; no full-population rescore; uncertain and non-atomic relations receive no automatic credit."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    for name in ("run-dir", "selection", "policy", "output"):
        p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20261016)
    p.add_argument("--quiet", action="store_true")
    for name in ("lock-alignment", "prepare-evidence", "summarize"):
        p = commands.add_parser(name)
        p.add_argument("folder", type=Path)
        p.add_argument("--quiet", action="store_true")
        if name != "prepare-evidence":
            p.add_argument("review", type=Path)
    args = parser.parse_args()
    with operation(enabled=not args.quiet, new=True) as op:
        emit(op, "semantic_audit", "start", "started")
        try:
            result = {"status": "OK"}
            if args.command == "prepare":
                prepare(args.run_dir, args.selection, args.policy, args.output, args.seed)
            elif args.command == "lock-alignment":
                lock_alignment(args.folder, args.review)
            elif args.command == "prepare-evidence":
                prepare_evidence(args.folder)
            else:
                result = summarize(args.folder, args.review)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            emit(op, "semantic_audit", "end", "success")
            return 0
        except (ValueError, OSError, KeyError, TypeError, RecursionError):
            print('{"error_code":"audit_artifact_invalid"}')
            emit(op, "semantic_audit", "end", "failure", error_code="audit_artifact_invalid")
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
