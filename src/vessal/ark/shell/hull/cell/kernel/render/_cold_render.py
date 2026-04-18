"""_cold_render.py — Project CompactionRecord dicts into Ping-ready Markdown.

Ordering note: render_cold_zone assumes the caller has already ordered the outer
list as [L_n, L_{n-1}, ..., L_0] (older first) and each layer time-ascending.
This is the shape produced by FrameStream.project_render()["cold"].
"""
from __future__ import annotations


def project_compaction_record(record: dict) -> str:
    """Return a Markdown section for one CompactionRecord dict.

    Empty fields are omitted. Ordering of field subheadings is fixed:
    Intent / Operations / Outcomes / Artifacts / Notable.
    """
    layer = record["layer"]
    a, b = record["range"][0], record["range"][1]
    lines: list[str] = [f"## L_{layer} frames {a}\u2013{b}", ""]
    if record["intent"]:
        lines.append(f"**Intent**: {record['intent']}")
    ops = record.get("operations") or ()
    if ops:
        lines.append("**Operations**:")
        for op in ops:
            lines.append(f"- {op}")
    if record["outcomes"]:
        lines.append(f"**Outcomes**: {record['outcomes']}")
    arts = record.get("artifacts") or ()
    if arts:
        lines.append("**Artifacts**:")
        for a_ in arts:
            lines.append(f"- {a_}")
    if record["notable"]:
        lines.append(f"**Notable**: {record['notable']}")
    return "\n".join(lines)


def render_cold_zone(cold_view: list[list[dict]]) -> str:
    """Join all CompactionRecord projections with blank-line separators.

    Returns empty string if cold_view is empty or contains only empty layers.
    """
    blocks: list[str] = []
    for layer in cold_view:
        for record in layer:
            blocks.append(project_compaction_record(record))
    return "\n\n".join(blocks)
