---
name: regex-danger-zone
description: >
  Mandatory rules and comment format for modifying regex patterns in
  _regex.py or demacro.py. Load before touching ANY regex pattern or
  the build_dictionary() elif chain.
---

## DANGER ZONE: Rules for Touching the Regex

**Do not touch these things without an explicit instruction and a prior failing test:**

1. **Any lambda or constant in `_regex.py`.** They are interdependent; changing
   one breaks others in non-obvious ways that only appear on edge-case inputs.

2. **Named capture groups.** `content_replacement()` reconstructs macro expansions
   by calling `arg.group('arg1')`, `arg.group('arg2')`, etc. Renaming any
   group silently breaks argument substitution for every macro that uses it.

3. **The `elif` chain order in `build_dictionary()`.** `\edef` must expand its
   content immediately using the *current* `macro_dict` state, unlike `\def`.
   The order encodes this semantic. Reordering it produces wrong expansions.

---

## Mandatory comment block

Before modifying any pattern, add this above it:

```python
# MATCHES: \newcommand{\cmdname}[N][default]{body}
# CAPTURES:
#   new_com_csname   → the command name, e.g. "mycommand"
#   new_com_num_args → the optional [N] argument count, e.g. "2"
#   new_com_default1 → first optional default value
#   new_com_content  → the replacement body
# LIMITATIONS:
#   - Does not handle \newcommand* (starred form; irrelevant for expansion)
#   - Does not handle @ in command names outside \makeatletter blocks
```

Commit this comment block in a **separate commit** before making any functional
change. This is what allows future sessions to understand intent without
re-deriving it from the regex syntax.

---

## The regex engine invariant

All patterns assume preprocessing has produced a flat single-line string with
at most one ASCII space between tokens. The pattern fragment ` ?(?<arg1>...)`
is correct as written — do not add `\s+` or multiline flags unless you
understand why this invariant exists.

---

## The Regex Torture Test

Before committing any change to `_regex.py` or the `find_all` pattern in
`demacro.py`, you must run the regex torture test and ensure it passes. This
test is located in `tests/test_demacro.py` and uses the fixture
`tests/fixtures/regex_torture_test.tex`. This test ensures that your change
does not break any previously fixed edge cases.

After every bug fix (Step 6.5 in coding-agent), add a minimal, non-failing
version of the problematic syntax to `tests/fixtures/regex_torture_test.tex`
with a comment: `%% From BUG-N: <what this tests>` — use `%%` not `%` so
the comment is not picked up by the regex calls.

---

## Per-file ruff ignores (do not "fix" these)

From `pyproject.toml`:
- `_regex.py` and `demacro.py`: E501, E731, UP031 are intentionally suppressed.
  Lambda pattern-builders and %-formatting are there because `{}` in f-strings
  would require double-escaping regex `{N}` quantifiers. NEVER convert these.
- F507 false-positives in `demacro.py`: ruff miscounts `%s` in helpers that
  expand to multi-placeholder strings. The code is correct.
- `find_packages.py`: E501, UP031 — same reason (regex pattern construction).
- `unfold.py`: E501 — long regex pattern lines that cannot be meaningfully shortened.
