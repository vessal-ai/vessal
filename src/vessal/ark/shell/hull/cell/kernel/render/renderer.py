"""renderer.py — Renderer main entry point.

render(ns, config) -> Ping

Output structure (Ping three fields):
    system_prompt: ns["_system_prompt"] (stripped)
    frame_stream:  recent frame history text (══════ frame stream ══════ prefix + frame blocks, trimmed to token budget)
    signals:       _signal_outputs concatenated text

Side effects: writes ns["_context_pct"], ns["_budget_total"], ns["_dropped_frame_count"].
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from vessal.ark.shell.hull.cell.protocol import Ping, State
from vessal.ark.shell.hull.cell.kernel.render._frame_render import render_frame_stream
from vessal.ark.shell.hull.cell.kernel.render._signal_render import render_signals
from vessal.ark.shell.hull.cell.kernel.render._prompt_render import render_skill_protocols
from vessal.ark.util.token_util import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderConfig:
    """Renderer configuration.

    Attributes:
        system_prompt_key:    Key name in ns for the system prompt; default "_system_prompt"
        frame_budget_ratio:   Ratio of frame stream budget to remaining token budget; default 0.7
        assemble_skill_context: Whether to concatenate SOUL and skill protocol sections; default True.
                              Should be set to False for compression frames to avoid injecting
                              irrelevant content into the compression prompt.
    """
    system_prompt_key: str = "_system_prompt"
    frame_budget_ratio: float = 0.7
    assemble_skill_context: bool = True


DEFAULT_CONFIG = RenderConfig()


def render(ns: dict, config: RenderConfig | None = None) -> Ping:
    """Render namespace as Ping (complete perceptual input from system to reasoner).

    Side effects: writes ns["_context_pct"], ns["_budget_total"], ns["_dropped_frame_count"].

    Args:
        ns:     Kernel namespace dict.
        config: Render config; uses DEFAULT_CONFIG when None.

    Returns:
        Ping(system_prompt, state)
    """
    if config is None:
        config = DEFAULT_CONFIG

    # ── three-segment system prompt assembly (physically isolated) ──
    kernel_protocol = ns.get(config.system_prompt_key, "")
    if not isinstance(kernel_protocol, str):
        kernel_protocol = str(kernel_protocol)
    kernel_protocol = kernel_protocol.strip()

    if config.assemble_skill_context:
        # SOUL section
        soul = ns.get("_soul", "")
        if isinstance(soul, str) and soul.strip():
            kernel_protocol += "\n\n══════ SOUL ══════\n" + soul.strip()

        # skill protocol section
        skill_protocols_text = render_skill_protocols(ns)
        if skill_protocols_text:
            meta = "The following are cognitive protocols for loaded skills. When in conflict with SOUL, SOUL takes precedence."
            kernel_protocol += (
                "\n\n══════ skill protocol ══════\n" + meta + "\n\n" + skill_protocols_text
            )

    system_prompt = kernel_protocol

    context_budget = ns.get("_context_budget", 128000)
    max_tokens = ns.get("_token_budget", 4096)
    if context_budget <= max_tokens:
        raise ValueError(
            f"context_budget ({context_budget}) <= max_tokens ({max_tokens})"
        )

    budget_total = context_budget - max_tokens
    ns["_budget_total"] = budget_total

    system_prompt_tokens = estimate_tokens(system_prompt)
    remaining = max(budget_total - system_prompt_tokens, 0)
    frame_budget = int(remaining * config.frame_budget_ratio)

    frame_stream_text, dropped = render_frame_stream(ns, frame_budget)
    ns["_dropped_frame_count"] = dropped

    # concatenate frame stream header
    if frame_stream_text:
        frame_stream = "══════ frame stream ══════\n" + frame_stream_text
    else:
        frame_stream = ""

    signals = render_signals(ns)

    # write context utilization
    total_text = system_prompt + frame_stream + signals
    total_tokens = estimate_tokens(total_text)
    ns["_context_pct"] = round(total_tokens / budget_total * 100) if budget_total > 0 else 0

    return Ping(
        system_prompt=system_prompt,
        state=State(frame_stream=frame_stream, signals=signals),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Backward compatibility: private helper functions for tests
# ──────────────────────────────────────────────────────────────────────────────


def _render_system_prompt(ns: dict, key: str) -> str:
    """Read system prompt from ns, return stripped; returns "" for empty/whitespace-only."""
    val = ns.get(key, "")
    if not isinstance(val, str):
        val = str(val)
    return val.strip()


def _render_frame_stream(ns: dict, budget_tokens: int) -> str:
    """Render frame stream section trimmed to token budget. Includes header line.

    Delegates to render_frame_stream() and concatenates the "══════ frame stream ══════" header.
    Side effect: writes ns["_dropped_frame_count"].
    """
    text, dropped = render_frame_stream(ns, budget_tokens)
    ns["_dropped_frame_count"] = dropped
    if not text:
        return ""
    return "══════ frame stream ══════\n" + text


def _render_auxiliary(ns: dict) -> str:
    """Render auxiliary signal section. Delegates to render_signals()."""
    return render_signals(ns)
