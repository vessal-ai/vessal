"""__init__.py — Kernel public interface: execution kernel and code execution result types."""
from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.executor import ExecResult
from vessal.ark.shell.hull.cell.kernel.render.renderer import RenderConfig, DEFAULT_CONFIG
from vessal.ark.shell.hull.cell.kernel.describe import render_value
from vessal.ark.shell.hull.cell.kernel.lenient import UnresolvedRef
from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry

__all__ = [
    "Kernel",
    "ExecResult",
    "RenderConfig",
    "DEFAULT_CONFIG",
    "render_value",
    "UnresolvedRef",
    "compose_boot_script",
    "BootSkillEntry",
]
