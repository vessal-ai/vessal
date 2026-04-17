"""kernel.py — Kernel main class: the Agent's execution kernel, holding the namespace and coordinating rendering and execution."""
# All Agent state (variables, functions, classes, instances, history, templates)
# lives in this dict.
#
# Public interface:
#   run(pong, tracer)              single-frame execution: exec → expect → frame → commit
#   prepare()                      per-frame init: update_signals → render → Ping
#   exec_operation(operation, frame_number, tracer) -> ExecResult
#                      execute operation code; does NOT increment _frame or append _frame_log
#   eval_expect(expect, tracer)  -> Verdict
#                      evaluate prediction assertions on a shallow copy of the namespace;
#                      does NOT modify the real namespace
#   render()           render current state only, without executing code
#   snapshot(path)     serialize namespace to a file
#   restore(path)      restore namespace from a file
#   ns                 namespace dict, fully exposed, readable/writable directly
#
# Initialization: decides where to start (fresh namespace or snapshot restore),
# and initializes all system variables.
# Kernel has no state outside of ns — no Gate, no counters, no config attributes.

from __future__ import annotations

import cloudpickle
import logging
from datetime import datetime, timezone

from vessal.ark.shell.hull.cell.kernel.executor import ExecResult, execute
from vessal.ark.shell.hull.cell.kernel.expect import evaluate_expect
from vessal.ark.shell.hull.cell.protocol import (
    FRAME_SCHEMA_VERSION,
    FrameRecord,
    Observation,
    Ping,
    Pong,
    State,
    Verdict,
)
from vessal.ark.shell.hull.cell.kernel.render import render as _render
from vessal.ark.shell.hull.cell.kernel.render.signals import BASE_SIGNALS
from vessal.ark.util.logging import Tracer

logger = logging.getLogger(__name__)

# Maximum number of frames retained in _frame_log. Oldest frames are trimmed when exceeded.
_FRAME_LOG_MAX = 200


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string with microsecond precision and Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _picklable(obj) -> bool:
    """Check whether an object can be serialized by cloudpickle.

    Args:
        obj: Any Python object.

    Returns:
        True if serializable, False if not.
    """
    try:
        cloudpickle.dumps(obj)
        return True
    except Exception:
        return False


