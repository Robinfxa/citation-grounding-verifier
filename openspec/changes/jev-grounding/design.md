## Context

See [proposal.md](proposal.md) for scope and [the research note](../../../docs/research/jev/README.md) for official sources and their limits. This design was recorded on 2026-10-20; implementation and outstanding real-provider acceptance are tracked separately in [verification.md](verification.md).

Current code already has answer-only anchored extraction, fixed-ID LLM judgment, exact citation validation, a shared operation budget and immutable evaluation records. Its provider seam returns generated JSON text and its statistics describe one provider/model. Jev is a typed-decision API, so these two assumptions cannot simply be reused unchanged. The user selected rule-based Minimal and LLM-extracted Optimized; both new names remain distinct from the existing LLM methods.

## Goals / Non-Goals

**Goals:** a bounded fast path with no generative LLM in Jev Minimal's normal case; a shared judgment path that isolates the value of LLM extraction; explicit evidence and uncertainty checks; honest whole-operation measurements.

**Non-Goals:** changing the default verifier, replacing old reports, adding retrieval infrastructure, giving confidence an accuracy guarantee, tuning on previously inspected held-out outputs, or restarting the stopped Codex pilot. First implementation is experimental and opt-in.

## Decisions

### 1. Small separate decision adapter

Add a Jev HTTPX adapter returning typed Choice answers, usage and actual model identity. Keep the existing structured-text provider for extraction and fallback. Do not fabricate arbitrary JSON-generation support or install an SDK solely for this endpoint. Reuse bounded body reads, safe error categories and a reusable async client; the adapter itself makes one attempt and owns no retries.

Use `POST https://api.typesafe.ai/v1/systemone`, explicit `jev-1.14.0`, and an ignored local `TYPESAFE_API_KEY`. Do not route this secret through `OPENAI_API_KEY`, inspect unrelated application credentials, enable long-context preview headers or use moving model aliases. Native authentication/error details must be verified against fixed SDK source before adapter code is finalized; live wire compatibility is a separate acceptance step.

Validate exact question coverage, no duplicate JSON keys, known answer types/options, finite numeric values (not bool), probability bounds/sum, argmax and returned version. Initial recorded tolerances: sum error at most 0.001, argmax tie tolerance 0.000001, confidence/formula difference at most 0.02. These are parser tolerances, not quality thresholds. Gate on the lesser of returned confidence and the locally computed documented formula (clipped to [0,1] only for numerical edge effects); retain both values and label the latter as derived. Thus a returned 0.8 with derived 0.78 cannot cross a 0.8 gate merely because it falls within parser tolerance. A smoke test must verify actual serialization precision; incompatible responses fail explicitly, never automatically widen tolerances or renormalize probabilities. Missing usage remains incomplete while usable measured counters survive later validation failure.

### 2. Extraction is the only method difference

| Stage | `jev_minimal` | `jev_optimized` |
| --- | --- | --- |
| End-to-end extraction | Reuse `heuristics.extract_claims`; retain its rule boundaries and disclose compound/missed factual claims | Reuse the answer-only `EXTRACT` prompt and exact anchor validator |
| Oracle extraction | None; supplied claims remain fixed | None; supplied claims remain fixed |
| Jev judgment / evidence / fallback | Identical shared path and configuration | Identical shared path and configuration |

Reuse small extraction/fixed-claim judgment helpers from the existing verifier where necessary; do not copy a second retry/repair implementation or change existing prompt bytes. Both Jev methods use the refined fixed-claim `JUDGE` prompt for escalation. Existing provider/model settings designate the LLM used for extraction and fallback; Jev has its own model/key settings. No runtime LLM selection based on which answer looks better. The actual LLM identity is frozen before measurement; the existing Codex allowance is not authorization to call it in this new experiment.

Blank answer and empty extracted claim list are zero-judgment paths. Empty context yields U only after extraction; Jev Minimal needs no model, Jev Optimized may still need its extractor. Missing optional fallback credentials fail configuration preflight when fallback is enabled, before spending Jev attempts.

### 3. Full-context labels, bounded evidence proposals, then quote-only checking

Fast-path evidence needs text that already exists. An LLM evidence proposer on every request would erase much of Minimal's intended saving. Choosing one passage also cannot express joint evidence. Use a deliberately bounded local candidate policy, versioned and measured rather than described as complete retrieval:

