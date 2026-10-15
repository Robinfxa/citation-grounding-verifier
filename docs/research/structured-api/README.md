# 结构化 API 与可靠性研究

核查日期：2026-10-15。角色：有界 Researcher；本文件是证据与建议，采纳由父 Director 决定。只研究任务已有的 `/verify` 服务；没有调用真实模型、读取项目密钥或修改产品代码。以下接口及预算是建议合同，不是已完成的实现或实测结果。

## 建议结论

本项目可以直接用一个长期存活的 `httpx.AsyncClient` 调用官方 `POST https://api.openai.com/v1/responses`，用 Pydantic 生成简单 JSON Schema，再用本地严格解析和精确引文检查守门。无需为这一条请求路径增加 OpenAI SDK、Instructor、Guardrails 或通用 LLM 框架。

OpenAI 推荐新项目使用 Responses，Chat Completions 仍受支持。两者都能使用 Structured Outputs；本任务没有需要同时维护两套接口的证据。Responses 的类型化 `output` 稍多解析工作，但小型无状态服务不必采用它的会话、工具、后台运行或检索能力。[OpenAI 迁移指南](https://developers.openai.com/api/docs/guides/migrate-to-responses)

严格 Schema 约束结构，不能证明引文真实存在、结论被蕴含、断言分解完整或没有遗漏。官方说明结构化结果仍会犯错，拒绝和输出截断也需要单独处理。因此成功边界应是“完整上游响应 → 严格结构解析 → 请求相关的精确引文守门 → 返回报告”。语义质量仍须由真实标注评测约束。[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

## 8 组一手来源

等级含义：E1 为官方接口/语言文档；E2 为项目当前实现或作者示例；P 为本地合成输入探针。E2 能证明实现方式，不能证明模型质量。链接均已实际打开；页面是可变文档，未声称其内容等同未来安装版本。

| 来源 | 已核查的事实 | 限制与本项目用途 |
| --- | --- | --- |
| S1 — [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)，E1 | Python 有 Pydantic 解析辅助；REST 支持 `text.format`；Schema 有支持子集；拒绝、未完成及内容错误仍须处理。 | 不能把 Schema 保证扩大成语义保证。用 REST 也可获得相同结构约束。 |
| S2 — [OpenAI Create a model response](https://developers.openai.com/api/reference/resources/responses/methods/create)，E1 | `output` 是不同类型条目的数组；生成有独立 `status`；`max_output_tokens` 包括可见输出和推理 token；有 `usage` 与 `incomplete_details`。 | 该页过大，网页读取器失败后已用公开 HTTPS 页面成功读取正文；没有使用认证。不能假定第一个 `output` 就是最终文本。 |
| S3 — [OpenAI Responses 迁移指南](https://developers.openai.com/api/docs/guides/migrate-to-responses)，E1 | 新项目推荐 Responses，Chat Completions 继续支持；REST 的结构化格式从 `response_format` 移至 `text.format`；`output_text` 是 SDK 辅助属性；可以设置 `store:false`。 | 文档中的通用模型优势不证明本数据集更准、更快或更便宜，需实测。 |
| S4 — Pydantic [strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)、[conversion table](https://pydantic.dev/docs/validation/latest/concepts/conversion_table/)、[validators](https://pydantic.dev/docs/validation/latest/concepts/validators/)，E1 | 默认可能发生类型转换；严格整数排除 bool；验证方法支持显式 context；`assert` 在优化运行时可能被跳过。 | 使用 Pydantic v2 的 `model_validate_json` / `model_validate`，运行守门抛明确校验错误，不依赖 `assert`。 |
| S5 — FastAPI [Pydantic 迁移](https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/)、[response model](https://fastapi.tiangolo.com/tutorial/response-model/)、[handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)，E1 | FastAPI 0.128.0 已移除 `pydantic.v1` 支持；返回模型会校验输出；请求验证异常可持有原始 body。 | 新服务直接用 v2；框架输出校验不能替代 passage 相关守门。不要复制文档中回传 body 或打印完整异常的调试示例。 |
| S6 — HTTPX [timeouts](https://www.python-httpx.org/advanced/timeouts/)、[async support](https://www.python-httpx.org/async/)、[transports](https://www.python-httpx.org/advanced/transports/)，E1 | 有 connect/read/write/pool 四类超时；read 是等待数据块的时限；复用客户端才有连接池收益；传输层 retries 只覆盖连接错误/连接超时。 | 超时不是整次验证的总时限；429/5xx/格式修复需要本应用统一控制。优先现有 HTTPX，不为两次重试增加依赖。 |
| S7 — Jason Liu 的 [Verifying LLM Citations with Pydantic](https://python.useinstructor.com/blog/2023/11/18/validate-citations/)（2023-11-18），[当前 CitationMixin 文档](https://python.useinstructor.com/concepts/citation/)及[展示的实现](https://python.useinstructor.com/api/)，E2 | 作者示例用子串检查与 validation context；当前 mixin 源码在 `instructor/v2/dsl/citation.py`，可模糊匹配最多 5 字符错误、改写成找到的原文并丢弃找不到的引用；缺失 context 时直接返回。文档明确只校验引用，不校验事实。 | 借用本地守门和分离语义验证的思路。不可直接借 mixin 的容错、跨来源搜索或静默删除行为。本文不建议新增该依赖，因此未作安装/许可审批或兼容承诺。 |
| S8 — [Python 3.11 Built-in Types](https://docs.python.org/3.11/library/stdtypes.html)，E1；[本地探针](boundary-probes.md)，P | `str` 按 Unicode code point 索引；`find` 给出最先匹配位置；bool 属于 int 的子类；负索引有效；空字符串是任意字符串的子串。 | 这些语言行为足以产生“伪合法引用”。探针只证明标准库边界，不证明 HTTP 服务或供应商行为。 |

## 最小 REST 请求和响应合同

以下是字段清单；`model`、输出上限及总预算由项目配置固定。JSON Schema 来自同一份 Pydantic v2 模型，避免手写 Schema 与本地类型漂移。

| 请求字段 | 建议 |
| --- | --- |
| `model` | 用户配置的精确模型 ID；评测元数据记录请求模型名与上游实际返回模型名，不自动换模型。 |
| `input` | 两条 message：`system` 放核验规则；`user` 的 `content` 是 JSON 编码的 `{context_passages, generated_answer}`。将内容声明为待分析数据，保留 passage 原顺序和原字符。 |
| `text.format` | `{type:"json_schema", name:"verification_report", strict:true, schema:...}`。 |
| `store` | 明确 `false`，保持各 case 独立。它不是“供应商绝不留存任何数据”的保证。 |
| `stream` | `false`，完整接收后才解析。 |
| `max_output_tokens` | 有界且可配置；推理 token 也可能消耗此额度，不能仅按最终 JSON 长度估计。 |
| 工具和状态 | 不添加 `tools`、`previous_response_id`、conversation 或 background；本任务只需无状态结构化文本。 |

**Schema 限制：**顶层用对象，所有输出字段必填，所有对象禁止额外字段。用简单对象、数组、字符串、整数和枚举；不让模型生成可选 offsets。Pydantic 的严格类型规则与动态 passage 上界仍在本地执行。固定模型后核对生成的 Schema 属于该模型支持子集，不能假定 Pydantic 的所有约束都会被提供方执行。S1/S4 支持这些边界；具体字段选择是研究建议。

**原始 REST JSON 与 SDK 不同：**不要读取顶层 `data["output_text"]`。先检查 HTTP 状态与完整 JSON，再要求 `status == "completed"`；遍历 `output` 中 `type == "message"` 的 `content`，检查 `type == "refusal"`，读取 `type == "output_text"` 的 `text`。推理条目不是报告。对于本任务，建议只接受一个完整最终文本对象；多条最终文本、缺失文本或意外工具输出归为上游协议错误，不用拼接掩盖歧义。`output`/`content` 自身的类型也须检查，不能只靠索引取第一项。S1/S2/S3 支持字段语义；只接受一个结果是本项目的收窄建议。

`incomplete` 即使带部分 JSON 也不成功；记录安全分类 `truncated` 或 `content_filtered`，不要解析可用前缀。`failed`、`cancelled`、`queued`、`in_progress` 或未知状态都不应被当作完整同步结果。拒绝、无 JSON、JSON 解码错误、Schema 校验失败和引文不合法必须有各自分类；它们不属于 `UNSUPPORTED`。S1/S2 支持状态边界。

## 本地精确引文合同

建议用一个显式接收 `report` 和原始 `context_passages` 的短小纯函数，放在任何报告离开服务前。Pydantic 负责静态结构，纯函数负责请求相关关系；不要引入隐式全局 context 或自定义构造器来传请求。若选择 Pydantic context，也必须显式调用带 context 的验证方法，不能认为普通 `Model(...)` 或框架响应序列化会自动带上来源。S4 支持两者的能力边界。

| 条件 | 必须满足的结果 |
| --- | --- |
| 引用 index 是 `true`、`false`、`0.0` 或 `"0"` | 拒绝；使用严格整数，守门不可仅写 `isinstance(index, int)`。 |
| index 为 -1 或等于 passage 数 | 拒绝；必须先验证 `0 <= index < len(passages)`，再访问列表。 |
| quote 为空或仅空白 | 拒绝作为证据；仅判定“是否为空白”，不能先 strip 再保存改写后的引用。 |
| quote 是原始 `passages[index]` 的非空精确子串 | 才通过引文存在检查；其他 passage 恰好含相同句子不弥补错误 index。 |
| quote 改写空格、换行、标点、大小写或 Unicode 规范化形式 | 不匹配就拒绝；不做 fuzzy search、normalize、casefold 或静默改写。 |
| quote 只出现在多个 passage 的拼接边界 | 拒绝；每个 passage 独立检查。 |
| `SUPPORTED` / `CONTRADICTED` 无合法引用 | 拒绝该次报告。 |
| `UNSUPPORTED` 带引用 | 拒绝该次报告。 |
| 一条报告里只有某条引用不合法 | 使本次尝试失败；可在剩余预算内修复，不静默丢引用或改 verdict。 |
| 引用存在但不蕴含断言 | 引文守门不能确认正确；语义判断和标注评测仍须覆盖。 |

若将来提供 offsets，建议由服务计算，采用原始解码字符串的 **0-based Unicode code point、半开区间 `[start_char,end_char)`**；要求 `0 <= start < end <= len(passage)` 且切片等于 quote。重复引用选最先出现的位置并公开说明。JavaScript 的 UTF-16 单元和 UTF-8 字节都不是这个单位，不能直接互换。本地 Python 3.11.9 合成探针得到同一引用的三种范围分别为 `[5,7)`、`[6,8)` 和 `[8,11)`，见 [探针证据](boundary-probes.md)。offsets 是可选能力，当前可以不构建。

## 超时、退避和失败语义建议

先用一个总预算覆盖排队、分解、核验、退避和输出修复，使用单调时钟。HTTPX 的 read timeout 只约束等数据块的时间，仍需最外层异步总时限。连接池复用一个客户端，在服务 lifespan 关闭它。取消后停止后续重试。S6 支持 HTTPX 行为；以下数值只是可调起点，尚未由模型时延验证。

- 总截止时间可先设 45 秒；单次网络等待上限不超过 20 秒，connect 3 秒、write 5 秒、pool 1 秒；每次再裁到剩余总预算。
- 单次 `/verify` 的上游请求总数至多 3；即使采用两步分解/核验，也共用这 3 次。网络重试与输出修复都扣同一计数，不各自乘出新预算。
- 只允许有限退避，例如首次 0.25–1 秒随机等待；`Retry-After` 若超过剩余预算则终止。不要为少量重试引入 Tenacity。
- 连接/超时、408、429、5xx 可在剩余预算内重试。401/403、错误模型、错误参数或 Schema 不支持应直接暴露为配置/上游错误。429 是提供方限流，不是断言不受支持。
- Schema 或精确引文失败最多使用一次修复机会，传递稳定错误代码和字段位置；仍失败就报错。拒绝不尝试规避式修复；截断不接受部分输出，也不无限加 token 重试。
- HTTPX transport retries 保持 0，由这一层管理。未来若换 SDK/Instructor，先关闭其隐式重试，避免总预算失真。

建议 HTTP 映射如下；具体状态码由父 Director 统一成公开合同，稳定分类比抄上游消息更重要。

| 情况 | 建议结果 |
| --- | --- |
| 请求缺字段、错类型、超过公开输入限额 | 422 + 安全的 `invalid_request`；不回显 body。 |
| 合法空答案 / 成功识别到无事实断言 | 200 + `claims:[]`；前者可确定性快捷返回，后者必须来自成功处理。 |
| 空 context + 非空答案 | 正常执行断言识别；可验证的事实缺证据才为 `UNSUPPORTED`，不因空 context 隐藏分解失败。 |
| 拒绝、截断、无效 JSON、结构或引文不合法且修复耗尽 | 502 + 对应分类；没有伪成功报告。 |
| 上游不可用、限流耗尽、服务缺少模型配置 | 503 + 对应分类。 |
| 总预算耗尽 | 504 + `deadline_exceeded`。 |
| 自身程序违反已验证响应模型 | 500；不要转成模型的语义 verdict。 |

输入限额应涵盖 passage 个数、总字符、答案长度与输出断言/引用个数；超过限额应明确拒绝，不静默截断来源。系统指令应说明来源和答案均为不可信数据，只能依据来源判断；没有工具和外部检索权限。Prompt 不能保证抵抗注入，应把来源内恶意指令纳入评测。

## 本地安全日志与真实计量

本节依据项目 Overlay 的现有隐私约束，未增加遥测平台需求。本次为研究文档，不修改运行路径；产品实施仍需执行项目的 local-logging-reviewer 技能。

日志只用白名单：内部生成的 request ID、阶段、结果分类、耗时、调用/修复次数与数值计量。不要记录 passage、答案、引用、原始响应、Authorization、完整请求/响应、URL 中的秘密、原始异常或 Pydantic `errors()` 的 input/ctx。异常的字符串和 traceback 也可能含输入；用明确枚举分类替代。FastAPI 和 Pydantic 文档里的调试输出不是本项目的安全默认值。

实施后用合成秘密标记贯穿成功、无效请求、无效模型输出、超时、429 和连接故障，检查真实 HTTP/CLI 结果与捕获日志：错误分类能定位阶段，秘密标记不出现，重试次数不超预算。日志独立核验者应只读实现并运行真实路径；mock provider 证据不能外推成真实 LLM 质量或费用证据。

当前没有用户项目凭据，**真实模型 tokens、时延、成本和质量均未测量**。未来 benchmark 建议为每个 case 记录：

- 模型配置、上游返回模型名、接口、依赖版本、prompt/schema/dataset 版本及运行时间；只在评测元数据中记录，不扩大运行日志白名单。
- 每次尝试的墙钟耗时、是否成功/拒绝/截断/网络失败、重试与修复次数；端到端耗时包含失败和等待。报告 p50/p95、样本数及失败率，不能只统计最终成功的一次调用。
- 原始 `usage` 中的数值白名单：`input_tokens`、`output_tokens`、`total_tokens` 及存在时的 cached/cache-write/reasoning 明细。明细是细分，不能与总数重复相加。S2 定义这些字段；可选字段按实际响应处理。
- 按固定日期、精确模型及官方价格快照估算所有尝试的费用，说明缓存/推理计费口径。供应商失败时未返回 usage，应记 `null` / unknown，不能写 0；此时已知 token 合计不等于全部已计费 token。无需为此构建在线价格抓取服务。
- 非 LLM baseline 的模型 token 成本可明确为 0；没有执行的 LLM 路径标记 `not_run`，不要把无凭据状态画成零成本成功。

## 应借用和不应构建的内容

借用现有 Python 3.11+、FastAPI、Pydantic v2、HTTPX 与 pytest；只自写请求封装、确定性守门和共享预算。当前 FastAPI 官方迁移页已经排除 v1 混用；依赖锁定后在不调用模型的条件下验证 schema、HTTPX 模拟传输和真实 ASGI/CLI 路径，用户配置项目环境后再做最小真实集成与质量评测。

Instructor 作者的“先做确定性引用检查，再评估语义”值得借鉴；逐引用再调用一个模型只为判断子串是否存在，会增加成本并削弱确定性。现有 mixin 宽容匹配不适用于本任务，不为此新增依赖或复制其代码。

没有证据支持现在构建通用 provider 注册中心、动态 model router、agent 编排、向量库、数据库、跨请求语义缓存、自动模糊修复引用、多个框架套用的重试、熔断/队列平台、遥测上传或第二套 SDK 适配。重试、限流和 Schema 生成需要存在，但保持一处短路径即可。

尚未解决的实测问题只有用户环境配置后才能回答：选定模型能否接受最终生成的 Schema、合适的输出上限和时限、两步分解是否改善完整性，以及修复收益能否抵消 token/时延开销。文档证据不能替代这些实验。
