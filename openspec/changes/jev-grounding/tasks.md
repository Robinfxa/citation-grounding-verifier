## 1. Optional typed-decision skeleton

- [ ] 1.1 Confirm native authentication/error/usage shapes from fixed official SDK source, then implement the bounded single-attempt Jev adapter and strict Choice validation. Verify mocked HTTP success, version drift, malformed/missing confidence, parser-tolerance threshold crossings, duplicate IDs, usage preservation and safe failures; record the still-unverified live boundary.
- [ ] 1.2 Add opt-in method configuration and the two extraction paths, reusing existing prompts/validators without altering old behavior. Verify through actual service entry points that Minimal makes no extraction call, Optimized receives answer-only data, oracle claims retain identity/multiplicity, and blank/empty-context cases obey the spec.

## 2. Evidence and bounded escalation

- [ ] 2.1 Implement versioned exact-offset windows/bundles, full-context relation/reason decisions and question-local quote-only checking. Verify Unicode, overlapping spans, antecedents, cross-passage evidence, conflicts, missing candidates and input bounds; retain failed evidence as escalation rather than U.
- [ ] 2.2 Add independent fixed-ID LLM fallback and the shared deadline/attempt accounting across all stages. Verify low-confidence success, disabled fallback, fallback ID/quote defects, repair exhaustion, cancellation and timeout through actual consumers; assert no confidence resampling or calls after the global cap.

## 3. Reproducible mixed-provider evaluation

- [ ] 3.1 Add explicit new-format Jev records, stage/model/usage attribution and confidence/routing artifacts with allowlisted logs. Verify Jev-plus-Codex yields a known Jev subtotal and unknown whole cost, missing usage stays unknown, legacy serialization stays unchanged, and fixed-source historical replay retains all artifacts.
- [ ] 3.2 Expose both approaches in the existing CLI and report automatic coverage/error, fallback outcomes, failure-inclusive quality, extraction/evidence measures and complete workflow resources. Verify offline replay and threshold sweeps do not invent unobserved fallback results, incompatible policies/models are rejected for controlled comparisons, and ERROR/NOT_RUN retain full denominators.

## 4. Acceptance and real experiment

- [ ] 4.1 Complete focused tests, lint and cross-boundary regressions; obtain non-author source review plus fresh local HTTP/CLI success, escalation failure and recovery probes under the project's logging contract. Save exact evidence scope and state explicitly that substituted provider responses do not establish live quality or speed.
- [ ] 4.2 After local Jev credentials, explicit LLM configuration and a new provider-attempt/spending budget are supplied, freeze and run a small stop-on-error real smoke. Verify returned 1.14 identity, response precision/usage, question-local evidence behavior, both extraction paths and actual end-to-end outcomes; report actual consumption before requesting any larger run budget.
- [ ] 4.3 With separately authorized measurements, run development calibration, freeze the chosen policy and report complete latency/cost/quality with uncertainty. Keep held-out inputs and aliases untouched, avoid treating oracle sampling differences as extraction gains, and leave unavailable empirical stages uncompleted. Update README/AI_used/architecture only to reflect delivered and actually verified behavior.
