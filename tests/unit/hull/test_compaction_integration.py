"""test_compaction_integration — End-to-end integration tests for hierarchical compaction.

Each test verifies at least one of the five invariants:
  1. Prefix stability
  2. Shift gating atomicity
  3. Static storage monotonic append
  4. Single in-flight
  5. Single writer
"""
from __future__ import annotations

import json
import pytest

from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.protocol import CompactionRecord, FRAME_SCHEMA_VERSION


def _frame(n: int) -> dict:
    return {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": n,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": f"t{n}", "action": {"operation": f"op{n}", "expect": ""}},
        "observation": {
            "stdout": "",
            "diff": "",
            "error": "",
            "verdict": {"total": 0, "passed": 0, "failures": []},
        },
    }


def _record_json(a: int, b: int) -> str:
    return json.dumps({
        "range": [a, b], "intent": f"mock {a}-{b}",
        "operations": ["mock_op"], "outcomes": "ok",
        "artifacts": [], "notable": "",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Task 26: hot-only scenario
# ─────────────────────────────────────────────────────────────────────────────

def test_hot_only_below_k_never_triggers_compaction():
    """Invariant 2 (shift gating): with fewer than k frames, no shift fires."""
    fs = FrameStream(k=4, n=3)
    for i in range(3):
        fs.commit_frame(_frame(i))
    assert fs.try_shift() is None
    assert fs.cold_record_count() == 0
    assert fs.in_flight is False
    assert fs.compression_zone is None


# ─────────────────────────────────────────────────────────────────────────────
# Task 27: trigger scenario
# ─────────────────────────────────────────────────────────────────────────────

def test_kth_frame_triggers_shift():
    """Invariant 2: exactly k frames → shift fires once, in_flight becomes True."""
    fs = FrameStream(k=4, n=3)
    for i in range(4):
        fs.commit_frame(_frame(i))
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 0
    assert fs.in_flight is True
    # First shift ejects B_4 which was empty (only 4 frames, none cascaded to B_4 yet)
    assert task["payload"] == []
    # Subsequent try_shift while in_flight returns None
    assert fs.try_shift() is None


# ─────────────────────────────────────────────────────────────────────────────
# Task 28: cold roundtrip
# ─────────────────────────────────────────────────────────────────────────────

def test_cold_roundtrip_applies_record_to_l0():
    """Invariant 3 + 5: successful round-trip writes one L_0 record; only main thread writes."""
    fs = FrameStream(k=2, n=3)
    # Fill 5 shifts so B_4 carries payload
    for i in range(10):
        fs.commit_frame(_frame(i))
        if (i + 1) % 2 == 0:
            task = fs.try_shift()
            assert task is not None
            if task["payload"]:
                rec = CompactionRecord(
                    range=(task["payload"][0]["number"], task["payload"][-1]["number"]),
                    intent="mock", operations=("x",), outcomes="",
                    artifacts=(), notable="", layer=0, compacted_at=i + 1,
                ).to_dict()
                fs.apply_results([(rec, 0)])
            else:
                fs.abort_compaction()
    assert fs.cold_record_count() >= 1
    assert fs._cold[0][0]["layer"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Task 29: backpressure
# ─────────────────────────────────────────────────────────────────────────────

def test_backpressure_blocks_second_shift_while_in_flight():
    """Invariant 4: only one compaction in flight; a second shift is refused."""
    fs = FrameStream(k=2, n=3)
    for i in range(2):
        fs.commit_frame(_frame(i))
    first = fs.try_shift()
    assert first is not None
    assert fs.in_flight is True
    # Fill B_0 again without applying results
    for i in range(2, 4):
        fs.commit_frame(_frame(i))
    assert fs.try_shift() is None  # still in_flight → refused
    # B_0 is allowed to exceed k transiently (backpressure)
    for i in range(4, 6):
        fs.commit_frame(_frame(i))
    assert len(fs._hot[0]) >= fs.k


# ─────────────────────────────────────────────────────────────────────────────
# Task 30: crash-restart
# ─────────────────────────────────────────────────────────────────────────────

def test_restart_resumes_compression_from_snapshot():
    """Invariant 4: a surviving in_flight flag blocks new shifts until worker re-submits."""
    fs = FrameStream(k=2, n=3)
    for i in range(2):
        fs.commit_frame(_frame(i))
    fs.try_shift()
    assert fs.in_flight is True
    assert fs.compression_zone is not None

    # Simulate crash + reload via snapshot roundtrip
    restored = FrameStream.from_dict(fs.to_dict())
    assert restored.in_flight is True
    assert restored.compression_zone is not None

    # Even committing more frames, no new shift fires until restored completes
    for i in range(2, 4):
        restored.commit_frame(_frame(i))
    assert restored.try_shift() is None

    # Simulate worker completion
    rec = CompactionRecord(
        range=(0, 1), intent="resumed", operations=(), outcomes="",
        artifacts=(), notable="", layer=0, compacted_at=4,
    ).to_dict()
    restored.apply_results([(rec, 0)])
    assert restored.in_flight is False

    # Now a new shift can fire
    assert restored.try_shift() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Task 31: layer cascade
# ─────────────────────────────────────────────────────────────────────────────

def test_cascade_l0_overflows_triggers_l0_to_l1():
    """Invariant 3: k+1 in L_0 triggers enqueue of L_0→L_1; residual is 1."""
    fs = FrameStream(k=2, n=3)

    def _land_record(intent: str, a: int, b: int, compacted_at: int):
        fs._in_flight = True
        fs._compression_zone = []
        fs.apply_results([
            (CompactionRecord(range=(a, b), intent=intent, operations=(), outcomes="",
                              artifacts=(), notable="", layer=0, compacted_at=compacted_at).to_dict(), 0),
        ])

    _land_record("a", 0, 1, 2)
    _land_record("b", 2, 3, 4)
    _land_record("c", 4, 5, 6)  # L_0 now has 3 > k=2 → cascade

    from collections import deque
    assert list(fs._pending) == [1]
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 1
    assert len(task["payload"]) == 2  # oldest k records of L_0
    # L_0 holds exactly 1 residual record (the newest)
    assert len(fs._cold[0]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Task 32: prefix stability (end-to-end)
# ─────────────────────────────────────────────────────────────────────────────

def test_prefix_byte_stability_across_hot_and_cold_shifts():
    """Invariant 1: appending hot frames with cold stable ⟹ r4 starts with r3 bytes."""
    from vessal.ark.shell.hull.cell.kernel.render._frame_render import render_frame_stream

    fs = FrameStream(k=2, n=3)
    for i in range(2):
        fs.commit_frame(_frame(i))
    r1, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=50_000)

    # Hot shift
    fs.try_shift()
    r2, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=50_000)

    # Apply a cold record (cold grows before hot)
    rec = CompactionRecord(
        range=(0, 1), intent="cold1", operations=(), outcomes="",
        artifacts=(), notable="", layer=0, compacted_at=2,
    ).to_dict()
    fs.apply_results([(rec, 0)])
    r3, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=50_000)

    # Commit more hot frames — cold unchanged, so r4 must start with r3
    for i in range(2, 4):
        fs.commit_frame(_frame(i))
    r4, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=50_000)

    assert r4.startswith(r3), (
        f"prefix diverged after hot append\n"
        f"r3_tail={r3[-80:]!r}\n"
        f"r4_mid={r4[len(r3)-20:len(r3)+40]!r}"
    )
