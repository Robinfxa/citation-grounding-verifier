"""Frozen gold annotations and deterministic structural validation."""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, StrictStr, ValidationError, model_validator

from grounding.contracts import (
    MAX_CLAIMS,
    VERDICTS,
    Citation,
    StrictModel,
    Verdict,
    VerifyRequest,
)
from grounding_eval.provenance import AnswerAnchor, Provenance, strict_json, verify_manifest

CATEGORIES = ("supported", "subtle_distortion", "extrinsic", "synthesis")
DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "datasets" / "main.jsonl"
LEGACY_DATASET = DEFAULT_DATASET.parent / "legacy" / "main-v1.jsonl"
SCHEMA_VERSION = "2"


def normalize(text: str) -> str:
    """Only whitespace is normalized; punctuation, case and numbers remain intact."""
    return " ".join(text.split())


class DatasetError(ValueError):
    """Safe codes only: input lines and validation payloads never reach diagnostics."""


class GoldClaim(StrictModel):
    id: StrictStr = Field(min_length=1)
    claim_text: StrictStr = Field(min_length=1)
    aliases: list[StrictStr]
    verdict: Verdict
    evidence_sets: list[list[Citation]]
    rationale: StrictStr = Field(min_length=1)
    answer_anchor: AnswerAnchor | None = None

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if any(not value.strip() for value in [self.id, self.claim_text, self.rationale]):
            raise ValueError("blank_gold_field")
        if any(not alias.strip() for alias in self.aliases):
            raise ValueError("blank_alias")
        if (self.verdict == "UNSUPPORTED") != (not self.evidence_sets):
            raise ValueError("gold_evidence_shape")
        if any(not group for group in self.evidence_sets):
            raise ValueError("empty_evidence_group")
        return self


class Case(StrictModel):
    id: StrictStr = Field(min_length=1)
    family_id: StrictStr = Field(min_length=1)
    split: Literal["dev", "test", "diagnostic"]
    category: Literal["supported", "subtle_distortion", "extrinsic", "synthesis", "edge"]
    tags: list[StrictStr]
    provenance: Provenance
    context_passages: list[StrictStr]
    generated_answer: StrictStr
    gold_claims: list[GoldClaim] = Field(max_length=MAX_CLAIMS)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        VerifyRequest(context_passages=self.context_passages, generated_answer=self.generated_answer)
        if not self.id.strip() or not self.family_id.strip():
            raise ValueError("blank_case_id")
        if (self.split == "diagnostic") != (self.category == "edge"):
            raise ValueError("diagnostic_split_mismatch")
        claim_ids: set[str] = set()
        aliases: dict[str, int] = {}
        for number, claim in enumerate(self.gold_claims):
            if self.provenance.kind == "real_source" and claim.answer_anchor is None:
                raise ValueError("real_source_requires_answer_anchor")
            anchor = claim.answer_anchor
            if anchor is not None and (anchor.end > len(self.generated_answer)
                                      or self.generated_answer[anchor.start:anchor.end] != anchor.quote):
                raise ValueError("answer_anchor_not_verbatim")
            if claim.id in claim_ids:
                raise ValueError("duplicate_claim_id")
            claim_ids.add(claim.id)
            for text in [claim.claim_text, *claim.aliases]:
                key = normalize(text)
                if key in aliases:
                    raise ValueError("overlapping_or_duplicate_alias")
                aliases[key] = number
            for group in claim.evidence_sets:
                seen = set()
                for citation in group:
                    if citation.index >= len(self.context_passages):
                        raise ValueError("gold_index_out_of_range")
                    if citation.quote not in self.context_passages[citation.index]:
                        raise ValueError("gold_quote_not_verbatim")
                    key = (citation.index, citation.quote)
                    if key in seen:
                        raise ValueError("duplicate_gold_evidence")
                    seen.add(key)
        return self


def validate_cases(cases: list[Case], *, main: bool = False) -> dict:
    ids: set[str] = set()
    families: dict[str, str] = {}
    for case in cases:
        if case.id in ids:
            raise DatasetError("duplicate_case_id")
        ids.add(case.id)
        if case.family_id in families and families[case.family_id] != case.split:
            raise DatasetError("family_crosses_splits")
        families[case.family_id] = case.split
    if not cases:
        raise DatasetError("empty_dataset")
    counts = Counter((case.split, case.category) for case in cases)
    if main and all(c.provenance.kind == "original_fixture" for c in cases) and counts != Counter({(s, c): n for s, n in [("dev", 2), ("test", 6)] for c in CATEGORIES}):
        raise DatasetError("main_layout_must_be_8_dev_24_test_four_equal_categories")
    return {
        "cases": len(cases),
        "families": len(families),
        "splits": dict(sorted(Counter(case.split for case in cases).items())),
        "categories": dict(sorted(Counter(case.category for case in cases).items())),
        "claims_by_split": {
            split: {v: sum(g.verdict == v for c in cases if c.split == split for g in c.gold_claims)
                    for v in VERDICTS}
            for split in sorted({case.split for case in cases})
        },
    }


def load_dataset(path: Path = DEFAULT_DATASET, *, main: bool = False) -> list[Case]:
    try:
        cases = [Case.model_validate(strict_json(line))
                 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError) as exc:
        raise DatasetError("dataset_unreadable") from exc
    except (ValueError, TypeError, ValidationError) as exc:
        raise DatasetError("dataset_schema_invalid") from exc
    validate_cases(cases, main=main)
    if any(case.provenance.kind == "real_source" for case in cases):
        try:
            verify_manifest(path, cases)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise DatasetError("dataset_manifest_invalid") from exc
    return cases


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
