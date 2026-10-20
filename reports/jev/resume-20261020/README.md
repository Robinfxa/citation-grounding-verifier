# Jev 剩余额度恢复：probability_sum 后停止

2026-10-20，冻结干净提交 `6feda7b09eac9566d63804d3b53133f73b4d3c06`。
只选择 `v2-pilot-reviewed-1` 的 `v2-dev-p01`，请求 jev_minimal / jev_optimized
各一次 end-to-end；seed 为 20261015。唯一真实 CLI 退出 **2 / COMPLETED_WITH_ERRORS**。

固定排序先运行 optimized：Codex 提取成功，Jev 原生协议校验随后拒绝响应，安全错误为
`provider_protocol_error`，固定诊断标签为 **`probability_sum`**。该标签对应至少一个
Choice 的概率总和未通过与 1 相差不超过 0.001 的守门规则；没有保存上游原始 body，
因此没有具体概率值、偏差方向或问题身份的证据。minimal 按模型错误停机规则保存为
**NOT_RUN**，未调用 provider。没有自动重试、修产品或额外诊断调用。

| 阶段 | 请求及返回模型 | Attempts | Input / output tokens | 阶段耗时 ms | 结果 |
| --- | --- | --- | --- | --- | --- |
| extraction / Codex | gpt-6.1-sol | 1 | 462 / 301 | 9864.058 | success |
| jev_judgment / Typesafe | jev-1.14.0 | 1 | 18763 / 3594 | 470.124 | probability_sum |

Jev 一次请求包含 24 个问题。两阶段 usage 完整，输入合计 **19225**、输出 **3895**、
cached input 0；retry / repair 均为 0。完整 CLI 墙钟时间为 **16800.456 ms**，
从进程启动到退出，包含初始化、鉴权、模型、评分与落盘；失败操作耗时 10427.904 ms。
没有价格快照，订阅及未定价阶段的美元总额未知，已知小计 0 不表示免费。

本轮 shared cap 为 **10**，每操作 6；两 provider 各配额 10 且受 shared cap 约束。
本轮实际 **2/10**，加上原 smoke 的 2 次，累计 **4/12**，剩余 **8** 未使用。
剩余额度不授权再次运行。旧 Codex pilot 的项目预算独立，原 smoke 和独立审查文件未改。

两个请求各保留全部 8 gold，共 16 个请求级 gold 分母。没有有效最终报告或已通过协议
校验的 Choice；optimized 的 8 个 trace 均 unresolved，minimal 无 trace。失败统计的
零分保留失败含义，不能推出模型语义准确率、方法优越性、速度或成本优势。

`run-01/` 是冻结保存产物。用该提交的计算源码离线执行 report，退出码仍为 2，
原目录内全部 **23 个文件逐字节不变**，没有推理调用。重放耗时 3437.420 ms；
失败保存链可重算，Jev live 成功链仍未验证。独立验收与发布由父端负责。

`resume-receipt.json` 保存阶段资源、固定 protocol_reason、配置/源码绑定和重放哈希。
其中 `reproduction_command` 明确是便携复现示例，使用公开相对输入和全新输出目录，
不是原始执行命令。完整真实命令和安全原始诊断留在私有记录。示例描述本轮的历史参数，
不能在剩余 8 次额度下自行执行；任何新 live 都需要新的明确授权及预算。
冻结产物未做路径改写，路径审计未发现本机用户名、虚拟环境或私有 scratch 路径。

以下仅离线重算，要求计算源码与 config 的指纹一致：

```sh
uv run grounding-eval report reports/jev/resume-20261020/run-01
```
