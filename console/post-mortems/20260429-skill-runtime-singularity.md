# 2026-04-29 — Skill Runtime Singularity

## What broke
After `vessal create` + `vessal start`, the Console showed no chat tab even
though chat was a loaded Skill. User-visible symptom: the entire Skill UI tab
row was empty.

## Root cause (Five Whys)
1. Why no chat tab? `/skills/ui` returned an empty list.
2. Why empty? `<project>/skills/bundled/chat/ui/index.html` did not exist.
3. Why missing? `vessal create`'s `shutil.copytree(... ignore=ignore_patterns(
   "ui", "search", "audio", "vision"))` excluded the path.
4. Why "ui"? The intent was to skip the four top-level SkillHub-distributed
   Skill directories (`vessal/skills/ui/` etc.) because they ship as separate
   downloads.
5. Why did the exclusion eat nested ui? `shutil.ignore_patterns` runs the
   glob at every directory level, so `chat/ui/` matched too.

## Why this surfaced
Two prior architectural choices conspired:
- **Bundled-copy model** — every project carries a full duplicate of
  `vessal.skills.*` under `skills/bundled/`. This duplication exists
  *because* `skill_paths` was a hand-rolled discovery mechanism that
  required the directories to be inside the project.
- **Negative ignore filter** — to keep heavy Skills out of the default
  copy, we wrote a recursive ignore glob instead of a positive allowlist.

A positive allowlist (`for name in DEFAULT_PROJECT_SKILLS: copytree(...)`)
could not have produced this bug.

## Systemic fix
Eliminate the duality. `<project>/skills/<name>/` is the single source of
truth at runtime, registered into the project venv via a `.pth` file.
`SkillLoader` resolves Skills via `importlib.import_module("skills.<name>")`.
The four heavy SkillHub Skills are deleted from the vessal package; they
live in SkillHub.

## Prevention
- **R1** (Single Source of Truth): the bundled copy model was a textbook R1
  violation; the new model has exactly one Skill source at runtime.
- **R6** (Native Mechanism First): `skill_paths` reinvented Python's import
  system. The replacement (`.pth` + `importlib`) is 50 years of standard
  Python.
- **Negative filtering anti-pattern**: when an exclusion list grows past
  one item, switch to a positive list. Negative lists silently capture
  unintended matches.

## What we did NOT do
- Did not preserve a "vessal.skills.*-runtime-fallback" code path in
  Hull. With `.pth` registration the project owns its Skills end-to-end;
  fallbacks would re-introduce the duality.
- Did not write a `vessal sync-skills` command yet. If a future vessal
  release adds a new built-in Skill, users copy it manually or via
  `skill_manager.download_skill`. A first-class sync command is a separate
  PR (out of scope here).
