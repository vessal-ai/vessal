"""executor.py — Code execution engine: safely executes Agent-generated code in a sandboxed namespace."""
#   ExecResult                  operation execution result dataclass
#   execute(operation, ns, frame_number) -> ExecResult
#       Execute Python code in a namespace dict, return ExecResult.
#       All side effects are written to ns system variables:
#         _operation  the code that was executed
#         _stdout     captured print output
#         _error      exception info (None if no exception)
#         _diff       change summary (added/modified/deleted user variables)
#       Does NOT write ns["_frame"] — that is _commit_frame's responsibility.
#       Does NOT write _frame_log or construct FrameRecord — that is Cell's responsibility.
#       Exception tracebacks are intelligently compressed — user code frames and exception
#       info are retained while library-internal frames are folded.
#       Bare expressions (e.g. x, data.head()) have their value appended to _stdout
#       (Jupyter-style).
#   attach_source(code, ns) -> None
#       Attaches the source code of each top-level function/class definition in code
#       as a obj._source attribute on the object.
#       Called by execute.
#   is_user_var(name) -> bool
#       Determines whether a variable name is a user variable (does not start with _).
#       Shared between executor and renderer.
#
# This is the mechanism layer (fixed, unchanging); it has no dependencies on
# other Kernel modules, only on describe.renderers.

from __future__ import annotations

import ast
import io
import sys
import time as _time
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any

from vessal.ark.shell.hull.cell.kernel.describe import render_value
from vessal.ark.shell.hull.cell.protocol import ErrorRecord


# Maximum length for bare expression repr. Truncated with "..." when exceeded.
_EXPR_REPR_MAX_LEN = 2000

# Traceback line count threshold. Returned as-is when <= this value; longer
# tracebacks have library-internal frames folded.
_TRACEBACK_COMPRESS_THRESHOLD = 20


@dataclass(frozen=True, slots=True)
class ExecResult:
    """Operation execution result.

    Attributes:
        stdout: print() output + the last non-None expression value.
        diff: Namespace change record.
        error: Exception info. None when no exception occurred.
    """

    stdout: str
    diff: str
    error: str | None


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


