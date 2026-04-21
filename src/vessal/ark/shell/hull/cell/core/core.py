"""core.py — LLM call pipeline: Core is the reasoning half of the Agent loop, responsible for model invocation and retries."""
#   1. Constructs OpenAI-compatible messages from Ping (system_prompt + state)
#   2. Calls the LLM API (OpenAI-compatible interface), handles network retries
#   3. Extracts text from the response, calls parse_response() to return a Pong
#
# Model compatibility design principles:
#   - Core only fixes two parameters: model (from OPENAI_MODEL env var) and messages
#   - All other API parameters are passed through via api_params dict to create()
#   - Parameters required by different models/providers (temperature, max_tokens,
#     extra_body, etc.) are injected by the caller (Cell/Hull) via config; Core
#     does not hardcode them
#
# Network robustness:
#   - Retryable errors (network timeout, connection drop): automatic retry with exponential backoff
#   - Non-retryable errors (auth failure, bad request): raise immediately, no wasted retries
#
# Public interface:
#   Core(timeout, max_retries, api_params)    constructor
#   run(ping, tracer, frame) -> Pong          call LLM, return parsed Pong

import logging
import os
import time

import openai
from openai import (
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
)

from vessal.ark.shell.hull.cell._tracer_protocol import TracerLike
from vessal.ark.shell.hull.cell.protocol import Ping, Pong
from vessal.ark.shell.hull.cell.core.retry import is_retryable_error, calculate_backoff_seconds
from vessal.ark.shell.hull.cell.core.parser import ParseError, parse_response

# Module-specific logger for Core
logger = logging.getLogger("vessal.cell.core")


class Core:
    """LLM call pipeline. Ping → LLM API → parse → Pong.

    Sends the perceptual state rendered by Ping to the LLM, and parses
    the response into a Pong (control signal).

    Model compatibility: Core only fixes model and messages; all other API
    parameters are determined entirely by api_params. When switching models
    or providers, only api_params and environment variables need to be updated;
    Core code itself requires no modification.

    Stateless: each run() is an independent API call; no conversation history
    is maintained and no responses are cached.
    """

    # Default values used when api_params is not specified.
    # Valid for most OpenAI-compatible models; if max_completion_tokens,
    # extra_body, etc. are needed, override the entire dict via the
    # api_params constructor argument.
    _DEFAULT_API_PARAMS: dict[str, object] = {
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        api_params: dict[str, object] | None = None,
    ) -> None:
        """Initialize Core.

        Args:
            timeout:    Request timeout in seconds, default 60. 0 means no timeout (not recommended).
            max_retries: Maximum retry count for network errors, default 3.
            api_params: Parameters passed through to chat.completions.create().
                        Core only manages model and messages; everything else is
                        determined by the caller via this dict.
                        Default: {"temperature": 0.7, "max_tokens": 4096}.
                        Example: {"temperature": 0.5, "max_completion_tokens": 2048,
                                  "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        """
        self._client = openai.OpenAI(timeout=timeout)
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._timeout = timeout
        self._max_retries = max_retries
        self._api_params = dict(api_params) if api_params else dict(self._DEFAULT_API_PARAMS)

    def run(
        self,
        ping: Ping,
        tracer: TracerLike | None = None,
        frame: int = 0,
    ) -> tuple[Pong, int | None, int | None]:
        """Call the LLM, parse the response, and return a Pong.

        Constructs system + user messages, calls parse_response() internally,
        and returns a Pong (containing think and action).

        Args:
            ping:   Perceptual input rendered by Kernel (contains system_prompt/state).
            tracer: Optional TracerLike.
            frame:  Frame number, used for trace recording.

        Returns:
            (Pong, prompt_tokens, completion_tokens) tuple.

        Raises:
            APITimeoutError: Timeout with retries exhausted
            APIConnectionError: Connection error with retries exhausted
            AuthenticationError: Invalid API key (raised immediately, no retry)
            PermissionDeniedError: Insufficient permissions (raised immediately)
            BadRequestError: Malformed request (raised immediately)
        """
        state_parts = [p for p in [ping.state.frame_stream, ping.state.signals] if p.strip()]
        state = "\n\n".join(state_parts)
        messages = [
            {"role": "system", "content": ping.system_prompt},
            {"role": "user", "content": state},
        ]

        start_time = time.time()
        last_exception = None

        if tracer:
            tracer.start(frame, "core.api_call")

        # +1 because range includes the initial attempt
        for attempt in range(self._max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Core retry attempt {attempt}/{self._max_retries}")

                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    **self._api_params,
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

                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else None
                completion_tokens = usage.completion_tokens if usage else None

                if tracer:
                    details = f"attempts={attempt + 1}"
                    if usage:
                        details += f",tokens_in={prompt_tokens},tokens_out={completion_tokens}"
                    tracer.end(frame, "core.api_call", details)

                pong = parse_response(raw_text)
                return pong, prompt_tokens, completion_tokens

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
