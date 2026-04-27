# Kernel/Cell 重构 PR 计划（草案）

> 落手前每个 PR 单独详谈。原则：单层 PR 优先；只有"中间态会坏"的协议同步切换才允许跨层。

| # | 分支 | 层 | 一句话 | 依赖 |
|---|---|---|---|---|
| 1a | `feature/kernel-frame-log-5tables` | Kernel | 五张表 schema（entries / frame_content / summary_content / signals / errors）；写入顺序 entries 行最后；崩溃恢复 `MAX(n_start) FROM entries`。 | — |
| 1b | `feature/cell-data-dir-layout` | Hull + Shell | Hull 给 Cell 注入 `cell_name` + `data_dir`；`vessal.yaml` 默认声明 `cells.main`；`vessal create` 脚手架建 `<project>/data/main/`。 | 1a |
| 1c ✅ | `feature/console-frame-renderer-5tables` | Shell（Console）+ Hull | `Hull.frames()` 拍平为 5-table 列名（`pong_*` / `obs_*` / `verdict_*` / `n`）；Console SPA 跟随。R1 的 `viewer.html` / `frame-renderer.js` 双副本在 v0.0.4 已删除。 | 1a |
| 2 | `feature/kernel-linecache-source` | Kernel | `exec` 时把 operation/expect 注册进 `linecache`；boot 从 `frame_content` 重灌；`inspect.getsource(MyClass)` 跨重启可用。 | 1a |
| 3 | `feature/kernel-lenient-restore` | Kernel | `UnresolvedRef` + `cloudpickle.loads` 永不向外抛；失败原因写进 boot frame 的 `obs_diff_json`。 | 1a |
| 4a | `feature/ping-pong-primitives` | Kernel + Core + Cell | Kernel 收敛到 `ping(pong, ns) → Ping`；Core 收敛到 `pong(ping, llm_config) → Pong`；Composer 从 Kernel 移到 Core；`Ping` 改 `PingState(frame_stream, signals)`。**三层一次性切，否则中间态破坏 Cell 流水线**。 | 1a, 2, 3 |
| 4b | `feature/console-pingstate-adapt` | Shell（Console） | SSE 契约 + Console 渲染跟随新 `PingState` 形态。 | 4a |
| 5a | `feature/hull-cells-list` | Hull | `Hull.cells: list[Cell]`；`vessal.yaml` 支持多 Cell 声明；snapshot/restore 编排迭代每个 cell；`gates/` 目录改 per-Cell 子目录。 | 4a |
| 5b | `feature/compaction-cell` | Kernel(Skill) + Hull | `CompactionSkill` 跨 DB 写主 Cell 的 layer≥1 entry + summary_content；Hull 事件驱动调度（"某层 ≥ k 条未覆盖 entry"触发 `compaction_cell.step()`）。 | 5a |

## 落地后用户感知

- **1a-1c 串完**：内部 schema/路径换了，外部 CLI 不变；Console frame 显示无破坏（中间状态由 1c 同步收尾）。
- **2 / 3**：纯增能 + 纯防御，零破坏。
- **4a + 4b 串完**：Cell 内部接口干净；外部 Skill `signal`/`signal_update` 契约不变。
- **5a**：单 Cell 部署仍只跑 `cells.main`，行为不变；为多 Cell 留下 plumbing。
- **5b**：长会话不再被 hot zone 撑爆 context。

## 每个 PR 内自带

- R4：Whitepaper 对应章节同 PR 更新
- R5：PR 描述写 Layer / Responsibility / Change 三段
- D5：先写失败的 regression 测试再写实现
- 架构测试（`tests/architecture/vessal/*`）跟随更新
