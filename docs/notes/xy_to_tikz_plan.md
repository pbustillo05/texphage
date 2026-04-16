# XY-to-TikZ Converter: Launch Plan

## Overview

Refactor `scripts/xy_to_tikz.py` into a first-class texphage converter module.
The converter is the **pilot instance of the "obsolete LaTeX modernisation"
family** described in `user_applications.md` §9. Primary entry point:

- **Standalone CLI** (`texphage-convert xy`) — for humans modernising old papers.

Pipeline integration (`convert_xy=True` in `texphage()`) is **deferred** until
Phase 4 (see below). The CLI alone is sufficient for the current use case.

---

## Core philosophy

- **Opt-in**: `convert_xy=False` by default. Existing callers are unaffected.
- **Inherently approximate**: XY uses MetaPost; tikzcd uses PGF. SSIM < 1.0 is
  expected and must be documented, not hidden.
- **Unsupported constructs → original unchanged**: if the converter cannot handle
  a construct, that `\xymatrix` block is returned verbatim with a `log.warning`.
  Silent partial conversion is never acceptable.
- **Operates on raw source**: the CLI reads the user's original `.tex` file and
  outputs a modified file with only `\xymatrix` blocks replaced. Full
  preprocessing is NOT applied; the converter uses `regex.DOTALL` to match
  multi-line environments.

---

## Corrections to the original plan

### Pre-preprocessing constraint — wrong stated reason

The original plan said "newlines are implicit `\\` row separators" inside
`\xymatrix`. **This is false.** XY-pic uses explicit `\\` as row separators;
newlines are plain whitespace and survive preprocessing step 4 (whitespace
collapse) unchanged. The actual reason for the ordering decision is pragmatic:
the CLI operates on raw source without invoking the demacro pipeline at all.

### `\xymatrix*` — not valid XY-pic syntax

Playground test (2026-04-14) shows `\xymatrix*{...}` raises a fatal XY-pic
error: "\\xymatrix<setup>{<rows>} expected." The starred form does not exist.
Papers using it fail to compile regardless. No conversion mapping is needed;
a LIMITATIONS entry documents this.

### Additional bugs found in `scripts/xy_to_tikz.py`

Two bugs were missing from the original Phase 0 table (now fixed):
- **`print('ERROR:...')`** in `replace_xymatrix` lines 260, 263
- **`match.group('curve')[:1] == '^-'`** dead branch (should be `[:2]`)

---

## Phase 0: Fix bugs in `scripts/xy_to_tikz.py` ✅ DONE

All 5 bugs fixed; 18 tests pass. See `tests/test_xy_tikzcd.py`.

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| 1 | Line 3 | `import re` — `re.compile(ar)` raises `re.error` at import | `import regex as re` |
| 2 | Line 102 | `print(ar)` at module level | Removed |
| 3 | Lines 128, 142, 144, 159, 162 | `match.grouo(...)` ×5 | `match.group(...)` |
| 4 | Lines 260, 263 | `print('ERROR:...')` + silent partial return | `log.warning(...)` + `return match.group(0)` |
| 5 | Line 174 | `[:1] == '^-'` dead branch | `[:2]` |

---

## Phase 1: Build `scripts/evaluate_xy_conversion.py` ✅ DONE

**Fixture:** `tests/fixtures/xymatrix_simple/main.tex` — simple 2×2 commutative
square. Both original (XY) and converted (tikzcd) compile to 1 page.
Converted output verified to compile cleanly before running SSIM benchmarks.

**SSIM baseline log** (append results here after running on arXiv papers):
```
# Date         Input file                    Pages  Min-SSIM  Verdict
# (run: python scripts/evaluate_xy_conversion.py <file>)
```

**Purpose:** empirically establish the realistic SSIM range before committing
to any threshold or pipeline integration. This script **does not touch
`texphage()`**.

