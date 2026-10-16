## Purpose

Measure context-grounded verification on dense real-source answers with auditable annotation, frozen experimental controls and explicit limits on what deterministic scores establish.

## ADDED Requirements

### Requirement: Versioned real-source inputs
The evaluator SHALL accept strictly typed legacy and real-source cases. Real-source cases MUST identify answer origin, immutable sources, document-family split, annotation version and verbatim answer anchors. The default main dataset SHALL be checked against a versioned manifest specifying its content hash, layout and source mappings. Unknown fields, invalid anchors, missing sources, altered source bytes, family leakage or layout mismatch SHALL fail validation. Sources MUST include reuse terms and a reproducible transformation into supplied passages. Gold metadata MUST NOT enter end-to-end verifier inputs.

#### Scenario: Altered source or answer anchor
- **WHEN** a v2 source file or an anchored answer span differs from its declared bytes/text
- **THEN** validation fails before inference and emits a safe error without echoing data

#### Scenario: Frozen legacy asset
- **WHEN** an existing v1 fixture is loaded explicitly
- **THEN** its original fictional provenance remains supported and its original 32-case layout remains testable
- **AND** the diagnostic split remains separate from dev/test `all`

### Requirement: Immutable historical replay
Old reports SHALL remain unchanged and SHALL be reproducible using their fixed compatible source/lockfile in an isolated copy. New reports SHALL identify schema, dataset and scorer versions separately from prompt/code fingerprints. Current replay MUST reject incompatible scoring code or damaged population, records and hashes; compatibility SHALL NOT be manufactured by changing historical fingerprints.

#### Scenario: Changed scorer
- **WHEN** a report is replayed with scoring modules different from its saved fingerprints
- **THEN** replay fails without inference or rewriting the saved records
- **AND** documented fixed-version replay remains available for the historical report

### Requirement: Explicit measurement layers
Strict headline alignment SHALL remain deterministic, verdict-blind and one-to-one. Reports SHALL show oracle per-class/macro F1, confusion, C/U-to-S false-support with its denominator, request failures, S/C evidence coverage, and end-to-end decomposition and joint scores including all gold and predictions. Omitted, unmatched and duplicated claims SHALL remain visible. Literal quote validity, gold-span coverage, semantic evidence sufficiency and quote economy SHALL be distinguished.

#### Scenario: Correct unregistered paraphrase
- **WHEN** a prediction is a valid paraphrase absent from frozen aliases
- **THEN** strict scoring retains its missing/extra consequence
- **AND** a separate semantic audit can record its equivalence without rewriting the headline score or adding test aliases

### Requirement: Preselected two-stage semantic audit
A test subset SHALL be selected before final outputs and include all compared methods. Stage-one reviewers SHALL see answer and claim texts without method identities, verdicts, reasoning or citations and SHALL lock alignments and extraction relations before stage two. Stage two SHALL assess label and evidence sufficiency without altering alignment for score gains. Records MUST distinguish AI and human reviewers, exposure, disagreements and unresolved items. Audit denominators SHALL refer only to the selected population; uncertain or many-to-one relations SHALL NOT silently receive full credit.

#### Scenario: Merged claims with opposite labels
- **WHEN** a predicted claim merges independently checkable gold propositions
- **THEN** the audit records the merge before labels are exposed and applies the frozen atomicity policy
- **AND** it does not match using the verdict that yields the best score

### Requirement: Bounded controlled experiments
Real model runs MUST have valid authorized configuration and an explicit attempt budget including retries. A frozen selection SHALL determine all requested jobs. Exhaustion or provider failure SHALL retain uncalled or failed jobs and their gold denominators. A controlled development comparison MUST hold data, annotations, scorer, provider/model, transport and parameters fixed while changing one declared factor. Final test runs MUST use a precommitted matrix/order policy and preserve every repeat rather than best-of-N.

#### Scenario: Insufficient remaining call budget
- **WHEN** the remaining run allowance cannot safely cover another model job
- **THEN** the runner records the remaining model jobs as unattempted budget failures without sending calls
- **AND** heuristic jobs can still execute and completion is not reported as fully successful

### Requirement: Family-paired repeated uncertainty
Comparisons across repeated runs SHALL preserve pairing by case and repetition, cluster all dependent measurements by source family, reject incomplete or incompatible paired populations, and report each repetition alongside pooled results. Missing usage/cost SHALL remain unknown. Dataset and annotation limitations SHALL be disclosed with measured scores.

#### Scenario: Repeated case
- **WHEN** a case appears in three predefined repeats
- **THEN** its three observations remain in the same family cluster and do not count as three independent source families

### Requirement: Traceable understandable delivery
The final report SHALL link important conclusions to frozen inputs, predictions and executable checks. It SHALL distinguish strict scores from semantic audit, natural/generated/intervention slices, source or annotation issues from verifier errors, and controlled results from uncontrolled history. The code walkthrough MUST follow real service/evaluation symbols, and interview material MUST identify human review and practice still pending.

#### Scenario: Incomplete empirical stage
- **WHEN** budget, credentials or unresolved annotation prevents the planned final measurement
- **THEN** documentation states the precise incomplete stage and preserves implemented/offline evidence without inventing model scores or human approval
