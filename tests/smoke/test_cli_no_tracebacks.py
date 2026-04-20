"""test_cli_no_tracebacks — D7 system defense.

Contract: every CLI code path that represents a condition Vessal itself
understands (user-recoverable or transport-level benign) must NOT emit a
Python ``Traceback`` on stderr. New cases are added as the domesticated set
grows. PR-1 seeds the wizard-collision case; PR-2 adds the HTTP-disconnect
case.

Issue: console/3-executing/20260420-cli-traceback-noise.md
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _wizard_collision_case(tmp_path: Path) -> tuple[list[str], str]:
    (tmp_path / "agent_test").mkdir()
    # name -> collision, name re-prompt -> fresh, 3 blanks, dockerize n
    stdin = "agent_test\nfresh_agent\n\n\n\nn\n"
    return ["create"], stdin


_CASES = {
    "vessal_create_name_collision": _wizard_collision_case,
}


@pytest.mark.parametrize("case_name", sorted(_CASES))
def test_cli_paths_are_traceback_free(vessal_cli, tmp_path, case_name):
    argv, stdin = _CASES[case_name](tmp_path)
    result = vessal_cli(argv, stdin=stdin)
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"{case_name}: unexpected Traceback on CLI output:\n{combined}"
    )