def execute(operation: str | None, ns: dict[str, Any], frame_number: int) -> ExecResult:
    """Execute operation code in the namespace.

    frame_number: passed in by Cell via Kernel; used for ErrorRecord and _ns_meta tracking.
    execute() is responsible for updating _stdout/_diff/_error/_ns_meta and _operation.
    execute() must NOT write ns["_frame"] — that is _commit_frame's responsibility.
    execute() must NOT write _frame_log or construct FrameRecord.

    Args:
        operation: Python code string to execute. None or whitespace-only is treated as a no-op.
        ns: Agent's namespace dict; side effects are written directly to it.
        frame_number: Current frame number; used for ErrorRecord and _ns_meta, not written to ns["_frame"].

    Returns:
        ExecResult containing stdout, diff, and error fields.

    Side effects:
        ns["_operation"], ns["_stdout"], ns["_error"], ns["_diff"] are updated after execution.
        ns["_ns_meta"] is updated with variable metadata after execution.
    """
    # Step 1: return immediately for empty code, reset side-effect variables
    # Note: _ns_meta and _frame_log are not reset; empty operation produces no new frame data
    if not operation or not operation.strip():
        ns["_operation"] = ""
        ns["_stdout"] = ""
        ns["_error"] = None
        ns["_diff"] = ""
        return ExecResult(stdout="", diff="", error=None)

    # Step 2: record the operation source
    ns["_operation"] = operation

    # Step 3: before-snapshot — record keys, id()s, and value references before execution
    # id(v) is the object's memory address; unchanged for the same object; changes when value is replaced
    # before_values only stores references (no deep copy); used by _compute_diff to generate -old lines
    before_keys = set(ns.keys())
    before_ids = {k: id(v) for k, v in ns.items()}
    before_values = {k: v for k, v in ns.items() if is_user_var(k)}

    # Snapshot protected keys before exec (for restoring builtins agent deleted)
    protected_keys = set(ns.get("_protected_keys", []))
    protected_snapshot = {k: ns[k] for k in protected_keys if k in ns}

    # Step 3.5: check if the last statement is a bare expression; rewrite as assignment if so
    modified_operation = _maybe_capture_last_expr(operation)

    # Step 4: execute code, capture stdout and exceptions
    stdout_buffer = io.StringIO()
    error = None

    try:
        with redirect_stdout(stdout_buffer):
            exec(modified_operation, ns)  # noqa: S102
    except KeyboardInterrupt:
        raise  # User interrupt (Ctrl+C); do not catch; allow Agent to be stopped
    except BaseException:
        # SystemExit (exit()/sys.exit()) and all regular exceptions are captured as
        # strings and do not propagate
        try:
            error = _compress_traceback(traceback.format_exc())
        except Exception:
            error = traceback.format_exc()  # use raw traceback if compression itself fails
        errors = ns.get("_errors", [])
        errors.append(ErrorRecord("runtime", error, frame_number, _time.time()))
        if len(errors) > 50:
            ns["_errors"] = errors[-50:]
        else:
            ns["_errors"] = errors

    # Step 4.5: if there is a bare expression result, append it to stdout
    expr_result = ns.pop("_expr_result", None)
    captured_stdout = stdout_buffer.getvalue()
    if expr_result is not None and error is None:
        result_repr = repr(expr_result)
        if len(result_repr) > _EXPR_REPR_MAX_LEN:
            result_repr = result_repr[:_EXPR_REPR_MAX_LEN] + "..."
        if captured_stdout and not captured_stdout.endswith("\n"):
            captured_stdout += "\n"
        captured_stdout += result_repr + "\n"

    ns["_stdout"] = captured_stdout
    ns["_error"] = error

    # Step 5: clean up __builtins__ injected by exec
    # exec() injects __builtins__ into ns; remove it if it wasn't there before
    if "__builtins__" in ns and "__builtins__" not in before_keys:
        del ns["__builtins__"]

    # Step 5.5: restore protected keys deleted by agent code
    restored_keys = []
    for k, v in protected_snapshot.items():
        if k not in ns:
            ns[k] = v
            restored_keys.append(k)
    if restored_keys:
        warning = f"[system] The following variables were deleted by code and have been automatically restored: {', '.join(sorted(restored_keys))}\n"
        captured_stdout += warning
        ns["_stdout"] = captured_stdout
        errors = ns.get("_errors", [])
        errors.append(ErrorRecord(
            "builtin_restored", warning.strip(),
            frame_number, _time.time(),
        ))
        if len(errors) > 50:
            ns["_errors"] = errors[-50:]
        else:
            ns["_errors"] = errors

    # Step 6: attach the source of each newly defined function/class to the object's _source attribute
    # Use the original operation, not modified_operation, to ensure accurate source
    attach_source(operation, ns)

    # Step 7: compute diff (git-style +/- format), write to _diff
    _compute_diff(ns, before_keys, before_ids, before_values)

    # Step 8: update _ns_meta — variable lifecycle tracking
    ns["_ns_meta"] = _update_ns_meta(ns, before_keys, before_ids, frame_number)

    return ExecResult(stdout=ns["_stdout"], diff=ns["_diff"], error=ns["_error"])


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


def attach_source(code: str, ns: dict) -> None:
    """Store the source code of each top-level function/class definition in code as the object's _source attribute.

    Source is stored as obj._source on the object itself, not in an external
    mapping. cloudpickle serialization includes __dict__ automatically, so
    _source is preserved with the object.

    Design notes:
    - When a function is redefined, the old object is GC'd and its source
      disappears; no manual cleanup is needed
    - After bar = foo, both share the same object and the same _source, as intended
    - Source includes comments, docstrings, and decorators within the function
      body — all original text within the ast line range

    Silently skips on ast.parse failure (code with syntax errors will have
    already failed at exec time).

    Args:
        code: The code string that was executed.
        ns: The namespace dict after execution; used to look up objects by name.
    """
    try:
        tree = ast.parse(code)
        lines = code.splitlines(True)  # keepends=True, preserves line endings

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            name = node.name
            if name not in ns:
                continue
            # When decorators are present, start from the first decorator line;
            # otherwise start from the def/class line (both are 1-based)
            start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            source = "".join(lines[start_line - 1 : node.end_lineno])
            try:
                ns[name]._source = source
            except (AttributeError, TypeError):
                pass  # C-implemented builtin types (int, len, etc.) cannot have attributes; skip

    except SyntaxError:
        pass  # syntax error means exec already failed; skip source extraction


