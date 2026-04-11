# XY-to-TikZ: Implementation Plan

## Context (updated 2026-03-25)

`xy_to_tikz.py` is a standalone script that converts `\xymatrix` diagrams to
`tikzcd`. It is the **first concrete instance of the "obsolete LaTeX
modernisation" converter family** described in `user_applications.md` §9.

As a converter, it fits into the broader toolbox architecture under
`src/texphage/converters/` and exposes an optional flag in `texphage()`. It
is useful for both humans (modernising old papers) and NLP pipelines
(eliminating the `xy` package dependency to reduce the required preamble).

This document supersedes the earlier "critique" framing. It describes bugs
that must be fixed, the correct architecture, and the full phase-by-phase
implementation plan.

---

## Known bugs in `scripts/xy_to_tikz.py` (must fix before integration)

### Bug 1: `import re` instead of `import regex as re`

`embed_brackets` builds a pattern with recursive named group `(?&bracket%i)`.
This is a PCRE feature not supported by Python's `re`. Every call to
`find_xymatrix` silently fails to match nested braces.

**Fix:** `import regex as re` at the top of the file.

### Bug 2: `print(ar)` at module level (line 102)

Every import of this module dumps the raw arrow regex to stdout.

**Fix:** Remove the `print(ar)` line.

### Bug 3: Five `match.grouo(...)` typos

Lines 128, 144, 147, 160, 163 all read `match.grouo(...)`. They raise
`AttributeError` at runtime for those branches.

Affected groups: `uppos`, `downpos` (×2), `midpos` (×2).

**Fix:** Rename to `match.group(...)` in all five places.

### Bug 4: Silent fallback in `replace_xymatrix` on unknown operators

When an unknown XY option is encountered, the function prints to stderr and
returns a partial tikzcd result. The caller cannot distinguish a successful
conversion from a partial one.

**Fix:** Raise `ValueError("unsupported XY operator: ...")` instead. The
caller in `convert_xy_body()` (see Phase 2) will catch this and return the
original string unchanged, with a logged warning.

---

## Architectural constraints

### Constraint 1: Run before preprocessing

texphage's preprocessing (step 4) collapses all whitespace to a single space.
Inside `\xymatrix{...}`, newlines serve as implicit `\\` row separators in TeX.
After whitespace collapse they are gone. The xy→tikzcd conversion **must run
on the raw, unprocessed source**, before `demacro.preprocessing()` is called.

The call order in `texphage()` must be:
```
unfold → convert_xy (raw source) → preprocessing → demacro → preamble
```

### Constraint 2: Inherently approximate — document, don't hide

XY and tikzcd use different layout engines (MetaPost vs. PGF). Even a
semantically perfect translation will produce pixel-level differences. The
SSIM threshold in the evaluation script is a calibration target, not a
guarantee. The converter's docstring and `LIMITATIONS` block must state this
clearly.

### Constraint 3: Unsupported constructs → return original unchanged

If the converter encounters a construct it cannot handle (crossing paths,
`\vcenter`, unknown tips), it should return the original `\xymatrix`
environment unchanged rather than producing a broken tikzcd. A log warning is
appropriate; a silent partial conversion is not.

---

## Phase 0: Fix bugs in `scripts/xy_to_tikz.py` (prerequisite)

**Scope:** Mechanical fixes only. No new functionality.

**Steps:**
1. Replace `import re` with `import regex as re`.
2. Remove `print(ar)` on line 102.
3. Fix all five `match.grouo(...)` → `match.group(...)`.
4. Replace the silent-fallback `else` branch in `replace_xymatrix` with
   `raise ValueError(f"unsupported XY operator: {op!r}")`.

**Tests to write first (before touching the code):**

