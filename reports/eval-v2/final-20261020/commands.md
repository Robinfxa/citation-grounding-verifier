# 最终 test 调用前冻结命令

状态：准备完成，尚未推理，等待父端最后窄核。原始绝对argv已私有冻结；以下为同一检查点、数据、选择和限制的便携示例。

源码提交 `324559dccba4624dfa803849f5fd26284c7b27f4`；源码指纹 `cd15430a02b364c2f6ddef034e6ef046b335dd99b3678d3dada5186e31dd89a6`。

从仓库根目录导出固定提交，保留现有Python依赖与已授权Codex登录配置；不导出.env或凭据。复现实验会产生新的调用，必须使用全新输出路径，不能删除或覆盖旧证据。

```sh
final_checkpoint_dir=$(mktemp -d)
git archive 324559dccba4624dfa803849f5fd26284c7b27f4 src datasets pyproject.toml uv.lock | tar -x -C "$final_checkpoint_dir"
```

三块固定顺序如下。每块结束后先应用块间规则，再决定下一块；不要把三个命令无条件串联。

## full-test

48 test case；288 job；192模型操作；硬上限360次（含修复）。

```sh
env GROUNDING_PROVIDER=codex GROUNDING_MODEL=gpt-6.1-sol GROUNDING_PROVIDER_TIMEOUT=120 GROUNDING_OPERATION_TIMEOUT=240 GROUNDING_MAX_PROVIDER_ATTEMPTS=6 GROUNDING_TRANSPORT_RETRIES=0 GROUNDING_DIAGNOSTICS=true GROUNDING_RETRY_DELAY=0.25 GROUNDING_MAX_OUTPUT_TOKENS=8192 OPENAI_BASE_URL=https://api.openai.com/v1 PYTHONPATH="$final_checkpoint_dir/src" python -m grounding_eval run --dataset "$final_checkpoint_dir/datasets/main.jsonl" --split test --format-version 2 --approaches heuristic,minimal,optimized --track both --case-ids-file reports/eval-v2/final-20261020/full-case-ids.json --seed 20261015 --bootstrap-samples 10000 --max-total-provider-attempts 360 --output reports/eval-v2/final-20261020/full-test
```

## repeat-02

16 test case；96 job；64模型操作；硬上限120次（含修复）。

```sh
env GROUNDING_PROVIDER=codex GROUNDING_MODEL=gpt-6.1-sol GROUNDING_PROVIDER_TIMEOUT=120 GROUNDING_OPERATION_TIMEOUT=240 GROUNDING_MAX_PROVIDER_ATTEMPTS=6 GROUNDING_TRANSPORT_RETRIES=0 GROUNDING_DIAGNOSTICS=true GROUNDING_RETRY_DELAY=0.25 GROUNDING_MAX_OUTPUT_TOKENS=8192 OPENAI_BASE_URL=https://api.openai.com/v1 PYTHONPATH="$final_checkpoint_dir/src" python -m grounding_eval run --dataset "$final_checkpoint_dir/datasets/main.jsonl" --split test --format-version 2 --approaches heuristic,minimal,optimized --track both --case-ids-file reports/eval-v2/final-20261020/repeat-case-ids.json --seed 20261015 --bootstrap-samples 10000 --max-total-provider-attempts 120 --output reports/eval-v2/final-20261020/repeat-02
```

## repeat-03

16 test case；96 job；64模型操作；硬上限120次（含修复）。

```sh
env GROUNDING_PROVIDER=codex GROUNDING_MODEL=gpt-6.1-sol GROUNDING_PROVIDER_TIMEOUT=120 GROUNDING_OPERATION_TIMEOUT=240 GROUNDING_MAX_PROVIDER_ATTEMPTS=6 GROUNDING_TRANSPORT_RETRIES=0 GROUNDING_DIAGNOSTICS=true GROUNDING_RETRY_DELAY=0.25 GROUNDING_MAX_OUTPUT_TOKENS=8192 OPENAI_BASE_URL=https://api.openai.com/v1 PYTHONPATH="$final_checkpoint_dir/src" python -m grounding_eval run --dataset "$final_checkpoint_dir/datasets/main.jsonl" --split test --format-version 2 --approaches heuristic,minimal,optimized --track both --case-ids-file reports/eval-v2/final-20261020/repeat-case-ids.json --seed 20261015 --bootstrap-samples 10000 --max-total-provider-attempts 120 --output reports/eval-v2/final-20261020/repeat-03
```

共同限制：provider120秒、operation240秒、每操作6attempts、零transport retry；requested8192 output tokens对Codex不生效。首错停止关闭，native quota/budget停止保留。

块间规则：quota/budget停、模型ERROR数/该块全部预定模型job数≥10%、任何model NOT_RUN或完整性/cleanup/源码数据漂移时暂停后续块并报告。普通ERROR低于门槛时保留并继续；不重跑失败或未知结果，不更换16项，不伪造completion，不从外部强中断当前CLI。

48 test完整原始run是主结果；固定16项从三个原始run复用现有analyze_repeated，family与重复同簇；固定24项用于独立语义审计，两个12项批次不重叠。runtime/bootstrap seed20261015，metadata selection seed20261020；无test后调参。

新总上限600与所有历史预算分开，预期400次仅为无修复条件估计。新增调用、未知usage与订阅美元未知分别报告。
