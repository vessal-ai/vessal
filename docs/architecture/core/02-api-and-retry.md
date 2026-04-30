# 02 · API 调用与重试

本章把 `pong()` 的第二、第三步拆到字节级。四件事：`llm_config` 的注入规则与 model / messages / base_url / api_key 的责任归属（§2.1）；api_call 子模块的薄封装（§2.2）；retry 子模块的四类可重试错误与指数退避公式（§2.3）；为什么 retry 必须是纯函数、不能和 api_call 合并（§2.4）。

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
        key = (cfg.api_key, cfg.base_url, self._timeout)
        client = self._client_cache.get(key)
        if client is None:
            client = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=self._timeout)
            self._client_cache[key] = client
        return client
```

llm_config.api_params 整体 `**unpack` 进 `create()` —— Core 不筛、不补默认值。Cell 想传什么就传什么，`model` / `messages` 这两个被 Core 占用的 key 若在 api_params 里重复会被 Python 的 `**kwargs` 规则直接报错，这是期望行为（防止上游误覆盖 Core 的固定职责）。

## 2.2 api_call 的薄封装

api_call 子模块就是 `_call_api` 那一段，薄到只剩一个 `client.chat.completions.create()` 调用。不做的事：

- 不做参数预处理（llm_config 原样透传）。
- 不做响应解析（parse 是 §03 的事）。
- 不做缓存（Core 无状态）。
- 不做日志（tracer 注入由 Cell 做，Core 里只 return）。
- 不做流式（Vessal 一帧一个完整 Pong，流式无收益）。

薄到这个程度的好处：OpenAI SDK 本身的行为就是 api_call 的行为。SDK 升级带来的参数变化、错误类型演化、新模型支持，Core 不用追 —— 透传接口天生兼容。

## 2.3 retry：四类可重试错误与指数退避

retry 是独立的纯函数模块 `retry.py`：

```python
# retry.py
def is_retryable_error(exc: Exception) -> bool: ...
def calculate_backoff_seconds(attempt: int, exc: Exception) -> float: ...
```

Core 主流程调 retry 的方式：

```python
def _call_with_retry(self, messages, llm_config):
    for attempt in range(MAX_RETRIES):
        try:
            return self._call_api(messages, llm_config)
        except Exception as e:
            if not is_retryable_error(e):
                raise
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(calculate_backoff_seconds(attempt, e))
```

### 四类可重试

| 异常类 | 语义 | 为什么可重试 |
|---|---|---|
| `APITimeoutError` | 请求超时 | 瞬时网络或服务器慢，重试大概率成功 |
| `APIConnectionError` | 连接失败（DNS / socket） | 瞬时网络抖动 |
| `InternalServerError` | 5xx | 服务端瞬时故障，SLA 外 |
| `RateLimitError` | 429 | 限流是时间窗问题，等一等就过了 |

**其它一律 fatal**：

- `AuthenticationError` —— key 错 / 过期，重试无意义，让用户修 env。
- `BadRequestError` / `UnprocessableEntityError` —— 请求本身不合法（prompt 太长、参数非法）。重试只是重复同一个错。
- `NotFoundError` —— model 不存在。重试无意义。
- `PermissionDeniedError` —— 权限问题。重试无意义。
- 非 openai 异常（KeyError / TypeError / ...） —— 代码 bug，不能掩盖。

**ParseError 也是 fatal** —— 它不是网络层错误，是 LLM 返回内容不符合 `<action>` 契约。重试同一个 prompt 大概率拿到同一个错误内容。见 §03。

### 指数退避公式

```python
BASE_DELAY = 1.0       # seconds
MAX_DELAY  = 30.0
MAX_RETRIES = 3

def calculate_backoff_seconds(attempt: int, exc: Exception) -> float:
    # RateLimitError 优先用服务端指定的 retry-after
    if isinstance(exc, RateLimitError):
        retry_after = _extract_retry_after(exc)
        if retry_after is not None:
            return min(retry_after, MAX_DELAY)
    # 其它走指数退避
    return min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
