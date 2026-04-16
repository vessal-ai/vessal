"""retry.py — LLM API call retry helper functions (pure functions, no side effects)."""
from __future__ import annotations

from openai import (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    RateLimitError,
)

_RETRYABLE_ERRORS = (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    RateLimitError,
)


def is_retryable_error(exc: Exception) -> bool:
    """Determine whether an exception is retryable.

    Retryable errors: APITimeoutError, APIConnectionError, InternalServerError, RateLimitError.
    All other errors (AuthenticationError, PermissionDeniedError, BadRequestError, etc.)
    are non-retryable.

    Args:
        exc: The exception instance to check.

    Returns:
        True if retryable, False if non-retryable (should be raised immediately).
    """
    return isinstance(exc, _RETRYABLE_ERRORS)


def calculate_backoff_seconds(attempt: int, exc: Exception) -> float:
    """Calculate the exponential backoff wait time in seconds.

    For RateLimitError, prefers the retry-after field returned by the server;
    for all other retryable errors, uses 2^attempt seconds of exponential backoff.

    Args:
        attempt: Current retry count, starting from 0 (0 means the wait before the first retry).
        exc: The exception that triggered the retry.

    Returns:
        Wait time in seconds (float).
    """
    if isinstance(exc, RateLimitError):
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            return float(retry_after)
    return 2 ** attempt
