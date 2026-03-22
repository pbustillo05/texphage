---
name: playground-protocol
description: >
  How to use scripts/latex_playground.py as the oracle for all test assertions.
  Load before writing any test or verifying any fix. Contains Templates A, C, D.
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
