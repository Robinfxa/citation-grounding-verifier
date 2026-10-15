# 本地 ChatGPT 套餐 provider

本 provider 名为 `codex`，使用本应用独立取得的 Sign in with ChatGPT（SIWC）授权。它调用公共 Responses API，不导入 Codex CLI 或 Hermes 的凭据，不启动代码代理。适用产品范围是用户自己的本地服务。公开协议来源为 [SIWC 概览](https://developers.openai.com/siwc/token-sharing-open-source)。

## 登录与账号选择

在项目目录运行以下命令；登录命令会打开系统浏览器。登录超时默认 180 秒，可设置为 1–600 秒内的值。

```sh
uv run --frozen grounding-auth login --profile default --timeout-seconds 180
uv run --frozen grounding-auth status --profile default
uv run --frozen grounding-auth models --profile default
```

首次登录需在 OpenAI 页面完成账号、workspace 和套餐使用授权。`status` 输出 JSON，`signed_in:true` 表示身份已保存；只有 `plan_enabled:true` 才允许推理。`models` 返回该账号当前可见的模型 slug，保持服务端顺序。模型目录仅供选择，实际可用性以请求成功完成为准。[注册协议](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)、[模型协议](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)

若授权码交换返回 HTTP 400 / `invalid_grant`，同一次登录会沿用本次注册的 client ID，再打开浏览器授权一次。新一轮使用全新的 state、nonce 和 PKCE，丢弃旧授权码，并继续受原登录总时限约束。第二次失败即结束；身份验证前不会保存新凭据或替换现有账号。若整次登录失败，本次新注册 ID 不会跨进程保存。此恢复遵循[官方流程](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)。

为另一个账号或 workspace 选择另一个 profile，例如 `--profile personal`。profile 只允许 1–64 位小写字母、数字、下划线和连字符，首位必须为字母或数字。同名 profile 的回访登录沿用原注册；返回的 client 或已验证 subject 不匹配时，旧凭据保留。相同邮箱不作为合并账号的依据；应用只保留所需的 subject/client 身份映射。

如果已经登录但未允许套餐使用，可由用户主动重新请求同意：

```sh
uv run --frozen grounding-auth login --profile default --consent
```

应用校验实际返回的 scopes；浏览器回调中的 scope 不作为权限依据。缺少权限时返回 `plan_not_authorized`，不会推理或自动切换付费路径。[权限与错误恢复](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)

## 凭据位置与配置

默认目录为 `~/.config/citation-grounding/`，应用目录权限为 `0700`，凭据、host ID 和锁文件为 `0600`。可在每个命令上显式使用 `--auth-dir /absolute/path/outside/repository`，或者设置进程环境变量 `GROUNDING_AUTH_DIR`。`GROUNDING_AUTH_PROFILE` 选择 CLI 默认 profile。CLI 不自动加载 `.env`；命令上的明确选择优先。

目录中每个 `profile-<name>.json` 包含一份注册及其 token，`host.json` 保留本机稳定 host ID。它们不应进入仓库、支持记录或评测产物。应用拒绝仓库内目录、符号链接目录、非本用户文件和宽松文件权限；该检查不依赖工作流 `AGENTS.md`。如应用目录或文件权限被改动，可先确认路径属于本应用，再恢复目录 `0700`、文件 `0600`。[本地凭据要求](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)

在服务配置中使用以下非秘密设置：

```dotenv
GROUNDING_PROVIDER=codex
GROUNDING_MODEL=<从 models 命令选择的确切 slug>
GROUNDING_AUTH_PROFILE=default
# 可选：必须是仓库外的绝对路径
# GROUNDING_AUTH_DIR=/absolute/path/to/app-credentials
```

服务工厂须显式传入 `Settings.auth_profile` / `Settings.auth_dir`，因为读取 `.env` 不会修改进程环境。构造接口为 `CodexProvider(model, timeout_seconds=30, *, profile="default", auth_dir=None)`；测试可注入 HTTPX client、凭据 store 和最终对象 parser。调用方负责关闭 provider；外部注入的 client 由注入者关闭。

## 最小真实验收

离线验收没有运行真实登录或推理。准备使用套餐额度时，可执行以下真实兼容性检查。

1. 执行登录，确认 `status` 中 `plan_enabled:true`，然后用 `models` 选择确切 slug。
2. 将 `GROUNDING_MODEL` 设置为该 slug；自定义账号目录或 profile 时也设置相应进程环境变量。
3. 运行下面的一次请求。它使用严格 schema，只有完整 `response.completed` 且本地结果匹配时才输出成功。

```sh
uv run --frozen python - <<'PY'
import asyncio
import json
import os
from grounding.codex_provider import CodexProvider
from grounding.contracts import StructuredRequest

async def main():
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    provider = CodexProvider(
        os.environ["GROUNDING_MODEL"],
        profile=os.environ.get("GROUNDING_AUTH_PROFILE", "default"),
        auth_dir=os.environ.get("GROUNDING_AUTH_DIR"),
    )
    try:
        result = await provider.generate(StructuredRequest(
            "compatibility_probe", schema,
            "Return the requested JSON object with ok set to true.",
            {"probe": "local structured-output compatibility"},
        ))
        assert json.loads(result.text) == {"ok": True}
        print(json.dumps({"completed": True, "model": result.model,
                          "usage_complete": result.usage.complete}))
    finally:
        await provider.aclose()

asyncio.run(main())
PY
```

4. 通过后再运行实际 `/verify`、minimal/optimized 核验与评测。单次 probe 不证明核验质量或整批成功。

SIWC 专页尚未明确承诺此路由支持 `text.format` strict JSON Schema；上面的 probe 是必要的兼容性确认。实现不会在能力不支持时撤掉 schema 或改用其他 provider。请求固定使用 `store:false`、`stream:true`、`instructions` 和完整 user 数据，省略该预览禁止的参数和所有工具。[预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

直接路由可能省略 `Content-Type`；适配器仍要求合法、有界的 SSE，明确声明其他媒体类型时会拒绝。只有收到真正的 `response.completed` 且状态为 completed、无错误或不完整原因时，结果才可进入最终校验。若终态的 `output` 恰为空数组，适配器可以采用此前配对的 `output_item.added` / `output_item.done`：响应身份、从零连续的项索引和项 ID 必须一致，每项必须完成，重复或未完成项均拒绝；内容事件也必须指向对应的项和有效内容索引。完整终态输出仍按原路径解析。[官方流事件](https://developers.openai.com/api/reference/resources/responses/streaming-events)

重建仅使用完成项中的完整内容，之后仍通过同一个严格最终解析器；delta、text-done、EOF 或 `[DONE]` 均不能单独证明成功。流、事件和重建后的最终对象继续受 4 MiB / 1 MiB / 1 MiB 上限约束，usage 与 model 仍取自最终响应。

## 退出、恢复与计量

```sh
uv run --frozen grounding-auth logout --profile default
```

退出先尝试撤销 renewable session，网络/服务故障最多重试一次，然后清除本地 tokens，保留注册与 host ID。JSON 中 `remote_revocation_confirmed:false` 表示仅本地退出完成；用户应到 [ChatGPT 设置 → Usage](https://chatgpt.com/settings/usage) 断开此应用。CLI 此时退出码为 0，调用者必须查看该字段。不同 profile 互不退出。[会话管理](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)

刷新在进程文件锁内重读最新凭据，access、refresh、scope 和 expiry 一起原子替换。暂时故障保留原文件；确认失效的 refresh grant 清除不可用 tokens，保留注册，提示重新登录。等待锁、网络和流读取可取消；关闭流后不会继续推理。

一次 `generate` 只有一次推理尝试。额度错误 `quota_exhausted` 和能力错误 `unsupported_capability` 均不可重试。provider 不永久缓存额度失败，之后独立请求仍可在权限或额度恢复后成功。流打开之前的临时网络、限速和服务错误由服务层决定是否重试；provider 将流打开后的中断、超时或失败标记为不可重试，避免重复消耗额度。服务编排必须保留该标记；被外层时限取消的请求也应保守停止重试。

token 计量仅保留 Responses 实际返回的值；缺失或无效计量保持 unknown。应用不根据 token 数推算美元、套餐剩余比例或 reset。`status` 的 `quota_remaining` / `quota_reset_at` 始终为 `null`，用户应查看 Usage 页面。

## 离线证据与日志边界

```sh
uv run --frozen pytest tests/provider -q
uv run --frozen ruff check src/grounding/codex_auth.py src/grounding/codex_provider.py tests/provider
uv run --frozen python tests/provider/offline_probe.py --output .multi-subflow/provider
```

全部凭据均在临时目录中合成；官方域名请求使用 HTTPX MockTransport，只有 `127.0.0.1` 回调使用真实 socket。CLI 探针替换浏览器启动，不会打开真实浏览器。脚本保存公开 CLI 的原始 stdout、stderr、退出码，以及 provider 成功、注入故障与恢复的记录。

诊断只含内部 request ID、固定阶段/事件、分类、耗时；复用服务 operation 上下文和 `GROUNDING_DIAGNOSTICS=false` 开关。不会输出 token、账号、授权 URL、原始异常、请求或响应正文。写入失败是 best effort；测试涵盖默认缓冲 CLI 的安全退出，但不声称可以限制永久阻塞的同步日志 sink。

登录失败的诊断另外区分固定阶段：`auth_callback` 表示本机回调，`auth_token_exchange` 表示授权码交换，`auth_jwks` 表示公钥请求，`auth_id_token` 表示签名与身份校验。`http_status` 仅为数字 HTTP 状态；`reason` 仅含固定类别，例如 `oauth_invalid_grant`、`jwt_signature`、`jwt_audience`、`jwt_nonce`，不包含上游错误原文或 token 中的值。页面授权成功仅说明浏览器步骤完成，最终登录成功仍以 CLI 保存已验证身份为准。

触发上述恢复时，日志会在同一个 request ID 下增加一条固定的 `auth_login` / `progress` / `reauthorizing` 记录；之后会出现第二组回调与交换结果。它表示一次新的浏览器授权，旧授权码不会再次发送。

当前实现面向 macOS/Linux，使用标准库 `fcntl`；Windows 不在已验证范围。真实登录、套餐权限及模型目录已验证。严格 schema 的受控请求已观察到完整输出项和完成终态，但其响应省略媒体类型且终态输出为空；对应适配与离线回归已完成，修复后的正常 CodexProvider 真实复验仍待完成，尚不能宣称真实兼容性通过。

模型目录的响应最多读取 1 MiB；超限会明确失败并关闭响应。认证端点的 discovery、公钥和 token 响应仍分别使用原有的 128 KiB 上限。
