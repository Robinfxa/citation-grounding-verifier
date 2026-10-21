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

- [x] 3.1 With explicit budget and valid configuration, run the pilot and frozen development comparison; record actual resources and failure taxonomy.

  Historical quota/partial/recovery runs remain immutable at 63/150 attempts. The separately authorized [new development comparison](../../../reports/eval-v2/completion-dev-20261020/combined-analysis/summary.json) covers all 72 jobs: 71 OK and one original protocol ERROR. Its [row map](../../../reports/eval-v2/completion-dev-20261020/combined-analysis/source-row-map.json) retains original OK/ERROR rows and replaces only the 32 unattempted jobs with later measured rows. This is a failure-inclusive analytical combination, not a successful single CLI run. The parent independently ran [guarded replay](../../../reports/eval-v2/completion-dev-20261020/replay-combined.py): 72 unique mapped jobs and byte-identical summary, zero inference calls. Actual new consumption is 62/320 attempts including the two checks; unknown usage and subscription costs remain unknown. Timeouts changed before this baseline, so it is not a prompt-only comparison against historical runs. The [development findings](../../../reports/eval-v2/completion-dev-20261020/development-findings.json) separate extraction, citation scope, strict-score artifacts and operational failure.

- [x] 3.2 Run at least one one-factor development ablation, preserve controls, and record adoption/rejection with measured tradeoffs.

  [C01](../../../reports/eval-v2/ablation-20261020/README.md) adds only the prespecified Minimal end-to-end citation sentence. Three new 12-case blocks completed in the fixed order, using 36/216 attempts without retry or repair; the original control error remains in the primary comparison. Independent parent replay reproduced all 48 mapped observations and family-paired analysis. Parent adoption accepts the demonstrated condition-citation improvements and measured resource increase, with the localcontext merge, remaining antecedent gap, strict-score artifacts and small-sample limitations explicitly retained. Only this exact prompt delta is handed to the original service owner; final test has not informed the decision.
- [x] 3.3 Expand only after pilot review, resolve annotation disputes, validate family/near-duplicate separation, and freeze the final dataset, selections, methods, scorer, matrix and budget before test inference.

  Reviewed main is 72 cases / 668 claims, 24 dev / 48 test, across 48 document/topic families. Source bytes, split separation and independent annotations are recorded in the [data card](../../../reports/eval-v2/data-card.md) and linked original/projection evidence. [Final freeze](../../../reports/eval-v2/final-20261020/experiment-plan.json) binds source commit `324559dccba4624dfa803849f5fd26284c7b27f4`, the adopted prompt, data/scorer/settings, exact 48/16-case run selections, 24-case audit selections and the audit policy before inference. Parent independently reconstructed all 480 seeded jobs and accepted the 600-attempt cap and block-stop policy. Three ambiguous RAGTruth cases are excluded from the separate auxiliary scoring subset before model outcomes; main remains unchanged.

## 4. Measurement and understandable delivery

- [x] 4.1 Run the predefined final comparison and stability subset with all raw outcomes/resources retained; independently replay without provider calls.
- [x] 4.2 Complete the preselected semantic audit and publish strict/audit/slice/repeat analyses with actual representative failures and uncertainty.

  The [final main report](../../../reports/eval-v2/final-20261020/README.md) preserves 479 OK / one ERROR across 480 jobs and 400/600 measured attempts, the original full 48-case result, the fixed 16-case three-observation analysis, two locked audit batches and eight source-linked examples. The parent actually ran the public consumer from an independent source export: [acceptance](../../../reports/eval-v2/final-20261020/parent-acceptance.json) records exit 0, all 294 saved files identical, eight repeat groups and both audit batches/correction sensitivity identical, zero provider calls. Original reviewer votes remain unchanged; two confirmed errors are a separate sensitivity. Human review, strict matching/atomicity limitations and incomplete usage remain explicit. The natural-response auxiliary stays separate: 54/54 OK, 46/90 calls including one repair, and parent independent replay exited 0 with 18 private files and the public aggregate unchanged. Its exact output replay requires the original private saved run.
- [x] 4.3 Verify frozen installation, lint, complete tests and real long-input HTTP/CLI success plus safe failure/recovery in a fresh environment; independently review changed critical paths.

  [Final isolated installation](../../../reports/eval-v2/final-offline-verification.json) passed locked dependency installation in a new environment, 861 tests, lint and main validation at the exact adopted C01 runtime fingerprint. The original service owner ran [real long-development HTTP/CLI consumers](../../../reports/eval-v2/final-consumer-verification.json): 200 → safe 422 → 200, identical recovery body, two-track CLI and byte-identical report replay, four actual process exits 0, no provider calls. Parent checked the new runtime/input binding and returned evidence. Earlier independently accepted diagnostic fault probes are reused only for unchanged code; no new model-quality inference is implied.

- [x] 4.4 Update README, data card and AI use; deliver symbol-based code walkthrough, interview self-check/exercises and explicit human-review queue; verify links and prepare a reviewable local commit.

  README, data card, protocol, architecture and AI use now describe the completed main and natural-response populations, actual failures/resources, proxy limits and pending human review. The source-linked walkthrough, exercises, eight measured examples and unchecked human queue are delivered. Parent checked 337 local targets across 14 authored documents, including source-row line bounds; current lint and strict OpenSpec validation passed. The scoped branch commit contains public main artifacts and auxiliary aggregates only, with private workflow, credentials and natural news/predictions excluded. Final publication/CI outcome is recorded in the Director handoff, not inferred from these document checks.