1. Derive source offsets for individual sentences and contiguous windows of up to three sentences. Slice original Unicode strings; never join normalized sentences or alter spaces/punctuation. Exclude windows longer than 1,200 characters, deduplicate identical `(passage,start,end)` spans and retain the eight highest lexical-overlap windows per claim. Use a frozen simple Unicode token overlap score, then shorter span and source offset as deterministic tie breakers; no gold data or external search. Low coverage is an expected fallback cause.
2. Enumerate those single windows and unordered pairs (at most 36 bundles), plus `NO_ADEQUATE_BUNDLE`. Merge overlapping spans from the same passage only by slicing their original contiguous union, within the 2,400-character bundle cap. Preserve separate indices for different passages. More complex evidence remains eligible for LLM fallback. Never add the entire context as a catch-all option.
3. First Jev batch shares the **complete original context**, plus one deduplicated catalog of the proposed windows with original indices, offsets and text. Bundle options reference catalog IDs instead of repeating quotation text for every pair; all IDs needed by the model appear in visible instructions/criteria. Per fixed claim, ask independent Choice questions for (a) S/C/U against the original context; (b) a candidate bundle ID, when candidates exist; and (c) why U, with `INSUFFICIENT_EVIDENCE` / `UNRESOLVED_CONFLICT` options. The latter two are speculative: each question contains the claim and task explicitly and cannot depend on the answer to (a). Question IDs are only routing keys.
4. High-confidence U additionally requires a confident U-reason decision, then produces no citations and a reason template distinguishing conflict from insufficient evidence. Low-confidence labels/reasons go to fallback. For high-confidence S/C, no adequate bundle means fallback, never U. Selection confidence is saved but is not an acceptance gate: its variable option count and limited candidate coverage do not establish reliability.
5. A second Jev batch checks whether each selected quote bundle **alone** completely supports or directly refutes its claim. Put each claim and only its selected quotations into that question's structured instructions; shared state contains policy only, no source text or other claims' quotations. This input design relies on the documented independent-question behavior, and does not claim verified service-side isolation. Ask the same three relation options. Accept only a high-confidence label matching the full-context label. Disagreement, low confidence or insufficient quoted evidence goes to fallback.
6. Assemble quotations from retained source offsets, apply `validate_report`, and use short disclosed reason templates referencing selected passage indices. These are summaries of the decision, not a generated reasoning trace or proof. The LLM fallback can produce ordinary brief reasoning under the existing schema.

The full-context check sees adverse/conflicting evidence, while the quote-only check tests what the returned evidence actually establishes. Two model decisions still may share a semantic error; neither is a deterministic entailment proof. Offline request inspection must prove that each question contains only its own quoted evidence and that shared state has no sources. Real paired probes must check behavior with unrelated or adversarial neighboring questions; neither mocked responses nor a few live examples prove universal service-side isolation.

Normal logical calls are one Jev call for all-U answers, two for answers with S/C evidence, plus one extractor call for Optimized. All claims are batched. Candidate growth is bounded; total serialized size and provider context limits still apply. Never trim the original context to make a request fit, claim that character count is token count, or split independent chunks and combine them as though each saw the full context. Infeasible request size fails explicitly with `unsupported_capability` under a recorded local size bound or provider-limit response. First live probes must establish practical question/context limits before larger runs.

### 4. Confidence gates and one fallback batch

For the experimental profile start with **0.8 separately** for full-context relation, quote relation and U reason, applied to the conservative gate score above. This is an explicit uncalibrated starting policy, not a production threshold or a claim of 80% accuracy. The three-class formula and two-class reason formula use their own option counts. Save each raw score/distribution, derived score and gate outcome; never multiply scores or attach Jev confidence to the final LLM verdict. A missing score is a protocol failure, not a low score.

Collect unresolved claim IDs and invoke one logical LLM judgment batch with those original texts and the **full original context**. Do not send Jev's candidate verdict/probabilities to the LLM; this avoids asking it to endorse the first model. Validate exact ID multiplicity and quotes before merging with accepted results. One bounded structured-output repair remains allowed; no second fallback or confidence-driven Jev resampling. Failed extraction cannot fall back to rule splitting, which would silently change Optimized's method.

Semantic routing reasons include `label_uncertain`, `unsupported_reason_uncertain`, `candidate_missing`, `quote_uncertain`, and `quote_disagreement`. Authentication, quota, transport and malformed responses remain classified errors under the existing bounded transport policy; they do not silently switch providers. Explicit fallback-disabled runs return HTTP 502 `confidence_unresolved` when escalation is needed. Configured fallback failures preserve their own error category plus the original routing reason; the public endpoint never returns partial success.

All stages and retries share the existing operation deadline and total attempt cap. Increment the shared counter before every network attempt, including fallback repair. The experiment preflight reserves the full configured per-operation cap and checks separately authorized provider allowances. Cancellation or exhausted allowance prevents the next attempt. A response with 100 questions counts as one provider attempt and 100 questions; both are recorded. Initial no-retry probes and stop-on-model-error are operational policies, not semantic confidence retries.

