"""test_hull_facade.py — guard that Hull remains a single facade class.

After the 2026-04-20 Shell/Hull layering refactor (P3), Hull's implementation
is split across four mixins, but `Hull` itself is still the only class an
external caller instantiates. This test prevents regression:
  (1) `from vessal.ark.shell.hull import Hull` works.
  (2) Mixins are not re-exported from `vessal.ark.shell.hull` __init__.
  (3) Hull's MRO lists all four mixins.
"""
from __future__ import annotations


def test_hull_is_importable_from_package_root() -> None:
    from vessal.ark.shell.hull import Hull
    assert Hull.__name__ == "Hull"


def test_hull_mixins_not_exported_from_package() -> None:
    import vessal.ark.shell.hull as pkg
    exported = getattr(pkg, "__all__", [])
    forbidden = {"HullInitMixin", "HullSkillsMixin", "HullCompactionMixin", "HullRuntimeMixin"}
    assert forbidden.isdisjoint(exported), (
        f"Hull mixins must stay internal; found in __all__: {forbidden & set(exported)}"
    )


def test_hull_composes_all_four_mixins() -> None:
    from vessal.ark.shell.hull.hull import Hull
    from vessal.ark.shell.hull.hull_init_mixin import HullInitMixin
    from vessal.ark.shell.hull.hull_skills_mixin import HullSkillsMixin
    from vessal.ark.shell.hull.hull_compaction_mixin import HullCompactionMixin
    from vessal.ark.shell.hull.hull_runtime_mixin import HullRuntimeMixin
    for mixin in (HullInitMixin, HullSkillsMixin, HullCompactionMixin, HullRuntimeMixin):
        assert issubclass(Hull, mixin), f"Hull must inherit from {mixin.__name__}"
