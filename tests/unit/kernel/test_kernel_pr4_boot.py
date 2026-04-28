"""test_kernel_pr4_boot.py — regression for PR 4 / spec §7 boot."""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.frame_log import open_db
from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry


# ────────────────────────────────────────────────────────────
# Boot script composition (pure unit)
# ────────────────────────────────────────────────────────────

def test_compose_boot_script_emits_imports_and_zero_arg_constructors():
    entries = [
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
        BootSkillEntry("chat", "vessal.skills.chat", "Chat", ""),
    ]
    script = compose_boot_script(entries)
    # Standard tools always present
    assert "import importlib, copy, json" in script
    # Skill imports
    assert "from vessal.skills.system import SystemSkill" in script
    assert "from vessal.skills.chat import Chat" in script
    # Zero-arg construction in declared order
    sys_idx = script.find("_system = SystemSkill()")
    chat_idx = script.find("chat = Chat()")
    assert 0 < sys_idx < chat_idx


def test_compose_boot_script_supports_kwargs_repr():
    entries = [
        BootSkillEntry("chat", "vessal.skills.chat", "Chat", "model=\"gpt-4\""),
    ]
    script = compose_boot_script(entries)
    assert "chat = Chat(model=\"gpt-4\")" in script


# ────────────────────────────────────────────────────────────
# 4-step linear flow (cold start)
# ────────────────────────────────────────────────────────────

def test_kernel_cold_start_writes_boot_frame_at_n_1(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
    ])
    Kernel(boot_script=script, db_path=str(db))

    conn = open_db(str(db))
    rows = conn.execute(
        "SELECT layer, n_start, n_end FROM entries ORDER BY n_start"
    ).fetchall()
    assert rows == [(0, 1, 1)]


def test_boot_frame_pong_operation_contains_real_script(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
    ])
    Kernel(boot_script=script, db_path=str(db))

    conn = open_db(str(db))
    op, expect, verdict = conn.execute(
        "SELECT pong_operation, pong_expect, verdict_value FROM frame_content WHERE n = 1"
    ).fetchone()
    assert "from vessal.skills.system import SystemSkill" in op
    assert expect == "True"
    assert verdict == "true"


def test_boot_frame_obs_stdout_captures_skill_init_prints(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
    ])
    Kernel(boot_script=script, db_path=str(db))

    conn = open_db(str(db))
    (stdout,) = conn.execute(
        "SELECT obs_stdout FROM frame_content WHERE n = 1"
    ).fetchone()
    # SystemSkill.__init__ prints a self-introduction (Task 7)
    assert "SystemSkill" in stdout or "_system" in stdout


def test_cold_start_obs_diff_json_is_empty_object(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([])
    Kernel(boot_script=script, db_path=str(db))

    conn = open_db(str(db))
    (diff,) = conn.execute(
        "SELECT obs_diff_json FROM frame_content WHERE n = 1"
    ).fetchone()
    assert diff == "{}"


# ────────────────────────────────────────────────────────────
# Skills land in G, not L
# ────────────────────────────────────────────────────────────

def test_preset_skills_live_in_G(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
        BootSkillEntry("chat", "vessal.skills.chat", "Chat", ""),
    ])
    k = Kernel(boot_script=script, db_path=str(db))

    assert "_system" in k.G
    assert "chat" in k.G
    assert "_system" not in k.L
    assert "chat" not in k.L


def test_systemskill_zero_arg_construction(tmp_path: Path):
    """Spec §7.4 example: `_system = SystemSkill()` — no arguments."""
    from vessal.skills.system import SystemSkill
    s = SystemSkill()
    assert isinstance(s.signal, dict)


def test_systemskill_bound_to_kernel_after_boot(tmp_path: Path):
    """Kernel walks G after exec; calls _bind_kernel(self) on any object that defines it."""
    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
    ])
    k = Kernel(boot_script=script, db_path=str(db))
    sysskill = k.G["_system"]
    # After bind: signal_update can read kernel.L
    sysskill.signal_update()
    assert "frame" in sysskill.signal


