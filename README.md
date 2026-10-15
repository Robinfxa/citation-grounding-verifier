# Citation Grounding & Faithfulness Verifier

An HTTP service that splits an answer into factual claims, checks them against supplied passages, and attaches exact quotations. It distinguishes **SUPPORTED**, **CONTRADICTED**, and **UNSUPPORTED** without external knowledge.

Three approaches share one interface: a deterministic heuristic, a minimal single-call LLM verifier (**the default**), and an optimized decomposition/judgment pipeline. The [frozen experiment](reports/2026-10-15/README.md) found no clear overall quality advantage for the larger pipeline, while minimal used less time and fewer tokens.

## Try it offline

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). No credential or network inference is needed for these checks; installation downloads the locked dependencies.

```bash
uv sync --frozen
uv run pytest
uv run grounding-eval validate
uv run grounding-eval run --approaches heuristic --split dev --track both \
  --output reports/runs/heuristic-dev
```

Use a fresh output directory for every run. To try the HTTP service without credentials, start it with `GROUNDING_APPROACH=heuristic` as shown below. The heuristic is a limited lexical baseline, not a substitute for measured LLM quality.

## Configure a model

```bash
cp .env.example .env
```

| Route | Setup | Accounting |
| --- | --- | --- |
| ChatGPT plan (`codex`) | Run `uv run grounding-auth login`, then `uv run grounding-auth models`; set `GROUNDING_PROVIDER=codex` and an available `GROUNDING_MODEL` in `.env` | Authorized ChatGPT/Codex plan usage; dollar cost remains unknown |
| OpenAI API (`openai`) | Set `GROUNDING_PROVIDER=openai`, `GROUNDING_MODEL` and `OPENAI_API_KEY` in `.env` | Measured provider tokens; dollar estimates require explicit matching prices |

`GROUNDING_APPROACH=minimal` is the default; set `optimized` to opt into two-stage verification. The ChatGPT-plan adapter targets macOS/Linux and obtains this application's own authorization, keeping tokens outside the repository. See [authentication setup and limitations](docs/codex-provider.md).

`GROUNDING_MAX_OUTPUT_TOKENS` is sent to the OpenAI API route. The Codex route **does not apply this token cap**. New evaluation configurations distinguish the requested limit from the effective limit (`null` / not applied for Codex); time, response-byte and attempt bounds remain separate.

## Run the service

```bash
# Use the configured model and default minimal approach:
uv run uvicorn grounding.app:app --host 127.0.0.1 --port 8000 --no-access-log

# Or, without model credentials:
GROUNDING_APPROACH=heuristic uv run uvicorn grounding.app:app \
  --host 127.0.0.1 --port 8000 --no-access-log
```

Run one server command, then in a second terminal:

```bash
curl --fail-with-body http://127.0.0.1:8000/verify \
  -H 'Content-Type: application/json' --data-binary @examples/wal.json
```

Interactive API documentation is at `/docs`. The request has only `context_passages` and `generated_answer`; each response claim contains `claim_text`, `verdict`, `reasoning`, and `citations` of `{index, quote}`.

## Measured results

The **2026-10-15** frozen comparison used real Codex / `gpt-6.1-sol` calls on **24 held-out cases / 50 claims**, with sequential seeded execution. All 144 approach/track/case jobs completed without errors, retries, repairs or unknown usage. These are single observed trials on agent-authored synthetic English data.

| End-to-end approach | Joint label F1 | Joint label + evidence F1 | Exact cases | Median latency | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heuristic | 0.3299 | 0.3299 | 6/24 | 0.60 ms | 0 / 0 |
| Minimal | 0.9800 | 0.9600 | 22/24 | 4.50 s | 8,972 / 3,614 |
| Optimized | 0.9600 | 0.9600 | 23/24 | 7.82 s | 26,293 / 5,198 |

Joint F1 counts correctly aligned claims against **all gold and predicted claims**, including omissions and extras. Exact cases also require every claim and citation to satisfy the frozen evidence proxy. Both LLM oracle tracks labeled **50/50** supplied claims correctly and covered **35/35** non-UNSUPPORTED evidence sets.

The paired optimized-minus-minimal joint-label F1 difference was **−0.0200**, with a 95% family-bootstrap interval **[−0.1200, +0.0577]**. It spans zero: minimal is the lower-latency, lower-token default, without a claim of proven accuracy superiority. Codex dollar cost is `null`, not zero; token usage is not a remaining-quota estimate.

Minimal made one real unknown-versus-contradicted judgment error and lost one conservative full-quote match. Optimized produced two plural rewrites unmatched by the frozen claims/aliases, with possible scope ambiguity. No held-out aliases or scores were changed. Development v1→v2 changed annotations, transport and the judge prompt together, so it was **not a controlled prompt-only A/B experiment**. The [full report](reports/2026-10-15/README.md) retains predictions, errors, resource tables, confidence intervals and failure analysis.

## Run evaluations and diagnostics

```bash
# After configuring a provider; each output directory must be new.
uv run grounding-eval run --approaches heuristic,minimal,optimized \
  --split dev --track both --output reports/runs/development
uv run grounding-eval run --approaches heuristic,minimal,optimized \
  --split test --track both --output reports/runs/held-out
uv run grounding-eval report reports/runs/held-out

# Separate edge cases; never included in --split all or the main leaderboard.
uv run grounding-eval run --dataset datasets/diagnostic.jsonl \
  --approaches heuristic,minimal,optimized --split diagnostic --track both \
  --output reports/runs/diagnostic
```

The [dataset card](datasets/README.md) describes 32 main cases / 68 claims, with disjoint development (8 cases) and test (24 cases) families, balanced categories, and six separate diagnostics. `--split all` means dev and test only. Oracle evaluation fixes the input claims; end-to-end evaluation includes extraction. Frozen text/alias matching is verdict-blind and one-to-one; correct unregistered paraphrases can be undercounted.

Runs preserve failures in the denominators and save configuration, dataset/prompt/code fingerprints, actual latency, usage and model IDs. Gold evidence coverage is a conservative span proxy, not an independent semantic judge. Zero denominators remain undefined. Small-sample bootstrap intervals do not account for annotation bias or model stochasticity.

## Contract and engineering checks

SUPPORTED means fully entailed by context; CONTRADICTED means directly refuted; UNSUPPORTED includes missing evidence and unresolved equal-scope conflicts. Supported/contradicted claims require exact source citations; unsupported claims have none. Code enforces strict integer indices, bounds, nonblank quotes and case-sensitive substring membership without normalization. **A genuine quotation does not prove a correct judgment.**

Blank answers return `{"claims": []}` without inference. Other no-fact answers require successful extraction. Model failures never become fabricated unsupported claims. Limits include a 1 MiB body, 32 passages, 64 claims, a 60-second operation deadline and six provider attempts. Safe errors distinguish invalid input (422/413), unavailable configuration/provider (503), invalid/refused/incomplete output (502), and deadline expiry (504). Local diagnostics exclude input text, quotes, credentials and raw upstream errors. Use the service on loopback.

```bash
uv run ruff check .
```

See [architecture and research sources](docs/architecture.md), [annotation history](docs/dataset-review.md), and [verification evidence](openspec/changes/citation-grounding/verification.md). Service, evaluator and dataset received independent agent reviews. New provider authentication/streaming increments have author tests and live acceptance, but their independent review was stopped by a platform risk check; no independent approval is claimed. OpenAI API-key inference has offline transport coverage and was not measured live. Deterministic guards do not guarantee semantic accuracy, extraction completeness or universal prompt-injection resistance.
