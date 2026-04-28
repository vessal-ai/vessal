"""composer.py — Flatten dataclass Ping to LLM message list.

Spec §1.4: Kernel does not stringify; Core composes the prompt before LLM call.
This module is the only place in Cell that produces LLM-prompt strings from
structured Ping dataclasses.

Public entry: compose(ping: Ping) -> list[dict]
Returns messages list in OpenAI chat-completion shape: [{"role": ..., "content": ...}].
"""
from __future__ import annotations

from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream, Ping, SummaryContent,
)


def compose(ping: Ping) -> list[dict]:
    """Build OpenAI-style messages list from a dataclass Ping."""
    messages: list[dict] = []
    sys_text = ping.system_prompt.strip()
    messages.append({"role": "system", "content": sys_text})

    user_text = _compose_user(ping.state.frame_stream, ping.state.signals)
    if user_text:
        messages.append({"role": "user", "content": user_text})

    return messages


def _compose_user(fs: FrameStream, signals: dict) -> str:
    parts: list[str] = []

    fs_text = _compose_frame_stream(fs)
    if fs_text:
        parts.append("══════ frame stream ══════\n" + fs_text)

    sig_text = _compose_signals(signals)
    if sig_text:
        parts.append("══════ signals ══════\n" + sig_text)

    return "\n\n".join(parts)


def _compose_frame_stream(fs: FrameStream) -> str:
    if not fs.entries:
        return ""
    blocks = [_compose_entry(e) for e in fs.entries]
    return "\n\n".join(b for b in blocks if b)


def _compose_entry(e: Entry) -> str:
    if e.layer == 0:
        assert isinstance(e.content, FrameContent)
        return _compose_layer0(e.n_start, e.content)
    assert isinstance(e.content, SummaryContent)
    return _compose_layerk(e.n_start, e.n_end, e.content)


def _compose_layer0(n: int, fc: FrameContent) -> str:
    lines: list[str] = [f"── frame {n} ──"]

    if fc.think:
        lines.append("[think]")
        lines.append(fc.think)

    if fc.operation:
        lines.append("[operation]")
        lines.append(fc.operation)

    if fc.expect:
        lines.append("[expect]")
        lines.append(fc.expect)

    if fc.observation.get("stdout"):
        lines.append("[stdout]")
        lines.append(fc.observation["stdout"].rstrip("\n"))

    if fc.observation.get("stderr"):
        lines.append("[stderr]")
        lines.append(fc.observation["stderr"].rstrip("\n"))

    diff = fc.observation.get("diff")
    if diff:
        lines.append("[diff]")
        lines.append(_format_diff(diff))

    err = fc.observation.get("error")
    if err:
        lines.append("[error]")
        lines.append(err)

    if fc.verdict is not None:
        lines.append("[verdict]")
        lines.append(_format_verdict(fc.verdict))

    return "\n".join(lines)


def _compose_layerk(n_start: int, n_end: int, sc: SummaryContent) -> str:
    return f"── summary [{n_start}..{n_end}] ──\n{sc.body}"


def _format_diff(diff: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in diff.items())


def _format_verdict(verdict: dict) -> str:
    if verdict.get("error"):
        return f"error: {verdict['error']}"
    return str(verdict.get("value", ""))


def _compose_signals(signals: dict) -> str:
    if not signals:
        return ""
    lines: list[str] = []
    for (cls, var, scope), payload in sorted(signals.items()):
        lines.append(f"── {cls} · {var} ({scope}) ──")
        if "error" in payload:
            lines.append(f"error: {payload['error']}")
        else:
            for k, v in sorted(payload.items()):
                lines.append(f"{k}: {v}")
    return "\n".join(lines)
