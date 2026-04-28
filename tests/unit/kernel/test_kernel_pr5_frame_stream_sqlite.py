"""test_kernel_pr5_frame_stream_sqlite.py — PR 5 invariants.

Spec §1.4 + §4.8-§4.10:
  - Kernel.ping() returns Ping with FrameStream dataclass (not string).
  - Kernel reads frame_stream from SQLite each ping (no in-memory LSM).
  - Kernel L initialization no longer seeds rendering / budget / LSM keys.
"""
from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import FrameStream, Ping, State


def _kernel(tmp_path):
    db = str(tmp_path / "fl.sqlite")
    return Kernel(boot_script="", db_path=db)


def test_l_init_no_longer_seeds_rendering_keys(tmp_path):
    k = _kernel(tmp_path)
    forbidden = {
        "_frame_stream", "_compaction_k", "_compaction_n",
        "_context_pct", "_budget_total", "_context_budget", "_token_budget",
        "_dropped_frame_count", "_render_config", "_frame_type", "_ns_meta",
    }
    leaked = forbidden & set(k.L.keys())
    assert not leaked, f"PR 5 forbids these L keys, found: {leaked}"


def test_ping_returns_dataclass_state(tmp_path):
    k = _kernel(tmp_path)
    ping = k.ping(None, {"globals": k.G, "locals": k.L})
    assert isinstance(ping, Ping)
    assert isinstance(ping.state.frame_stream, FrameStream)
    assert isinstance(ping.state.signals, dict)


def test_ping_frame_stream_reflects_sqlite(tmp_path):
    """After two committed frames, FrameStream has entries for x=1 and y=2."""
    from vessal.ark.shell.hull.cell.protocol import Action, Pong

    k = _kernel(tmp_path)
    p1 = Pong(think="", action=Action(operation="x = 1", expect="True"))
    k.ping(p1, {"globals": k.G, "locals": k.L})
    p2 = Pong(think="", action=Action(operation="y = 2", expect="True"))
    ping = k.ping(p2, {"globals": k.G, "locals": k.L})

    fs = ping.state.frame_stream
    operations = [e.content.operation for e in fs.entries if e.layer == 0]
    assert "x = 1" in operations
    assert "y = 2" in operations


def test_frame_stream_module_no_longer_imports():
    with pytest.raises(ImportError):
        import vessal.ark.shell.hull.cell.kernel.frame_stream  # noqa: F401


def test_render_module_no_longer_imports():
    with pytest.raises(ImportError):
        from vessal.ark.shell.hull.cell.kernel import render  # noqa: F401


def test_kernel_render_helper_removed():
    """Kernel.ping no longer calls a Kernel-side render() function."""
    import inspect
    from vessal.ark.shell.hull.cell.kernel import kernel as k_mod
    src = inspect.getsource(k_mod.Kernel.ping)
    assert "_render(" not in src
    assert "render(self.L" not in src
