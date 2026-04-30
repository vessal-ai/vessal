# Core llm_config Symmetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the documented `core.pong(ping, llm_config)` per-frame symmetry by making `LLMConfig` (api_key, base_url, model, api_params) a value object passed into `Core.step()` per call, removing all env reads from Core, and propagating ownership of config resolution to Hull.

**Architecture:** Introduce a frozen `LLMConfig` dataclass in `cell/protocol.py` alongside Ping/Pong. Refactor `Core.__init__` to hold only network policy (timeout, max_retries) and an LRU cache of `openai.OpenAI` clients keyed by `(api_key, base_url, timeout)`; `Core.step(ping, llm_config, ...)` looks up / lazily creates the client and forwards `model` + `**api_params` per call. Refactor `Cell.__init__` to take a `default_llm_config: LLMConfig` and pass it to every `core.step()` invocation. Hull resolves `LLMConfig` from `.env` + `hull.toml` once during `_init_phase_1`, logs the effective config (api_key redacted), and constructs main + compaction Cells with their respective configs. Update `docs/architecture/core/{00-mental-model,02-api-and-retry}.md` first per R4 (spec is source of truth, fix spec before code).

**Tech Stack:** Python 3.12+, `dataclasses` (frozen), `openai` SDK ≥ 1.0 (explicit `OpenAI(api_key=, base_url=, timeout=)`), `python-dotenv` (Hull only), `functools.lru_cache` (Core client cache), pytest + `unittest.mock`.

**Layer declaration (R5):** Cell + Core + Hull + docs/architecture/core. Hull owns config resolution (env, dotenv, hull.toml merge) and logs effective values; Cell owns per-frame config injection into Core; Core owns stateless LLM call execution given an LLMConfig; docs/architecture/core encodes the contract. The change moves Vessal toward end-state where Core never touches env, and per-frame model switching becomes a one-line Cell change with no new mechanism.

**PR strategy:** Single PR. All architectural drift sites (Core code, Cell code, Hull code, both architecture docs, all affected tests, boot-log redaction) land together. No deferred cleanup.

---

## File Structure

**Create:**

- `tests/ark/shell/hull/cell/test_llm_config.py` — unit tests for the new `LLMConfig` dataclass.

**Modify:**

- `src/vessal/ark/shell/hull/cell/protocol.py` — add `LLMConfig` frozen dataclass alongside Ping/Pong/State.
- `src/vessal/ark/shell/hull/cell/core/core.py` — remove env reads in `__init__`; add `llm_config` parameter to `step()`; LRU-cache `openai.OpenAI` instances by `(api_key, base_url, timeout)`.
- `src/vessal/ark/shell/hull/cell/core/__init__.py` — re-export `LLMConfig` if helpful for callers.
- `src/vessal/ark/shell/hull/cell/cell.py` — replace `api_params` constructor argument with `default_llm_config: LLMConfig`; pass it to `self._core.step()`.
- `src/vessal/ark/shell/hull/hull_init_mixin.py` — build `LLMConfig` from env + `hull.toml`; log effective values with redacted api_key; pass to main + compaction Cells.
- `src/vessal/ark/shell/hull/cell/core/CONTEXT.md` — update boundary statement to reflect new contract (Core never reads env).
- `docs/architecture/core/00-mental-model.md` — rewrite §0.1 lines 9–15 so api_key/base_url/model are part of `llm_config`, not env-implicit.
- `docs/architecture/core/02-api-and-retry.md` — rewrite §2.1 table + constructor code example to match new contract.
- `docs/architecture/core/07-digest.md` — sync electron-microscope summary.
- `docs/architecture/core/README.md` — sync if it summarizes the contract.
- `tests/ark/shell/hull/cell/core/test_core.py` — adapt all existing tests to new `step(ping, llm_config)` signature.
- `tests/unit/cell/test_core_max_tokens.py` — adapt `max_tokens` derivation if still applicable (likely moves to Cell or LLMConfig).
- `tests/unit/cell/test_core_composer_wiring.py` — adapt to new signature.

**Test:**

- `tests/ark/shell/hull/cell/test_llm_config.py` (created above)
- `tests/ark/shell/hull/cell/core/test_core.py` (modified)
- `tests/ark/shell/hull/test_hull_llm_config_logging.py` — new: assert Hull boot logs effective config with redacted api_key.

**Out of scope (explicit):** Per-frame model switching wired to Skill signals, connection pool migration to Hull-owned registry (route B), whitepaper edits beyond a sanity scan of `references/whitepaper/06-cache.md`. These are tracked as future work.

---

## Task 1: Define LLMConfig dataclass

**Files:**

- Create: `tests/ark/shell/hull/cell/test_llm_config.py`
- Modify: `src/vessal/ark/shell/hull/cell/protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ark/shell/hull/cell/test_llm_config.py
import pytest
from dataclasses import FrozenInstanceError
from vessal.ark.shell.hull.cell.protocol import LLMConfig


def test_llm_config_has_four_fields():
    cfg = LLMConfig(
        api_key="sk-test",
        base_url="http://localhost:8001/v1",
        model="qwen",
        api_params={"temperature": 0.7, "max_tokens": 4096},
    )
    assert cfg.api_key == "sk-test"
    assert cfg.base_url == "http://localhost:8001/v1"
    assert cfg.model == "qwen"
    assert cfg.api_params == {"temperature": 0.7, "max_tokens": 4096}


def test_llm_config_is_frozen():
    cfg = LLMConfig(api_key="k", base_url="u", model="m", api_params={})
    with pytest.raises(FrozenInstanceError):
        cfg.model = "other"


def test_llm_config_api_params_independent_per_instance():
    """api_params dict identity must not be shared across instances."""
    a = LLMConfig(api_key="k", base_url="u", model="m", api_params={"t": 1})
    b = LLMConfig(api_key="k", base_url="u", model="m", api_params={"t": 2})
    assert a.api_params is not b.api_params
    assert a.api_params == {"t": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ark/shell/hull/cell/test_llm_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'LLMConfig'`.

- [ ] **Step 3: Implement LLMConfig**

Append to `src/vessal/ark/shell/hull/cell/protocol.py` (after the existing Ping/Pong/State block):

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    """Per-frame LLM call contract — full set of values that determine one LLM invocation.

    Frozen so that downstream code cannot mutate it after construction; api_params is
    a mutable dict by necessity (callers can pre-build it), but identity is held by
    the LLMConfig instance and must not be reused across configs.

    Owned by: Hull (resolution from env + hull.toml).
    Consumed by: Core.step(ping, llm_config).
    Carried by: Cell (each Cell holds a default LLMConfig and forwards it to core.step()).
    """
    api_key: str
    base_url: str
    model: str
    api_params: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ark/shell/hull/cell/test_llm_config.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add src/vessal/ark/shell/hull/cell/protocol.py tests/ark/shell/hull/cell/test_llm_config.py
