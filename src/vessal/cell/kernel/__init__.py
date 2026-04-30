"""__init__.py — Kernel public interface: execution kernel and code execution result types."""
from vessal.cell.kernel.kernel import Kernel
from vessal.cell.kernel.executor import ExecResult
from vessal.cell.kernel.describe import render_value
from vessal.cell.kernel.lenient import UnresolvedRef
from vessal.cell.kernel.boot import compose_boot_script, BootSkillEntry
from vessal.cell.kernel.dead_handle import DeadHandle
from vessal.cell.kernel.transient import transient

__all__ = [
    "Kernel",
    "ExecResult",
    "render_value",
    "UnresolvedRef",
    "compose_boot_script",
    "BootSkillEntry",
    "DeadHandle",
    "transient",
]
