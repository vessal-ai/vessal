# tests/unit/kernel/test_kernel_pr2_ping_primitive.py
"""Pin PR 2 contracts: single ping primitive + observation/verdict in L.

Each test pins one contract from refactor-plan.md PR 2:
  - kernel.ping(pong, namespace) -> Ping is the single entry
  - L["observation"] is an Observation dataclass after non-None ping
  - L["verdict"] is a Verdict (or None) after non-None ping
  - Legacy scattered keys (_stdout/_error/_diff/_verdict/_actual_tokens_*/
    _protected_keys) no longer appear in L after ping
  - The 8 deleted multi-entry methods do not exist on Kernel
"""
from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import (
    Action, Observation, Ping, Pong, Verdict,
)
from tests.unit.kernel._ping_helpers import minimal_kernel


@pytest.fixture
def k():
    """Fresh Kernel, no snapshot, no db."""
    return minimal_kernel()


def test_ping_signature_returns_Ping(k):
    """kernel.ping(pong, namespace) returns a Ping dataclass."""
    namespace = {"globals": k.G, "locals": k.L}
    result = k.ping(None, namespace)
    assert isinstance(result, Ping)


def test_ping_pong_None_does_not_commit_frame(k):
    """First call with pong=None must not increment _frame."""
    namespace = {"globals": k.G, "locals": k.L}
    before = k.L["_frame"]
    k.ping(None, namespace)
    assert k.L["_frame"] == before


def test_ping_with_pong_increments_frame(k):
    """ping(pong, ns) where pong is non-None must increment _frame by 1."""
    namespace = {"globals": k.G, "locals": k.L}
    # Bootstrap so _last_ping is set
    k.ping(None, namespace)
    before = k.L["_frame"]
    pong = Pong(think="", action=Action(operation="x = 1", expect=""))
    k.ping(pong, namespace)
    assert k.L["_frame"] == before + 1


def test_ping_writes_observation_to_L(k):
    """After ping(pong, ns), L['observation'] is an Observation dataclass."""
    namespace = {"globals": k.G, "locals": k.L}
    k.ping(None, namespace)
    pong = Pong(think="", action=Action(operation="print('hi')", expect=""))
    k.ping(pong, namespace)
    obs = k.L["observation"]
    assert isinstance(obs, Observation)
    assert "hi" in obs.stdout
    assert obs.error is None


def test_ping_writes_verdict_to_L_when_expect_present(k):
    """ping with non-empty expect writes Verdict to L['verdict']."""
    namespace = {"globals": k.G, "locals": k.L}
    k.ping(None, namespace)
    pong = Pong(think="", action=Action(operation="x = 1", expect="assert x == 1"))
    k.ping(pong, namespace)
    verdict = k.L["verdict"]
    assert isinstance(verdict, Verdict)
    assert verdict.total == 1
    assert verdict.passed == 1


def test_ping_writes_None_verdict_when_expect_empty(k):
    """ping with empty expect writes None to L['verdict']."""
    namespace = {"globals": k.G, "locals": k.L}
    k.ping(None, namespace)
    pong = Pong(think="", action=Action(operation="x = 1", expect=""))
    k.ping(pong, namespace)
    assert k.L["verdict"] is None


def test_ping_skips_eval_when_operation_errors(k):
    """When operation raises, verdict stays None even if expect is non-empty."""
    namespace = {"globals": k.G, "locals": k.L}
    k.ping(None, namespace)
    pong = Pong(think="", action=Action(operation="1/0", expect="assert True"))
    k.ping(pong, namespace)
    assert k.L["verdict"] is None


def test_legacy_scalar_keys_absent_after_init(k):
    """Legacy scattered keys must not appear in L after Kernel construction.

    These keys were deleted in PR 2:
      _stdout, _error, _diff, _verdict, _actual_tokens_in, _actual_tokens_out,
      _protected_keys
    """
    forbidden = {
        "_stdout", "_error", "_diff", "_verdict",
        "_actual_tokens_in", "_actual_tokens_out",
        "_protected_keys",
    }
    leaked = forbidden & set(k.L.keys())
    assert leaked == set(), f"PR 2 forbidden keys leaked into L: {leaked}"


def test_legacy_scalar_keys_absent_after_ping(k):
    """After a full ping cycle, scattered legacy keys still must not appear."""
    namespace = {"globals": k.G, "locals": k.L}
    k.ping(None, namespace)
    pong = Pong(think="", action=Action(operation="x = 1", expect="assert x == 1"))
    k.ping(pong, namespace)
    forbidden = {"_stdout", "_error", "_diff", "_verdict",
                 "_actual_tokens_in", "_actual_tokens_out", "_protected_keys"}
    leaked = forbidden & set(k.L.keys())
    assert leaked == set(), f"PR 2 forbidden keys leaked into L after ping: {leaked}"


def test_multi_entry_methods_removed():
    """The 8 multi-entry Kernel methods deleted in PR 2 must not exist."""
    forbidden_attrs = {
        "prepare", "step", "exec_operation", "eval_expect",
        "update_signals", "render", "_commit_frame",
        "_build_frame_write_spec",
    }
    existing = forbidden_attrs & set(dir(Kernel))
    assert existing == set(), f"PR 2 forbidden Kernel methods still exist: {existing}"