git commit -m "feat(cell): add LLMConfig dataclass for per-frame LLM call contract"
```

---

## Task 2: Update architecture spec FIRST (R4)

R4: "If the whitepaper is wrong, the whitepaper is the bug — fix it first, then the code." docs/architecture is the project-level analogue and the user's source-of-truth memory says docs/architecture is the only authoritative spec. Spec edits land before code refactor so the code change has a target to converge to.

**Files:**

- Modify: `docs/architecture/core/00-mental-model.md`
- Modify: `docs/architecture/core/02-api-and-retry.md`
- Modify: `docs/architecture/core/07-digest.md`
- Modify: `docs/architecture/core/README.md`

- [ ] **Step 1: Rewrite `core/00-mental-model.md` §0.1**

Replace lines 9–15 (the `pong(ping, llm_config)` definition + the "连接参数走环境变量" paragraph) with:

```markdown
`pong(ping, llm_config) -> Pong`。Core 的全部对外表面就这一行签名。

`ping` 是 Cell 传入的结构化 Ping 对象：`system_prompt: str` + `state: PingState(frame_stream: FrameStream, signals: dict[tuple, dict])`。结构的由来见 kernel/§00 §0.1，此处只需知道 state 有两部分 —— 低频不变的 frame_stream（Kernel 每帧从 SQLite 五张表现算的 LSM 风格投影）和每帧重写的 signals（按 `(class_name, var_name, scope)` 聚合）。

`llm_config` 是 Cell 每帧灌进来的 **完整 LLM 调用契约**：`LLMConfig(api_key, base_url, model, api_params)`。四个字段构成一次 LLM 调用所需的全部信息 —— `api_key` / `base_url` 决定打到哪家 endpoint、`model` 决定调哪个模型、`api_params` 决定推理参数（temperature / max_tokens / extra_body / ...）。Core 不读 `os.environ`，不持有"启动期默认值"，每一帧的调用语义完全由当帧传入的 LLMConfig 决定。

为什么把连接参数（api_key / base_url）也放进 llm_config？因为 model 和 endpoint 在 OpenAI 兼容生态里是绑定的：本地 Qwen 走 `192.168.x.x:8001`，Anthropic 走 anthropic.com，Provider 切换天然带着 endpoint 切换。把 endpoint 视为"启动期常量"等于假设"Agent 全生命周期只用一家 Provider"，这与白皮书 §05 多 Provider 适配的目标矛盾。LLMConfig 一致地把四个字段当作"逐帧可变值"对待 —— 即使当前阶段每帧都灌同一个 LLMConfig，未来用 cheap_config / smart_config 做逐帧切换时，零新机制即可启用。

LLMConfig 的字段所有权由 Hull 在 `_init_phase_1` 阶段从 `.env` + `hull.toml` 一次性解析得到，启动时打印一行有效配置（api_key 脱敏）；之后 Cell 持有这个值，每次 `core.step()` 调用时整体作为参数传入。Core 自己不持有 LLMConfig 状态，构造时只接 `timeout` / `max_retries`（网络策略，与 LLM 内容正交）。
```

- [ ] **Step 2: Rewrite `core/02-api-and-retry.md` §2.1**

Replace the entire §2.1 (lines 5–44, the table + constructor example) with:

````markdown
## 2.1 llm_config 与职责归属

Core 对任何 OpenAI 兼容的 Provider / 模型零改动适配。这句话能成立的前提是**所有 LLM 调用相关的值通过 llm_config 一并传入、Core 自己不持有任何启动期 LLM 状态**：

| 参数 | 谁定 | 从哪来 | 字段位置 |
|---|---|---|---|
| `api_key` | Hull | `.env` 解析或 `hull.toml [llm]` 节 | `LLMConfig.api_key` |
| `base_url` | Hull | `.env` 解析或 `hull.toml [llm]` 节 | `LLMConfig.base_url` |
| `model` | Hull → Cell | `.env` 解析或 `hull.toml [llm]` 节，未来可由 Skill 信号逐帧切换 | `LLMConfig.model` |
| `api_params`（temperature / max_tokens / extra_body / ...） | Hull → Cell | `hull.toml [core.api_params]` 或 `hull.toml [cells.<name>.api_params]` | `LLMConfig.api_params` |
| `messages` | Core | Composer 产出 | `core.step()` 内部构造 |
| `timeout` / `max_retries` | Hull | `hull.toml [core]` | `Core.__init__` 网络策略 |

**Core 不读 os.environ**。整个 Core 模块没有任何 `os.environ.get` 调用；`openai.OpenAI()` 也以显式形式构造（`OpenAI(api_key=..., base_url=..., timeout=...)`），不依赖 SDK 隐式 env 读取。这条边界由测试 `test_core_does_not_touch_environ` 钉住。

**llm_config 是逐帧契约**。每次 `core.step(ping, llm_config)` 都重新接收 LLMConfig；当前阶段 Cell 持有的 default_llm_config 每帧都灌同一个值，但机制上随时可被覆盖为帧级动态值（用于将来"压缩帧用便宜模型 / 推理帧用前沿模型"的优化）。

### 构造与调用

```python
class Core:
    def __init__(self, *, timeout: float = 60.0, max_retries: int = 3):
        # No LLM config at construction. Core is a stateless protocol adapter.
        self._timeout = timeout
        self._max_retries = max_retries
        self._client_cache: dict[tuple, openai.OpenAI] = {}

    def step(self, ping: Ping, llm_config: LLMConfig, *,
             tracer: TracerLike | None = None, frame: int = 0) -> tuple[Pong, dict]:
        client = self._client_for(llm_config)
        messages = self._build_messages(ping)
        response = client.chat.completions.create(
            model=llm_config.model,
            messages=messages,
            **llm_config.api_params,
        )
        ...

    def _client_for(self, cfg: LLMConfig) -> openai.OpenAI:
        # Cache by (api_key, base_url, timeout) so repeated frames with the same
        # LLMConfig reuse the underlying httpx connection pool. Cache size starts
        # at 1 (the steady-state case) and grows naturally if Cell starts switching
        # configs per frame. No eviction policy needed — Vessal sees at most a few
        # distinct configs per project lifetime.
        key = (cfg.api_key, cfg.base_url, self._timeout)
        client = self._client_cache.get(key)
        if client is None:
            client = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=self._timeout)
            self._client_cache[key] = client
        return client
