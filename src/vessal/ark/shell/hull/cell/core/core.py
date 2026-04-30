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

import logging
import time

import openai

from vessal.ark.shell.hull.cell._tracer_protocol import TracerLike
from vessal.ark.shell.hull.cell.protocol import Ping, Pong, LLMConfig
from vessal.ark.shell.hull.cell.core.retry import is_retryable_error, calculate_backoff_seconds
from vessal.ark.shell.hull.cell.core.parser import ParseError, parse_response

# Module-specific logger for Core
logger = logging.getLogger("vessal.cell.core")


class Core:
    """LLM call pipeline. Ping → LLM API → parse → Pong.

    Stateless wrt LLM contract: each step() receives a full LLMConfig
    (api_key, base_url, model, api_params) per call. Core holds only
    network policy (timeout, max_retries) and a cache of openai.OpenAI
    instances keyed by (api_key, base_url, timeout).
    """

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._client_cache: dict[tuple[str, str, float], "openai.OpenAI"] = {}

    def _client_for(self, cfg: LLMConfig) -> "openai.OpenAI":
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

    @staticmethod
    def _build_messages(ping: "Ping") -> list[dict]:
        from vessal.ark.shell.hull.cell.core.composer import compose
        return compose(ping)

    def step(
        self,
        ping: Ping,
        llm_config: LLMConfig,
        *,
        tracer: TracerLike | None = None,
        frame: int = 0,
    ) -> tuple[Pong, dict]:
        """Call the LLM, parse the response, and return a Pong.

        Constructs system + user messages, calls parse_response() internally,
        and returns a Pong (containing think and action).

        Args:
            ping:   Perceptual input rendered by Kernel (contains system_prompt/state).
            tracer: Optional TracerLike.
            frame:  Frame number, used for trace recording.

        Returns:
            (Pong, usage) where usage is {} when response.usage is None,
            otherwise a dict with keys:
              prompt_tokens / completion_tokens / cached_tokens /
              elapsed_seconds / attempts.

        Raises:
            APITimeoutError: Timeout with retries exhausted
            APIConnectionError: Connection error with retries exhausted
            AuthenticationError: Invalid API key (raised immediately, no retry)
            PermissionDeniedError: Insufficient permissions (raised immediately)
            BadRequestError: Malformed request (raised immediately)
        """
        messages = self._build_messages(ping)

        start_time = time.time()
        last_exception = None

        if tracer:
            tracer.start(frame, "core.api_call")

        # +1 because range includes the initial attempt
        for attempt in range(self._max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Core retry attempt {attempt}/{self._max_retries}")

                client = self._client_for(llm_config)
                response = client.chat.completions.create(
                    model=llm_config.model,
                    messages=messages,
                    **llm_config.api_params,
                )

                # message.content is the model's final output text.
                # reasoning_content (DeepSeek R1 and other reasoning models) is a
                # separate field; we do not read it — the parser only processes content.
                raw_text = response.choices[0].message.content or ""
                elapsed = time.time() - start_time

                logger.info(
                    f"Core API call successful, "
                    f"elapsed={elapsed:.2f}s, "
                    f"attempts={attempt + 1}"
                )

                usage_obj = response.usage
                if usage_obj is None:
                    usage_dict: dict = {}
                else:
                    details_obj = getattr(usage_obj, "prompt_tokens_details", None)
                    cached = getattr(details_obj, "cached_tokens", 0) if details_obj else 0
                    usage_dict = {
                        "prompt_tokens": usage_obj.prompt_tokens,
                        "completion_tokens": usage_obj.completion_tokens,
                        "cached_tokens": cached or 0,
                        "elapsed_seconds": round(elapsed, 3),
                        "attempts": attempt + 1,
                    }

                if tracer:
                    details_str = f"attempts={attempt + 1}"
                    if usage_obj is not None:
                        details_str += (
                            f",tokens_in={usage_obj.prompt_tokens}"
                            f",tokens_out={usage_obj.completion_tokens}"
                        )
                    tracer.end(frame, "core.api_call", details_str)

                return parse_response(raw_text), usage_dict

            except Exception as exc:
                elapsed = time.time() - start_time
                last_exception = exc

                # Non-retryable error: raise immediately, do not waste retries
                if not is_retryable_error(exc):
                    logger.error(
                        f"Core non-retryable error after {elapsed:.2f}s: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    if tracer:
                        error_body = str(exc)[:500]
                        tracer.end(frame, "core.api_call",
                                   f"error={type(exc).__name__},msg={error_body}")
                    raise

                # Max retries reached: raise the last exception
                if attempt >= self._max_retries:
                    logger.error(
                        f"Core max retries ({self._max_retries}) exceeded, "
                        f"total elapsed={elapsed:.2f}s, "
                        f"last error: {type(exc).__name__}: {exc}"
                    )
                    if tracer:
                        tracer.end(frame, "core.api_call", f"error={type(exc).__name__},max_retries")
                    raise last_exception

                # Calculate wait time and log
                wait_seconds = calculate_backoff_seconds(attempt, exc)
                logger.warning(
                    f"Core retryable error (attempt {attempt + 1}/{self._max_retries + 1}): "
                    f"{type(exc).__name__}, waiting {wait_seconds:.1f}s"
                )
                time.sleep(wait_seconds)
