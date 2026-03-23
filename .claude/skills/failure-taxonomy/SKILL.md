---
name: failure-taxonomy
description: >
  The three failure modes (A/B/C) for texphage bugs, with pattern probe
  code and diagnostic paths. Load before any bug triage, before writing
  any test, and before any coding-agent or testing-agent run.
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

## Diagnostic Paths

### For `undefined_control_sequence \foo` (Mode A or B)

**Step 1 — Get the macro's definition. The right tool depends on what you know.**

**If you know (or can infer) which package defines `\foo`:**
Go directly to the `.sty` source — this is faster and more reliable than texdef.
- **CTAN online (preferred — always up-to-date):**
  `https://mirror.ctan.org/macros/latex/contrib/<pkg>/<pkg>.sty`
  or the package page: `https://ctan.org/pkg/<pkg>`
- **Local TexLive (fallback):**
  `kpsewhich <pkg>.sty` gives the file path; read it directly.
  The local distribution at `/usr/local/texlive/` may be outdated — if texdef
  output and CTAN source disagree, trust CTAN.
- **texdoc:** `texdoc <pkgname>` or `https://texdoc.org/pkg/<pkgname>`

For TeX primitives or LaTeX2e kernel macros:
- **TeXbook / texbytopic:** https://texdoc.org/serve/texbytopic/0
- **LaTeX2e source:** https://ctan.org/pkg/source2e

When reading source, look for: exact argument syntax, expansion result,
starred variants, and what happens when optional args are absent.

**If you do NOT know which package defines `\foo`:**
Use `texdef` to discover the package and see TeX's internal representation:
```bash
texdef -t latex -f \\foo
```
texdef uses the local TexLive installation. If the local distro is outdated,
the output may not match current CTAN — cross-check with CTAN if uncertain.

**Step 2 — Pattern probe (Template B): does find_all see the definition?**

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

If `\foo`'s definition does NOT appear → **Mode A**. The pattern is missing or wrong.
If present but wrong → **Mode B**.

**Step 3 — Run `expand()` with DEBUG logging** to trace every substitution
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

### For compile errors not involving `\undefined` (Mode B or C)

1. Compare `pipeline_output.tex` against the original source to see what changed.
2. If the error involves a verbatim-like environment with mangled content → Mode C.
   Check `_VERBATIM_ENVS` in `demacro.py`. Identify the responsible package.
3. If the error involves brace mismatch or environment mismatch:
   find the relevant macro definition in the preamble, run Template B above
   to confirm expected expansion, then run the pattern probe.

---

### For visual diff pages (SSIM < 0.95)

Open `visual_diff/page_N_diff.png`. Determine: is the difference a content
change (wrong text) or a layout shift (same text, different position)?
- Layout shift only → likely acceptable reflow from macro expansion; LOW/MEDIUM.
- Content change → run **Playground Template A** (in `playground-protocol` skill)
  with the suspect macro to confirm what TeX produces, then trace the demacro
  output to find the discrepancy.

---

### For multi-macro interaction bugs

If a paper fails but every suspect macro tests correctly in isolation:
1. Run the playground with the **full preamble** (all definitions together),
   not just the minimal reproducer.
2. If it compiles in the playground with the full preamble but fails with a
   single definition → interaction bug; note this explicitly in BUGS.md.
3. Interaction bugs are often caused by one macro expanding into a call to
   another — trace the expansion chain with DEBUG logging.
