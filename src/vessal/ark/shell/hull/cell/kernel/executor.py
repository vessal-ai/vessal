"""executor.py — Code execution engine: safely executes Agent-generated code in a sandboxed namespace."""
#   ExecResult                  operation execution result dataclass
#   execute(operation, G, L, frame_number) -> ExecResult
#       Execute Python code with three-arg exec(code, G, L), return ExecResult.
#       NO SIDE EFFECTS on L beyond _ns_meta and any user variables the code itself binds.
#       Caller (Kernel.ping) is responsible for assembling Observation from ExecResult
#       and writing L["observation"].
#       Does NOT write ns["_frame"] — that is Kernel._commit()'s responsibility.
#       Does NOT write _frame_log or construct FrameRecord — that is Cell's responsibility.
#       Exception tracebacks are intelligently compressed — user code frames and exception
#       info are retained while library-internal frames are folded.
#       Bare expressions (e.g. x, data.head()) have their value appended to captured stdout
#       (Jupyter-style).
#   is_user_var(name) -> bool
#       Determines whether a variable name is a user variable (does not start with _).
#       Shared between executor and renderer.
#
# This is the mechanism layer (fixed, unchanging); it has no dependencies on
# other Kernel modules, only on describe.
# ExecResult.error is the raw exception with __traceback__ cleared.
# Textual traceback formatting is the caller's responsibility (kernel.py, Task 4).

from __future__ import annotations

import ast
import io
import sys
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any

from vessal.ark.shell.hull.cell.kernel import source_cache
from vessal.ark.shell.hull.cell.kernel.describe import render_value


# Maximum length for bare expression repr. Truncated with "..." when exceeded.
_EXPR_REPR_MAX_LEN = 2000

# Traceback line count threshold. Returned as-is when <= this value; longer
# tracebacks have library-internal frames folded.
_TRACEBACK_COMPRESS_THRESHOLD = 20


@dataclass(frozen=True, slots=True)
class ExecResult:
    """Operation execution result.

    `error` is the raw exception (`__traceback__` cleared) so that L can be
    cloudpickle'd and Agent can `isinstance(error, SomeExceptionClass)`.
    The errors-table textual format is computed by the caller from this
    exception via `traceback.TracebackException.from_exception(...)`.
    """

    stdout: str
    diff: str
    error: BaseException | None


def is_user_var(name: str) -> bool:
    """Determine whether a variable name is a user variable (does not start with _).

    Variables starting with _ are system variables and do not participate in
    diff calculation or namespace display. This function is also used by
    renderer.py to avoid duplicating the same convention in multiple places.

    Args:
        name: Variable name string.

    Returns:
        True for user variable, False for system variable.
    """
    return not name.startswith("_")


