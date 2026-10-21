# 代码导读：沿真实输入走完两条路径

版本绑定：请在包含本文的同一 Git 提交中打开下列相对链接；用 `git rev-parse HEAD` 确认正在阅读的版本。实验运行另有 `config.json` 中的逐文件指纹，不能用今天的代码解释成另一个版本已经运行过。当前第二轮的真实实验进度见[协议](../reports/eval-v2/protocol.md)。

本文说明实际调用链、边界不变量和失败语义；运行证据与语义质量结论仍以相应评测记录为准。

## 一、从 HTTP 请求到报告

输入只有 `context_passages` 和 `generated_answer`。系统判断答案是否忠于给定材料；模型不能上网补证据。

| 节点与真实符号 | 输入 → 输出；重要不变量 | 正常路径 / 失败路径 |
| --- | --- | --- |
| [app.py](../src/grounding/app.py) `_RequestBoundary.__call__`、`_body` | ASGI 请求消息 → 受限 body；按实际字节计 1 MiB，创建内部 request ID，涵盖截止时间和断开取消 | 合法 JSON 交给 FastAPI；超大 body 返回 413，未调用模型；断开会取消并等待请求任务结束 |
| [contracts.py](../src/grounding/contracts.py) `VerifyRequest`、`StrictModel` | JSON → 严格输入对象；未知字段拒绝，32 段、每段 16,000 字符、总 96,000 字符、答案 12,000 字符 | 两个合法字段通过；负载类型或长度错误返回 422，错误不回显正文 |
| [app.py](../src/grounding/app.py) `create_app` 内的 `verify`；[config.py](../src/grounding/config.py) `Settings.from_env` | 设置和输入 → 选定 verifier；默认 minimal；项目 `.env` 可被进程环境覆盖 | 空白答案直接返回空 claims；其他输入若配置无效，返回明确配置错误 |
| [verifiers.py](../src/grounding/verifiers.py) `build_verifier`、`_BaseVerifier.verify`、`_run` | 输入 → `VerificationRun(report, stats)`；每次操作共用截止时间和调用预算 | heuristic 不调用模型；异常以 `VerificationError` 返回，附已知统计，不伪装为 U |
| 同文件 `LLMVerifier._verify` 的 minimal 分支 | 原 context + answer → 完整结构化报告；一次逻辑调用 | 模型直接抽取、判断、引用；非法引文/结构使请求失败，minimal 不做内容 repair |
| 同文件 optimized 分支、`_Extraction` | **仅 answer** → claim texts + answer quotes；锚点须是答案逐字子串，不能因为 context 不支持就漏掉答案中的事实 | 抽取后保持事实原意；锚点造假、重复 claim 或无效结构最多有限 repair，仍失败就明确报错 |
| 同文件 `_judge`、`_Judgments` | context + 固定整数 claim IDs/texts → judgments → 恢复原 claim texts | 顺序可变，但 ID 必须完整且恰好一次；漏、增、重 ID 拒绝整次输出 |
| 同文件 `_structured`、`_attempt`；[prompts.py](../src/grounding/prompts.py) | `StructuredRequest` → provider 结果 → 严格 JSON/schema/quote 验证；每次 retry/repair 都消耗同一预算 | transient transport 可按既定规则重试；超时、拒绝、不完整结果不是语义上的 UNSUPPORTED |
| [providers.py](../src/grounding/providers.py) `OpenAIProvider.generate`、`parse_response`；[codex_provider.py](../src/grounding/codex_provider.py) `CodexProvider.generate`、`_consume` | 单次外部请求 → 完整文本、模型标识和 usage；adapter 不隐藏重试 | OpenAI 普通 Responses 或 Codex 完成的流式响应进入同一解析边界；EOF/部分文本不能冒充完成；未知 usage 保留未知 |
| [contracts.py](../src/grounding/contracts.py) `Claim`、`validate_report` | 结构化 claims + 原 passages → 合法报告；S/C 有引文，U 无引文；索引严格整数，引文精确、非空、区分大小写和 Unicode | 合法逐字引用通过；`True` 索引、越界、空白或仅相似引文拒绝；这一步**不证明语义蕴含** |
| [app.py](../src/grounding/app.py) `verify`、`_error_response` | 内部运行结果 → 公开 report，或固定错误对象 | 成功只返回约定 claim/citation 字段；502/503/504 等操作失败不混入成功 claim 列表 |

