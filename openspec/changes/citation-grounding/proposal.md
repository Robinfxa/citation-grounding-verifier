## Why

An LLM answer may mix grounded facts, direct contradictions, and plausible facts absent from the supplied context. Consumers need an explicit claim-level report with auditable evidence, and reviewers need a benchmark that does not reward omitted claims or conflate quote existence with entailment.

## What Changes

- Add `POST /verify` to decompose an answer, classify each atomic factual claim, and return exact source quotations with deterministic validation.
- Add bounded handling of malformed model output, upstream failures, empty contexts and non-factual answers.
- Implement a deterministic heuristic, a minimal single-call LLM verifier and an optimized LLM verifier behind one evaluation interface.
- Author a balanced benchmark with more than 20 labeled cases and fixed development/test partitions.
- Provide reproducible evaluation, transparent metrics, measured latency/usage, failure analysis, and an honest report of any unavailable live measurements.
- Complete delivery with an executable separate diagnostic split, accurate requested/effective provider limits and the measured minimal default, while preserving the frozen experiment and avoiding architecture expansion.

## Capabilities

### New Capabilities
- `grounding-verification`: Claim extraction, context-only verdict semantics, exact citation integrity, HTTP and provider failure boundaries.
- `grounding-evaluation`: Labeled dataset, comparable verification approaches, claim coverage, reproducible quality and resource reports.

### Modified Capabilities
None. The target project has no existing product code or specifications.

## Impact

New Python service and evaluation packages, tests, dataset, dependency lock, run documentation and research-backed architecture. External model access uses only explicitly configured project credentials. No database, retrieval service, external telemetry, or hosted deployment is required. Public repository creation is a separate final delivery action.