class Kernel:
    """Agent execution kernel.

    Core equation: exec_result = kernel.exec_operation(operation, frame_number)
    operation is a Python code string; exec_result contains stdout/diff/error.

    ns is fully exposed; external code may read/write it directly. Keys starting
    with _ are system variables; modify them at your own risk.
    Kernel itself is stateless — it is simply the executor and renderer of the namespace.

    Construction and appending of _frame_log is Cell's responsibility (Phase 3 implementation).
    """

    def __init__(self, snapshot_path: str | None = None) -> None:
        """Initialize Kernel.

        Args:
            snapshot_path: If provided, restore namespace from this file (continuing
                           a previous session). Otherwise, start a fresh namespace
                           with factory defaults.
        """
        self.ns: dict = {}
        if snapshot_path:
            self.restore(snapshot_path)
        else:
            self._init_namespace()

    def _init_namespace(self) -> None:
        """Inject system variable factory defaults into an empty namespace."""
        ns = self.ns
        # v3 system prompt and pinned observations
        ns["_system_prompt"] = ""                 # system prompt; Hull loads from SOUL.md
        ns["_frame_type"] = "work"               # frame type; Hull rewrites each frame (always "work")
        ns["_render_config"] = None              # RenderConfig written by Hull; uses default when None
        ns["_wake"] = ""                         # wake reason; written by Hull.run()

        # Execution state
        ns["_frame"] = 0                          # current frame number; set by executor before execution
        ns["_ns_meta"] = {}                       # variable usage tracking; rewritten by executor each frame
        ns["_frame_log"] = []                     # structured frame log; appended by Cell._commit_frame() each frame
        ns["_signal_outputs"] = []               # populated by update_signals() each frame

        # Context utilization (written by renderer on each frame render)
        ns["_context_pct"] = 0                    # context utilization percentage
        ns["_budget_total"] = 0                   # total render budget; written by renderer each frame

        # Context budget (used by renderer to calculate utilization)
        ns["_context_budget"] = 128000            # total context window (estimated tokens); Hull can override
        ns["_max_tokens"] = 4096                  # reserved for LLM reply; Cell will override with actual value

        # Initial values of side-effect variables written by executor
        # (ensures fields exist when rendering the first frame)
        ns["_operation"] = ""                     # operation code executed in the previous frame
        ns["_stdout"] = ""                        # stdout from this frame
        ns["_error"] = None                       # exception from this frame
        ns["_errors"] = []                        # error history, list[ErrorRecord], capped at 50
        ns["_actual_tokens_in"] = None            # actual input token count returned by API (None if unavailable)
        ns["_actual_tokens_out"] = None           # actual output token count returned by API (None if unavailable)
        ns["_diff"] = ""                          # change summary for this frame (git-style +/- format)

        # Mirror variable (updated by Cell._commit_frame())
        ns["_verdict"] = None                     # verdict from the previous frame

        # Hierarchical compaction config
        ns["_compaction_k"] = 16                  # hot-bucket depth; frames before shift
        ns["_compaction_n"] = 8                   # max cold-zone layers

        # Frame drop count
        ns["_dropped_frame_count"] = 0            # number of frames dropped in this render; written by renderer

        # Lifecycle variables
        ns["_sleeping"] = False                   # set to True when Agent sleeps → frame loop pauses

        def _sleep_fn():
            ns["_sleeping"] = True

        ns["sleep"] = _sleep_fn
        ns["_next_wake"] = None                  # next wake time set by Agent (absolute timestamp)

        # Protected keys: all keys present at namespace init time.
        # executor restores any of these that agent code deletes.
        ns["_protected_keys"] = list(ns.keys())

    def exec_operation(
        self,
        operation: str,
        frame_number: int,
        tracer: Tracer | None = None,
    ) -> ExecResult:
        """Execute operation code. Does not increment _frame or append _frame_log.

        Delegates to executor.execute(), passing frame_number.
        _frame incrementing and _frame_log construction are Cell's responsibility.

        Args:
            operation: Python code string to execute.
            frame_number: Current frame number; written to ns["_frame"] and passed to _ns_meta.
            tracer: Optional Tracer for recording execution time.

        Returns:
            ExecResult containing stdout, diff, and error fields.
        """
        if tracer:
            tracer.start(frame_number, "executor.execute")
        result = execute(operation, self.ns, frame_number)
        if tracer:
            tracer.end(frame_number, "executor.execute")
        return result

    def eval_expect(
        self,
        expect: str,
        tracer: Tracer | None = None,
    ) -> Verdict:
        """Evaluate prediction assertions on a shallow copy of the namespace. Does not modify the real namespace.

        Delegates to expect.evaluate_expect().

        Args:
            expect: Expect code string (containing assert statements).
            tracer: Optional Tracer for recording evaluation time.

        Returns:
            Verdict containing total/passed/failures fields.
        """
        frame = self.ns.get("_frame", 0)
        if tracer:
            tracer.start(frame, "kernel.eval_expect")
        result = evaluate_expect(expect, self.ns)
        if tracer:
            tracer.end(frame, "kernel.eval_expect")
        return result

    def update_signals(self) -> None:
        """Collect base signals + duck-typing signal sources into ns["_signal_outputs"].

        Signal format is uniformly a (title, body) tuple.

        1. Iterate over BASE_SIGNALS (list of (name, fn(ns) -> str)); include fn result
           in outputs when it returns a non-empty str.
        2. Iterate over all objects in the namespace that have a _signal method
           (duck-typing); call _signal() and collect returned (title, body) tuples.
           Any object only needs to implement the _signal protocol; no inheritance
           from SkillBase is required.
        3. Signal errors are caught and logged; they never interrupt the agent.

        Side effects:
            Writes to ns["_signal_outputs"] (list[tuple[str, str]]).
        """
        outputs: list[tuple[str, str]] = []

        # Base signals (system-level, always present)
        for signal_name, fn in BASE_SIGNALS:
            try:
                result = fn(self.ns)
                if isinstance(result, str) and result.strip():
                    outputs.append((signal_name, result))
            except Exception as e:
                fn_name = getattr(fn, "__name__", repr(fn))
                logger.warning("Base signal '%s' failed: %s", fn_name, e)

        # Duck-typing signal scan: any object in namespace with a _signal method
        for obj in list(self.ns.values()):
            if hasattr(obj, "_signal") and callable(getattr(obj, "_signal")):
                try:
                    result = obj._signal()
                    if isinstance(result, tuple) and len(result) == 2:
                        title, body = result
                        if isinstance(body, str) and body.strip():
                            outputs.append((str(title), body))
                except Exception as e:
                    obj_name = getattr(obj, "name", repr(obj))
                    logger.warning("Signal source '%s' failed: %s", obj_name, e)

        self.ns["_signal_outputs"] = outputs

    def render(self) -> Ping:
        """Render current namespace state only, without executing code.

        Returns:
            Ping(system_prompt, state)
        """
        return _render(self.ns, self.ns.get("_render_config"))

    def snapshot(self, path: str) -> None:
        """Serialize the namespace to a file.

        Uses cloudpickle, supporting functions, classes, lambdas, closures, and
        all other callables. The file is written in two parts: first _loaded_skills
        metadata (header), then the full ns (body). The header is used at restore
        time to repair sys.path before deserialization, ensuring __import__ succeeds.
        Module objects are recorded by cloudpickle under their names and re-imported
        from disk at restore time.
        Atomic write: first writes to a temp file; replaces the target only on full
        success; the original file is unaffected on failure.

        Fallback strategy: if full serialization fails (e.g., C-extension objects
        like PIL Image), unpicklable keys are filtered out and the rest is saved;
        no exception is raised.

        Args:
            path: Serialization file path.

        Side effects:
            Writes to file. On full failure, writes a partial namespace.
        """
        import os
        import tempfile
        path = str(path)

        header_bytes = cloudpickle.dumps(self.ns.get("_loaded_skills", {}))
        try:
            body_bytes = cloudpickle.dumps(self.ns)
        except Exception as e:
            picklable = {k: v for k, v in self.ns.items() if _picklable(v)}
            dropped = [k for k in self.ns if k not in picklable]
            logger.debug(
                "full namespace serialization failed (%s), "
                "dropping %d unpicklable keys: %s",
                e, len(dropped), dropped[:10],
            )
            partial = picklable
            # Record dropped keys and their creation context for reconstruction
            partial["_dropped_keys"] = dropped
            partial["_dropped_keys_context"] = {
                k: self._find_creation_operation(k)
                for k in dropped
            }
            body_bytes = cloudpickle.dumps(partial)

        dir_name = os.path.dirname(path) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(header_bytes)
                f.write(body_bytes)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def restore(self, path: str) -> None:
        """Restore namespace from a file, completely replacing the current state.

        Reads the header (Skill metadata) first, repairs sys.path and clears
        sys.modules cache, then reads the body (full ns). cloudpickle deserializes
        the body with __import__ for modules, by which point sys.path is ready.

        Args:
            path: File path written by snapshot().

        Side effects:
            Completely replaces self.ns. Modifies sys.path and sys.modules.
        """
        import sys as _sys
        with open(path, "rb") as f:
            loaded_skills = cloudpickle.load(f)
            for name, info in loaded_skills.items():
                parent_path = info.get("parent_path", "")
                if parent_path and parent_path not in _sys.path:
                    _sys.path.insert(0, parent_path)
                # Clear sys.modules cache to ensure latest code is loaded from disk
                stale = [k for k in _sys.modules
                         if k == name or k.startswith(name + ".")]
                for k in stale:
                    del _sys.modules[k]
            self.ns = cloudpickle.load(f)
        self._migrate_frame_log()

    def _find_creation_operation(self, key: str) -> str:
        """Search frame_log in reverse for the most recent operation that created a variable.

        frame_log may be empty (first snapshot or cleared by schema migration),
        in which case an empty string is returned.

        Args:
            key: Variable name.

        Returns:
            The operation string that created the variable, or empty string if not found.
        """
        for frame in reversed(self.ns.get("_frame_log", [])):
            diff = frame.get("observation", {}).get("diff", "")
            if f"+ {key}" in diff:
                return frame.get("pong", {}).get("action", {}).get("operation", "")
        return ""

    def _migrate_frame_log(self) -> None:
        """Check _frame_log schema version; clear it if incompatible."""
        frame_log = self.ns.get("_frame_log", [])
        if not frame_log:
            return
        first = frame_log[0]
        if isinstance(first, dict) and first.get("schema_version") == FRAME_SCHEMA_VERSION:
            return
        # Old format incompatible, clear
        self.ns["_frame_log"] = []
        logger.info("Cleared incompatible frame_log (schema < %d)", FRAME_SCHEMA_VERSION)

    # ------------------------------------------------------------------ High-level interface

    def prepare(self) -> Ping:
        """Per-frame init: update signals, render and return Ping.

        Cell calls this method at the start of each step() to ensure Ping
        always contains the latest signals.

        Returns:
            Rendered Ping.
        """
        self.update_signals()
        return self.render()

    def run(
        self,
        pong: Pong,
        tracer: Tracer | None = None,
        ping: "Ping | None" = None,
    ) -> None:
        """Single-frame execution: exec → expect → observation → frame → commit.

        Receives a Pong and completes all Kernel-side work for this frame:
        executes the operation, evaluates predictions, constructs Observation and
        the frame dict, and commits the frame.
        No longer pre-renders the next Ping — signal collection and rendering are
        done by Cell at the start of the next frame via prepare().

        Args:
            pong:   Control signal from the reasoner, containing action.operation / action.expect.
            tracer: Optional Tracer, forwarded to exec_operation and eval_expect.
            ping:   Perceptual input seen by the model for this frame (optional;
                    used to write into FrameRecord v6).
        """
        frame_number = self.ns["_frame"] + 1

        exec_result = self.exec_operation(pong.action.operation, frame_number, tracer)

        if exec_result.error is None and pong.action.expect.strip():
            verdict = self.eval_expect(pong.action.expect, tracer)
        else:
            verdict = None

        observation = Observation(
            stdout=exec_result.stdout,
            diff=exec_result.diff,
            error=exec_result.error,
            verdict=verdict,
        )

        self._commit_frame(pong, observation, frame_number, ping=ping)

    def _commit_frame(
        self,
        pong: Pong,
        observation: Observation,
        frame_number: int,
        ping: "Ping | None" = None,
    ) -> None:
        """Construct FrameRecord, append to _frame_log, update verdict mirror.

        Args:
            pong:         Control signal from the reasoner.
            observation:  Execution result observation for this frame.
            frame_number: Frame sequence number.
            ping:         Perceptual input seen by the model for this frame
                          (optional; uses empty Ping when absent).
        """
        ns = self.ns
        effective_ping = ping if ping is not None else Ping(
            system_prompt="", state=State(frame_stream="", signals="")
        )
        record = FrameRecord(
            number=frame_number,
            ping=effective_ping,
            pong=pong,
            observation=observation,
        )
        frame_log = ns.setdefault("_frame_log", [])
        frame_log.append(record.to_dict())
        if len(frame_log) > _FRAME_LOG_MAX:
            del frame_log[: len(frame_log) - _FRAME_LOG_MAX]
        ns["_verdict"] = observation.verdict