def execute(
    operation: str | None,
    G: dict[str, Any],
    L: dict[str, Any],
    frame_number: int,
) -> ExecResult:
    """Execute operation code in the namespace.

    frame_number: passed in by Cell via Kernel; used for _ns_meta tracking.
    execute() must NOT write L["_frame"] — that is Kernel._commit()'s responsibility.
    execute() must NOT write _frame_log or construct FrameRecord.

    Args:
        operation: Python code string to execute. None or whitespace-only is treated as a no-op.
        G: Preset assets dict (Skills, boot globals); read-only by convention. Globals for exec().
        L: Agent state dict; only _ns_meta and user-bound variables are written.
        frame_number: Current frame number; used for _ns_meta, not written to L["_frame"].

    Returns:
        ExecResult containing stdout, diff, and error fields.
    """
    # Step 1: return immediately for empty code
    if not operation or not operation.strip():
        return ExecResult(stdout="", diff="", error=None)

    # Step 3: before-snapshot — record keys, id()s, and value references before execution
    # id(v) is the object's memory address; unchanged for the same object; changes when value is replaced
    # before_values only stores references (no deep copy); used by _compute_diff to generate -old lines
    before_keys = set(L.keys())
    before_ids = {k: id(v) for k, v in L.items()}
    before_values = {k: v for k, v in L.items() if is_user_var(k)}

    # Step 3.5: check if the last statement is a bare expression; rewrite as assignment if so
    modified_operation = _maybe_capture_last_expr(operation)

    # Step 4: register the original operation text into linecache under
    # <frame-N> so inspect.getsource() works on classes/functions defined
    # below; compile against the same filename so co_filename matches.
    source_cache.register(frame_number, operation, None)
    filename = f"<frame-{frame_number}>"

    # Step 5: execute code, capture stdout and exceptions
    stdout_buffer = io.StringIO()
    error: BaseException | None = None

    try:
        # SyntaxError from compile() is a user error; catch it here so the
        # error handling path below formats and stores it like any runtime error.
        code = compile(modified_operation, filename, "exec")
        # Set __name__ so classes defined in this exec record __module__ = filename,
        # enabling inspect.getsource(SomeClass) via the sys.modules entry registered above.
        G["__name__"] = filename
        with redirect_stdout(stdout_buffer):
            exec(code, G, L)  # noqa: S102
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        # Detach traceback so cloudpickle can serialise the exception object.
        # The traceback frame chain holds references to live frame locals,
        # which often contain unpicklable objects.
        exc.__traceback__ = None
        error = exc

    # Step 5.5: if there is a bare expression result, append it to stdout
    expr_result = L.pop("_expr_result", None)
    captured_stdout = stdout_buffer.getvalue()
    if expr_result is not None and error is None:
        result_repr = repr(expr_result)
        if len(result_repr) > _EXPR_REPR_MAX_LEN:
            result_repr = result_repr[:_EXPR_REPR_MAX_LEN] + "..."
        if captured_stdout and not captured_stdout.endswith("\n"):
            captured_stdout += "\n"
        captured_stdout += result_repr + "\n"

    # Step 6: clean up __builtins__ and __name__ injected by exec into G
    if "__builtins__" in G:
        del G["__builtins__"]
    if "__name__" in G and G.get("__name__") == filename:
        del G["__name__"]

    # Step 7: compute diff (git-style +/- format)
    diff = _compute_diff(L, before_keys, before_ids, before_values)

    # Step 8: update _ns_meta — variable lifecycle tracking
    L["_ns_meta"] = _update_ns_meta(L, before_keys, before_ids, frame_number)

    return ExecResult(stdout=captured_stdout, diff=diff, error=error)


def _maybe_capture_last_expr(action: str) -> str:
    """If the last statement in action is a bare expression, rewrite it as an assignment to _expr_result.

    Returns the original string unchanged on syntax error or when the last
    statement is not an Expr node. Simple assignments (x = 1), function
    definitions, imports, etc. do not trigger this.
    After rewriting, the executor pops _expr_result from ns and appends its
    repr to _stdout.

    Uses ast.get_source_segment to extract the expression text, correctly
    handling multiple statements on one line (semicolons).

    Args:
        action: Original code string.

    Returns:
        Rewritten code string, or the original if no bare expression is found.
    """
    try:
        tree = ast.parse(action)
    except SyntaxError:
        return action

    if not tree.body:
        return action

    last_stmt = tree.body[-1]
    if not isinstance(last_stmt, ast.Expr):
        return action

    # Use ast.get_source_segment to precisely extract the expression text (handles column offsets)
    expr_text = ast.get_source_segment(action, last_stmt)
    if expr_text is None:
        return action

    # Rebuild action: the part before the expression + assignment statement + the part after
    lines = action.splitlines(True)
    start_line = last_stmt.lineno - 1       # 0-based
    start_col = last_stmt.col_offset
    end_line = last_stmt.end_lineno - 1     # 0-based
    end_col = last_stmt.end_col_offset

    before = "".join(lines[:start_line]) + lines[start_line][:start_col]
    after_same = lines[end_line][end_col:] if end_line < len(lines) else ""
    after_rest = "".join(lines[end_line + 1:]) if end_line + 1 < len(lines) else ""

    replacement = f"_expr_result = ({expr_text})\n"
    return before + replacement + after_same + after_rest


