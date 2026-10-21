# Dataset versions

| Asset | Purpose | Current status |
| --- | --- | --- |
| `v2/pilot.jsonl` + `v2/pilot.manifest.json` | Dense answers over frozen licensed documentation | Development pilot; no final test population or LLM result yet |
| `v2/pilot-author-draft-1.jsonl` | Original author draft retained for annotation comparisons | Historical input, not the revised pilot |
| `legacy/main-v1.jsonl` | Byte-identical original main dataset | 32 fictional cases / 68 facts; frozen |
| `main.jsonl` | Default main input | Still v1; switches only after v2 pilot/resource acceptance and final split freeze |
| `diagnostic.jsonl` | Six safety and edge cases | Separate `diagnostic` split; excluded by `--split all` |

Use the explicit pilot path for new work. See the [v2 data card](../reports/eval-v2/data-card.md) for measured composition, licenses, annotation disputes and limitations, and the [current experiment status](../reports/eval-v2/README.md) for unfinished work.

## Real-source representation

Each real-source case records its source IDs, family, origin (`natural_response`, `generated_from_real_source`, or `controlled_mutation`), generator and annotation version. Gold claims have exact answer anchors with Unicode code-point offsets, start inclusive and end exclusive. Overlapping sentence anchors are allowed when separate facts share the sentence. The public HTTP request remains unchanged.

A neighboring typed manifest binds the JSONL bytes, layout, versions, source revision/URL, raw text and license hashes, and every passage's exact raw Unicode slice. Paths stay inside the dataset directory. Unknown fields, mismatched hashes, invalid anchors/quotes, cross-split families and identical sources disguised as different families are rejected. This verifies recorded relationships, not semantic truth or all possible near-duplicates.

Raw reStructuredText/Markdown/SGML is retained. No hidden cleanup removes qualifiers, tables or code examples. Full upstream notices and excerpt/change explanations are in [v2/NOTICE](v2/NOTICE). Token counts use a named estimate where the matching provider tokenizer is unavailable; estimates are not measured provider usage.

The pilot is authored and reviewed by AI. The reviewer locked judgments before seeing author labels, then compared and requested corrections. [Original judgments, disagreements and publication hashes](../reports/eval-v2/annotation-review/README.md) remain available. Human review is pending. Metadata, labels and review notes never enter the end-to-end verifier payload.

## Historical v1 annotation notes

`legacy/main-v1.jsonl` contains 32 original English cases about deliberately fictional systems: 8 development and 24 held-out cases, with 2 dev / 6 test cases in each of `supported`, `subtle_distortion`, `extrinsic`, and `synthesis`. Each case has a distinct family. There are 68 gold claims: 18 dev (8 supported, 3 contradicted, 7 unsupported) and 50 test (20 supported, 15 contradicted, 15 unsupported). The two causal examples each separately cover the supported timing fact, the unsupported occurrence of the alleged cause, and the unsupported causal relation, alongside their other original claim, giving four claims in those cases. `diagnostic.jsonl` contains separate edge cases and must not be merged into the quality leaderboard.

Run the diagnostic file explicitly into a fresh directory; saved configuration and summaries identify its split as `diagnostic`. `--split all` selects only dev/test, even if an input file also contains diagnostic cases. Model runs also require an explicit `--max-total-provider-attempts` allowance; keep diagnostics separate from quality comparisons.

```sh
uv run grounding-eval run --dataset datasets/diagnostic.jsonl --split diagnostic \
  --approaches heuristic --track both --output reports/runs/diagnostic-heuristic
```

These are **agent-authored annotations with independent agent review**. The non-author reviewer inspected all 32 cases and six diagnostics, requested three case revisions, and passed the 66-claim version before benchmark predictions were inspected. After the first development run, a source-only review identified two omitted cause-occurrence facts in the original answers. Each affirmative “A because B” also asserts that B occurred; a gold item for the causal relation alone did not separately cover that event. The current correction adds only those two instance facts as unsupported, with no evidence or aliases; no predictions were read to author this correction. Contexts, answers, existing gold claims and aliases are unchanged. They are not human annotations or an inter-annotator agreement study.

The corrected 68-claim main-file SHA-256 is `c9a30acf3ddb3093514a89831f7ae1d2be336f02df1d7b9143b1a01719aec1be`; targeted independent agent review passed on 2026-10-15 and this version is frozen. The review confirmed that only the two cause-event items were added, with all previous gold claims, aliases, inputs, other cases and diagnostics unchanged. The previous 66-claim hash was `90d760c1fb9cd4497e32466084db56e0534485a74a72acae08d758217a68477c`. Existing development and heuristic results retain their original dataset versions and scores. All compared methods must be evaluated on the corrected version before reporting a new comparison; old results must not be rescored in place or combined with the new version. See [dataset review and freeze](../docs/dataset-review.md) for review evidence and history. Structural validation alone cannot establish annotation correctness.

Each claim is assessed against the supplied context alone. `SUPPORTED` means the complete proposition follows; `CONTRADICTED` requires direct refutation; otherwise it is `UNSUPPORTED`. A stronger modality or a converse implication is unsupported without an explicit counterexample. Conflicting equal-scope evidence is diagnostic and maps to unsupported. Unsupported claims have no evidence. Each non-empty `evidence_sets` member is one sufficient AND-group of exact quotations; alternative groups are OR-ed. Multi-passage positive and negative examples require facts joined across passages. Missing-premise synthesis is intentionally unsupported.

Aliases are predeclared, verdict-independent text equivalents. Only whitespace is normalized when matching claim texts; no punctuation, case, number, unit, operator or negation changes are permitted. Aliases cannot overlap between gold claims. Valid unregistered paraphrases and alternate sufficient quotes may be undercounted: strict matching is an auditable conservative proxy, not a semantic entailment proof.

Do not add aliases or tune against held-out predictions. A substantive annotation correction after evaluation requires a new dataset hash, preserved historical outputs and re-evaluation of all compared approaches; any test-driven system tuning requires a fresh holdout for a new generalization claim.

This small synthetic technical-English benchmark is deliberately controlled. It does not estimate production accuracy, universal prompt-injection resistance, contamination absence, or performance on naturally generated answers. Diagnostic cases cover empty context, blank/non-factual answers, source conflicts, embedded instructions and Unicode; malformed provider outputs are tested separately in code.
