## Context

This is a new project with no prior service or evaluation code. The user requested research before implementation, and subsequently requested a Codex quota provider informed by Hermes Agent. See [proposal](proposal.md) for scope and [architecture](../../../docs/architecture.md) for the durable design and source-backed choices.

## Goals / Non-Goals

Goals: independently enforce structural/evidence integrity, make semantic uncertainty measurable, retain all claims and failures, and keep the HTTP service and evaluation runner on one small typed seam. External inference credentials stay local.

Non-goals: external truth retrieval, vector storage, a user interface, production hosting, automatic public publication, or declaring an optimized model better before measuring it.

## Decisions

- Use Python 3.11, Pydantic v2 and FastAPI. Their existing validation and HTTP lifecycle support avoids a bespoke server/type system.
- Split optimized extraction and judgment; stable IDs prohibit silent rewriting/deletion. Borrow the pattern from FActScore/RAGAS, not their binary labels or loose parsing. Context-only three-way labels follow the assignment and the distinction highlighted by FEVER.
- Validate exact quotes in a pure function and judge evidence jointly. ALCE supports the latter distinction; no fuzzy citation library is imported.
- Define one single-attempt structured provider seam, with shared deadline/retry/repair budgets outside the adapter. OpenAI Responses uses HTTPX directly; the user-requested Codex adapter follows the separately documented transport investigation before implementation.
- Evaluate fixed gold claims separately from complete-answer extraction. Frozen strict aliases make alignment auditable; their conservative limitation is disclosed. Failure denominators, evidence sets and paired case bootstrap prevent common inflated scores.
- The final delivery review adds explicit diagnostic selection while preserving `all` as dev/test only. Diagnostic artifacts are separate from the frozen quality comparison. New resource metadata distinguishes requested and applied output limits; the Codex preview adapter continues to omit its unsupported token-limit parameter.
- Default to minimal after the frozen experiment found no clear overall optimized benefit, with materially lower measured latency and token use. These delivery corrections do not change prompts, datasets, aliases, scoring or historical run artifacts.

## Risks / Trade-offs

- Semantic extraction can omit or distort claims → independent gold claims, coverage metrics and adversarial cases; no deterministic completeness claim.
- Exact citations can be irrelevant → separate semantic/gold-evidence metrics and literal integrity metrics.
- Strict text matching undercounts valid paraphrases → label the score conservatively and expose unmatched records beside oracle results.
- Codex subscription transport may differ from API Responses and may not report billing usage → verify real adapter behavior, surface unavailable metadata, and do not invent dollar costs.
- Missing credentials or inaccessible provider → continue offline work and retain live benchmark tasks as incomplete.

## Migration Plan

No existing consumer migration is needed. Deliver a locked local package, HTTP/CLI examples, offline tests and live-run commands. Public repository creation and deployment remain separate final actions.

Final acceptance uses a clean clone and a new environment with frozen dependency installation, offline tests, a running HTTP example, separate live diagnostic records, and a source-only submission archive. A prompt-only development ablation remains optional future work and is not a delivery gate.
