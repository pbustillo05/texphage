# AGENTS.md — Claude Continuous Improvement Protocol

You (Claude) are the Testing Agent and Coding Agent for this repository.
The scripts `scripts/test_fidelity.py` and `scripts/coding_agent.py` are
optional cron-based automation. **Your primary job is to follow this checklist
conversationally** — the user triggers you by saying:

- `"Run testing agent"` or `"Run testing agent on seed 42"` → act as Testing Agent
- `"Fix next bug"` or `"Fix BUG-N"` → act as Coding Agent
- `"Run quarterly audit"` → act as Quarterly Audit Agent

**All rules below are mandatory. Never deviate. The META-RULE in
`CLAUDE_INSTRUCTIONS.md` applies here too — always write a failing test before
touching code, and always comment regex before changing it.**

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

## Testing Agent

### When to run
The user says: `"Run testing agent"`, `"Run testing agent on seed 42"`,
or `"Run testing agent on IDs 2401.12345 2312.09876"`.

**Before downloading anything, ask the user:**
`"Should I download 5 new arXiv papers (may take several minutes), or use
specific IDs? What seed or IDs should I use?"`

Only proceed with downloads if the user confirms. This prevents accidental
network usage and gives the user control over which papers are tested.

### Step 1 — Acquire lock
Check and create the lock file as described above.

### Step 2 — Sample papers
Download 5 papers. Distribution per run: 2 from `math.CT`, 2 from `math.AT`,
1 from `cs.LO` or `math.AG` (rotate each run). Use `get_all_arxiv_ids()` from
`scripts/extractor.py`.

Create `tests/runs/<run_id>/manifest.json`:
```json
{
  "run_id": "20240115_030000_42",
  "seed": 42,
  "papers": [
    {
      "arxiv_id": "2401.12345",
      "category": "math.CT",
      "download_timestamp": "2024-01-15T03:00:01Z",
      "tarball_sha256": "abc123..."
    }
  ]
}
```
`run_id` format: `YYYYMMDD_HHMMSS_<seed>`.

### Step 3 — Compile baseline PDFs

For each paper, compile the **raw unprocessed** source:
```python
result = subprocess.run(
    ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error'],
    cwd=raw_data_dir,
    capture_output=True,
    text=True,
    timeout=120,   # MANDATORY: TeX is Turing-complete and can loop forever
)
```

**If `subprocess.TimeoutExpired`:** log as `baseline_compile_timeout`, skip the
paper entirely. We cannot test our pipeline against a paper that times out even
without us.

**If exit code is nonzero:** log as `baseline_compile_failed`, skip the paper.
We need a working baseline to measure against.

Record: exit code, page count (`pdfinfo`), file size, duration.

### Step 4 — Run the pipeline

```python
import logging
from texphage.unfold import unfold
from texphage.demacro import demacro

logging.basicConfig(level=logging.DEBUG, filename=str(run_dir / 'pipeline.log'))

tex = unfold(raw_data_dir)
expanded_tex, packages, problems = demacro(tex)
```

Save `pipeline_output.tex`, `pipeline.log`, and `demacro_report.json`:
```json
{
  "packages": ["tikz", "amsmath"],
  "problematic_macros": [
    {"name": "foo", "position": 1234, "reason": "no_progress"}
  ]
}
```

### Step 5 — Compile pipeline output

```python
result = subprocess.run(
    ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
     'pipeline_output.tex'],
    cwd=str(run_dir),
    capture_output=True,
    text=True,
    timeout=120,   # MANDATORY: same reason as Step 3
)
```

**If `subprocess.TimeoutExpired`:** record as `output_compile_timeout`. This is
always CRITICAL severity — our pipeline created an infinite TeX loop.

### Step 6 — Compare results

Store all scores in `tests/runs/<run_id>/<arxiv_id>/comparison.json`.

**6a — Compilation success**

