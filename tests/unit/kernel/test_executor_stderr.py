"""executor stderr capture — spec §3.2 requires both stdout and stderr captured."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.executor import execute


def test_execute_captures_stderr():
    G: dict = {}
    L: dict = {}
    operation = "import sys; sys.stderr.write('warning: x is deprecated\\n')"

    result = execute(operation, G, L, frame_number=1)

    assert result.stderr == "warning: x is deprecated\n"
    assert result.stdout == ""
    assert result.error is None


def test_execute_stderr_independent_of_stdout():
    G: dict = {}
    L: dict = {}
    operation = (
        "import sys\n"
        "print('to stdout')\n"
        "sys.stderr.write('to stderr\\n')\n"
    )

    result = execute(operation, G, L, frame_number=1)

    assert result.stdout == "to stdout\n"
    assert result.stderr == "to stderr\n"


def test_execute_empty_stderr_is_empty_string():
    G: dict = {}
    L: dict = {}
    result = execute("x = 1", G, L, frame_number=1)
    assert result.stderr == ""


def test_execute_stderr_write_return_value_does_not_appear_in_stdout():
    G: dict = {}
    L: dict = {}
    # sys.stderr.write() returns the number of bytes written as an int.
    # That int must NOT appear in stdout — we capture the side effect, not the return value.
    result = execute("import sys; sys.stderr.write('abc\\n')", G, L, frame_number=1)
    assert result.stdout == ""  # "4" must not be in stdout
