# Evaluation v2: source and redistribution review

Reviewed 2026-10-16. This is a methods and source-permission review, not a dataset release or an evaluation result. No product model, provider credentials, or paid inference was used. Candidate source choices and train/dev/test assignments remain the evaluation owner's decisions.

## Findings

Use RAGTruth to inform span annotation, null handling, and source-level grouping. Its repository license does **not establish permission to republish every underlying news article, web passage, or Yelp review**. For a publicly redistributable frozen context pack, CPython documentation, the Rust Reference, and PostgreSQL documentation offer direct documentation grants, subject to the notices below.

The requested MiniCheck citation needs correction: the paper is [EMNLP 2024 main.499](https://aclanthology.org/2024.emnlp-main.499/). [ACL 2024 long.499](https://aclanthology.org/2024.acl-long.499/) is a different paper, *Focus on Your Question! Interpreting and Mitigating Toxic CoT Problems in Commonsense Reasoning*.

## RAGTruth: actual files, joins, and labels

I read and structurally audited both complete upstream JSONL files at [commit c103204b9ce28d6bbad859304bf30de72b8ed8fe](https://github.com/ParticleMedia/RAGTruth/tree/c103204b9ce28d6bbad859304bf30de72b8ed8fe). The following counts are local computations over those exact bytes, not model measurements.

| File | SHA-256 | Bytes |
| --- | --- | ---: |
| [dataset/response.jsonl](https://raw.githubusercontent.com/ParticleMedia/RAGTruth/c103204b9ce28d6bbad859304bf30de72b8ed8fe/dataset/response.jsonl) | `e4c2e4ac24fff676d8984cc61c35d791612fadc58015335d97dd632375e18073` | 21,458,735 |
| [dataset/source_info.jsonl](https://raw.githubusercontent.com/ParticleMedia/RAGTruth/c103204b9ce28d6bbad859304bf30de72b8ed8fe/dataset/source_info.jsonl) | `0dffc26ea9f3c1c3d7c7e8336b56ef1646e3cec876edffcca3c9c624d12d578b` | 15,117,971 |

The join is `response.source_id == source_info.source_id`; IDs are strings. There are 17,790 response rows and 2,965 unique source rows, exactly six responses per source, no duplicate source IDs, and no orphan responses. Response `id` identifies a response, not its source.

| Record | Actual fields and representation |
| --- | --- |
| Response | `id`, `source_id`, `model`, `temperature`, `labels`, `split`, `quality`, `response` |
| Source | `source_id`, `task_type`, `source`, `source_info`, `prompt` |
| Span label | `start`, `end`, `text`, `meta`, `label_type`, `implicit_true`, `due_to_null` |
| `Summary` context | `source_info` is a string |
| `QA` context | `source_info` is a dictionary with string `question` and **string** `passages`; passages are not a JSON list |
| `Data2txt` context | `source_info` is a dictionary; observed fields include `name`, `address`, `city`, `state`, `categories`, `hours`, `attributes`, `business_stars`, `review_info` |

These representations agree with the [upstream schema documentation](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/README.md#dataset). Preserve the supplied context separately from the generation prompt. Any passage segmentation or structured-data rendering requires an explicit, reproducible transformation; do not silently assume existing passage indexes.

| Upstream split | Responses | Distinct sources |
| --- | ---: | ---: |
| `train` | 15,090 | 2,515 |
| `test` | 2,700 | 450 |

The two source-ID sets have zero intersection. `split` lives on responses, not source records. There is no upstream `dev` value in this snapshot. Keep the upstream test boundary; derive development subsets from training sources, grouping all responses to a source together. Separate IDs alone do not establish absence of near-duplicate articles or topic overlap.

The source counts are CNN/DM 628, Recent News 315, Yelp 1,033, and MARCO 989. Quality values are `good` 17,617, `truncated` 29, and `incorrect_refusal` 144. Declare any quality filtering in advance and report exclusions rather than silently dropping failures.

All 14,289 labels satisfy Python string slicing `response[start:end] == text`. This verifies half-open character offsets against response text; it provides no evidence-source offsets. Every observed span has boolean `implicit_true` and `due_to_null`: respectively 1,928 and 1,642 values are true.

The [RAGTruth paper, §3.4](https://aclanthology.org/2024.acl-long.585.pdf), treats a span that may be true outside the context as a hallucination in its strict grounding setting; `implicit_true` marks that distinction. Therefore, do not turn such spans into context-supported positives merely because they sound factually correct. `due_to_null` marks claims produced by interpreting missing/null information as negative information. Null does not establish false, “No,” or absence of a feature. Keep these cases as explicit strata if used.

A separate structural probe found 2,181 actual JSON null values in Data2txt `attributes`. The same attributes also contain booleans, strings, and dictionaries; preserve these types when rendering the input.

RAGTruth's error spans are not a complete gold inventory of atomic claims, nor a set of supporting citations. Unmarked response text must not automatically become independently validated positive claims. Converting to eight-claim answers with exact evidence needs separate annotation and review.

## What the five primary works contribute

| Work actually read | Useful method | Limit for this evaluation |
| --- | --- | --- |
| [RAGTruth, ACL 2024](https://aclanthology.org/2024.acl-long.585.pdf) | Naturally generated RAG responses, error-span taxonomy, strict context grounding, and source-grouped splits. | Error spans do not supply complete positive claim/evidence gold. Source text has multiple upstream rights holders. |
| [HaluEval, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.397.pdf) and [official project](https://github.com/RUCAIBox/HaluEval/tree/b7253db3cdaa0ab2c382f92b26b390109174f77e) | Sampling and filtering plausible synthetic hallucinations; 30,000 task examples plus 5,000 human-annotated general responses. | Generation artifacts and binary recognition differ from complete long-answer claim extraction. Contexts originate in HotpotQA, OpenDialKG, and CNN/DailyMail. The [MIT project license](https://github.com/RUCAIBox/HaluEval/blob/b7253db3cdaa0ab2c382f92b26b390109174f77e/LICENSE) does not resolve all upstream text rights. |
| [FActScore, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.741.pdf) and [official project](https://github.com/shmsw25/FActScore/tree/f28272deffcf33efc1f1117d5479c10bb75221a9) | Decompose long generation into atomic facts and check each against a knowledge source. | Factual precision over generated facts does not measure omitted gold facts. The [implementation](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/README.md) has optional length penalty and abstention settings; freeze them if comparing. Its [MIT code license](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/LICENSE) is not a Wikipedia text license. |
| [ALCE, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398.pdf) and [official project](https://github.com/princeton-nlp/ALCE/tree/246c476a4edfc564266b7346b6e29ef4861ae937) | Separate answer correctness from citation support and irrelevant citations. Citation recall checks whether produced statements are supported by their combined cited passages. | Citation recall is not coverage of a required gold fact inventory. ASQA/QAMPARI use Wikipedia; ELI5 uses Sphere/Common Crawl. The [MIT project license](https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/LICENSE) is not a blanket copyright grant over crawled pages. |
| [MiniCheck, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.499.pdf) and [official project](https://github.com/Liyan06/MiniCheck/tree/b58b9fa69acbd1015ec970fa65dd752413a053d2) | Sentence-level document/claim support classification; counterexamples made by removing support; balanced accuracy across constituent datasets. | Binary unsupported merges missing support and contradiction; classifier output does not establish exact evidence quotes. The paper evaluates 10 datasets; this [pinned README](https://github.com/Liyan06/MiniCheck/blob/b58b9fa69acbd1015ec970fa65dd752413a053d2/README.md) describes 11 after adding RAGTruth. Keep versions distinct. Its [Apache-2.0 code license](https://github.com/Liyan06/MiniCheck/blob/b58b9fa69acbd1015ec970fa65dd752413a053d2/LICENSE) does not clear every aggregated document. |

The review did not run these packages, download model weights, or reproduce their reported scores. Reading a paper's published results is not evidence about this service's performance.

## Complete-context redistribution boundary

- **RAGTruth full context pack: not cleared by this review.** Its [MIT license](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/LICENSE) grants rights in the licensor's work, but the corpus includes third-party material. The paper identifies CNN/DailyMail, additional news, MS MARCO, and Yelp; no individual publisher grants were established here.
- **MARCO is a concrete counterexample to inferring open-text permission.** Microsoft's [dataset terms](https://github.com/microsoft/msmarco/blob/master/README.md#terms-and-conditions) limit intended use to non-commercial research, state that underlying document rights may not belong to Microsoft, and do not extend underlying intellectual-property rights. The repository's separate content/code licenses do not override that dataset-specific statement.
- **Yelp and news:** Yelp's [official support page](https://www.yelp-support.com/article/Can-I-use-data-from-Yelp-for-a-school-project?l=en_US) confirms academic use with restrictions. The full dataset agreement endpoint was unavailable during this review, so no detailed redistribution permission is asserted. No blanket CNN, Daily Mail, or Recent News publisher grant was found in the reviewed materials.
- **Wikipedia-based contexts:** a release needs its own article/revision, attribution, applicable text license, and adaptation/share-alike treatment; a benchmark's MIT code license is insufficient. This review does not approve an untraced Wikipedia extract or a mixed upstream pack.
- **LLM-AggreFact:** the anonymous dataset-card request returned HTTP 401; no credentials were requested. Its code and paper were read, but its complete dataset licensing chain was not verified. The paper also describes use of constituent datasets for research purposes. Do not relabel the aggregate as Apache-2.0 merely from MiniCheck's repository.
- A paper's own publication license does not relicense a separate dataset or the source articles discussed in it.

## Three practical sources with direct documentation grants

The following are **candidate recipes**, not adopted examples or reserved split families. I read the complete three candidate files. Counts use local `tiktoken` `cl100k_base` over the exact raw UTF-8 file, including markup. They are not provider usage or cost measurements. Canonical passage extraction must be specified, counted, and hashed separately. None requires filling the context with unrelated text to reach the target length.

| Project / immutable source | Snapshot | Raw tokens | Source SHA-256 |
| --- | --- | ---: | --- |
| [CPython `Doc/library/bisect.rst`](https://raw.githubusercontent.com/python/cpython/60403a5409ff2c3f3b07dd2ca91a7a3e096839c7/Doc/library/bisect.rst) | `v3.13.0`, commit `60403a5409ff2c3f3b07dd2ca91a7a3e096839c7` | 2,488 | `1fb2fa097a86e3bd92049f3e6b791a9bbf3bdf54a1098fcbb369d3e0e5c56a5c` |
| [Rust Reference `src/attributes/testing.md`](https://raw.githubusercontent.com/rust-lang/reference/2dafab96d919d6ab2884488e970bf95610ff83eb/src/attributes/testing.md) | commit `2dafab96d919d6ab2884488e970bf95610ff83eb`; repository snapshot, not a claimed Rust release | 1,690 | `fb218d9c5a4f35b6c2fa31ed456beabcef782c45f517ccabcbe69cfd1d6d3855` |
| [PostgreSQL `doc/src/sgml/ref/notify.sgml`](https://raw.githubusercontent.com/postgres/postgres/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/ref/notify.sgml) | `REL_17_0`, commit `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e` | 2,214 | `8b9bd78aed5e1b0fc9bb4b8553862d4f9add312139176202b2dc408391c1ee21` |

**CPython permission.** The pinned [documentation license source](https://github.com/python/cpython/blob/60403a5409ff2c3f3b07dd2ca91a7a3e096839c7/Doc/license.rst) explicitly covers software and documentation. PSF license clause 2 permits reproduction, derivatives, and distribution while retaining the agreement and PSF copyright; clause 3 requires a brief change summary for distributed derivatives. Preserve the pinned [LICENSE](https://github.com/python/cpython/blob/60403a5409ff2c3f3b07dd2ca91a7a3e096839c7/LICENSE), relevant documentation notices and authorship, and extraction/modification notes. The documentation's separate zero-clause BSD grant applies to code examples, not a replacement license for all prose.

The bisect page supports at least eight distinct fact axes: insertion-point purpose, comparison method, left/right duplicate boundaries, range bounds, search-key treatment, insertion-key treatment, insertion cost, and discarded key computations. These are authoring opportunities, not prevalidated gold claims. External pages linked by the documentation are outside this permission review.

**Rust permission.** This documentation repository includes [LICENSE-MIT](https://github.com/rust-lang/reference/blob/2dafab96d919d6ab2884488e970bf95610ff83eb/LICENSE-MIT) and [LICENSE-APACHE](https://github.com/rust-lang/reference/blob/2dafab96d919d6ab2884488e970bf95610ff83eb/LICENSE-APACHE). The MIT grant expressly includes associated documentation and permits copying, modification, and distribution with copyright and permission notices. Preserve both supplied license texts and source attribution; Apache-2.0 §4 also describes notice retention and changed-file notices. Do not substitute a generic website footer or the different Rust Book's license without checking its own source.

The testing page supports distinct rules for test-mode compilation, allowed function signatures, termination-based results, nontermination, ignored-test compilation, ignored-test execution, forced execution of ignored tests, and panic-message conditions. The raw snapshot contains an editorial TODO about duplicate `test` attributes; avoid treating that disputed point as settled compiler behavior. No Rust compiler conformance test was performed here.

**PostgreSQL permission.** The pinned [COPYRIGHT](https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/COPYRIGHT) explicitly grants copying, modification, and distribution of software **and its documentation** for any purpose. Its condition is to retain the copyright, grant paragraph, and both disclaimer paragraphs in all copies. Include that entire file in the frozen pack, rather than only the SPDX name. The [official license page](https://www.postgresql.org/about/licence/) confirms the same documentation grant.

The NOTIFY page supports conditions concerning listener/database scope, payloads, sender commit, listener transactions, duplicate folding, delivery order, queue exhaustion, and two-phase commit. A deliberately noncanonical tag-stripping probe yielded 1,211 tokens, so prose extraction is plausibly within 800–4,000; the actual selected extraction still needs its own count and hash. Do not inherit the much shorter reference pages' raw token count as a guarantee about their rendered prose.

## Freezing and split recommendations

Store project, exact commit, original path/URL, retrieval date, raw SHA-256, complete relevant license/notices, transformation description, final passage SHA-256, tokenizer name/count, and source/topic family. Retain literal source text before authoring answer paraphrases or controlled mistakes; distinguish these transformations in the manifest. Quotes must be exact substrings of the final frozen passages.

Keep a document, its alternate versions, near-duplicates, and answer variants in one split. Different topics in one project can form topic-disjoint families, but that is not project-disjoint evaluation. Count required gold facts independently of extracted claims, so omitted facts remain failures. Report support correctness, gold coverage, extra claims, evidence correctness, and failed requests separately; no single borrowed precision or citation metric establishes all of them.

Additional paths checked for the data author: the same Rust snapshot contains `src/visibility-and-privacy.md` (2,175 raw tokens), `src/destructors.md` (6,815; requires a bounded complete-section excerpt), and `src/attributes/testing.md`. In PostgreSQL `REL_17_0`, transaction isolation is in `doc/src/sgml/mvcc.sgml` (`transaction-iso` and its child sections), backups in `doc/src/sgml/backup.sgml`, and privileges in `doc/src/sgml/ddl.sgml` (`ddl-priv`). Those PostgreSQL source files greatly exceed 4,000 tokens; use complete bounded subsections and preserve both original-file and final-excerpt hashes. These paths were inspected for availability and structure; they are not eight-fact gold annotations.

## Evidence scope and remaining limits

The private working receipts contain repository revisions, hashes, structural counts, and source-length probes; no news passages or review bodies are copied into this report. Checks here establish the recorded snapshot's schema and the identified documentation grants. They do not certify every third-party dependency, every external hyperlink, future repository revisions, compiler behavior, or any newly authored gold example. Final dataset selection, legal-notice packaging, canonical extraction, human gold review, and service evaluation remain separate work.