```

llm_config.api_params 整体 `**unpack` 进 `create()` —— Core 不筛、不补默认值。Cell 想传什么就传什么，`model` / `messages` 这两个被 Core 占用的 key 若在 api_params 里重复会被 Python 的 `**kwargs` 规则直接报错，这是期望行为（防止上游误覆盖 Core 的固定职责）。
````

- [ ] **Step 3: Update `core/07-digest.md`**

Open `docs/architecture/core/07-digest.md`. Search for any line containing `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `os.environ`, or `api_params` and reword so the digest matches the new contract: Core takes `(timeout, max_retries)` at construction; LLM contract enters per call as `LLMConfig`; api_key/base_url/model are Hull-resolved.

Replace any phrase like "客户端级配置 / 启动时一次性绑定" with "逐帧 LLMConfig / Core 自身无启动期 LLM 状态".

- [ ] **Step 4: Update `core/README.md`**

Same scan as Step 3. If the README has a "constructor" or "config" summary block, sync it to the new shape:

```python
Core(timeout=60.0, max_retries=3)             # constructor: network policy only
core.step(ping, llm_config, tracer, frame)    # per-frame call
```

- [ ] **Step 5: Run docs lint (if any)**

Run: `uv run pytest tests/architecture/ -v`
Expected: PASS (we haven't broken architecture invariants yet — code still matches old spec, but spec change alone shouldn't fail any test). If a test asserts a specific phrase from the old docs, it will fail; record it and address in Task 3.

- [ ] **Step 6: Commit**

```bash
git add docs/architecture/core/
git commit -m "docs(core): update spec to llm_config-per-frame symmetry (R4 spec-first)

R4: spec is source of truth; spec change must precede code. This commit
aligns the core/ architecture docs with the documented (but un-implemented)
pong(ping, llm_config) contract from core/00-mental-model.md §0.1, and
extends llm_config to include api_key/base_url/model so the four LLM-call
fields are all carried per-frame instead of env-implicit at startup.

Code change follows in subsequent commits."
```

---

## Task 3: Refactor Core — TDD failing test

**Files:**

- Modify: `tests/ark/shell/hull/cell/core/test_core.py`

- [ ] **Step 1: Write the failing tests at the top of test_core.py (after imports)**

```python
# === New contract: Core takes llm_config per call, never reads env ===

def _make_llm_config(**overrides) -> "LLMConfig":
    from vessal.ark.shell.hull.cell.protocol import LLMConfig
    base = dict(
        api_key="sk-test",
        base_url="http://localhost:9999/v1",
        model="test-model",
        api_params={"temperature": 0.5, "max_tokens": 2048},
    )
    base.update(overrides)
    return LLMConfig(**base)


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_step_takes_llm_config_per_call(mock_openai_cls):
    """Core.step(ping, llm_config) is the new signature; llm_config is required."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_mock_response(
        "<action>x = 1</action>"
    )
    core = Core()
    cfg = _make_llm_config()
    pong, _ = core.step(_make_ping(), cfg)

    call_args = mock_client.chat.completions.create.call_args
    assert call_args.kwargs["model"] == "test-model"
    assert call_args.kwargs["temperature"] == 0.5
    assert call_args.kwargs["max_tokens"] == 2048
    assert isinstance(pong, Pong)


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_constructs_client_with_explicit_credentials(mock_openai_cls):
    """openai.OpenAI(...) MUST be called with api_key= and base_url= explicitly,
    not relying on SDK env-implicit behavior. This is the regression test for
    the 403/phantom-config class of bugs."""
    mock_openai_cls.return_value = MagicMock()
    core = Core(timeout=42.0)
    cfg = _make_llm_config(api_key="sk-explicit", base_url="http://x/v1")
    core.step(_make_ping(), cfg)

    mock_openai_cls.assert_called_once_with(
        api_key="sk-explicit",
        base_url="http://x/v1",
        timeout=42.0,
    )


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_does_not_touch_environ(mock_openai_cls, monkeypatch):
    """Core MUST NOT read OPENAI_* env vars. Set hostile env values; if Core
    reaches for them, the test fails (because llm_config values would be ignored)."""
    monkeypatch.setenv("OPENAI_API_KEY", "WRONG_KEY_FROM_ENV")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://wrong.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "WRONG_MODEL_FROM_ENV")

    mock_openai_cls.return_value = MagicMock()
    core = Core()
    cfg = _make_llm_config(api_key="sk-correct", base_url="http://right/v1", model="right-model")
    core.step(_make_ping(), cfg)

    # OpenAI() received the LLMConfig values, not the env values
    mock_openai_cls.assert_called_once_with(
        api_key="sk-correct", base_url="http://right/v1", timeout=60.0,
    )
    create_kwargs = mock_openai_cls.return_value.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "right-model"


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_caches_client_per_credentials(mock_openai_cls):
    """Two step() calls with the same LLMConfig MUST reuse the OpenAI client
    instance (one openai.OpenAI() call, not two)."""
    mock_openai_cls.return_value = MagicMock()
    mock_openai_cls.return_value.chat.completions.create.return_value = _make_mock_response(
        "<action>pass</action>"
    )
    core = Core()
    cfg = _make_llm_config()
    core.step(_make_ping(), cfg)
    core.step(_make_ping(), cfg)
    assert mock_openai_cls.call_count == 1


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_creates_distinct_clients_for_distinct_configs(mock_openai_cls):
    """Two step() calls with different LLMConfigs MUST create two clients
    (this is the future per-frame model switching enabler)."""
    mock_openai_cls.return_value = MagicMock()
    mock_openai_cls.return_value.chat.completions.create.return_value = _make_mock_response(
        "<action>pass</action>"
    )
    core = Core()
    core.step(_make_ping(), _make_llm_config(api_key="sk-a", base_url="http://a/v1"))
    core.step(_make_ping(), _make_llm_config(api_key="sk-b", base_url="http://b/v1"))
    assert mock_openai_cls.call_count == 2
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py::test_core_step_takes_llm_config_per_call tests/ark/shell/hull/cell/core/test_core.py::test_core_constructs_client_with_explicit_credentials tests/ark/shell/hull/cell/core/test_core.py::test_core_does_not_touch_environ tests/ark/shell/hull/cell/core/test_core.py::test_core_caches_client_per_credentials tests/ark/shell/hull/cell/core/test_core.py::test_core_creates_distinct_clients_for_distinct_configs -v`
Expected: ALL FAIL — Core.step doesn't accept llm_config; OpenAI() called without api_key/base_url; env vars are still read.

