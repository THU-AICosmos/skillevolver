# Skill Template

Use this as the default structure for evolved skills.

```markdown
---
name: <skill-name>
description: <one-line reusable description>
---

# <Human-readable skill title>

## What This Skill Is For

- Describe the family of tasks this skill targets.
- Keep this at the level of patterns, not one benchmark item.

## Atomic Operations

### Operation 1: <name>
- Purpose: one reusable mechanical action
- When to use it:
- How to invoke it:
- File: `scripts/<tool>.py`

### Operation 2: <name>
- Purpose:
- When to use it:
- How to invoke it:
- File: `scripts/<tool>.py`

## Failure Lessons

### Failure: <short title>
- Symptom:
- Root cause:
- Evidence:
- Details file: `references/<failure-note>.md`

## Success Patterns

### Success: <short title>
- What worked:
- Why it worked:
- Contrast with the matching failure:
- Details file: `references/<success-note>.md`

## Decision Rules

- When you need <X> and constraints <Y> hold, do <Z>.
- When you observe <failure signal>, avoid <pattern> and switch to <alternative>.
- When compatibility with <interface / verifier / file format> matters, preserve <structural property>.

## Anti-Patterns / Do Not Overfit

- Do not hardcode:
- Do not assume:
- Do not copy directly from this task:

## References

- scripts/<tool>.py
- references/<doc>.md
```

Directory rule:

- executable reusable operations go in `scripts/`
- historical experience and evidence go in `references/`

Checklist before finalizing:

1. Could this skill still help on a related task with different filenames and constants?
2. Are the decision rules conditional rather than absolute?
3. Did you separate failures from successful contrasts?
4. Are bundled scripts atomic rather than end-to-end solvers?
