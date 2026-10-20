# Citation Grounding & Faithfulness Verifier

An HTTP service that extracts factual claims from an answer, checks them only against supplied passages, and returns **SUPPORTED**, **CONTRADICTED**, or **UNSUPPORTED** with exact quotations. A heuristic, a minimal single-call LLM verifier (the default), and an optional extraction/judgment pipeline share the same interface and safety checks.

## Current evaluation status

The second evaluation round addresses a weakness in the original submission: short fictional fixtures and high scores do not establish performance on dense real documents. A 12-case / 126-fact licensed-document development pilot and stricter measurement tooling are ready for inspection. **The two recovery checks succeeded, but the full pilot stopped at its first upstream timeout; a complete method comparison is still unavailable.** Cumulative pilot use is 63/150 approved attempts, with 87 unspent. See the [staged recovery and preserved records](reports/eval-v2/pilot-recovery-20261020.md), [earlier continuation](reports/eval-v2/pilot-resume-20261020.md), [current report](reports/eval-v2/README.md), [data card](reports/eval-v2/data-card.md) and [experiment protocol](reports/eval-v2/protocol.md). Controlled optimization and final held-out evaluation remain incomplete.

`datasets/v2/pilot.jsonl` is the new development-only input. `datasets/main.jsonl` still contains v1 while pilot/resource acceptance and the final split remain pending; it is not presented as a completed v2 migration. The commands below name the pilot explicitly. No v2 test results or general accuracy claim are available.

## Try it offline

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Installation downloads locked dependencies; these checks perform no model inference.

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
uv run grounding-eval validate --dataset datasets/v2/pilot.jsonl
uv run grounding-eval run --dataset datasets/v2/pilot.jsonl \
  --approaches heuristic --split dev --track both \
  --output reports/runs/pilot-offline
uv run grounding-eval report reports/runs/pilot-offline
```

Use a **new output directory for every run**. The heuristic is a lexical baseline; its successful execution does not validate model quality. Platforms building `cryptography` from source need its [build prerequisites](https://cryptography.io/en/latest/installation/#building-cryptography-on-macos).

## Configure and run the service

Copy `.env.example` to `.env`. For the OpenAI API route, configure `GROUNDING_PROVIDER=openai`, `GROUNDING_MODEL` and `OPENAI_API_KEY`. For the existing ChatGPT-plan route, run `uv run grounding-auth login` and `uv run grounding-auth models`, then configure `GROUNDING_PROVIDER=codex` and an available model. The application obtains its own authorization and stores credentials outside the repository; see [setup and limitations](docs/codex-provider.md).

`GROUNDING_APPROACH=minimal` remains the default; `optimized` selects the two-stage method. `GROUNDING_MAX_OUTPUT_TOKENS` applies to the OpenAI API route. The Codex route does not apply that cap: saved evaluations distinguish requested and effective limits, with the effective token limit unknown. Time, byte and attempt bounds are separate.

Two optional experimental methods use TypeSafe's pinned `jev-1.14.0`: **`jev_minimal` splits sentences with rules**, while **`jev_optimized` uses LLM atomic extraction**. Both use typed Jev decisions, exact source windows and a separate check of the selected quotations; uncertain claims escalate to one fixed-ID LLM batch. See [Jev configuration, confidence limits and evaluation](docs/jev-provider.md). The original default is unchanged. No live Jev quality, latency or cost advantage has been measured; its credentials and a new experiment budget are still required.

```bash
# Configured model:
uv run uvicorn grounding.app:app --host 127.0.0.1 --port 8000 --no-access-log

# Alternatively, no model credentials:
GROUNDING_APPROACH=heuristic uv run uvicorn grounding.app:app \
  --host 127.0.0.1 --port 8000 --no-access-log
```

Choose one server command. In a second terminal:

```bash
curl --fail-with-body http://127.0.0.1:8000/verify \
  -H 'Content-Type: application/json' --data-binary @examples/wal.json
```

The request contains `context_passages` and `generated_answer`; each response claim contains `claim_text`, `verdict`, `reasoning`, and `citations` of `{index, quote}`. Interactive documentation is at `/docs`.

## Run bounded evaluations

Model runs require an explicit total attempt allowance, including retries and repairs. Set the following shell variable to your approved integer allowance before running; it is not read from `.env`. This example does not constitute a frozen final experiment.

```bash
uv run grounding-eval run --dataset datasets/v2/pilot.jsonl \
  --approaches heuristic,minimal,optimized --split dev --track both \
  --stop-on-model-error \
  --max-total-provider-attempts "${EVAL_ATTEMPTS:?Set an approved attempt allowance}" \
  --output reports/runs/pilot-models