**CLI interface:**
```
python scripts/evaluate_xy_conversion.py <path_to_tex_file>
    [--out-dir DIR]            # default: tests/runs/xy_eval_<timestamp>/
    [--ssim-threshold 0.97]    # PASS/FAIL cutoff for reporting
```

**What it does:**
1. Reads the `.tex` file.
2. Compiles original with `latexmk -pdf -interaction=nonstopmode` → `original.pdf`.
3. Calls `xy_to_tikzcd()` on the source.
4. Writes `converted.tex`; compiles with `latexmk` → `converted.pdf`.
5. Uses `pdf2image` to rasterise both PDFs (one PNG per page).
6. For each page pair: computes SSIM and MSE with `scikit-image`.
7. Prints a table: page | SSIM | MSE | PASS/FAIL | diff path.
8. Prints final verdict: `SUCCESS` or `FAILURE`.

**Fixture to create** (`tests/fixtures/xymatrix_simple/main.tex`):
```latex
\documentclass{article}
\usepackage[all]{xy}

\begin{document}

A simple commutative square:
\xymatrix{
  A \ar[r]^f \ar[d]_g & B \ar[d]^{h} \\
  C \ar[r]_k & D
}

\end{document}
```

**Milestone:** Run on 5–10 arXiv papers with `\xymatrix`. Record SSIM scores in
a comment block at the top of the script. Expected: 0.93–0.97 for simple diagrams.

**Dependencies:** `pdf2image`, `scikit-image`, `numpy` — already in `[agents]`
extras.

---

## Phase 2: Refactor into `src/texphage/xy_to_tikzcd.py` ✅ DONE

**Prerequisites:** Phase 0 bugs fixed ✅; Phase 1 baseline documented.

**Module docstring template:**
```python
"""
Pure string-manipulation XY-to-tikzcd converter.
No I/O, no side effects, no compilation.
Operates on raw or preprocessed source (regex.DOTALL for multi-line matching).

MATCHES: \xymatrix environments with \ar arrows, basic tip/conn styles,
         curve/shift options, label positioning.
LIMITATIONS:
  [observed] \xymatrix inside \vcenter is not converted; tikzcd cannot be
             used inside \vcenter.
  [observed] Crossing paths |!{[dl];[rr]}\hole require global arrow analysis;
             not supported — block left unchanged.
  [inferred] Harpoon variants (^|, _|) produce incorrect output.
  [observed] Unsupported tip types (\\(, \\), \\+, \\/) leave arrow without tips.
  [observed] \\xymatrix inside user macros is invisible: macro content is not
             yet expanded at conversion time.
  [inferred] Comments inside \\xymatrix{...} (e.g. % this arrow) confuse the
             converter — block left unchanged with log.warning.
  [observed] \\xymatrix*{...} is not valid XY-pic syntax (playground-confirmed);
             the * is captured into options and silently ignored.
  [observed] The conversion changes pixel-level rendering (XY uses MetaPost,
             tikzcd uses PGF). SSIM < 1.0 is expected and documented.
USED BY: texphage-convert CLI
"""
```

**Public API:**
```python
def convert_xy_body(tex: str) -> str:
    """Replace all \\xymatrix environments with tikzcd equivalents.

    Operates on raw source text (regex.DOTALL for multi-line matching).
    Unsupported \\xymatrix blocks are left unchanged with log.warning.
    """

def convert_xy_preamble(preamble: str) -> str:
    """Remove \\usepackage{xy} variants; add \\usepackage{tikz-cd} if absent."""
```

**Pattern migration:** load the `regex-writing` skill before migrating patterns
from `xy_to_tikz.py`. Patterns shared with demacro go in `_regex.py`; patterns
specific to xy conversion stay in `_xy_tikzcd.py`. Follow the mandatory
`MATCHES/CAPTURES/LIMITATIONS/USED BY` comment block format.

**After Phase 2:** `scripts/xy_to_tikz.py` becomes a thin CLI wrapper (~10 lines)
that calls `convert_xy_body` from the module. No duplicate logic.

