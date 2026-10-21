# 12-case 开发基线补全：跨冻结运行，保留原协议失败

原72项矩阵在p07 Minimal/end-to-end发生一次Codex协议错误后按规则停止。
随后只执行原32项NOT_RUN，四组均成功。组合分析为 **71 OK / 1 ERROR / 0 NOT_RUN**；
48个模型操作中47成功、1失败，24个heuristic操作全部成功。两个可用性检查单独计费，不进入质量比较。
这是一组有完整已尝试分母的跨运行比较，原矩阵CLI仍退出2；没有把它改称单次全成功运行。

冻结源为 `45d01e2a3d7142f4d8a5737a53e1743a921ea294`，数据为12 dev / 12 source families /126 gold，
SHA `701fe4bf85bb745824d460399b6dd6efd8302856e48cea4e751bb09f8ca040df`。
gold分布为 `{"CONTRADICTED": 10, "SUPPORTED": 110, "UNSUPPORTED": 6}`，不是平衡的三分类自然分布。
Codex/gpt-6.1-sol，seed20261015，provider120秒/operation240秒，retries0、每操作6次。
期限增加是运行条件变化；prompt、alias、gold、scorer未改。请求8192 output tokens未实际应用，effective为null。
成功响应报告的model集合为 `["gpt-6.1-sol"]`；失败响应没有可用model/usage，无法验证该次实际模型身份。

## 保留失败与来源

[安全诊断](failure-diagnosis.json)确认Codex已打开兼容响应流，约10.389秒后返回provider_protocol_error；
现有日志不足以区分缺完成事件、提前EOF、完成数据/组装或最终解析失败。没有抓取原始上游body。
原p07 ERROR只计一次，未重跑；其未知token字段不是零用量或零费用。
[恢复计划](continuation-plan.json)先冻结每项原NOT_RUN至四个新run的映射，再按8/8/6/10项执行。
分组续跑改变了全局时间顺序，不能排除provider随时间的变化。

[组合来源映射](combined-analysis/source-row-map.json)保留原40行，替换仅32条原NOT_RUN；每行绑定source run、
0基source_line_index、原始sequence、完整records/config hash与含换行row hash。
[组合摘要](combined-analysis/summary.json)复用原scoring/bootstrap，不追加alias，不选最好重复结果。
bootstrap仍以这12个source family为单位；多方法/轨道/重复不新增独立来源。

## Oracle：全部126条gold进入每种方法分母

| 方法 | 成功case | 正确标签 | 三类macro F1 | 严格gold-evidence命中 |
| --- | ---: | ---: | ---: | ---: |
| heuristic | 12/12 | 7/126 | 0.0365 | 7/126 |
| minimal | 12/12 | 126/126 | 1.0000 | 57/126 |
| optimized | 12/12 | 126/126 | 1.0000 | 107/126 |

## End-to-end：保守文本/alias对齐

| 方法 | 成功case | 严格匹配gold | 预测数 | joint label F1 | joint evidence F1 | exact case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic | 12/12 | 63/126 | 102 | 0.0614 | 0.0614 | 0/12 |
| minimal | 11/12 | 85/126 | 111 | 0.7173 | 0.2954 | 0/12 |
| optimized | 12/12 | 89/126 | 131 | 0.6926 | 0.6148 | 1/12 |

分数保留漏项、多项和失败。gold-span命中是证据代理；字面quote合法也不证明语义充分。
[开发归因](development-findings.json)区分表面失配、原子合并、真实上位条件引用缺口和保守证据代理差异。
这些是有界开发例子的定性判断，不是盲态test audit，也不补改主分数。
数据由代理创作及复核，人类复核仍待完成；未读取未来test。

## 实际资源

| 方法/轨道 | 调用 | 已知 input/output tokens | 操作 median/p95 秒 |
| --- | ---: | ---: | ---: |
| heuristic/oracle | 0 | 0 / 0 | 0.093 / 0.172 |
| heuristic/end-to-end | 0 | 0 / 0 | 0.065 / 0.091 |
| minimal/oracle | 12 | 40716 / 9459 | 17.956 / 21.188 |
| minimal/end-to-end | 12 | 36140 / 10771 | 20.974 / 27.194 |
| optimized/oracle | 12 | 44664 / 11570 | 22.548 / 25.784 |
| optimized/end-to-end | 24 | 50551 / 17031 | 34.398 / 41.163 |

本轮含检查实际 **62/320次**，余258；
其中检查2次、首段矩阵18次、续跑42次，比较记录重试0次、修复0次；检查均为0。
已知input/output为 **178434 / 50165**；
原失败使总usage未知，Codex订阅美元成本为null。旧pilot63/150及Jev8/12保持独立，不冲销旧失败。
七次CLI墙钟合计1226.856秒（含初始化、鉴权、评分、落盘及清理）；
从首段启动至最终组合重放的实际过程为2160.930秒，另含诊断与准备间隔。

## 离线重放与限制

七个真实run分别以guarded report重放，原三段退出0/0/2，四段续跑退出0/0/0/0，
每个run的23文件均逐字节不变。guard禁止网络、配置/凭据加载及verifier构造。
组合另经只读consumer重算，三份分析文件字节一致，无网络、推理或凭据读取。
28个原源码文件、442个旧保护文件及原三段69个运行文件均未改。
这些是evaluator的实际自验，父端独立核验另行记录；本文件不替代它。

在同一源码指纹/依赖下，离线核对组合：

```sh
uv run --frozen python reports/eval-v2/completion-dev-20261020/replay-combined.py
```

真实run的report命令只用于各自保存目录，不把组合分析伪装成一个可重放的成功run。
[调用前计划](experiment-plan.json)中的命令是便携复现示例，原绝对argv仅在私有收据；
其手工展开顺序表有[保留原表的更正说明](execution-order-clarification.json)，实际CLI顺序由冻结源、选择集和seed重算一致。
[下一矩阵估算](next-matrix-estimate.json)给出C01三块36次理想调用、独立上限216及条件性资源推算。
C01尚未测量或采纳，需先核该完整分母/control及候选单因素冻结。最终数据/测试矩阵尚未在本轮冻结。

## Replaying the historical control after C01 adoption

The combined development analysis is bound to the original control source. After the product prompt adopts C01, export the original source first; keep the replay consumer's source-equality assertion intact. From the repository root, using the existing Python environment with project dependencies:

```sh
replay_control_dir=$(mktemp -d)
git archive 45d01e2a3d7142f4d8a5737a53e1743a921ea294 src | tar -x -C "$replay_control_dir"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$replay_control_dir/src" python reports/eval-v2/completion-dev-20261020/replay-combined.py
```

This reads Git history and saved artifacts, makes no inference or credential calls, and does not change the checkout. The exported source has control fingerprint `353c9d50f6035dadf76006913708123f4fbe525f79d74c70e9245e919413239e`. This export-and-replay path was executed successfully. Historical receipts retain their original README/script hashes; `control-replay-amendment.json` records this documentation addition, and `replay-format-amendment.json` records the earlier AST-equivalent script cleanup.
