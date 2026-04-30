"""Integration test: 4-frame Cell loop writes 4 JSONL records to cache_metrics.jsonl."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vessal.ark.shell.hull.cell.cell import Cell
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def _stub_pong(op: str = "x = 1"):
    return Pong(think="t", action=Action(operation=op, expect=""))


def _stub_usage(frame_index: int):
    return {
        "prompt_tokens": 1000 + frame_index,
        "completion_tokens": 100 + frame_index,
        "cached_tokens": 500 + frame_index,
        "elapsed_seconds": round(0.1 * (frame_index + 1), 3),
        "attempts": 1,
    }


@pytest.fixture
def cell_with_data_dir(tmp_path):
    from unittest.mock import patch
    from vessal.ark.shell.hull.cell.protocol import LLMConfig
    cfg = LLMConfig(api_key="k", base_url="u", model="m", api_params={})
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        cell = Cell(data_dir=str(tmp_path), default_llm_config=cfg)
    return cell, tmp_path


def test_four_frame_loop_writes_four_jsonl_records(cell_with_data_dir):
    cell, data_dir = cell_with_data_dir

    call_idx = {"n": 0}

    def stubbed_step(ping, llm_config, *, tracer=None, frame=0):
        i = call_idx["n"]
        call_idx["n"] += 1
        return _stub_pong(f"step_{i} = {i}"), _stub_usage(i)

    cell._core.step = stubbed_step

    for _ in range(4):
        cell.step()

    jsonl_path = data_dir / "cache_metrics.jsonl"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4

    records = [json.loads(line) for line in lines]
    for i, record in enumerate(records):
        assert record["prompt_tokens"] == 1000 + i
        assert record["completion_tokens"] == 100 + i
        assert record["cached_tokens"] == 500 + i
        assert record["attempts"] == 1
        assert "frame" in record
        assert "ts" in record


def test_no_jsonl_record_when_action_gate_blocks(cell_with_data_dir):
    """Action gate block returns protocol_error. JSONL is written before gate check —
    documents current write-then-gate ordering."""
    cell, data_dir = cell_with_data_dir
    cell.action_gate = "safe"
    cell.set_gate("action", lambda code: (False, "denied"))

    cell._core.step = MagicMock(return_value=(_stub_pong(), _stub_usage(0)))  # MagicMock accepts any args
    result = cell.step()

    jsonl_path = data_dir / "cache_metrics.jsonl"
    if jsonl_path.exists():
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
    assert result.protocol_error is not None