```python
# tests/test_xy_tikzcd.py
import pytest
from scripts.xy_to_tikz import convert_xy_body  # will fail before Phase 2

def test_import_does_not_print(capsys):
    import importlib
    import scripts.xy_to_tikz
    importlib.reload(scripts.xy_to_tikz)
    assert capsys.readouterr().out == ""

def test_simple_arrow():
    src = r'\xymatrix{ A \ar[r]^{f} & B }'
    result = convert_xy_body(src)
    assert r'\begin{tikzcd}' in result
    assert r'A' in result and r'B' in result

def test_nested_braces_not_truncated():
    # Verifies that the regex import fix makes nested braces work
    src = r'\xymatrix{ \mathrm{Hom}(A,B) \ar[r] & C }'
    result = convert_xy_body(src)
    assert r'\mathrm{Hom}(A,B)' in result
```

---

## Phase 1: Build `scripts/evaluate_xy_conversion.py`

**Purpose:** Empirically establish what SSIM score the converter achieves on
real arXiv papers before committing to any threshold or pipeline integration.

**This script does NOT touch `texphage()`.**

**Interface:**
```
python scripts/evaluate_xy_conversion.py <path_to_tex_file>
    [--out-dir DIR]   # where to write compiled PDFs (default: /tmp)
    [--ssim-threshold 0.97]
```

**What it does:**
1. Reads the `.tex` file.
2. Compiles original with `latexmk` (baseline PDF).
3. Runs `convert_xy_body()` + `convert_xy_preamble()` on the source.
4. Compiles converted source with `latexmk`.
5. Computes per-page SSIM and MSE using `pdf2image` + `scikit-image`.
6. Prints a table: page, SSIM, MSE, PASS/FAIL vs. threshold.
7. Saves side-by-side PNG comparisons for any FAIL page.

**Milestone:** Run on 5–10 arXiv papers that use `\xymatrix`. Record the
SSIM scores. This establishes the realistic threshold (expected: 0.93–0.97 for
simple diagrams; lower for crossing paths). Results should be documented in a
comment at the top of the evaluation script.

**Dependencies:** `pdf2image`, `scikit-image`, `numpy` — already in the
`[agents]` extras.

---

## Phase 2: Refactor into `src/texphage/converters/_xy_tikzcd.py`

**Prerequisites:** Phase 0 bugs fixed, Phase 1 baseline established.

**Target module:** `src/texphage/converters/_xy_tikzcd.py`

```python
"""
Pure string-manipulation XY-to-tikzcd converter.
No I/O, no side effects, no compilation.

MATCHES: \xymatrix environments with \ar arrows, basic tip/conn styles,
         curve/shift options, label positioning
LIMITATIONS:
  [observed] \xymatrix inside \vcenter is not converted; tikzcd cannot be
             used inside \vcenter.
  [observed] Crossing paths |!{[dl];[rr]}\hole require global arrow analysis;
             not supported.
  [inferred] Harpoon variants (^|, _|) produce incorrect output.
  [observed] Unsupported tip types (\(, \), \+, \/) leave arrow without tips.
  [observed] The conversion changes pixel-level rendering (XY uses MetaPost,
             tikzcd uses PGF). SSIM < 1.0 is expected and documented.
USED BY: texphage.pipeline (when convert_xy=True), texphage-convert CLI
"""
import regex as re
from texphage._regex import ...  # move patterns here as needed

def convert_xy_body(tex_body: str) -> str:
    """Replace all \xymatrix environments with tikzcd equivalents.

    If a particular \xymatrix environment uses unsupported features,
    that environment is left unchanged (with a log.warning), and processing
    continues with the next one.
    """
    ...

def convert_xy_preamble(tex_preamble: str) -> str:
    """Remove \\usepackage{xy} variants; add \\usepackage{tikz-cd} if absent."""
    result = re.sub(r'\\usepackage(?:\[[^\]]*\])?\{xy\}', '', tex_preamble)
    if r'\usepackage{tikz-cd}' not in result:
        result = result + r'\usepackage{tikz-cd}'
    return result
```

**Pattern migration:** The compiled regex patterns in `xy_to_tikz.py` must
follow the naming conventions in `.claude/notes/regex-writing.md` (load the
`regex-writing` skill before doing this). Patterns that belong in `_regex.py`
(shared with demacro) should be moved there; patterns specific to xy conversion
stay in `_xy_tikzcd.py`.

