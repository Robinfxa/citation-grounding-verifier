# Evaluation v2 data card

`datasets/main.jsonl` is now the reviewed real-document population: **72 cases / 668 gold claims**, with 24 development and 48 held-out cases. The [strict manifest](../../datasets/main.manifest.json) binds the dataset, annotation version, source files, licenses and exact Unicode passage ranges. [Promotion evidence](final-20261020/main-promotion.json) confirms equality with the accepted candidate except the annotation-version field; v1 remains byte-identical at `datasets/legacy/main-v1.jsonl`.

## Population and density

| Property | Historical v1 | Current main |
| --- | ---: | ---: |
| Cases, dev / test | 8 / 24 | 24 / 48 |
| Gold claims | 68 | 668: 258 dev / 410 test |
| Document/topic families | 32 fictional fixtures | 48 from five upstream projects |
| S / C / U claims | 28 / 18 / 22 | 598 / 47 / 23 |
| Context characters, min / median / max | 76 / 116.5 / 267 | 3,905 / 8,937.5 / 15,959 |
| Gold claims per answer, min / median / max | 2 / 2 / 4 | 8 / 9 / 14 |
| Source passages, min / median / max | — | 2 / 4 / 7 |

The [machine-readable statistics](main-data-statistics.json) are computed directly from the promoted main file. Characters mean Unicode code points. Context-token estimates are **976.25–3,989.75**, median 2,234.375, calculated as characters divided by four; they are not measured provider tokens. Consumer-input whitespace word counts are 74–143, median 122, including the explicit question prefix where present. Seventy of 72 answers contain 6–12 gold facts; the other two contain 13 and 14. Markup, examples, headings and scope qualifiers remain in source passages.

The dev distribution is 242 S / 10 C / 6 U; test is 356 S / 37 C / 17 U. Case categories are 34 supported, 11 synthesis, nine subtle distortion and 18 extrinsic. Categories are authoring strata, not equal difficulty or balanced claim labels. Forty-five answers contain only S claims. The S-heavy population limits conclusions about rare C/U errors.

Origins are **0 natural responses, 48 generated-from-real-source answers and 24 controlled mutations**. Base answers and mutation history are retained in [component metadata](../../datasets/v2/realistic-draft/README.md). These are newly AI-authored tasks on real documents, not recorded production traffic. For the 60 new cases, the actual consumer sees `Question: {question}\n\nAnswer: {answer}` in `generated_answer`; questions are not evidence. The inherited 12-case pilot payload is unchanged. Answer anchors address the complete consumer string.

Four cases require substantive links across passages; scope/condition reasoning is a separate dimension. More passages or retained headings do not establish cross-passage reasoning. The original broad difficulty target is not demonstrated by length or category counts alone. Actual model outcomes and the separate semantic audit must show what the added density exposes.

## Source provenance and reuse

| Project | Fixed revision | Included permission notices |
| --- | --- | --- |
| CPython 3.13.0 | `60403a5409ff2c3f3b07dd2ca91a7a3e096839c7` | PSF LICENSE and documentation license/history |
| Rust Reference | `2dafab96d919d6ab2884488e970bf95610ff83eb` | MIT and Apache-2.0; MIT redistribution option |
| PostgreSQL 17.0 | `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e` | PostgreSQL COPYRIGHT |
| pytest 8.3.3 | `d0f136fe64f9374f18a04562305b178fb380d1ec` | MIT LICENSE |
| curl 8.10.1 | `7eb8c048470ed2cc14dca75be9c1cdae7ac8498b` | curl COPYING and per-file notices |

The [NOTICE](../../datasets/v2/realistic-draft/NOTICE), retained raw files and manifest support offline validation. Each context passage is an unchanged contiguous slice of pinned UTF-8 source. Sources are not shortened by deleting counterevidence or qualifiers. Independent source verification compared the retained raw/license assets with their pinned upstream bytes; this is provenance verification, not a legal opinion or semantic-quality guarantee.

Families group source-document/API/topic clusters. Versions, exact source URLs, raw hashes and exact passage hashes have no cross-split overlap. A lexical overlap review classified its threshold flags as pytest session-output boilerplate. The lexical thresholds can miss paraphrases and semantic dependence. CPython, Rust, pytest and curl occur in both splits, so 48 topic families are not 48 independent projects. English technical-domain concentration and public pretraining exposure remain limitations. See the [selection research](../../docs/research/eval-v2-realistic-selection.md).

## Annotation and review

