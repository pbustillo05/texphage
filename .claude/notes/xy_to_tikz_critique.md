# XY-to-TikZ: Critique and Implementation Design

## What this is

`xy_to_tikz.py` is a standalone script (not yet integrated into texphage) that
converts `\xymatrix` diagrams to `tikzcd`. Two Gemini prompts propose integrating
it: one builds an evaluation harness (`xy_to_tikz_integration_prompt.md`), the
other designs a full pipeline integration with a fidelity agent
(`xy_to_tikz_agent_prompt.md`).

This note critiques both, identifies concrete bugs in the existing code, and
specifies what a correct implementation should look like.

---

## Part 1: Bugs in the existing `xy_to_tikz.py`

These must be fixed before anything else.

### 1.1 `import re` instead of `import regex as re`

`embed_brackets` builds a pattern with a recursive named group `(?&bracket%i)`.
This is a PCRE feature not supported by Python's `re`. Using `import re` means
every call to `find_xymatrix` silently fails to match nested braces correctly.
This is a project-standard violation (see `docs/project-context.md` §"Why regex
not re"). Fix: `import regex as re`.

### 1.2 `print(ar)` at module level (line 102)

```python
ar = re.sub(r'\#\s*','', ar)
print(ar)          # <-- side effect on import
find_ar = re.compile(ar)
```

Every import of this module dumps the raw arrow regex (several hundred
characters) to stdout. Must be removed.

### 1.3 Five `match.grouo(...)` typos

Lines 128, 144, 147, 160, 163 all read `match.grouo(...)` instead of
`match.group(...)`. These raise `AttributeError` at runtime whenever the
corresponding named group is non-None. They are currently masked only if those
branches are never exercised in tests.

Affected groups: `uppos`, `downpos` (×2), `midpos` (×2).

### 1.4 `else` branch in `replace_xymatrix` silently returns a partial result

Lines 260–264: when an unknown operator is encountered in XY options, the
function prints an error and returns a `tikzcd` without the options. This is
a silent partial conversion — the caller gets a string that looks converted but
may be wrong. It should raise an exception or return the original unchanged.

---

## Part 2: Conceptual problems with the conversion itself

### 2.1 XY and tikzcd have different layout engines

XY (via `xy.sty`) renders arrows in MetaPost; tikzcd uses PGF. Their:
- Default row/col sep differ (XY: 2pc ≈ 2.4em; tikzcd: 2.8em by default, though
  the script hardcodes 1.8em which is already wrong for the default tikzcd).
- Font selection for labels may differ depending on preamble.
- Arrow tip rendering is visually different at any resolution.

Even a semantically perfect translation will produce pixel-level differences.
The proposed SSIM threshold of 0.99 is almost certainly unreachable for real
arXiv papers. No baseline has been measured. This threshold needs empirical
grounding before it can be a useful default.

### 2.2 The conversion is inherently incomplete

The script itself documents unsupported constructs:
- `\xymatrix` inside `\vcenter` (tikzcd cannot be inside `\vcenter`)
- Crossing paths: `|!{[dl];[rr]}\hole` (needs `crossing over` on the *other*
  arrow — requires global arrow analysis)
- Several tip types: `\(`, `\)`, `\+`, `\/`
- Harpoon variants `^|`, `_|`

These are not edge cases. Crossing paths appear in many commutative diagram
papers.

### 2.3 Preprocessing mismatch

texphage's preprocessing collapses all whitespace to a single space (step 4 of
the 6-step pipeline). `xy_to_tikz.py` was written for raw, unprocessed LaTeX.
After whitespace collapse, `\xymatrix` content changes: newlines that TeX uses
as implicit `\\` row separators are collapsed. The existing patterns assume at
most one space between tokens, which is fine, but `\\` row separators inside the
matrix body that relied on newlines are already gone after preprocessing. The
conversion must run on the *raw* source, not the preprocessed string, or the
pipeline integration point must be before preprocessing.

### 2.4 The NLP use case doesn't benefit from this conversion

The stated project goal is: "feeding NLP pipelines where custom macros must be
resolved so that a snippet can be compiled and understood with a minimal
preamble."

For NLP, the semantic content of a commutative diagram (node labels, arrow
directions) is the same in XY and tikzcd. Converting XY to tikzcd does not make
the content more understandable to a downstream model. It only changes the
*rendering package*, not the *content*. The conversion is useful for:

