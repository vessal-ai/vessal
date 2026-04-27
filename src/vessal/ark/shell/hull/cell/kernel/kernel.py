"""kernel.py — Kernel main class: the Agent's execution kernel, holding the namespace and coordinating rendering and execution."""
# All Agent state (variables, functions, classes, instances, history, templates)
# lives in this dict.
#
# Public interface:
#   run(pong, tracer)              single-frame execution: exec → expect → frame → commit
#   prepare()                      per-frame init: update_signals → render → Ping
#   exec_operation(operation, frame_number, tracer) -> ExecResult
#                      execute operation code; does NOT increment _frame or commit to _frame_stream
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
from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.kernel.render import render as _render
from vessal.ark.shell.hull.cell.kernel.render.signals import BASE_SIGNALS
from vessal.ark.shell.hull.cell._tracer_protocol import TracerLike

logger = logging.getLogger(__name__)


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

    def __init__(self, snapshot_path: str | None = None, *, db_path: str | None = None) -> None:
        """Initialize Kernel.

        Args:
            snapshot_path: If provided, restore namespace from this file (continuing
                           a previous session). Otherwise, start a fresh namespace
                           with factory defaults.
            db_path: Optional path to a SQLite database for the frame_log. When set,
                     opens (or creates) the database and exposes a FrameLog via
                     self.frame_log. When None (default), self.frame_log is None and
                     no database is opened.
        """
        self.ns: dict = {}
        if snapshot_path:
            self.restore(snapshot_path)
        else:
            self._init_namespace()
        self.frame_log: FrameLog | None = None
        if db_path is not None:
            self.frame_log = FrameLog(open_db(db_path))

    def _init_namespace(self) -> None:
        """Inject system variable factory defaults into an empty namespace."""
        ns = self.ns
        # v3 system prompt and pinned observations
        ns["_system_prompt"] = ""                 # system prompt; Hull loads from SOUL.md
        ns["_frame_type"] = "work"               # frame type; Hull rewrites each frame (always "work")
        ns["_render_config"] = None              # RenderConfig written by Hull; uses default when None
        ns["_wake"] = ""                         # wake reason; written by Hull.run()

        # Hierarchical compaction config (must precede _frame_stream init)
        ns["_compaction_k"] = 16                  # hot-bucket depth; frames before shift
        ns["_compaction_n"] = 8                   # max cold-zone layers

        # Execution state
        ns["_frame"] = 0                          # last committed frame number; written by _commit_frame
        ns["_ns_meta"] = {}                       # variable usage tracking; rewritten by executor each frame
        ns["_frame_stream"] = FrameStream(
            k=ns["_compaction_k"],
            n=ns["_compaction_n"],
        )
        ns["_signal_outputs"] = []               # populated by update_signals() each frame

        # Context utilization (written by renderer on each frame render)
        ns["_context_pct"] = 0                    # context utilization percentage
        ns["_budget_total"] = 0                   # total render budget; written by renderer each frame

        # Context budget (used by renderer to calculate utilization)
        ns["_context_budget"] = 128000            # total context window (estimated tokens); Hull can override
        ns["_token_budget"] = 4096                # reserved for LLM reply; Hull writes via cell.set("_token_budget", cell.max_tokens)

        # Initial values of side-effect variables written by executor
        # (ensures fields exist when rendering the first frame)
        ns["_operation"] = ""                     # operation code executed in the previous frame
        ns["_stdout"] = ""                        # stdout from this frame
        ns["_error"] = None                       # exception from this frame
        ns["_errors"] = []                        # error history, list[ErrorRecord]; cap enforced by append_error() via _error_buffer_cap
        ns["_actual_tokens_in"] = None            # actual input token count returned by API (None if unavailable)
        ns["_actual_tokens_out"] = None           # actual output token count returned by API (None if unavailable)
        ns["_diff"] = ""                          # change summary for this frame (git-style +/- format)

        # Mirror variable (updated by Cell._commit_frame())
        ns["_verdict"] = None                     # verdict from the previous frame

        # Frame drop count
        ns["_dropped_frame_count"] = 0            # number of frames dropped in this render; written by renderer

        # Lifecycle variables
        ns["_sleeping"] = False                   # set to True when Agent sleeps → frame loop pauses
        ns["sleep"] = self.sleep
        ns["_next_wake"] = None                  # next wake time set by Agent (absolute timestamp)

        # Protected keys: all keys present at namespace init time.
        # executor restores any of these that agent code deletes.
        ns["_protected_keys"] = list(ns.keys())

    def exec_operation(
        self,
        operation: str,
        frame_number: int,
        tracer: TracerLike | None = None,
    ) -> ExecResult:
        """Execute operation code. Does not increment _frame or append _frame_log.

        Delegates to executor.execute(), passing frame_number.
        _frame incrementing and _frame_log construction are Cell's responsibility.

        Args:
            operation: Python code string to execute.
            frame_number: Current frame number; passed to executor for ErrorRecord/_ns_meta tracking.
                          Not written to ns["_frame"] — that is _commit_frame's responsibility.
            tracer: Optional TracerLike for recording execution time.

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
        tracer: TracerLike | None = None,
        frame_number: int | None = None,
    ) -> Verdict:
        """Evaluate prediction assertions on a shallow copy of the namespace. Does not modify the real namespace.

        Delegates to expect.evaluate_expect().

        Args:
            expect: Expect code string (containing assert statements).
            tracer: Optional TracerLike for recording evaluation time.
            frame_number: Current frame number for linecache registration. When None,
                falls back to ns["_frame"] + 1 (next frame).

        Returns:
            Verdict containing total/passed/failures fields.
        """
        frame = frame_number if frame_number is not None else self.ns.get("_frame", 0) + 1
        if tracer:
            tracer.start(frame, "kernel.eval_expect")
        result = evaluate_expect(expect, self.ns, frame)
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

        # TODO: future optimization — switch to explicit registry via
        # ns["_signal_sources"] when O(|ns|) full scan becomes measurable.
        # Current duck-typing scan is intentional design — see console/1-active/
        # 20260421-cell-architecture-review.md C16.
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
        """Serialize namespace to file. Pure bytes — no Skill awareness.

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
                f.write(body_bytes)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def restore(self, path: str) -> None:
        """Restore ns from file. Caller MUST have prepared sys.path / sys.modules.

        Args:
            path: File path written by snapshot().

        Side effects:
            Completely replaces self.ns.
        """
        import io as _io
        with open(path, "rb") as f:
            raw = f.read()
        buf = _io.BytesIO(raw)
        first = cloudpickle.load(buf)
        remaining = len(raw) - buf.tell()
        if remaining > 0:
            # Legacy layout: [cloudpickle(header_dict)][cloudpickle(ns)]
            # Discard header; load the actual namespace from remaining bytes.
            self.ns = cloudpickle.load(buf)
            # Write back in new format so subsequent restores use fast path.
            with open(path, "wb") as f:
                f.write(cloudpickle.dumps(self.ns))
        else:
            self.ns = first
        self._migrate_snapshot()

    def _find_creation_operation(self, key: str) -> str:
        """Search hot-zone frames in reverse for the most recent operation that created a variable.

        Args:
            key: Variable name.

        Returns:
            The operation string that created the variable, or empty string if not found.
        """
        fs = self.ns.get("_frame_stream")
        if fs is None:
            return ""
        return fs.find_creation(key) or ""

    def _migrate_snapshot(self) -> None:
        """Clear per-run state whose schema version doesn't match.

        For v6→v7, the flat _frame_log is dropped and _frame_stream is reinitialized.
        No backfill is attempted.
        """
        # Drop stale _frame_log if present (v6 and earlier)
        self.ns.pop("_frame_log", None)

        fs = self.ns.get("_frame_stream")
        if fs is None:
            self.ns["_frame_stream"] = FrameStream(
                k=self.ns.get("_compaction_k", 16),
                n=self.ns.get("_compaction_n", 8),
            )
        else:
            try:
                d = fs.to_dict()
                if d.get("schema_version") != FRAME_SCHEMA_VERSION:
                    raise ValueError("schema mismatch")
            except Exception:
                self.ns["_frame_stream"] = FrameStream(
                    k=self.ns.get("_compaction_k", 16),
                    n=self.ns.get("_compaction_n", 8),
                )
                logger.info("Cleared incompatible frame_stream (schema mismatch)")
        self.ns["sleep"] = self.sleep

    def sleep(self) -> None:
        """Mark agent as sleeping. Pauses the frame loop until Shell wakes it."""
        self.ns["_sleeping"] = True

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

    def step(
        self,
        pong: Pong,
        tracer: TracerLike | None = None,
        ping: "Ping | None" = None,
        frame_number: int | None = None,
    ) -> None:
        """Single-frame execution: exec → expect → observation → frame → commit.

        Receives a Pong and completes all Kernel-side work for this frame:
        executes the operation, evaluates predictions, constructs Observation and
        the frame dict, and commits the frame.
        No longer pre-renders the next Ping — signal collection and rendering are
        done by Cell at the start of the next frame via prepare().

        Args:
            pong:         Control signal from the reasoner, containing action.operation / action.expect.
            tracer:       Optional TracerLike, forwarded to exec_operation and eval_expect.
            ping:         Perceptual input seen by the model for this frame (optional;
                          used to write into FrameRecord v6).
            frame_number: Frame sequence number. When None, computed from ns["_frame"] + 1
                          (backward-compatibility guard for callers that do not pass it).
        """
        if frame_number is None:
            frame_number = self.ns["_frame"] + 1

        exec_result = self.exec_operation(pong.action.operation, frame_number, tracer)

        if exec_result.error is None and pong.action.expect.strip():
            verdict = self.eval_expect(pong.action.expect, tracer, frame_number)
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
        """Construct FrameRecord, commit to _frame_stream, update verdict mirror.

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
        fs = ns.get("_frame_stream")
        if fs is None:
            fs = FrameStream(k=ns.get("_compaction_k", 16), n=ns.get("_compaction_n", 8))
            ns["_frame_stream"] = fs
        fs.commit_frame(record.to_dict())
        ns["_frame"] = frame_number
        ns["_verdict"] = observation.verdict
        if self.frame_log is not None:
            self.frame_log.write_frame(self._build_frame_write_spec(record))

    def _build_frame_write_spec(self, record: FrameRecord) -> "FrameWriteSpec":
        """Translate a FrameRecord into a FrameWriteSpec for the frame_log writer.

        Args:
            record: Completed FrameRecord from this frame.

        Returns:
            FrameWriteSpec ready to pass to FrameLog.write_frame().
        """
        import json as _json
        from vessal.ark.shell.hull.cell.kernel.frame_log.types import ErrorOnSource, FrameWriteSpec

        obs = record.observation
        operation_error = (
            ErrorOnSource("operation", None, obs.error)
            if obs.error is not None
            else None
        )
        verdict_value: str | None = None
        if obs.verdict is not None:
            verdict_value = _json.dumps(obs.verdict.to_dict())
        diff_json = obs.diff
        return FrameWriteSpec(
            n=record.number,
            pong_think=record.pong.think,
            pong_operation=record.pong.action.operation,
            pong_expect=record.pong.action.expect,
            obs_stdout=obs.stdout or "",
            obs_stderr="",
            obs_diff_json=diff_json,
            operation_error=operation_error,
            verdict_value=verdict_value,
            verdict_error=None,
            signals=[],
        )
