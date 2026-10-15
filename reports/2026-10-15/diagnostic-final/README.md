# Separate delivery diagnostics

This run exercises the six pre-existing diagnostic cases after the final delivery corrections, independently of the frozen main benchmark. It is not a new leaderboard or a held-out rerun. The cases cover empty context, a blank answer, a non-factual answer, equal-scope source conflict, an instruction embedded in evidence, and exact Unicode quotations.

- Implementation commit: `dbe8b77263be8bf952428d83ff0f1eca30a6b24d`.
- Started: `2026-10-15T10:05:37.530547+00:00`; parent wrapper completed in 93.216 seconds.
- Source aggregate SHA-256: `fa3e618108958f417727bd56652f359e3446d6ca4918781aa38ff16f9746b9cb`.
- Unchanged diagnostic dataset SHA-256: `39d581b9abfe695c263130b4e84439aa86aef66900186158b26716a265a34fb0`.
- Provider/model: real Codex / `gpt-6.1-sol`, sequential seeded execution, both tracks, seed 20261015.
- **36/36 jobs completed without operational errors**, retries, repairs, unknown usage, quota stop or source changes. The LLM paths made 19 provider calls total.

| Approach / track | Exact cases | Provider calls | Input / output tokens |
| --- | ---: | ---: | ---: |
| Heuristic / end-to-end | 4/6 | 0 | 0 / 0 |
| Heuristic / oracle | 4/6 | 0 | 0 / 0 |
| Minimal / end-to-end | 6/6 | 5 | 1,706 / 259 |
| Minimal / oracle | 6/6 | 3 | 1,085 / 178 |
| Optimized / end-to-end | 6/6 | 8 | 3,817 / 378 |
| Optimized / oracle | 6/6 | 3 | 2,072 / 180 |

Each track contains four gold factual claims plus two zero-claim cases. Blank answers, empty oracle claims and empty-context oracle judgments can complete without model calls. An exact case means agreement with the fixed claim/evidence proxy, including no extra claims. These six fixtures do not establish broad semantic correctness or general prompt-injection resistance. Diagnostic timings are retained in the raw records but are not used for a new performance comparison; a separate clean-environment installation ran concurrently.

The heuristic's two failures are preserved in both tracks: it returned SUPPORTED despite equally scoped locked/unlocked sources, and UNSUPPORTED rather than CONTRADICTED for the red-versus-blue case containing an embedded instruction. The model methods matched the frozen expectations in this single run. No prompts, annotations, aliases or scoring rules were changed to obtain these results.

The new configuration states the output-token limitation explicitly:

```json
"max_output_tokens": {
  "requested": 8192,
  "effective": null,
  "application": "not_applied"
}
```

Codex does not receive that cap. Existing time, attempt and response-byte bounds do not establish an output-token bound. All cached-input counts were zero; subscription dollar cost remains unknown. In the older development/held-out configurations, the scalar `max_output_tokens: 8192` records only the request and must not be read as applied. Those historical files and scores remain unchanged.

To reproduce into a new directory after configuring a provider:

```bash
uv run --frozen grounding-eval run --dataset datasets/diagnostic.jsonl \
  --approaches heuristic,minimal,optimized --split diagnostic --track both \
  --output reports/runs/diagnostic
uv run --frozen grounding-eval report reports/2026-10-15/diagnostic-final
```

The configuration and summary explicitly use `split: diagnostic`. `--split all` still selects only dev/test, including when the input contains all three partitions. The five machine-readable files here are exact copies of the completed run; records SHA-256 is `fe6fca7a574c7c1b432e08493a09b601fbc968f468be23c744bacd937f1f1643`.
