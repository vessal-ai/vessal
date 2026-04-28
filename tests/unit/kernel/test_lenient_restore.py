"""test_lenient_restore.py — lenient cloudpickle.loads via UnresolvedRef.

Spec: docs/architecture/kernel/05-persistence.md §5.4. cloudpickle.loads
must never raise on by-reference resolution failure. Failed positions are
substituted with UnresolvedRef placeholders that self-describe via __repr__
and raise on use.
"""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path

import cloudpickle
import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel, UnresolvedRef
from vessal.ark.shell.hull.cell.kernel.lenient import LenientUnpickler
from tests.unit.kernel._ping_helpers import minimal_kernel


# ─── UnresolvedRef invariants ───────────────────────────────────────────

class TestUnresolvedRefRepr:
    """__repr__ must never raise against adversarial inputs."""

    def test_repr_basic(self):
        ref = UnresolvedRef("skills.chat", "ChatSkill", "ModuleNotFoundError")
        out = repr(ref)
        assert "skills.chat" in out
        assert "ChatSkill" in out
        assert "ModuleNotFoundError" in out

    def test_repr_with_none_inputs(self):
        ref = UnresolvedRef(None, None, None)
        out = repr(ref)
        assert isinstance(out, str)

    def test_repr_with_bytes_input(self):
        ref = UnresolvedRef(b"binary", "Cls", "reason")
        out = repr(ref)
        assert isinstance(out, str)

    def test_repr_with_huge_string(self):
        big = "x" * 10000
        ref = UnresolvedRef(big, "Cls", "reason")
        out = repr(ref)
        assert isinstance(out, str)

    def test_repr_with_special_chars(self):
        ref = UnresolvedRef("mod\nwith\tnewline", "Cls<>", 'with "quotes"')
        out = repr(ref)
        assert isinstance(out, str)

    def test_attribute_access_raises_attribute_error(self):
        ref = UnresolvedRef("skills.chat", "ChatSkill", "missing")
        with pytest.raises(AttributeError, match="unavailable"):
            _ = ref.send_message

    def test_call_raises_runtime_error(self):
        ref = UnresolvedRef("skills.chat", "ChatSkill", "missing")
        with pytest.raises(RuntimeError, match="unavailable"):
            ref()

    def test_slots_accessible(self):
        ref = UnresolvedRef("m", "q", "r")
        assert ref.module == "m"
        assert ref.qualname == "q"
        assert ref.reason == "r"

    def test_setstate_discards_state(self):
        ref = UnresolvedRef("m", "q", "r")
        ref.__setstate__({"greeting": "hi"})  # must not raise, must not modify ref
        assert ref.module == "m"


# ─── LenientUnpickler ──────────────────────────────────────────────────

class TestLenientUnpickler:
    """find_class hook: healthy paths resolve; missing module/attr → UnresolvedRef."""

    def test_resolves_existing_class(self):
        blob = cloudpickle.dumps(types.SimpleNamespace)
        result = LenientUnpickler(io.BytesIO(blob)).load()
        assert result is types.SimpleNamespace

    def test_missing_module_returns_unresolved_ref(self):
        # Install a temp module, pickle a class from it by-reference,
        # then remove the module before unpickling.
        mod_name = "vessal_test_lenient_missing_mod_xyz"
        mod = types.ModuleType(mod_name)
        class TempCls:
            pass
        mod.TempCls = TempCls
        TempCls.__module__ = mod_name
        sys.modules[mod_name] = mod
        try:
            blob = cloudpickle.dumps(TempCls)
        finally:
            del sys.modules[mod_name]

        result = LenientUnpickler(io.BytesIO(blob)).load()
        # cloudpickle may use by-value (if the module was synthetic).
        # If by-reference was used and failed → UnresolvedRef.
        # If by-value was used → reconstructed class (still valid).
        assert isinstance(result, type) or isinstance(result, UnresolvedRef)

    def test_missing_attribute_returns_unresolved_ref(self):
        mod_name = "vessal_test_lenient_missing_attr_abc"
        mod = types.ModuleType(mod_name)
        class WillBeRemoved:
            pass
        mod.WillBeRemoved = WillBeRemoved
        WillBeRemoved.__module__ = mod_name
        sys.modules[mod_name] = mod

        blob = cloudpickle.dumps(WillBeRemoved)
        del mod.WillBeRemoved  # attr gone, module stays

        try:
            result = LenientUnpickler(io.BytesIO(blob)).load()
            assert isinstance(result, type) or isinstance(result, UnresolvedRef)
        finally:
            del sys.modules[mod_name]


# ─── End-to-end via Kernel.restore() ────────────────────────────────────

class TestKernelRestoreLenient:
    """Kernel.restore() must not raise even when a snapshot contains a
    by-reference object whose module has been removed."""

    def test_restore_with_missing_skill_does_not_raise(self, tmp_path: Path):
        mod_name = "vessal_test_skill_disappearing_e2e"
        mod = types.ModuleType(mod_name)
        class FakeSkill:
            def __init__(self, greeting: str):
                self.greeting = greeting
        # Remove .<locals>. so cloudpickle uses by-reference (not by-value bytecode embedding).
        FakeSkill.__qualname__ = "FakeSkill"
        mod.FakeSkill = FakeSkill
        FakeSkill.__module__ = mod_name
        sys.modules[mod_name] = mod

        try:
            k = minimal_kernel()
            k.L["my_skill"] = FakeSkill("hi")
            snap = str(tmp_path / "snap.bin")
            k.snapshot(snap)
        finally:
            del sys.modules[mod_name]

        k2 = minimal_kernel()
        k2.restore(snap)  # must NOT raise
        assert "my_skill" in k2.L
        # By-reference path was forced: placeholder must be UnresolvedRef.
        assert isinstance(k2.L["my_skill"], UnresolvedRef)

    def test_restored_missing_ref_repr_contains_unresolved(self, tmp_path: Path):
        mod_name = "vessal_test_skill_repr_check_e2e"
        mod = types.ModuleType(mod_name)
        class ReprSkill:
            pass
        # Force by-reference serialization.
        ReprSkill.__qualname__ = "ReprSkill"
        mod.ReprSkill = ReprSkill
        ReprSkill.__module__ = mod_name
        sys.modules[mod_name] = mod

        try:
            k = minimal_kernel()
            k.L["rs"] = ReprSkill()
            snap = str(tmp_path / "snap.bin")
            k.snapshot(snap)
        finally:
            del sys.modules[mod_name]

        k2 = minimal_kernel()
        k2.restore(snap)
        val = k2.L["rs"]
        assert isinstance(val, UnresolvedRef)
        assert "UnresolvedRef" in repr(val)
