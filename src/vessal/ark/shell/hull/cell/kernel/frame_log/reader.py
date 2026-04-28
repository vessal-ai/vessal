"""reader.py — Spec §4.10 SQLite-based frame_stream rendering.

Sibling of writer.py: same schema, opposite direction. Every kernel.ping() step ⑤
recomputes FrameStream from frame_log.sqlite. No long-lived in-process projection.
"""
from __future__ import annotations

import json
import sqlite3

from vessal.ark.shell.hull.cell.protocol import (
    Entry,
    FrameContent,
    FrameStream,
    SummaryContent,
)


def render_frame_stream(conn: sqlite3.Connection) -> FrameStream:
    """Spec §4.10: visibility SQL → fetch content rows → assemble dataclass.

    Layer DESC + n_start ASC ordering enforced by the visibility SQL itself.
    Non-transactional reads (no concurrent compaction writer at this phase); no Python-side O(N^2) coverage check.
    """
    with conn:
        visible = conn.execute(
            "SELECT layer, n_start, n_end FROM entries e "
            "WHERE NOT EXISTS ("
            "    SELECT 1 FROM entries upper "
            "    WHERE upper.layer > e.layer "
            "      AND upper.n_start <= e.n_start "
            "      AND upper.n_end >= e.n_end"
            ") "
            "ORDER BY layer DESC, n_start ASC"
        ).fetchall()

        layer0_n = [n for layer, n, _ in visible if layer == 0]
        layerk = [(layer, n) for layer, n, _ in visible if layer >= 1]

        fc_map = _fetch_frame_content(conn, layer0_n)
        sc_map = _fetch_summary_content(conn, layerk)
        sg_map = _fetch_signals(conn, layer0_n)
        err_map = _fetch_errors_for_visible(conn, visible)

    entries: list[Entry] = []
    for layer, n_start, n_end in visible:
        if layer == 0:
            entries.append(Entry(
                layer=0, n_start=n_start, n_end=n_end,
                content=_build_frame_content(fc_map[n_start], sg_map.get(n_start, {}), err_map),
            ))
        else:
            sc_row = sc_map[(layer, n_start)]
            entries.append(Entry(
                layer=layer, n_start=n_start, n_end=n_end,
                content=SummaryContent(
                    schema_version=sc_row["schema_version"],
                    body=sc_row["body"],
                ),
            ))
    return FrameStream(entries=entries)


def _fetch_frame_content(conn: sqlite3.Connection, ns: list[int]) -> dict[int, dict]:
    if not ns:
        return {}
    placeholders = ",".join("?" for _ in ns)
    rows = conn.execute(
        f"SELECT n, pong_think, pong_operation, pong_expect, "
        f"       obs_stdout, obs_stderr, obs_diff_json, obs_error_id, "
        f"       verdict_value, verdict_error_id "
        f"FROM frame_content WHERE n IN ({placeholders})",
        ns,
    ).fetchall()
    return {
        r[0]: {
            "n": r[0],
            "pong_think": r[1] or "",
            "pong_operation": r[2] or "",
            "pong_expect": r[3] or "",
            "obs_stdout": r[4] or "",
            "obs_stderr": r[5] or "",
            "obs_diff_json": r[6] or "{}",
            "obs_error_id": r[7],
            "verdict_value": r[8],
            "verdict_error_id": r[9],
        }
        for r in rows
    }


def _fetch_summary_content(
    conn: sqlite3.Connection,
    keys: list[tuple[int, int]],
) -> dict[tuple[int, int], dict]:
    if not keys:
        return {}
    layer_to_nstarts: dict[int, list[int]] = {}
    for layer, n_start in keys:
        layer_to_nstarts.setdefault(layer, []).append(n_start)

    out: dict[tuple[int, int], dict] = {}
    for layer, n_starts in layer_to_nstarts.items():
        placeholders = ",".join("?" for _ in n_starts)
        rows = conn.execute(
            f"SELECT n_start, schema_version, body FROM summary_content "
            f"WHERE layer=? AND n_start IN ({placeholders})",
            [layer] + n_starts,
        ).fetchall()
        for n_start, schema_version, body in rows:
            out[(layer, n_start)] = {"schema_version": schema_version, "body": body}
    return out


def _fetch_signals(
    conn: sqlite3.Connection,
    ns: list[int],
) -> dict[int, dict[tuple[str, str, str], dict]]:
    if not ns:
        return {}
    placeholders = ",".join("?" for _ in ns)
    rows = conn.execute(
        f"SELECT n_start, class_name, var_name, scope, payload_json, error_id "
        f"FROM signals WHERE n_start IN ({placeholders})",
        ns,
    ).fetchall()
    out: dict[int, dict[tuple[str, str, str], dict]] = {}
    for n, cls, var, scope, payload_json, err_id in rows:
        bucket = out.setdefault(n, {})
        if err_id is not None:
            bucket[(cls, var, scope)] = {"_error_id": err_id}
        else:
            bucket[(cls, var, scope)] = json.loads(payload_json) if payload_json else {}
    return out


def _fetch_errors_for_visible(
    conn: sqlite3.Connection,
    visible: list[tuple[int, int, int]],
) -> dict[int, str]:
    if not visible:
        return {}
    rows = conn.execute("SELECT id, format_text FROM errors").fetchall()
    return {r[0]: r[1] for r in rows}


def _build_frame_content(
    fc_row: dict,
    signals: dict[tuple[str, str, str], dict],
    err_map: dict[int, str],
) -> FrameContent:
    obs_error_text = err_map.get(fc_row["obs_error_id"]) if fc_row["obs_error_id"] is not None else None
    verdict_error_text = err_map.get(fc_row["verdict_error_id"]) if fc_row["verdict_error_id"] is not None else None

    observation = {
        "stdout": fc_row["obs_stdout"],
        "stderr": fc_row["obs_stderr"],
        "diff": json.loads(fc_row["obs_diff_json"]) if fc_row["obs_diff_json"] else {},
        "error": obs_error_text,
    }
    verdict: dict | None
    if fc_row["verdict_value"] is None and verdict_error_text is None:
        verdict = None
    else:
        verdict = {
            "value": fc_row["verdict_value"],
            "error": verdict_error_text,
        }

    enriched_signals: dict[tuple[str, str, str], dict] = {}
    for key, payload in signals.items():
        if "_error_id" in payload:
            enriched_signals[key] = {"error": err_map.get(payload["_error_id"], "")}
        else:
            enriched_signals[key] = payload

    return FrameContent(
        think=fc_row["pong_think"],
        operation=fc_row["pong_operation"],
        expect=fc_row["pong_expect"],
        observation=observation,
        verdict=verdict,
        signals=enriched_signals,
    )
