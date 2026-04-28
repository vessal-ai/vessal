"""PR 6 architecture invariants — spec §3 / §5 / §6 / §7 / §8."""
from __future__ import annotations

import dataclasses

from vessal.ark.shell.hull.cell.protocol import Observation


def test_observation_shape() -> None:
    fields = {f.name for f in dataclasses.fields(Observation)}
    assert fields == {"stdout", "stderr", "diff", "error"}


def test_no_kernel_sleep_method() -> None:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    assert not hasattr(Kernel, "sleep")


def test_kernel_l_init_minimal() -> None:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    k = Kernel(boot_script="")
    assert set(k.L.keys()) == {"_frame", "signals"}


def test_dead_handle_unresolved_ref_transient_exported() -> None:
    from vessal.ark.shell.hull.cell.kernel import (
        DeadHandle, transient,
    )
    from vessal.ark.shell.hull.cell.kernel.lenient import UnresolvedRef
    assert callable(transient)
    assert DeadHandle.__name__ == "DeadHandle"
    assert UnresolvedRef.__name__ == "UnresolvedRef"


def test_system_skill_has_sleep_wake() -> None:
    from vessal.skills.system import SystemSkill
    assert callable(SystemSkill.sleep)
    assert callable(SystemSkill.wake)


def test_system_skill_signal_update_does_not_read_dead_keys(tmp_path) -> None:
    """SystemSkill.signal_update must source from authoritative places only."""
    import inspect
    from vessal.skills.system.skill import SystemSkill
    src = inspect.getsource(SystemSkill.signal_update)
    forbidden = ["_context_pct", "_budget_total", "_context_budget",
                 "_token_budget", "_frame_type", "_errors"]
    for sym in forbidden:
        assert f'"{sym}"' not in src and f"'{sym}'" not in src, (
            f"_system Skill still reads dead key {sym!r}"
        )
