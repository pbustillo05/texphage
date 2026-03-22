---
name: bug-management
description: >
  The BUGS.md and TODO.md format, duplicate-check protocol, and commit
  conventions for bug and test lifecycle management. Load when creating,
  updating, or closing bug entries.
---

## BUGS.md entry format

```markdown
## BUG-<N>: <short title>

- **severity**: CRITICAL | HIGH | MEDIUM | LOW
- **root_cause_pattern**: incorrect_expansion | missed_expansion | brace_mismatch |
  environment_error | package_stripping | verbatim_corruption | preprocessing |
  compilation_timeout | unrecognised_definition_pattern | other
- **failure_mode**: A | B | C   ← from the failure-taxonomy skill
- **seen_in**: [2401.12345, 2312.09876]
- **description**: 2–3 sentences grounded in compile logs, demacro_report.json,
  or visual_diff PNGs. Include the texdef output if Mode A/B.
- **relevant_code_location**: src/texphage/demacro.py — build_dictionary(), \newcommand branch
- **relevant_latex_docs**: https://ctan.org/pkg/xparse
- **reproduction**: minimal .tex snippet
- **first_seen**: YYYY-MM-DD
- **last_seen**: YYYY-MM-DD
- **status**: OPEN
```

---

## Duplicate check rule

Before creating a new BUGS.md entry, check for an existing bug with the same
`root_cause_pattern` and similar context (same macro definition style, same
package). If found: update its `seen_in` list and `last_seen` date instead
of creating a duplicate.

---

## Fixture creation rule

Every new bug entry must be accompanied by a reproduction snippet as a fixture
file: `tests/fixtures/bug_N_<short_name>/main.tex`.

For quarterly audit findings: `tests/fixtures/audit_<pattern_name>/main.tex`.

`tests/fixtures/` is committed — the test suite must never depend on external
data.

---

## TODO.md vs BUGS.md distinction

- **BUGS.md** — strictly for regressions: cases where the pipeline's output is
  provably incorrect vs. what TeX produces. Every entry needs a reproduction
  snippet.
- **TODO.md** — planned features, enhancements, and very low-priority edge
  cases that are not regressions. Also: new features suggested by users or
  Gemini research.

Never mix them. If unsure: if you can write a minimal .tex snippet that
demonstrates wrong output today, it's a bug. If it's about adding new
capability, it's a TODO.

**When to use TODO.md:**
- When the user suggests a new feature (e.g., "Add support for `pgfkeys`").
- When the Quarterly Pattern Audit discovers a new, low-prevalence macro pattern.
- When a bug is discovered that is a very obscure edge case with minimal
  impact, the user may decide to log it in `TODO.md` instead of `BUGS.md`.

---

## Commit message format

```
fix(demacro): handle <construct> in <definition style> (BUG-N)

<2–3 sentences: what was wrong, what changed, why the fix is correct.>
```

```
test: add failing test for BUG-N (fails before fix)
test: run <run_id>, N new bugs, M updated
chore: mark BUG-N IN_PROGRESS
docs: update known limitations
```

---

## Bug lifecycle

1. **OPEN** — identified, not yet being worked on.
2. **IN_PROGRESS** — commit `chore: mark BUG-N IN_PROGRESS` when starting work.
3. **PARTIAL** — unit tests pass but end-to-end still fails; describe what remains.
4. **FIXED** — only after: regression test passes AND `README.md` limitations
   updated AND the fix is committed. Mark with `fixed: <date>`.

---

## Safety Rules (Non-Negotiable)

These apply in every session, not just agent runs.

1. **Never delete or modify working regex patterns without a prior failing test.**
   If you can't write a test that fails before your change, you don't understand
   the bug well enough to fix it.

2. **If you don't understand a LaTeX construct, ask.** Add the bug as MEDIUM,
   create the fixture, and ask the user for the CTAN documentation link.
   Do not guess at the meaning of TeX macros.

3. **Never commit `tests/runs/`**, tarballs, compiled PDFs, or cache files.
   These are in `.gitignore` for a reason. Run `git status` before every
   commit and verify the staged files look right.

4. **Every bug fix must have a permanent regression test** in `test_pipeline.py`
   before it is marked FIXED. A fix without a regression test will silently
   reappear in future sessions.

5. **After every fix, check `README.md`** "Known limitations" section. If the fix
   adds a previously unsupported construct, remove it from limitations. If it
   reveals a new limitation, add it.

6. **Commit messages must follow Conventional Commits** + BUG-N reference:
   `fix(demacro): <description> (BUG-N)`
   `test: <description> (BUG-N)`
   `docs: <description>`

7. **After any change to `_regex.py` or `demacro.py`**, run the full test suite
   and both linters before committing:
   ```bash
   pytest tests/ -v && ruff check src/ && mypy src/texphage/
   ```

8. **Every test must assert the positive case, grounded in playground output.**
   `assert 'bar' not in expanded` alone is not enough — also assert what IS
   there, using a value verified by `compile_snippet`. Without this anchor,
   a test can pass even when the output is wrong.

9. **Verbatim environment fixes (Mode C) always name the source package.**
   Add a comment next to every entry in `_VERBATIM_ENVS` identifying which
   package defines it and why it needs protection. This prevents future agents
   from removing entries they don't understand.