Classify failed compiles:
- `undefined_control_sequence` — a macro was incorrectly expanded or deleted
- `missing_brace` / `extra_brace` — brace matching failed
- `environment_mismatch` — `\begin`/`\end` was incorrectly modified
- `package_missing` — a package was stripped incorrectly
- `compilation_timeout` — pipeline output creates an infinite TeX loop
- `other`

**6b — Page count delta**

`|output_pages - baseline_pages|`. Any nonzero value is a regression.
Difference > 2 pages → HIGH severity.

**6c — Visual diff (SSIM)**

Convert both PDFs to grayscale PNG at 150 dpi. Compute SSIM per page.

```python
from pdf2image import convert_from_path
from skimage.metrics import structural_similarity
import numpy as np

def compare_pdfs_ssim(baseline_pdf: str, output_pdf: str) -> list[float]:
    b_pages = convert_from_path(baseline_pdf, dpi=150, grayscale=True)
    o_pages = convert_from_path(output_pdf,   dpi=150, grayscale=True)
    n = max(len(b_pages), len(o_pages))
    def to_arrays(pages, target):
        blank = np.zeros_like(np.array(pages[0]))
        arrays = [np.array(p) for p in pages[:target]]
        while len(arrays) < target:
            arrays.append(blank)
        return arrays
    return [float(structural_similarity(b, o))
            for b, o in zip(to_arrays(b_pages, n), to_arrays(o_pages, n))]
```

**Severity thresholds:**
- SSIM < 0.85 on any page **AND** text diff > 5 lines on that same page → HIGH
  (both conditions required; layout-only shifts from correct macro expansion
  are expected and acceptable — SSIM alone is too sensitive to text reflow)
- SSIM 0.85–0.95 on any page → MEDIUM

Save side-by-side PNGs for pages with SSIM < 0.95:
`visual_diff/page_N_diff.png` — [baseline | output | absolute diff ×5]

**6d — Text extraction diff**

```python
import pdfplumber, difflib

def text_diff(baseline_pdf: str, output_pdf: str) -> list[str]:
    def extract(path):
        with pdfplumber.open(path) as pdf:
            return [line for page in pdf.pages
                    for line in (page.extract_text() or '').splitlines()]
    return list(difflib.unified_diff(
        extract(baseline_pdf), extract(output_pdf),
        fromfile='baseline', tofile='output'
    ))
```

Diff lines > 50 → HIGH; 10–50 → MEDIUM; < 10 → LOW.

### Step 7 — Diagnose bugs

**If you encounter a LaTeX error you do not understand:**
Do NOT guess at the cause. Instead:
1. Quote the exact error from `output_compile.log`.
2. Search for the relevant construct in `CLAUDE_INSTRUCTIONS.md` section 1.4.
3. If not found there, ask the user: `"I see error X which involves the
   construct Y. Could you point me to the relevant CTAN documentation?"`
4. Add the bug to BUGS.md as MEDIUM with the reproduction snippet, and wait
   for guidance before attempting a fix.

**For `undefined_control_sequence \foo`:**
1. Search `demacro_report.json` for `foo` in `problematic_macros`.
   - Found → macro was known-problematic; gap in `build_dictionary`.
   - Not found → macro was incorrectly expanded; regex matched wrongly.
2. Find the first occurrence of `\foo` in `pipeline_output.tex` and examine
   the surrounding 200 characters for context.
3. Find the original definition of `\foo` in the raw source.

**For visual diff pages (SSIM < 0.95):**
Open the side-by-side PNG at `visual_diff/page_N_diff.png` and describe what
you see — which element changed, whether it is a content change or a layout
shift, and whether it looks like a macro expansion error.

### Step 8 — Write to `BUGS.md`

Check for duplicates first: if a bug with the same `root_cause_pattern` and
similar context exists, update its `seen_in` and `last_seen` instead of
creating a new entry.

