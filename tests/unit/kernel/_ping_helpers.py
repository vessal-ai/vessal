from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def _ns(k: Kernel) -> dict:
    return {"globals": k.G, "locals": k.L}


def _exec(k: Kernel, op: str, expect: str = "") -> None:
    if k._last_ping is None:
        k.ping(None, _ns(k))
    pong = Pong(think="", action=Action(operation=op, expect=expect))
    return k.ping(pong, _ns(k))


def minimal_kernel(*, db_path: str | None = None, with_system: bool = True, restore_path: str | None = None):
    """Construct a Kernel with a minimal boot script — used by all PR 1/2/3 tests."""
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    entries = []
    if with_system:
        entries.append(
            BootSkillEntry("_system", "vessal.skills.system", "SystemSkill", "")
        )
    return Kernel(boot_script=compose_boot_script(entries), db_path=db_path, restore_path=restore_path)