# ────────────────────────────────────────────────────────────
# Restart path (4-step ② before ③)
# ────────────────────────────────────────────────────────────

def test_restart_loads_l_after_boot_script(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    snap = tmp_path / "snap.pkl"
    script = compose_boot_script([
        BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", ""),
    ])

    # Cold start, write some L state, snapshot it
    k = Kernel(boot_script=script, db_path=str(db))
    k.L["my_var"] = 42
    k.snapshot(str(snap))

    # Restart: same boot script, same db, but with restore_path
    k2 = Kernel(
        boot_script=script,
        db_path=str(db),
        restore_path=str(snap),
    )
    assert k2.L["my_var"] == 42
    # boot frame at n = n_prev + 1 = 2
    conn = open_db(str(db))
    rows = conn.execute(
        "SELECT n_start FROM entries WHERE layer = 0 ORDER BY n_start"
    ).fetchall()
    assert rows == [(1,), (2,)]


def test_restart_obs_diff_json_lists_restored_keys(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    snap = tmp_path / "snap.pkl"
    script = compose_boot_script([])

    k = Kernel(boot_script=script, db_path=str(db))
    k.L["alpha"] = "value-a"
    k.L["beta"] = 7
    k.snapshot(str(snap))

    Kernel(boot_script=script, db_path=str(db), restore_path=str(snap))

    conn = open_db(str(db))
    (diff,) = conn.execute(
        "SELECT obs_diff_json FROM frame_content WHERE n = 2"
    ).fetchone()
    # diff is {key: repr(value), ...} per spec §7.6
    import json
    parsed = json.loads(diff)
    assert "alpha" in parsed and "'value-a'" in parsed["alpha"]
    assert "beta" in parsed and parsed["beta"] == "7"


# ────────────────────────────────────────────────────────────
# Vestigial removal
# ────────────────────────────────────────────────────────────

def test_kernel_init_no_longer_takes_snapshot_path():
    import inspect
    sig = inspect.signature(Kernel.__init__)
    assert "snapshot_path" not in sig.parameters
    assert "boot_script" in sig.parameters


def test_kernel_no_init_L_method():
    assert not hasattr(Kernel, "_init_L")
    assert not hasattr(Kernel, "_init_namespace")


def test_no_dropped_keys_helpers():
    """_picklable / _find_creation_operation / _dropped_keys / _dropped_keys_context
    are all gone from kernel.py (deferred to PR 6 DeadHandle but the L-side filter
    must already be removed in PR 4 because boot frame's obs_diff_json is the
    spec-mandated disclosure channel)."""
    import vessal.ark.shell.hull.cell.kernel.kernel as km
    src = Path(km.__file__).read_text()
    assert "_picklable" not in src
    assert "_dropped_keys" not in src
    assert "_find_creation_operation" not in src


def test_skills_manifest_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        import vessal.ark.shell.hull.skills_manifest  # noqa: F401


# ────────────────────────────────────────────────────────────
# Snapshot location (spec §5.1)
# ────────────────────────────────────────────────────────────

def test_snapshots_live_under_per_cell_data_dir(tmp_path: Path, monkeypatch):
    """Spec §5.1: snapshot blobs are sibling of frame_log.sqlite, both under
    data/<cell>/. Hull MUST NOT use <project>/snapshots/."""
    # Hull-level integration test: build a Hull on a fake project, snapshot,
    # verify path lands under data/<cell>/snapshots/.
    from vessal.ark.shell.hull.hull import Hull

    project = tmp_path / "agent"
    (project / "data" / "main").mkdir(parents=True)
    (project / "hull.toml").write_text(
        '[hull]\nskills = []\n[cells.main]\ndata_dir = "data/main"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    h = Hull(project_dir=str(project))
    h.snapshot()

    # Assert the .pkl landed under data/main/snapshots/, NOT <project>/snapshots/
    assert (project / "data" / "main" / "snapshots").exists()
    assert list((project / "data" / "main" / "snapshots").glob("*.pkl"))
    assert not (project / "snapshots").exists()
