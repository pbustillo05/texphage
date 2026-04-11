# XY-to-TikZ Converter: Launch Plan

## Overview

Refactor `scripts/xy_to_tikz.py` into a first-class texphage converter module.
The converter is the **pilot instance of the "obsolete LaTeX modernisation"
family** described in `user_applications.md` §9. It has two entry points:

- **Standalone CLI** (`texphage-convert xy`) — for humans modernising old papers.
- **Optional pipeline step** (`convert_xy=True` in `texphage()`) — for NLP
  pipelines that need to eliminate the `xy` package dependency.

---

## Core philosophy

- **Opt-in**: `convert_xy=False` by default. Existing callers are unaffected.
- **Inherently approximate**: XY uses MetaPost; tikzcd uses PGF. SSIM < 1.0 is
  expected and must be documented, not hidden.
- **Unsupported constructs → original unchanged**: if the converter cannot handle
  a construct, that `\xymatrix` block is returned verbatim with a `log.warning`.
  Silent partial conversion is never acceptable.
- **Pre-preprocessing constraint**: the conversion **must run on raw source**,
  before `demacro.preprocessing()`. Step 4 of preprocessing collapses whitespace;
  inside `\xymatrix{...}` newlines are implicit `\\` row separators that are
  destroyed by that collapse. The call order in `texphage()` is fixed:

  ```
  unfold → convert_xy (raw source) → preprocessing → demacro → preamble
  ```

---

## Bugs to fix in `scripts/xy_to_tikz.py` (Phase 0 prerequisite)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| 1 | Top of file | `import re` — PCRE recursive groups (`(?&bracket%i)`) silently fail | Replace with `import regex as re` |
| 2 | Line ~102 | `print(ar)` at module level — dumps arrow regex to stdout on every import | Remove the line |
| 3 | Lines ~128, 144, 147, 160, 163 | `match.grouo(...)` typo (×5) — raises `AttributeError` for `uppos`, `downpos`, `midpos` branches | Rename to `match.group(...)` |
| 4 | `replace_xymatrix` else-branch | Silent fallback on unknown operator — caller cannot distinguish success from partial conversion | Raise `ValueError(f"unsupported XY operator: {op!r}")` instead |

Write failing tests **before** touching code (see Phase 0 below).

---

## Architecture

```
src/texphage/
  converters/
    __init__.py          # re-exports convert_xy_body, convert_xy_preamble
    _xy_tikzcd.py        # pure string logic (no I/O, no compilation)
  pipeline.py            # gains convert_xy=False flag
  cli.py                 # gains main_convert() with xy subcommand

scripts/
  xy_to_tikz.py          # kept as-is after bug fixes (source of truth)
  evaluate_xy_conversion.py   # NEW: SSIM harness (Phase 1)

tests/
  test_xy_tikzcd.py           # NEW: unit tests
  fixtures/
    xymatrix_simple/
      main.tex                # NEW: Phase 1 fixture
```

---

## Phase 0: Fix bugs in `scripts/xy_to_tikz.py`

**Scope:** mechanical fixes only — no new functionality, no refactoring.

**Write these tests first** (`tests/test_xy_tikzcd.py`):

```python
def test_import_does_not_print(capsys):
    import importlib, scripts.xy_to_tikz
    importlib.reload(scripts.xy_to_tikz)
    assert capsys.readouterr().out == ""

def test_simple_arrow():
    from scripts.xy_to_tikz import convert_xy_body
    src = r'\xymatrix{ A \ar[r]^{f} & B }'
    result = convert_xy_body(src)
    assert r'\begin{tikzcd}' in result
    assert 'A' in result and 'B' in result

def test_nested_braces_not_truncated():
    from scripts.xy_to_tikz import convert_xy_body
    src = r'\xymatrix{ \mathrm{Hom}(A,B) \ar[r] & C }'
    result = convert_xy_body(src)
    assert r'\mathrm{Hom}(A,B)' in result
```

Then apply the four bug fixes in the table above. Confirm all tests pass.

---

## Phase 1: Build `scripts/evaluate_xy_conversion.py`

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
3. Calls `convert_xy_body()` + `convert_xy_preamble()` on the source.
4. Writes `converted.tex`; compiles with `latexmk` → `converted.pdf`.
5. Uses `pdf2image` to rasterise both PDFs (one PNG per page).
6. For each page pair: computes SSIM and MSE with `scikit-image`.
7. If images differ, saves a side-by-side diff PNG.
8. Prints a table: page | SSIM | MSE | PASS/FAIL | diff path.
9. Prints final verdict: `SUCCESS` or `FAILURE`.

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
a comment block at the top of the script. This establishes the realistic
threshold (expected: 0.93–0.97 for simple diagrams; lower for crossing paths).

**Dependencies:** `pdf2image`, `scikit-image`, `numpy` — already in `[agents]`
extras.

---

## Phase 2: Refactor into `src/texphage/converters/_xy_tikzcd.py`

