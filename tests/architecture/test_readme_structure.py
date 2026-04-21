"""test_readme_structure — Every package directory has README.md."""
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_every_package_has_readme():
    """Every directory containing __init__.py has README.md (excluding tests/ directories).

    Only boundary-layer components (directories with CONTEXT.md) require README.md.
    Packages without CONTEXT.md are implementation details and do not need a README.
    """
    missing = []
    for init in (_REPO_ROOT / "src" / "vessal").rglob("__init__.py"):
        pkg_dir = init.parent
        if "__pycache__" in str(pkg_dir):
            continue
        # co-located test directories don't need README.md
        if "tests" in pkg_dir.parts:
            continue
        # Only boundary-layer components (directories with CONTEXT.md) require README.md.
        # Packages without CONTEXT.md are implementation details.
        if not (pkg_dir / "CONTEXT.md").exists():
            continue
        if not (pkg_dir / "README.md").exists():
            missing.append(str(pkg_dir))
    assert missing == [], "Missing README.md:\n" + "\n".join(missing)
