# 04 · Telemetry

Core 跑在 OpenAI 兼容协议上，不区分 Provider。每次 `pong()` 调用结束后，把 LLM 返回的 `usage` 信息写一行 JSONL 到 `<cell_data_dir>/cache_metrics.jsonl`。这是 framework 唯一的 cache / token 观察通道。

本章四件事：为什么不引入 adapter pattern（§4.1）；JSONL 字段（§4.2）；文件位置（§4.3）；写入责任（§4.4）。

## 4.1 为什么不引入 adapter pattern

早期版本设想了一组 `CacheAdapter` Protocol（Anthropic / RadixAttention / Prompt Cache / none 四条路径），各自负责往 Composer 输出里加引擎特异的 cache 标注。最终决定不实现，理由三条：

- **YAGNI**。当前 Vessal 的所有 Provider 都走 OpenAI 兼容接口，`response.usage` 字段格式相同。没有 Anthropic 直连需求，也没有自部署 SGLang / vLLM 实例需要标注。
- **R6 Native Mechanism First**。OpenAI prompt caching 在 `usage.prompt_tokens_details.cached_tokens` 已经返回命中数；引擎自己负责 cache 决策（前缀匹配、模块预计算），framework 不需要参与。给 framework 加 adapter 只是把别人已经做好的事情再包装一层。
- **耦合面**。adapter pattern 要求 Composer 输出从 `list[dict]` 变成 `ComposedMessages(messages, boundaries)`，所有下游消费者（Cell、Core 内部链路、测试）都要跟着改。代价远大于收益。

未来某天某 Provider 出了非 OpenAI 兼容的 cache API，再单写一个 PR 引入 adapter，那时再付这笔耦合代价。当前不付。

## 4.2 JSONL 字段

每次 LLM 成功调用后写一行 JSON：

```json
{
  "frame": 42,
  "prompt_tokens": 1234,
  "completion_tokens": 567,
  "cached_tokens": 800,
  "elapsed_seconds": 1.23,
  "attempts": 1,
  "ts": "2026-04-29T13:45:21.345678+00:00"
}
```

字段定义：

| 字段 | 来源 | 含义 |
|---|---|---|
| `frame` | `Cell._kernel.L["_frame"] + 1` | 当前帧号（落档前） |
| `prompt_tokens` | `response.usage.prompt_tokens` | 输入 token 数 |
| `completion_tokens` | `response.usage.completion_tokens` | 输出 token 数 |
| `cached_tokens` | `response.usage.prompt_tokens_details.cached_tokens` | OpenAI prompt cache 命中数；Provider 不返回时落 0 |
| `elapsed_seconds` | Core 内 `time.time()` 差 | API 调用总耗时（含重试），三位小数 |
| `attempts` | Core 重试计数器 | 实际调用次数（1 = 首次成功，>1 = 触发了重试） |
| `ts` | `datetime.now(timezone.utc).isoformat()` | ISO-8601 UTC 时间戳 |

**`response.usage` 为 None 时**：跳过本行（不写零行、不补默认值）。framework 不编造数据。

## 4.3 文件位置

`<project>/data/<cell_name>/cache_metrics.jsonl`

每个 Cell 自带一份，与 `frame_log.sqlite` 和 `snapshot.cloudpickle` 同目录。

| 文件 | 答的问题 | 谁写 |
|---|---|---|
| `frame_log.sqlite` | "一路上发生了什么"（Agent 状态） | Kernel |
| `snapshot.cloudpickle` | "现在的状态是什么" | Kernel |
| `cache_metrics.jsonl` | "每次 LLM 调用花了多少钱、命中了多少 cache" | Cell |

JSONL 是 append-only 文本，跨 restart 持续累积。崩溃中途产生的半行通过 `json.loads` 在解析时自然跳过（`json.JSONDecodeError`），不需要事务。

## 4.4 写入责任

Core 不持有文件路径，不写文件。Core 返回 `(Pong, usage: dict)`，把 `usage` 当作纯数据交给 Cell。Cell 持有 `_data_dir`，知道往哪写，调用 `core/telemetry.py` 的 `append_usage(jsonl_path, record)`。

```python
class Cell:
    def step(self, tracer=None):
        ...
        pong, usage = self._core.step(self._ping, tracer, frame_number)
        if self._data_dir is not None and usage:
            jsonl_path = Path(self._data_dir) / "cache_metrics.jsonl"
            telemetry.append_usage(jsonl_path, {
                "frame": frame_number,
                **usage,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        ...
```

`data_dir is None` 的回归路径（Cell 不带数据目录构造，常见于早期单测）跳过 JSONL 写入。

## 4.5 不变量

- Core 不碰文件系统。`pong()` 只返 `(Pong, usage: dict)`。
- Cell 写 JSONL，路径由 `_data_dir` 决定。
- JSONL 字段固定七个：`frame / prompt_tokens / completion_tokens / cached_tokens / elapsed_seconds / attempts / ts`。
- 每次 LLM 成功调用写恰好一行；`response.usage` 为 None 时跳过；调用失败（异常返到 Cell）时不写。
- `cached_tokens` 默认 0 而非 None —— Provider 没返回 = 没命中，可读性优先。
- JSONL 文件 append-only，跨 restart 持续。无 rotation、无 size 限制（运维侧自行截）。
- 没有 adapter pattern，没有 SegmentBoundaries，没有 ComposedMessages。Composer 直接产 `list[dict]` —— 与 §01 一致。
