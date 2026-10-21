from grounding.jev_evidence import (
    MAX_BUNDLE_CHARS,
    MAX_WINDOW_CHARS,
    Span,
    merge_spans,
    propose,
    windows,
)


def test_unicode_offsets_keep_original_spacing_and_contiguous_sentence_windows():
    source = "  杉树暂停。\n\t它于一点恢复！  Café e\u0301 keeps 7.\r\nLast fact.  "
    passages = [source, "Second source."]
    spans = windows(passages)
    assert Span(0, source.index("杉"), source.index("！") + 1) in spans
    assert any(span.quote(passages) == "Café e\u0301 keeps 7.\r\nLast fact." for span in spans)
    assert all(span.quote(passages) == passages[span.index][span.start:span.end] for span in spans)
    assert all(0 < span.end - span.start <= MAX_WINDOW_CHARS for span in spans)


def test_top_eight_and_at_most_36_bundles_have_stable_ties_and_no_catchall():
    passages = [f"Fact item{i}. Extra sentence. Third sentence. Fourth sentence." for i in range(12)]
    candidates = propose(passages, ["Missing claim."])
    assert len(candidates.catalog) == 8
    assert len(candidates.bundles[0]) == 36
    assert candidates == propose(passages, ["Missing claim."])
    assert all(span.end - span.start < len(passages[span.index])
               for span in candidates.catalog.values())
    assert all(sum(s.end - s.start for s in bundle) <= MAX_BUNDLE_CHARS
               for bundle in candidates.bundles[0].values())
    assert len(propose(["x" * (MAX_WINDOW_CHARS + 1)], ["x"]).bundles[0]) == 0


def test_overlap_merges_only_original_union_and_preserves_cross_source_indices():
    assert merge_spans((Span(0, 2, 12), Span(0, 8, 20), Span(1, 0, 8))) == (
        Span(0, 2, 20), Span(1, 0, 8),
    )
    assert merge_spans((Span(0, 0, 4), Span(0, 4, 8))) == (Span(0, 0, 4), Span(0, 4, 8))
    passages = ["Cedar is the relay.", "The relay resumes at one."]
    candidates = propose(passages, ["Cedar resumes at one."])
    pair = next(key for key, spans in candidates.bundles[0].items()
                if {span.index for span in spans} == {0, 1})
    citations = candidates.citations(0, pair, passages)
    assert [citation.index for citation in citations] == [0, 1]
    assert all(c.quote == passages[c.index] for c in citations)


def test_catalog_deduplicates_spans_without_merging_duplicate_claim_identities():
    candidates = propose(["Oak stores 7 blocks."], ["Oak.", "Oak."])
    assert len(candidates.catalog) == 1
    assert len(candidates.bundles) == 2
    assert candidates.references[0] == candidates.references[1]
