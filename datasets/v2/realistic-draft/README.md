# Realistic evaluation candidate

`main-candidate.jsonl` and its adjacent strict manifest contain 72 cases:
24 development and 48 held-out test, 48 source-document/API/topic families,
668 atomic gold claims. `main-candidate.metadata.json` binds source components,
original hashes and accepted independent AI blind/affected-review evidence.
The parent owner performs promotion and measurement. This directory includes
earlier immutable drafts too; they are not the final candidate.

The components are the unchanged 12-case pilot payload, `dev-revised-2`,
`test-first24-revised-2` and `test-second24-revised-1`. Assembly only unifies
the derived `provenance.annotation_version` to `v2-realistic-candidate-1`.
All other case fields, including all 126 inherited pilot gold claims, remain
exactly equal to those accepted components. Original pilot/v1 and historical
blind packets remain unchanged. The old pilot metadata's pending handoff
status is superseded by its later accepted affected-review evidence, without
editing that snapshot. No human signoff or measured verifier quality is claimed.

`review-evidence/publication-manifest.json` provides public documentation-only
original blind judgments, lock projections, affected acceptances and explicit
author-to-accepted differences for all sixty added cases. It distinguishes
original and published hashes and does not change the accepted candidate hashes.

Main inputs use licensed real documentation with AI-authored questions and
answers: 48 answers without controlled error insertion and 24 controlled
mutations. They are not recorded benchmark model responses. No saved verifier
predictions were used to select, author, or adjudicate these cases. The six
controlled first-batch answers with lost punctuation have an explicit versioned
punctuation-only correction; every non-injected answer remains unchanged.

For the sixty newly authored cases, the consumer input is
`Question: {question}\n\nAnswer: {answer}`. The pilot input stays unchanged. Questions
are visible AI-authored tasks and never source evidence. Answer anchors index
the full adapted Unicode string. The original unprefixed authored answers,
questions and hashes are retained in component metadata. Source passages
remain contiguous Unicode slices, with exact source IDs, revisions, hashes
and ranges in the manifest. The raw files and complete notices in this folder
make the main candidate loadable offline.

Families and source variants share one split. Source URL, raw hash and exact
passage hashes have no cross-split overlap. The recorded lexical audit found
only session-output boilerplate among its reviewed threshold flags; this does
not establish project or semantic independence. CPython, Rust, pytest and curl
appear in both splits. Public pretraining exposure and technical-domain
concentration remain limitations. Character-count/4 token estimates are
approximate and never provider usage or measured cost.

`NOTICE` lists all five upstream projects, including the inherited PostgreSQL
pilot. `auxiliary/` describes a separate fixed 12-response RAGTruth selection.
Its original full contexts/responses remain privately downloaded. The raw
acquisition rebuild and the prefix-plus-claim-gold scoring rebuild are distinct
layers, each bound to hashes. The main candidate contains no RAGTruth,
HaluEval or FActScore natural-response records and uses atomic-claim methodology
without claiming their annotations as its gold.
