# Jev 单项数值诊断：成功，未触发数值事件

2026-10-20，冻结提交 `926d5a1b990bb2a4dbcd47577b27287af2d54e61`。
父端确认 CI 39430155877 success 后，唯一真实 CLI 运行仅选择
`v2-dev-p01 / jev_optimized / end-to-end`，退出 **0 / COMPLETE**。
没有第二次 launch 或额外诊断请求，原 smoke/resume 及审查文件未改。

本次没有 `probability_sum` 或其它协议拒绝事件。公开回执的
`numeric_diagnostic.status` 为 **not_observed**、`values` 为 **null**；没有生成
probability_count / probability_sum / probability_sum_delta / probability_sum_tolerance
这组错误诊断值。本次通过不能补填旧失败的偏差，也不能确定舍入是否为原因。

| 阶段 | 请求及返回模型 | Attempts | Input / output tokens | 阶段耗时 ms |
| --- | --- | --- | --- | --- |
| extraction / Codex | gpt-6.1-sol | 1 | 462 / 301 | 9688.318 |
| jev_judgment / Typesafe | jev-1.14.0 | 1 | 18763 / 3593 | 355.183 |
| jev_evidence / Typesafe | jev-1.14.0 | 1 | 2043 / 367 | 119.515 |
| fallback / Codex | gpt-6.1-sol | 1 | 2936 / 635 | 15722.259 |

四阶段均成功，usage 完整；合计输入 **24204**、输出 **4896**、cached input 0，
retry / repair 均为 0。Jev 共 31 个请求问题，分属 2 次调用；31 个通过协议校验的
Choice 记录不是 31 个自动通过的断言。完整 CLI 墙钟为 **28404.395 ms**，
单操作为 25942.296 ms。美元总额未知，未提供价格快照且 Codex 使用订阅通道。

本轮 shared cap **6** 是原剩余 8 次内的子限额，每操作 6、每 provider 配额 6
均受 shared cap 约束。实际本轮 **4/6**，子限额未用 2；先前已用 4，累计
**8/12**，原额度剩余 **4**。旧 Codex pilot 预算独立，剩余额度不授权自动再运行。

本次评测为 1 requested / 1 succeeded / 8 gold / 8 predictions。严格文本匹配 7/8，
1 omitted / 1 extra，joint-label F1 **0.875**、joint-evidence F1 **0.75**，
literal citations **10/10**，exact case **0/1**。这些是冻结 scorer 的单例结果，
引用命中和文本对齐不是独立语义认证，也不支持总体质量、速度或成本优势。

最终来源为 Jev 4、LLM 4；自动 gold 覆盖 4/8、对齐自动标签错误 0/4。
4 个 fallback claim 由 1 次 LLM 调用处理，原因是 label_uncertain 1、
quote_uncertain 3。没有 Minimal、oracle、held-out 或阈值校准测量。

冻结源码离线 report 退出 0，耗时 1870.043 ms，`run-01/` 的 **23 个文件全部
逐字节不变**，没有推理。该单项运行完成成功流程；历史概率偏差的具体数值仍未取得，
完整 Jev 验收由父端继续判断。

`numeric-receipt.json` 含实际阶段资源、明确未观察到的数值诊断、预算和源码/配置绑定。
其中 portable `reproduction_command` 是复现示例，完整真实命令保存在私有记录；
示例不是原始 argv，也不授权新 live。原保存产物未做路径改写，路径审计未发现本机
用户名、虚拟环境或私有 scratch 路径。以下命令仅离线重算，要求计算源码指纹匹配：

```sh
uv run grounding-eval report reports/jev/numeric-diagnostic-20261020/run-01
```
