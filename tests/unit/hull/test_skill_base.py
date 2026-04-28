"""test_skill_base — SkillBase abstract interface contract."""
import pytest
from vessal.ark.shell.hull.skill import SkillBase


def test_skillbase_cannot_be_instantiated_directly():
    """SkillBase is abstract — direct instantiation raises TypeError."""
    with pytest.raises(TypeError):
        SkillBase()


def test_concrete_skill_must_define_name_and_description():
    """A concrete skill without name/description raises on class definition."""
    with pytest.raises(TypeError):
        class BadSkill(SkillBase):
            pass


def test_concrete_skill_with_required_attrs():
    """A well-formed concrete skill instantiates and has defaults."""
    class GoodSkill(SkillBase):
        name = "test"
        description = "A test skill."

    s = GoodSkill()
    assert s.name == "test"
    assert s.description == "A test skill."
    assert s.guide == ""
    assert not hasattr(s, "_signal_output")


def test_signal_is_noop_by_default():
    """Default _signal() returns None."""
    class Minimal(SkillBase):
        name = "minimal"
        description = "Minimal."

    s = Minimal()
    result = s._signal()
    assert result is None


def test_signal_can_be_overridden():
    """Subclass overrides _signal() to return (title, body) tuple."""
    class Custom(SkillBase):
        name = "custom"
        description = "Custom."
        def __init__(self):
            super().__init__()
            self.data = "hello"
        def _signal(self):
            return ("custom", f"data={self.data}")

    s = Custom()
    result = s._signal()
    assert isinstance(result, tuple)
    assert result == ("custom", "data=hello")


def test_isinstance_check():
    """SkillBase instances pass isinstance check."""
    class MySkill(SkillBase):
        name = "my"
        description = "My."

    s = MySkill()
    assert isinstance(s, SkillBase)
