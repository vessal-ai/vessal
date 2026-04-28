"""test_pin_skill — Pin Skill class-based API tests."""
import pytest
from vessal.skills.pin.skill import Pin
from vessal.skills._base import BaseSkill


def test_pin_is_skillbase():
    assert issubclass(Pin, BaseSkill)


def test_pin_has_required_attrs():
    assert isinstance(Pin.name, str) and Pin.name
    assert isinstance(Pin.description, str) and Pin.description


def test_pin_unpin():
    p = Pin()
    p.pin("x")
    assert "x" in p._pins
    p.unpin("x")
    assert "x" not in p._pins


def test_signal_no_pins_empty():
    p = Pin(ns={"x": 1})
    p.signal_update()
    assert p.signal == {}


def test_signal_no_ns_empty():
    p = Pin(ns=None)
    p.pin("x")
    p.signal_update()
    assert p.signal == {}


def test_signal_with_existing_var():
    ns = {"x": 42}
    p = Pin(ns=ns)
    p.pin("x")
    p.signal_update()
    assert p.signal != {}
    body = p.signal["pinned"]
    assert "x" in body


def test_signal_missing_var():
    ns = {}
    p = Pin(ns=ns)
    p.pin("missing_var")
    p.signal_update()
    assert p.signal != {}
    body = p.signal["pinned"]
    assert "not found" in body


def test_signal_multiple_pins():
    ns = {"a": 1, "b": 2}
    p = Pin(ns=ns)
    p.pin("a")
    p.pin("b")
    p.signal_update()
    assert p.signal != {}
    body = p.signal["pinned"]
    assert "a" in body
    assert "b" in body


def test_signal_sorted():
    ns = {"z": 1, "a": 2}
    p = Pin(ns=ns)
    p.pin("z")
    p.pin("a")
    p.signal_update()
    assert p.signal != {}
    body = p.signal["pinned"]
    a_pos = body.index("a")
    z_pos = body.index("z")
    assert a_pos < z_pos


def test_isinstance_check():
    p = Pin()
    assert isinstance(p, BaseSkill)
