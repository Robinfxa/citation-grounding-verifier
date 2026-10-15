# Codex 额度 Provider 研究

核查日期：2026-10-15。角色：有界 Researcher；本文是证据和建议，是否采纳由父 Director 决定。研究没有调用模型，没有读取 `~/.codex/auth.json` 或其他凭据文件，也没有安装 Hermes。

## 结论

建议将“使用 ChatGPT 套餐额度”做成独立、明确启用的 provider。长期实现优先采用 OpenAI 为本地开源应用公布的 **Sign in with ChatGPT (SIWC) + 公共 Responses API**。不要复制 Hermes 的 Codex 私有 OAuth/内部 API 路径，也不要从 Codex CLI 凭据文件导入 token。

OpenAI 当前为本地开源工具公布了用户授权流程和额度使用合同：新客户端动态注册、用户明确授权 `chatgpt.tokens.use.direct`，然后用 access token 请求 `https://api.openai.com/v1/responses`。此路径可严格限制为一次无工具的结构化核验请求，并且不需要应用读取 Codex CLI 的认证材料。[SIWC 总览](https://developers.openai.com/siwc/token-sharing-open-source)、[注册与登录](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)、[模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)

适用边界是本地运行的开源工具或个人项目。若把服务改为收费或远程托管产品，不能仅凭代码开源就假定可使用这条额度路径；官方文档要求先提交 interest form。

Codex CLI 的 `codex exec` 是可选的个人本机入口。它能使用现成的 ChatGPT 登录，也提供 `--output-schema`、`--output-last-message`、`--ephemeral` 和只读沙箱；但它是代码代理命令，能运行本地工具，且没有在本机 `codex exec --help` 中看到关闭所有工具的开关。对含有用户任意文本、可能包含提示注入的核验任务，不应把代理 CLI 当作纯模型调用边界。若作为本地试验选项，必须隔离工作目录、只读运行、使用临时会话、检查最终文件并继续执行本地引文守门。[Codex CLI 命令参考](https://learn.chatgpt.com/docs/cli/reference)、[Codex CLI 自动化示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)

Hermes 值得借鉴的是 provider 与 auth 分层、刷新互斥、轮换 token 的事务写入、类型化错误和有限重试。其公开 Codex provider 配置指向 `https://chatgpt.com/backend-api/codex`，并使用自己的 OAuth 流程和凭据存储；这些不是 OpenAI 当前给本项目发布的公共接口合同。[Hermes provider profile（固定 commit）](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/plugins/model-providers/openai-codex/__init__.py)、[Hermes 作者文档（固定 commit）](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/website/docs/integrations/providers.md)

## 与现有 Responses 研究的接口差异

现有 [结构化 API 研究](../structured-api/README.md)面向 API key provider，建议非流式调用、`stream: false`、`max_output_tokens` 和通用 `system` 消息。SIWC 当前预览合同要求 `store: false`、`stream: true`、每次发送完整 `input`，并用 `instructions` 或 developer message；它明确列出 `max_output_tokens`、`temperature`、`top_p` 等字段为不支持。显式 `system` message 也会被拒绝。因此 Codex/SIWC 需要自己的请求构造和流解析分支，不能只替换 API key。[SIWC 预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

SIWC 专页没有明确确认 `text.format` 严格 JSON Schema 在该预览路径上的兼容性。普通 Responses API 支持结构化输出，但不能据此推定 SIWC 路由也接受相同参数。实施时先加离线合同覆盖；首次有意进行真实集成时，再用最小请求确认所选账户、模型和 schema 能完成一次 `response.completed`。在此之前，把该能力记为未核实；无论上游 schema 是否可用，都必须保留本地严格解析和逐条精确 quote 检查。

## 建议的 SIWC provider 合同

- **授权分层：**为本应用创建自己的 SIWC 注册，不复用 Hermes 或 Codex CLI 的 client ID/token。首次注册使用 `dynamic_agent_client` 和稳定的 `ext_agent_host_id`；保存 OpenAI 返回的 issued `client_id`，后续针对同一账号/workspace 复用。每个 app 安装的 host ID 独立且不包含用户身份。请求身份 scope 与 `offline_access resource.invoke chatgpt.tokens.use.direct`；只有实际获授 `chatgpt.tokens.use.direct` 才允许发送推理请求。[注册流程](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- **模型选择：**若需要发现模型，用获授权 token 查询 `GET /v1/models`，显示账户返回的可见模型 slug；将用户选定的确切 slug 固定到本次评测元数据。模型目录不等于最终 entitlement，最终以该请求是否成功完成为准。不可把某个账户能用的模型硬编码为所有账户可用。[模型发现](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)、[app-server 模型说明](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- **调用：**只调用 `POST https://api.openai.com/v1/responses`，不调用 `chatgpt.com/backend-api/codex`。发送 `store: false`、`stream: true`、完整 `input`，并用 `instructions` 或 developer message 提供规则。省略 SIWC 专页标记不支持的参数和所有未证实能力；不要附加 shell、MCP、web search 或其他工具。
- **完成解析：**按 SSE 事件类型解析；只在完整收到 `response.completed` 后接收结果。将 `response.output_text.delta` 拼成候选文本；`response.failed`、`response.incomplete`、显式 error、断流或总时限结束一律作为上游失败，不把部分 JSON 当成功。遇到 refusal 也单独分类。[SIWC 流程](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)、[流事件定义](https://developers.openai.com/api/reference/resources/responses/streaming-events)
- **确定性守门：**用 Pydantic 严格解析本地报告结构，再逐条检查 verdict 与 citations 关系、index 是严格整数且在范围内、quote 非空且是对应原始 passage 的精确子串；不做 strip、规范化、模糊匹配或静默删除。只有所有守门都通过才返回成功。模型 schema 约束和 quote 存在检查都不能证明语义蕴含或断言没有遗漏。
- **额度与 usage：**只记录上游 `response.completed.response.usage` 实际给出的 token 数值；字段缺失/null 就报告 `unknown`，不能报 0。token 数不能换算成 ChatGPT 套餐剩余额度、信用点或美元成本。使用套餐的应用额度与 Codex/ChatGPT Work 额度共享；用户在 Settings → Usage 查看使用量和设置该 app 的上限。服务不猜 reset 时间，也不宣称有独立额度。[使用与管理](https://learn.chatgpt.com/docs/sign-in-with-chatgpt)
- **失败：**额度错误 `subscription_sharing_usage_limit_exceeded`（429）停止新请求并提示用户查看 Settings → Usage，不重试，也不暗示整个套餐额度耗尽；该错误也可能是 app 自身上限。`subscription_sharing_unsupported_capability`（400）修正请求，不重放相同 body。`503` usage unavailable 可在剩余总预算内有限退避。401/403 显示登录、scope、账户/workspace 或策略问题；不得静默换 API key 或另一个付费 provider。[官方错误恢复表](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- **刷新：**access token 当前有效 1 小时；refresh token 当前有效 30 天，每次成功刷新会返回新的 refresh token。保存最新整组 token 与 expiry；对同一个 profile 串行刷新，避免并发复用已轮换 token。官方 SIWC 的 token refresh endpoint、client_id 和 resource 参数以官方页面为准，不照抄 Hermes 常量。[Token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference)、[Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- **限时与并发：**可沿用现有结构化 API 研究的总预算作为初始值（45 秒），但这不是 Codex 实测时延。每个 HTTP 请求绑定该总截止时间和 HTTPX 连接/读取超时；ASGI 取消时关闭 SSE 响应，停止后续重试。先把 Codex provider 并发限制设为 1，避免并发请求突发消耗额度，再通过真实本地证据调高。最多一次 schema/quote 修复，且共用总时限和调用预算；不对 401/403/额度 429/unsupported capability/partial stream 自动重试。对流已开始后的断线不自动整单重放，以免重复计费。

## `codex exec` 本机 provider 对照

本机 `codex-cli 0.159.2` 的 `codex exec --help` 确认这些参数可用：`--model`、`--sandbox read-only`、`--ephemeral`、`--json`、`--output-schema`、`--output-last-message`，提示可从 stdin 读 prompt。`codex login status` 返回 `Logged in using ChatGPT`。只读了 CLI help/status；未读取 auth store，也未执行模型调用。该状态只描述本机，不能当成其他安装的前提。

如果父 Director 仍选择 CLI 方案，最小调用边界建议是：显式 `provider=codex_cli` 和精确模型配置；用参数数组启动 `codex`（不经 shell）；将完整 prompt 从 stdin 输入；`cwd` 使用空的临时目录；设置 `--ephemeral --sandbox read-only --ignore-user-config --skip-git-repo-check --model <model> --output-schema <temp-schema> --output-last-message <temp-result>`。`--ignore-user-config` 不关闭认证，官方说明认证仍使用 `CODEX_HOME`；它用于避免用户配置改变运行行为。进程超时、取消时终止子进程及其进程组；只在退出码为 0、最终文件存在且 JSON/本地 schema/quote 校验通过时返回报告。可加 `--json` 做有大小上限的 JSONL 诊断，但最终文件应是唯一报告来源。不要向调用方返回 stdout/stderr 原文。

这一路仍有关键限制：`codex exec` 可能运行本地工具；本机帮助中没有“禁用所有工具”的选项；如果认证状态是 API key，usage 会走 API 计费而不是套餐额度。必须 fail closed 确认 ChatGPT 登录，绑定空工作目录、只读沙箱、ephemeral，禁止自动换认证模式。因为报告输入是任意文本，直接无工具 Responses provider 的安全边界更清楚。Codex CLI 的 `--output-schema` 与最终 JSON 仍不能替代本地精确 quote 检查。官方 `codex exec` cookbook 示例使用 `OPENAI_API_KEY`，只用于证明 CLI schema/output 文件用法，不证明 ChatGPT 套餐授权。[CLI 参考](https://learn.chatgpt.com/docs/cli/reference)、[CLI 示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)

## 离线合同验证建议

不调用真实模型的测试应覆盖：

1. OAuth 返回缺少 `chatgpt.tokens.use.direct`、access token 过期、刷新成功并轮换 refresh token、两个并发请求只触发一次 profile 刷新、终结刷新错误与临时错误分类。
2. SSE 正常 delta + completed；failed、incomplete、refusal、JSONL/SSE 畸形行、缺少终结事件、早断流、超时和 task cancellation。确保 partial output 不会变成功。
3. upstream 429 配额耗尽、unsupported capability、401/403、503 的映射与重试预算；额度 429 不重试，不从错误正文猜 reset。
4. Schema 正常但 quote 错误、passage index 为 bool/string/float/负数/越界、unsupported 带 citation、supported 缺 citation，以及内容对抗性输入。所有无效上游报告必须在 HTTP/CLI 边界失败关闭。
5. 若有 CLI backend，mock `create_subprocess_exec`：校验参数数组、stdin、不触发真 `codex`、退出码与缺文件、无效 JSON、JSONL 超限、超时/取消杀子进程。不要让 CI 执行当前登录用户的 CLI。
6. 用合成秘密标记经过成功和故障路径，确认日志不包含 passage、generated answer、quote、token、OAuth URL、原始 stderr/异常正文。

## 尚待父 Director 决策

1. 本项目是否要支持其他人本机的 SIWC 登录与刷新？若是，按官方 SIWC 注册/本地凭据存储实施；不能假定运行服务的机器就是用户的 Codex CLI 登录机器。
2. SIWC 预览是否接受本项目生成的严格 JSON Schema、所有所选模型是否兼容？公开专页未确认；研究没有消耗额度验证。真实集成阶段需要最小授权探针，并记录当时 CLI/模型/schema 版本。
3. 要不要保留个人开发用 Codex CLI adapter？如保留，需明确只用于 loopback 的本机部署，并评估模型触发本地工具的能力是否可被彻底关闭。若无法证明 no-tools，则不让它处理不可信请求。

来源与本机非敏感探针记录见 [sources-and-probes.md](sources-and-probes.md)。