Entry format:
```markdown
## BUG-<N>: <short title>

**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Root cause pattern:** incorrect_expansion | missed_expansion | brace_mismatch |
  environment_error | package_stripping | verbatim_corruption | preprocessing |
  compilation_timeout | unrecognised_definition_pattern | other
**Status:** OPEN
**First seen:** YYYY-MM-DD
**Last seen:** YYYY-MM-DD
**Seen in:** [2401.12345, 2312.09876]

**Description:**
2–3 sentences grounded in evidence from compile logs, demacro_report.json, or
visual_diff PNGs.

**Relevant code location:**
src/texphage/demacro.py — build_dictionary(), \newcommand branch

**Relevant LaTeX docs:**
https://ctan.org/pkg/xparse

**Reproduction:**
\documentclass{article}
\NewDocumentCommand{\myCmd}{D(){default}}{result: #1}
\begin{document}
\myCmd(value)
\end{document}
```

**After adding a bug entry:** also create the reproduction snippet as a fixture
file in `tests/fixtures/bug_N_<short_name>/main.tex`. This ensures the test
suite has a local copy and never depends on re-downloading from arXiv.

Commit: `test: run <run_id>, N new bugs, M updated`

### Step 9 — Cleanup

Delete intermediate files after comparison results are saved:

```python
import shutil

def cleanup_run(id_run_dir: Path):
    shutil.rmtree(id_run_dir / 'raw_data', ignore_errors=True)
    for ext in ['aux', 'log', 'fls', 'fdb_latexmk', 'out', 'toc',
                'bbl', 'blg', 'synctex.gz']:
        for f in id_run_dir.glob(f'**/*.{ext}'):
            f.unlink(missing_ok=True)
    # Keep: baseline.pdf, pipeline_output.tex, pipeline_output.pdf,
    #        demacro_report.json, pipeline.log, comparison.json, visual_diff/
```

### Step 10 — Release lock

Always in a `finally` block.

---

## Coding Agent

### When to run
The user says: `"Fix next bug"` or `"Fix BUG-N"`.

### Step 1 — Acquire lock
Check and create the lock file.

### Step 2 — Select target bug

If the user said `"Fix next bug"`: pick the highest-severity OPEN bug in
`BUGS.md`. Break ties by `seen_in` count (most common first).

If the user said `"Fix BUG-N"`: use that entry.

**Before starting, read the entry fully.** If the `relevant_latex_docs` field
is empty or you do not understand the LaTeX construct involved, ask the user:
`"BUG-N involves [construct]. Could you share the relevant documentation so I
understand the expected behaviour before I touch the regex?"`

Mark the bug `IN_PROGRESS` and commit: `chore: mark BUG-N IN_PROGRESS`

### Step 3 — Write a failing test first (non-negotiable)

Use the `Reproduction` snippet from the bug entry to write a new test. **Run it
first and confirm it fails.** A fix without a prior failing test is not accepted.

- demacro bug → add to `tests/test_demacro.py`
- unfold bug → add to `tests/test_unfold.py`
- end-to-end / compile error → add to `tests/test_pipeline.py`

If the reproduction fixture file does not already exist in `tests/fixtures/`,
create it now from the `Reproduction` snippet.

Commit the failing test alone:
`test: add failing test for BUG-N (fails before fix)`

### Step 4 — Fix

Read `relevant_code_location` and `description`. Rules:

- **Surgical changes only.** Do not refactor unrelated code.
- **Before touching any regex pattern:** add the `MATCHES/CAPTURES/LIMITATIONS`
  comment block (Part 1.3 of `CLAUDE_INSTRUCTIONS.md`). Commit this separately.
- **Before touching `build_dictionary()`:** re-read the DANGER ZONE rules.
  Adding a new `elif` branch must go in the correct position in the chain
  (order is semantically significant — `\edef` must come before `\def`).
- **If you don't understand the LaTeX construct:** do not guess. Ask the user
  for the CTAN link from `relevant_latex_docs` and read it first.

### Step 5 — Verify

```bash
pytest tests/ -x                    # all existing tests must pass
pytest tests/ -k "BUG_N"            # the new test must now pass
ruff check src/
mypy src/texphage/
```

### Step 5.5 — Re-run the testing agent on the same papers

