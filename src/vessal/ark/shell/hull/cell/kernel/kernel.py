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
# Initialization: four-step boot (spec §7.2):
#   ① self.L = {}
#   ② exec(boot_script, G, G) — capture stdout/stderr
#   ③ (restart only) LenientUnpickler.load(restore_path) → self.L
#   ④ write boot frame at n = n_prev + 1
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


class Kernel:
    """Agent execution kernel.

    Public entry point: kernel.ping(pong, namespace) — single-frame primitive.
    operation is executed as Python code; result contains stdout/diff/error.

    L is fully exposed; external code may read/write it directly. Keys starting
    with _ are system variables; modify them at your own risk.
    Kernel itself is stateless — it is simply the executor and renderer of L.

    Construction and appending of _frame_log is Cell's responsibility (Phase 3 implementation).
    """

    def __init__(
        self,
        boot_script: str,
        *,
        db_path: str | None = None,
        restore_path: str | None = None,
    ) -> None:
        """Spec §7.2 four-step boot:

          ① self.L = {}
          ② exec(boot_script, G, G) — capture stdout/stderr
          ③ (restart only) LenientUnpickler.load(restore_path) → self.L
          ④ write boot frame at n = n_prev + 1

        Args:
            boot_script: complete Python source synthesized by Hull via
                         compose_boot_script().
            db_path: SQLite frame_log location. None disables frame_log entirely
                     (test-only path; production always sets it).
            restore_path: pathname of a cloudpickle-dumps(L) blob. None = cold start.
        """
        self.G: dict = {}
        # ① empty L
        self.L: dict = {}

        # ② boot script — captures Skill __init__ prints into stdout/stderr
        import contextlib, io
        boot_stdout = io.StringIO()
        boot_stderr = io.StringIO()
        with contextlib.redirect_stdout(boot_stdout), contextlib.redirect_stderr(boot_stderr):
            exec(compile(boot_script, "<boot>", "exec"), self.G, self.G)

        # post-hook: bind any object that wants the kernel back-reference (D6)
        # Skip classes themselves — only bind instances (bound-method check).
        for obj in self.G.values():
            if isinstance(obj, type):
                continue
            bind = getattr(obj, "_bind_kernel", None)
            if callable(bind):
                bind(self)

        self._signal_errors_this_frame: list[tuple[str, str, Exception]] = []
        self.frame_log: FrameLog | None = None
        if db_path is not None:
            conn = open_db(db_path)
            source_cache.reload_from_db(conn)
            self.frame_log = FrameLog(conn)

        # ③ restart only
        if restore_path is not None:
            self.restore(restore_path)

        self._last_ping: Ping | None = None

        # ④ boot frame
        self._write_boot_frame(
            boot_script=boot_script,
            boot_stdout=boot_stdout.getvalue(),
            boot_stderr=boot_stderr.getvalue(),
        )

    def _write_boot_frame(
        self,
        *,
        boot_script: str,
        boot_stdout: str,
        boot_stderr: str,
    ) -> None:
        """Spec §7.6: write a layer=0 entry at n = n_prev + 1 capturing the boot."""
        if self.frame_log is None:
            return

        last = self.frame_log.last_committed_frame() or 0
        n = last + 1
        diff_json = self._compute_boot_diff_json()

        from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec
        spec = FrameWriteSpec(
            n=n,
            pong_think="",
            pong_operation=boot_script,
            pong_expect="True",
            obs_stdout=boot_stdout,
            obs_stderr=boot_stderr,
            obs_diff_json=diff_json,
            operation_error=None,
            verdict_value="true",
            verdict_error=None,
            signals=[],
        )
        self.frame_log.write_frame(spec)
        self.L["_frame"] = n

    def _compute_boot_diff_json(self) -> str:
        """Spec §7.6: diff(empty, L_restored) — each value repr()'d."""
        import json
        diff: dict[str, str] = {}
        for k, v in self.L.items():
            try:
                diff[k] = repr(v)
            except Exception as e:
                diff[k] = f"<unrepr: {type(v).__name__}: {type(e).__name__}>"
        return json.dumps(diff, ensure_ascii=False)

    def ping(self, pong: "Pong | None", namespace: dict) -> Ping:
        """Single Kernel primitive (spec §1.2). Runs five steps internally:

          ① archive pong (deferred to _commit inside this call)
          ② exec(pong.operation, G, L) → L["observation"]
          ③ eval(pong.expect, G, copy(L)) → L["verdict"]
          ④ signal_scan → L["signals"]
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

    def snapshot(self, path: str) -> None:
        """Serialize L to file. Pure cloudpickle.dumps(L) — no per-key filtering."""
        import os, tempfile
        path = str(path)
        body_bytes = cloudpickle.dumps(self.L)
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
        """Restore L from file. sys.modules populated by boot script before this runs."""
        with open(path, "rb") as f:
            raw = f.read()
        import io as _io
        self.L = LenientUnpickler(_io.BytesIO(raw)).load()

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
        """Stash signal error; return its index (valid only within current ping frame)."""
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
