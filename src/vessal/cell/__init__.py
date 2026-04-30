"""__init__.py — Cell public interface: stateful execution engine and frame protocol data structures."""
from vessal.cell.cell import Cell
from vessal.cell.protocol import StepResult

__all__ = ["Cell", "StepResult"]
