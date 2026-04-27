from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream


def _fake_frame_dict(n: int) -> dict:
    return {
        "schema_version": 7,
        "number": n,
        "ping": {"system_prompt": "s", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": "", "verdict": {"total": 0, "passed": 0, "failures": []}},
    }


def _fake_record(layer: int, frame_idx: int) -> dict:
    from vessal.ark.shell.hull.cell.protocol import CompactionRecord
    return CompactionRecord(
        range=(frame_idx, frame_idx + 1),
        intent="t",
        operations=("op",),
        outcomes="o",
        artifacts=(),
        notable="",
        layer=layer,
        compacted_at=frame_idx + 1,
    ).to_dict()


# ── Task 4: skeleton ──────────────────────────────────────────────────────────

def test_frame_stream_new_empty():
    fs = FrameStream(k=4, n=3)
    assert fs.hot_frame_count() == 0
    assert fs.cold_record_count() == 0
    assert fs.in_flight is False
    assert fs.compression_zone is None


def test_commit_frame_appends_to_b0():
    fs = FrameStream(k=4, n=3)
    fs.commit_frame(_fake_frame_dict(1))
    fs.commit_frame(_fake_frame_dict(2))
    assert fs.hot_frame_count() == 2


def test_commit_frame_rejects_wrong_schema():
    fs = FrameStream(k=4, n=3)
    bad = _fake_frame_dict(1)
    bad["schema_version"] = 6
    with pytest.raises(ValueError):
        fs.commit_frame(bad)


# ── Task 5: try_shift gating ──────────────────────────────────────────────────

def test_try_shift_returns_none_when_b0_under_k():
    fs = FrameStream(k=4, n=3)
    fs.commit_frame(_fake_frame_dict(1))
    assert fs.try_shift() is None


def test_try_shift_returns_none_when_in_flight():
    fs = FrameStream(k=4, n=3)
    for i in range(4):
        fs.commit_frame(_fake_frame_dict(i))
    fs._in_flight = True
    assert fs.try_shift() is None


def test_try_shift_returns_none_when_compression_zone_occupied():
    fs = FrameStream(k=4, n=3)
    for i in range(4):
        fs.commit_frame(_fake_frame_dict(i))
    fs._compression_zone = [{"stub": True}]
    assert fs.try_shift() is None


def test_try_shift_pops_pending_before_checking_hot():
    fs = FrameStream(k=4, n=3)
    fs._pending.append(1)
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 1
    assert fs._in_flight is True


# ── Task 6: hot shift ─────────────────────────────────────────────────────────

def test_hot_shift_moves_b0_up_and_empties_it():
    fs = FrameStream(k=4, n=3)
    for i in range(4):
        fs.commit_frame(_fake_frame_dict(i))
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 0
    # First shift: compression zone gets the (empty) old B_4
    assert task["payload"] == []
    assert len(fs._hot[0]) == 0
    assert len(fs._hot[1]) == 4
    assert fs._compression_zone == []


def test_hot_shift_cascades_buckets_after_five_shifts():
    fs = FrameStream(k=2, n=3)
    for shift_i in range(5):
        for f in range(2):
            fs.commit_frame(_fake_frame_dict(shift_i * 2 + f))
        task = fs.try_shift()
        assert task is not None
        if shift_i == 4:
            assert len(task["payload"]) == 2
        fs._in_flight = False
        fs._compression_zone = None


def test_hot_shift_strips_at_level_4():
    fs = FrameStream(k=2, n=3)
    for i in range(10):
        f = _fake_frame_dict(i)
        f["pong"]["think"] = "ABC"
        f["observation"]["stdout"] = "out"
        fs.commit_frame(f)
        if (i + 1) % 2 == 0:
            task = fs.try_shift()
            if task and task["payload"]:
                for frame in task["payload"]:
                    assert frame["pong"]["think"] == ""
                    assert frame["observation"]["stdout"] == ""
                return
            fs._in_flight = False
            fs._compression_zone = None
    raise AssertionError("no bucket reached compression zone in 5 shifts")


# ── Task 7: apply_results + abort ─────────────────────────────────────────────

def test_apply_results_appends_to_l0():
    fs = FrameStream(k=4, n=3)
    fs._in_flight = True
    fs._compression_zone = []
    fs.apply_results([(_fake_record(0, 10), 0)])
    assert fs.cold_record_count() == 1
    assert len(fs._cold[0]) == 1
    assert fs._compression_zone is None
    assert fs._in_flight is False


def test_apply_results_creates_higher_layers_lazily():
    fs = FrameStream(k=2, n=3)
    fs._in_flight = True
    fs._compression_zone = []
    fs.apply_results([(_fake_record(1, 10), 1)])
    assert len(fs._cold) == 2
    assert len(fs._cold[0]) == 0
    assert len(fs._cold[1]) == 1


def test_apply_results_triggers_cascade_when_l0_exceeds_k():
    fs = FrameStream(k=2, n=3)
    fs._cold = [[_fake_record(0, 0), _fake_record(0, 1)], [], []]
    fs._in_flight = True
    fs._compression_zone = []
    fs.apply_results([(_fake_record(0, 2), 0)])
    assert len(fs._cold[0]) == 3
    assert list(fs._pending) == [1]


def test_abort_compaction_resets_state_without_appending():
    fs = FrameStream(k=4, n=3)
    fs._in_flight = True
    fs._compression_zone = [{"stub": True}]
    fs.abort_compaction()
    assert fs._in_flight is False
    assert fs._compression_zone is None
    assert fs.cold_record_count() == 0


def test_cascade_residual_is_one_record_under_single_writer():
    fs = FrameStream(k=2, n=3)
    fs._cold = [[_fake_record(0, 0), _fake_record(0, 1)], [], []]
    fs._in_flight = True
    fs._compression_zone = []
    fs.apply_results([(_fake_record(0, 2), 0)])
    assert list(fs._pending) == [1]
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 1
    assert len(task["payload"]) == 2
    assert len(fs._cold[0]) == 1
    assert fs._cold[0][0]["range"] == [2, 3]


def test_extract_payload_for_layer_drains_oldest_k():
    fs = FrameStream(k=2, n=3)
    fs._cold = [
        [_fake_record(0, 0), _fake_record(0, 1), _fake_record(0, 2)],
        [],
        [],
    ]
    fs._pending.append(1)
    task = fs.try_shift()
    assert task is not None
    assert task["layer"] == 1
    assert len(task["payload"]) == 2
    assert task["payload"][0]["range"] == [0, 1]
    assert len(fs._cold[0]) == 1
    assert fs._cold[0][0]["range"] == [2, 3]


# ── Task 8: snapshot ──────────────────────────────────────────────────────────

def test_frame_stream_snapshot_roundtrip():
    fs = FrameStream(k=2, n=3)
    for i in range(3):
        fs.commit_frame(_fake_frame_dict(i))
    fs.try_shift()
    fs.apply_results([(_fake_record(0, 3), 0)])
    fs._pending.append(1)

    d = fs.to_dict()
    restored = FrameStream.from_dict(d)
    assert restored._k == fs._k
    assert restored._n == fs._n
    assert restored._hot == fs._hot
    assert restored._compression_zone == fs._compression_zone
    assert restored._cold == fs._cold
    assert restored._in_flight == fs._in_flight
    assert list(restored._pending) == list(fs._pending)


def test_frame_stream_snapshot_has_schema_version():
    fs = FrameStream(k=4, n=3)
    d = fs.to_dict()
    assert d["schema_version"] == 7


def test_frame_stream_from_dict_rejects_wrong_schema():
    d = FrameStream(k=4, n=3).to_dict()
    d["schema_version"] = 6
    with pytest.raises(ValueError):
        FrameStream.from_dict(d)


# ── Task 9: projection ────────────────────────────────────────────────────────

def test_project_render_returns_cold_then_hot_ordered():
    fs = FrameStream(k=2, n=3)
    fs._cold = [[_fake_record(0, 5)], [], []]
    fs.commit_frame(_fake_frame_dict(10))
    fs.commit_frame(_fake_frame_dict(11))
    view = fs.project_render()
    assert "cold" in view
    assert "hot" in view
    assert view["cold"][-1] == [_fake_record(0, 5)]
    assert len(view["hot"]) == 5
    assert len(view["hot"][-1]) == 2
    assert view["hot"][-1][0]["number"] == 10


def test_project_compactions_is_json_safe():
    import json
    fs = FrameStream(k=2, n=3)
    fs._cold = [[_fake_record(0, 0), _fake_record(0, 1)], [_fake_record(1, 2)]]
    proj = fs.project_compactions()
    json.dumps(proj)
    assert proj["layers"][0]["records"][0]["layer"] == 0
    assert proj["layers"][1]["records"][0]["layer"] == 1
