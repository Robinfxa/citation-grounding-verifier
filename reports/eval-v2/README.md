# Evaluation v2 — pilot checkpoint

**Status: blocked on provider quota; this is not a completed model comparison.** Robin approved a 60-attempt development pilot. Its first Codex request returned `quota_exhausted`; the runner preserved all requested jobs and stopped subsequent model calls. The user confirmed quota had not recovered and requested preservation of the records. [The saved run](pilot-live.md) used 1 attempt, leaving 59; no LLM prediction or usage total was returned.

The original benchmark's short fictional answers did not provide persuasive evidence of real-document performance. This round prepares 12 development cases / 126 facts over licensed documentation, non-author annotation review and versioned measurement tools. It preserves the old results rather than relabeling them as new evidence.

The implementation and offline checks can be inspected now. The remaining sequence is pilot inference and resource measurement, controlled development, final dataset/split freeze, held-out comparison, repeated-subset measurement and a preselected semantic audit. The proposed 72-case scope has not been replaced by a claim that 12 development cases constitute a final benchmark. `datasets/main.jsonl` remains v1 until that acceptance is complete.

A [non-author review](pilot-live-review.json) independently checked the new run's frozen inputs, complete population, quota stop, accounting and resource uncertainty. Its isolated offline replay returned the expected exit 2 and preserved all 23 run files byte-for-byte, with no network, provider or credential access. This is run-integrity verification, not model-quality validation.

## Evidence available now

| Feedback or requirement | Artifact | Evidence and boundary |
| --- | --- | --- |
| Replace short fictional material with denser real-source tasks | [Pilot and data card](data-card.md); [source research](../../docs/research/eval-v2-sources.md) | Frozen licensed documentation, exact source/answer mappings, origin labels; development only, no production-response sample |
| Establish annotation reliability before measuring | [Locked independent judgments and disagreements](annotation-review/README.md) | Non-author AI review before author-label exposure; original judgments retained; human review pending |
| Separate measurement errors from model errors | [Scorer calibration](../../tests/evaluation/fixtures/measurement-calibration.md); [audit policy](audit-policy.md) | Deterministic strict scoring plus a separate two-stage audit format; no test semantic score yet |
| Preserve versions, denominators and resources | [Evaluator](../../src/grounding_eval/runner.py); [engineering checks](verification.json) | Typed manifests, attempt reservations, complete NOT_RUN/error populations, snapshots, scorer-bound replay and family-preserving repeats tested |
| Bound actual model calls and preserve failure outcomes | [Frozen pilot plan](pilot-live-plan.json); [live-run record](pilot-live.md) | 1 quota-blocked attempt, 47 NOT_RUN model jobs, 24 successful heuristic jobs; no fabricated LLM quality or usage |
| Retain historical reproducibility | [Baseline checks](baseline-checks.json) | Fixed baseline `8b0b0fe70c7a5d19c1fce14fc77cea68e233e90e` installed in isolation; four old reports reproduced byte-for-byte |
| Provide interpretable optimization evidence | [Experiment protocol](protocol.md) | Planned, not run. No new hypothesis is adopted without dev failure evidence and a one-factor comparison |
| Prepare the author to explain the work | [Walkthrough](../../docs/code-walkthrough.zh-CN.md), [16 questions and exercises](../../docs/interview-self-check.zh-CN.md), [human checklist](human-review.md), [AI use](../../AI_used.md) | Materials prepared; Robin's own review and demonstrated understanding remain pending |

## What the current results do—and do not—show

A clean source export with no `.env`, workflow files, previous environment or caches installed the unchanged lockfile into a new virtual environment, using the existing dependency cache. The full offline suite passed **510 tests**, and lint passed. Independent measurement review exercised budget exhaustion, failure denominators, source/snapshot corruption, strict scoring, family/repeat pairing and the audit state sequence. It found and retested a diagnostic-output failure. The actual heuristic completed [24 pilot jobs](pilot-offline/summary.json) across both tracks; report replay preserved every saved byte. A real loopback HTTP request with 8,418 context characters and an eight-fact answer returned 200, invalid extra input returned a safe 422, and the subsequent valid request recovered. These are engineering and heuristic observations, not LLM quality results. [Verification](verification.json) binds them to runtime hashes and states the exact acceptance scope.

