# Core 文档

Core 是 LLM 的边界适配器。

对外暴露一个原语 `pong(ping, llm_config) → Pong`：接收 Cell 传入的结构化 Ping，把它编排成 OpenAI 兼容的 messages，调 LLM API，对返回文本做 `<think>/<action>/<expect>` 标签解析，返回 Pong 结构体。Pong 的一级结构是 `think` 与 `action`，`action` 再拆为 `operation` 与 `expect`（白皮书 §4）。Core 自身无状态；每次调用独立；模型差异全部由 `llm_config` 注入。

本文件夹是 Core 的完整设计文档。

## 章节

| # | 文件 | 本章建立什么 |
|---|---|---|
| 00 | `00-mental-model.md` | Core 整体样貌：`pong` 原语的输入输出、无状态 pipeline、四个子模块（composer / api_call / retry / parser） |
| 01 | `01-composer.md` | 结构化 Ping → messages 的适配器：三区顺序（system_prompt / frame_stream / signals）、信号分区规则、多模态扩展点 |
| 02 | `02-api-and-retry.md` | OpenAI 兼容 API 调用；`llm_config` 注入规则；可重试 / 不可重试错误分类；指数退避公式 |
| 03 | `03-parser.md` | `<think>/<action>/<expect>` 标签解析；重复标签策略；ParseError 触发条件 |
| 04 | `04-telemetry.md` | 每次 LLM 调用后写一行 JSONL 到 `<cell_data_dir>/cache_metrics.jsonl` —— token 用量 + cache 命中数；为什么不做 adapter pattern |
| 07 | `07-digest.md` | Core 层全部机制与架构决策的电报体浓缩，一页纸 review |

## 阅读方式

主线 `00 → 01 → 02 → 03 → 07`。§04 是观察通道的展开，与 §01 互为补充；读完主线后单独读。

§07 是电报体汇总，既可以做主线读完之后的 quick recap，也可以单独拎出来整体审阅。

## 相关文档

- `../cell/` —— Cell 如何调 `core.pong`，以及在 Core 前后插入 Gate 的位置
- `../kernel/` —— Kernel 返回的 Ping 结构（尤其 signals 的 `(class_name, var_name, scope)` 聚合键）
- `../../references/whitepaper/06-cache.md` —— P1-P5 原则与 cache 层设计理论依据
