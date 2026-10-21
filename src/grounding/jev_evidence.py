"""Bounded citation proposals sliced from source offsets, never semantic judgments."""

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass
from itertools import combinations

from grounding import heuristics
from grounding.contracts import Citation

CANDIDATE_POLICY_VERSION = "unicode-overlap-windows-v1"
MAX_WINDOW_CHARS = 1_200
MAX_BUNDLE_CHARS = 2_400
MAX_WINDOWS = 8
NO_ADEQUATE_BUNDLE = "NO_ADEQUATE_BUNDLE"
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True, order=True)
class Span:
    index: int
    start: int
    end: int

    def quote(self, passages: list[str]) -> str:
        return passages[self.index][self.start:self.end]


def _sentence_spans(text: str):
    start = 0
    # Share the baseline's sentence boundaries, retaining exact Unicode offsets.
    for end in [match.start() for match in heuristics._SPLIT.finditer(text)] + [len(text)]:
        part = text[start:end]
        left = start + len(part) - len(part.lstrip())
        right = end - len(part) + len(part.rstrip())
        if left < right:
            yield left, right
        if end < len(text):
            start = heuristics._SPLIT.match(text, end).end()


def windows(passages: list[str]) -> list[Span]:
    result = set()
    for index, passage in enumerate(passages):
        sentences = list(_sentence_spans(passage))
        for first, (start, _) in enumerate(sentences):
            for _, end in sentences[first:first + 3]:
                if end - start <= MAX_WINDOW_CHARS:
                    result.add(Span(index, start, end))
    return sorted(result)


def _terms(text: str) -> frozenset[str]:
    return frozenset(_WORDS.findall(text.casefold()))


def merge_spans(spans: tuple[Span, ...]) -> tuple[Span, ...]:
    merged = []
    for span in sorted(spans):
        if merged and merged[-1].index == span.index and span.start < merged[-1].end:
            previous = merged.pop()
            merged.append(Span(span.index, previous.start, max(previous.end, span.end)))
        else:
            merged.append(span)
    return tuple(merged)


@dataclass
class Candidates:
    catalog: dict[str, Span]
    bundles: list[dict[str, tuple[Span, ...]]]
    references: list[dict[str, list[str]]]

    def visible_catalog(self, passages: list[str]) -> list[dict]:
        return [
            {"id": key, "index": span.index, "start": span.start, "end": span.end,
             "quote": span.quote(passages)}
            for key, span in self.catalog.items()
        ]

    def citations(self, claim_id: int, bundle: str, passages: list[str]) -> list[Citation]:
        return [Citation(index=s.index, quote=s.quote(passages))
                for s in self.bundles[claim_id][bundle]]


def propose(passages: list[str], claims: list[str]) -> Candidates:
    pool = windows(passages)
    terms = {span: _terms(span.quote(passages)) for span in pool}
    catalog, ids, all_bundles, all_references = {}, {}, [], []
    for claim in claims:
        wanted = _terms(claim)
        selected = heapq.nsmallest(MAX_WINDOWS, pool, key=lambda span: (
            -len(wanted & terms[span]), span.end - span.start,
            span.index, span.start, span.end,
        ))
        for span in selected:
            if span not in ids:
                key = f"w{len(ids)}"
                ids[span] = key
                catalog[key] = span
        bundles, references = {}, {}
        for parts in [(span,) for span in selected] + list(combinations(selected, 2)):
            merged = merge_spans(parts)
            if sum(span.end - span.start for span in merged) > MAX_BUNDLE_CHARS:
                continue
            key = f"B{len(bundles)}"
            bundles[key] = merged
            references[key] = [ids[span] for span in parts]
        all_bundles.append(bundles)
        all_references.append(references)
    return Candidates(catalog, all_bundles, all_references)
