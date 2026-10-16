# Evaluation v2 protocol

Status: reviewed 12-case development pilot and offline measurement/consumer checks complete; explicit model-call budget pending. No v2 LLM scores, controlled ablation or final test results are available.

## Baseline and gaps

The local baseline is `8b0b0fe70c7a5d19c1fce14fc77cea68e233e90e`, with a clean working tree at task start. The old main file has 32 cases / 68 claims and SHA-256 `c9a30acf3ddb3093514a89831f7ae1d2be336f02df1d7b9143b1a01719aec1be`. Its byte-identical copy is `datasets/legacy/main-v1.jsonl`. Original reports under `reports/2026-10-15/` and the diagnostic dataset are protected from edits.

Observed gaps: provenance only permits fictional agent-authored fixtures; main validation hard-codes 8 dev / 24 test; strict one-to-one text/alias alignment misses unregistered paraphrases. OR-of-AND evidence, failure denominators, exact quotation guards and saved-artifact hash checks already exist and will be retained. The current extraction/judgment prompts already mention numbers, conditions, negation and scope; repeating these instructions is not a new optimization.

Baseline verification: 426 offline tests passed in the existing environment. An isolated archive of the fixed baseline installed with `uv sync --frozen` into a fresh virtual environment (existing dependency cache), then reproduced all four historical runs without changing any copied artifact bytes. Development-v1 still exits 2 for its preserved errors; the other three exit 0. See [machine-readable checks](baseline-checks.json). This verifies engineering/replay behavior, not semantic benchmark validity.

The old 0.98/0.96 end-to-end joint-label F1 values describe v1 only. Scores across changed data or scoring versions are not estimates of verifier improvement.

## Planned sequence

1. **Pilot:** 12 development cases from real redistributable sources. Check complete assertions, context-only S/C/U labels, exact evidence, answer anchors, meaningful multi-passage reasoning and non-author review before expanding. A data author is separate from the prompt optimizer.
2. **Dataset migration:** typed provenance and source mappings; manifest-validated layout; legacy fixtures explicitly named by old tests. Unknown fields remain errors. Raw sources, license notices and deterministic passage construction are retained.
3. **Development measurement:** all three methods, both tracks. Diagnose annotation, extraction/scope, strict-alignment, judgment, evidence and operational failures separately. Oracle/end-to-end differences are diagnostic, not a causal decomposition.
4. **Controlled experiment:** choose at most two hypotheses using development evidence. At least one comparison changes only one defined factor while data, annotations, model, provider, transport, parameters and scorer are fixed. Adopt or reject it on documented quality/resource tradeoffs.
5. **Freeze:** hashes bind the data, source groups, splits, annotation policy, scorer, prompt, parameters, run matrix, audit selections and budget/stop rules before any final test inference.
6. **Final measurement:** same provider/model/limits, recorded seeded order, all failures retained. Proposed resource-limited design: one full test comparison and a preselected 16-case subset measured three times in total, counting its observations in the full run as repetition 1. This proposal is finalized only after the pilot and explicit call budget.
7. **Audit and delivery:** independent replay; separately bounded semantic audit; source-family paired uncertainty; actual failure examples; clean environment, public CLI/HTTP checks; concise report and code/interview guides.

## Dataset and review rules

The provisional target is 72 cases (24 dev / 48 test), at least 36 source families, and roughly 400–700 atomic claims. These are design targets, not acceptance by count: pilot quality or a confirmed resource limit can justify a smaller population before freezing. Most contexts should be about 800–4,000 estimated text tokens and answers 6–12 assertions. Word/character measurements and a named estimate are kept separate from actual provider usage. At least about one third should require a real cross-passage relation or scope resolution.

Origins distinguish natural responses, AI answers generated from real documents and controlled mutations; the actual proportions will be reported. Clear source reuse terms take precedence over claiming use of a named benchmark. A code repository license alone does not establish permission to republish third-party news. Public-document pretraining contamination and correlated AI annotation remain limitations.

Source families, document versions, mirrors and overlapping excerpts stay on one side of the split. The prompt optimizer sees only development material before the final freeze. Non-author label review should initially hide author verdicts/rationales, lock judgments, then record disagreements and adjudications. Human review remains pending. Unresolved items are excluded or retained outside the scored population.

## Measurement policy

Strict scoring remains deterministic, verdict-blind and one-to-one, with omissions, extras, duplicates and operational failures retained. Report oracle macro F1, confusion, false-support rate and evidence coverage; end-to-end decomposition and joint label/evidence scores; exact cases as a secondary measure. Literal quote validity, gold-span coverage, semantic sufficiency and quote economy are distinct.

A stratified subset of up to 24 test cases is selected before test outputs for all three methods. Semantic audit stage 1 shows answer, gold claim texts and shuffled anonymous prediction texts only; methods, verdicts, reasoning and citations are hidden. Alignments and extraction relations are locked before stage 2 assesses labels/evidence. Merges, splits and scope loss do not receive automatic full credit. Results apply only to the audited subset. No automatic LLM judge or post-test aliases are introduced. Style can still weaken name blinding.

Repeated measurements remain attached to the same source family in paired resampling; neither claims nor repeat runs are new independent sources. Confidence intervals crossing zero indicate unclear differences. No best-of-N, significance-driven repeats, hidden fallbacks or inferred zero costs.

## Resources and authorization

The existing authorized route is Codex / `gpt-6.1-sol`. A pilot allowance of at most 60 provider attempts (including retries) has been requested; no v2 inference starts until explicit budget confirmation. A final budget will follow measured pilot consumption. The Codex output-token request is recorded as not applied, with effective limit unknown; time, byte and attempt limits are separate.

Data authoring/review by coding sessions and benchmark inference are reported separately. Coding-session usage is not available as measured benchmark tokens. Authentication and streaming are outside this change. Private instructions and correspondence are not published; no recruiter message is sent.

## Current checkpoint

The revised pilot has 12 dev cases / 126 facts, with final dataset SHA `701fe4bf85bb745824d460399b6dd6efd8302856e48cea4e751bb09f8ca040df`. The [non-author follow-up](annotation-review/affected-review.md) accepted 81 affected claims; 45 unchanged claims retain their original review by exact field equality. Its author handoff metadata remains unchanged, including the then-pending re-review state. Human review is still pending. No future test content has been generated.

[Offline acceptance](verification.json) passed from a clean source export: frozen dependency installation, 510 tests, lint, actual pilot CLI/HTTP paths, and byte-identical replay of the 24-job heuristic run. [Current results and unfinished work](README.md) distinguish those observations from the unrun LLM comparison. The provisional final population, optimization hypotheses and test selections have not been frozen. The pilot budget question remains unanswered; no resource-limited scope reduction or budget approval is inferred from elapsed time.