Facts cover what the answer actually asserts. Conditions, negation, attribution, numbers, entities and version scope stay attached. Independent properties are intended to be split; merely relational/conditional assertions are not fragmented to inflate counts. Supported and contradicted facts use exact OR-of-AND evidence alternatives containing necessary identity and scope links. Unsupported facts have empty evidence. Missing evidence alone is not contradiction; unresolved same-scope conflict is unsupported.

The inherited pilot has [locked non-author review and affected acceptance](annotation-review/README.md): 126 final facts, 81 affected facts rechecked and 45 unchanged facts carried forward by exact equality. The additional 60 cases have [public independent-review evidence](../../datasets/v2/realistic-draft/review-evidence/README.md). Three blind batches produced 145, 275 and 245 independent judgments before exposure to the author's verdicts/evidence. Comparison, adjudication and affected re-review produced 542 accepted additional gold claims. Differences in reviewer/author counts include granularity, not just omissions. Original blind judgments, locks and revision history remain separate from later acceptance.

Public projections identify original and published hashes and any omitted private fields; a projected lock is not represented as the original lock. Reviewers were separate AI sessions configured as `gpt-6.1-sol / max`. **Human review remains pending**, and correlated AI errors remain possible. No held-out final-test output was used to change gold, aliases or prompts. [Robin's review queue](human-review.md) remains unchecked.

## Observed measurement limits

The [completed main evaluation](final-20261020/README.md) finds near-ceiling oracle classification and a severe strict-text end-to-end floor. The [fixed 24-case semantic audit](final-20261020/semantic-audit-analysis.json) resolves many paraphrases, but remains conditional on frozen gold granularity. In [E02](final-20261020/failure-examples.md), a Counter gold claim combines hashable keys, zero counts and negative counts, while the model separates them. Its split penalty is not evidence that the predictions are false; extra predictions are likewise not automatically false facts. This is an observed limitation of the intended atomicity policy, not a post-test gold revision.

Two targeted evidence-review votes were confirmed overly strict by the original AI reviewers; [original votes and a separate correction sensitivity](final-20261020/semantic-audit-adjudication.json) are retained. A scope uncertainty and a gold-span/antecedent question remain unresolved. Method style was partly recognizable during evidence review, and each item was not double-reviewed. These findings do not establish exhaustive annotation or audit correctness. Human review remains pending.

## Relation to RAGTruth, HaluEval and FActScore

The [source research](../../docs/research/eval-v2-sources.md) examined these benchmarks and related work. Main uses licensed real documentation and atomic-claim methodology; it does not claim to import their natural-response records or reproduce their benchmark scores. HaluEval binary labels and RAGTruth hallucination spans are not automatically this project's S/C/U labels.

A [separate RAGTruth auxiliary selection](../../datasets/v2/realistic-draft/auxiliary/README.md) retains 12 original model responses at a fixed upstream revision: six CNN/DM and six Recent News, with upstream spans, source IDs, model IDs and hashes. It is deliberately balanced by original error-span presence, not a prevalence estimate. Original contexts and responses are preserved privately; public metadata and reconstruction recipes avoid republishing third-party news. The repository's MIT license alone does not establish rights to the news content.

The raw acquisition recipe and actual question-prefix/claim-gold scoring recipe are different layers. Independent blind annotation locked 197 judgments before comparing the original 161 author claims. Adjudication and affected acceptance produced a 12-response / 170-claim diagnostic collection. Three whole cases have unresolved textual ambiguity and are excluded before inference; the **nine-case scoring subset has 125 claims: 111 S, two C and 12 U**, with 9–19 claims per answer. Its contexts contain 575–1,931.75 estimated character/4 tokens. Original natural responses and contexts are unchanged. The [public membership and review status](../../datasets/v2/realistic-draft/auxiliary/README.md) explain exclusions; exact reconstruction and failure probes passed independently. This purposive, ambiguity-filtered subset does not represent all RAGTruth, and two C claims provide little class-specific evidence. The [auxiliary measurement](ragtruth-20261020/README.md) is complete: 54/54 jobs succeeded, with 46 measured provider calls including one output repair and zero transport retries. Only aggregate results are public; all original natural-response inputs, predictions and logs remain private. Oracle labels are 123/125 and 122/125 correct, while strict end-to-end identities match only 8/125 and 2/125. These scores remain separate from main and do not establish general RAGTruth difficulty or faithfulness performance. The six original security/edge diagnostics also remain outside main rankings.
