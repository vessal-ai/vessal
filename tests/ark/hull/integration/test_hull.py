# test_hull.py — Hull module tests (merged from test_hull.py + test_hull_v3.py)
#
# Strategy: build project directory using real filesystem (tmp_path fixture), mock Cell's
# _core.step to avoid real API calls. Kernel uses real instances; snapshot/restore follow
# real paths.
#
# Hull.run_forever() is an async method — sync tests use hull._event_loop._frame_loop().
# Agent signals completion via sleep(), no longer uses finished/result/goal.
# Tests build project directories using real filesystem, mock Cell's _core.step to avoid
# real API calls.

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.hull import Hull


# ============================================================
# Utility functions
# ============================================================


def _make_project(tmp_path, toml_content="", skills=None, env_content=None, soul_content=None):
    """Create a Hull project structure under tmp_path."""
    if toml_content:
        (tmp_path / "hull.toml").write_text(toml_content, encoding="utf-8")
    if skills:
        for rel_path, content in skills.items():
            skill_file = tmp_path / rel_path
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(content, encoding="utf-8")
    if env_content is not None:
        (tmp_path / ".env").write_text(env_content, encoding="utf-8")
    if soul_content is not None:
        (tmp_path / "SOUL.md").write_text(soul_content, encoding="utf-8")


def _make_hull(tmp_path, toml_content="", skills=None, env_content=None, soul_content=None):
    """Create a Hull and mock Core to avoid API calls. Returns Hull instance."""
    _make_project(tmp_path, toml_content, skills, env_content, soul_content)
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        hull = Hull(str(tmp_path))
    return hull


def _set_responses(hull, responses):
    """Set mock return values for Hull's internal Cell's _core.step ((Pong, None, None) triples).

    Bare Python strings are auto-wrapped in <action>...</action> format to pass parse_response.
    """
    from vessal.ark.shell.hull.cell.core.parser import parse_response

    def make_result(resp):
        if isinstance(resp, str):
            # Wrap bare code in v4 protocol format (<action> tag required by parse_response)
            if "<action>" not in resp:
                resp = f"<action>\n{resp}\n</action>"
            return (parse_response(resp), None, None)
        return resp

    hull._cell._core.step = MagicMock(side_effect=[make_result(r) for r in responses])


def _run_frame_loop(hull):
    """Synchronously execute the frame loop; test helper."""
    hull._event_loop._frame_loop()


# ============================================================
# Configuration parsing tests
# ============================================================


class TestConfig:
    def test_no_toml_uses_defaults(self, tmp_path):
        """Uses all defaults when hull.toml does not exist."""
        hull = _make_hull(tmp_path)
        assert "role" not in hull._cell.ns
        assert "language" not in hull._cell.ns

    def test_empty_toml_uses_defaults(self, tmp_path):
        """Uses all defaults when hull.toml is an empty file."""
        hull = _make_hull(tmp_path, toml_content=" ")
        assert "role" not in hull._cell.ns

    def test_agent_role_not_injected(self, tmp_path):
        """[agent].role is no longer injected into namespace (identity defined by SOUL.md)."""
        toml = '[agent]\nrole = "You are a test assistant"'
        hull = _make_hull(tmp_path, toml_content=toml)
        assert "role" not in hull._cell.ns

    def test_agent_language_injected(self, tmp_path):
        """[agent].language is written to ns["language"]."""
        toml = '[agent]\nlanguage = "zh"'
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell.ns["language"] == "zh"

    def test_cell_temperature_forwarded(self, tmp_path):
        """[cell].temperature is forwarded to Core api_params."""
        toml = "[cell]\ntemperature = 0.3"
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell._core._api_params["temperature"] == 0.3

    def test_max_frames_config(self, tmp_path):
        """[cell].max_frames is stored in Hull (not in Cell)."""
        toml = "[cell]\nmax_frames = 50"
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._max_frames == 50

    def test_gates_applied(self, tmp_path):
        """[gates] config is written to cell.state_gate and cell.action_gate."""
        toml = '[gates]\nstate_gate = "auto"\naction_gate = "auto"'
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell.state_gate == "auto"
        assert hull._cell.action_gate == "auto"

    def test_context_budget_set(self, tmp_path):
        """[cell].context_budget is written to ns["_context_budget"]."""
        toml = "[cell]\ncontext_budget = 64000"
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell.ns["_context_budget"] == 64000

    def test_core_timeout_forwarded(self, tmp_path):
        """[core].timeout is forwarded to Core."""
        toml = "[core]\ntimeout = 120.0"
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell._core._timeout == 120.0

    def test_core_max_retries_forwarded(self, tmp_path):
        """[core].max_retries is forwarded to Core."""
        toml = "[core]\nmax_retries = 5"
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell._core._max_retries == 5

    def test_core_default_timeout(self, tmp_path):
        """Uses default timeout of 60.0 when hull.toml has no [core] section."""
        hull = _make_hull(tmp_path)
        assert hull._cell._core._timeout == 60.0

    def test_core_default_max_retries(self, tmp_path):
        """Uses default max_retries of 3 when hull.toml has no [core] section."""
        hull = _make_hull(tmp_path)
        assert hull._cell._core._max_retries == 3

    def test_renderer_config_parsed(self, tmp_path):
        """[renderer] section is parsed correctly (auxiliary_modules removed from RenderConfig)."""
        toml = """
[renderer]
system_prompt_key = "_my_prompt"
frame_budget_ratio = 0.8
"""
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._work_render_config.system_prompt_key == "_my_prompt"
        assert hull._work_render_config.frame_budget_ratio == 0.8

