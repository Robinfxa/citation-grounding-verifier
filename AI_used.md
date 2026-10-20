# AI use and development workflow

Codex helped research, design, implement, test and document this project. Robin set the goals, supplied configuration, authorized model calls and challenged the results. “One continuous delivery” means carrying the same assignment through review and repair. It does not mean one prompt produced a correct final system.

The private **dev-flow-GPT** workflow is not included. These are the rules used here, with enough detail to understand the process without installing it.

## How the workflow works

**Give each owner a clear responsibility.** A parent Director owns architecture, shared interfaces, integration and delivery. Service, evaluation and provider owners each carry their part through implementation, verification and repairs. A brief names the inputs, permitted files, constraints and acceptance evidence. Shared files have one writer; independent work can proceed in parallel. Bounded assistants research specific questions or review another author's work.

**Define observable behavior before claiming completion.** OpenSpec records the problem, design choices, expected scenarios and unfinished tasks. For example, an empty answer returns no claims without inference; an invalid quotation is rejected; a timeout remains an error rather than becoming UNSUPPORTED. The public [service scenarios](openspec/changes/citation-grounding/specs/grounding-verification/spec.md) and [evaluation scenarios](openspec/changes/evaluation-v2/specs/evaluation-v2/spec.md) show these contracts. Routine repairs reuse existing requirements.

**Check the actual consumer and repair the original defect.** Implementation first connects a runnable path, then adds scenarios. HTTP and CLI checks exercise the real entry points. Offline tests may replace an external provider, so their scope is identified separately from live inference. Review findings return to the original owner; affected checks run again after a repair. A written implementation, passing author tests, independent review and integrated acceptance are different states.

**Make failures diagnosable without retaining secrets.** Important boundaries record safe operation IDs, stages, outcomes and measured usage. For example, a Jev validation error initially identified only that probabilities did not sum correctly. The repair added the option count, computed sum, signed deviation and tolerance, without saving response text or individual probabilities. Regression tests and non-author HTTP probes checked success, failure and recovery. The subsequent live operation succeeded and did not reproduce that error; the earlier deviation remains unknown. Details remain in the [Jev verification record](openspec/changes/jev-grounding/verification.md#numeric-diagnostic-repair--2026-10-20).

**Resume from evidence, not conversation memory.** Git records code; specifications record intended behavior; a private plan records ownership and next steps; saved runs record observations. Before resuming, the Director checks running processes and completed receipts to avoid duplicate calls. Evidence is reused only while its code, inputs and scope still apply. This is a coordination discipline, not a claim that a background monitor was installed.

## How this project used it

AI researched grounding methods, evaluation and structured output before implementation. Early Hermes-inspired provider research used the requested Luna 6; later subordinate sessions used `gpt-6.1-sol` with `max` reasoning. Coding-session models and usage are distinct from the provider/model measured in benchmark runs.

The first [comparison](reports/2026-10-15/README.md) used short fictional cases. It supported retaining the cheaper Minimal default, but did not establish a general accuracy advantage. Reviewer feedback exposed the dataset's limited difficulty. The current [evaluation protocol](reports/eval-v2/protocol.md) therefore prioritizes longer real sources, dense answers, source-family separation and explicit annotation provenance. Natural responses, AI-generated answers and controlled mutations are reported separately.

Data authors are separated from prompt optimization. Non-author AI reviewers lock judgments before seeing the author's labels and evidence; disagreements are resolved before evaluation. The reviewed main dataset now contains 72 real-document cases and 668 claims, with [public review evidence](datasets/v2/realistic-draft/review-evidence/README.md). Test content stayed out of the [controlled development experiment](reports/eval-v2/ablation-20261020/README.md): it changed one citation instruction while preserving data, scoring and model settings. The adopted instruction improved the strict evidence proxy and known citation-condition failures, at a measured cost in output tokens and latency. Strict scores remain separate from the [blinded semantic audit](reports/eval-v2/audit-policy.md); predictions do not justify adding retrospective aliases.

Live failures and unused jobs remain in saved records. Earlier quota errors, timeouts and Jev protocol failures were not converted into successful judgments or discarded. New experiments use frozen inputs, finite attempt caps and actual call accounting. Subscription costs and unavailable usage are unknown, not zero. The [current report](reports/eval-v2/README.md) is the source of truth for which measurements have actually completed; work in progress is not a final result.

## Why the evidence is checkable

Program checks verify schemas, exact quotations, source hashes, failure denominators and saved-run replay. Live records identify the inputs, provider/model, outputs, errors, latency and known usage. Non-author review can find semantic mistakes that those checks cannot. None of these establishes that every annotation or judgment is correct: AI reviewers can share biases, public sources may occur in training data, and strict matching can undercount valid paraphrases.

Robin's own review remains separate. The [human review queue](reports/eval-v2/human-review.md), [code walkthrough](docs/code-walkthrough.zh-CN.md) and [interview exercises](docs/interview-self-check.zh-CN.md) support that work; generating them does not demonstrate that Robin completed it. OpenAI API-key inference was not measured live. An earlier provider authentication/streaming review was stopped by a platform risk check and remains incomplete; later evaluator checks do not certify that scope. Private correspondence, workflow files and credentials are excluded.