1. Eliminating the `xy` package dependency in the output (so the output
   compiles with only `tikz-cd`).
2. Feeding downstream tools that prefer tikzcd.

Neither is the primary texphage use case. This is legitimate but should be
framed as "reduce package dependencies" not "improve NLP pipeline output."

---

## Part 3: Problems with the proposed architecture

### 3.1 The fidelity check is expensive and misplaced in the core pipeline

The proposed `converters.py::convert_xy()` runs two full `latexmk` compilations
and a SSIM comparison for every paper containing `\xymatrix`. A single `latexmk`
run takes 15–60 seconds. This makes the pipeline unsuitable for batch processing
of arXiv tarballs (which is the main use case).

Even with `convert_xy_to_tikz=False` by default, having the fidelity check *in*
`converters.py` means the module carries heavy deps (`pdf2image`, `scikit-image`,
`numpy`) that don't belong in the core package.

Better: the fidelity check belongs in a standalone evaluation script
(`scripts/evaluate_xy_conversion.py`), not in the pipeline-facing API.

### 3.2 Two incompatible API proposals

The integration prompt proposes `xy_to_tikzcd(tex)` — a simple string→string
function. The agent prompt proposes `convert_xy_body(tex_body)` +
`convert_xy_preamble(tex_preamble)` as separate functions. These are
contradictory and need to be reconciled before implementation.

The split into body/preamble is cleaner and matches how texphage already
separates preamble from body (via the preprocessing split on `\begin{document}`).
The body function should operate on the raw body only; preamble manipulation is
separate.

### 3.3 The `xy_tikz_fidelity_agent` is premature

The proposal calls for a dedicated long-running agent to iteratively improve
the converter. This makes sense *after* the converter achieves basic correctness
on the supported subset. Right now, with five typos, a broken import, and
module-level side effects, the converter has never been successfully exercised
end-to-end. The agent infrastructure is premature.

### 3.4 The evaluation harness fixture is wrong

The fixture in `xy_to_tikz_integration_prompt.md` (lines 40–61) mixes XY syntax
and tikzcd syntax in the same document and includes a tikzcd diagram that uses
`\ar[r,"f"]` — which is PGF-keys notation, not XY. This would not be a valid XY
source file. The fixture needs to be pure XY input to be a useful test.

---

## Part 4: What a correct implementation looks like

### Phase 0: Fix the existing script (prerequisite)

Before any integration work, fix `xy_to_tikz.py` in place:
1. `import regex as re`
2. Remove `print(ar)` on line 102
3. Fix all five `match.grouo` typos → `match.group`
4. Change the silent-fallback `else` branches to raise `ValueError`

These are all mechanical fixes. Write tests first (see §4.4).

### Phase 1: Build the evaluation harness only

Implement `scripts/evaluate_xy_conversion.py` per the integration prompt, but
with a correct fixture and without pipeline integration. This gives empirical
SSIM baselines before committing to any threshold.

The script:
- Takes a `.tex` file path
- Compiles original with `latexmk`
- Runs conversion using the fixed `xy_to_tikz.py`
- Compiles converted
- Reports SSIM + MSE per page
- Does NOT integrate into `texphage()` — it is a diagnostic tool

This is cheap to build and immediately useful for calibrating the SSIM
threshold.

### Phase 2: Refactor into `src/texphage/_xy_converter.py`

Only after Phase 0 and Phase 1 produce a working, tested converter:

```python
# src/texphage/_xy_converter.py
"""
Pure string-manipulation XY-to-tikzcd converter.
No I/O, no side effects, no compilation.

MATCHES: \xymatrix environments with \ar arrows, basic tip/conn styles,
         curve/shift options, label positioning
LIMITATIONS:
  [observed] \xymatrix inside \vcenter is not converted (tikzcd cannot be
             inside \vcenter)
  [observed] Crossing paths |!{...}\hole are not converted
  [inferred] Harpoon variants (^|, _|) produce incorrect output
  [observed] Unsupported tips (\(, \), \+, \/) silently produce empty strings
"""
import regex as re

# ... (the pattern definitions from xy_to_tikz.py) ...

def convert_xy_body(tex_body: str) -> str:
    """Replace all \xymatrix environments with tikzcd equivalents."""
    return re.sub(find_xymatrix, replace_xymatrix, tex_body)

def convert_xy_preamble(tex_preamble: str) -> str:
    """Remove \usepackage{xy} variants and add \usepackage{tikz-cd}."""
    result = re.sub(r'\\usepackage(?:\[[^\]]*\])?\{xy\}', '', tex_preamble)
    if r'\usepackage{tikz-cd}' not in result:
        result = result + r'\usepackage{tikz-cd}'
    return result
```