---

## Task 4: Refactor Core to satisfy the new contract

**Files:**

- Modify: `src/vessal/ark/shell/hull/cell/core/core.py`

- [ ] **Step 1: Replace `Core.__init__` and `Core.step` signatures + bodies**

Open `src/vessal/ark/shell/hull/cell/core/core.py`. Replace lines 51–82 (the `_DEFAULT_API_PARAMS` class attr + `__init__`) with:

```python
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Core.

        Core holds only network policy at construction time. All LLM-call
        semantics (api_key, base_url, model, api_params) arrive per call
        via the llm_config argument to step().

        Args:
            timeout:    Request timeout in seconds, default 60. 0 means no timeout (not recommended).
            max_retries: Maximum retry count for retryable network errors, default 3.
        """
        self._timeout = timeout
        self._max_retries = max_retries
        self._client_cache: dict[tuple[str, str, float], "openai.OpenAI"] = {}
```

Replace `step()` signature on line 95–100 with:

```python
    def step(
        self,
        ping: Ping,
        llm_config: "LLMConfig",
        *,
        tracer: TracerLike | None = None,
        frame: int = 0,
    ) -> tuple[Pong, dict]:
```

Inside `step()`, replace the `response = self._client.chat.completions.create(...)` block with:

```python
                client = self._client_for(llm_config)
                response = client.chat.completions.create(
                    model=llm_config.model,
                    messages=messages,
                    **llm_config.api_params,
                )
```

- [ ] **Step 2: Add the `_client_for` helper**

Add as a method on `Core`, immediately after `__init__`:

```python
    def _client_for(self, cfg: "LLMConfig") -> "openai.OpenAI":
        key = (cfg.api_key, cfg.base_url, self._timeout)
        client = self._client_cache.get(key)
        if client is None:
            client = openai.OpenAI(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                timeout=self._timeout,
            )
            self._client_cache[key] = client
        return client
```

- [ ] **Step 3: Add the LLMConfig import**

At the top of `core.py`, add:

```python
from vessal.ark.shell.hull.cell.protocol import Ping, Pong, LLMConfig
```

(replace the existing `from ... import Ping, Pong` line).

- [ ] **Step 4: Remove the `max_tokens` property's reliance on `self._api_params`**

The property on lines 84–88 currently reads `self._api_params`. Since Core no longer holds api_params, the responsibility moves to Cell. Delete the `max_tokens` property from Core entirely (Cell already exposes its own `max_tokens` property — Task 5 updates that to read from `default_llm_config.api_params`).

- [ ] **Step 5: Update the docstring header comment block (lines 1–19)**

Rewrite the file header to:

```python
"""core.py — LLM call pipeline: Core is the reasoning half of the Agent loop, responsible for model invocation and retries."""
#
#   1. Constructs OpenAI-compatible messages from Ping (system_prompt + state)
#   2. Calls the LLM API (OpenAI-compatible interface), handles network retries
#   3. Extracts text from the response, calls parse_response() to return a Pong
#
# Core is stateless wrt LLM contract:
#   - Construction takes only network policy (timeout, max_retries).
#   - Per-call llm_config (api_key, base_url, model, api_params) arrives via step().
#   - openai.OpenAI() instances are cached internally by (api_key, base_url, timeout)
#     so repeated frames with the same LLMConfig reuse the underlying connection pool.
#
# Network robustness:
#   - Retryable errors (network timeout, connection drop): automatic retry with exponential backoff
#   - Non-retryable errors (auth failure, bad request): raise immediately, no wasted retries
#
# Public interface:
#   Core(timeout, max_retries)                           constructor, network policy only
#   step(ping, llm_config, tracer, frame) -> Pong        per-frame LLM call
```

- [ ] **Step 6: Run new tests to verify they pass**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py::test_core_step_takes_llm_config_per_call tests/ark/shell/hull/cell/core/test_core.py::test_core_constructs_client_with_explicit_credentials tests/ark/shell/hull/cell/core/test_core.py::test_core_does_not_touch_environ tests/ark/shell/hull/cell/core/test_core.py::test_core_caches_client_per_credentials tests/ark/shell/hull/cell/core/test_core.py::test_core_creates_distinct_clients_for_distinct_configs -v`
Expected: ALL PASS.

- [ ] **Step 7: Run full Core test file to see what else broke**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py -v`
Expected: ~25 PRE-EXISTING tests FAIL because they call `core.step(_make_ping())` without `llm_config`, or assert `core._model == "..."`, or assert `mock_openai_cls.assert_called_once_with(timeout=60.0)` (without api_key/base_url). Record the failing list — Task 6 fixes them.

- [ ] **Step 8: Commit**

```bash
git add src/vessal/ark/shell/hull/cell/core/core.py tests/ark/shell/hull/cell/core/test_core.py
git commit -m "refactor(core): take LLMConfig per call, drop env reads, cache clients

Core.step() now requires (ping, llm_config). Core.__init__ holds only network
policy (timeout, max_retries). openai.OpenAI() is constructed with explicit
api_key/base_url from llm_config; results are cached by (api_key, base_url,
timeout) so repeated frames with the same config reuse the connection pool.

Restores the documented core.pong(ping, llm_config) contract from
docs/architecture/core/00-mental-model.md §0.1. Eliminates the phantom-config
class of bugs (e.g. dotenv override=False masking .env values with stale
shell env, surfacing as 403 PermissionDeniedError).

Pre-existing Core tests broken by signature change; fixed in subsequent commit."
```

---

## Task 5: Refactor Cell to carry default LLMConfig

**Files:**

- Modify: `src/vessal/ark/shell/hull/cell/cell.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/ark/shell/hull/cell/core/test_core.py` (or new file `tests/ark/shell/hull/cell/test_cell_llm_config.py`):

```python
@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_cell_passes_default_llm_config_to_core(mock_openai_cls):
    """Cell holds default_llm_config and passes it to every core.step() call."""
    from vessal.ark.shell.hull.cell.cell import Cell
    from vessal.ark.shell.hull.cell.protocol import LLMConfig

    mock_openai_cls.return_value = MagicMock()
    mock_openai_cls.return_value.chat.completions.create.return_value = _make_mock_response(
        "<action>pass</action>"
    )

    cfg = LLMConfig(api_key="sk-cell", base_url="http://cell/v1",
                    model="cell-model", api_params={"temperature": 0.3})
    cell = Cell(default_llm_config=cfg)

    cell.step()  # bootstrap + frame 1

    mock_openai_cls.assert_called_once_with(
        api_key="sk-cell", base_url="http://cell/v1", timeout=60.0,
    )
    create_kwargs = mock_openai_cls.return_value.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "cell-model"
    assert create_kwargs["temperature"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py::test_cell_passes_default_llm_config_to_core -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'default_llm_config'`.