**Tests:** extend `tests/test_xy_tikzcd.py` with playground-verified assertions.
Every `LIMITATIONS` entry needs a test demonstrating the boundary behaviour
(unsupported construct → original returned unchanged).

---

## Phase 3: CLI entrypoint ✅ DONE

**Prerequisites:** Phase 2 complete; Phase 1 SSIM baseline documented.

Add to `pyproject.toml`:
```toml
[project.scripts]
texphage-convert = "texphage.cli:main_convert"
```

**Usage:**
```
texphage-convert xy input.tex [-o output.tex] [--strict]
  --strict    raise an error if any \xymatrix cannot be converted
              (default: warn and leave that block unchanged)
```

**Implementation in `src/texphage/cli.py`:**
```python
def main_convert() -> None:
    # regex-split raw .tex into preamble + body (no full preprocessing)
    # call convert_xy_body(body) and convert_xy_preamble(preamble)
    # reassemble and write output
```

The document split uses `regex` (not a full preprocessing pass):
```python
_DOC_SPLIT_RE = regex.compile(
    r'(?P<preamble>.*?)\\begin\{document\}(?P<body>.*?)\\end\{document\}',
    regex.DOTALL,
)
```

**Gate:** `texphage-convert xy tests/fixtures/xymatrix_simple/main.tex` produces
compilable output; SSIM ≥ threshold documented in Phase 1.

---

## Phase 4: Pipeline integration and demacro API refactor (long-term)

**Why deferred:** CLI-only is sufficient for the current use case. Pipeline
integration adds complexity (API refactor, integration tests) not yet justified.

**When to implement:**
- If arXiv prevalence of `\xymatrix` justifies automated pipeline conversion.
- Or if other converters (eqnarray→align, psfig→includegraphics) need the same
  integration point.

**Design:**
```python
# Expose demacro.preprocessing() + demacro.expand() as separate public functions
# Pipeline call order:
raw_tex = unfold(src_dir, main_tex)
body, preamble = demacro.preprocessing(raw_tex)   # exposed
if convert_xy:
    body    = convert_xy_body(body)
    preamble = convert_xy_preamble(preamble)
expanded = demacro.expand(body, preamble)          # new public step
```

---

## Phase 5: xy-fidelity-agent (long-term)

After Phase 3 establishes a stable API, define a `xy-fidelity-agent` in
`CLAUDE.md` — analogous to `arxiv-fidelity` — that:
1. Downloads arXiv papers using `\xymatrix`.
2. Runs the converter and measures SSIM.
3. Logs failures to `BUGS.md`.

---

## Recommended sequencing

```
Phase 0  Fix 5 bugs in scripts/xy_to_tikz.py    ✅ DONE (2026-04-14)
         18 tests pass in tests/test_xy_tikzcd.py
Phase 1  scripts/evaluate_xy_conversion.py       ✅ DONE (2026-04-14)
         tests/fixtures/xymatrix_simple/main.tex created; both orignal and
         converted compile to 1 page. Run on arXiv xy papers; document SSIM.
Phase 2  src/texphage/xy_to_tikzcd.py           ✅ DONE (2026-04-14)
         All regex in _regex.py §9; 33 tests pass
         scripts/xy_to_tikz.py is now a 7-line thin wrapper
Phase 3  texphage-convert CLI                   ✅ DONE (2026-04-14)
         39 tests pass; gate: fixture converts cleanly to tikzcd
Phase 4  demacro API refactor + pipeline flag   long-term
Phase 5  xy-fidelity-agent                      long-term, after Phase 3
```

---

## Open questions

1. **`\xymatrix` prevalence on arXiv**: if < 5% of papers use it, Phase 4 pipeline
   integration may not justify the complexity; Phase 3 CLI alone may be sufficient.

2. **Compilability vs. visual fidelity**: if the goal is only eliminating the
   `xy` package dependency (so output compiles with tikzcd alone), SSIM is
   overkill — a compile success/failure check suffices. Decide after Phase 1.
