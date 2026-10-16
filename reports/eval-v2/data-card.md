# V2 development pilot data card

This is a **12-case development pilot**, not a final held-out benchmark. Schema and dataset/annotation versions are recorded in the [typed manifest](../../datasets/v2/pilot.manifest.json). The [machine-readable statistics](data-statistics.json), [author's source audit](../../datasets/v2/pilot.audit.json) and [revision history](../../datasets/v2/pilot.revisions.json) expose the underlying counts and changes. Final expansion and default-main migration are pending pilot inference/resource acceptance.

## Population and density

| Property | Historical v1 main | Revised v2 development pilot |
| --- | ---: | ---: |
| Cases | 32: 8 dev / 24 test | 12 dev / **0 test** |
| Gold facts | 68 | 126 |
| Declared source families | 32 fictional fixtures | 12 document/topic families from 3 projects |
| S / C / U facts | 28 / 18 / 22 | 110 / 10 / 6 |
| Context characters, min / median / max | 76 / 116.5 / 267 | 6,603 / 10,178 / 15,546 |
| Answer words, min / median / max | 7 / 15 / 26 | 74 / 95.5 / 135 |
| Facts per answer, min / median / max | 2 / 2 / 4 | 8 / 10.5 / 13 |

Characters are decoded Unicode code points; words use whitespace splitting. Estimated context tokens are **1,651–3,886**, computed as rounded Unicode characters divided by four. No matching provider tokenizer is used, and these are not measured input tokens. RST/Markdown/SGML markup and code examples remain in the context. Increased length and density are observable; increased model difficulty has not yet been demonstrated.

Origins are **0 natural responses, 6 generated-from-real-source answers and 6 controlled mutations**. The controlled variants retain their base answers and 15 deliberate local edits in [metadata](../../datasets/v2/pilot.metadata.json). Non-injected summaries are AI-written and may still have authoring mistakes; annotation review revised two answers before any candidate model output. Each primary category has three cases: supported, subtle distortion, extrinsic information and synthesis. Six complete answers contain only S claims. The high S share (110/126) is a limitation, not class balance implied by balanced case categories.

Two cases genuinely require multiple passage links: tar-filter inheritance (p01-c03) and PostgreSQL isolation-mode mapping (p10-c05/c06). SQLite transaction control (p02) and queue shutdown (p05) exercise mode/scope reasoning but admit sufficient single-passage proofs. Independent review corrected the original overstatement of four necessarily cross-passage cases. The pilot does not establish all final difficulty quotas, domain coverage or a representative natural-error distribution.

## Sources and reuse terms

| Project and fixed source | Cases | Included terms |
| --- | ---: | --- |
| CPython 3.13.0, `60403a5409ff2c3f3b07dd2ca91a7a3e096839c7` | 6 | Complete PSF LICENSE and documentation license/history notice |
| Rust Reference snapshot, `2dafab96d919d6ab2884488e970bf95610ff83eb` | 3 | MIT redistribution option; complete MIT and Apache-2.0 texts retained |
| PostgreSQL 17.0, `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e` | 3 | Complete PostgreSQL COPYRIGHT, permission grant and disclaimers |

See [source metadata](../../datasets/v2/source-metadata.json) for every title, pinned URL, acquisition time, raw hash, revision and selected range. [NOTICE](../../datasets/v2/NOTICE) explains excerpting and retains the required attribution. Each passage is an unchanged contiguous Unicode slice of a retained raw UTF-8 file. No hidden cleanup deletes headings, table qualifiers, examples or counterevidence. Inputs are within the existing service's passage/answer limits.

The [research review](../../docs/research/eval-v2-sources.md) examined RAGTruth, HaluEval, FActScore, ALCE and MiniCheck. This pilot does **not** claim to use their natural model-response datasets or reproduce their scores. Redistribution of all underlying news/web prose was not established by a repository code license, so the pilot uses clearly licensed documentation instead. Claims are relabeled under this project's context-only S/C/U contract, not imported from hallucination spans or binary labels.

## Annotation and evidence policy

Facts describe what the answer actually asserts. Independent properties are split; conditions, negation, numbers, subjects and version scope remain attached. A relational or conditional assertion is not fragmented merely to increase counts. Exact answer anchors may overlap when separate facts share a sentence. Supported and contradicted facts have OR-of-AND evidence alternatives with all necessary identity/scope links. Unsupported facts have empty evidence; missing information alone is not contradiction. Simple arithmetic is permitted only from explicit quantities, units and denominators, with a recorded calculation; no outside defaults are assumed.

One AI author drafted 123 facts. A non-author AI reviewer first saw passages, answers, candidate texts and anchors, but not author labels, rationale or evidence. It locked its two batches before comparison. **122/123 labels agreed; one S/U disagreement and additional scope/evidence/atomicity findings required adjudication.** This is descriptive AI agreement, not human reliability or verifier accuracy.

The [comparison](annotation-review/comparison.md) identifies the changes: explicit non-flag defaults and conversion-only scope; three atomic splits (126 final facts); necessary-condition evidence; mode headings; sufficient shorter alternatives; and removal of overstated cross-passage requirements. The [original draft](../../datasets/v2/pilot-author-draft-1.jsonl) remains byte-identical. No verifier prediction was used to make these changes. The author packet records 78 changed old claims / 81 affected new claims; [affected re-review](annotation-review/affected-review.md) passed all 81 changed claims and carried forward 45 unchanged claims by exact field equality. This post-gold check is separate from the original blind judgments. Author-package pending fields are retained as the frozen handoff state; the later review receipt records acceptance. Original locks and public-view hashes are distinguished in [publication metadata](annotation-review/publication.json).

Human review is pending. [Robin's queue](human-review.md) covers C/U boundaries, numeric/version scope, multi-passage links, atomicity and evidence economy. Actual coding-session model build, tokens and cost are unknown; the configured author/reviewer identity is `gpt-6.1-sol / max`.

## Dependence, exclusions and remaining gaps

A family represents one source-document/function-topic cluster; mirrors, overlapping excerpts and versions must remain together. All current families are **dev**. No future test data has been generated or inspected, so cross-split independence has not yet been demonstrated. The 12 families share CPython, Rust and PostgreSQL conventions; they are not 12 proven independent projects.

The deterministic within-pilot check compares all 66 pairs using sets of lowercase ASCII alphanumeric/underscore five-word shingles. It found zero exact context duplicates and maximum Jaccard **0.000895** (p10/p12). This detects some textual reuse; it does not establish semantic independence. Public source material may have appeared in model pretraining.

The source selection favors English technical documentation. Natural production answers, broader domains, a final test population, a more complete difficulty matrix and empirical strict-versus-semantic scoring analysis remain unfinished. No ambiguous draft is silently counted as validated: the original ambiguous wording and judgments stay in the review history, with the revised pilot separately versioned. The six original security/edge diagnostics remain outside this population.
