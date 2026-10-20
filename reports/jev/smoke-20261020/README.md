# Jev 首次 live smoke：协议失败后停止

2026-10-20，冻结源码提交 `d951dca92f210b2946f73c7595cd1e97b60c6620`。
数据为 `v2-pilot-reviewed-1`，只选择 `v2-dev-p01`，两种方法各请求一次 end-to-end。
唯一一次真实 CLI 退出 **2 / COMPLETED_WITH_ERRORS**，没有重跑或额外诊断请求。

固定 seed 排序先执行 `jev_optimized`。Codex 提取成功，随后 Typesafe 的原生 Jev
判定未通过协议校验，安全错误为 `provider_protocol_error`；`jev_minimal` 按
stop-on-model-error 保留为 **NOT_RUN**，没有 provider 调用。

| 阶段 | 请求及返回模型 | Attempts | Input / output tokens | 阶段耗时 ms | 结果 |
| --- | --- | --- | --- | --- | --- |
| extraction / Codex | gpt-6.1-sol | 1 | 462 / 378 | 11050.061 | success |
| jev_judgment / Typesafe | jev-1.14.0 | 1 | 18755 / 3594 | 273.148 | protocol error |

Jev 请求包含 24 个问题；这不是 24 次请求或 24 个有效答案。两阶段 usage 均完整，
合计输入 19217、输出 3972、cached input 0；retry / repair 均为 0。
完整 CLI 墙钟时间为 13898.888 ms，从进程启动计至退出，包含鉴权、调用和落盘。
没有价格快照，且 Codex 为订阅通道，因此美元总额未知；已知小计 0 不表示免费。

本次上限为总计 12、每操作 6；各 provider 配额均为 12，并共享总 cap。
实际使用 **2/12**，余 **10** 未使用；剩余额度不授权再次运行。
旧 Codex pilot 账本与本次独立。

两个请求各保留全部 8 个 gold，共 16 个请求级 gold 分母。没有最终报告或有效的
Choice 置信度：optimized 的 8 个 trace 均 unresolved，minimal 未尝试。
失败分母上的零分保留失败含义，不能据此推断模型语义准确率、方法优越性、速度或成本优势。
上游原始响应未公开或留存，安全记录无法定位更细的协议拒绝原因。

`run-01/` 是原始保存产物。冻结源码执行离线 `report` 后仍退出 2，目录内全部
23 个文件逐字节不变，未调用推理。该结果证明失败记录可重算，未证明 Jev 成功链路。
独立复核及完整任务验收由父端负责。

`smoke-receipt.json` 含阶段用量、实际模型、配置/源码绑定与重放哈希。
其中 `reproduction_command` 是明确标注的**便携复现示例**，不是原始执行命令；
原始绝对路径命令及原始诊断保留在私有记录。冻结运行文件未做路径改写，路径审计未发现
本机用户名、虚拟环境或私有 scratch 路径字符串。

如获全新的 live 授权，使用对应冻结源码、已配置凭据、默认官方端点，以及 receipt 中
完整的非秘密环境配置，可按下例写入全新目录；**本轮不会执行此示例**：

```sh
GROUNDING_PROVIDER=codex GROUNDING_MODEL=gpt-6.1-sol TYPESAFE_MODEL=jev-1.14.0 \
GROUNDING_TRANSPORT_RETRIES=0 GROUNDING_MAX_PROVIDER_ATTEMPTS=6 \
uv run grounding-eval run --dataset datasets/v2/pilot.jsonl --split dev \
  --case-ids-file reports/jev/smoke-20261020/case-ids.json \
  --approaches jev_minimal,jev_optimized --track end-to-end --format-version 3 \
  --provider-budgets reports/jev/smoke-20261020/budget.json \
  --max-total-provider-attempts 12 --stop-on-model-error \
  --seed 20261015 --bootstrap-samples 10000 --output reports/jev/smoke-reproduction-new
```

以下仅离线重算，要求计算源码哈希与 config 一致：

```sh
uv run grounding-eval report reports/jev/smoke-20261020/run-01
```