def _compress_traceback(tb_text: str) -> str:
    """Compress traceback: retain user code frames and exception info, fold library-internal frames.

    Returns unchanged when <= _TRACEBACK_COMPRESS_THRESHOLD lines — shallow call
    stacks need no compression. For longer tracebacks, retains:
      1. First line "Traceback (most recent call last):"
      2. Last File "<string>" frame (user code error location) and its code line
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

    # Last user code frame (LLM's code executes in "<string>")
    user_frame_idx = -1
    for i, line in enumerate(lines):
        if 'File "<string>"' in line:
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


def _update_ns_meta(ns: dict[str, Any], before_keys: set, before_ids: dict, frame: int) -> dict[str, Any]:
    """Update and return the new _ns_meta — tracking lifecycle metadata for user variables.

    Rules (only processes user variables, i.e., those not starting with _):
    - New variable: write created, last_used (both = frame), size, type, accesses=1
    - Modified variable (id changed): update last_used, size, type, accesses +1; preserve created
    - Unchanged variable: keep old meta as-is
    - Deleted variable: automatically excluded from new_meta

    Args:
        ns:          Current namespace (after execute)
        before_keys: Set of keys before execution
        before_ids:  id() mapping for each variable before execution
        frame:       Current frame number (frame_number, passed in by Cell)

    Returns:
        Updated _ns_meta dict (written by execute; caller assigns to ns["_ns_meta"])
    """
    # Read old meta (already present in ns before execute)
    old_meta: dict = ns.get("_ns_meta", {})
    new_meta: dict = {}
    after_keys = set(ns.keys())

    for k in sorted(after_keys):
        if not is_user_var(k):
            continue  # skip system variables
        obj = ns[k]
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
    ns: dict, before_keys: set, before_ids: dict, before_values: dict
) -> None:
    """Compute diff and write to ns["_diff"].

    Format (git-style, only + and - symbols):
    - New variable:      +name = preview
    - Modified variable: -name = old_preview  (old value)
                         +name = new_preview  (new value, immediately following)
    - Deleted variable:  -name = old_preview
    Lines are sorted alphabetically by variable name; modified -old and +new
    are kept consecutive.

    Args:
        ns:             Current namespace (after execute)
        before_keys:    Set of keys before execution
        before_ids:     id() mapping for each variable before execution
        before_values:  Value references for each user variable before execution
                        (references only, no deep copy)

    Side effects:
        Writes to ns["_diff"].
    """
    after_keys = set(ns.keys())
    lines = []

    # New variables (sorted by name)
    for k in sorted(after_keys - before_keys):
        if is_user_var(k):
            lines.append(f"+{k} = {render_value(ns[k], 'diff')}")

    # Modified variables (id changed) — consecutive -old / +new
    for k in sorted(after_keys & before_keys):
        if is_user_var(k) and id(ns[k]) != before_ids.get(k):
            old_preview = render_value(before_values[k], "diff")
            new_preview = render_value(ns[k], "diff")
            lines.append(f"-{k} = {old_preview}")
            lines.append(f"+{k} = {new_preview}")

    # Deleted variables
    for k in sorted(before_keys - after_keys):
        if is_user_var(k):
            old_preview = render_value(before_values[k], "diff")
            lines.append(f"-{k} = {old_preview}")

    ns["_diff"] = "\n".join(lines)
