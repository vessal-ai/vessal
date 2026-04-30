"""__init__.py — Hull public interface: Agent orchestration layer entry point."""
from vessal.hull.hull import Hull
from vessal.cell.kernel.describe import render_value

__all__ = ["Hull", "render_value"]