- [ ] **Step 3: Update Cell.__init__ signature**

In `src/vessal/ark/shell/hull/cell/cell.py`, replace the constructor (lines 49–67 region):

```python
    def __init__(
        self,
        boot_script: str | None = None,
        timeout: float = 60.0,
        core_max_retries: int = 3,
        default_llm_config: "LLMConfig | None" = None,
        action_gate: str = "auto",
        state_gate: str = "auto",
        *,
        cell_name: str = "main",
        data_dir: str | None = None,
        restore_path: str | None = None,
    ) -> None:
```

Update the docstring `Args:` block: replace the `api_params:` paragraph with:

```
default_llm_config: LLMConfig used for every core.step() call this Cell makes.
    Resolved by Hull from .env + hull.toml; carries api_key, base_url,
    model, and api_params. None is allowed only for unit tests that mock
    Core entirely; production Hull always passes a value.
```

- [ ] **Step 4: Wire the new field through to Core.step**

In `Cell.__init__`, replace lines around `self._core = Core(...)` (lines 103–107):

```python
        self._kernel = Kernel(boot_script=boot_script, db_path=db_path, restore_path=restore_path)
        self._core = Core(timeout=timeout, max_retries=core_max_retries)
        self._default_llm_config = default_llm_config
```

In `Cell.step()` (around line 205), update the core.step call:

```python
        try:
            assert self._default_llm_config is not None, (
                "Cell.step() requires default_llm_config; only unit tests that mock Core may pass None."
            )
            self._pong, usage = self._core.step(
                self._ping,
                self._default_llm_config,
                tracer=tracer,
                frame=frame_number,
            )
```

- [ ] **Step 5: Update Cell.max_tokens property**

Replace the existing `max_tokens` property (line 116–117):

```python
    @property
    def max_tokens(self) -> int:
        """Token budget derived from default_llm_config.api_params."""
        if self._default_llm_config is None:
            return 4096
        ap = self._default_llm_config.api_params
        return ap.get("max_tokens", ap.get("max_completion_tokens", 4096))
```

- [ ] **Step 6: Add LLMConfig import**

At the top of `cell.py`, change:

```python
from vessal.ark.shell.hull.cell.protocol import Ping, Pong, StepResult
```

to:

```python
from vessal.ark.shell.hull.cell.protocol import Ping, Pong, StepResult, LLMConfig
```

- [ ] **Step 7: Run new test to verify it passes**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py::test_cell_passes_default_llm_config_to_core -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/vessal/ark/shell/hull/cell/cell.py tests/ark/shell/hull/cell/core/test_core.py
git commit -m "refactor(cell): take default_llm_config, forward to core.step per call

Cell.__init__ replaces api_params= with default_llm_config: LLMConfig.
Cell.step() forwards default_llm_config to core.step() each frame, completing
the per-frame symmetry: Kernel.ping(pong, namespace) | Core.pong(ping, llm_config).

Cell.max_tokens now derives from default_llm_config.api_params."
```

---

## Task 6: Adapt pre-existing Core tests to new signatures

**Files:**

- Modify: `tests/ark/shell/hull/cell/core/test_core.py`
- Modify: `tests/unit/cell/test_core_max_tokens.py`
- Modify: `tests/unit/cell/test_core_composer_wiring.py`

- [ ] **Step 1: Identify failing tests**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py tests/unit/cell/ -v 2>&1 | grep FAIL`

Expected list (approximate): `test_step_calls_api_correctly`, `test_step_returns_pong`, `test_step_empty_response`, `test_client_created_with_timeout`, `test_client_created_with_custom_timeout`, `test_model_from_env`, `test_default_parameters`, `test_system_and_user_messages_sent`, `test_messages_sent_every_call`, `test_default_timeout`, `test_custom_timeout`, `test_retry_on_timeout`, `test_retry_exhausted_raises`, `test_no_retry_on_auth_error`, `test_no_retry_on_permission_error`, `test_no_retry_on_bad_request`, `test_retry_on_connection_error`, `test_retry_on_server_error`, `test_core_step_accepts_ping`, `test_core_step_ping_builds_system_and_user_messages`, `test_core_step_pong_parsed_correctly`, `TestCoreUsageReturn::test_returns_usage_tuple`, `TestCoreUsageReturn::test_returns_none_when_no_usage`, `test_core_step_returns_pong_and_usage_dict`, `test_core_step_usage_empty_when_response_usage_is_none`, `test_core_step_cached_tokens_defaults_to_zero`.

- [ ] **Step 2: Mass-rewrite each call site**

Rule for each broken test:

1. If the test calls `core.step(ping)` or `core.step(_make_ping())`, change to `core.step(ping, _make_llm_config())` (use the helper added in Task 3).
2. If the test calls `Core(api_params={...})`, drop the `api_params` argument and instead pass an `LLMConfig(api_params={...})` to `step()`.
3. If the test asserts `core._model == "..."` or `core._api_params[...] == ...`, delete the assertion (no longer applicable — these moved to LLMConfig).
4. If the test asserts `mock_openai_cls.assert_called_once_with(timeout=60.0)`, change to `mock_openai_cls.assert_called_once_with(api_key=ANY, base_url=ANY, timeout=60.0)` (`from unittest.mock import ANY`) — or assert specific values if the test created an LLMConfig.
5. Delete `test_model_from_env` and `test_default_parameters` entirely (no longer applicable; LLMConfig is fully explicit, no env-driven defaults inside Core).

Concrete examples:

`test_step_calls_api_correctly` (line 162) becomes:
```python
@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_step_calls_api_correctly(self, mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_mock_response(
        "<think>thinking</think>\n<action>\nx = 1\n</action>"
    )
    core = Core()
    cfg = _make_llm_config(model="test-model",
                           api_params={"temperature": 0.5, "max_tokens": 2048})
    pong, _ = core.step(_make_ping(), cfg)

    call_args = mock_client.chat.completions.create.call_args
    assert call_args.kwargs["model"] == "test-model"
    assert call_args.kwargs["temperature"] == 0.5
    assert call_args.kwargs["max_tokens"] == 2048
    assert isinstance(pong, Pong)
```