# ============================================================
# Frame loop tests
# ============================================================


class TestRunLoop:
    """Hull event loop behavior tests."""

    def test_frame_loop_sets_idle(self, tmp_path):
        """Agent calls sleep(); _frame_loop() stops after that frame."""
        hull = _make_hull(tmp_path)
        _set_responses(hull, ['sleep()'])
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        assert hull._cell.ns["_sleeping"] is True

    def test_frame_loop_calls_step(self, tmp_path):
        """_frame_loop() calls cell.step()."""
        hull = _make_hull(tmp_path)
        assert not hasattr(hull._cell, "run")
        _set_responses(hull, ['sleep()'])
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)  # should not raise

    def test_frame_loop_max_frames_cutoff(self, tmp_path):
        """Loop stops at the frame limit; _sleeping remains False."""
        toml = "[cell]\nmax_frames = 2"
        hull = _make_hull(tmp_path, toml_content=toml)
        from vessal.ark.shell.hull.cell.core.parser import parse_response
        _raw = "<action>\npass\n</action>"
        hull._cell._core.step = MagicMock(
            return_value=(parse_response(_raw), None, None)
        )
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        # Frame limit reached; _sleeping was not set by Agent
        assert hull._cell.ns.get("_sleeping") is False

    def test_frame_loop_rewrite_runtime_owned_each_frame(self, tmp_path):
        """_frame_type is reset to "work" before each frame's step()."""
        hull = _make_hull(tmp_path)
        frame_types_seen = []

        original_step = hull._cell.step

        def capturing_step(tracer=None):
            frame_types_seen.append(hull._cell.ns.get("_frame_type"))
            return original_step(tracer)

        hull._cell.step = capturing_step
        from vessal.ark.shell.hull.cell.core.parser import parse_response
        _raw = '<action>\nsleep()\n</action>'
        hull._cell._core.step = MagicMock(
            return_value=(parse_response(_raw), None, None)
        )
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)

        assert all(ft == "work" for ft in frame_types_seen)

    def test_frame_loop_preserves_namespace_across_runs(self, tmp_path):
        """Namespace is preserved between multiple _frame_loop() calls."""
        hull = _make_hull(tmp_path)
        _set_responses(hull, [
            'x = 42\nsleep()',
        ])
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        assert hull._cell.ns.get("x") == 42

        _set_responses(hull, ['result_val = x\nsleep()'])
        hull._cell.ns["_sleeping"] = False
        hull._cell.ns["_wake"] = "user_message"
        _run_frame_loop(hull)
        assert hull._cell.ns.get("result_val") == 42

    def test_frame_loop_snapshot_not_auto(self, tmp_path):
        """_frame_loop() does not automatically snapshot (snapshots triggered manually by Hull.snapshot())."""
        hull = _make_hull(tmp_path)
        _set_responses(hull, ['sleep()'])
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        snapshots = list((tmp_path / "snapshots").glob("*.pkl")) if (tmp_path / "snapshots").exists() else []
        assert len(snapshots) == 0

    def test_hull_has_run(self, tmp_path):
        """Hull has a run() method (replaces old run_forever)."""
        import inspect
        hull = _make_hull(tmp_path)
        assert hasattr(hull, "run")
        assert inspect.iscoroutinefunction(hull.run)

    def test_hull_has_event_queue(self, tmp_path):
        """Hull has an event_queue attribute (stdlib queue.Queue, thread-safe)."""
        import queue as queue_mod
        hull = _make_hull(tmp_path)
        assert hasattr(hull, "event_queue")
        assert isinstance(hull.event_queue, queue_mod.Queue)

    def test_hull_has_stop(self, tmp_path):
        """Hull has a stop() method."""
        hull = _make_hull(tmp_path)
        assert hasattr(hull, "stop")
        assert callable(hull.stop)



# ============================================================
# Memory search tests
# ============================================================


# ============================================================
# Logging tests
# ============================================================