```

### RateLimitError 的 retry-after 优先策略

限流响应里服务端常带 `Retry-After` header（秒数）或 `x-ratelimit-reset-requests`（时间戳）。服务端知道"还需要等多久窗口重置"，比客户端瞎猜指数退避准得多。retry 的策略：

1. 解 `exc.response.headers` 找 `retry-after`（秒）。
2. 若有且合理（< MAX_DELAY）→ 用。
3. 若无或超限 → 退回指数退避公式。

`MAX_DELAY = 30s` 是安全上限：服务端偶尔会返回巨大 retry-after（比如几分钟），Vessal 的帧循环不该为一次限流阻塞这么久，宁可走 fatal 路径让 Cell 的 protocol_error 传上去，由 Hull 决定更长的退避策略。

### 为什么是 3 次重试

四类瞬时错误的经验分布：

- 第 1 次重试成功率 ≈ 70%（瞬时网络抖动）。
- 第 2 次 ≈ 85%（累计）。
- 第 3 次 ≈ 92%。
- 第 4 次以后边际收益 < 5%，但累计延迟已经到 `1+2+4+8 = 15s`。

3 次是延迟 vs 成功率的经验拐点。可以配置但不该改大 —— 真的 8% 都失败的请求，说明问题不在瞬时网络，该让 protocol_error 上浮。

## 2.4 为什么 retry 必须是纯函数

retry 做成独立纯函数模块（而不是 Core 类的方法或 api_call 的私有实现），有三个具体理由：

**理由 1：可独立测试**。`is_retryable_error` 和 `calculate_backoff_seconds` 的单元测试不需要 mock 网络、不需要 mock client、不需要 fixtures。传 exception 实例进、检查 bool / float 出，纯函数单测最廉价。

**理由 2：分类规则可审计**。retryable 四类是架构决策（白皮书隐含的"瞬时 vs 永久"二分），不是实现细节。作为纯函数暴露，外部（测试、日志、文档）都能直接引用同一张分类表，不会有"api_call 内部的私有 if 分支偷偷改了规则"的漂移。

**理由 3：不和 api_call 纠缠**。api_call 的职责是"调 openai SDK"，retry 的职责是"判断和延时"。混在一起会出现 `_call_api(messages, llm_config, max_retries=3)` 这种签名 —— 调用方被迫理解重试策略，或者反过来 retry 被迫理解请求参数。分开后 Core 主流程用一个 for 循环把它们组合，职责边界干净。

### retry 不知道的事

- 不知道调用的是哪个 Provider（只看异常类型）。
- 不知道 Cell / Hull 的更高层退避策略（只处理单次 pong 内的重试）。
- 不知道请求内容（messages 不传给 retry）。
- 不知道业务语义（fatal 上浮后交给 Cell 的 protocol_error）。

这些无知是设计。retry 只回答两个问题："这个异常该重试吗？"和"重试前睡多久？"多一个问题都是越界。

## 2.5 与现有实现的对比

现有 `core/core.py` 和 `core/retry.py` 已经把上述架构做了八成：retry 是纯函数模块，四类可重试已经枚举，指数退避已经实现。三处调整：

1. `Core.__init__` 移除 `self._client = OpenAI()` 和 `self._model = os.environ["OPENAI_MODEL"]`，改为 `_client_cache` 懒创建；`step()` 签名增加 `llm_config: LLMConfig` 参数。
2. `_call_api` 从 `model=self._model, **llm_config` 改为 `model=llm_config.model, **llm_config.api_params`，client 从 cache 按 `(api_key, base_url, timeout)` 取。
3. 返回值目标：`(Pong, usage: dict)`，Cell 写 JSONL。最终形式在 Cell 重构时和 `frame_log.observation` 表结构一起定。

不变的：retry 的四类分类、指数退避公式、api_call 薄封装原则。这些在现有实现里就对，新架构只沿用。
