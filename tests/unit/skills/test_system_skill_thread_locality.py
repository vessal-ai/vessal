from __future__ import annotations

import threading
from pathlib import Path


def test_signal_update_callable_from_non_construction_thread(tmp_path: Path):
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry

    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "System"),
    ])
    kernel = Kernel(boot_script=script, db_path=str(db))
    sys_skill = kernel.G["_system"]

    error: list = []

    def worker():
        try:
            sys_skill.signal_update()
        except Exception as exc:
            error.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert error == [], f"signal_update raised on worker thread: {error}"
    assert "frame" in sys_skill.signal


def test_signal_update_no_db_does_not_crash(tmp_path: Path):
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry

    script = compose_boot_script([
        BootSkillEntry("_system", "System"),
    ])
    kernel = Kernel(boot_script=script, db_path=None)
    sys_skill = kernel.G["_system"]

    sys_skill.signal_update()

    assert "frame" in sys_skill.signal
    assert "recent_errors" not in sys_skill.signal