`test_default_timeout` (line 321) becomes:
```python
@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_default_timeout(self, mock_openai_cls):
    """Default timeout is 60.0; openai.OpenAI() is constructed lazily on first step()."""
    mock_openai_cls.return_value = MagicMock()
    mock_openai_cls.return_value.chat.completions.create.return_value = _make_mock_response(
        "<action>pass</action>"
    )
    core = Core()
    core.step(_make_ping(), _make_llm_config())
    mock_openai_cls.assert_called_once_with(
        api_key="sk-test", base_url="http://localhost:9999/v1", timeout=60.0,
    )
```

For `test_core_step_returns_pong_and_usage_dict` (lines 582–616) — the `monkeypatch.setattr(core._client.chat.completions, "create", ...)` line will fail because `core._client` no longer exists. Change to:

```python
def test_core_step_returns_pong_and_usage_dict(monkeypatch):
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        # ... build _FakeResponse as before ...
        mock_client.chat.completions.create.return_value = _FakeResponse
        core = Core()
        pong, usage = core.step(ping, _make_llm_config(), tracer=None, frame=1)
        # assertions unchanged
```

- [ ] **Step 3: Run all Core/Cell tests**

Run: `uv run pytest tests/ark/shell/hull/cell/core/test_core.py tests/unit/cell/ -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/ark/shell/hull/cell/core/test_core.py tests/unit/cell/
git commit -m "test(core,cell): adapt pre-existing tests to LLMConfig-per-call signature

Drops test_model_from_env and test_default_parameters (no longer applicable;
LLMConfig is fully explicit, Core has no env-driven defaults). All other Core
tests reshape calls to core.step(ping, llm_config) and assert openai.OpenAI()
is constructed with explicit api_key/base_url."
```

---

## Task 7: Refactor Hull to build LLMConfig + log redacted

**Files:**

- Modify: `src/vessal/ark/shell/hull/hull_init_mixin.py`
- Create: `tests/ark/shell/hull/test_hull_llm_config_logging.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ark/shell/hull/test_hull_llm_config_logging.py
import logging
from unittest.mock import patch
from pathlib import Path
import pytest


def _make_minimal_project(tmp_path: Path) -> Path:
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-test123456789abcdef\n"
        "OPENAI_BASE_URL=http://localhost:8001/v1\n"
        "OPENAI_MODEL=qwen-test\n"
    )
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "t"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 1\n'
        '[core]\ntimeout = 60\nmax_retries = 3\n'
        '[core.api_params]\ntemperature = 0.7\nmax_tokens = 4096\n'
        '[hull]\nskills = []\n'
        '[cells.main]\ndata_dir = "data/main"\n'
        '[gates]\n'
    )
    (tmp_path / "SOUL.md").write_text("test agent")
    return tmp_path


def test_hull_logs_redacted_llm_config_at_boot(tmp_path, caplog):
    from vessal.ark.shell.hull.hull import Hull
    project = _make_minimal_project(tmp_path)

    with caplog.at_level(logging.INFO):
        with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
            Hull(project_dir=str(project))

    log_text = "\n".join(r.message for r in caplog.records)
    assert "core config" in log_text.lower() or "llm config" in log_text.lower()
    assert "qwen-test" in log_text
    assert "http://localhost:8001/v1" in log_text
    # api_key MUST be redacted; full key MUST NOT appear
    assert "sk-test123456789abcdef" not in log_text
    # redacted form should show prefix + last char (or similar)
    assert "sk-" in log_text and "***" in log_text


def test_hull_passes_llm_config_to_main_cell(tmp_path):
    from vessal.ark.shell.hull.hull import Hull
    from vessal.ark.shell.hull.cell.protocol import LLMConfig
    project = _make_minimal_project(tmp_path)

    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        hull = Hull(project_dir=str(project))

    cfg = hull._main_cell._default_llm_config
    assert isinstance(cfg, LLMConfig)
    assert cfg.api_key == "sk-test123456789abcdef"
    assert cfg.base_url == "http://localhost:8001/v1"
    assert cfg.model == "qwen-test"
    assert cfg.api_params["temperature"] == 0.7
    assert cfg.api_params["max_tokens"] == 4096
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ark/shell/hull/test_hull_llm_config_logging.py -v`
Expected: FAIL — Hull does not yet build LLMConfig or log it; `_default_llm_config` attribute does not exist on Cell instance from old api_params path.

- [ ] **Step 3: Add `_resolve_llm_config` helper to Hull**

In `src/vessal/ark/shell/hull/hull_init_mixin.py`, add a helper method (above `_init_phase_2` or wherever Cells are constructed):

```python
    def _resolve_llm_config(self, core_cfg: dict, cell_cfg: dict,
                           overrides: dict | None = None) -> "LLMConfig":
        """Build an LLMConfig from env + hull.toml. Hull-only concern.

        Precedence: overrides (per-cell hull.toml section) > [core.api_params] > defaults.
        api_key/base_url/model come from environment (loaded via load_dotenv earlier
        in _init_phase_1; that load is the only env-touching point in Vessal).
        """
        from vessal.ark.shell.hull.cell.protocol import LLMConfig

        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        model = os.environ.get("OPENAI_MODEL", "")
        if not api_key or not base_url or not model:
            raise RuntimeError(
                f"Hull cannot resolve LLMConfig: missing one of OPENAI_API_KEY / "
                f"OPENAI_BASE_URL / OPENAI_MODEL. Check your .env (loaded from "
                f"{self._project_dir / '.env'!s})."
            )

        overrides = overrides or {}
        api_params = overrides.get("api_params") or core_cfg.get("api_params", {
            "temperature": cell_cfg.get("temperature", 0.7),
            "max_tokens": cell_cfg.get("max_tokens", 4096),
        })

        return LLMConfig(
            api_key=api_key, base_url=base_url, model=model,
            api_params=dict(api_params),
        )

    @staticmethod
    def _redact_api_key(api_key: str) -> str:
        """Show first 3 + last 1 chars, mask middle. 'sk-test...c' style."""
        if len(api_key) <= 8:
            return "***"
        return f"{api_key[:3]}***{api_key[-1]}"
```

- [ ] **Step 4: Use the helper in `_init_phase_2`**

In `hull_init_mixin.py` around the existing api_params block (lines 160–172), replace:

```python
        api_params = core_cfg.get("api_params", {
            "temperature": cell_cfg.get("temperature", 0.7),
            "max_tokens": cell_cfg.get("max_tokens", 4096),
        })
        self._main_cell = Cell(
            boot_script=boot_script,
            timeout=core_cfg.get("timeout", 60.0),
            core_max_retries=core_cfg.get("max_retries", 3),
            api_params=api_params,
            cell_name=cell_name,
            data_dir=str(data_dir_abs),
            restore_path=restore_path,
        )
```

