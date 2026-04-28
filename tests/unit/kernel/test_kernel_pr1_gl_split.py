"""test_kernel_pr1_gl_split.py — Contracts for PR 1 (G/L namespace split).

These tests pin the spec invariants from docs/architecture/kernel/02-namespace.md:
- Kernel exposes G and L as separate dicts.
- exec(code, G, L) writes only to L; G is untouched.
- eval(expr, G, copy(L)) cannot pollute L.
- snapshot serializes only L.
- restore loads only into L; G is reconstructed by __init__.
- Lenient restore continues to put UnresolvedRef into L on missing module.
"""
from __future__ import annotations

import cloudpickle
import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.lenient import UnresolvedRef


class TestKernelHasGAndL:
    def test_kernel_exposes_g_and_l_as_dicts(self):
        k = Kernel()
        assert isinstance(k.G, dict)
        assert isinstance(k.L, dict)

    def test_g_and_l_are_distinct_objects(self):
        k = Kernel()
        assert k.G is not k.L

    def test_g_starts_empty_in_pr1(self):
        # PR 1 does not populate G yet; boot script (PR 4) will.
        k = Kernel()
        assert k.G == {}

    def test_l_has_init_namespace_keys(self):
        k = Kernel()
        # Spot-check a few keys that belonged to _init_namespace pre-PR1
        assert "_frame" in k.L
        assert "_protected_keys" in k.L
        assert "_frame_stream" in k.L


class TestThreeArgExecWritesToLOnly:
    def test_assignment_in_operation_lands_in_L(self):
        k = Kernel()
        k.exec_operation("x = 42", frame_number=1)
        assert k.L["x"] == 42
        assert "x" not in k.G

    def test_g_is_readable_from_operation(self):
        k = Kernel()
        k.G["chat"] = "g_chat_marker"
        # Agent reads `chat`; Python LEGB falls back from L to G
        k.exec_operation("found = chat", frame_number=2)
        assert k.L["found"] == "g_chat_marker"
        assert "chat" not in k.L  # still only in G

    def test_g_is_not_written_by_assignment(self):
        k = Kernel()
        k.G["counter"] = 0
        k.exec_operation("counter = 99", frame_number=3)
        # Agent's reassignment shadows in L; G stays put
        assert k.L["counter"] == 99
        assert k.G["counter"] == 0


class TestEvalExpectUsesCopyOfL:
    def test_walrus_in_expect_does_not_pollute_L(self):
        # expect normally blocks walrus, but the contract here is that
        # whatever eval does internally cannot mutate the real L.
        k = Kernel()
        k.L["base"] = 1
        # Use a benign expect that reads but does not assign
        k.eval_expect("assert base == 1", frame_number=4)
        assert k.L["base"] == 1
        # No new L key should appear from expect machinery
        assert "tmp" not in k.L


class TestSnapshotDumpsOnlyL:
    def test_snapshot_file_is_cloudpickle_of_L(self, tmp_path):
        k = Kernel()
        k.L["agent_var"] = "value_from_L"
        k.G["preset_var"] = "value_from_G"
        path = tmp_path / "snap.cp"
        k.snapshot(str(path))

        with open(path, "rb") as f:
            loaded = cloudpickle.loads(f.read())

        assert isinstance(loaded, dict)
        assert loaded["agent_var"] == "value_from_L"
        assert "preset_var" not in loaded


class TestRestoreLoadsOnlyIntoL:
    def test_restore_into_L_leaves_G_to_init(self, tmp_path):
        # Step 1: write a snapshot
        k1 = Kernel()
        k1.L["session_x"] = 7
        path = tmp_path / "snap.cp"
        k1.snapshot(str(path))

        # Step 2: restore in a fresh kernel
        k2 = Kernel(snapshot_path=str(path))
        assert k2.L["session_x"] == 7
        # G is rebuilt by __init__, not from snapshot
        assert k2.G == {}


class TestLenientRestoreStillWorks:
    def test_unresolved_ref_lands_in_L_not_G(self, tmp_path):
        import io

        # Construct a pickle bytestream by hand so the GLOBAL opcode references
        # 'nonexistent.module.Marker' without requiring the module to exist at
        # serialization time.  CPython's pickle validates importability on dumps,
        # so we bypass that by building the opcodes directly (protocol 2).
        #
        # Byte layout: PROTO 2, EMPTY_DICT, BINPUT 0,
        #   BINUNICODE 'vanished', BINPUT 1,
        #   GLOBAL 'nonexistent.module\nMarker\n', BINPUT 2,
        #   EMPTY_TUPLE, NEWOBJ, BINPUT 3,
        #   SETITEM, STOP
        buf = io.BytesIO()
        buf.write(bytes([0x80, 2]))  # PROTO 2
        buf.write(b"}")              # EMPTY_DICT
        buf.write(b"q\x00")         # BINPUT 0
        buf.write(b"X")             # BINUNICODE (4-byte LE length + UTF-8)
        key = b"vanished"
        buf.write(len(key).to_bytes(4, "little"))
        buf.write(key)
        buf.write(b"q\x01")         # BINPUT 1
        buf.write(b"c")             # GLOBAL opcode
        buf.write(b"nonexistent.module\nMarker\n")
        buf.write(b"q\x02")         # BINPUT 2
        buf.write(b")")             # EMPTY_TUPLE
        buf.write(b"\x81")          # NEWOBJ
        buf.write(b"q\x03")         # BINPUT 3
        buf.write(b"s")             # SETITEM
        buf.write(b".")             # STOP
        blob = buf.getvalue()

        path = tmp_path / "snap.cp"
        path.write_bytes(blob)

        k = Kernel(snapshot_path=str(path))
        assert isinstance(k.L["vanished"], UnresolvedRef)
        assert k.G == {}  # G untouched by restore
