"""token_util.py — Token count estimation.

Single token estimation function. All modules that need to estimate tokens import from here.

Current implementation: UTF-8 byte count / 4.
Approximately accurate for English (1 token ≈ 4 bytes); underestimates by ~25-33% for Chinese
(Chinese characters are 3 bytes in UTF-8 ≈ 1 token, but this algorithm estimates 0.75 token).

This function is used only for pre-allocation before API calls. Precise context usage
is calculated from usage.prompt_tokens returned by the API (see Cell.step()).

The implementation can be replaced in the future; the interface signature will not change.
"""


def estimate_tokens(text: str) -> int:
    """Estimate the token count of text (for pre-allocation only, not exact measurement).

    Current algorithm: UTF-8 byte count / 4.
    Underestimates Chinese content by ~25-33%, but safe enough for frame-stream pre-allocation.
    Precise context usage is calculated by Cell.step() from API usage data.

    Args:
        text: Text to estimate.

    Returns:
        Estimated token count (integer, minimum 0).
    """
    return len(text.encode("utf-8")) // 4
