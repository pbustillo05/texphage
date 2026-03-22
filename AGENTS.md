# AGENTS.md — Claude Continuous Improvement Protocol

You (Claude) are the Testing Agent and Coding Agent for this repository.
The scripts `scripts/test_fidelity.py` and `scripts/coding_agent.py` are
optional cron-based automation. **Your primary job is to follow this checklist
conversationally** — the user triggers you by saying:

- `"Run testing agent"` or `"Run testing agent on seed 42"` → act as Testing Agent
- `"Fix next bug"` or `"Fix BUG-N"` → act as Coding Agent
- `"Run quarterly audit"` → act as Quarterly Audit Agent

**All rules below are mandatory. Never deviate.**

Every time you improve, fix a bug, or run an agent:
1. Always write a failing test before touching any code.
2. Always add the `MATCHES/CAPTURES/LIMITATIONS` comment block before touching
   any regex pattern in `demacro.py` or `_regex.py` (format in the
   DANGER ZONE section below).
3. If you encounter a LaTeX construct you do not recognise, do NOT guess.
   Add it to `BUGS.md` as MEDIUM severity with a reproduction snippet, and look
   it up in `memory/latex_docs.md` or ask the user for the CTAN link.
4. Never commit `tests/runs/`, tarballs, or compiled PDFs.

---

## Failure Mode Taxonomy

**Read this before every bug fix.** Demacro fails in exactly three modes.
Classify the bug into a mode *before reading any code*, because each mode
has a completely different fix location and diagnostic path.

### Mode A — Recognition failure
`find_all` does not match the definition in the preamble → macro is never
added to `macro_dict` → it remains unexpanded in the body → compile error
`undefined control sequence`.

**Signal:** macro appears in `problematic_macros` with reason `pattern_mismatch`,
OR is completely absent from `demacro_report.json` despite being in the preamble.

**Fix location:** the regex pattern in `find_all` (or a missing branch).

### Mode B — Expansion failure
`find_all` matches the definition and `build_dictionary` adds it to
`macro_dict`, but `expand()` produces the wrong string — or logs
`pattern_mismatch` because the compiled call-site pattern doesn't match
the actual usage in the body.

**Signal:** the macro IS in `macro_dict` (check with the pattern probe below)
but the output is wrong or a `pattern_mismatch` is logged during expansion.

**Fix location:** `build_dictionary()`, `content_replacement()`, or
`expand()` — NOT the `find_all` pattern.

### Mode C — Preprocessing failure
`preprocessing()` corrupts the source before `find_all` ever runs —
typically by collapsing whitespace inside a verbatim-like environment,
destroying content that TeX requires to be literal.

**Signal:** compile error whose cause disappears when you compare
`pipeline_output.tex` against the raw source; `pipeline.log` shows TeX
scanning to EOF unexpectedly.

**Fix location:** `_VERBATIM_ENVS` in `preprocessing()`, usually by adding
a new environment name or a package→environment mapping.

