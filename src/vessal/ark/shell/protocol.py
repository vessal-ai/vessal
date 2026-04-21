"""protocol.py — Shell ↔ Hull protocol definitions. Shared by all Shell implementations.

handle() is Hull's sole entry point. Shell adapters (subprocess_mode, container_mode,
future embedded ipc_adapter) translate external requests into handle(method, path, body)
calls and translate return values back to external protocols.

This module defines the return type of handle(), shared by all adapters.
"""

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from vessal.ark.shell.hull.hull_api import StaticResponse

# handle() return type: (status code, JSON dict or StaticResponse)
HandleResult = tuple[int, Union[dict, "StaticResponse"]]
