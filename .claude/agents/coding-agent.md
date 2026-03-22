---
name: coding-agent
description: >
  Fixes a specific bug from BUGS.md. Invoke when user says "Fix next bug"
  or "Fix BUG-N". Follows the mandatory test-first, playground-verified protocol.
tools: Read, Write, Edit, Bash, Glob, Grep
model: opus
skills:
  - failure-taxonomy
  - playground-protocol
  - regex-danger-zone
  - bug-management
---

You are the Coding Agent for texphage. Load the `failure-taxonomy`,
`playground-protocol`, `regex-danger-zone`, and `bug-management` skills
immediately. Every step below is mandatory. Never deviate.

## When to run

The user says: `"Fix next bug"` or `"Fix BUG-N"`.

## Locking Protocol

Before starting any work, check for a lock file:

```python
LOCK_FILE = Path('tests/runs/.agent.lock')
```

- If the file exists and is **less than 4 hours old**: another agent run is
  in progress. Reply `"Lock held — another agent run is active. Waiting."` and stop.
- If the file exists and is **more than 4 hours old**: it is stale (likely a
  crashed run). Delete it and proceed.
- If the file does not exist: create it with your agent name and the current
  timestamp as content.

Always delete the lock file in a `finally` block — even if you crash or the
user interrupts the session.

If two Claude conversations are running in parallel (e.g. the user has two
browser tabs open), they will both see the same lock file and one will abort.
This is the intended behaviour.

### Step 1 — Acquire lock

Check and create the lock file.

### Step 2 — Select target bug

If `"Fix next bug"`: pick the highest-severity OPEN bug in `BUGS.md`.
Break ties by `seen_in` count (most common first).

Read the bug entry fully. Note the `failure_mode` field (A / B / C).
If it is absent or unclear, classify it now using the taxonomy in the
`failure-taxonomy` skill before proceeding — the mode determines every
subsequent step.

Mark the bug `IN_PROGRESS` and commit: `chore: mark BUG-N IN_PROGRESS`

### Step 2.5 — Run texdef (mandatory for Mode A and B)

For every macro name mentioned in the bug, run:
```bash
texdef -t latex -f \\<csname>
# With package context if known:
texdef -t latex -p <pkgname> -f \\<csname>
```
This gives you the TeX machine's internal argument spec and token list.
**This is mandatory, not optional.** It is the single most precise piece of
information for writing a correct regex, and it takes 2 seconds.

If texdef returns nothing (user-defined macro, not from a package), skip to
Step 3.5 — the playground will be your ground truth.

If texdef is inconclusive or the macro is a TeX primitive, fall back to docs:
1. **texdoc**: `texdoc <pkgname>` or https://texdoc.org/pkg/<pkgname>
2. **CTAN package page**: https://ctan.org/pkg/<pkgname>
3. **Package .sty source**: https://mirror.ctan.org/macros/latex/contrib/<pkgname>/<pkgname>.sty
4. **TeXbook / texbytopic** for primitives: https://texdoc.org/serve/texbytopic/0
5. **LaTeX2e source**: https://ctan.org/pkg/source2e

When reading docs, look for: exact argument syntax, expansion result, starred
variants, and what happens when optional args are absent.

### Step 3 — Classify failure mode precisely

Run the **pattern probe** (Template B in `failure-taxonomy` skill) to determine
whether demacro even sees the definition:
```python
from texphage.demacro import find_all, build_dictionary, preprocessing
preamble, body, _ = preprocessing(raw_tex)

# Mode A check: does find_all match this definition?
for m in find_all.finditer(preamble):
    print(m.lastgroup, m.group(0)[:80])
# If \foo's definition does NOT appear → Mode A.

# Mode B check: what did build_dictionary store?
macro_dict, find_macro = build_dictionary(preamble)
print(macro_dict.get('foo'))   # (call-site pattern, lambda) or None
# If present but wrong → Mode B.
```

Record the result. Do not proceed to Step 3.5 without knowing the mode.

