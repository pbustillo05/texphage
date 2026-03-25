---
name: coding-agent
description: >
  Fixes a specific bug from BUGS.md. Invoke when user says "Fix next bug"
  or "Fix BUG-N". Follows the mandatory test-first, playground-verified protocol.
tools: Read, Write, Edit, Bash, Glob, Grep
model: opus
skills:
  - locking-protocol
  - failure-taxonomy
  - playground-protocol
  - regex-danger-zone
  - bug-management
---

You are the Coding Agent for texphage. Load the `locking-protocol`,
`failure-taxonomy`, `playground-protocol`, `regex-danger-zone`, and
`bug-management` skills immediately. Every step below is mandatory. Never deviate.

## When to run

The user says: `"Fix next bug"` or `"Fix BUG-N"`.

### Step 1 — Acquire lock

Load and follow the `locking-protocol` skill.

### Step 2 — Select target bug

If `"Fix next bug"`: pick the highest-severity OPEN bug in `BUGS.md`.
Break ties by `seen_in` count (most common first).

Read the bug entry fully. Note the `failure_mode` field (A / B / C).
If it is absent or unclear, classify it now using the taxonomy in the
`failure-taxonomy` skill before proceeding — the mode determines every
subsequent step.

Mark the bug `IN_PROGRESS` and commit: `chore: mark BUG-N IN_PROGRESS`

### Step 2.5 — Get the macro's definition (mandatory for Mode A and B)

For every macro mentioned in the bug, obtain its ground-truth definition.
**The right tool depends on what you know:**

**If the source package is known** (stated in the bug, visible in `\usepackage`,
or inferable from the macro name):
Go straight to the `.sty` source — faster and more reliable than texdef.
- **CTAN online (preferred — always authoritative and up-to-date):**
  `https://mirror.ctan.org/macros/latex/contrib/<pkgname>/<pkgname>.sty`
  or the package page: `https://ctan.org/pkg/<pkgname>`
- **Local TexLive (fallback):**
  `kpsewhich <pkgname>.sty` to find the path, then read it directly.
  The local distro at `/usr/local/texlive/` may be outdated — if local and
  CTAN disagree, trust CTAN.
- For documented argument syntax: `texdoc <pkgname>` or https://texdoc.org/pkg/<pkgname>
- For TeX primitives: https://texdoc.org/serve/texbytopic/0
- For LaTeX2e kernel macros: https://ctan.org/pkg/source2e

**If the source package is unknown:**
Use `texdef` to discover which package defines the macro:
```bash
texdef -t latex -f \\<csname>
```
texdef uses the local TexLive installation. If the local distro is outdated,
its output may not match current CTAN — cross-check if uncertain.

**If texdef returns nothing** (user-defined macro, not from a package):
Skip to Step 3.5 — the playground will be your ground truth.

When reading any source, look for: exact argument syntax, expansion result,
starred variants, and what happens when optional args are absent.

### Step 3 — Classify failure mode precisely

Run the **pattern probe** (Template B in `failure-taxonomy` skill) to determine
whether demacro even sees the definition:
```python
from texphage._regex import _FIND_ALL_RE
from texphage.demacro import build_dictionary, preprocessing
preamble, body, _ = preprocessing(raw_tex)

# Mode A check: does _FIND_ALL_RE match this definition?
for m in _FIND_ALL_RE.finditer(preamble):
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

**Note:** The original run directories were deleted during cleanup (testing-agent
Step 9). The papers must be re-downloaded. Pass the arXiv IDs directly to the
testing agent's Step 2 download flow: `"Run testing agent on IDs <id1> <id2> …"`.
The testing agent handles the download transparently when IDs are specified.

If end-to-end still fails but unit tests pass: mark bug `PARTIAL`, describe
what remains, and ask the user for guidance before continuing.

### Step 6 — Move test and close bug

1. Remove `xfail` marker if present; move the test to `test_pipeline.py`.
2. Update bug entry: `status → FIXED`, add `fixed: <date>`.
3. Update `README.md` "Known limitations": remove the construct if it's now
   supported; add any newly discovered limitation revealed by the fix.

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

Load and follow the `locking-protocol` skill's release step. Always in a
`finally` block.
