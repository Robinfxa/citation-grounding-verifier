import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from grounding.config import Settings
from grounding.verifiers import build_verifier
from grounding_eval import audit
from grounding_eval.dataset import load_dataset
from grounding_eval.runner import run_benchmark


def reviewer(exposure):
    return {"id": "offline-protocol-test", "kind": "ai", "model": "fixture-not-inference",
            "completed_at": "2026-10-16T00:00:00Z", "exposure": exposure}


@pytest.fixture
async def packet(tmp_path):
    legacy = Path(__file__).resolve().parents[2] / "datasets/legacy/main-v1.jsonl"
    case = load_dataset(legacy)[0].model_copy(update={"split": "test"})
    dataset = tmp_path / "fixture.jsonl"
    dataset.write_text(json.dumps(case.model_dump()) + "\n")
    settings = Settings(diagnostics=False)
    methods = ["heuristic", "minimal", "optimized"]
    run = tmp_path / "run"
    # Actual runner, with the explicitly labeled offline verifier seam only.
    await run_benchmark(dataset_path=dataset, output=run, approaches=methods, split="test",
                        track="end-to-end", bootstrap_samples=5, settings=settings,
                        verifiers={name: build_verifier("heuristic", settings=settings) for name in methods})
    selection, policy = tmp_path / "selection.json", tmp_path / "policy.md"
    selection.write_text(json.dumps([case.id]))
    policy.write_text("Frozen protocol fixture; not substantive reviewer evidence.\n")
    folder = tmp_path / "audit"
    audit.prepare(run, selection, policy, folder, seed=9)
    return folder


def alignment_review(folder):
    packet = audit.read(folder / "alignment-input.json")
    return {"packet_sha256": audit.digest(folder / "alignment-input.json"),
            "reviewer": reviewer("alignment_text_only"), "items": [
                {"item_id": item["item_id"], "relations": [
                    {"gold_ids": [g["id"]], "prediction_indices": [i],
                     "relation": "equivalent", "reason": "Synthetic protocol expectation."}
                    for i, g in enumerate(item["gold_claims"])]} for item in packet["items"]]}


def lock(folder, value=None):
    path = folder / "alignment-review.json"
    audit.save_new(path, value or alignment_review(folder))
    audit.lock_alignment(folder, path)
    audit.prepare_evidence(folder)


def evidence_review(folder):
    packet = audit.read(folder / "evidence-input.json")
    return {"packet_sha256": audit.digest(folder / "evidence-input.json"),
            "reviewer": reviewer("locked_alignment_and_evidence"), "items": [
                {"item_id": item["item_id"], "judgments": [
                    {"gold_id": r["gold_ids"][0], "prediction_index": r["prediction_indices"][0],
                     "label": "correct", "evidence": "sufficient", "quote_economy": "compact",
                     "reason": "Synthetic protocol expectation."}
                    for r in item["relations"] if r["relation"] == "equivalent"]}
                for item in packet["items"]]}


async def test_packet_hides_all_label_and_method_fields_and_actual_cli_round_trip(packet):
    value = audit.read(packet / "alignment-input.json")
    assert len(value["items"]) == 3
    for item in value["items"]:
        assert set(item) == {"item_id", "answer", "gold_claims", "predictions"}
        assert all(set(g) == {"id", "text"} for g in item["gold_claims"])
        assert all(set(p) == {"index", "text"} for p in item["predictions"])
    lock(packet)
    review = packet / "evidence-review.json"
    audit.save_new(review, evidence_review(packet))
    result = subprocess.run([sys.executable, "-m", "grounding_eval.audit", "summarize", str(packet), str(review)],
                            capture_output=True, text=True, env=os.environ.copy(), timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert set(summary["groups"]) == {"heuristic", "minimal", "optimized"}
    assert all(g["counts"]["gold"] == 2 for g in summary["groups"].values())
    assert all(g["joint_label"]["recall"]["value"] == 1 for g in summary["groups"].values())
    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert [e["outcome"] for e in events] == ["started", "success"]
    assert all(e["stage"] == "semantic_audit" for e in events)
    assert len({e["request_id"] for e in events}) == 1
    quiet = subprocess.run([sys.executable, "-m", "grounding_eval.audit", "summarize", str(packet), str(review), "--quiet"],
                           capture_output=True, text=True, timeout=10)
    assert quiet.returncode == 0 and quiet.stdout == result.stdout and not quiet.stderr


async def test_cannot_reveal_evidence_before_alignment_is_locked(packet):
    with pytest.raises(FileNotFoundError):
        audit.prepare_evidence(packet)
    assert not (packet / "evidence-input.json").exists()


@pytest.mark.parametrize("defect", ["duplicate_gold", "missing_prediction", "exposure", "unknown_field", "wrong_hash"])
async def test_invalid_or_leaked_alignment_rejected(packet, defect):
    value = alignment_review(packet)
    if defect == "duplicate_gold":
        value["items"][0]["relations"][1]["gold_ids"] = ["c1"]
    elif defect == "missing_prediction":
        value["items"][0]["relations"].pop()
    elif defect == "exposure":
        value["reviewer"]["exposure"] = "locked_alignment_and_evidence"
    elif defect == "unknown_field":
        value["items"][0]["predicted_verdict"] = "SUPPORTED"
    else:
        value["packet_sha256"] = "0" * 64
    review = packet / "bad.json"
    audit.save_new(review, value)
    with pytest.raises(ValueError):
        audit.lock_alignment(packet, review)


@pytest.mark.parametrize("file", ["alignment-input.json", "alignment-locked.json", "key.json"])
async def test_locked_artifact_changes_fail_closed(packet, file):
    lock(packet)
    with (packet / file).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="locked_input_changed"):
        audit.locked(packet)