**Verbatim protocol (every Mode C fix):**
When a new verbatim-like environment is found, the fix is always two steps:
1. Identify which package defines the environment (check `find_used_packages`
   output or the paper's `\usepackage` list).
2. Add the package→environment mapping to `_VERBATIM_ENVS` in `demacro.py`.
Never hard-code just the environment name without noting the source package
in a comment — otherwise future agents won't know why it's there.

---

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

---

## `TODO.md` for Enhancements

This repository uses `TODO.md` to track planned features, enhancements, and
very low-priority bugs that are not considered regressions. `BUGS.md` is
strictly for tracking regressions where the pipeline's output is incorrect.

**When to use `TODO.md`:**
- When the user suggests a new feature (e.g., "Add support for `pgfkeys`").
- When the Quarterly Pattern Audit discovers a new, low-prevalence macro pattern.
- When a bug is discovered that is a very obscure edge case with minimal
  impact, the user may decide to log it in `TODO.md` instead of `BUGS.md`.

**Your responsibility as an agent is to:**
1.  Check `TODO.md` before starting work to see if your task is already documented.
2.  When asked to implement a new feature, first add it to the "Proposed"
    section of `TODO.md` and ask the user to confirm its priority.
3.  When working on a TODO item, move it to the "In Progress" section.

---

## Testing Agent

### When to run
The user says: `"Run testing agent"`, `"Run testing agent on seed 42"`,
`"Run testing agent on IDs 2401.12345 2312.09876"`, or
`"Run tests on arXiv papers with refactored directories"` (canonical mode).

**Before downloading anything, ask the user:**
`"Should I download 5 new arXiv papers (may take several minutes), or use
specific IDs? What seed or IDs should I use?"`

**Pipeline modes** (pass `--pipeline` to `test_fidelity.py`):
- `raw` (default): compile `pipeline_output.tex` from `raw_data/` — attachments
  resolve via their original relative paths.
- `canonical`: call `texphage_to_dir()` — creates a self-contained
  `canonical_output/` directory with all attachments copied into `unalienable/`
  and paths rewritten.  Triggered by `"run tests … with refactored directories"`.

Only proceed with downloads if the user confirms. This prevents accidental
network usage and gives the user control over which papers are tested.

### Step 1 — Acquire lock
Check and create the lock file as described above.

### Step 2 — Sample papers
Download 5 papers. Distribution per run: 2 from `math.CT`, 2 from `math.AT`,
1 from `cs.LO` or `math.AG` (rotate each run). Use `get_all_arxiv_ids()` from
`scripts/extractor.py`.

Create `tests/runs/<run_id>/manifest.json` with fields: `run_id`, `seed`,
and per-paper: `arxiv_id`, `category`, `download_timestamp`, `tarball_sha256`.
`run_id` format: `YYYYMMDD_HHMMSS_<seed>`.

### Step 3 — Compile baseline PDFs

For each paper, compile the **raw unprocessed** source with `latexmk`:
```python
subprocess.run(
    ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error'],
    cwd=raw_data_dir, capture_output=True, timeout=120,
)
```
`timeout=120` is **mandatory** — TeX is Turing-complete and can loop forever.

**If `subprocess.TimeoutExpired`:** log `baseline_compile_timeout`, skip paper.
**If exit code nonzero:** log `baseline_compile_failed`, skip paper.

### Step 4 — Run the pipeline

```python
from texphage.pipeline import build_minimal_preamble
from texphage.unfold import unfold
from texphage.demacro import demacro

tex = unfold(raw_data_dir)
expanded_tex, packages, problems = demacro(tex)

# Goal (see README.md): \documentclass + \usepackage calls only (no macro
# definitions) + 1-line demacro'ed body. Do NOT keep the full preamble.
minimal_preamble = build_minimal_preamble(tex)
pipeline_tex = (
    minimal_preamble + '\n\\begin{document}\n'
    + expanded_tex + '\n\\end{document}\n'
)
(run_dir / 'pipeline_output.tex').write_text(pipeline_tex)
```

Save `pipeline.log` (DEBUG level) and `demacro_report.json`. The report
must include, for each entry in `problematic_macros`:
- `name`, `position`, `reason` (as now)
- `definition_pattern`: `macro_dict[name][0]` — the regex pattern stored
- `context`: 150 chars of body text centred on `position`

This context makes the report self-diagnosing: an agent reading it in a new
session can see exactly what matched and why the call-site pattern failed,
without re-running anything.

### Step 5 — Compile pipeline output

```python
subprocess.run(
    ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
     'pipeline_output.tex'],
    cwd=str(run_dir), capture_output=True, timeout=120,
)
```
**If `subprocess.TimeoutExpired`:** CRITICAL — our pipeline created an infinite TeX loop.

### Step 6 — Compare results

Store all scores in `tests/runs/<run_id>/<arxiv_id>/comparison.json`.

**6a — Compilation success.** Classify failed compiles:
- `undefined_control_sequence` — macro incorrectly expanded or deleted
- `missing_brace` / `extra_brace` — brace matching failed
- `environment_mismatch` — `\begin`/`\end` incorrectly modified
- `package_missing` — package stripped incorrectly
- `compilation_timeout` — infinite TeX loop
- `other`

**6b — Page count delta.** `|output_pages - baseline_pages|` > 2 → HIGH.

**6c — Visual diff (SSIM).** Convert to grayscale PNG at 150 dpi.
SSIM < 0.85 **AND** text diff > 5 lines on that page → HIGH.
SSIM 0.85–0.95 → MEDIUM. Save side-by-side PNGs for pages with SSIM < 0.95.

**6d — Text extraction diff.** > 50 lines → HIGH; 10–50 → MEDIUM; < 10 → LOW.

### Step 7 — Diagnose bugs

The error type from Step 6a determines which diagnostic path to follow.
Always classify into a failure mode (see Taxonomy above) before doing anything
else.

---

#### For `undefined_control_sequence \foo` (Mode A or B)

**Step 7.1 — Run texdef first. This is mandatory, not optional.**
```bash
texdef -t latex -f \\foo
# If the macro comes from a known package:
texdef -t latex -p amsmath -f \\foo
```
texdef gives you the TeX machine's internal representation of the macro.
This is the ground truth for what the regex must match. Record the output.

**Step 7.2 — Classify mode A vs B.**
```python
# Does find_all recognise the *definition* in the preamble?
from texphage.demacro import find_all, preprocessing
preamble, _, _ = preprocessing(raw_tex)
matches = list(find_all.finditer(preamble))
# Is there a match whose group name corresponds to \foo's definition style?
# If NO → Mode A. The pattern is missing or wrong.
# If YES → Mode B. Build the dictionary and inspect it:
from texphage.demacro import build_dictionary
macro_dict, _ = build_dictionary(preamble)
print(macro_dict.get('foo'))   # (call-site pattern, lambda) or None
```

**Step 7.3 — Get TeX ground truth via playground.** (See Playground Templates A & B below.)

**Step 7.4 — Run `expand()` with DEBUG logging** to trace every substitution
attempt and see exactly where and why it fails:
```python
import logging, logging.handlers
from texphage.demacro import build_dictionary, expand, preprocessing
logging.basicConfig(level=logging.DEBUG)
preamble, body, _ = preprocessing(raw_tex)
macro_dict, find_macro = build_dictionary(preamble)
expanded, problems = expand(body, macro_dict, find_macro, log_level=logging.DEBUG)
# The debug log shows: every macro found, every re.sub attempt, every
# pattern_mismatch or no_progress event, with positions.
```

---

#### For compile errors not involving `\undefined` (Mode B or C)

1. Compare `pipeline_output.tex` against the original source to see what changed.
2. If the error involves a verbatim-like environment with mangled content → Mode C.
   Check `_VERBATIM_ENVS` in `demacro.py`. Identify the responsible package.
3. If the error involves brace mismatch or environment mismatch:
   find the relevant macro definition in the preamble, run **Playground Template B**
   to confirm expected expansion, then run the pattern probe (Step 7.2 above).

---

#### For visual diff pages (SSIM < 0.95)

Open `visual_diff/page_N_diff.png`. Determine: is the difference a content
change (wrong text) or a layout shift (same text, different position)?
- Layout shift only → likely acceptable reflow from macro expansion; LOW/MEDIUM.
- Content change → run **Playground Template A** with the suspect macro to
  confirm what TeX produces, then trace the demacro output to find the discrepancy.

---

#### For multi-macro interaction bugs

If a paper fails but every suspect macro tests correctly in isolation:
1. Run the playground with the **full preamble** (all definitions together),
   not just the minimal reproducer.
2. If it compiles in the playground with the full preamble but fails with a
   single definition → interaction bug; note this explicitly in BUGS.md.
3. Interaction bugs are often caused by one macro expanding into a call to
   another — trace the expansion chain with DEBUG logging.

---

### Step 8 — Write to `BUGS.md`

Check for duplicates first: if a bug with the same `root_cause_pattern` and
similar context exists, update its `seen_in` and `last_seen` instead.

Entry format:
```markdown
## BUG-<N>: <short title>

- **severity**: CRITICAL | HIGH | MEDIUM | LOW
- **root_cause_pattern**: incorrect_expansion | missed_expansion | brace_mismatch |
  environment_error | package_stripping | verbatim_corruption | preprocessing |
  compilation_timeout | unrecognised_definition_pattern | other
- **failure_mode**: A | B | C   ← from the taxonomy above
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

**After adding a bug entry:** create the reproduction snippet as a fixture
file in `tests/fixtures/bug_N_<short_name>/main.tex`.

Commit: `test: run <run_id>, N new bugs, M updated`

### Step 9 — Cleanup

**Delete the entire run directory** (`shutil.rmtree(run_dir)`).  All scores are
already printed to the console and written to `manifest.json` before deletion.
arXiv tarballs and compiled PDFs are large; do not let them accumulate.

To keep the run directory for debugging (SSIM diffs, compile logs, etc.), pass
`--keep-runs` to `test_fidelity.py`.  Never commit `tests/runs/`.

### Step 10 — Release lock

Always in a `finally` block.

---

## Coding Agent

### When to run
The user says: `"Fix next bug"` or `"Fix BUG-N"`.

### Step 1 — Acquire lock
Check and create the lock file.

### Step 2 — Select target bug

If `"Fix next bug"`: pick the highest-severity OPEN bug in `BUGS.md`.
Break ties by `seen_in` count (most common first).

Read the bug entry fully. Note the `failure_mode` field (A / B / C).
If it is absent or unclear, classify it now using the taxonomy above before
proceeding — the mode determines every subsequent step.

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

Run the **pattern probe** to determine whether demacro even sees the definition:
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
See **Playground Templates** section for copy-pasteable patterns.

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
  comment block (format in DANGER ZONE). Commit this separately.
- **Before touching `build_dictionary()`:** re-read the DANGER ZONE rules.
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

Then verify the fix end-to-end with the playground (Template C):
```python
result = compile_snippet(preamble=<definition>, body=<call>)
expanded, _, _ = demacro(doc(<definition>, <call>))
assert expanded.strip() == result.pdf_text.strip(), \
    f"demacro: {expanded!r}\nTeX:    {result.pdf_text!r}"
```

If there is still a discrepancy, run `expand()` with `log_level=logging.DEBUG`
(see Testing Agent Step 7.4) to trace the exact substitution chain.

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

---

## Playground Templates

These are copy-pasteable patterns for the most common debugging scenarios.
Use them exactly — do not improvise a different structure.

### Template A — Verify expansion correctness

**Question:** What does TeX actually expand `\foo{arg}` to?

```python
from scripts.latex_playground import compile_snippet
from texphage.demacro import demacro

def doc(preamble, body):
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")

definition = r'\newcommand{\foo}[1]{result: #1}'
call       = r'\foo{hello}'

# Step 1: TeX ground truth
tex_result = compile_snippet(preamble=definition, body=call)
print("TeX produces:", repr(tex_result.pdf_text.strip()))

# Step 2: What does demacro produce?
expanded, _, problems = demacro(doc(definition, call))
print("demacro produces:", repr(expanded.strip()))
print("problems:", problems)

# Step 3: Are they equal?
assert tex_result.pdf_text.strip() == expanded.strip(), "MISMATCH"
```

### Template B — Pattern probe (is the definition recognised?)

**Question:** Does `find_all` see this definition, and what does `build_dictionary` store?

```python
from texphage.demacro import find_all, build_dictionary, preprocessing

raw_tex = r"""
\documentclass{article}
\newcommand{\foo}[1]{result: #1}
\begin{document}
\foo{hello}
\end{document}
"""

preamble, body, _ = preprocessing(raw_tex)

print("=== find_all matches in preamble ===")
for m in find_all.finditer(preamble):
    print(f"  branch={m.lastgroup!r}  text={m.group(0)[:100]!r}")

print("\n=== macro_dict entry for 'foo' ===")
macro_dict, find_macro = build_dictionary(preamble)
entry = macro_dict.get('foo')
if entry:
    print(f"  call-site pattern: {entry[0]!r}")
    print(f"  replacement:       {entry[1]}")
else:
    print("  NOT IN macro_dict → Mode A (recognition failure)")
```

### Template C — Batch verification after a fix

**Question:** Does the fix produce the right output across all known cases?

```python
from scripts.latex_playground import compile_snippet
from texphage.demacro import demacro

def doc(p, b):
    return f"\\documentclass{{article}}\n{p}\n\\begin{{document}}\n{b}\n\\end{{document}}"

test_cases = [
    # (definition, call, description)
    (r'\newcommand{\foo}[1]{#1}',          r'\foo{hello}',       'basic'),
    (r'\newcommand{\foo}[2][opt]{#1 #2}',  r'\foo{a}',           'with default'),
    (r'\newcommand{\foo}[2][opt]{#1 #2}',  r'\foo[x]{a}',        'override default'),
]

for defn, call, desc in test_cases:
    tex   = compile_snippet(preamble=defn, body=call)
    dm, _, _ = demacro(doc(defn, call))
    status = "OK" if tex.pdf_text.strip() == dm.strip() else "MISMATCH"
    print(f"[{status}] {desc}")
    if status == "MISMATCH":
        print(f"  TeX:    {tex.pdf_text.strip()!r}")
        print(f"  demacro:{dm.strip()!r}")
```

### Template D — Characterise an unknown macro variant

**Question:** How does TeX treat `\newcommand*` vs `\newcommand`?

```python
from scripts.latex_playground import compile_snippet

variants = [
    (r'\newcommand{\foo}[1]{#1}',  r'\foo{\par}',  'unstarred with \\par'),
    (r'\newcommand*{\foo}[1]{#1}', r'\foo{safe}',  'starred, safe arg'),
]
for defn, call, desc in variants:
    r = compile_snippet(preamble=defn, body=call)
    print(f"{desc}: ok={r.ok}  text={r.pdf_text.strip()!r}")
    if r.error_lines:
        print(f"  errors: {r.error_lines[:3]}")
```

---

## Quarterly Pattern Audit

### When to run
The user says: `"Run quarterly audit"`.

**Purpose:** Discover new macro-definition patterns in recently published
LaTeX packages that the demacro engine has never seen, and measure coverage
against the most-used packages on arXiv.

### Step 1 — Fetch recently updated CTAN packages

Query: `https://ctan.org/json/2.0/packages`

Filter for packages updated in the last 90 days (`date` field). For each,
download the primary `.sty` source:
`https://mirror.ctan.org/macros/latex/contrib/<pkgname>/<pkgname>.sty`

### Step 2 — Check for unrecognised patterns and measure coverage

**NEVER re-audit patterns already handled** (`\newcommand`, `\def`, xparse
argument types, `\NewDocumentCommand`, etc.). Their APIs are frozen.

Run `find_all` from `demacro.py` against each new `.sty` file. A package with
many `\def`/`\newcommand` calls but zero `find_all` matches uses an
unrecognised pattern.

Also compute a **coverage score** for the top 50 arXiv math packages:
- Count total macro definitions in each package.
- Count how many `find_all` matches.
- Report: `package: N_matched / N_total definitions`.
This score tracks improvement over time and prioritises which gaps to fix.

Also explicitly check for these high-value targets:

| Pattern | Package | Docs |
|---------|---------|------|
| `\cs_new:Npn`, `\cs_set:Npn` | expl3/LaTeX3 | https://ctan.org/pkg/l3kernel (interface3.pdf §3) |
| `\pgfkeys{/foo/.code=...}` | pgf/tikz | https://ctan.org/pkg/pgf (pgfmanual.pdf §87) |
| `\DeclareOption` + `\ProcessOptions` | LaTeX2e class system | https://www.latex-project.org/help/documentation/clsguide.pdf §5 |
| `\keys_define:nn` | l3keys | https://ctan.org/pkg/l3keys2e |

### Step 3 — Write to `BUGS.md` and create fixture

For any unrecognised pattern found in > 3 recent packages:
- Severity: MEDIUM
- Root cause: `unrecognised_definition_pattern`
- Failure mode: A
- Seen in: package names (not arXiv IDs)
- Create a fixture file in `tests/fixtures/audit_<pattern_name>/main.tex`

**Never add a fix in the same session as the audit.** Add the BUGS.md entry,
create the fixture, commit, and tell the user what was found. The fix happens
in a separate Coding Agent session after the user has reviewed the findings.

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

**Mandatory comment block — before modifying any pattern, add this above it:**

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

**The regex engine invariant:** All patterns assume preprocessing has produced
a flat single-line string with at most one ASCII space between tokens. The
pattern fragment ` ?(?<arg1>...)` is correct as written — do not add `\s+`
or multiline flags unless you understand why this invariant exists.

**The Regex Torture Test:**
Before committing any change to `_regex.py` or the `find_all` pattern in
`demacro.py`, you must run the regex torture test and ensure it passes. This
test is located in `tests/test_demacro.py` and uses the fixture
`tests/fixtures/regex_torture_test.tex`. This test ensures that your change
does not break any previously fixed edge cases.

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

---

## Run Directory Structure

```
tests/
  runs/
    .agent.lock                          ← lock file; deleted after each run
    <run_id>/                            ← YYYYMMDD_HHMMSS_<seed>
      manifest.json                      ← DELETED by default cleanup (Step 9)
      <arxiv_id>/                        ← DELETED by default cleanup (Step 9)
        raw_data/
        baseline.pdf
        pipeline_output.tex
        pipeline_output.pdf
        demacro_report.json
        pipeline.log
        baseline_compile.log
        output_compile.log
        comparison.json
        visual_diff/

tests/fixtures/                          ← COMMITTED; every reproduction lives here
  nested_input/
  subfile_example/
  bug_N_<short_name>/                    ← added when BUG-N is created
  audit_<pattern_name>/                  ← added by quarterly audit
```

**Default:** entire `<run_id>/` directory is deleted after the run (Step 9).
Use `--keep-runs` to preserve it for debugging.
`tests/runs/` is in `.gitignore` — never committed.
`tests/fixtures/` is committed — the test suite must never depend on external data.

---

## Advanced Agent Capabilities (Future Vision)

### RAG pipeline for LaTeX package sources

When the Testing Agent encounters an `undefined_control_sequence` for a
command not defined in the local preamble, it currently relies on texdef and
docs. A RAG system would make this faster and more autonomous:

1. **Knowledge Base:** Scan CTAN for the top N most-used packages. Download
   their `.sty` and `.cls` sources, chunk by macro definition, store in a
   vector database.
2. **Query on failure:** For `\undefined_control_sequence \foo`, query:
   *"definition, argument spec, and expansion of `\foo` in package `<pkg>`"*.
3. **Retrieval:** The agent gets the actual source of `\foo` as context.
4. **Fix generation:** With ground-truth source in context, the agent writes
   the correct regex branch and test without guessing.

This would transform Mode A failures (recognition) into near-automatic fixes.

### Coverage dashboard

A persistent JSON file tracking, for each major arXiv math package:
- Number of macro definitions
- Number matched by `find_all`
- Percentage covered

Updated after each quarterly audit. Lets the user see progress over time
and prioritise which package to tackle next.

---

## System Dependencies

**Python** (install with `pip install -e ".[agents]"`):
```
pdf2image, pdfplumber, scikit-image, numpy, tqdm, requests
```

**System** (must be on PATH; install instructions in README):
```
latexmk      — TeX Live; for compiling baseline and output PDFs
kpsewhich    — TeX Live; for find_packages.py dependency resolution
pdftoppm     — poppler-utils; used by pdf2image for PDF→PNG
pdfinfo      — poppler-utils; for page count
texdef       — texlive-extra-utils or MacTeX; for macro introspection
pdftotext    — poppler-utils; used by latex_playground.py for text extraction
```

---

## Testing History

Seeds select different random shuffles of recent arXiv papers in the sampled
categories (`math.CT`, `math.AT`, `cs.LO`).  Each seed gives a reproducible
but distinct paper set.  **Do not reuse a seed** — the goal is broad coverage.

| Date       | Seed | Papers tested | New bugs |
|------------|------|---------------|----------|
| 2026-03-21 |   42 | 4             | BUG-3, BUG-4, BUG-5, BUG-6 |
| 2026-03-21 |    0 | (re-run, infra debugging) | — |
| 2026-03-22 |    7 | 4             | BUG-7 (fixed), BUG-8, BUG-9 |