After the fix passes all unit tests, re-run the testing agent on the arXiv IDs
from the bug's `seen_in` list and confirm the end-to-end regression is resolved.

If the end-to-end still fails but unit tests pass: mark the bug `PARTIAL`,
describe what remains, and ask the user for guidance before continuing.

### Step 6 — Move test to `test_pipeline.py` and commit

When the bug is confirmed fixed end-to-end:
1. If the test was `xfail`, remove the marker and move it to `test_pipeline.py`
   as a permanent regression test.
2. Update the bug entry: status → `FIXED`, add `Fixed in: <commit hash>`.
3. If the fix changes what the pipeline can or cannot handle, update the
   "Known limitations" section of `README.md`.

Commit:
```
fix(demacro): handle <construct> in <definition style> (BUG-N)

<2–3 sentences: what was wrong, what changed, why the fix is correct.>
```

### Step 7 — Release lock

Always in a `finally` block.

---

## Quarterly Pattern Audit

### When to run
The user says: `"Run quarterly audit"`.

**Purpose:** Discover new macro-definition patterns in recently published
LaTeX packages that the demacro engine has never seen. The engine fails
*additively* — new unsupported patterns appear; existing patterns don't change.

### Step 1 — Fetch recently updated CTAN packages

Query: `https://ctan.org/json/2.0/packages`

Filter for packages updated in the last 90 days (`date` field). For each,
download the primary `.sty` source:
`https://mirror.ctan.org/macros/latex/contrib/<pkgname>/<pkgname>.sty`

### Step 2 — Check for unrecognised patterns

**NEVER re-audit patterns already handled** (`\newcommand`, `\def`, xparse
argument types, `\NewDocumentCommand`, etc.). Their APIs are frozen.
`\newcommand` has not changed since 1994. Spending time re-auditing them is
wasted effort.

Run `find_all` from `demacro.py` against each new `.sty` file. A package with
many `\def`/`\newcommand` calls but zero `find_all` matches uses an
unrecognised pattern.

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
- Seen in: package names (not arXiv IDs)
- Create a fixture file in `tests/fixtures/audit_<pattern_name>/main.tex`

**Never add a fix in the same session as the audit.** Add the BUGS.md entry,
create the fixture, commit, and tell the user what was found. The fix happens
in a separate Coding Agent session after the user has reviewed the findings.

---

## Safety Rules (Non-Negotiable)

These apply in every session, not just agent runs.

1. **Never delete or modify working regex patterns without a prior failing test.**
   If you can't write a test that fails before your change, you don't understand
   the bug well enough to fix it.

2. **If you don't understand a LaTeX construct, ask.** Add the bug as MEDIUM,
   create the fixture, and ask the user for the CTAN documentation link.
   Do not guess at the meaning of TeX macros.

3. **Never commit `tests/runs/`**, tarballs, compiled PDFs, or pickle/json cache
   files. These are in `.gitignore` for a reason. Run `git status` before every
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

---

## Run Directory Structure

```
tests/
  runs/
    .agent.lock                          ← lock file; deleted after each run
    <run_id>/                            ← YYYYMMDD_HHMMSS_<seed>
      manifest.json
      <arxiv_id>/
        raw_data/                        ← DELETED by cleanup (Step 9)
        baseline.pdf                     ← kept
        pipeline_output.tex              ← kept
        pipeline_output.pdf              ← kept
        demacro_report.json              ← kept
        pipeline.log                     ← kept
        baseline_compile.log             ← kept
        output_compile.log               ← kept
        comparison.json                  ← kept
        visual_diff/
          page_N_diff.png                ← kept for pages with SSIM < 0.95

tests/fixtures/                          ← COMMITTED; every reproduction lives here
  nested_input/
  subfile_example/
  bug_1_<short_name>/                    ← added when BUG-1 is created
  audit_<pattern_name>/                  ← added by quarterly audit
```

`tests/runs/` is in `.gitignore` — never committed.
`tests/fixtures/` is committed — the test suite must never depend on external data.

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
```