with:

```python
        main_llm_config = self._resolve_llm_config(core_cfg, cell_cfg)
        logger.info(
            "core config: model=%s base_url=%s api_key=%s api_params=%s",
            main_llm_config.model,
            main_llm_config.base_url,
            self._redact_api_key(main_llm_config.api_key),
            main_llm_config.api_params,
        )
        self._main_cell = Cell(
            boot_script=boot_script,
            timeout=core_cfg.get("timeout", 60.0),
            core_max_retries=core_cfg.get("max_retries", 3),
            default_llm_config=main_llm_config,
            cell_name=cell_name,
            data_dir=str(data_dir_abs),
            restore_path=restore_path,
        )
```

And around the compaction Cell block (lines 200–208), replace with:

```python
        compaction_llm_config = self._resolve_llm_config(
            core_cfg, cell_cfg, overrides=compaction_cfg
        )
        if compaction_llm_config != main_llm_config:
            logger.info(
                "compaction core config: model=%s base_url=%s api_key=%s api_params=%s",
                compaction_llm_config.model,
                compaction_llm_config.base_url,
                self._redact_api_key(compaction_llm_config.api_key),
                compaction_llm_config.api_params,
            )
        self._compaction_cell = Cell(
            boot_script=compaction_boot_script,
            timeout=core_cfg.get("timeout", 60.0),
            core_max_retries=core_cfg.get("max_retries", 3),
            default_llm_config=compaction_llm_config,
            cell_name="compaction",
            data_dir=str(compaction_data_dir_abs),
            restore_path=compaction_restore,
        )
```

- [ ] **Step 5: Ensure `logger` is defined at module level**

If not already present at top of `hull_init_mixin.py`:

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 6: Run new tests to verify they pass**

Run: `uv run pytest tests/ark/shell/hull/test_hull_llm_config_logging.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/vessal/ark/shell/hull/hull_init_mixin.py tests/ark/shell/hull/test_hull_llm_config_logging.py
git commit -m "feat(hull): build LLMConfig at boot, log redacted, pass to main+compaction Cells

Hull resolves OPENAI_{API_KEY,BASE_URL,MODEL} from environment (loaded by
load_dotenv in _init_phase_1) plus hull.toml [core.api_params] into a
single LLMConfig value, logs the effective config with api_key redacted
(sk-***c form), and passes it to Cell.__init__ as default_llm_config.

Compaction Cell receives its own LLMConfig (overrides honored from
[cells.compaction.api_params]); when distinct from main, a separate
log line is emitted.

Closes the phantom-config class of bugs at the source: the values that
control LLM calls are now (a) resolved in exactly one place, and
(b) printed at boot so the user can verify resolution before any frame runs."
```

---

## Task 8: Update CONTEXT.md and verify R-Cell-2026-04-21 invariants

**Files:**

- Modify: `src/vessal/ark/shell/hull/cell/core/CONTEXT.md`

- [ ] **Step 1: Update Core's boundary statement**

Open `src/vessal/ark/shell/hull/cell/core/CONTEXT.md`. Locate the boundary section (around line 15 has the "Hardcoding API parameters beyond model selection" bullet). Rewrite the whole boundary block to:

```markdown
## Boundary

Core does:
- Receive a `Ping` and an `LLMConfig` per call (`step(ping, llm_config)`)
- Compose messages from Ping (system_prompt + frame_stream + signals)
- Call `chat.completions.create(model=llm_config.model, messages=..., **llm_config.api_params)`
- Parse `<think>/<action>/<expect>` from the response, return `Pong`
- Cache `openai.OpenAI` clients internally by `(api_key, base_url, timeout)` for connection reuse

Core does NOT:
- Read `os.environ` (the entire module has zero `os.environ.get` calls; pinned by `test_core_does_not_touch_environ`)
- Hold any startup-bound LLM state — every step() call re-receives full LLMConfig
- Hardcode API parameter defaults — temperature / max_tokens / extra_body all come from llm_config.api_params
- Touch SQLite (Kernel's job), tracer lifecycle (Hull's job), or boot scripts (Kernel's job)
```

- [ ] **Step 2: Verify R-Cell-2026-04-21 dependency tree test still passes**

Run: `uv run pytest tests/architecture/vessal/test_cell_dependency_tree.py -v`
Expected: PASS. The Cell boundary rule (no imports of `vessal.ark.util.logging`, no access to `Core._DEFAULT_API_PARAMS`, no `fs._hot`) is preserved or strengthened — `_DEFAULT_API_PARAMS` is now deleted entirely.

- [ ] **Step 3: Commit**

```bash
git add src/vessal/ark/shell/hull/cell/core/CONTEXT.md
git commit -m "docs(core): update CONTEXT.md boundary to reflect LLMConfig-per-call contract"
```

---

## Task 9: Full test sweep + smoke test

**Files:**

- (No new files; verification only)

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest -x`
Expected: PASS. If any unexpected test fails, diagnose:
- Test calls `Core(api_params=...)` → adapt to new constructor + LLMConfig.
- Test calls `Cell(api_params=...)` → adapt to `default_llm_config=`.
- Hull integration test fails because `.env` is missing in the fixture → add a minimal `.env` with `OPENAI_*` vars to the test fixture.

- [ ] **Step 2: Run boot smoke test**

If a smoke test exists for `vessal start` (per R14), run:

```bash
uv run pytest tests/smoke/ -v
```

Expected: PASS, including a check that the boot log line `core config: model=... base_url=... api_key=sk-***x` appears.

- [ ] **Step 3: Manual end-to-end check (Explore mode user)**

The plan executor should manually start `vessal start` in the `agent_test/` project and confirm:
1. The startup log includes `core config: model=qwen_3_vl_235b_a22b_awq_int4 base_url=http://192.168.40.42:8001/v1 api_key=sk-***x api_params={...}` (or equivalent for the user's `.env`).
2. Sending a Chat message produces a normal SORA frame (no 403, no immediate sleep-back).
3. The Console UI stays in `active` for the duration of the frame, transitions to `sleep` only after the frame commits.

If 403 still occurs, the bug is in the local LLM endpoint (network / model unavailability) and not in Vessal — confirm by running `curl` against the endpoint with the same key/base_url.

---

## Task 10: Whitepaper sanity scan

**Files:**

- Read-only: `references/whitepaper/06-cache.md`

- [ ] **Step 1: Open and inspect the one whitepaper match**

Open `references/whitepaper/06-cache.md` line ~556 (the only match for `api_params` / `llm_config` / `OPENAI_*` in the whitepaper).

