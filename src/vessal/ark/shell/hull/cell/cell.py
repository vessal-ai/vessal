"""cell.py — Stateful execution engine: Kernel + Core + single-frame step(); does not auto-loop."""
#
# Single-frame execution order:
#   (first call only) kernel.ping(None, ns) → state_gate → core.step → action_gate → kernel.ping(pong, ns) → return StepResult
#
# Public interface:
#   G               preset assets dict (property, proxied from Kernel)
#   L               agent state dict (property, proxied from Kernel)
#   ping            Ping from the most recently committed frame record (property, read-only)
#   pong            Pong from the previous step (property, read-only)
#   action_gate     str property (reads and writes go through an ActionGate instance)
#   state_gate      str property (reads and writes go through a StateGate instance)
#   step(tracer)    single-frame ping-pong, returns StepResult
#   snapshot(path)  serialize L to file
#   restore(path)   deserialize L from file

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from vessal.ark.shell.hull.cell._errors_helper import append_error
from vessal.ark.shell.hull.cell.core import Core
from vessal.ark.shell.hull.cell.gate import ActionGate, StateGate
from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import ErrorRecord, Ping, Pong, StepResult
from vessal.ark.shell.hull.cell._tracer_protocol import TracerLike


class Cell:
    """Stateful state machine (v4 Protocol).

    Encapsulates Kernel (execution) and Core (reasoning), providing a single-frame step() interface.
    Does not auto-loop, does not hold logs, and does not manage the Tracer lifecycle — these are Hull's responsibility.

    Hull injects system variables (_system_prompt, _memories, etc.) via cell.L;
    the L dict itself is the injection interface, no dedicated channel is needed.

    gate attributes take values "auto" | "safe" | "human"; reads and writes go through ActionGate/StateGate instances.
    Hull can switch modes via cell.action_gate = "safe" without knowing about internal Gate objects.
    """

    def __init__(
        self,
        snapshot_path: str | None = None,
        timeout: float = 60.0,
        core_max_retries: int = 3,
        api_params: dict[str, object] | None = None,
        action_gate: str = "auto",
        state_gate: str = "auto",
        *,
        cell_name: str = "main",
        data_dir: str | None = None,
    ) -> None:
        """Initialize Cell.

        Args:
            snapshot_path: If not None, restore namespace from snapshot.
            timeout: Request timeout in seconds, passed through to Core.
            core_max_retries: Network-layer retry count, passed through to Core.
            api_params: API parameter dict passed through to Core, forwarded as **kwargs to
                chat.completions.create(). Default: {"temperature": 0.7, "max_tokens": 4096}.
            action_gate: ActionGate initial mode, "auto" | "safe" | "human".
            state_gate: StateGate initial mode, "auto" | "safe" | "human".
            cell_name: Logical Cell name, e.g. "main" or "compaction". Used by callers
                for logging and by future multi-Cell wiring; does not affect Kernel.
            data_dir: Absolute filesystem path to this Cell's per-Cell data directory
                (typically <project>/data/<cell_name>/). When provided, the directory
                must already exist; Cell forwards <data_dir>/frame_log.sqlite to
                Kernel as db_path so SQLite frame_log is enabled. When None, no
                frame_log is opened (back-compat for callers that do not yet pass it).
        """
        self.cell_name = cell_name
        self._data_dir = data_dir

        db_path: str | None = None
        if data_dir is not None:
            if not Path(data_dir).is_dir():
                raise FileNotFoundError(
                    f"Cell data_dir does not exist: {data_dir!r}. "
                    f"Hull is responsible for creating it before constructing Cell."
                )
            db_path = str(Path(data_dir) / "frame_log.sqlite")

        self._kernel = Kernel(snapshot_path=snapshot_path, db_path=db_path)
        self._core = Core(
            timeout=timeout,
            max_retries=core_max_retries,
            api_params=api_params,
        )
        self._action_gate = ActionGate(mode=action_gate)
        self._state_gate = StateGate(mode=state_gate)
        self._ping: Ping | None = None
        self._pong: Pong | None = None

    # ------------------------------------------------------------------ Public interface

    @property
    def max_tokens(self) -> int:
        return self._core.max_tokens

    @property
    def action_gate(self) -> str:
        """Current ActionGate mode string ("auto" | "safe" | "human")."""
        return self._action_gate.mode

    @action_gate.setter
    def action_gate(self, mode: str) -> None:
        self._action_gate = ActionGate(mode=mode)

    @property
    def state_gate(self) -> str:
        """Current StateGate mode string ("auto" | "safe" | "human")."""
        return self._state_gate.mode

    @state_gate.setter
    def state_gate(self, mode: str) -> None:
        self._state_gate = StateGate(mode=mode)

    @property
    def ping(self) -> Ping | None:
        """Ping from the most recently committed frame record. Updated at the end of step() from frame_stream."""
        return self._ping

    @property
    def pong(self) -> Pong | None:
        """Pong from the most recently committed frame record. Updated at the end of step() from frame_stream."""
        return self._pong

    @property
    def G(self) -> dict[str, Any]:
        """Preset assets dict (boot script populates in PR 4)."""
        return self._kernel.G

    @property
    def L(self) -> dict[str, Any]:
        """Agent state dict. Direct read/write."""
        return self._kernel.L

    def snapshot(self, path: str) -> None:
        """Serialize L to file. Proxied to Kernel.snapshot().

        Args:
            path: Path to save the snapshot file.
        """
        self._kernel.snapshot(path)

    def restore(self, path: str) -> None:
        """Restore L from file. Proxied to Kernel.restore().

        Args:
            path: Path to the snapshot file.
        """
        self._kernel.restore(path)

    def step(self, tracer: TracerLike | None = None) -> StepResult:
        """Execute one frame.

        Flow:
            1. (first call only) kernel.ping(None, ns) — bootstrap initial Ping
            2. state_gate     — state gating against current Ping
            3. core.step      — call LLM, parse Pong
            4. action_gate    — action gating
            5. kernel.ping(pong, ns) — commits previous frame, returns next Ping
            6. return StepResult

        Frame N is committed inside the kernel.ping(pong_N, ns) call. The very
        first step() does not commit any frame (no prior pong to execute) — it
        only generates the initial Ping for the LLM.

        Args:
            tracer: Optional TracerLike instance.

        Returns:
            StepResult containing protocol_error (frame was not committed if non-None).
        """
        ns = {"globals": self._kernel.G, "locals": self._kernel.L}

        # Bootstrap: first call generates the initial Ping (pong=None).
        if self._ping is None:
            self._ping = self._kernel.ping(None, ns)

        self._check_state_gate(self._ping)

        frame_number = self._kernel.L["_frame"] + 1

        try:
            self._pong, prompt_tokens, completion_tokens = self._core.step(
                self._ping, tracer, frame_number,
            )
        except Exception as e:
            append_error(self._kernel.L, ErrorRecord(
                "protocol", str(e),
                self._kernel.L.get("_frame", 0), _time.time(),
            ))
            return StepResult(protocol_error=str(e))

        # Real-token bookkeeping (deferred to PR 5; kept for now)
        if prompt_tokens is not None:
            self._kernel.L["_actual_tokens_in"] = prompt_tokens
            budget_total = self._kernel.L.get("_budget_total", 0)
            if budget_total > 0:
                self._kernel.L["_context_pct"] = round(
                    prompt_tokens / budget_total * 100
                )
        if completion_tokens is not None:
            self._kernel.L["_actual_tokens_out"] = completion_tokens

        if self._check_action_gate(self._pong.action.operation) is None:
            self._pong = None  # do not execute next call
            return StepResult(protocol_error="Action gate blocked")

        # Single Kernel primitive: commits frame N, returns Ping for frame N+1
        if tracer:
            tracer.start(frame_number, "kernel.ping")
        self._ping = self._kernel.ping(self._pong, ns)
        if tracer:
            tracer.end(frame_number, "kernel.ping")

        return StepResult()

    def set_gate(self, gate_type: str, fn: Any) -> None:
        """Set a custom gate function, replacing all existing rules.

        Args:
            gate_type: "action" or "state".
            fn: callable(code_or_state: str) -> tuple[bool, str], returns (allowed, reason).

        Raises:
            ValueError: Raised when gate_type is not "action" or "state".
        """
        def _wrap(user_fn):
            def wrapper(value: str) -> str | None:
                allowed, reason = user_fn(value)
                return None if allowed else reason
            return wrapper

        if gate_type == "action":
            self._action_gate = ActionGate(mode="safe")
            self._action_gate.replace_rules([("custom", _wrap(fn))])
        elif gate_type == "state":
            self._state_gate = StateGate(mode="safe")
            self._state_gate.replace_rules([("custom", _wrap(fn))])
        else:
            raise ValueError(f"Unknown gate type: {gate_type!r}. Use 'action' or 'state'.")

    # ------------------------------------------------------------------ Gates

    def _check_state_gate(self, ping: Ping) -> None:
        """State gating before the LLM sees Ping. Blocks logged to _errors ring."""
        result = self._state_gate.check(ping.state.frame_stream)
        if not result.allowed:
            append_error(self._kernel.L, ErrorRecord(
                "protocol", f"State gate blocked: {result.reason}",
                self._kernel.L.get("_frame", 0), _time.time(),
            ))

    def _check_action_gate(self, action: str) -> str | None:
        """Action gating before exec. Returns None when blocked."""
        result = self._action_gate.check(action)
        if not result.allowed:
            append_error(self._kernel.L, ErrorRecord(
                "protocol", f"Action gate blocked: {result.reason}",
                self._kernel.L.get("_frame", 0), _time.time(),
            ))
            return None
        return action