三个容易混淆的地方：

- `answer_quote` 证明抽取结果有答案中的文本锚点，不证明所有事实都已抽取，也不证明 claim 改写完全保留范围。
- 引用“窗口在 10 点关闭”不能证明“窗口在 9 点关闭”。`validate_report` 只能证明引文存在，语义正确性需要评测。
- 60 秒操作上限、最多 6 次尝试、响应字节上限与输出 token 上限是不同限制。Codex 路径没有应用所请求的输出 token cap；配置如实保存 requested/effective。

默认服务的 provider/operation 截止时间为 **30/60 秒**；最终评测显式采用 **120/240 秒**。HTTP 的外层截止时间包括读取 body，verifier 的内层截止时间覆盖验证操作；不能把二者相加。`_provider_attempt` 只有在错误允许重试且预算足够时才重试；外层单次调用计时器触发的超时被设为不可重试，因为无法确认上游是否已完成。Optimized 每个结构化阶段最多一次内容修复，总调用仍受同一个六次预算约束。协议失败不会走语义上的 U 分支。

这里的 Minimal 是 LLM 单次抽取并判断。**规则切句只用于实验性的 `jev_minimal`**（以及 heuristic 的规则抽取）；不能把 Jev 的设计误说成主榜 Minimal 的实现。Jev 的低置信度降级和协议异常也不同：合法低置信度决定可按配置降级，协议异常保留为操作错误。

## 二、从数据文件到可复算实验

