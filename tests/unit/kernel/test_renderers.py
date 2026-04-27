# tests/test_renderers.py — describe renderer module tests
#
# Tests render_value(obj, detail_level) for three detail_level values:
#   "directory" — type + key metrics, one-line summary
#   "diff"      — change display, shows value but truncated
#   "pin"       — detailed observation, retains more content
#
# Types covered: primitives, collections, callables, instances, binary

import inspect
import io
import types
import pytest

from vessal.ark.shell.hull.cell.kernel.describe import render_value


# ──────────────────────────────────────────────────────────────────────────────
# Directory view tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderValueDirectory:
    def test_int(self):
        assert render_value(42, "directory") == "int"

    def test_float(self):
        assert render_value(3.14, "directory") == "float"

    def test_bool(self):
        assert render_value(True, "directory") == "bool"

    def test_none(self):
        assert render_value(None, "directory") == "None"

    def test_short_string(self):
        result = render_value("alice", "directory")
        assert result == "str, 5 chars"

    def test_long_string(self):
        s = "x" * 300
        result = render_value(s, "directory")
        assert "str" in result
        assert "300 chars" in result

    def test_empty_string(self):
        result = render_value("", "directory")
        assert "str" in result
        assert "0 chars" in result

    def test_small_list(self):
        result = render_value([1, 2, 3], "directory")
        assert "list" in result
        assert "3 items" in result

    def test_large_list_with_type(self):
        result = render_value(list(range(20)), "directory")
        assert "list" in result
        assert "20 items" in result

    def test_mixed_list_no_elem_type(self):
        result = render_value([1, "a", 3.0], "directory")
        assert "list" in result
        assert "3 items" in result

    def test_dict(self):
        result = render_value({"a": 1, "b": 2}, "directory")
        assert "dict" in result
        assert "2 items" in result

    def test_empty_dict(self):
        result = render_value({}, "directory")
        assert "dict" in result
        assert "0 items" in result

    def test_tuple(self):
        result = render_value((1, 2), "directory")
        assert "tuple" in result
        assert "2 items" in result

    def test_set(self):
        result = render_value({1, 2, 3}, "directory")
        assert "set" in result
        assert "3 items" in result

    def test_bytes_bytes(self):
        result = render_value(b"\x00" * 5, "directory")
        assert "bytes" in result
        assert "5B" in result

    def test_bytes_kb(self):
        result = render_value(b"\x00" * 2048, "directory")
        assert "bytes" in result
        assert "KB" in result

    def test_bytes_mb(self):
        result = render_value(b"\x00" * (2 * 1024 * 1024), "directory")
        assert "bytes" in result
        assert "MB" in result

    def test_module(self):
        import os
        result = render_value(os, "directory")
        assert "module" in result
        assert "os" in result

    def test_function(self):
        def my_func(x, y):
            return x + y
        result = render_value(my_func, "directory")
        assert "function" in result

    def test_class(self):
        class MyClass:
            def method_a(self): pass
            def method_b(self): pass
        result = render_value(MyClass, "directory")
        assert "class" in result

    def test_io_open(self):
        buf = io.StringIO("hello")
        result = render_value(buf, "directory")
        assert "open" in result or "StringIO" in result
        buf.close()

    def test_instance(self):
        class Foo:
            pass
        result = render_value(Foo(), "directory")
        assert "Foo" in result

    def test_custom_vessal_repr(self):
        """__vessal_repr__ is called first when the object has it."""
        class CustomObj:
            def __vessal_repr__(self, detail_level):
                return f"custom:{detail_level}"
        result = render_value(CustomObj(), "directory")
        assert result == "custom:directory"


# ──────────────────────────────────────────────────────────────────────────────
# Diff view tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderValueDiff:
    def test_int_full_value(self):
        assert render_value(42, "diff") == "42"

    def test_float(self):
        assert render_value(3.14, "diff") == "3.14"

    def test_bool(self):
        assert render_value(True, "diff") == "True"

    def test_none(self):
        assert render_value(None, "diff") == "None"

    def test_short_string_full(self):
        result = render_value("hello", "diff")
        assert "hello" in result

    def test_medium_string_truncated(self):
        s = "a" * 500
        result = render_value(s, "diff")
        assert len(result) < 500
        assert "chars" in result

    def test_long_string_truncated(self):
        s = "a" * 3000
        result = render_value(s, "diff")
        assert len(result) < 3000
        assert "chars" in result

    def test_small_list_full(self):
        lst = [1, 2, 3]
        result = render_value(lst, "diff")
        assert "1" in result and "2" in result and "3" in result

    def test_large_list_first_3(self):
        lst = list(range(50))
        result = render_value(lst, "diff")
        assert "0" in result
        assert "items" in result

    def test_dict_small(self):
        d = {"k": "v"}
        result = render_value(d, "diff")
        assert "k" in result or "v" in result

    def test_bytes(self):
        result = render_value(b"\x00\x01\x02", "diff")
        assert "bytes" in result

    def test_module(self):
        import os
        result = render_value(os, "diff")
        assert "os" in result

    def test_function(self):
        def add(a, b): return a + b
        result = render_value(add, "diff")
        assert "add" in result

    def test_class(self):
        class Foo:
            pass
        result = render_value(Foo, "diff")
        assert "Foo" in result