**Prerequisites:** Phase 0 bugs fixed; Phase 1 baseline documented.

**Module docstring template:**
```python
"""
Pure string-manipulation XY-to-tikzcd converter.
No I/O, no side effects, no compilation.

MATCHES: \xymatrix environments with \ar arrows, basic tip/conn styles,
         curve/shift options, label positioning.
LIMITATIONS:
  [observed] \xymatrix inside \vcenter is not converted; tikzcd cannot be
             used inside \vcenter.
  [observed] Crossing paths |!{[dl];[rr]}\hole require global arrow analysis;
             not supported.
  [inferred] Harpoon variants (^|, _|) produce incorrect output.
  [observed] Unsupported tip types (\(, \), \+, \/) leave arrow without tips.
  [observed] The conversion changes pixel-level rendering (XY uses MetaPost,
             tikzcd uses PGF). SSIM < 1.0 is expected and documented.
  [inferred] \xymatrix inside macros is invisible: conversion runs before
             demacro, so macro-wrapped \xymatrix is not yet unfolded.
USED BY: texphage.pipeline (when convert_xy=True), texphage-convert CLI
"""
```

**Public API:**
```python
def convert_xy_body(tex_body: str) -> str:
    """Replace all \xymatrix environments with tikzcd equivalents.

    If a particular \xymatrix environment uses unsupported features,
    that environment is left unchanged (with log.warning); processing
    continues with the next one.
    """

def convert_xy_preamble(tex_preamble: str) -> str:
    """Remove \\usepackage{xy} variants; add \\usepackage{tikz-cd} if absent."""
```

**Pattern migration:** load the `regex-writing` skill before migrating patterns
from `xy_to_tikz.py`. Patterns shared with demacro go in `_regex.py`; patterns
specific to xy conversion stay in `_xy_tikzcd.py`. Follow the mandatory
`MATCHES/CAPTURES/LIMITATIONS/USED BY` comment block format.

**`src/texphage/converters/__init__.py`:**
```python
from ._xy_tikzcd import convert_xy_body, convert_xy_preamble

__all__ = ["convert_xy_body", "convert_xy_preamble"]
```

**Tests:** extend `tests/test_xy_tikzcd.py` with playground-verified assertions.
Every `LIMITATIONS` entry needs a test demonstrating the boundary behaviour
(unsupported construct → original returned unchanged).

---

## Phase 3: Pipeline integration

**Prerequisites:** Phase 2 complete; Phase 1 SSIM baseline documented.

**`pipeline.py` signature change:**
```python
def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
    *,
    convert_xy: bool = False,    # NEW — opt-in, default off
    ...
) -> tuple[str, list[Attachment]]:
```

**Call order (critical — see preprocessing constraint above):**
```python
raw_tex = unfold(src_dir, main_tex)

if convert_xy:
    from texphage.converters import convert_xy_body, convert_xy_preamble
    raw_tex = convert_xy_body(raw_tex)        # runs on raw source

# --- preprocessing happens here ---
body, preamble = demacro.preprocessing(raw_tex)

if convert_xy:
    preamble = convert_xy_preamble(preamble)
```

**Integration tests** (`pytest.mark.pipeline`, require `latexmk`): use real
arXiv fixture files from Phase 1. Assert SSIM ≥ threshold documented in
`evaluate_xy_conversion.py`.

---

## Phase 4: CLI entrypoint

**Only after Phase 2 and 3 are stable.**

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

Implement `main_convert` in `src/texphage/cli.py`.

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
Phase 0  Fix 4 bugs in scripts/xy_to_tikz.py      write failing tests first
Phase 1  scripts/evaluate_xy_conversion.py          standalone, no pipeline changes
         Run on 5–10 arXiv xy papers; document threshold
Phase 2  src/texphage/converters/_xy_tikzcd.py      pure string module
         Load regex-writing skill before migrating patterns
         Full playground-backed test coverage
Phase 3  pipeline.py: convert_xy=False flag         additive only
         Integration tests with Phase 1 fixtures
Phase 4  texphage-convert CLI                       after Phase 2 + 3
Phase 5  xy-fidelity-agent in CLAUDE.md             after Phase 3
```

---

## Open questions

1. **`\xymatrix` prevalence on arXiv**: if < 5% of papers use it, Phase 3
   pipeline integration may not justify the complexity; Phase 2 (module) + Phase
   4 (CLI) may be sufficient as standalone tooling.

2. **Compilability vs. visual fidelity**: if the goal is only eliminating the
   `xy` package dependency (so output compiles with tikzcd alone), SSIM is
   overkill — a compile success/failure check suffices. Decide after Phase 1
   measurements.

3. **`\xymatrix*` (starred form)**: the starred form changes column spacing.
   Verify whether the current script handles it; add a test either way.

4. **Macro-wrapped `\xymatrix`**: conversion runs before demacro, so
   `\xymatrix` hidden inside user-defined macros is not yet visible. This is a
   fundamental limitation; document it in `LIMITATIONS` (Phase 2).