| 节点与真实符号 | 输入 → 输出；重要不变量 | 正常路径 / 失败路径 |
| --- | --- | --- |
| [cli.py](../src/grounding_eval/cli.py) `parser`、`main` | 命令参数 → validate/run/report；stdout 是机器可读结果 | heuristic 可离线；实际模型评测必须显式给总尝试预算；`all` 只选 dev/test |
| [dataset.py](../src/grounding_eval/dataset.py) `load_dataset`、`Case.coherent`、`validate_cases` | JSONL → 完整 cases；ID、family/split、gold、别名、引用与 v2 answer anchors 校验 | legacy 可显式加载；重复 ID、跨 split family、越界/伪造 gold 引文在推理前拒绝 |
| [provenance.py](../src/grounding_eval/provenance.py) `Manifest`、`verify_manifest`、`relative_file` | 来源与布局声明 → 验证真实 raw/license bytes、hash、Unicode 区间和 passage 映射 | 固定 raw 文本的连续切片复现 context；源被改、manifest 不匹配、路径越界或缺来源失败 |
| [runner.py](../src/grounding_eval/runner.py) `run_benchmark` | 同一冻结选择 × 方法 × track → 有种子打乱的完整 jobs | oracle 仅传 context 和 gold claim **文本**；end-to-end 仅传 context 和原 answer，不传 gold/metadata |
| 同文件预算与记录逻辑 | 每 job → 调用或 NOT_RUN 记录；启动前保守预留单 job 最大尝试数 | 已知统计扣实际 calls，未知统计扣预留；余额不足仍保存未调用 jobs 和 gold 分母，heuristic 继续 |
| 同文件 `stop_on_model_error`、`validate_saved_state` | 可选的失败即停策略 → 原失败记录与后续零调用记录 | 首个模型任务失败后不再启动模型任务，heuristic 继续；重放核对触发原因、调用顺序与零计量，旧报告未设置此选项时保持原策略 |
| [scoring.py](../src/grounding_eval/scoring.py) `score_case` | gold + 预测 → verdict-blind 一对一 strict matching、confusion、遗漏和 extra | 冻结文本/alias 只归一化空白；正确未登记改写仍可能 missing + extra；重复预测不能挑更有利 verdict 匹配 |
| 同文件 `evidence_covered` | 已对齐 claim + 实际返回引文 → 保守 evidence proxy | 任一 evidence set 全部满足即可（组间 OR、组内 AND）；缺一个跨段链接失败；通过也不是独立语义判断 |
| 同文件 `aggregate`；[reporting.py](../src/grounding_eval/reporting.py) `build_summary`、`resources` | 所有请求 → quality、slices、errors、latency、tokens | 主报告使用 `failure_inclusive_quality` 保留全部分母；旧 `quality=null` 仅说明未测，不能用来丢弃失败；未知费用不写零 |
| [uncertainty.py](../src/grounding_eval/uncertainty.py) `bootstrap`；[repeated.py](../src/grounding_eval/repeated.py) `analyze_repeated` | family 内绑定 case/repetition 的分数 → 配对差异与区间 | 重采样整个 family 及其所有重复；错配、缺少预定 population 或不同配置拒绝；16-case 三次不等于全测试集三次 |
| [runner.py](../src/grounding_eval/runner.py) `save_dataset_snapshot`、`validate_saved_state`、`regenerate_report` | 原始 cases/config/records/completion + 源快照 → 重新生成 summary | 不调用 provider；验证 hash、完整 population、状态、评分模块；损坏或 scorer 改变拒绝，旧版用固定旧提交复算 |
| [audit.py](../src/grounding_eval/audit.py) `prepare`、`lock_alignment`、`prepare_evidence`、`summarize` | 事前选择的保存输出 → 两阶段非作者审查 → 独立子集结果 | 先隐藏方法/标签/引文锁定 alignment，再看语义证据；锁定被改或清单不完整拒绝；程序不替审查员推断语义 |

当前主集有 72 个真实文档案例、668 条断言。新增 60 个案例把问题保留为 `generated_answer` 中的 `Question: ...\n\nAnswer: ...`，实际 verifier 可以看到提问范围；问题不加入 `context_passages`，也不当成证据。字段中的断言锚点以这份完整输入为准。独立复核、原始版本、裁决和许可映射见[数据卡](../reports/eval-v2/data-card.md)。RAGTruth 原始模型回答作为单独的辅助集合，不能和这些代理创作答案混称自然分布。

端到端 joint label F1 是 `2 × 对齐且标签正确的事实数 / (gold 数 + predicted 数)`。输出很少不能只靠“输出的都正确”得到高分。S/C→证据覆盖只谈需要证据的事实；C/U→S false-support 应同时看它的分母、判断覆盖和请求失败，不能靠不作答降低危险错误率后宣称变好。

`read_saved_run` 先校验 config/records/cases 的哈希，再检查 `SCORING_FILES` 的实际文件指纹、数据快照和完整运行状态。内部发现 `scorer_version_changed` 会被统一包装为公开的 `run_artifact_invalid`；CLI 退出码为 2。只看错误字符串不能区分所有损坏原因，需要核对冻结指纹。`regenerate_report` 会写回 `summary.json`，所以学习时先复制 run；不是所有离线 replay 都只读。复算保存输出能验证分数与记录一致，不能证明原模型输出或 AI 审阅本身正确，也不能复现下一次非确定模型调用。

阅读顺序建议：先追一个 `examples/wal.json` 请求；再读 `tests/service/test_verifiers.py` 的固定 ID 与失败用例；最后追 `tests/evaluation/fixtures/measurement-calibration.jsonl` 的独立评分边界和一个保存 run。涉及真实模型的操作需明确预算；本导读不要求为学习额外消耗额度。