async def test_stage_two_cannot_change_alignments_or_forge_source(packet):
    lock(packet)
    value = evidence_review(packet)
    value["items"][0]["judgments"][0]["prediction_index"] = 1
    path = packet / "bad.json"
    audit.save_new(path, value)
    with pytest.raises(ValueError, match="judgments_do_not_match"):
        audit.summarize(packet, path)
    value = evidence_review(packet)
    source = audit.read(packet / "evidence-input.json")
    source["items"][0]["context_passages"] = ["Forged context"]
    (packet / "evidence-input.json").write_text(json.dumps(source))
    value["packet_sha256"] = audit.digest(packet / "evidence-input.json")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="evidence_binding_invalid"):
        audit.summarize(packet, path)


async def test_uncertain_alignment_has_no_automatic_correct_credit(packet):
    value = alignment_review(packet)
    value["items"][0]["relations"][0]["relation"] = "uncertain"
    lock(packet, value)
    path = packet / "evidence-review.json"
    audit.save_new(path, evidence_review(packet))
    summary = audit.summarize(packet, path)
    group = next(g for g in summary["groups"].values() if g["counts"].get("relation_uncertain"))
    assert group["counts"]["gold"] == group["counts"]["predicted"] == 2
    assert group["joint_label"]["recall"]["value"] == .5


def test_atomicity_relations_partition_without_many_to_one_credit():
    packet = {"items": [{"item_id": "item", "gold_claims": [{"id": "a"}, {"id": "b"}],
                          "predictions": [{"index": 0}]}]}
    value = {"packet_sha256": "x", "reviewer": reviewer("alignment_text_only"), "items": [
        {"item_id": "item", "relations": [{"gold_ids": ["a", "b"], "prediction_indices": [0],
          "relation": "merged", "reason": "Two independent propositions."}]}]}
    audit.check_alignment(packet, audit.AlignmentReview.model_validate(value))
    invalid = copy.deepcopy(value)
    invalid["items"][0]["relations"][0]["relation"] = "equivalent"
    with pytest.raises(ValueError, match="invalid_relation"):
        audit.check_alignment(packet, audit.AlignmentReview.model_validate(invalid))


async def test_safe_cli_failure_and_recovery_do_not_echo_raw_input(packet):
    bad = packet / "bad-review.json"
    bad.write_text("SECRET_INPUT_NOT_JSON")
    command = [sys.executable, "-m", "grounding_eval.audit", "lock-alignment", str(packet)]
    failed = subprocess.run([*command, str(bad)], capture_output=True, text=True, timeout=10)
    assert failed.returncode == 2
    assert "SECRET_INPUT" not in failed.stdout + failed.stderr
    assert json.loads(failed.stdout) == {"error_code": "audit_artifact_invalid"}
    good = packet / "good-review.json"
    audit.save_new(good, alignment_review(packet))
    recovered = subprocess.run([*command, str(good)], capture_output=True, text=True, timeout=10)
    assert recovered.returncode == 0


@pytest.mark.parametrize("valid", [True, False])
async def test_default_buffered_read_only_stderr_keeps_result_and_exit(packet, valid):
    lock(packet)
    review = packet / "evidence-review.json"
    audit.save_new(review, evidence_review(packet))
    if not valid:
        review.write_text("SECRET_AUDIT_INPUT")
    code = """
import os, sys
fd = os.open(os.devnull, os.O_RDONLY)
os.dup2(fd, 2)
os.close(fd)
from grounding_eval.audit import main
raise SystemExit(main())
"""
    result = subprocess.run([sys.executable, "-c", code, "summarize", str(packet), str(review)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == (0 if valid else 2)
    value = json.loads(result.stdout)
    assert bool(value.get("groups")) is valid
    assert "SECRET_AUDIT_INPUT" not in result.stdout + result.stderr


def test_audit_rejects_duplicate_json_fields_and_nonfinite_numbers(tmp_path):
    path = tmp_path / "bad.json"
    for content in ('{"label":"incorrect","label":"correct"}', '{"score":NaN}'):
        path.write_text(content)
        with pytest.raises(ValueError):
            audit.read(path)
