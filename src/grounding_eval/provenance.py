"""Typed source bindings; all offsets refer to decoded UTF-8 Unicode characters."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from grounding.contracts import StrictModel

if TYPE_CHECKING:
    from grounding_eval.dataset import Case

Nonblank = Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]
SHA256 = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
Split = Literal["dev", "test", "diagnostic"]
Category = Literal["supported", "subtle_distortion", "extrinsic", "synthesis", "edge"]


class LegacyProvenance(StrictModel):
    kind: Literal["original_fixture"]
    authorship: Literal["agent_authored"]
    language: Literal["en"]
    fictional: StrictBool

    @model_validator(mode="after")
    def fictional_fixture(self) -> Self:
        if not self.fictional:
            raise ValueError("fixture_must_be_fictional")
        return self


class Generator(StrictModel):
    kind: Literal["model", "human", "program"]
    name: Nonblank
    version: Nonblank


class RealSourceProvenance(StrictModel):
    kind: Literal["real_source"]
    fictional: StrictBool
    language: Literal["en"]
    origin: Literal["natural_response", "generated_from_real_source", "controlled_mutation"]
    source_ids: list[Nonblank] = Field(min_length=1)
    generator: Generator
    annotation_version: Nonblank

    @model_validator(mode="after")
    def real_source(self) -> Self:
        if self.fictional or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("invalid_real_source_provenance")
        return self


Provenance = Annotated[LegacyProvenance | RealSourceProvenance, Field(discriminator="kind")]


class AnswerAnchor(StrictModel):
    quote: Nonblank
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def nonempty_range(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.quote):
            raise ValueError("invalid_answer_anchor_range")
        return self


class Source(StrictModel):
    id: Nonblank
    family_id: Nonblank
    url: Nonblank
    revision: Nonblank
    license: Nonblank
    license_path: Nonblank
    license_sha256: SHA256
    raw_path: Nonblank
    raw_sha256: SHA256

    @model_validator(mode="after")
    def safe_url(self) -> Self:
        url = urlsplit(self.url)
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError("invalid_source_url")
        return self


class LayoutEntry(StrictModel):
    split: Split
    category: Category
    cases: StrictInt = Field(ge=1)


class PassageMap(StrictModel):
    case_id: Nonblank
    passage_index: StrictInt = Field(ge=0)
    source_id: Nonblank
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(gt=0)
    text_sha256: SHA256

    @model_validator(mode="after")
    def nonempty_range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("invalid_passage_range")
        return self


class Manifest(StrictModel):
    format_version: StrictInt = Field(ge=2, le=2)
    schema_version: Literal["2"]
    dataset_version: Nonblank
    annotation_version: Nonblank
    dataset_file: Nonblank
    dataset_sha256: SHA256
    layout: list[LayoutEntry] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    passage_maps: list[PassageMap] = Field(min_length=1)


def strict_json(text: str):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate_json_key")
            value[key] = item
        return value

    def invalid_constant(_):
        raise ValueError("invalid_json_constant")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def manifest_path(dataset_path: Path) -> Path:
    return dataset_path.with_suffix(".manifest.json")


def relative_file(root: Path, name: str) -> Path:
    """Reject lexical traversal and symlink escapes before touching source bytes."""
    path = PurePosixPath(name)
    if (path.is_absolute() or "\\" in name or ":" in name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("unsafe_source_path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("unsafe_source_path")
    return resolved


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_manifest(dataset_path: Path, cases: list[Case]) -> Manifest:
    """Validate the full declared population and every raw/license/passage binding."""
    path = manifest_path(dataset_path)
    manifest = Manifest.model_validate(strict_json(path.read_text(encoding="utf-8")))
    root = path.parent
    if (relative_file(root, manifest.dataset_file) != dataset_path.resolve()
            or digest(dataset_path.read_bytes()) != manifest.dataset_sha256):
        raise ValueError("dataset_manifest_hash_mismatch")
    layout = {(entry.split, entry.category): entry.cases for entry in manifest.layout}
    if (len(layout) != len(manifest.layout)
            or Counter((case.split, case.category) for case in cases) != Counter(layout)):
        raise ValueError("dataset_manifest_layout_mismatch")
    sources = {source.id: source for source in manifest.sources}
    if len(sources) != len(manifest.sources):
        raise ValueError("duplicate_source_id")
    texts, source_families = {}, {}
    for source in manifest.sources:
        # Mirrors and byte-identical document versions cannot invent independent
        # families, even if their source IDs and URLs differ.
        for identity in (("bytes", source.raw_sha256), ("url", source.url)):
            if identity in source_families and source_families[identity] != source.family_id:
                raise ValueError("source_family_alias_mismatch")
            source_families[identity] = source.family_id
        raw = relative_file(root, source.raw_path).read_bytes()
        license_bytes = relative_file(root, source.license_path).read_bytes()
        if (digest(raw) != source.raw_sha256 or digest(license_bytes) != source.license_sha256
                or not license_bytes.strip()):
            raise ValueError("source_or_license_hash_mismatch")
        texts[source.id] = raw.decode("utf-8")
        license_bytes.decode("utf-8")
    mappings = {(m.case_id, m.passage_index): m for m in manifest.passage_maps}
    expected = {(case.id, index) for case in cases for index in range(len(case.context_passages))}
    if len(mappings) != len(manifest.passage_maps) or set(mappings) != expected:
        raise ValueError("passage_mapping_population_mismatch")
    used_sources = set()
    for case in cases:
        provenance = case.provenance
        if (not isinstance(provenance, RealSourceProvenance)
                or provenance.annotation_version != manifest.annotation_version):
            raise ValueError("manifest_provenance_mismatch")
        case_sources = set()
        for index, passage in enumerate(case.context_passages):
            mapping = mappings[case.id, index]
            source = sources.get(mapping.source_id)
            if source is None or source.family_id != case.family_id:
                raise ValueError("source_family_mismatch")
            # AIDEV-NOTE: offsets are Unicode [start,end), never UTF-8 byte offsets.
            # A source slice itself constructs the passage; no unrecorded cleaning runs.
            if (mapping.end > len(texts[source.id])
                    or texts[source.id][mapping.start:mapping.end] != passage
                    or digest(passage.encode("utf-8")) != mapping.text_sha256):
                raise ValueError("source_passage_mismatch")
            case_sources.add(source.id)
        if set(provenance.source_ids) != case_sources:
            raise ValueError("case_source_population_mismatch")
        used_sources.update(case_sources)
    if used_sources != set(sources):
        raise ValueError("unused_manifest_sources")
    return manifest
