# write-note skill

## Trigger

Load this skill whenever the user asks you to:
- "write a note about X"
- "write a prompt about X"
- "make a note on X"
- "create a note for X"
- "jot down X"
- or any similar phrasing that amounts to capturing an idea, plan, or
  instruction for future reference.

## Rule

**Notes always go in `docs/notes/`** — never anywhere else unless the user
explicitly names a different path.

- If a relevant file already exists in `docs/notes/`, update it.
- Otherwise, create a new file: `docs/notes/<descriptive_slug>.md`.
- Use clear markdown structure. No frontmatter needed.
- After writing, tell the user the filename you wrote to.

## What does NOT count as a note

- Bug entries → `BUGS.md`
- TODO / enhancement items → `TODO.md`
- Memory (user preferences, project facts) → `.claude/projects/.../memory/`
- Skill definitions → `.claude/skills/<name>/SKILL.md`