class TestLog:
    def test_frame_logger_can_be_created(self, tmp_path):
        """FrameLogger can be created normally."""
        from vessal.ark.util.logging import FrameLogger
        hull = _make_hull(tmp_path)
        log_dir = hull._log_dir
        fl = FrameLogger(log_dir)
        run_dir = fl.open()
        fl.close()
        assert run_dir.exists()

    def test_log_dir_under_project(self, tmp_path):
        """Log directory is under the project directory's logs/ folder."""
        hull = _make_hull(tmp_path)
        assert str(tmp_path / "logs") in hull._log_dir

    def test_log_dir_created(self, tmp_path):
        """logs/ directory exists after Hull initialization."""
        hull = _make_hull(tmp_path)
        assert Path(hull._log_dir).exists()


# ============================================================
# Snapshot tests
# ============================================================


class TestSnapshot:
    def test_snapshot_manual(self, tmp_path):
        """Manual snapshot() saves to the specified path."""
        hull = _make_hull(tmp_path)
        path = str(tmp_path / "manual.pkl")
        returned = hull.snapshot(path)
        assert returned == path
        assert Path(path).exists()

    def test_snapshot_auto_path(self, tmp_path):
        """snapshot() auto-generates a timestamped filename when no path is given."""
        hull = _make_hull(tmp_path)
        path = hull.snapshot()
        assert path.endswith(".pkl")
        assert Path(path).exists()
        assert str(tmp_path / "snapshots") in path

    def test_snapshots_dir_under_project(self, tmp_path):
        """Snapshot directory is under the project directory's snapshots/ folder."""
        hull = _make_hull(tmp_path)
        snap_path = hull.snapshot()
        assert str(tmp_path / "snapshots") in snap_path

    def test_restore_latest_snapshot(self, tmp_path):
        """Automatically restores the latest .pkl from snapshots/ on startup."""
        hull1 = _make_hull(tmp_path)
        # Set a variable directly in namespace, then manually snapshot
        hull1._cell.ns["my_var"] = "hello"
        hull1.snapshot()

        with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
            hull2 = Hull(str(tmp_path))
        assert hull2._cell.ns.get("my_var") == "hello"

    def test_no_snapshots_dir_ok(self, tmp_path):
        """Silently skips restore when snapshots/ directory does not exist."""
        hull = _make_hull(tmp_path)
        assert not (tmp_path / "snapshots").exists()
        assert hull._cell.ns is not None


# ============================================================
# .env loading tests
# ============================================================


class TestEnv:
    def test_env_loaded_before_cell(self, tmp_path):
        """.env variables are loaded into os.environ before Cell is created."""
        env_content = "TEST_HULL_UNIQUE_VAR=hello_world"
        os.environ.pop("TEST_HULL_UNIQUE_VAR", None)

        _make_project(tmp_path, env_content=env_content)
        with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
            Hull(str(tmp_path))

        assert os.environ.get("TEST_HULL_UNIQUE_VAR") == "hello_world"
        os.environ.pop("TEST_HULL_UNIQUE_VAR", None)

    def test_no_env_file_ok(self, tmp_path):
        """Silently skips when .env does not exist; startup proceeds normally."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns is not None


# ============================================================
# Namespace passthrough tests
# ============================================================


class TestNamespaceAccess:
    def test_ns_injection_visible_to_agent(self, tmp_path):
        """Variables injected via hull._cell.ns are visible during _frame_loop()."""
        hull = _make_hull(tmp_path)
        hull._cell.ns["custom_var"] = "test_value"
        _set_responses(hull, ['result_val = custom_var\nsleep()'])
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        assert hull._cell.ns.get("result_val") == "test_value"


# ============================================================
# frame_type tests
# ============================================================


class TestFrameType:
    def test_frame_type_default_is_work(self, tmp_path):
        """_frame_type is "work" after Hull initialization."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns["_frame_type"] == "work"

    def test_frame_type_in_ns(self, tmp_path):
        """_frame_type exists in namespace."""
        hull = _make_hull(tmp_path)
        assert "_frame_type" in hull._cell.ns

    def test_rewrite_runtime_owned_sets_frame_type(self, tmp_path):
        """_rewrite_runtime_owned always sets _frame_type to "work"."""
        hull = _make_hull(tmp_path)
        hull._rewrite_runtime_owned()
        assert hull._cell.ns["_frame_type"] == "work"


# ============================================================
# RenderConfig tests
# ============================================================


