## 1. Baseline and measurement design

- [x] 1.1 Protect baseline datasets/reports and verify byte-identical legacy data plus isolated fixed-version replay.
- [x] 1.2 Review source methods/licenses and deliver a 12-case development pilot with blind non-author labels, resolved disagreements and valid source/answer mappings.

## 2. Evaluator migration

- [x] 2.1 Implement strict real-source provenance, anchors and manifest/layout validation; verify legacy fixtures, malformed source/anchor rejection and actual CLI success/failure/recovery.
- [x] 2.2 Add explicit version fields, frozen case selection and conservative total-attempt budgeting; verify complete failure denominators, unknown usage and damaged-artifact/replay rejection.
- [x] 2.3 Add false-support/extraction diagnostics, honest slices and family-paired repeat analysis; verify independent calibration examples and dependency-preserving resampling.
- [x] 2.4 Freeze and validate a two-stage semantic audit policy and packet/record format, including blinded stage-one alignment and separate evidence assessment.
- [x] 2.5 Add opt-in stop-on-model-error execution; verify no later model calls, complete NOT_RUN denominators, continued heuristic work, safe diagnostics, tampered-stop rejection and byte-identical historical replay through actual CLI consumers.

## 3. Controlled development and final population

- [ ] 3.1 With explicit budget and valid configuration, run the pilot and frozen development comparison; record actual resources and failure taxonomy.

  The original quota failure used 1 attempt; the [2026-10-20 continuation](../../../reports/eval-v2/pilot-resume-20261020.md) used 54 more, yielding five model outputs but no complete comparison. The user approved a cumulative ceiling of 150 and the [staged recovery plan](../../../reports/eval-v2/pilot-recovery-budget.md). Task 2.5 passed [independent offline acceptance](../../../reports/eval-v2/model-error-stop-verification.json). Under the [frozen plan](../../../reports/eval-v2/pilot-recovery-20261020-plan.json), both fixed recovery checks succeeded, then the full matrix stopped at its first model timeout. This sequence used eight attempts; cumulative use is 63/150, with 87 unspent. The approved failure stop blocks further calls in this sequence; no complete comparison is claimed. This task stays open.

- [ ] 3.2 Run at least one one-factor development ablation, preserve controls, and record adoption/rejection with measured tradeoffs.
- [ ] 3.3 Expand only after pilot review, resolve annotation disputes, validate family/near-duplicate separation, and freeze the final dataset, selections, methods, scorer, matrix and budget before test inference.

## 4. Measurement and understandable delivery

- [ ] 4.1 Run the predefined final comparison and stability subset with all raw outcomes/resources retained; independently replay without provider calls.
- [ ] 4.2 Complete the preselected semantic audit and publish strict/audit/slice/repeat analyses with actual representative failures and uncertainty.
- [x] 4.3 Verify frozen installation, lint, complete tests and real long-input HTTP/CLI success plus safe failure/recovery in a fresh environment; independently review changed critical paths.
- [x] 4.4 Update README, data card and AI use; deliver symbol-based code walkthrough, interview self-check/exercises and explicit human-review queue; verify links and prepare a reviewable local commit.
