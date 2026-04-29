"""executor _compute_diff returns list[{op,name,type}] per spec §3.4."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.executor import execute


def test_diff_new_var_is_plus_op_with_type():
    G: dict = {}
    L: dict = {}
    result = execute("x = 1", G, L, frame_number=1)
    assert result.diff == [{"op": "+", "name": "x", "type": "int"}]


def test_diff_delete_var_is_minus_op():
    G: dict = {}
    L: dict = {"x": "old"}
    result = execute("del x", G, L, frame_number=1)
    assert result.diff == [{"op": "-", "name": "x", "type": "str"}]


def test_diff_rebind_is_minus_then_plus():
    G: dict = {}
    L: dict = {"x": 1}
    result = execute("x = 'hello'", G, L, frame_number=1)
    assert result.diff == [
        {"op": "-", "name": "x", "type": "int"},
        {"op": "+", "name": "x", "type": "str"},
    ]


def test_diff_empty_for_no_namespace_change():
    G: dict = {}
    L: dict = {}
    result = execute("print('hi')", G, L, frame_number=1)
    assert result.diff == []


def test_diff_skips_underscore_prefixed_names():
    G: dict = {}
    L: dict = {}
    result = execute("_internal = 1\nx = 2", G, L, frame_number=1)
    names = [d["name"] for d in result.diff]
    assert "_internal" not in names
    assert "x" in names