- [ ] **Step 2: Decision**

If the prose still describes Core as "reading env" or treating api_params as the only per-frame config: rewrite the local sentence to mention `LLMConfig` instead. If the prose is generic enough to remain accurate (e.g. just mentions `api_params` as a slot that receives values), leave it.

- [ ] **Step 3: Commit (if changes were made)**

```bash
git add references/whitepaper/06-cache.md
git commit -m "docs(whitepaper): sync 06-cache.md with LLMConfig-per-call contract"
```

If no change was needed, skip the commit and document the no-op in the PR description ("whitepaper sanity-scanned, no edits required").

---

## Task 11: PR description (R5 + D2 + D5 declaration)

**Files:**

- (No file edits; PR creation only)

- [ ] **Step 1: Open the PR**

```bash
gh pr create --base develop --title "refactor(core): restore llm_config-per-frame symmetry" --body "$(cat <<'EOF'
## Layer (R5)

Cell + Core + Hull + docs/architecture/core. Hull owns LLMConfig resolution from env + hull.toml; Cell owns per-frame config injection; Core owns stateless LLM call execution; docs/architecture/core encodes the contract.

## Responsibility

Core was documented since 2026-Q1 as `pong(ping, llm_config) -> Pong` with llm_config as a per-frame value (docs/architecture/core/00-mental-model.md §0.1), but the implementation kept LLM contract as constructor state and additionally let api_key/base_url leak to ambient env via openai SDK's implicit reads. This PR closes the gap by promoting LLMConfig to a frozen dataclass (api_key, base_url, model, api_params), passing it to Core.step() per call, removing all env reads from Core, and restoring per-frame symmetry with Kernel.ping(pong, namespace).

## Change

- Add `LLMConfig` dataclass to `cell/protocol.py`.
- Refactor `Core` to take `(timeout, max_retries)` only; `step(ping, llm_config, ...)` per call; cache `openai.OpenAI` instances by `(api_key, base_url, timeout)`.
- Refactor `Cell` to take `default_llm_config`, forward to `core.step()` each frame.
- Refactor `Hull._init_phase_2` to build LLMConfig (env + hull.toml), log effective config (api_key redacted), pass to main + compaction Cells.
- Update `docs/architecture/core/{00-mental-model,02-api-and-retry,07-digest,README}.md` to match new contract.
- Update `cell/core/CONTEXT.md` boundary statement.

## Why (D2 — Five Whys)

1. Why did sending a Chat message produce a 403? → Core's openai client was constructed without explicit api_key/base_url and read OPENAI_* env vars set by the parent shell (not the project .env).
2. Why did parent-shell env shadow .env? → `load_dotenv()` defaults to `override=False`.
3. Why didn't Core simply pass override=True? → Because the deeper bug is that Core reads env at all. Per docs/architecture/core/00-mental-model.md §0.1, Core is supposed to be stateless wrt LLM contract — config arrives per call.
4. Why did the implementation drift from the documented contract? → `__init__` was easier to write than threading config through every step() call, and the OpenAI SDK's implicit env behavior made the hidden coupling invisible.
5. Why did the doc itself contain a contradictory line ("api_key/base_url 走环境变量 / Core 不转手", core/00-mental-model.md line 15)? → The doc evolved across multiple iterations; line 13 stated the new contract while line 15 preserved the old caveat. Both lines never got reconciled.

## Sibling search (D3)

Searched via `code-review-graph semantic_search_nodes` for "env read in Cell scope" and grep for `os.environ.get.*OPENAI` across `src/vessal/`: only `src/vessal/skills/chat/skill.py` and `src/vessal/skills/memory/skill.py` read `VESSAL_DATA_DIR` (legitimate, Hull-set). No sibling instances of "engine reads LLM config from env" outside Core. Conclusion: no siblings.

## Hyrum scan (D4)

`get_impact_radius` on `Cell.__init__` (api_params arg removal) → 2 callers: `Hull._init_phase_2` (updated in this PR) and `tests/`. `Core.__init__` (api_params removal) → 1 caller: `Cell` (updated). `Core.step` (signature change) → 1 caller: `Cell.step` (updated). Conclusion: contained.

## Regression test (D5)

`test_core_does_not_touch_environ` (`tests/ark/shell/hull/cell/core/test_core.py`) sets hostile `OPENAI_*` env values and asserts Core uses LLMConfig values, not env values. This test would have failed against the original implementation, locking out the phantom-config regression class permanently.

## System defense (D7)

Test-level: `test_core_does_not_touch_environ` is sufficient because Core is the only component that talks to the LLM. No project-wide linter rule needed (a future "no os.environ.get inside cell/" lint is possible but not necessary for this fix).

## Post-mortem

`console/post-mortems/20260430-core-phantom-config.md` — to be drafted as a separate doc commit if the team wants the full incident write-up. (Not blocking this PR; the D2 chain above captures the essentials.)
EOF
)"
```

- [ ] **Step 2: Verify CI green**

After push, watch CI; if green, request review.

---

## Self-Review

**Spec coverage check:**
- ✅ Add LLMConfig dataclass — Task 1
- ✅ Update docs/architecture/core/00-mental-model.md (line 13–15 reconciliation) — Task 2 Step 1
- ✅ Update docs/architecture/core/02-api-and-retry.md (table + constructor example) — Task 2 Step 2
- ✅ Refactor Core to take llm_config per call — Task 4
- ✅ Refactor Core to remove env reads — Task 4 (and pinned by test in Task 3)
- ✅ Cache openai.OpenAI by (api_key, base_url, timeout) — Task 4 Step 2
- ✅ Refactor Cell to forward default_llm_config — Task 5
- ✅ Refactor Hull to build LLMConfig + log redacted — Task 7
- ✅ Compaction Cell handled — Task 7 Step 4
- ✅ Update CONTEXT.md boundary — Task 8
- ✅ Pre-existing tests adapted — Task 6
- ✅ Hull boot-log smoke test — Task 7 Step 1 + Task 9 Step 2
- ✅ Whitepaper scan — Task 10
- ✅ PR description with R5 + D2 + D3 + D4 + D5 + D7 — Task 11

**Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" — every task has full code, exact paths, exact commands.

**Type consistency:**
- `LLMConfig(api_key, base_url, model, api_params)` — same shape across Tasks 1, 3, 4, 5, 7.
- `Core.step(ping, llm_config, *, tracer=None, frame=0)` — same signature across Tasks 3, 4, 5, 6.
- `Cell(default_llm_config=...)` — keyword consistent across Tasks 5, 6, 7.

No drift detected.
