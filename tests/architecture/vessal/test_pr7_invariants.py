"""Architecture invariants locked in by PR 7 — Cell spec realignment."""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import get_type_hints


def test_observation_diff_annotated_as_list():
    """Observation.diff must be annotated as list[dict[str, str]], not str."""
    from vessal.ark.shell.hull.cell.protocol import Observation

    hints = get_type_hints(Observation)
    diff_hint = hints["diff"]
    assert diff_hint is not str, "Observation.diff must not be annotated as str"
    origin = getattr(diff_hint, "__origin__", None)
    assert origin is list, f"Observation.diff must be a list type; got origin={origin}"
    assert len(diff_hint.__args__) == 1
    inner = diff_hint.__args__[0]
    assert getattr(inner, "__origin__", None) is dict


def test_observation_has_stderr_field():
    """Observation must have a stderr field."""
    from vessal.ark.shell.hull.cell.protocol import Observation

    obs = Observation(stdout="", stderr="captured", diff=[], error=None)
    assert obs.stderr == "captured"


def test_frame_content_schema_has_no_verdict_error_id(tmp_path):
    """The frame_content table must not have a verdict_error_id column."""
    from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db

    conn = open_db(tmp_path / "test.db")
    cursor = conn.execute("PRAGMA table_info(frame_content)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "verdict_error_id" not in columns


def test_frame_write_spec_has_verdict_errors_list_field():
    """FrameWriteSpec must have verdict_errors as a list field (not verdict_error)."""
    from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec

    field_names = [f.name for f in dataclasses.fields(FrameWriteSpec)]
    assert "verdict_errors" in field_names
    assert "verdict_error" not in field_names

    spec_field = FrameWriteSpec.__dataclass_fields__["verdict_errors"]
    assert spec_field.default_factory is list


def test_dead_code_is_actually_deleted():
    """flatten_frame_dict must not exist in protocol module."""
    import vessal.ark.shell.hull.cell.protocol as proto

    assert not hasattr(proto, "flatten_frame_dict")


def test_frame_schema_version_is_8():
    """FRAME_SCHEMA_VERSION must equal 8."""
    from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION

    assert FRAME_SCHEMA_VERSION == 8


def test_executor_result_has_stderr_field():
    """ExecResult from executor must have a stderr field that captures stderr output."""
    from vessal.ark.shell.hull.cell.kernel.executor import execute

    result = execute("import sys; sys.stderr.write('err')", {}, {}, 1)
    assert hasattr(result, "stderr")
    assert "err" in result.stderr


def test_kernel_does_not_hardcode_obs_stderr_empty():
    """Kernel must pass exec_result.stderr to Observation, not hardcode empty string."""
    REPO_ROOT = Path(__file__).resolve().parents[3]
    src = (REPO_ROOT / "src/vessal/ark/shell/hull/cell/kernel/kernel.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr
        else:
            continue
        if func_name != "Observation":
            continue
        for kw in node.keywords:
            if kw.arg == "stderr":
                assert not (
                    isinstance(kw.value, ast.Constant) and kw.value.value == ""
                ), "Kernel hardcodes stderr='' in Observation constructor"
