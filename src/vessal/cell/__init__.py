"""__init__.py — Cell public interface: stateful execution engine and frame protocol data structures."""
from vessal.ark.shell.hull.cell.cell import Cell
from vessal.ark.shell.hull.cell.protocol import StepResult

__all__ = ["Cell", "StepResult"]