uv run grounding-eval report reports/runs/pilot-models

# Edge cases are separate from the main population.
uv run grounding-eval run --dataset datasets/diagnostic.jsonl \
  --approaches heuristic --split diagnostic --track both \
  --output reports/runs/diagnostic-offline
```

`--split all` selects dev/test only. `--case-ids-file` accepts a frozen JSON array of unique IDs for a subset within the selected split. Before a model job, the runner reserves that operation's maximum attempts; it charges known actual calls, or conservatively keeps the reservation when statistics are missing. Insufficient budget produces explicit NOT_RUN records with all gold facts retained. Jobs and provider calls are different units.

`--stop-on-model-error` stops subsequent model jobs after the first model failure while continuing heuristic work. The triggering job can use its existing bounded retries; later uncalled jobs retain their gold facts and consume no attempts. Omitting the option preserves the earlier execution policy. Carry prior spending forward when setting another run's allowance.

Oracle runs supply gold claim **texts**, never verdicts or evidence. End-to-end runs receive only passages and the answer. Strict text/registered-alias matching is verdict-blind and one-to-one; omissions, extras, duplicate predictions and operational failures remain in the relevant denominators. Correct unregistered paraphrases can be undercounted. False-support rate is accompanied by non-supported judgment coverage and failure counts. S/C evidence coverage, literal quotation validity and semantic sufficiency are distinct.

The [two-stage audit policy](reports/eval-v2/audit-policy.md) supplements strict scores: anonymous claim alignment is locked before labels and evidence are shown. No actual test semantic audit has occurred yet. Source-family resampling keeps repeated observations together; claims or repeated runs are not additional independent sources.

## Historical results and replay

The [2026-10-15 report](reports/2026-10-15/README.md) retains the original Codex / `gpt-6.1-sol` measurements on **24 fictional held-out cases / 50 claims**. Minimal and optimized strict joint-label F1 were 0.98 and 0.96; the paired interval crossed zero. Minimal used fewer tokens and less time, which motivated the current default. These are v1 observations, not evidence of v2 quality or proven accuracy superiority. That round's combined annotation, transport and prompt change was not a controlled prompt-only ablation.

The original 32-case dataset is preserved byte-for-byte at `datasets/legacy/main-v1.jsonl`; all historical run files remain unchanged. Replay them with their fixed original source, not the new scorer. From this repository:

```bash
legacy_checkout=$(mktemp -d)
git archive 8b0b0fe70c7a5d19c1fce14fc77cea68e233e90e | tar -x -C "$legacy_checkout"
(
  cd "$legacy_checkout"
  uv sync --frozen
  uv run grounding-eval report reports/2026-10-15/held-out
)
```

[Baseline checks](reports/eval-v2/baseline-checks.json) reproduced all four historical runs without changing any copied artifact bytes. The original development-v1 run still exits 2 because its recorded failures are preserved. New v2 records replay with the new code and frozen source snapshots; changing the scorer or damaging an artifact is expected to reject replay.

## Contract, evidence and learning materials

SUPPORTED requires complete context entailment; CONTRADICTED requires direct same-scope refutation; UNSUPPORTED includes missing evidence and unresolved equal-scope conflict. S/C require exact quotations with valid integer indices; U requires no citations. **A genuine quotation does not establish a correct judgment.**

Blank answers return empty claims without inference. Limits include a 1 MiB body, 32 passages, 96,000 total context characters, 12,000 answer characters, 64 claims, a 60-second operation deadline and six provider attempts. Failures remain errors, with safe status codes and diagnostics that exclude input text, quotes, credentials and raw upstream errors. Use the service on loopback.

- [Engineering verification](reports/eval-v2/verification.json) and [evaluation requirements](openspec/changes/evaluation-v2/specs/evaluation-v2/spec.md)
- [Architecture](docs/architecture.md), [source research](docs/research/eval-v2-sources.md), and [AI use/workflow](AI_used.md)
- [Code walkthrough](docs/code-walkthrough.zh-CN.md), [interview self-check](docs/interview-self-check.zh-CN.md), and [human review queue](reports/eval-v2/human-review.md)

AI authorship, non-author AI review, program checks and human review are reported separately. Public-document contamination, annotation bias and scoring proxies limit any eventual result. OpenAI API-key inference was not measured live. The earlier provider authentication/streaming increment's independent review was stopped by a platform risk check and remains incomplete; the new evaluator review does not certify that scope.
