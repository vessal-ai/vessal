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
# Initialization: decides where to start (fresh L or snapshot restore),
# and initializes all system variables.
# Kernel has no state outside of G and L — no Gate, no counters, no config attributes.

from __future__ import annotations

import cloudpickle
import logging

from vessal.ark.shell.hull.cell.kernel.executor import execute
from vessal.ark.shell.hull.cell.kernel.expect import evaluate_expect
from vessal.ark.shell.hull.cell.protocol import (
    FRAME_SCHEMA_VERSION,
    FrameRecord,
    Observation,
    Ping,
    Pong,
    State,
)
from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel import source_cache
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.kernel.lenient import LenientUnpickler
from vessal.ark.shell.hull.cell.kernel.render import render as _render

logger = logging.getLogger(__name__)


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

    Public entry point: kernel.ping(pong, namespace) — single-frame primitive.
    operation is executed as Python code; result contains stdout/diff/error.

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
        # SystemSkill is always present in G; restored sessions also get a fresh instance.
        from vessal.skills.system import SystemSkill
        self.G["_system"] = SystemSkill(self)
        self._signal_errors_this_frame: list[tuple[str, str, Exception]] = []
        self.frame_log: FrameLog | None = None
        if db_path is not None:
            conn = open_db(db_path)
            source_cache.reload_from_db(conn)
            self.frame_log = FrameLog(conn)
        self._last_ping: Ping | None = None

    def ping(self, pong: "Pong | None", namespace: dict) -> Ping:
        """Single Kernel primitive (spec §1.2). Runs five steps internally:

          ① archive pong (deferred to _commit inside this call)
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
            self._signal_scan()
            # commit frame N (uses self._last_ping as the FrameRecord.ping field)
            L["observation"] = Observation(
                stdout=L["observation"].stdout,
                diff=L["observation"].diff,
                error=L["observation"].error,
                verdict=L["verdict"],   # FrameRecord still nests verdict inside observation in v7
            )
            self._commit(pong, L["observation"], frame_n, ping_for_record=self._last_ping)
        else:
            # First call after boot: signal_scan only (no exec/eval, no commit)
            self._signal_scan()

        # ⑤ render
        self._last_ping = _render(self.L, self.L.get("_render_config"))
        return self._last_ping

    def _init_L(self) -> None:
        """Inject Agent-state factory defaults into an empty L."""
        L = self.L
        # v3 system prompt and pinned observations
        L["_system_prompt"] = ""
        L["_frame_type"] = "work"
        L["_render_config"] = None

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
        L["signals"] = {}

        # Context utilization (written by renderer on each frame render)
        L["_context_pct"] = 0
        L["_budget_total"] = 0

        # Context budget (used by renderer to calculate utilization)
        L["_context_budget"] = 128000
        L["_token_budget"] = 4096

        # Errors ring buffer
        L["_errors"] = []
        L["_error_buffer_cap"] = 50

        # Frame drop count
        L["_dropped_frame_count"] = 0

        # Lifecycle variables
        L["_sleeping"] = False
        L["sleep"] = self.sleep
        L["_next_wake"] = None

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
        self.L.setdefault("signals", {})

    def sleep(self) -> None:
        """Mark agent as sleeping. Pauses the frame loop until Shell wakes it."""
        self.L["_sleeping"] = True

    # ------------------------------------------------------------------ Private helpers

    def _signal_scan(self) -> None:
        """Spec §6: scan G ∪ L for BaseSkill instances; aggregate to L["signals"].

        Iteration order: G first, L second. When the same var_name exists in both,
        L wins (LEGB shadowing) — the G entry is dropped.

        Aggregation key: (class_name, var_name, scope).
        On signal_update exception, the entry's payload is {"_error_id": <id>} and
        the error is logged. Other Skills' scans are unaffected.
        """
        from vessal.skills._base import BaseSkill
        self._signal_errors_this_frame = []
        signals: dict[tuple[str, str, str], dict] = {}
        l_var_names = {k for k, v in self.L.items() if isinstance(v, BaseSkill)}

        for var_name, value in self.G.items():
            if not isinstance(value, BaseSkill):
                continue
            if var_name in l_var_names:
                continue  # shadowed by L
            self._scan_one(signals, value, var_name, "G")

        for var_name, value in self.L.items():
            if not isinstance(value, BaseSkill):
                continue
            self._scan_one(signals, value, var_name, "L")

        self.L["signals"] = signals

    def _scan_one(
        self,
        signals: dict,
        skill: "BaseSkill",
        var_name: str,
        scope: str,
    ) -> None:
        cls_name = type(skill).__name__
        try:
            skill.signal_update()
        except Exception as exc:
            logger.warning(
                "signal_update raised on %s (%s@%s): %s",
                cls_name, var_name, scope, exc,
            )
            error_id = self._record_signal_error(cls_name, var_name, exc)
            signals[(cls_name, var_name, scope)] = {"_error_id": error_id}
            return

        payload = skill.signal
        if not isinstance(payload, dict):
            logger.warning(
                "%s.signal is %s, expected dict — coercing to empty",
                cls_name, type(payload).__name__,
            )
            payload = {}
        signals[(cls_name, var_name, scope)] = dict(payload)  # shallow copy

    def _record_signal_error(self, cls_name: str, var_name: str, exc: Exception) -> int:
        bucket = self._signal_errors_this_frame
        bucket.append((cls_name, var_name, exc))
        return len(bucket) - 1

    def _commit(
        self,
        pong: Pong,
        observation: Observation,
        frame_number: int,
        ping_for_record: "Ping | None" = None,
    ) -> None:
        """Construct FrameRecord, commit to _frame_stream, update _frame counter.

        Args:
            pong:            Control signal from the reasoner.
            observation:     Execution result observation for this frame.
            frame_number:    Frame sequence number.
            ping_for_record: Perceptual input seen by the model for this frame
                             (optional; uses empty Ping when absent).
        """
        L = self.L
        effective_ping = ping_for_record if ping_for_record is not None else Ping(
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
        if self.frame_log is not None:
            self.frame_log.write_frame(self._build_write_spec(record))

    def _build_write_spec(self, record: FrameRecord) -> "FrameWriteSpec":
        """Translate a FrameRecord into a FrameWriteSpec for the frame_log writer.

        Args:
            record: Completed FrameRecord from this frame.

        Returns:
            FrameWriteSpec ready to pass to FrameLog.write_frame().
        """
        import json as _json
        import traceback as _tb
        from vessal.ark.shell.hull.cell.kernel.frame_log.types import ErrorOnSource, FrameWriteSpec, SignalRow

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
        sig_rows: list[SignalRow] = []
        for (cls_name, var_name, scope), payload in self.L.get("signals", {}).items():
            err_id = payload.get("_error_id") if isinstance(payload, dict) else None
            if err_id is not None and 0 <= err_id < len(self._signal_errors_this_frame):
                _cls, _var, exc = self._signal_errors_this_frame[err_id]
                tb_text = "".join(_tb.TracebackException.from_exception(exc).format())
                sig_rows.append(SignalRow(
                    class_name=cls_name,
                    var_name=var_name,
                    scope=scope,
                    payload_json=None,
                    error=ErrorOnSource("signal_update", var_name, tb_text),
                ))
            else:
                sig_rows.append(SignalRow(
                    class_name=cls_name,
                    var_name=var_name,
                    scope=scope,
                    payload_json=_json.dumps(payload, default=str),
                    error=None,
                ))
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
            signals=sig_rows,
        )