**`src/texphage/converters/__init__.py`:**
```python
from ._xy_tikzcd import convert_xy_body, convert_xy_preamble
__all__ = ["convert_xy_body", "convert_xy_preamble"]
```

**Tests:** Extend `tests/test_xy_tikzcd.py` with playground-verified
assertions. Every claim in the `LIMITATIONS` block needs a test demonstrating
the boundary behaviour (unsupported construct → original returned).

---

## Phase 3: Pipeline integration

**Prerequisites:** Phase 2 complete, Phase 1 SSIM baseline documented.

**Changes to `pipeline.py`:**

```python
def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
    *,
    convert_xy: bool = False,    # NEW
    ...
) -> tuple[str, list[Attachment]]:
    ...
    raw_tex = unfold(src_dir, main_tex)
    if convert_xy:
        from texphage.converters import convert_xy_body, convert_xy_preamble
        raw_tex = convert_xy_body(raw_tex)   # must run on raw source
    # --- preprocessing happens here ---
    body, preamble = demacro.preprocessing(raw_tex)
    if convert_xy:
        preamble = convert_xy_preamble(preamble)
    ...
```

**Important:** `convert_xy=False` by default. Adding the flag is a no-op for
all existing callers.

**Integration tests** (`pytest.mark.pipeline`, require `latexmk`): Use real
arXiv fixture files from Phase 1. Assert SSIM ≥ the threshold documented in
`evaluate_xy_conversion.py`.

---

## Phase 4: CLI entrypoint

**Only after Phase 2 and 3 are stable.**

Add to `pyproject.toml`:
```toml
texphage-convert = "texphage.cli:main_convert"
```

Usage:
```
texphage-convert xy input.tex [-o output.tex] [--strict]
  --strict: raise an error if any \xymatrix cannot be converted (default: warn and leave unchanged)
```

Implement `main_convert` in `src/texphage/cli.py` (created during formatter
implementation).

---

## Phase 5: Fidelity agent (long-term)

Define a `xy-fidelity-agent` in `CLAUDE.md` — analogous to `testing-agent` —
that downloads arXiv papers using `\xymatrix`, runs the converter, measures
SSIM, and logs failures to `BUGS.md`. This agent only makes sense after
Phase 3 establishes a stable API.

---

## Open questions

1. **What fraction of arXiv papers use `\xymatrix`?** The answer affects
   prioritisation. If < 5%, the Phase 3 pipeline integration may not be worth
   the complexity; Phase 2 (standalone converter) and Phase 4 (CLI) may be
   sufficient.

2. **Compilability vs. visual fidelity?** If the goal is just eliminating the
   `xy` package dependency (so the output compiles with only tikzcd), then the
   SSIM metric is overkill — a compile success/failure check is enough. Decide
   after Phase 1 measurements.

3. **Does the conversion need to handle `\xymatrix` inside macros?** After
   demacro, some `\xymatrix` calls may originate from macro expansion. The
   conversion runs before demacro (Phase 3 ordering), so macro-wrapped
   `\xymatrix` is not yet visible. This is a fundamental limitation; document it.

4. **`\xymatrix*` (starred form)?** The starred form changes the column spacing.
   Verify whether the current script handles it and add a test.

---

## Recommended sequencing

```
Phase 0  Fix bugs in scripts/xy_to_tikz.py         (small, do first)
         Write failing tests first
Phase 1  scripts/evaluate_xy_conversion.py          (standalone, no pipeline)
         Measure SSIM on 5-10 real arXiv XY papers
         Document threshold in script header
Phase 2  src/texphage/converters/_xy_tikzcd.py      (pure string module)
         Full playground-backed test coverage
         Load regex-writing skill before migrating patterns
Phase 3  pipeline.py: convert_xy=False flag          (additive only)
         Integration tests with real fixtures
Phase 4  texphage-convert CLI                        (after Phase 2+3)
Phase 5  xy-fidelity-agent definition in CLAUDE.md  (after Phase 3)
```
