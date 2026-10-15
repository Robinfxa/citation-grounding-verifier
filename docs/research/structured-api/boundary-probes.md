# Python 字符串与引用边界探针

运行日期：2026-10-15。实际解释器：Python 3.11.9。输入全部为合成文本；未导入产品模块、Pydantic 或模型客户端，未读环境密钥，未发送 API 请求。本证据只覆盖 Python 标准库行为，供后续产品回归案例复用。

实际观察：

| 探针 | 结果 | 对守门的影响 |
| --- | --- | --- |
| `isinstance(True, int)` | `True` | 仅用该检查不能排除 bool。 |
| `0 <= True < 2` | `True` | 仅检查上下界仍会把 bool 当合法 passage index。 |
| `['first','last'][-1]` | `'last'` | 必须先明确拒绝负数。 |
| `type(index) is int and 0 <= index < 2` | 只接受 0 和 1；拒绝 False、True、-1、2、0.0、'0' | 对来自 JSON 的 index 可直接表达严格边界；Pydantic strict int 也应保持同样语义。 |
| `'' in source` | `True` | 子串检查前必须拒绝空 quote。 |
| 对 `s='A😀Cafe\u0301\r\nB'` 找 `q='e\u0301'` | code point 范围 `[5,7)` | 原始 Python `str` 切片可精确还原 quote。 |
| 同一范围的 UTF-8 bytes | `[8,11)` | 不能把字节位置标成 `start_char`。 |
| 同一范围的 UTF-16 units | `[6,8)` | 不能直接用 JavaScript 字符串位置解释 code point offsets。 |
| `'é' in s` | `False` | 视觉相近的预组合/分解形式不构成精确匹配。 |
| `'a\nb' in 'a\r\nb'` | `False` | 不能提前统一换行。 |
| `'bc' in ''.join(['ab','cd'])` | `True`，但各 passage 均不含 `'bc'` | 不能先拼接来源再检查引用。 |
| `'go go'.find('go')` | 0，范围 `[0,2)` | 重复引文可确定性选择首次位置；无需模型生成 offsets。 |

复现命令：

```sh
python3 - <<'PY'
import json, platform
s = 'A😀Cafe\u0301\r\nB'
q = 'e\u0301'
start = s.find(q)
results = {
    'runtime': platform.python_version(),
    'isinstance_true_int': isinstance(True, int),
    'boolean_passes_naive_bounds_for_two_passages': 0 <= True < 2,
    'negative_index_selects_last_item': ['first', 'last'][-1] == 'last',
    'strict_index_acceptance': {repr(i): type(i) is int and 0 <= i < 2
                                for i in [False, True, -1, 0, 1, 2, 0.0, '0']},
    'empty_quote_matches_every_source': '' in s,
    'decomposed_quote_codepoint_span': [start, start + len(q)],
    'same_quote_utf8_byte_span': [len(s[:start].encode()),
                                 len(s[:start + len(q)].encode())],
    'same_quote_utf16_unit_span': [len(s[:start].encode('utf-16-le')) // 2,
                                  len(s[:start + len(q)].encode('utf-16-le')) // 2],
    'precomposed_e_acute_in_original': 'é' in s,
    'lf_quote_matches_crlf_source': 'a\nb' in 'a\r\nb',
    'joined_passages_can_invent_quote': 'bc' in ''.join(['ab', 'cd'])
        and not any('bc' in p for p in ['ab', 'cd']),
    'duplicate_quote_first_span': ['go go'.find('go'),
                                    'go go'.find('go') + len('go')],
    'slice_returns_expected_quote': s[start:start + len(q)] == q,
}
print(json.dumps(results, ensure_ascii=False, indent=2))
PY
```

结果不是 `/verify` 的成功证据。实现者应将这些输入放进实际守门与 HTTP 故障路径，另验证安全错误映射和日志不泄漏。
