## Purpose

Provide optional Jev-based verification whose confidence gates, exact evidence and bounded LLM escalation remain auditable without weakening the existing context-only report or failure-inclusive evaluation.

## ADDED Requirements

### Requirement: Explicit extraction variants
The system SHALL provide opt-in `jev_minimal` and `jev_optimized` methods. The former SHALL use deterministic sentence extraction and disclose that sentences may contain several factual propositions; the latter SHALL use answer-only LLM extraction with verbatim answer anchors. They SHALL share judgment, evidence and fallback policies. Oracle evaluation SHALL skip extraction and preserve every supplied claim's identity and multiplicity. Existing methods and the default minimal LLM method SHALL remain unchanged.

#### Scenario: Compound answer
- **WHEN** an answer says "Oak stores seven blocks and uses checksums."
- **THEN** Jev Minimal retains the rule-produced sentence without an extraction LLM call
- **AND** Jev Optimized asks an LLM to extract independently checkable assertions using only the answer
- **AND** evaluation retains merged, missing and extra claim penalties rather than crediting the sentence as automatically atomic

#### Scenario: Empty input
- **WHEN** an answer is blank
- **THEN** both methods return no claims with zero model calls
- **WHEN** context is empty but extraction produces factual claims
- **THEN** those claims are UNSUPPORTED without Jev judgment calls

### Requirement: Validated versioned typed decisions
Jev requests SHALL pin a concrete model version. Decisions SHALL have the exact requested question IDs, declared answer types, complete option sets, finite probabilities in range, a distribution summing to one within a recorded tolerance, a maximum-probability chosen option and finite in-range confidence. Missing or malformed values SHALL NOT be silently repaired, normalized or assigned confidence. The requested and returned model identities SHALL be retained; unexpected identity SHALL prevent successful evaluation under the pinned configuration.

#### Scenario: Invalid choice response
- **WHEN** a response omits a requested question, has null confidence, an unknown choice, NaN, missing probability keys or an invalid distribution
- **THEN** verification fails with a safe protocol error and preserves known usage
- **AND** it does not return unsupported claims or silently invoke a different provider

### Requirement: Full-context judgments and sufficient verbatim evidence
Final user-facing verdicts SHALL refer to the full supplied context and existing support, direct-refutation and unresolved-conflict rules. Candidate retrieval SHALL only organize citations, never define the universe in which support is judged. Non-UNSUPPORTED results accepted directly from Jev SHALL have exact indexed quotations whose combined sufficiency has passed a separate quote-only semantic check; that auxiliary check SHALL NOT borrow facts, antecedents or conditions from unquoted context. LLM escalation SHALL apply the existing full-context fixed-claim judgment and evidence rules without another Jev acceptance cycle. All successful reports SHALL pass the existing literal citation guard. Uncertain or inadequate candidate evidence SHALL trigger escalation, not a fabricated quotation or a changed factual label. Machine-selected reasons SHALL be disclosed as templates, not generated reasoning traces.

#### Scenario: Antecedent missing from candidate
- **GIVEN** a source says "Cedar Relay pauses at noon. It resumes at one."
- **WHEN** the proposed citation contains only "It resumes at one." for a claim naming Cedar Relay
- **THEN** existence alone does not authorize success; the evidence check must establish the referent using only the quoted evidence or route the claim to LLM escalation

#### Scenario: Joint evidence and conflicts
- **WHEN** a claim requires a link in passage 0 and a fact in passage 1
- **THEN** the evidence path can retain both exact quotations, or escalate when its bounded candidates are insufficient
- **WHEN** equally scoped passages conflict
- **THEN** an accepted result is UNSUPPORTED with a conflict explanation and no citations, without selecting a convenient source by order

### Requirement: Confidence is routing metadata
The system SHALL keep candidate labels, distributions, confidence gates and final result origins distinct. A low score SHALL express operational abstention, not missing evidence. Acceptance SHALL require every relevant semantic gate to pass its recorded threshold; parser tolerance SHALL NOT allow a returned confidence to bypass a lower score derived from the documented formula. Both original and derived scores SHALL remain distinguishable. Scores SHALL NOT be multiplied or represented as calibrated correctness probabilities. Candidate-selection confidence SHALL NOT be treated as proof of candidate completeness. Thresholds and question/candidate policy versions SHALL be frozen for each run.

#### Scenario: Uncertain supported candidate
- **GIVEN** a recorded label threshold of 0.8
- **WHEN** Jev selects SUPPORTED with confidence 0.6
- **THEN** the claim is routed for LLM judgment, without returning the candidate label or changing it to UNSUPPORTED
- **AND** any final LLM result has no invented Jev confidence

### Requirement: One bounded escalation over fixed claims
Uncertain or evidence-incomplete claims SHALL be grouped into at most one logical LLM judgment batch using their original IDs/texts and the complete original context. The LLM SHALL judge independently of Jev's candidate verdicts. Validated returned IDs SHALL exactly cover that batch, and accepted Jev results SHALL retain their identities when merged. Extraction, Jev, escalation, repair and transport retry attempts SHALL share one deadline and total attempt cap. No confidence resampling loop, recursive fallback or hidden retry is permitted.

