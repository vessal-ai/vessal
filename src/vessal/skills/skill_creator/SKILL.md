---
name: skill_creator
description: Create a new skill scaffold
---

# skill_creator

Generates a Skill directory scaffold under skill_paths. Creates 7 files including full protocol documentation and reference material that the AI can read to implement the Skill directly.

## Methods

skill_creator.create(name, description) — Create a scaffold directory

## Generated Structure

```
{name}/
  __init__.py       Exports the Skill class
  skill.py          Full protocol comments + skeleton code
  SKILL.md          Guide template
  CONTEXT.md        Formalin contract framework
  REFERENCE.md      Reference docs (whitepaper excerpts + example source)
  tests/
    __init__.py
    test_{name}.py  Test skeleton
```

## Usage

```python
skill_creator.create("code_review", "Code review tool")
# → Creates code_review/ directory under skill_paths[0] (7 files)
# 1. Read REFERENCE.md to understand the Skill protocol
# 2. Edit skill.py to fill in the implementation (remove comment blocks)
# 3. Edit SKILL.md to write the guide
# 4. Edit CONTEXT.md to write the contract
# 5. Edit tests/test_code_review.py to add tests
# 6. skills.load("code_review") to load
```

## Modifying an Existing Skill

Any Skill (including built-ins) can be modified: edit the file, then call skills.unload(name) → skills.load(name).
Modifications to built-in Skills will be overwritten when vessal is upgraded. For persistent changes, create a user Skill with the same name to override it.
