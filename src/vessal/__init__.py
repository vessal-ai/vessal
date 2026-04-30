"""vessal — Public interface for the LLM-powered Agent runtime.

Re-exports core types. Users may write `from vessal import Cell, Core, Hull`
or import directly from `vessal.cell`, `vessal.cell.core`, `vessal.hull`.
Both forms are equivalent.
"""

from vessal.cell import Cell
from vessal.cell.core import Core
from vessal.hull import Hull

__version__ = "0.0.4"
__all__ = ["Cell", "Core", "Hull"]
