# Evaluation-v2 verification checkpoint

This change is **not complete**. Measurement infrastructure and the reviewed development pilot are delivered as a local checkpoint. The first authorized live pilot stopped on provider quota before any LLM prediction. Successful pilot measurement, controlled ablation, expansion/final freeze, held-out measurement and semantic test audit remain open. The task list retains those unchecked items.

## Evidence and scope

- Baseline: `8b0b0fe70c7a5d19c1fce14fc77cea68e233e90e`, initially clean. The legacy dataset is byte-identical; all original reports and diagnostics remain unchanged. [Four fixed-version replays](../../../reports/eval-v2/baseline-checks.json) preserved every copied artifact, including development-v1's failures.
- Strict real-source provenance, Unicode anchors, typed manifests, source snapshots, total-attempt budgets, complete populations, false-support/omission diagnostics, source-family repeat pairing and two-stage audit artifacts have offline checks and a non-author AI implementation review.
- An independent review found a real audit CLI diagnostic-sink defect: successful stdout was followed by an error JSON and exit 120. The original author reused the existing best-effort diagnostic path. Affected independent process checks passed for normal, quiet, read-only-stderr, safe error and recovery cases. No unresolved measurement implementation issue remains in that scope.
- Full offline tests, frozen installation, lint and actual consumer results are recorded in [verification.json](../../../reports/eval-v2/verification.json), with runtime and input hashes. Mocked provider-boundary tests, actual heuristic execution and actual model inference are distinguished.
- [Annotation review](../../../reports/eval-v2/annotation-review/README.md) retains locked independent judgments, disagreements and versioned corrections. It is separate from implementation review and from the future semantic audit of verifier predictions.

## Limits and unfinished gates

Robin authorized 60 pilot provider attempts, including retries/repairs. The [frozen plan and actual run](../../../reports/eval-v2/pilot-live.md) retained 72 requested jobs: 24 heuristic successes, one `quota_exhausted` model error and 47 unstarted model jobs. One attempt was charged and 59 remain. The error took approximately 3.80 seconds including authentication work; token usage and subscription cost are unknown. The user confirmed that quota had not recovered and requested preservation of the records. No LLM quality, successful-inference latency, controlled improvement, final test uncertainty or semantic audit score is claimed. The provisional 72-case plan is not declared fulfilled by a development-only pilot. The default `main.jsonl` remains v1 until final v2 acceptance.

The [human review queue](../../../reports/eval-v2/human-review.md) and [interview exercises](../../../docs/interview-self-check.zh-CN.md) remain for Robin. AI review cannot substitute for human understanding. Public-source contamination, correlated annotation and strict evidence/claim proxies remain limitations.

No authentication/provider runtime was changed or independently re-approved in this round. The earlier provider review limitation remains in the original change's verification record. No new publication, recruiter message or GitHub CI result is claimed.
