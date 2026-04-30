"""Tests for core/telemetry.py — per-Cell cache_metrics.jsonl appender."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vessal.cell.core.telemetry import append_usage


def test_append_usage_creates_file_when_missing(tmp_path: Path):
    p = tmp_path / "cache_metrics.jsonl"
    assert not p.exists()
    append_usage(p, {"frame": 1, "prompt_tokens": 100})
    assert p.exists()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"frame": 1, "prompt_tokens": 100}


def test_append_usage_appends_to_existing_file(tmp_path: Path):
    p = tmp_path / "cache_metrics.jsonl"
    append_usage(p, {"frame": 1})
    append_usage(p, {"frame": 2})
    append_usage(p, {"frame": 3})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["frame"] for l in lines] == [1, 2, 3]


def test_append_usage_one_record_per_line(tmp_path: Path):
    p = tmp_path / "cache_metrics.jsonl"
    record = {"frame": 7, "prompt_tokens": 500, "completion_tokens": 200,
              "cached_tokens": 300, "elapsed_seconds": 1.5, "attempts": 1,
              "ts": "2026-04-29T13:45:21+00:00"}
    append_usage(p, record)
    contents = p.read_text(encoding="utf-8")
    assert contents.count("\n") == 1
    assert contents.endswith("\n")


def test_append_usage_unicode_safe(tmp_path: Path):
    p = tmp_path / "cache_metrics.jsonl"
    append_usage(p, {"note": "压缩 hit 率 80%"})
    line = p.read_text(encoding="utf-8").splitlines()[0]
    assert "压缩" in line
    assert json.loads(line)["note"] == "压缩 hit 率 80%"


def test_append_usage_parent_dir_must_exist(tmp_path: Path):
    p = tmp_path / "missing_dir" / "cache_metrics.jsonl"
    with pytest.raises(FileNotFoundError):
        append_usage(p, {"frame": 1})
