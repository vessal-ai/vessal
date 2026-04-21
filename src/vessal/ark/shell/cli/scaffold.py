"""scaffold.py — Skill scaffold writer for the Vessal CLI."""
from __future__ import annotations

from pathlib import Path

_DEFAULT_DESCRIPTION = "(functional description, \u226415 words)"


def write_skill_scaffold(
    base: Path,
    skill_name: str,
    *,
    with_tutorial: bool = True,
    with_ui: bool = True,
    with_server: bool = True,
) -> None:
    """Write a Skill scaffold into `base`.

    Emits __init__.py, skill.py, SKILL.md, requirements.txt, tests/. Optionally
    emits TUTORIAL.md / ui/index.html / server.py based on flags. The Skill's
    description is a SKILL.md template placeholder; the wizard does not ask for it.
    """
    class_name = "".join(part.capitalize() for part in skill_name.split("_"))
    (base / "tests").mkdir(parents=True, exist_ok=True)

    (base / "__init__.py").write_text(
        f'"""{skill_name} — {_DEFAULT_DESCRIPTION}"""\n'
        f'from .skill import {class_name} as Skill\n\n'
        f'__all__ = ["Skill"]\n',
        encoding="utf-8",
    )
    (base / "skill.py").write_text(
        f'"""skill.py — {skill_name} Skill implementation."""\n'
        f'from __future__ import annotations\n'
        f'\n'
        f'from vessal.ark.shell.hull.skill import SkillBase\n'
        f'\n'
        f'\n'
        f'class {class_name}(SkillBase):\n'
        f'    name = "{skill_name}"\n'
        f'    description = "{_DEFAULT_DESCRIPTION}"\n'
        f'\n'
        f'    # ── Protocol conventions ──\n'
        f'    # 1. description ≤15 words, describe function not method names\n'
        f'    # 2. _signal() only shows state, does not expose method signatures\n'
        f'    # 3. SKILL.md is the only place containing method signatures\n'
        f'    # 4. _prompt() only contains behavior rules, not the API\n'
        f'\n'
        f'    def __init__(self, ns=None):\n'
        f'        super().__init__()\n'
        f'        self._ns = ns\n'
        f'        # Protect internal state with _ prefix to prevent Agent from bypassing the API\n'
        f'        # self._cache = {{}}\n'
        f'\n'
        f'    # Public methods: callable by Agent. Must produce observable feedback (print/return value/namespace diff)\n'
        f'    # def my_function(self, arg: str) -> str:\n'
        f'    #     """Tool description."""\n'
        f'    #     return arg\n'
        f'\n'
        f'    # Signal (optional, called each frame, returns (title, body) tuple)\n'
        f'    # def _signal(self) -> tuple[str, str] | None:\n'
        f'    #     return ("{skill_name}", "status info, no method names")\n',
        encoding="utf-8",
    )
    (base / "SKILL.md").write_text(
        f'---\n'
        f'name: {skill_name}\n'
        f'version: "0.1.0"\n'
        f'description: "{_DEFAULT_DESCRIPTION}"\n'
        f'author: ""\n'
        f'license: "Apache-2.0"\n'
        f'requires:\n'
        f'  skills: []\n'
        f'---\n'
        f'\n'
        f'# {skill_name}\n'
        f'\n'
        f'(Operation manual. Agent reads via `print({skill_name}.guide)`.\n'
        f'Keep concise: method signatures, usage examples, and hard rules only.)\n'
        f'\n'
        f'## Methods\n'
        f'\n'
        f'List each public method\'s signature + one-line purpose:\n'
        f'\n'
        f'    my_function(arg: str) -> str    # Do X, return Y\n'
        f'\n'
        f'## Protocol conventions\n'
        f'\n'
        f'Vessal Skill authoring rules \u2014 violating any of these is a bug.\n'
        f'\n'
        f'1. `description` \u226415 words; describe function, not method names.\n'
        f'2. `_signal()` only surfaces state; never expose method signatures.\n'
        f'3. `SKILL.md` is the single source of truth for method signatures.\n'
        f'4. `_prompt()` only contains behavior rules, never the API.\n'
        f'5. Protect internal state with the `_` prefix so the Agent cannot bypass the API.\n'
        f'\n'
        f'## Common pitfalls\n'
        f'\n'
        f'- Placing method names in `_signal()` or `description` (they belong here).\n'
        f'- Using print/log inside `_signal()` \u2014 it must stay pure.\n'
        f'- Forgetting to observe side effects (return value, namespace diff, or print).\n',
        encoding="utf-8",
    )
    (base / "requirements.txt").write_text("", encoding="utf-8")
    (base / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (base / "tests" / f"test_{skill_name}.py").write_text(
        f'"""test_{skill_name} — {skill_name} Skill basic tests"""\n\n\n'
        f'def test_{skill_name}_placeholder():\n'
        f'    """Placeholder test; replace with real tests."""\n'
        f'    pass\n',
        encoding="utf-8",
    )

    if with_tutorial:
        (base / "TUTORIAL.md").write_text(
            f'# {skill_name} \u2014 Tutorial\n'
            f'\n'
            f'Runnable examples beside this file are part of the tutorial.\n'
            f'Read them alongside this document.\n'
            f'\n'
            f'## External references\n'
            f'\n'
            f'- Vessal Skill protocol: https://github.com/vessal-ai/vessal/blob/main/references/whitepaper/\n'
            f'- SkillBase API: `from vessal.ark.shell.hull.skill import SkillBase`\n'
            f'\n'
            f'## Common pitfalls\n'
            f'\n'
            f'- Agent-visible print: every public method must yield observable feedback\n'
            f'  (print, return value, or namespace mutation). Silent success is a bug.\n'
            f'- Internal state leak: any attribute without a leading `_` is Agent-visible.\n'
            f'  Protect helpers with `_` to prevent the Agent from bypassing your API.\n'
            f'- `_signal()` side effects: keep it pure; it is called every frame.\n',
            encoding="utf-8",
        )

    if with_ui:
        ui_dir = base / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "index.html").write_text(
            f'<!doctype html>\n'
            f'<html><head><meta charset="utf-8"><title>{skill_name}</title></head>\n'
            f'<body>\n'
            f'  <h1>{skill_name}</h1>\n'
            f'  <button id="ping">Call /skills/{skill_name}/hello</button>\n'
            f'  <pre id="out"></pre>\n'
            f'  <script>\n'
            f'    document.getElementById("ping").addEventListener("click", async () => {{\n'
            f'      const r = await fetch("/skills/{skill_name}/hello");\n'
            f'        document.getElementById("out").textContent = await r.text();\n'
            f'    }});\n'
            f'  </script>\n'
            f'</body></html>\n',
            encoding="utf-8",
        )

    if with_server:
        (base / "server.py").write_text(
            f'"""server.py — HTTP routes exposed by the {skill_name} Skill.\n'
            f'\n'
            f'Vessal Shell auto-mounts this module at /skills/{skill_name}/*\n'
            f'when the Skill is loaded (see SkillLoader.has_server).\n'
            f'"""\n'
            f'from __future__ import annotations\n'
            f'\n'
            f'\n'
            f'def hello(request):\n'
            f'    """Example route. Fetched by ui/index.html on button click."""\n'
            f'    return {{"message": "hello from {skill_name}"}}\n'
            f'\n'
            f'\n'
            f'# Routes exported to the Shell host.\n'
            f'# Each entry: (HTTP method, path suffix, handler).\n'
            f'routes = [\n'
            f'    ("GET", "/hello", hello),\n'
            f']\n',
            encoding="utf-8",
        )