def _compress_traceback(tb_text: str) -> str:
    """Compress traceback: retain user code frames and exception info, fold library-internal frames.

    Returns unchanged when <= _TRACEBACK_COMPRESS_THRESHOLD lines — shallow call
    stacks need no compression. For longer tracebacks, retains:
      1. First line "Traceback (most recent call last):"
      2. Last File "<frame-*>" frame (user code error location) and its code line
      3. Last line (exception type and message)
    Intermediate library-internal frames are folded as "... (N lines omitted)".

    Args:
        tb_text: Output string from traceback.format_exc().

    Returns:
        Compressed traceback string.
    """
    lines = tb_text.splitlines()
    if len(lines) <= _TRACEBACK_COMPRESS_THRESHOLD:
        return tb_text

    # Last user code frame (LLM's code executes under "<frame-N>" filenames
    # registered into linecache by source_cache.register).
    user_frame_idx = -1
    for i, line in enumerate(lines):
        if 'File "<frame-' in line:
            user_frame_idx = i

    # Last line is the exception type and message (skip trailing blank lines)
    exc_idx = len(lines) - 1
    while exc_idx > 0 and not lines[exc_idx].strip():
        exc_idx -= 1

    # Set of lines to keep (excluding the first line)
    kept = set()
    if user_frame_idx >= 0:
        kept.add(user_frame_idx)
        # The code line immediately following the frame header (if not the exception line itself)
        if user_frame_idx + 1 < len(lines) and user_frame_idx + 1 != exc_idx:
            kept.add(user_frame_idx + 1)
    kept.add(exc_idx)

    omitted = len(lines) - 1 - len(kept)  # -1 for the first line

    result = [lines[0]]
    if omitted > 0:
        result.append(f"  ... ({omitted} lines omitted)")
    for i in sorted(kept):
        result.append(lines[i])
    return "\n".join(result)


def _update_ns_meta(L: dict[str, Any], before_keys: set, before_ids: dict, frame: int) -> dict[str, Any]:
    """Update and return the new _ns_meta — tracking lifecycle metadata for user variables.

    Rules (only processes user variables, i.e., those not starting with _):
    - New variable: write created, last_used (both = frame), size, type, accesses=1
    - Modified variable (id changed): update last_used, size, type, accesses +1; preserve created
    - Unchanged variable: keep old meta as-is
    - Deleted variable: automatically excluded from new_meta

    Args:
        L:           Agent state dict (after execute)
        before_keys: Set of keys before execution
        before_ids:  id() mapping for each variable before execution
        frame:       Current frame number (frame_number, passed in by Cell)

    Returns:
        Updated _ns_meta dict (written by execute; caller assigns to L["_ns_meta"])
    """
    # Read old meta (already present in L before execute)
    old_meta: dict = L.get("_ns_meta", {})
    new_meta: dict = {}
    after_keys = set(L.keys())

    for k in sorted(after_keys):
        if not is_user_var(k):
            continue  # skip system variables
        obj = L[k]
        if k not in before_keys:
            # New variable
            new_meta[k] = {
                "created": frame,
                "last_used": frame,
                "size": sys.getsizeof(obj),
                "type": type(obj).__name__,
                "accesses": 1,
            }
        elif id(obj) != before_ids.get(k):
            # Modified variable (id changed = object was replaced)
            prev = old_meta.get(k, {})
            new_meta[k] = {
                "created": prev.get("created", frame),  # preserve first-creation frame
                "last_used": frame,
                "size": sys.getsizeof(obj),
                "type": type(obj).__name__,
                "accesses": prev.get("accesses", 0) + 1,
            }
        else:
            # Unchanged — keep old meta
            if k in old_meta:
                new_meta[k] = old_meta[k]
            # If no old meta record (rare edge case), skip

    # Deleted variables (in before_keys but not in after_keys) are automatically
    # excluded from new_meta

    return new_meta


def _compute_diff(
    L: dict, before_keys: set, before_ids: dict, before_values: dict
) -> str:
    """Return git-style diff string of namespace changes since before_keys/before_ids snapshot.

    Format (git-style, only + and - symbols):
    - New variable:      +name = preview
    - Modified variable: -name = old_preview  (old value)
                         +name = new_preview  (new value, immediately following)
    - Deleted variable:  -name = old_preview
    Lines are sorted alphabetically by variable name; modified -old and +new
    are kept consecutive.

    Args:
        L:              Agent state dict (after execute)
        before_keys:    Set of keys before execution
        before_ids:     id() mapping for each variable before execution
        before_values:  Value references for each user variable before execution
                        (references only, no deep copy)
    """
    after_keys = set(L.keys())
    lines = []
    for k in sorted(after_keys - before_keys):
        if is_user_var(k):
            lines.append(f"+{k} = {render_value(L[k], 'diff')}")
    for k in sorted(after_keys & before_keys):
        if is_user_var(k) and id(L[k]) != before_ids.get(k):
            old_preview = render_value(before_values[k], "diff")
            new_preview = render_value(L[k], "diff")
            lines.append(f"-{k} = {old_preview}")
            lines.append(f"+{k} = {new_preview}")
    for k in sorted(before_keys - after_keys):
        if is_user_var(k):
            old_preview = render_value(before_values[k], "diff")
            lines.append(f"-{k} = {old_preview}")
    return "\n".join(lines)
