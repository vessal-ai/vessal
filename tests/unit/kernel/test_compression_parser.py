from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.compression_parser import (
    parse_compaction_json,
    CompactionParseError,
)


def test_parse_valid_json():
    raw = """
    {
      "range": [0, 15],
      "intent": "set up auth",
      "operations": ["hash", "store"],
      "outcomes": "token issued",
      "artifacts": ["auth.py"],
      "notable": ""
    }
    """
    rec = parse_compaction_json(raw, layer=0, compacted_at=16)
    assert rec.range == (0, 15)
    assert rec.intent == "set up auth"
    assert rec.operations == ("hash", "store")
    assert rec.artifacts == ("auth.py",)
    assert rec.layer == 0
    assert rec.compacted_at == 16


def test_parse_strips_code_fences():
    raw = '```json\n{"range": [0, 1], "intent": "x", "operations": [], "outcomes": "", "artifacts": [], "notable": ""}\n```'
    rec = parse_compaction_json(raw, layer=0, compacted_at=2)
    assert rec.intent == "x"


def test_parse_rejects_missing_field():
    raw = '{"range": [0, 1]}'
    with pytest.raises(CompactionParseError):
        parse_compaction_json(raw, layer=0, compacted_at=2)


def test_parse_caps_operations_and_artifacts_to_four():
    raw = """{"range": [0, 1], "intent": "x",
              "operations": ["a","b","c","d","e","f"],
              "outcomes": "",
              "artifacts": ["1","2","3","4","5"],
              "notable": ""}"""
    rec = parse_compaction_json(raw, layer=0, compacted_at=2)
    assert len(rec.operations) == 4
    assert len(rec.artifacts) == 4


def test_parse_rejects_non_list_operations():
    raw = '{"range": [0,1], "intent": "x", "operations": "nope", "outcomes": "", "artifacts": [], "notable": ""}'
    with pytest.raises(CompactionParseError):
        parse_compaction_json(raw, layer=0, compacted_at=2)


def test_parse_malformed_json():
    with pytest.raises(CompactionParseError):
        parse_compaction_json("not json", layer=0, compacted_at=2)
