"""kernel.ping plumbs stderr from executor into L['observation'].stderr and SQLite obs_stderr."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def test_kernel_ping_pipes_stderr_to_observation(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})  # first ping

    pong = Pong(think="t", action=Action(
        operation="import sys; sys.stderr.write('boom\\n')",
        expect="",
    ))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    assert k.L["observation"].stderr == "boom\n"


def test_kernel_writes_obs_stderr_to_sqlite(tmp_path: Path):
    import sqlite3

    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(
        operation="import sys; sys.stderr.write('warn\\n')",
        expect="",
    ))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    rows = sqlite3.connect(str(db)).execute(
        "SELECT n, obs_stderr FROM frame_content ORDER BY n"
    ).fetchall()
    # boot frame (n=1) has empty stderr in this test (empty boot script);
    # the ping frame (n=2) is the one with our 'warn' write.
    assert rows[-1][1] == "warn\n"
