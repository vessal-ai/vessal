---
name: skill_creator
description: Create a new skill scaffold
---

# skill_creator

Generates a Skill directory scaffold under `skill_paths[0]`. Delegates to the same generator used by
the `vessal skill create` CLI, so the two surfaces always produce the same layout.

## Methods

skill_creator.create(name, description) — Create a scaffold directory

## Generated Structure

```
{name}/
  __init__.py
  skill.py          SkillBase subclass with protocol-convention comments
  SKILL.md          Frontmatter + guide template
  requirements.txt  (empty)
  tests/
    __init__.py
    test_{name}.py  Placeholder test
```

## Usage

```python
skill_creator.create("code_review", "code review tool")
# → Creates code_review/ under skill_paths[0]
# 1. Edit skill.py to implement
# 2. Edit SKILL.md to describe methods
# 3. Edit tests/test_code_review.py
# 4. skills.load("code_review") to load
```

## Modifying an Existing Skill

Any Skill (including built-ins) can be modified: edit the file, then `skills.unload(name)` →
`skills.load(name)`. Modifications to built-in Skills will be overwritten when vessal is upgraded;
for persistent changes, create a user Skill with the same name to override it.
