# Verification evidence

## Shared foundation
- Workspace: `/Users/robin/Desktop/ass`; initial uncommitted implementation of `src/grounding/contracts.py`, `tests/test_contracts.py`, `pyproject.toml`, `uv.lock`.
- `openspec validate citation-grounding --strict`: passed.
- `uv sync --native-tls`: passed with Python 3.11.9. After adding JWT validation, cryptography 50.0.2 built successfully; PyJWT 2.15.1 and its dependency group installed. The build's temporary lock is released.
- `uv run pytest tests/test_contracts.py -q`: 19 passed. Covers strict indices, blank/wrong-source/Unicode/changed/cross-passage quotes, verdict/evidence shape, input coercion/limits, unknown usage aggregation.
- `uv run ruff check src/grounding/contracts.py tests/test_contracts.py`: passed before adding the four Codex error codes; final integrated lint still required.
- These are offline deterministic boundary tests. They do not establish real provider access, semantic accuracy or model token cost.

## Domain evidence
- Service: pending [owner result](../../../docs/plans/active/service-result.md).
- Evaluation: [owner result](../../../docs/plans/active/evaluation-result.md). Dataset freeze candidate exists, independent semantic review in progress before test inference.
- Provider: pending [owner result](../../../docs/plans/active/provider-result.md). Official public SIWC route selected; live authentication and schema compatibility remain unverified.

## Outstanding
All live quality comparisons, measured improvement claims, final integrated checks, independent runtime/logging review and public publication remain incomplete.