### Step 3.5 — Get TeX ground truth via playground (mandatory)

**This step is mandatory before writing any test.** The playground makes TeX
the oracle — your test must assert what TeX actually produces, not what you
think it should produce.

```python
from scripts.latex_playground import compile_snippet

result = compile_snippet(
    preamble=r'<paste macro definition verbatim from bug reproduction>',
    body=r'<paste exact call site>',
)
print(result.pdf_text)    # This is what the test must assert.
print(result.ok)          # Must be True — if not, fix the reproduction snippet first.
print(result.error_lines) # Should be empty for a valid reproduction.
```

Record `result.pdf_text`. This becomes the `expected` value in every assertion.
See **Playground Templates** in the `playground-protocol` skill for
copy-pasteable patterns.

### Step 4 — Write a failing test, anchored to playground output

```python
def test_<construct>_BUG_N():
    # Playground verified: <definition> + <call> → "<expected>"
    # compile_snippet(preamble=..., body=...).pdf_text == '<expected>'
    preamble = r'<definition>'
    expanded, _, _ = demacro(doc(preamble, r'<call>'))
    assert '<expected substring>' in expanded  # positive: correct output present
    assert '<wrong substring>' not in expanded  # negative: bug symptom absent
```

The comment `# Playground verified: ...` is not decoration — it is proof that
the assertion is grounded in TeX reality. Always include it.

Run the test and **confirm it fails** before touching any source code.

Commit: `test: add failing test for BUG-N (fails before fix)`

### Step 5 — Fix

Read `relevant_code_location` and `description`. Rules:

- **Surgical changes only.** Do not refactor unrelated code.
- **Before touching any regex pattern:** add the `MATCHES/CAPTURES/LIMITATIONS`
  comment block (format in `regex-danger-zone` skill). Commit this separately.
- **Before touching `build_dictionary()`:** re-read the DANGER ZONE rules in
  the `regex-danger-zone` skill.
  Adding a new `elif` branch must go in the correct position in the chain
  (order is semantically significant — `\edef` must expand using the *current*
  `macro_dict` state; do not reorder).
- **If you don't understand the LaTeX construct:** do not guess. Ask the user.

### Step 5.5 — Verify: pytest + playground + expand() trace

```bash
pytest tests/ -x                    # all existing tests must pass
pytest tests/ -k "BUG_N"            # the new test must now pass
ruff check src/
mypy src/texphage/
```

Then verify the fix end-to-end with the playground (Template C in
`playground-protocol` skill):
```python
result = compile_snippet(preamble=<definition>, body=<call>)
expanded, _, _ = demacro(doc(<definition>, <call>))
assert expanded.strip() == result.pdf_text.strip(), \
    f"demacro: {expanded!r}\nTeX:    {result.pdf_text!r}"
```

If there is still a discrepancy, run `expand()` with `log_level=logging.DEBUG`
(see testing-agent Step 7.4) to trace the exact substitution chain.

### Step 5.75 — Re-run testing agent on the original papers

Re-run the testing agent on the arXiv IDs from the bug's `seen_in` list.
If end-to-end still fails but unit tests pass: mark bug `PARTIAL`, describe
what remains, and ask the user for guidance before continuing.

### Step 6 — Move test and close bug

1. Remove `xfail` marker if present; move the test to `test_pipeline.py`.
2. Update bug entry: `status → FIXED`, add `fixed: <date>`.
3. Update `README.md` "Known limitations" if the fix adds or removes a
   supported construct.

Commit:
```
fix(demacro): handle <construct> in <definition style> (BUG-N)

<2–3 sentences: what was wrong, what changed, why the fix is correct.>
```

### Step 6.5 — Update Regex Torture Test

Add a minimal, non-failing version of the problematic syntax to
`tests/fixtures/regex_torture_test.tex` with a comment:
`%% From BUG-N: <what this tests>` — but make sure the comment is not
picked up by the regex calls (use `%%` not `%`).

### Step 7 — Release lock

Always in a `finally` block.
