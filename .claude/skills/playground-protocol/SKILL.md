---
name: playground-protocol
description: >
  How to use scripts/latex_playground.py as the oracle for all test assertions.
  Load before writing any test or verifying any fix. Contains Templates A, C, D, E, F.
---

## Template B — Pattern probe

Template B (does `find_all` see the definition? what does `build_dictionary` store?)
lives in the **`failure-taxonomy`** skill, not here. Load that skill for diagnostic
probe code. This skill covers playground invocations only (Templates A, C, D).

---

## The playground as oracle

**Every test assertion must be anchored to playground output.** TeX is the
oracle — your test must assert what TeX actually produces, not what you think
it should produce. `compile_snippet` compiles a minimal document with
`latexmk` and extracts the PDF text via `pdftotext`. This is ground truth.

The comment `# Playground verified: ...` in test code is not decoration —
it is proof that the assertion is grounded in TeX reality. Always include it.

---

## `doc()` helper (used in all templates)

```python
def doc(preamble, body):
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")
```

---

## Template A — Verify expansion correctness

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

---

## Template C — Batch verification after a fix

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

---

## Template D — Characterise an unknown macro variant

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

## Writing tests anchored to playground output

```python
def test_<construct>_BUG_N():
    # Playground verified: <definition> + <call> → "<expected>"
    # compile_snippet(preamble=..., body=...).pdf_text == '<expected>'
    preamble = r'<definition>'
    expanded, _, _ = demacro(doc(preamble, r'<call>'))
    assert '<expected substring>' in expanded  # positive: correct output present
    assert '<wrong substring>' not in expanded  # negative: bug symptom absent
```

Run the test and **confirm it fails** before touching any source code.

---

## Template E — Single snippet visual inspection

**Question:** What does this TeX fragment actually render as?

Use when `pdf_text` is insufficient (math symbols, spacing, fonts).
`use_standalone=True` gives a tight crop for self-contained fragments.
Do NOT use standalone when the snippet depends on page geometry or floats.

```python
from pathlib import Path
import shutil
from scripts.latex_playground import compile_snippet

keep = Path('/tmp/pg_probe')
result = compile_snippet(
    body=r'\( \int_0^1 x^2 \, dx = \tfrac{1}{3} \)',
    preamble=r'\usepackage{amsmath}',
    use_standalone=True,
    visual=True,
    keep_dir=keep,
)

if result.ok:
    # Use the Read tool on result.png_path — multimodal, no extra steps.
    print(result.png_path)
else:
    print(result.error_lines)

shutil.rmtree(keep)   # always clean up
```

Context cost: standalone PNG at 150 DPI ≈ 1–3k tokens.

---

## Template F — Multi-snippet visual comparison

**Question:** Are these TeX variants visually equivalent?

Snippets must be COMPLETE `.tex` strings (documentclass included).
Protocol: **diff first** — read the diff image before loading individual PNGs.

```python
from pathlib import Path
import shutil
from scripts.latex_playground import compare_snippets

snippets = [
    r"""\documentclass[border=4pt]{standalone}
\begin{document}$\frac{d}{dx}\sin x = \cos x$\end{document}""",

    r"""\documentclass[border=4pt]{standalone}
\begin{document}$(\sin x)' = \cos x$\end{document}""",
]

keep = Path('/tmp/pg_compare')
result = compare_snippets(snippets, keep_dir=keep, labels=['Leibniz', 'Prime'])

print(f"SSIM(0,1): {result.ssim_scores[(0, 1)]:.4f}")

# Step 1: Read result.diffs[(0, 1)] first.
#   Uniform/dark image → visually identical → done.
#   Bright regions → proceed to step 2.
# Step 2: Read result.pngs[0] and result.pngs[1].

shutil.rmtree(keep)
```

Context budget:

| Images loaded | Approx tokens |
|---|---|
| 1 diff PNG (standalone) | ~1–3k |
| diff + both PNGs (standalone) | ~5–10k |
| diff + both PNGs (full page) | ~30–50k |