# ──────────────────────────────────────────────────────────────────────────────
# Pin view tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderValuePin:
    def test_int_full(self):
        assert render_value(42, "pin") == "42"

    def test_none(self):
        assert render_value(None, "pin") == "None"

    def test_short_string_full(self):
        result = render_value("hi", "pin")
        assert "hi" in result

    def test_medium_string_500_chars(self):
        s = "a" * 1000
        result = render_value(s, "pin")
        assert len(result) <= 560  # 500 chars + truncation marker
        assert "chars" in result

    def test_long_string_200_chars(self):
        s = "a" * 3000
        result = render_value(s, "pin")
        assert len(result) <= 260
        assert "chars" in result

    def test_small_list_full(self):
        lst = [1, 2, 3]
        result = render_value(lst, "pin")
        assert "1" in result and "3" in result

    def test_large_list_first_5(self):
        lst = list(range(100))
        result = render_value(lst, "pin")
        assert "items" in result

    def test_huge_list_first_3(self):
        lst = list(range(2000))
        result = render_value(lst, "pin")
        assert "items" in result

    def test_bytes(self):
        result = render_value(b"\x00\x01\x02", "pin")
        assert "hex" in result

    def test_module(self):
        import os
        result = render_value(os, "pin")
        assert "module" in result or "os" in result

    def test_function_short_source(self):
        def tiny(x): return x + 1
        result = render_value(tiny, "pin")
        # Short function — should include function info
        assert "tiny" in result or "function" in result

    def test_custom_vessal_repr_pin(self):
        class CustomObj:
            def __vessal_repr__(self, detail_level):
                return f"custom:{detail_level}"
        result = render_value(CustomObj(), "pin")
        assert result == "custom:pin"


# ──────────────────────────────────────────────────────────────────────────────
# Fallback for unknown detail_level
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderValueFallback:
    def test_unknown_level_returns_string(self):
        """Unknown detail_level does not crash; returns a string."""
        result = render_value(42, "unknown_level")
        assert isinstance(result, str)

    def test_repr_fallback_for_unknown_type(self):
        """Unregistered type falls back to repr with truncation."""
        class Weird:
            def __repr__(self): return "i_am_weird"
        result = render_value(Weird(), "directory")
        assert isinstance(result, str)


# ──────────────────────────────────────────────────────────────────────────────
# render_function / render_class — linecache-backed source (no _source attr)
# ──────────────────────────────────────────────────────────────────────────────

class TestCallableSourceFromLinecache:
    """render_function and render_class must read source via inspect.getsource
    (linecache-backed) — they no longer rely on a _source attribute."""

    def test_render_function_pin_uses_linecache(self):
        import linecache, sys, types
        from vessal.ark.shell.hull.cell.kernel.describe import render_value
        filename = "<frame-9001>"
        source = "def hello():\n    return 'world'"
        linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
        if filename not in sys.modules:
            mod = types.ModuleType(filename)
            mod.__file__ = filename
            sys.modules[filename] = mod
        ns = {"__name__": filename}
        code = compile(source, filename, "exec")
        exec(code, ns)
        assert not hasattr(ns["hello"], "_source")
        rendered = render_value(ns["hello"], "pin")
        assert "def hello" in rendered
        assert "return 'world'" in rendered

    def test_render_class_pin_uses_linecache(self):
        import linecache, sys, types
        from vessal.ark.shell.hull.cell.kernel.describe import render_value
        filename = "<frame-9002>"
        source = "class Greeter:\n    def hi(self):\n        return 1"
        linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
        if filename not in sys.modules:
            mod = types.ModuleType(filename)
            mod.__file__ = filename
            sys.modules[filename] = mod
        ns = {"__name__": filename}
        code = compile(source, filename, "exec")
        exec(code, ns)
        assert not hasattr(ns["Greeter"], "_source")
        rendered = render_value(ns["Greeter"], "pin")
        assert "class Greeter" in rendered
        assert "def hi" in rendered