There is no `convert_xy()` function with fidelity check here. The fidelity check
stays in the evaluation script.

### Phase 3: Optional pipeline integration (deferred)

Only add `convert_xy_to_tikz: bool = False` to `texphage()` after:
- Phase 1 establishes that SSIM ≥ X is achievable on a sample of real arXiv XY papers
- The conversion runs on the raw source (before preprocessing), not the whitespace-collapsed body
- The conversion is gated by a feature flag and adds zero overhead when disabled
- The fidelity check is NOT run as part of the pipeline (too slow for batch use)

The pipeline integration point must be before `demacro.preprocessing()` because
preprocessing collapses whitespace, which corrupts the `\\` row separators inside
`\xymatrix` content.

### Phase 4: Standalone CLI (deferred, low priority)

`texphage-convert-xy` as a CLI entry point is useful if the tool is meant for
interactive use by paper authors. For the NLP pipeline use case, it is not
needed. Defer until there is a concrete user need.

### 4.4 Test strategy

Tests should be grounded in playground output per project convention. For unit
tests of the converter (no TeX needed):

```python
# tests/test_xy_converter.py
from texphage._xy_converter import convert_xy_body, convert_xy_preamble

def test_simple_arrow():
    src = r'\xymatrix{ A \ar[r]^f & B }'
    result = convert_xy_body(src)
    assert r'\begin{tikzcd}' in result
    assert r'\arrow[r, "{f}"]' in result  # verify with playground

def test_preamble_swap():
    src = r'\usepackage[all]{xy}'
    result = convert_xy_preamble(src)
    assert r'\usepackage{xy}' not in result
    assert r'\usepackage{tikz-cd}' in result
```

For integration tests (require latexmk), use `pytest.mark.pipeline` and real
arXiv fixture files with documented SSIM scores.

---

## Part 5: Recommended sequencing

```
Phase 0  Fix bugs in xy_to_tikz.py               (small, do first)
Phase 1  Build scripts/evaluate_xy_conversion.py  (standalone, no pipeline touch)
         → measure SSIM on 5–10 real arXiv papers
         → establish realistic threshold (likely 0.93–0.97, not 0.99)
Phase 2  Refactor into src/texphage/_xy_converter.py
         → pure string functions, no fidelity check
         → full test coverage via playground
Phase 3  Pipeline integration (IF Phase 1 shows it's viable)
         → hook point: BEFORE preprocessing
         → feature flag, no overhead when disabled
         → NO latexmk compilation in the pipeline path
Phase 4  CLI entrypoint (IF there's demand)
```

The `xy_tikz_fidelity_agent` concept is fine as a long-term vision. It should
be defined in `CLAUDE.md` similarly to `testing-agent` and `coding-agent` once
Phase 2 is complete and there is a stable API for it to work against.

---

## Part 6: Open questions before proceeding

1. **What fraction of arXiv papers use `\xymatrix`?** The script header mentions
   checking `.log` files. This number affects prioritization — if it's < 5% of
   papers, the effort may not be worth the pipeline complexity.

2. **What SSIM score does a good human translation achieve?** Until this is
   measured on 5–10 examples, the 0.99 threshold is a guess. Run the evaluation
   harness (Phase 1) and report back.

3. **Is the goal compilability or visual fidelity?** If compilability (the output
   must compile with only tikzcd, no xy package), then SSIM is the wrong metric —
   a compilation success/failure check is sufficient. If visual fidelity, SSIM is
   correct but the threshold needs calibration.

4. **Does the conversion need to handle papers where `\xymatrix` appears inside
   macros?** After demacro expansion, some `\xymatrix` calls may be the result
   of macro expansion and the raw source may not show them. The pipeline
   integration point timing matters here.
