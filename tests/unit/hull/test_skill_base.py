"""test_skill_base — BaseSkill abstract interface contract."""
import pytest
from vessal.skills._base import BaseSkill


def test_baseskill_cannot_be_instantiated_directly():
    """BaseSkill is abstract — direct instantiation raises TypeError."""
    with pytest.raises(TypeError):
        BaseSkill()


def test_concrete_skill_must_define_name_and_description():
    """A concrete skill without name/description raises on class definition."""
    with pytest.raises(TypeError):
        class BadSkill(BaseSkill):
            pass


def test_concrete_skill_with_required_attrs():
    """A well-formed concrete skill instantiates and has defaults."""
    class GoodSkill(BaseSkill):
        name = "test"
        description = "A test skill."

    s = GoodSkill()
    assert s.name == "test"
    assert s.description == "A test skill."
    assert s.guide == ""
    assert s.signal == {}


def test_signal_update_is_noop_by_default():
    """Default signal_update() does nothing (signal stays empty dict)."""
    class Minimal(BaseSkill):
        name = "minimal"
        description = "Minimal."

    s = Minimal()
    s.signal_update()
    assert s.signal == {}


def test_signal_update_can_be_overridden():
    """Subclass overrides signal_update() to mutate self.signal."""
    class Custom(BaseSkill):
        name = "custom"
        description = "Custom."
        def __init__(self):
            super().__init__()
            self.data = "hello"
        def signal_update(self):
            self.signal = {"data": self.data}

    s = Custom()
    s.signal_update()
    assert s.signal == {"data": "hello"}


def test_isinstance_check():
    """BaseSkill instances pass isinstance check."""
    class MySkill(BaseSkill):
        name = "my"
        description = "My."

    s = MySkill()
    assert isinstance(s, BaseSkill)
