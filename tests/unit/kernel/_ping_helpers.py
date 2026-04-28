from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def _ns(k: Kernel) -> dict:
    return {"globals": k.G, "locals": k.L}


def _exec(k: Kernel, op: str, expect: str = "") -> None:
    if k._last_ping is None:
        k.ping(None, _ns(k))
    pong = Pong(think="", action=Action(operation=op, expect=expect))
    return k.ping(pong, _ns(k))
