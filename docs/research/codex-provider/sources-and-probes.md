# 来源与探针记录

核查日期：2026-10-15。只用公开文档、公开源码和本机非敏感 CLI 命令。没有发起推理请求，也没有打开、读取、复制或打印 Codex/Hermes 凭据。

## Hermes Agent 一手源码

本次核对的 Hermes 仓库 `NousResearch/hermes-agent` 固定在 commit [`7bda2a3368024f7ae1c70cef16583e7c2c891674`](https://github.com/NousResearch/hermes-agent/commit/7bda2a3368024f7ae1c70cef16583e7c2c891674)。下列文件都从该 commit 的页面或公开 raw 源码实际读取；不依赖 `main` 的浮动内容。

| 文件 | 核实内容 | 对本项目的用法/限制 |
| --- | --- | --- |
| [`plugins/model-providers/openai-codex/__init__.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/plugins/model-providers/openai-codex/__init__.py) | 单独注册 `openai-codex` provider profile；标记 `api_mode="codex_responses"`、`auth_type="oauth_external"`，无 API key env，base URL 是 `https://chatgpt.com/backend-api/codex`。 | 复用“provider profile 与认证分离”的架构思路；不复用私有 host、接口或凭据流程。 |
| [`hermes_cli/auth_codex.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/hermes_cli/auth_codex.py) | 独立保存 Hermes Codex token；对过期 token 刷新；持有 provider store 锁完成重读、刷新、轮换 token 写回，处理并发刷新；可选择性从 Codex CLI 登录状态恢复，但源码会读 `~/.codex/auth.json`；另有 Codex quota probe、429 cooldown 与 `Retry-After` 分类。 | 借鉴刷新互斥、事务式轮换和把“配额耗尽”与“需要重新登录”分开的错误分类。不得复制 CLI 凭据导入，也不建议照搬 probe 使用的内部 usage 路径。 |
| [`hermes_cli/auth_codex_browser.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/hermes_cli/auth_codex_browser.py) | Codex 浏览器登录是可选的 loopback authorization-code + PKCE 流程；默认设备码登录在另一 auth 模块；回调 host/port/path 与注册 client 相绑。 | OAuth 应实现 state、PKCE、固定本机 callback 和授权校验。Hermes 使用的 Codex client 配置不等于本项目可复用的正式 client。 |
| [`agent/codex_responses_adapter.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/agent/codex_responses_adapter.py) 与 [`agent/transports/codex.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/agent/transports/codex.py) | 适配器处理 Responses 项目/消息、tool call、incomplete/failure、错误归一化和续传等 agent 运行时复杂度；Codex transport 单独处理 route header 和 Responses 语义。 | 这是面向长时 agent 的大适配层；本项目一次无工具核验不应移植其复杂度。复用“完整完成状态才算成功”和显式异常分类。 |
| [`hermes_cli/codex_models.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/hermes_cli/codex_models.py) | 从 Codex route 获取可见模型，同时有 curated 离线回退；注释指出有账户/计划门控模型、`supported_in_api` 不等同 Codex route 的可用性。 | 说明 provider 与 model catalog 要绑定 route/账号。项目优先使用官方 SIWC 的账户模型目录；静态模型表只能是提示，不能作 entitlement 证明。 |
| [`tests/e2e/core/providers/test_openai_responses.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/tests/e2e/core/providers/test_openai_responses.py) 与 [`tests/e2e/core/providers/test_openai_codex_pool.py`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/tests/e2e/core/providers/test_openai_codex_pool.py) | 有本地 fake Responses/token server、断流/tool 事件和多账号 token 轮换/429 cooldown 的故障合同测试。 | 借鉴 fake provider 离线测试方式；本次没有安装 Hermes，也没有运行这些测试。 |
| [`website/docs/integrations/providers.md`](https://github.com/NousResearch/hermes-agent/blob/7bda2a3368024f7ae1c70cef16583e7c2c891674/website/docs/integrations/providers.md) | 作者文档描述设备码为默认登录、loopback PKCE 为可选路径、凭据位于 Hermes 自己的 auth store，并可能导入 CLI credential。该固定版本的作者文档还明确写明 Codex 具体计划资格与额度消耗语义“not currently documented”。 | 这是 Hermes 自己的使用说明，不是 OpenAI 的公共集成承诺。OpenAI 当前的 SIWC 文档提供了更明确的公开合同。 |

Hermes 文档解释其 auth/refresh 设计，但不足以证实其私有 Codex route 长期稳定，或能用公开配额端点准确展示剩余使用量。源码中的 `/api/codex/usage` / `wham/usage` probe 属 Codex 内部路径；本项目不应依赖或公开该路径。

## OpenAI 官方 SIWC 文档

以下页面属于官方开发者文档和 ChatGPT Learn，均已实际打开阅读。

| 页面 | 支持的事实 |
| --- | --- |
| [SIWC overview](https://developers.openai.com/siwc/token-sharing-open-source) | ChatGPT 套餐授权是单独 scope；为本地 OSS app 明确给出流程；client 注册与 host ID 分开；远程托管或收费应用应先提交 interest form。 |
| [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in) | `dynamic_agent_client` 只用于首次动态注册，回调签发的 `client_id` 要保存；新登录需随机 state/nonce/PKCE；resource 为 `https://api.openai.com/v1`；仅获授权后才可用。 |
| [Profiles and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) | refresh 需 issued client id、最新 rotating refresh token 与 `resource`；同一会话刷新需串行；token 不得进源码、日志、分析或支持记录；用户可在 ChatGPT Settings 管理应用和额度。 |
| [Token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference) | 当前 access token 生命周期 1 小时，refresh token 30 天，成功 refresh 会替换 refresh token；token 中 OpenAI auth metadata 应作 opaque data 处理。 |
| [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) | 用授权 token 请求 `/v1/models`；推理用 `POST /v1/responses`；该路径要求 `store:false`、`stream:true`，并以 `response.completed` 为成功终点。 |
| [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) | 公开列出不支持参数、禁止显式 system role message；app-server 使用 HTTP/SSE，也可能提供本地 shell/MCP/子 agent 工具；app-server 不接受任意 Responses 参数。 |
| [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) | `subscription_sharing_usage_limit_exceeded` 是 429，要停止并指向 Settings → Usage，不能推断整个套餐耗尽或 reset；unsupported capability 是 400；不能静默切换到另一付费路径。 |
| [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server) | app-server 可用授权 OAuth token 访问 Responses；其 model catalog 可能只是 bundled catalog，不能当权限检查；成功 inference 才确认该模型该请求可用。 |
| [Sign in with ChatGPT on Learn](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) | app 额度计入用户现有 Codex/ChatGPT Work 使用额度；app cap 是总额度的上限，不是额外独立 allowance；用户在 Settings → Usage 查看与管理。 |
| [Codex CLI auth on Learn](https://learn.chatgpt.com/docs/auth) 与 [CLI reference](https://learn.chatgpt.com/docs/cli/reference) | CLI 支持 ChatGPT 与 API-key 两种 auth；CLI 可非交互运行，支持 output schema/final-output 文件、ephemeral session、只读 sandbox、stdin prompt 和 JSONL 输出。`--ignore-user-config` 不读取 CLI config，但认证仍使用 `CODEX_HOME`。 |
| [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events) | `response.completed` 对象包含 usage 字段；失败流中 usage 可为 null。可记录 API 实际返回 token 计量，但它不等于套餐剩余额度。 |
| [OpenAI Codex CLI structured-output cookbook](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex) | 示范 `codex exec --output-schema`、`--output-last-message` 和结构化脚本化输出；示例明确要求 `OPENAI_API_KEY`，因此只作为 CLI 参数证据，不作为 ChatGPT plan 登录证据。 |

### 官方 SIWC scope 和错误边界摘要

推理授权需要 `resource.invoke` 与 `chatgpt.tokens.use.direct`，另有身份 scope 和 `offline_access`。只成功身份认证但没有 plan usage scope 时，应该保留登录但禁用额度推理。API error 分类应保留 HTTP status、error code/param（存在时）和 request ID；不可将原始 error message 回显给用户或写入日志。`subscription_sharing_usage_limit_exceeded` 可能是 app-specific 限额，不表示整份订阅额度已尽，也没有提供可从该错误推断的 reset time。

## Codex CLI 本机只读探针

研究时执行的命令和结果：

| 命令 | 结果 | 证据边界 |
| --- | --- | --- |
| `command -v codex` | `/usr/local/bin/codex` | 仅本机安装路径。 |
| `codex --version` | `codex-cli 0.159.2` | 版本可能变化；provider 应在启动时检查/展示版本。 |
| `codex exec --help` | 包含 `--model`、`--sandbox`、`--output-schema`、`--json`、`-o`、`--ephemeral`、`--ignore-user-config`、stdin prompt 等选项。 | 只读帮助，没有运行执行命令。 |
| `codex login status` | 退出码 0，输出 `Logged in using ChatGPT` | 只检查状态，输出没有邮箱；没有打开认证文件。仅验证当前本机 login mode。 |

以上不证明任意模型对该账户有权限，不证明 schema 在 SIWC 路由有效，也没有证明请求耗时、套餐计量或语义质量。没有运行 `codex exec <prompt>`、`codex app-server`、Hermes OAuth、token refresh 或 Responses API 请求。

## 项目内证据与未确认事项

- [结构化 API 与可靠性研究](../structured-api/README.md)提供现有 API-key 路径的 Pydantic/HTTPX、严格 quote 验证、时限、失败语义和日志约束。SIWC 官方预览参数与该通用请求建议有差异，需要单独的 provider request builder。
- 项目 Overlay 指出所有非 `UNSUPPORTED` verdict 必须有 passage 索引和非空精确子串 citation；模型失败不得伪装成 `UNSUPPORTED`；日志不得包含 context、answer、quote、token 或原始异常。这些不变量对 Codex provider 一样适用。
- 专门的 SIWC 文档没有明确确认 `text.format` strict JSON schema 在 plan-usage preview 的支持状态。不得把“普通 Responses API 有 Structured Outputs”当成 SIWC 实测证据。
- 当前没有官方文档证据说明可以通过本地 CLI 机器接口读取每个 external app 的剩余额度、reset 时间或每一项消费占总额度比例。服务应为此输出 unknown/null，并把用户导向 Settings → Usage，而不是自己计算。