Implementation clarification: the initial spending policy enforces total/per-provider attempt caps, not a dollar ceiling. Price snapshots support measured cost only. Without a reliable provider debit guard or verified pre-call billing bound, a request for a hard monetary cap fails preflight. Do not infer a billing bound from local byte limits or silently treat a requested ceiling as effective. The live authorization must explicitly accept this policy and any unpriced subscription stages.

### 5. Mixed-provider records without rewriting history

Extend runtime statistics with per-attempt entries: stage, provider, requested/returned model, outcome, usage/completeness and elapsed time. Keep whole-operation wall time separate from summed stage durations. Add per-claim Jev decision/gate/final-origin diagnostics to explicitly requested evaluation artifacts, not the successful `/verify` JSON or routine logs.

Use a new, explicit saved-run format for Jev experiments; format-2 readers and historical artifacts remain strict and immutable. Old methods keep their existing serialization unless the new format is explicitly selected. Do not make old records appear to contain stage information that was never measured. Fixed-source historical replay remains the supported route when code fingerprints differ.

Save ordered question/criteria/candidate policy fingerprints, thresholds/tolerances, extractor/fallback identities, source hashes, requested/effective limits and a dated price snapshot. Report Jev cost only from measured Jev usage at the recorded input rate; output can be priced at zero while still counted as tokens. Codex stages retain unknown dollar cost. Missing usage or any unpriced stage makes total cost unknown, with a separately labeled known subtotal. Sum attempts across all providers; do not apply Jev prices to pooled tokens or infer budget balance from successful requests alone.

The new pair's oracle track has the same algorithm. Any live difference there is sampling/operational variation, not evidence of better extraction. Existing Minimal versus Jev Minimal changes model, extraction and judge policy together and must be described as a workflow comparison, not a controlled model-only or prompt-only ablation.

### 6. Development calibration and acceptance

Keep current development inputs and annotations fixed; no retrospective alias or held-out edits. Report automatic coverage and conditional errors at recorded thresholds, C/U-to-S false support with full denominators, merged/missed claims, final failure-inclusive quality, evidence sufficiency/quote length, fallback reasons/rate, latency and per-provider usage/cost. Family counts and uncertainty matter; a small pilot cannot certify calibration.

Threshold sweeps can replay stored Jev distributions to estimate automatic-decision coverage/error, but cannot invent results or costs for LLM fallbacks that were never run. Freeze the chosen policy before any new held-out matrix. Compare initial versus tuned policies on development only and label selection bias. Actual end-to-end quality and cost require running the frozen routing policy.

Implementation acceptance uses offline HTTPX responses through actual HTTP/CLI consumers, including high-confidence success, joint evidence, Unicode and scope/antecedent loss, missing candidates, low confidence followed by success/failure, malformed confidence and model drift, mixed accounting, global deadline/caps, safe logs and historical replay. A non-author checks source plus fresh local probes. This proves control flow and validation only. Real smoke, calibration and performance require a separately agreed bounded run after credentials are present.

## Risks / Trade-offs

- Candidate selection misses paraphrases or long/multi-hop evidence → bounded LLM fallback; measure rate and total cost rather than tuning on test answers.
- Confident but wrong semantic decisions → developer-set thresholds, family-held-out validation and semantic evidence audit; never promise zero hallucination.
- Two Jev rounds plus LLM extraction/fallback remove the advertised speed benefit → record full wall time; retain the simpler existing default unless measurements warrant change.
- Rule splitting merges claims or filters factual questions → keep behavior explicit, preserve evaluation penalties and compare oracle separately.
- Model/version or question changes invalidate prior confidence behavior → pin identities and freeze policy fingerprints; revalidate affected data.
- Provider overload or uncertain usage makes dollar budgeting imprecise → explicit attempt caps, known subtotals, unknown totals and failure-stop; do not spend the former pilot balance implicitly.

## Migration Plan

1. Add the optional adapter and offline consumer skeleton with current methods/default untouched.
2. Complete evidence, escalation and mixed-record acceptance before any paid run; publish experimental configuration documentation without credentials.
3. With local credentials and a new explicit budget, run small version/schema/usage and two-variant smoke checks, stopping on first model error. Quote the full matrix budget from observed use before proceeding.
4. Run development calibration and freeze the policy for any later held-out experiment. Retain current default. Rollback is selecting an existing approach; new artifacts are retained as historical evidence.

## Open Questions

- Which configured generative LLM and explicit per-provider call/spend allowance will be used for the live Jev experiment? This affects run configuration and feasibility, not the two methods' architecture. No new inference is authorized yet.
- Real 1.14 response precision, maximum practical batch size, rate-limit responses, usage completeness and speed need the bounded smoke. Until then the HTTP reference/SDK findings and offline fixtures are provisional compatibility evidence.
- The development sample may be too small to select trustworthy thresholds. If so, report that limitation and retain experimental status instead of claiming a calibrated policy.
