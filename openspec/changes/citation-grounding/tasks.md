## 1. Research, architecture and shared foundation
- [x] 1.1 Research grounding, evaluation and structured APIs; inspect the three dossiers and record adopted choices in docs/architecture.md.
- [x] 1.2 Investigate Hermes/Codex quota access with the requested Luna 6 researcher; document the selected provider route and a reproducible boundary test.
- [x] 1.3 Implement shared strict contracts and locked packaging; verify quote/type/limit tests and a clean environment install.

## 2. Service
- [x] 2.1 Implement heuristic, minimal and optimized verifiers with fixed-ID judgments and bounded repair; verify targeted semantic-contract and scripted-provider tests.
- [x] 2.2 Implement OpenAI Responses and the selected Codex quota adapters without leaking credentials or hiding usage; verify protocol, refusal, truncation, cancellation and failure fixtures.
- [x] 2.3 Implement HTTP request limits, deadlines, safe errors and local diagnostics; verify actual HTTP success/failure and independent logging probes.

## 3. Evaluation
- [x] 3.1 Author and freeze 32 balanced original cases plus diagnostic edges, disjoint splits and aliases; pass dataset validation and non-author annotation review before inspecting test model outputs.
- [x] 3.2 Implement oracle and end-to-end scoring, failure denominators, evidence metrics and case-bootstrap intervals; pass adversarial metric tests.
- [x] 3.3 Implement reproducible benchmark/report CLI with fingerprints, usage and overwrite protection; verify actual offline consumer runs and saved-result reproduction.

## 4. Empirical comparison and delivery
- [x] 4.1 Run a real provider smoke test and all three approaches on development cases, retain failures, and justify any optimized revision with measured evidence.
- [x] 4.2 Freeze prompts and run the held-out benchmark; report quality, resource use, paired uncertainty and concrete failure cases without tuning on test outputs.
- [ ] 4.3 Complete independent implementation/diagnostic review and necessary repairs; pass lint, full tests and HTTP/CLI integration checks on the final code.
  - Final clean-clone functional checks passed: 426 tests, lint, HTTP/CLI acceptance and immutable saved-report reproduction. Service/evaluator/dataset independent checks passed, including the final evaluator corrections. The new provider increment's independent review was stopped by a platform risk check and remains incomplete; no bypass or replacement PASS is claimed.
- [x] 4.4 Write concise run instructions and measured README report; verify commands, links, artifact fingerprints and repository hygiene.
- [ ] 4.5 Prepare a reviewable local submission; after required publication authorization, create/push the public GitHub repository and verify the remote contents.

## 5. Bounded final delivery corrections
- [x] 5.1 Expose `--split diagnostic`, retain dev/test-only `all`, and verify diagnostic CLI execution and report separation without changing data or scoring.
- [x] 5.2 Record requested versus effective output-token limits accurately for each configured provider; preserve historical report reproduction.
- [x] 5.3 Default Settings and the example environment to minimal; keep explicit optimized/heuristic choices and make the quickstart order easy to follow.
- [x] 5.4 Save real minimal and optimized diagnostic runs separately from the frozen benchmark and independently check the changed evaluator behavior.
- [x] 5.5 Validate frozen installation, tests and HTTP examples from a clean clone; commit the correction and export a source-only submission archive.
