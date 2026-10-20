## Why

The user wants to test whether TypeSafe Jev can reduce verification latency and cost while retaining explicit confidence-based escalation. Jev produces typed decisions, not arbitrary claim text or quotations, so adding it as a drop-in structured-text provider would misrepresent its capabilities.

## What Changes

- Add opt-in `jev_minimal` (existing rule-based sentence extraction) and `jev_optimized` (answer-only LLM atomic extraction), as explicitly selected by the user on 2026-10-20. Both use the same Jev judgment, exact-evidence and fallback policy.
- Pin `jev-1.14.0`; introduce a small typed-decision adapter alongside the existing structured-text seam.
- Judge against the complete supplied context. Select bounded verbatim evidence candidates and separately check their sufficiency. Uncertain decisions or inadequate candidates escalate once to a configured LLM over the same fixed claims and full context.
- Treat low confidence as an operational routing condition, never as `UNSUPPORTED`. Preserve whole-request failure, exact quotations and bounded attempts/deadlines.
- Record per-stage provider/model identity, confidence diagnostics, fallback reasons and usage. Evaluate total workflow quality, latency and cost, including extraction and fallback.
- Make probability-sum rejection diagnosable with bounded numeric aggregates (option count, observed sum, signed deviation and tolerance) in the existing opt-in local logger; retain payload exclusion and protocol-error semantics.
- Keep existing methods, default `minimal`, historical reports and the stopped Codex pilot unchanged. New live calls require a separately authorized budget and user-supplied local credentials.

## Capabilities

### New Capabilities

- `jev-grounding`: Optional typed-decision verification with two extraction strategies, bounded semantic escalation, exact evidence, and reproducible mixed-provider measurements.

### Modified Capabilities

None in the main spec inventory, which is currently empty. This extension references the in-flight `citation-grounding` and `evaluation-v2` contracts. Its sentence baseline explicitly measures non-atomic extraction; it does not redefine the existing minimal LLM method or claim to satisfy atomic decomposition by construction.

## Impact

Planned integration points are `grounding.contracts`, configuration/building, a new Jev adapter/verifier, HTTP error mapping, evaluation CLI/records/reporting, focused tests and public documentation. Reuse HTTPX, Pydantic, the existing extraction/judgment prompts and exact citation validator; no SDK, retrieval service, database or agent framework is required. Public success JSON remains unchanged; opt-in unresolved confidence adds an explicit operational error. Mixed-provider records need a versioned schema rather than overloading a single-model usage record.

Research and implementation design are linked from [design.md](design.md). This proposal is not evidence of implemented or measured Jev support.
