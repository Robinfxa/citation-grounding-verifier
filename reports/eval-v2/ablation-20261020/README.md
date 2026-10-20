# C01 开发消融结果

三块预定新运行全部完成。父端已于2026-10-20正式采纳单句 C01，并接受下述资源代价与残留问题；生产落地交原 Service owner，最终 test 尚未推理。

## 运行与分母

仅 MINIMAL end-to-end 增加一条充分引用指令。冻结 pilot 为 12 dev / 126 gold，数据 SHA `701fe4bf85bb745824d460399b6dd6efd8302856e48cea4e751bb09f8ca040df`。control1 来自已逐行映射的开发组合，11 OK / 1 原 p07 ERROR；其余三块依次 candidate1 → control2 → candidate2，各 12 OK、CLI0、12 次调用，retry/repair0，returned model 均为 gpt-6.1-sol。新预算实际 **36/216 次**，剩余 **180**，与历史预算分开。

三块新增已知 input/output/cached tokens 为 **117876 / 40439 / 0**，usage 完整。CLI 墙钟合计 **905948.179 ms**。Codex 订阅美元成本未知。provider120s/operation240s、每操作6次、零transport retry、model-error stop均按冻结配置；requested output limit仍not_applied/effective=null。

控制和候选各有 24 个 case-observation、252 个重复 gold；只有 **12 个独立 source family**。原控制错误仍进入全部主指标和资源，不把 candidate1 的成功归功于提示词。两次检查未进入质量比较。

## 配对结果

| 指标 | control1 | candidate1 | control2 | candidate2 | pooled control | pooled candidate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| joint-label F1 | 0.717300 | 0.782258 | 0.733871 | 0.761134 | 0.725773 | 0.771717 |
| joint-evidence F1 | 0.295359 | 0.653226 | 0.274194 | 0.623482 | 0.284536 | 0.638384 |
| macro F1 | 0.891057 | 0.916667 | 0.898148 | 0.878295 | 0.894695 | 0.897486 |

pooled candidate−control 的 family 配对重采样（seed20261015、10000次、重复留在family内）为：证据 F1 **+.353848**，95% family-sensitivity区间 **[.204756, .518758]**；标签 F1 **+.045944**，区间 **[−.008889, .109536]**。Exact case 为候选2/24、控制0/24；literal quotes分别259/259、241/241。macro区间有632/10000个无定义重采样。

这只是严格文本/gold-span代理与小开发样本的敏感性描述，不建立语义正确性的统计结论。固定块顺序、control1跨阶段组合、provider drift、标注偏差与未观察随机性均保留。次要共同成功分母为23对，证据F1候选.662420/控制.291755，不能替代含错误的主分母。

## 引用、回归与资源取舍

已逐项检查24对、126个changed aligned gold outcome，包含去重后的206种不同预测变体及双方unmatched预测。两次候选均在原sqlite3四个缺陷处保留False或LEGACY外层条件；control2的LEGACY/non-None项本已充分，未重复算修复。

未发现本次变化中新增明确的标签语义错判。严格回退包括Path限定名和the Access privileges column表面变化，相关事实及标签仍返回；candidate2把localcontext进入/退出两事实合并，是实际拆分粒度回归。size/hash合并也见于control2。candidate2 p07 prediction9仍缺This syntax的先行词。原parallel dump短引文已直接表达directory-only，不能将所有gold-span提升解释为原引文不充分。完整逐case结论见qualitative-review.json。

资源用全部成功且usage完整的第二次配对描述：input39004→39436（+1.11%，每请求+36）；output11772→14435（+22.62%）；操作耗时合计258651.182→318429.852ms（+23.11%），中位数20958.657→27838.084ms（+32.82%）；引用字符14789→26532（+79.40%）。这不是对未来运行的因果或耗时保证。完整控制池有一次未知usage，因此全池token/美元差值未知。

决策前原作者建议（历史记录）：已知充分引用缺口在两次候选中改善，证据代理方向一致，未见实质标签退化；同时接受较长引用、局部合并及剩余指代缺口，建议采纳。当时父端独立复核/资源接受/最终采纳待记录；父端现已正式采纳，见下节。gold、alias和评分未修改。

## 冻结与重放

调用前 source freeze SHA `ca5ea3f282cc197667ad1630adb91c58dc9e2c96d5a52bcc01a0da86aba97c22`；execution freeze SHA `885e5ef88fe57f4950daa8ce48b6874590de543101f52bb24f38de9b32dfa728`。control source指纹 `353c9d50f6035dadf76006913708123f4fbe525f79d74c70e9245e919413239e`，candidate指纹 `cd15430a02b364c2f6ddef034e6ef046b335dd99b3678d3dada5186e31dd89a6`。父端已在调用前接受单因素diff与控制一致性。

三块guarded离线report均CLI0，各23个文件逐字节不变；禁止网络、设置读取、凭据加载及verifier构造。analysis-row-map逐项绑定48行的来源文件、0基行号、request/sequence、整文件及含换行行SHA。公开consumer离线重算全部score、aggregate、family bootstrap、per-observation与资源，结果一致：

```sh
PYTHONPATH=src python reports/eval-v2/ablation-20261020/replay-analysis.py
```

该命令只读，使用control或candidate对应冻结源码，不加载.env或凭据、不推理、不写bytecode。原三块report重放应各使用对应冻结源码。

C01 postflight先核原基线182个公开文件全等。随后父端授权的组合replay脚本格式修复另存于completion-dev-20261020/replay-format-amendment.json：旧hash和原收据保留，AST等价，新脚本lint及72行组合重放通过。原始运行记录均未改变。

## 父端最终决定

父端独立重算48行配对及72行组合一致，直接核读p02四项条件、p04合并和p07先行词残留后采纳C01，接受第二观察约22.6%输出、23.1%操作总耗时增加。adoption-decision.json投影原决策并绑定其SHA；no-post-test-tuning约束生效。原analysis/qualitative-review/delivery-receipt里的pending是决策前冻结状态，保留历史，不重写评分或作者结论。最终代码须由原Service owner达到候选指纹cd15430a02b364c2f6ddef034e6ef046b335dd99b3678d3dada5186e31dd89a6后再冻结。
