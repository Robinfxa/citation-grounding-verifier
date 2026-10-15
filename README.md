# Citation Grounding & Faithfulness Verifier

An HTTP service that splits an answer into factual claims, checks them against supplied passages, and attaches exact quotations. It distinguishes **SUPPORTED**, **CONTRADICTED**, and **UNSUPPORTED** without consulting external knowledge.

The repository includes three approaches—an inexpensive deterministic heuristic, a minimal single-call LLM verifier, and an optimized decomposition/judgment pipeline—and an independent evaluation harness.

> Implementation and verification are in progress. The final measured comparison will be added after the frozen dataset, provider integration and independent reviews are complete. No simulated output is presented as a live LLM result.

## Run locally

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The ChatGPT-plan login adapter targets macOS and Linux.

```bash
uv sync --frozen
cp .env.example .env
```

Choose one inference route:

| Route | Setup | Accounting |
| --- | --- | --- |
| ChatGPT plan (`codex`) | `uv run grounding-auth login`, then `uv run grounding-auth models`; set `GROUNDING_PROVIDER=codex` and an available `GROUNDING_MODEL` in `.env` | Uses the app's authorized share of ChatGPT/Codex plan usage; token counts are not converted to dollars |
| OpenAI API (`openai`) | Set `GROUNDING_PROVIDER=openai`, `GROUNDING_MODEL` and `OPENAI_API_KEY` in `.env` | Provider tokens; cost estimates only when explicit matching prices are supplied |
| Offline heuristic | Set `GROUNDING_APPROACH=heuristic` | No model, credential or network inference required |

The ChatGPT-plan route uses this application's own public [Sign in with ChatGPT](https://developers.openai.com/siwc/token-sharing-open-source) authorization. It does not import another program's credentials or run a coding agent on request text. Tokens stay outside the repository in a protected local profile store. See [provider setup and limitations](docs/codex-provider.md).

```bash
uv run uvicorn grounding.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal:

```bash
curl --fail-with-body http://127.0.0.1:8000/verify \
  -H 'Content-Type: application/json' \
  --data-binary @examples/wal.json
```

`GROUNDING_APPROACH` selects `heuristic`, `minimal`, or `optimized` (default). The public request contains only `context_passages` and `generated_answer`. See interactive API documentation at `/docs` after starting the server.

## Contract

Each response claim contains `claim_text`, `verdict`, brief `reasoning`, and `citations` of `{index, quote}`.

- **SUPPORTED:** the provided evidence entails the whole claim.
- **CONTRADICTED:** the provided evidence directly refutes it.
- **UNSUPPORTED:** the context cannot establish either; this includes externally true but unmentioned facts and unresolved equal-scope source conflicts.

Supported and contradicted claims require evidence; unsupported claims require `citations: []`. Code checks strict integer indices, passage bounds, nonblank quotations and exact case-sensitive substring membership. It never normalizes or fuzzily repairs a citation. Multiple passages may jointly establish a claim. **A genuine quotation does not prove that a verdict is correct.**

Blank answers return `{"claims": []}` without model inference. Other no-fact answers require successful extraction. Empty context does not mean an empty answer: extracted facts remain unsupported. Refusal, truncation, invalid model output and provider outages produce explicit errors, never fabricated unsupported claims or partial successful reports.

Initial limits are 32 passages, 16,000 characters per passage, 96,000 aggregate context characters, 12,000 answer characters, 64 claims, a 1 MiB body, a 60-second operation deadline and six provider attempts. Optimized extraction and judgment each allow at most one output repair within the shared budget.

| Failure | HTTP status |
| --- | ---: |
| Invalid request / oversized body | 422 / 413 |
| Missing configuration, authentication or provider availability | 503 |
| Invalid, refused or incomplete upstream output | 502 |
| Operation deadline | 504 |

Error responses and local diagnostics contain safe categories and correlation IDs; they exclude supplied passages, answers, quotations, keys and upstream exception text. Use this local service on loopback; authentication for a multiuser hosted deployment is outside this assignment.

## Evaluation

```bash
uv run grounding-eval validate
uv run grounding-eval run --approaches heuristic --split dev --track both \
  --output reports/runs/heuristic-dev

# Run after configuring an inference provider. Use a fresh output directory.
uv run grounding-eval run --approaches heuristic,minimal,optimized \
  --split dev --track both --output reports/runs/development
uv run grounding-eval run --approaches heuristic,minimal,optimized \
  --split test --track both --output reports/runs/held-out
uv run grounding-eval report reports/runs/held-out
```

The main benchmark contains 32 original fictional systems cases across supported answers, subtle distortions, extrinsic hallucinations and genuine multi-passage inference. Development and held-out test families are disjoint. Separate diagnostic cases cover edge conditions. The [dataset card](datasets/README.md) records annotation provenance, split composition and limitations.

Two tracks prevent extraction quality from disappearing inside a single score:

1. **Oracle claims:** give every implementation exactly the same gold claims; evaluate three-way labels and evidence.
2. **End-to-end:** supply the original answer; match predictions one-to-one against frozen texts/aliases, without looking at predicted verdicts. Omissions, extras, duplicates and operational failures remain in the denominators.

End-to-end alignment is intentionally conservative: an unregistered but correct paraphrase can be counted as unmatched. Oracle results are therefore reported separately. Literal quote validity and gold evidence-set coverage are distinct; the latter is a conservative span-based diagnostic, not an independent semantic judge. Zero denominators remain undefined rather than becoming perfect scores.

Runs retain per-case results, safe errors, dataset/prompt/code fingerprints, settings, actual wall time, known/unknown token usage, retry/repair counts and requested/returned model IDs. Confidence intervals resample cases/families; paired differences use the same samples. A small synthetic set cannot establish deployment-wide accuracy, and bootstrap intervals do not account for annotation bias or model stochasticity.

## Measured results and iteration

Pending final integrated runs. The final report will distinguish engineering tests, heuristic measurements and live LLM measurements, and retain unsuccessful requests. Missing authentication or model access will be recorded as a limitation, not replaced with mock scores. Optimized is a design label, not a claim of an observed win.

## Development and design

```bash
uv run pytest
uv run ruff check .
```

The design is documented in [architecture.md](docs/architecture.md). The small shared contract sits in `src/grounding/contracts.py`; provider failures, model judgments and deterministic citation integrity have separate boundaries. The evaluator imports the public verification seam and does not share verdict logic or gold labels with implementations.

Research inspected original papers, source code and author documentation for [FActScore, RAGAS, ALCE, SAFE and Claimify](docs/research/grounding/sources.md), [benchmark methods](docs/research/evaluation/sources.md), [structured API behavior](docs/research/structured-api/README.md), and [Hermes/Codex providers](docs/research/codex-provider/sources-and-probes.md). Patterns are adapted to this closed-context task; peer retrieval systems and permissive citation parsers are not imported.

No vector database, web retrieval, server-side conversation state or external telemetry is needed. Deterministic guards do not guarantee semantic accuracy, extraction completeness or resistance to every prompt injection. See the measured failure analysis before using the service for consequential decisions.
