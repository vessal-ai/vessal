"""skill.py — skill_creator Skill implementation."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.skill import SkillBase


class SkillCreator(SkillBase):
    """Skill scaffold generator. Creates a protocol-compliant Skill directory structure under skill_paths.

    Attributes:
        _skill_paths: List of user Skill search paths.
    """

    name = "skill_creator"
    description = "create new skill scaffold"

    def __init__(self, ns: dict | None = None):
        super().__init__()
        self._skill_paths: list[str] = []
        if ns is not None:
            self._skill_paths = ns.get("skill_paths", [])

    def create(self, name: str, description: str) -> str:
        """Create a Skill directory scaffold (7 files) under skill_paths[0].

        Generated files: __init__.py, skill.py (with full protocol comments), SKILL.md (guide template),
        CONTEXT.md (Formalin contract), REFERENCE.md (reference docs),
        tests/__init__.py, tests/test_{name}.py (test scaffold).

        Args:
            name: Skill name (snake_case).
            description: One-line function description (≤15 chars, no method names).

        Returns:
            Operation result string.
        """
        if not self._skill_paths:
            return "Creation failed: skill_paths is empty, cannot determine target directory"

        base = Path(self._skill_paths[0]) / name
        if base.exists():
            return f"Creation failed: {name} already exists at {base}"

        class_name = "".join(part.capitalize() for part in name.split("_"))

        base.mkdir(parents=True)

        # __init__.py
        (base / "__init__.py").write_text(
            f'"""{name} — {description}"""\n'
            f"from .skill import {class_name} as Skill\n\n"
            f'__all__ = ["Skill"]\n',
            encoding="utf-8",
        )

        # skill.py — scaffold with full protocol comments
        (base / "skill.py").write_text(
            f'"""skill.py — {name} Skill implementation."""\n'
            f"from __future__ import annotations\n"
            f"\n"
            f"from pathlib import Path\n"
            f"\n"
            f"from vessal.ark.shell.hull.skill import SkillBase\n"
            f"\n"
            f"\n"
            f"class {class_name}(SkillBase):\n"
            f'    """(Replace with class description)\n'
            f"\n"
            f"    Attributes:\n"
            f"        _ns: Hull namespace reference (optional).\n"
            f"        _data_dir: Data persistence directory (optional).\n"
            f'    """\n'
            f"\n"
            f"    # ── Required ──\n"
            f'    name = "{name}"\n'
            f'    description = "{description}"  # ≤15 chars, function only, no method names\n'
            f"\n"
            f"    # ── Protocol spec (read before implementing; delete this comment block when done) ──\n"
            f"    #\n"
            f"    # Three-layer information separation:\n"
            f"    #   _prompt() → persistent layer: behavior rules injected into system prompt every frame\n"
            f"    #   guide    → manual layer: Agent prints on demand; cost to re-print = 1 frame\n"
            f"    #   _signal() → reminder layer: shows current state each frame; no method signatures\n"
            f"    #\n"
            f"    # Overridable methods:\n"
            f"    #   _signal() -> tuple[str, str] | None\n"
            f"    #       Returns (title, body). title is used as section header; body is signal content.\n"
            f"    #       Called every frame. Shows state only; never exposes method signatures.\n"
            f"    #\n"
            f"    #   _prompt() -> tuple[str, str] | None\n"
            f"    #       Returns (condition, methodology).\n"
            f"    #       Called every frame. Behavior rules only; no API reference.\n"
            f"    #       Rendered as: \"When {{condition}}: {{methodology}}\"\n"
            f"    #\n"
            f"    # Design rules:\n"
            f"    #   1. Internal state uses _ prefix (_inbox, _cache, etc.)\n"
            f"    #   2. Every public method must produce observable feedback (print, return value, or ns diff)\n"
            f"    #   3. SKILL.md guide is the only place that contains method signatures\n"
            f"    #   4. description ≤15 chars, function only, no method names\n"
            f"    #\n"
            f"    # Common ns keys:\n"
            f"    #   _data_dir: str      — data directory path (for persistence)\n"
            f"    #   _frame_log: list    — frame stream list\n"
            f"    #   _context_pct: int   — context usage percentage\n"
            f"    #   skill_paths: list   — Skill search paths\n"
            f"\n"
            f"    def __init__(self, ns: dict | None = None):\n"
            f"        super().__init__()\n"
            f"        self._ns = ns\n"
            f"        self._data_dir: Path | None = None\n"
            f"        if ns is not None:\n"
            f'            base = ns.get("_data_dir")\n'
            f"            if base:\n"
            f'                self._data_dir = Path(base) / "{name}"\n'
            f"                self._data_dir.mkdir(parents=True, exist_ok=True)\n"
            f"\n"
            f"    # ── Public methods (callable by Agent; must produce observable feedback) ──\n"
            f"\n"
            f"    # def my_method(self, arg: str) -> str:\n"
            f'    #     """Method description.\n'
            f"    #\n"
            f"    #     Args:\n"
            f"    #         arg: Parameter description.\n"
            f"    #\n"
            f"    #     Returns:\n"
            f"    #         Return value description.\n"
            f'    #     """\n'
            f"    #     return arg\n"
            f"\n"
            f"    # ── Optional overrides ──\n"
            f"\n"
            f"    # def _signal(self) -> tuple[str, str] | None:\n"
            f'    #     """Show current state each frame."""\n'
            f"    #     return None\n"
            f"\n"
            f"    # def _prompt(self) -> tuple[str, str] | None:\n"
            f'    #     """Inject behavior rules each frame."""\n'
            f"    #     return None\n",
            encoding="utf-8",
        )

        # SKILL.md — guide template
        (base / "SKILL.md").write_text(
            f"---\n"
            f"name: {name}\n"
            f'description: "{description}"\n'
            f"---\n"
            f"\n"
            f"# {name}\n"
            f"\n"
            f"(One-line positioning description. Agent reads this via `print({name}.guide)`.)\n"
            f"\n"
            f"## Methods\n"
            f"\n"
            f"<!-- guide is the only place with method signatures. Format: name.method(arg) — description -->\n"
            f"\n"
            f"{name}.method(arg) — (method description)\n"
            f"\n"
            f"## Usage\n"
            f"\n"
            f"```python\n"
            f"# Basic usage example\n"
            f'{name}.method("example")\n'
            f"```\n",
            encoding="utf-8",
        )

        # CONTEXT.md — Formalin contract framework
        title = " ".join(part.capitalize() for part in name.split("_"))
        (base / "CONTEXT.md").write_text(
            f"# {title}\n"
            f"\n"
            f"{description}.\n"
            f"\n"
            f"Responsible for:\n"
            f"- (list responsibilities)\n"
            f"\n"
            f"Not responsible for:\n"
            f"- (list out-of-scope responsibilities)\n"
            f"\n"
            f"## Constraints\n"
            f"\n"
            f"1. (list constraints)\n"
            f"\n"
            f"## Design\n"
            f"\n"
            f"(Design description. Use a mermaid diagram to describe data flow.)\n"
            f"\n"
            f"## Status\n"
            f"\n"
            f"### TODO\n"
            f"None.\n"
            f"\n"
            f"### Known Issues\n"
            f"None.\n"
            f"\n"
            f"### Active\n"
            f"None.\n",
            encoding="utf-8",
        )

        # tests/ — test scaffold
        tests_dir = base / "tests"
        tests_dir.mkdir()

        (tests_dir / "__init__.py").write_text("", encoding="utf-8")

        (tests_dir / f"test_{name}.py").write_text(
            f'"""test_{name} — {name} Skill unit tests."""\n'
            f"import pytest\n"
            f"\n"
            f"\n"
            f"@pytest.fixture\n"
            f"def skill(tmp_path):\n"
            f'    """Create a {name} instance with ns pointing to a temp directory."""\n'
            f"    from {name}.skill import {class_name}\n"
            f'    ns = {{"_data_dir": str(tmp_path)}}\n'
            f"    return {class_name}(ns=ns)\n"
            f"\n"
            f"\n"
            f"def test_name_and_description(skill):\n"
            f'    """name and description are correctly defined."""\n'
            f'    assert skill.name == "{name}"\n'
            f"    assert isinstance(skill.description, str)\n"
            f"    assert len(skill.description) <= 15\n"
            f"\n"
            f"\n"
            f"def test_signal_returns_none_or_tuple(skill):\n"
            f'    """_signal() returns None or a (str, str) tuple."""\n'
            f"    result = skill._signal()\n"
            f"    if result is not None:\n"
            f"        assert isinstance(result, tuple)\n"
            f"        assert len(result) == 2\n"
            f"        assert isinstance(result[0], str)\n"
            f"        assert isinstance(result[1], str)\n",
            encoding="utf-8",
        )

        # REFERENCE.md — reference documentation
        (base / "REFERENCE.md").write_text(
            self._build_reference(),
            encoding="utf-8",
        )

        return f"Created {name} ({base}). Read REFERENCE.md, then edit skill.py. When done, run skills.load('{name}')"

    def _build_reference(self) -> str:
        """Build REFERENCE.md content: SkillBase docstring + whitepaper excerpt + example source."""
        from vessal.ark.shell.hull.skill import SkillBase

        sections = []
        sections.append("# Skill Development Reference\n")
        sections.append(
            "This document is the complete reference for Skill development. After reading it you should be able to create a protocol-compliant Skill without consulting any other file.\n"
        )

        # 1. SkillBase docstring
        sections.append("## SkillBase Specification\n")
        sections.append("```")
        sections.append(SkillBase.__doc__ or "")
        sections.append("```\n")

        # 2. Key whitepaper excerpts (static text)
        sections.append("## Skill Architecture Key Points (from whitepaper)\n")
        sections.append(
            "### Dual-sided interface\n"
            'A Skill is not "Agent capability" — it is the interface between the Agent and the outside world. '
            "The inner face points toward the Agent (tool, signal, guide), defining what the Agent can do and perceive. "
            "The outer face points toward the world (server), defining how the world interacts with the Agent.\n\n"
            "### Skill class components\n"
            "The Skill class is loaded into the Cell's namespace and contains three component types:\n"
            "- **SOP metadata**: name, description, guide\n"
            "- **Tool**: Python methods; Agent calls via `skill_name.method()`\n"
            "- **Signal**: `_signal()` method; Kernel calls automatically each frame; returns `(title, body)` or None\n\n"
            "### Server separation\n"
            "Server is code separate from the skill class. Server is not loaded into the Cell; it runs outside the frame loop. "
            "Server communicates with the skill class via shared mutable data structures (e.g. thread-safe queue).\n\n"
            "### Discovery mechanism\n"
            "The Kernel knows nothing about skills. It discovers them via duck-typing:\n"
            "- Any object with a callable `_signal` method gets called\n"
            "- Tool methods are auto-discovered by scanning the namespace\n\n"
            "### Load / unload\n"
            "Loading is two-phase: (1) Hull injects the skill instance into the namespace, (2) starts the server (if present). "
            "Phase 2 failure rolls back phase 1.\n\n"
            "### Directory structure\n"
            "```\n"
            "skills/{name}/\n"
            "    __init__.py     exports Skill class\n"
            "    skill.py        Skill class (SOP + Tool + Signal)\n"
            "    SKILL.md        Guide text\n"
            "    CONTEXT.md      Formalin contract\n"
            "    REFERENCE.md    this file (reference docs)\n"
            "    server.py       Server code (optional)\n"
            "    tests/          test directory\n"
            "```\n"
        )

        # 3. Skill usage protocol from the system prompt (static excerpt)
        sections.append("## Skill Usage Protocol from Agent Perspective\n")
        sections.append(
            "Skills extend Agent capabilities. A Skill is an instance object in the namespace, called via `skill_name.method()`.\n\n"
            "**Before using any Skill for the first time, you must `print(name.guide)`. No exceptions.**\n\n"
            "The loaded Skill list is shown in the signal section (name + one-line description only). The description tells you what the Skill can do; the guide tells you how.\n"
        )

        # 4. Example Skill source (dynamically read)
        sections.append("## Example Skills\n")

        # Pin — minimal example
        sections.append("### class Pin (minimal example)\n")
        try:
            pin_path = Path(__file__).parent.parent / "pin" / "skill.py"
            pin_source = pin_path.read_text(encoding="utf-8")
            sections.append(f"```python\n{pin_source}```\n")
        except (OSError, IOError):
            sections.append("(unable to read pin source)\n")

        # Memory — full example
        sections.append("### class Memory (full example)\n")
        try:
            memory_path = Path(__file__).parent.parent / "memory" / "skill.py"
            memory_source = memory_path.read_text(encoding="utf-8")
            sections.append(f"```python\n{memory_source}```\n")
        except (OSError, IOError):
            sections.append("(unable to read memory source)\n")

        return "\n".join(sections)