Only the deterministic heuristic produced predictions on the **development** pilot. Its scores were unchanged in the later quota-blocked run:

| Method | Oracle macro F1 | End-to-end strict joint-label F1 | Actual provider calls |
| --- | ---: | ---: | ---: |
| Heuristic | 0.0365 | 0.0614 | 0 |
| Minimal | Not run | Not run | 0 |
| Optimized | Not run | No prediction: quota error | 1 |

Heuristic oracle judgment got 7/126 labels correct and covered 1/120 non-U gold evidence groups. Its false-support rate was 0/16, which is not evidence of useful performance when most supported claims are missed. End-to-end strict decomposition matched 63/126 gold facts against 102 predictions (F1 0.5526). These observations expose the lexical baseline's limits; they do not establish LLM difficulty or justify prompt changes. All numerators, failures and resources are in the saved summary above.

Strict scoring version is `2`; schema and run format are separately versioned. The whitespace/registered-alias matching rule remains conservative. New false-support reporting uses all C/U gold claims as its denominator and shows judgment coverage/failure alongside it. Literal validity, frozen evidence-span coverage, semantic sufficiency and quote economy remain separate concepts. Unknown cost and unobserved usage are not replaced by zero.

**V2 provider attempts: 1; successful LLM predictions: 0.** Pilot LLM quality, repeated-run comparisons, controlled-ablation results and semantic test-audit scores are **not available**. The observed failure belongs to the provider/quota category; it supplies no judgment, extraction or evidence-error example. Failure-inclusive zeros in the machine report preserve denominators; they are not a measurement of model accuracy. Annotation findings in the [comparison summary](annotation-review/comparison.md) remain dataset-review findings.

The requested route remains Codex / `gpt-6.1-sol`; the failed request returned no response-model identity. The approved pilot ceiling is 60 provider attempts, including retries and repairs, with 59 remaining. An allowance is a ceiling, not a guarantee that every job finishes: the runner conservatively reserves the per-operation maximum before starting a job. Provider timeout is 30 s, operation timeout 60 s, per-operation attempt ceiling 6; requested output limit is 8,192 tokens but **not applied on Codex**, with the effective limit unknown. The pilot plan was frozen before invocation; final-experiment settings, matrix and stop rules remain pending successful resource observations.

A 12-case, three-method, two-track pilot contains 72 jobs. In an ideal successful nonempty pass, the model paths require about 60 calls (minimal oracle/end-to-end one each, optimized oracle one and end-to-end two); repairs, retries or operational errors alter consumption. This is planning arithmetic, not measured usage. Data authoring and AI review used coding sessions whose token/cost accounting is unavailable.

## Reproduce the available checks

See the root [README](../../README.md) for frozen installation, explicit pilot CLI/HTTP commands, bounded model-run syntax and the isolated historical replay command. Do not send the unfrozen future test population to a model. All new run directories must be empty.

The semantic-audit tool is accessible as `uv run python -m grounding_eval.audit --help`; it prepares and validates reviewer artifacts, not an automatic LLM judge. Final audit IDs must be selected and frozen before any final test output. Repeated comparison is the small library in [repeated.py](../../src/grounding_eval/repeated.py), with explicit shared case IDs and family clustering.

## Remaining limits and next acceptance

The pilot is entirely AI-written over public technical documentation, not naturally collected production responses. Source projects and model pretraining can introduce dependence and contamination. AI author/reviewer agreement cannot prove annotation truth. Strict scorer calibration does not eliminate paraphrase undercounting, and a longer context alone does not establish difficulty.

Before completing the round: wait for quota recovery and continue within the remaining pilot allowance; measure and diagnose successful pilot outputs; agree the later matrix budget; expand only with reliable source/family separation; run one controlled dev ablation; freeze all data, labels, methods, scorer, selections and resource limits; execute the predefined final matrix and audit; independently replay; then switch the default main dataset and replace this checkpoint with the measured report. No final dataset freeze, new CI run, public push or recruiter communication is claimed here.
