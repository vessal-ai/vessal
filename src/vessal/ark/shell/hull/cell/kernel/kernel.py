"""kernel.py — Kernel main class: the Agent's execution kernel, holding G (preset assets) and L (Agent state)."""
# All Agent state (variables, functions, classes, instances, history, templates)
# lives in L (Agent state dict). G holds preset assets (Skills, boot globals).
#
# Public interface:
#   ping(pong, namespace)          single-frame primitive (spec §1.2): exec → eval → signals → commit → render
#   snapshot(path)                 serialize L to a file
#   restore(path)                  restore L from a file
#   L                              Agent state dict, fully exposed, readable/writable directly
#   G                              preset assets dict (Skills, boot globals); read-only by convention
#
# Legacy multi-entry surface (prepare/step/exec_operation/eval_expect/update_signals/render/_commit_frame)
# is inlined into ping() and deleted in PR 2 Task 7.
#
# Initialization: decides where to start (fresh L or snapshot restore),
# and initializes all system variables.
# Kernel has no state outside of G and L — no Gate, no counters, no config attributes.

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
from vessal.ark.shell.hull.cell.kernel import source_cache
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.kernel.lenient import LenientUnpickler
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

    L is fully exposed; external code may read/write it directly. Keys starting
    with _ are system variables; modify them at your own risk.
    Kernel itself is stateless — it is simply the executor and renderer of L.

    Construction and appending of _frame_log is Cell's responsibility (Phase 3 implementation).
    """

    def __init__(self, snapshot_path: str | None = None, *, db_path: str | None = None) -> None:
        """Initialize Kernel.

        Args:
            snapshot_path: If provided, restore L from this file (continuing a
                           previous session). G is rebuilt fresh by __init__
                           (boot script comes in PR 4).
            db_path: Optional path to a SQLite database for the frame_log.
        """
        self.G: dict = {}
        self.L: dict = {}
        if snapshot_path:
            self.restore(snapshot_path)
        else:
            self._init_L()
        self.frame_log: FrameLog | None = None
        if db_path is not None:
            conn = open_db(db_path)
            source_cache.reload_from_db(conn)
            self.frame_log = FrameLog(conn)
        self._last_ping: Ping | None = None

    def ping(self, pong: "Pong | None", namespace: dict) -> Ping:
        """Single Kernel primitive (spec §1.2). Runs five steps internally:

          ① archive pong (deferred to _commit_frame inside this call)
          ② exec(pong.operation, G, L) → L["observation"]
          ③ eval(pong.expect, G, copy(L)) → L["verdict"]
          ④ signal_scan → L["_signal_outputs"]   (PR 3 will rename to L["signals"])
          ⑤ render Ping structure

        pong=None (first call after boot/restart) skips ②③ — observation/verdict
        are not written. ④⑤ always run.

        Args:
            pong: LLM's previous frame Pong, or None on the very first call.
            namespace: {"globals": G, "locals": L}. Both dicts mutated in-place.

        Returns:
            Ping rendered from current L state. Caller passes this to LLM
            to obtain the next pong.
        """
        G = namespace["globals"]
        L = namespace["locals"]
        # Sanity check: G/L must be the Kernel's own dicts (in-place mutation contract).
        assert G is self.G and L is self.L, \
            "ping() namespace must reference Kernel.G and Kernel.L (in-place)"

        if pong is not None:
            frame_n = L["_frame"] + 1
            # ② exec
            exec_result = execute(pong.action.operation, G, L, frame_n)
            L["observation"] = Observation(
                stdout=exec_result.stdout,
                diff=exec_result.diff,
                error=exec_result.error,
                verdict=None,
            )
            # ③ eval
            if exec_result.error is None and pong.action.expect.strip():
                L["verdict"] = evaluate_expect(
                    pong.action.expect, G, L, frame_n,
                )
            else:
                L["verdict"] = None
            # ④ signal_scan
            self.update_signals()
            # commit frame N (uses self._last_ping as the FrameRecord.ping field)
            observation_for_record = Observation(
                stdout=L["observation"].stdout,
                diff=L["observation"].diff,
                error=L["observation"].error,
                verdict=L["verdict"],   # FrameRecord still nests verdict inside observation in v7
            )
            self._commit_frame(pong, observation_for_record, frame_n, ping=self._last_ping)
        else:
            # First call after boot: signal_scan only (no exec/eval, no commit)
            self.update_signals()

        # ⑤ render
        self._last_ping = self.render()
        return self._last_ping

    def _init_L(self) -> None:
        """Inject Agent-state factory defaults into an empty L."""
        L = self.L
        # v3 system prompt and pinned observations
        L["_system_prompt"] = ""
        L["_frame_type"] = "work"
        L["_render_config"] = None
        L["_wake"] = ""

        # Hierarchical compaction config (must precede _frame_stream init)
        L["_compaction_k"] = 16
        L["_compaction_n"] = 8

        # Execution state
        L["_frame"] = 0
        L["_ns_meta"] = {}
        L["_frame_stream"] = FrameStream(
            k=L["_compaction_k"],
            n=L["_compaction_n"],
        )
        L["_signal_outputs"] = []

        # Context utilization (written by renderer on each frame render)
        L["_context_pct"] = 0
        L["_budget_total"] = 0

        # Context budget (used by renderer to calculate utilization)
        L["_context_budget"] = 128000
        L["_token_budget"] = 4096

        # Initial values of side-effect variables written by executor
        # (ensures fields exist when rendering the first frame)
        L["_operation"] = ""
        L["_stdout"] = ""
        L["_error"] = None
        L["_errors"] = []
        L["_actual_tokens_in"] = None
        L["_actual_tokens_out"] = None
        L["_diff"] = ""

        # Mirror variable (updated by Cell._commit_frame())
        L["_verdict"] = None

        # Frame drop count
        L["_dropped_frame_count"] = 0

        # Lifecycle variables
        L["_sleeping"] = False
        L["sleep"] = self.sleep
        L["_next_wake"] = None

        # Protected keys: all keys present at L init time.
        # executor restores any of these that agent code deletes.
        L["_protected_keys"] = list(L.keys())

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
                          Not written to L["_frame"] — that is _commit_frame's responsibility.
            tracer: Optional TracerLike for recording execution time.

        Returns:
            ExecResult containing stdout, diff, and error fields.
        """
        if tracer:
            tracer.start(frame_number, "executor.execute")
        result = execute(operation, self.G, self.L, frame_number)
        if tracer:
            tracer.end(frame_number, "executor.execute")
        return result

    def eval_expect(
        self,
        expect: str,
        tracer: TracerLike | None = None,
        frame_number: int | None = None,
    ) -> Verdict:
        """Evaluate prediction assertions on a shallow copy of L. Does not modify the real L.

        Delegates to expect.evaluate_expect().

        Args:
            expect: Expect code string (containing assert statements).
            tracer: Optional TracerLike for recording evaluation time.
            frame_number: Current frame number for linecache registration. When None,
                falls back to L["_frame"] + 1 (next frame).

        Returns:
            Verdict containing total/passed/failures fields.
        """
        frame = frame_number if frame_number is not None else self.L.get("_frame", 0) + 1
        if tracer:
            tracer.start(frame, "kernel.eval_expect")
        result = evaluate_expect(expect, self.G, self.L, frame)
        if tracer:
            tracer.end(frame, "kernel.eval_expect")
        return result

    def update_signals(self) -> None:
        """Collect base signals + duck-typing signal sources into L["_signal_outputs"].

        Signal format is uniformly a (title, body) tuple.

        1. Iterate over BASE_SIGNALS (list of (name, fn(L) -> str)); include fn result
           in outputs when it returns a non-empty str.
        2. Iterate over all objects in L that have a _signal method
           (duck-typing); call _signal() and collect returned (title, body) tuples.
           Any object only needs to implement the _signal protocol; no inheritance
           from SkillBase is required.
        3. Signal errors are caught and logged; they never interrupt the agent.

        Side effects:
            Writes to L["_signal_outputs"] (list[tuple[str, str]]).
        """
        outputs: list[tuple[str, str]] = []

        # Base signals (system-level, always present)
        for signal_name, fn in BASE_SIGNALS:
            try:
                result = fn(self.L)
                if isinstance(result, str) and result.strip():
                    outputs.append((signal_name, result))
            except Exception as e:
                fn_name = getattr(fn, "__name__", repr(fn))
                logger.warning("Base signal '%s' failed: %s", fn_name, e)

        # TODO: future optimization — switch to explicit registry via
        # L["_signal_sources"] when O(|L|) full scan becomes measurable.
        # Current duck-typing scan is intentional design — see console/1-active/
        # 20260421-cell-architecture-review.md C16.
        # Duck-typing signal scan: any object in L with a _signal method
        for obj in list(self.L.values()):
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

        self.L["_signal_outputs"] = outputs

    def render(self) -> Ping:
        """Render current L state only, without executing code.

        Returns:
            Ping(system_prompt, state)
        """
        return _render(self.L, self.L.get("_render_config"))

    def snapshot(self, path: str) -> None:
        """Serialize L to file. Pure bytes — no Skill awareness. G is NOT serialized.

        Atomic write: first writes to a temp file; replaces the target only on full
        success; the original file is unaffected on failure.

        Fallback strategy: if full serialization of L fails (e.g., C-extension
        objects), unpicklable keys are filtered out and the rest is saved.

        Args:
            path: Serialization file path.
        """
        import os
        import tempfile
        path = str(path)

        try:
            body_bytes = cloudpickle.dumps(self.L)
        except Exception as e:
            picklable = {k: v for k, v in self.L.items() if _picklable(v)}
            dropped = [k for k in self.L if k not in picklable]
            logger.debug(
                "L serialization failed (%s); dropping %d unpicklable keys: %s",
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
        """Restore L from file. Caller MUST have prepared sys.path / sys.modules.

        Args:
            path: File path written by snapshot().

        Side effects:
            Completely replaces self.L.
        """
        import io as _io
        with open(path, "rb") as f:
            raw = f.read()
        from .lenient import LenientUnpickler
        buf = _io.BytesIO(raw)
        first = LenientUnpickler(buf).load()
        remaining = len(raw) - buf.tell()
        if remaining > 0:
            # Legacy layout: [cloudpickle(header_dict)][cloudpickle(L)]
            # Discard header; load the actual L from remaining bytes.
            self.L = LenientUnpickler(buf).load()
            # Write back in new format so subsequent restores use fast path.
            with open(path, "wb") as f:
                f.write(cloudpickle.dumps(self.L))
        else:
            self.L = first
        self._migrate_snapshot()

    def _find_creation_operation(self, key: str) -> str:
        """Search hot-zone frames in reverse for the most recent operation that created a variable.

        Args:
            key: Variable name.

        Returns:
            The operation string that created the variable, or empty string if not found.
        """
        fs = self.L.get("_frame_stream")
        if fs is None:
            return ""
        return fs.find_creation(key) or ""

    def _migrate_snapshot(self) -> None:
        """Clear per-run state whose schema version doesn't match.

        For v6→v7, the flat _frame_log is dropped and _frame_stream is reinitialized.
        No backfill is attempted.
        """
        # Drop stale _frame_log if present (v6 and earlier)
        self.L.pop("_frame_log", None)

        fs = self.L.get("_frame_stream")
        if fs is None:
            self.L["_frame_stream"] = FrameStream(
                k=self.L.get("_compaction_k", 16),
                n=self.L.get("_compaction_n", 8),
            )
        else:
            try:
                d = fs.to_dict()
                if d.get("schema_version") != FRAME_SCHEMA_VERSION:
                    raise ValueError("schema mismatch")
            except Exception:
                self.L["_frame_stream"] = FrameStream(
                    k=self.L.get("_compaction_k", 16),
                    n=self.L.get("_compaction_n", 8),
                )
                logger.info("Cleared incompatible frame_stream (schema mismatch)")
        self.L["sleep"] = self.sleep

    def sleep(self) -> None:
        """Mark agent as sleeping. Pauses the frame loop until Shell wakes it."""
        self.L["_sleeping"] = True

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
            frame_number: Frame sequence number. When None, computed from L["_frame"] + 1
                          (backward-compatibility guard for callers that do not pass it).
        """
        if frame_number is None:
            frame_number = self.L["_frame"] + 1

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
        L = self.L
        effective_ping = ping if ping is not None else Ping(
            system_prompt="", state=State(frame_stream="", signals="")
        )
        record = FrameRecord(
            number=frame_number,
            ping=effective_ping,
            pong=pong,
            observation=observation,
        )
        fs = L.get("_frame_stream")
        if fs is None:
            fs = FrameStream(k=L.get("_compaction_k", 16), n=L.get("_compaction_n", 8))
            L["_frame_stream"] = fs
        fs.commit_frame(record.to_dict())
        L["_frame"] = frame_number
        L["_verdict"] = observation.verdict
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
