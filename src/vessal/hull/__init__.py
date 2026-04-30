"""__init__.py — Hull public interface: Agent orchestration layer entry point."""
from vessal.ark.shell.hull.hull import Hull
from vessal.ark.shell.hull.cell.kernel.describe import render_value

__all__ = ["Hull", "render_value"]
