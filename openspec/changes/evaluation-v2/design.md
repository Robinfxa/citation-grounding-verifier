## Context

See the proposal and `reports/eval-v2/protocol.md`. The baseline evaluator uses Pydantic strict frozen cases, pure deterministic scoring, sequential saved jobs, module fingerprints and family bootstrap. The original contract is still in the unarchived `citation-grounding` change. HTTP and provider boundaries already satisfy this task's required interface.

## Goals / Non-Goals

**Goals:** make the real-source population reproducible; preserve honest strict measurement; add a reviewable semantic audit and controlled/repeated experiment evidence.

**Non-Goals:** automated LLM judging, retrieval, a framework/plugin architecture, authentication/transport changes or guaranteed optimized superiority.

## Decisions

1. **Keep the old replay environment.** A byte-identical v1 file is retained under `datasets/legacy/`. Archive baseline commit `8b0b0fe` to a scratch directory and replay copied old reports there with its lockfile. New code keeps the hash rejection guard; no dual-scorer framework is needed.
2. **Typed provenance plus a typed manifest.** Extend the existing case model with a discriminated real-source provenance variant and optional typed answer anchors that are mandatory for real-source gold. Keep raw sources and deterministic selected passage mappings. A manifest specifies layout/hash rather than hard-coded v2 numbers; legacy validation retains its explicit old layout. No arbitrary metadata dictionary bypasses validation. Dataset/schema/scorer versions have separate fields.
3. **Minimal runtime extensions.** Keep existing metrics and add false-support, missing/extra/duplicate counts and clearly labeled slices. Frozen case-ID selection and a total attempt allowance are small runner options. Before starting a model job reserve its maximum per-operation attempts; unknown stats consume that reservation. This can stop conservatively before the nominal allowance, which is preferable to exceeding it. Preserve uncalled jobs with existing safe failure codes.
4. **Separate human-readable semantic audit.** Prepare anonymous text-only packets; hash and lock reviewer stage-one mappings before revealing stage-two verdict/evidence packets. Record one-to-one equivalence, merges, splits, scope loss, duplicates, extras and omissions, with conservative credit for uncertain relations. This is a bounded data artifact plus validation/aggregation, not an automatic model-judge service.
5. **One-factor prompt ablation only after pilot evidence.** Preserve the minimal baseline. A candidate and its control use the same frozen dev data and scorer. If testing alternative prompt text, run through the real verifier and record exact prompt/code fingerprints; do not use the offline verifier injection seam to label custom calls as live. No runtime edits during a live run.
6. **Repeated-family analysis.** Use stable `(case_id, repetition)` pairing and keep all repetitions inside family clusters. Reject unequal populations/configurations instead of treating repeats as new cases. The proposed resource-limited full run plus two additional fixed-subset runs yields three observations for that subset, not three full-test runs.

## Risks / Trade-offs

- Public source contamination and common-project correlation → disclose them; group versions/mirrors/overlapping excerpts and show family counts rather than claiming independent claims.
- AI authors/reviewers share model biases → blind initial labels, retain disagreements, queue high-risk examples for Robin and never mark them human-reviewed prematurely.
- Conservative text/quote proxies → preserve transparent headline scoring and report a separate preselected semantic audit with its own denominator.
- Budget/long-output failures → explicit attempt bound, unchanged operation/byte limits, pilot consumption estimate, preserved failed and uncalled records.
- Future test exposure → data author/reviewer curate it separately; parent prompt optimizer reads only dev until freeze. Any accidental exposure is disclosed.

## Migration Plan

Protect old hashes first; add schema and legacy-specific fixture tests; validate reviewed pilot through CLI; expand only after annotation/measurement checks; freeze sources and selections; switch `datasets/main.jsonl` to reviewed v2; run new comparisons into fresh directories. Corrective changes after final freeze require a new dataset/experiment version while preserving original results. Publication is a separate user-authorized action.