class TestRenderConfig:
    def test_work_render_config_created(self, tmp_path):
        """Hull has a work frame RenderConfig after initialization."""
        hull = _make_hull(tmp_path)
        assert hull._work_render_config is not None

    def test_work_config_system_prompt_key(self, tmp_path):
        """Work frame config's system_prompt_key defaults to _system_prompt."""
        hull = _make_hull(tmp_path)
        assert hull._work_render_config.system_prompt_key == "_system_prompt"

    def test_work_config_frame_budget_ratio(self, tmp_path):
        """Work frame config's frame_budget_ratio defaults to 0.7."""
        hull = _make_hull(tmp_path)
        assert hull._work_render_config.frame_budget_ratio == 0.7

    def test_render_config_in_ns_is_work_config(self, tmp_path):
        """_render_config in namespace defaults to the work frame config."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns.get("_render_config") is hull._work_render_config

    def test_custom_renderer_config(self, tmp_path):
        """hull.toml [renderer] section config takes effect."""
        toml = """
[renderer]
system_prompt_key = "_custom_prompt"
frame_budget_ratio = 0.6
"""
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._work_render_config.system_prompt_key == "_custom_prompt"
        assert hull._work_render_config.frame_budget_ratio == 0.6


# ============================================================
# Cold storage injection tests
# ============================================================


# ============================================================
# Skill loading tests
# ============================================================


class TestSkills:
    def test_skill_paths_set(self, tmp_path):
        """[hull].skill_paths is parsed as absolute paths written to ns["skill_paths"]."""
        toml = '[hull]\nskill_paths = ["skills/extra/"]'
        hull = _make_hull(tmp_path, toml_content=toml)
        expected = str(tmp_path / "skills/extra")
        assert any(expected in p for p in hull._cell.ns["skill_paths"])

    def test_no_skills_section(self, tmp_path):
        """No Skills are loaded and startup proceeds normally when hull.toml has no [hull] section."""
        toml = '[agent]\nname = "test"'
        hull = _make_hull(tmp_path, toml_content=toml)
        assert hull._cell.ns is not None


# ============================================================
# SOUL.md loading tests
# ============================================================


class TestSoulMd:
    def test_soul_loaded_from_file(self, tmp_path):
        """SOUL.md content is loaded into _soul when present (no longer placed in _system_prompt)."""
        soul_content = "# Agent Identity\nYou are a data analysis expert."
        hull = _make_hull(tmp_path, soul_content=soul_content)
        # _soul holds the raw SOUL.md text; _system_prompt contains only kernel protocol
        assert soul_content == hull._cell.ns["_soul"]
        assert "Execution Model" in hull._cell.ns["_system_prompt"]

    def test_soul_empty_when_no_file(self, tmp_path):
        """_soul is empty string when SOUL.md does not exist; _system_prompt contains only runtime protocol."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns["_soul"] == ""
        assert "Execution Model" in hull._cell.ns["_system_prompt"]

    def test_soul_shown_in_rendered_state(self, tmp_path):
        """SOUL.md content appears in the rendered Ping via three-part renderer concatenation."""
        hull = _make_hull(tmp_path, soul_content="You are a data expert")
        ping = hull._cell._kernel.render()
        assert "You are a data expert" in ping.system_prompt


# ============================================================
# Virtualenv activation tests
# ============================================================


class TestVenvActivation:
    def test_activate_venv_adds_site_packages(self, tmp_path):
        """When .venv exists, site-packages is added to sys.path."""
        py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = tmp_path / ".venv" / "lib" / py_ver / "site-packages"
        site_packages.mkdir(parents=True)

        hull = _make_hull(tmp_path)

        assert str(site_packages) in sys.path
        sys.path.remove(str(site_packages))

    def test_no_venv_no_error(self, tmp_path):
        """Silently skips when no .venv directory exists; no error raised."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns is not None



class TestWake:
    def test_wake_default_empty(self, tmp_path):
        """_wake is empty string after Hull initialization."""
        hull = _make_hull(tmp_path)
        assert hull._cell.ns["_wake"] == ""

    def test_wake_set_before_frame_loop(self, tmp_path):
        """_wake retains its injected value during _frame_loop() execution."""
        hull = _make_hull(tmp_path)
        wake_seen = []
        original_step = hull._cell.step
        def capturing_step(tracer=None):
            wake_seen.append(hull._cell.ns.get("_wake"))
            return original_step(tracer)
        hull._cell.step = capturing_step
        from vessal.ark.shell.hull.cell.core.parser import parse_response
        _raw = '<action>\nsleep()\n</action>'
        hull._cell._core.step = MagicMock(
            return_value=(parse_response(_raw), None, None)
        )
        hull._cell.ns["_wake"] = "user_message"
        hull._cell.ns["_sleeping"] = False
        _run_frame_loop(hull)
        assert all(w == "user_message" for w in wake_seen)


class TestDataDir:
    def test_data_dir_injected(self, tmp_path):
        """Hull should inject _data_dir pointing to project_dir/data."""
        hull = _make_hull(tmp_path)
        data_dir = hull._cell.ns.get("_data_dir")
        assert data_dir is not None
        assert data_dir.endswith("/data") or data_dir.endswith("\\data")
