# TypeSafe Jev：接入前研究

研究日期：2026-10-20。阅读了官方文档、示例和固定版本 SDK 源码；尚未调用 Jev，也没有质量、延迟或成本实测。项目采用方案见 [设计](../../../openspec/changes/jev-grounding/design.md)，实施状态见 [任务](../../../openspec/changes/jev-grounding/tasks.md)。

## 已核实的能力

最新发布版本是 **`jev-1.14.0`**。读取时 `jev-latest` 仍指向 1.13.0，`jev-preview` 指向 1.14.0，因此实验必须固定版本并检查实际返回模型。官方输入标价为 **$0.042 / 百万 token**，输出免费；默认请求总上下文 64k、单题上下文 32k。价格和限制均为本次读取的快照。[Models](https://docs.typesafe.ai/models)

Jev 接收共享 `state` 和若干独立的类型化问题，返回选择及概率；它**不生成自由文本**，不能直接替换本项目生成断言、理由、引文的 `StructuredProvider`。[Introduction](https://docs.typesafe.ai/introduction)

`Choice` 接受预定义选项，返回 `choice / probabilities / confidence`。每题最多 255 个选项；题目 ID 不会进入模型，需要把断言及任务说明放进题目内容。可以批量提交独立问题，但不能假定同一请求里的后一道题能读取前一道答案。更多问题仍会增加 token。[Choice](https://docs.typesafe.ai/primitives/choice)

三分类适合本项目的 S/C/U。其 confidence 为 `(p_max - 1/n) / (1 - 1/n)`；三选一的 0.8 对应最高选项概率约 0.8667。它是模型分布统计量，**不是实际正确率**，不同问题的分数也不能相乘冒充联合可靠率。阈值必须用本项目开发数据检查。[Confidence](https://docs.typesafe.ai/confidence)

## 官方示例能借鉴什么

| 证据 | 可借鉴部分 | 本项目需要保留的边界 | 当前状态 |
| --- | --- | --- | --- |
| [引用核验示例](https://docs.typesafe.ai/cookbooks/citation_check) | 先检查引用存在，再判断来源关系；低 confidence 转复核 | 示例使用 1.12、八条预制引用和 0.8 阈值；会归一化空白及弯引号，只看选中 section。本项目必须逐字匹配，并处理完整 context 和跨段证据 | 仅采纳分层思想；未实现 |
| [抽取级联示例](https://docs.typesafe.ai/cookbooks/sde_cascade) | 快模型检查后，将有问题的项升级给 LLM | 示例是 1.12 的 Noul 错误概率阈值 0.7，不是 Choice confidence，也不是本任务校准结果 | 仅采纳有限升级；未实现 |
| [置信度路由](https://docs.typesafe.ai/patterns/confidence-routing) | 将语义标签与能否自动采用分开 | 低置信度不是缺乏来源证据；不能直接映射为 UNSUPPORTED | 设计采纳；未实现 |

## SDK 源码提供的边界证据

固定读取 [官方 Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python/tree/f36e68549ceca3191e5791e5f99ea1baa1a258b5)，版本声明为 0.7.5。没有安装或执行 SDK。

- [schema](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_schemas/models.py) 将 Choice confidence 声明为必填非空 float，但未覆盖全部概率范围、总和及题目集合约束。
- [响应实现](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/response_types.py) 使用严格模型；未知答案类型可能被忽略。因此应用还必须检查全部请求题目是否完整返回。
- [官方测试](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/tests/test_responses.py) 包含缺少 Choice confidence 时拒绝响应的例子。真实 1.14 的精度、舍入和异常响应尚未验证。

HTTP 参考的 system-one/errors 页面在本次读取中不可用；endpoint 和主要请求字段可由 Choice 文档交叉确认，但认证头、错误映射及限额预检仍须在实施前按固定 SDK 源码核实，并通过获授权的最小真实调用验收。不会把“SDK 能解码”写成协议和语义均可靠。

## 对现有项目的含义

已有 `heuristics.extract_claims` 可复用为用户选定的规则切句基线；已有 `prompts.EXTRACT`、固定 claim ID 判断和 `validate_report` 可用于 LLM 抽取与升级复核。规则句子不保证原子性，引用逐字存在也不保证语义充分。现有单 provider 的运行统计不能准确表达 Jev 与 LLM 混合调用，需要按阶段记账。

值得实现一个受控实验：Jev Minimal 的正常路径不调用生成式 LLM，Optimized 仍由 LLM 抽取；两者共用 Jev 与降级策略。主要风险是候选证据遗漏、错误但高置信度、LLM 抽取延迟和较高降级率。是否更快、更省，必须比较**整条流程**，包括所有题目、两轮 Jev、LLM 抽取、重试和复核。厂商案例或输入单价不能证明本项目的收益。
