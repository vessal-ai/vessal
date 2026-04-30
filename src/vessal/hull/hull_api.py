"""hull_api.py — Interface for Skill server interaction with Hull: route registration, wake, and static responses."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Callable


class StaticResponse:
    """Used when a route handler returns static content; Shell responds as-is with the given content_type.

    Attributes:
        content: Response body as bytes.
        content_type: MIME type string (e.g. "text/html").
    """
    __slots__ = ("content", "content_type")

    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.content_type = content_type

    @classmethod
    def from_file(cls, path: Path | str) -> "StaticResponse":
        """Construct a StaticResponse from a file path; content_type is inferred by mimetypes.

        Args:
            path: File path (Path or str).

        Returns:
            StaticResponse instance containing the file content and inferred MIME type.
        """
        path = Path(path)
        content = path.read_bytes()
        ct, _ = mimetypes.guess_type(path.name)
        return cls(content, ct or "application/octet-stream")


class HullApi:
    """Hull interface for Skill servers: route registration and Agent wake.

    Attributes:
        _routes: Reference to Hull's route table ((method, path) → handler).
        _wake_fn: Reference to Hull.wake; used by Skill servers to trigger a wake.
    """

    def __init__(
        self,
        routes: dict[tuple[str, str], Callable],
        wake_fn: Callable[[str], None],
    ):
        self._routes = routes
        self._wake_fn = wake_fn

    def register_route(
        self,
        method: str,
        path: str,
        handler: Callable[[dict | None], tuple[int, dict | StaticResponse]],
    ) -> None:
        """Register an HTTP route in the Hull route table.

        Args:
            method: HTTP method ("GET" or "POST"); auto-uppercased.
            path: Route path (e.g. "/skills/human/inbox").
            handler: Request handler with signature (body: dict | None) -> (status: int, response).
        """
        self._routes[(method.upper(), path)] = handler

    def unregister_route(self, path: str) -> None:
        """Unregister all routes for a given path (GET, POST, etc. are all removed).

        Args:
            path: The route path to unregister.
        """
        to_remove = [k for k in self._routes if k[1] == path]
        for k in to_remove:
            del self._routes[k]

    def wake(self, reason: str = "skill") -> None:
        """Wake the Agent by delivering an event to the Hull event queue.

        Args:
            reason: Wake reason (e.g. "heartbeat", "webhook").
        """
        self._wake_fn(reason)


class ScopedHullApi:
    """HullApi wrapper for a specific Skill; automatically prepends /skills/{name} to all routes.

    Attributes:
        _api: Underlying HullApi instance.
        _prefix: Route prefix string, format: /skills/{name}.
    """

    def __init__(self, hull_api: HullApi, skill_name: str):
        self._api = hull_api
        self._prefix = f"/skills/{skill_name}"

    def register_route(self, method: str, path: str, handler: Callable) -> None:
        """Register a route, automatically prepending the /skills/{name} prefix.

        Args:
            method: HTTP method ("GET" or "POST").
            path: Relative path; "/" maps to /skills/{name}/.
            handler: Request handler with signature (body: dict | None) -> (status: int, response).
        """
        full_path = self._prefix + path if path != "/" else self._prefix + "/"
        self._api.register_route(method, full_path, handler)

    def unregister_route(self, path: str) -> None:
        """Unregister a route, automatically prepending the /skills/{name} prefix.

        Args:
            path: Relative path; same convention as register_route.
        """
        full_path = self._prefix + path if path != "/" else self._prefix + "/"
        self._api.unregister_route(full_path)

    def wake(self, reason: str = "skill") -> None:
        """Wake the Agent (delegated to the underlying HullApi).

        Args:
            reason: Wake reason (e.g. "heartbeat").
        """
        self._api.wake(reason)