#### Scenario: Escalation changes or loses claims
- **WHEN** fallback omits, duplicates or rewrites a fixed claim, or fabricates a quote
- **THEN** its output is rejected under finite repair limits
- **AND** failure after those limits fails the entire request, preserving all requested evaluation denominators

#### Scenario: Escalation unavailable or exhausted
- **WHEN** a claim requires escalation but that path is explicitly disabled
- **THEN** the request returns a safe `confidence_unresolved` operational error rather than a partial success
- **WHEN** escalation is configured but lacks credentials, exceeds a budget or times out
- **THEN** the corresponding configuration, budget or timeout error is retained with the routing reason and known usage
- **AND** no additional provider call occurs after exhaustion or cancellation

### Requirement: Mixed-provider accounting and compatibility
New Jev records SHALL retain per-attempt stage/provider/model, measured usage and completeness, request attempts separately from question counts, semantic routing reasons and final claim origin. Known partial costs and unknown total costs SHALL be distinguishable; subscription usage SHALL NOT be priced using Jev rates. Saved records SHALL include effective limits and frozen policy identities. Existing artifacts SHALL remain immutable and keep fixed-source replay. Public successful HTTP JSON SHALL retain its existing fields.

#### Scenario: Subscription fallback
- **WHEN** one operation uses paid Jev requests and a Codex subscription fallback
- **THEN** the Jev portion can have a price-snapshot-based cost, while the whole-operation dollar cost remains unknown
- **AND** all calls and elapsed time remain included

### Requirement: Bounded experiments and confidence validation
Real calls SHALL require user-supplied local credentials, separately explicit total/per-provider attempt limits and a declared spending policy; previous Codex pilot allowance SHALL NOT authorize this experiment. The attempt limits SHALL be enforced before calls. A policy that only enforces attempts SHALL disclose that dollar costs are measured or unknown, not bounded by a hard monetary limit. Unsupported hard-dollar-limit requests SHALL fail before inference rather than be recorded as applied. Threshold development SHALL use development data only. Reports SHALL distinguish automatic coverage/conditional error, fallback outcomes, full-population false-support and failure-inclusive quality, extraction quality, evidence sufficiency, latency and provider costs. Missing and unattempted jobs SHALL retain denominators. Mock responses SHALL never establish live calibration, speed or cost.

#### Scenario: Unsupported monetary ceiling
- **WHEN** a run requests a hard dollar cap that the adapter/runtime cannot enforce
- **THEN** preflight rejects the unsupported policy without any provider invocation
- **AND** no recorded price snapshot or requested cap is presented as an effective spending guard

#### Scenario: Choosing a threshold
- **WHEN** development distributions are replayed at different thresholds
- **THEN** the report can describe automatic-decision coverage and observed errors
- **AND** it cannot invent unobserved fallback outcomes or claim whole-pipeline cost at an unexecuted threshold
- **AND** held-out labels, aliases and prompts remain untouched

### Requirement: Private diagnosable routing
Local logs SHALL expose safe correlation, stage, routing reason, duration, attempt counts and terminal error without source text, answers, quotations, credentials or raw provider bodies. For a probability-sum rejection after option keys and individual values are validated, the first failure event SHALL include bounded finite numeric aggregates: option count, the exact computed sum, signed deviation from one and the applied tolerance. These aggregates SHALL NOT include question IDs, option names or individual probabilities. Malformed diagnostic arguments SHALL be omitted without changing consumer behavior. Detailed confidence artifacts SHALL be retained only in explicitly requested evaluation output. Success, a key failure and subsequent recovery SHALL have independent local consumer-level verification before runtime acceptance.

#### Scenario: Low-confidence fallback timeout
- **WHEN** fallback times out after a valid uncertain Jev decision
- **THEN** logs identify the escalation reason and failed stage while excluding payload text
- **AND** a later independent request remains usable


#### Scenario: Numeric probability-sum diagnosis
- **GIVEN** two valid probability values of 0.4 and 0.5, with sum tolerance 0.001 and local diagnostics enabled
- **WHEN** the native response fails its sum validation
- **THEN** one correlated failure event records option count 2, sum 0.9, signed deviation approximately -0.1 and tolerance 0.001 without rounding away the deviation
- **AND** the public error remains provider_protocol_error, known usage is preserved, and no LLM fallback is dispatched
- **AND** a subsequent valid request succeeds, while disabled diagnostics or a broken log sink preserve the same public outcomes

#### Scenario: Diagnostic fields cannot carry payloads
- **WHEN** numeric diagnostic inputs contain strings, bools, nonfinite values, containers, out-of-range values or appear on another failure reason
- **THEN** the numeric detail is omitted safely without emitting supplied content or replacing the consumer outcome
