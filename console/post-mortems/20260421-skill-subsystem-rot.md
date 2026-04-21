# Skill Subsystem Rot — Post-Mortem

Date: 2026-04-21
Related PR: #13 (feature/skill-subsystem-bugs-fix)

## Root Cause

Two objects named `skills` existed concurrently in the Cell namespace:

1. `SkillsManager` — a class under `src/vessal/ark/shell/hull/` that held the
   Agent-facing `load()`/`unload()`/`search_hub()`/... API. It was hard-injected
   into Cell namespace under the key `skills` during Hull init.
2. `Skills(SkillBase)` — an empty shell under `src/vessal/skills/skills/` that
   served as the Console "Skill inventory" UI identity. Loaded via the normal
   built-in Skill path if configured in `hull.toml`.

When both were active, the loader ran `self._cell.set("skills", Skills_instance)`
and overwrote the `SkillsManager` reference in place. Subsequent Agent calls
of the form `skills.load(...)` now dispatched on `Skills` — which had no such
method — and raised `AttributeError`.

Five Whys:
  1. Why crash? Two objects shared ns key `skills`.
  2. Why same key? One exposed the Python interface, the other the UI identity; both used the label `skills`.
  3. Why two objects? The Python interface needed a `Hull` handle and was placed
     in `hull/` for that reason.
  4. Why no guard? The loader did not validate that the key was unused.
  5. Why not one object? Responsibility ("Skill management + inventory view")
     was one concept split across two locations by constructor convenience.

## Impact

Confirmed observable impact:
- Any sequence `skills.load("skills")` followed by `skills.load(...)` raised
  `AttributeError` at runtime.
- Console's Skill inventory tab was unreachable on a default `vessal init`
  project because the UI identity was not included in the default skill list.
- Architecture tests missed both problems because `SkillsManager` lived
  outside the scanned `src/vessal/skills/` tree.

Scope: development-time only; no production release shipped with the collision.

## Prevention

Structural:
  - `SkillsManager` merged into `Skills(SkillBase)` at
    `src/vessal/skills/skills/skill.py`. Single class, single name, single
    load path. Hull handle delivered via `_bind_hull(hull)` post-instantiation
    hook.
  - `hull/skills_manager.py` deleted.
  - Default `hull.toml` includes `"skills"` so new projects boot with the
    inventory tab present.

Regression tests:
  - `src/vessal/skills/skills/tests/test_skills.py` — full `Skills` class contract.
  - `src/vessal/ark/shell/hull/tests/test_bind_hull_hook.py` — loader calls
    `_bind_hull` after ns injection.
  - `src/vessal/ark/shell/hull/tests/test_hull_startup_no_skills_manager.py` —
    Hull does not import `SkillsManager` and does not pre-inject `skills`.

System defenses:
  - `tests/architecture/test_no_ns_collision.py` — every Skill `.name` is
    unique among built-ins and disjoint from Hull-reserved keys.
  - `tests/architecture/test_skill_server_uses_static_router.py` — AST-check
    bans the legacy `_hull_api/_static_cache/_make_static_handler` boilerplate
    in future `server.py` files.
  - `tests/smoke/test_skill_scaffold_boot.py` — scaffold→load end-to-end
    catches any future drift in the generated `__init__` signature.

Ancillary cleanup bundled into the same PR:
  - `StaticRouter` extracted; `chat`/`skills`/`ui` servers converted.
  - heartbeat class renamed `Skill` → `Heartbeat`.
  - 4 `__init__.py` files collapsed to the canonical single-line form.
  - `audio` / `search` / `vision` / `ui` migrated to `vessal-skills`
    on branch `feature/migrate-initial-skills` (not pushed).
