# demacro — Macro Expansion Engine

`demacro.py` is the core of texphage. It reads a flat LaTeX string, parses all
macro definitions from the preamble, and replaces every macro call in the
document body with its fully expanded form — producing output whose PDF is
identical to the original.

Most users get macro expansion for free via [`texphage()`](pipeline.md). Call
`demacro()` directly only if you need access to the intermediate outputs
(package list, problematic macros) or are building a custom pipeline.

---

## Why macro expansion matters

arXiv LaTeX papers define hundreds of custom shorthand macros:

```latex
\newcommand{\R}{\mathbb{R}}
\newcommand{\norm}[1]{\left\lVert #1 \right\rVert}
\DeclareMathOperator{\Tr}{Tr}
```

These make source opaque to NLP models and batch processors. After demacro, the
body contains only standard LaTeX — no custom definitions needed.

---

## The preprocessing contract

Before macro expansion, demacro normalises the raw LaTeX string through six
steps **in this exact order**:

1. **Protect verbatim** — `\begin{verbatim}…\end{verbatim}` (and variants:
   `Verbatim`, `lstlisting`, `minted`, `alltt`, `BVerbatim`, `LVerbatim`) are
   extracted and replaced with opaque placeholders. Their content is never
   touched by subsequent steps.

2. **Strip comments** — `%…\n` sequences are removed (`\%` is preserved).

3. **Preserve paragraph breaks** — blank lines become `\par` tokens so
   paragraph structure survives the next step.

4. **Collapse whitespace** — all remaining runs of whitespace (spaces, tabs,
   newlines) are collapsed to a single space. **This is the invariant that all
   patterns in `_regex.py` assume.** Every regex is written for
   single-space-separated tokens.

5. **Restore verbatim** — placeholders are replaced back with the original
   verbatim content.

6. **Split** — the string is split on `\begin{document}` / `\end{document}` to
   separate preamble from body.

Breaking this order corrupts the output. Step 4 after step 1 would destroy
verbatim content; step 2 before step 1 would strip `%` inside code listings.

---

## Supported macro definition styles

| LaTeX form | Notes |
|------------|-------|
| `\newcommand{\foo}{body}` | Standard, 0–9 arguments, optional default |
| `\newcommand{\foo}[n]{body}` | n mandatory arguments |
| `\newcommand{\foo}[n][default]{body}` | n args, first is optional with default |
| `\renewcommand{\foo}{body}` | Treated identically to `\newcommand` |
| `\newcommand*{\foo}{body}` | Starred form; treated identically to unstarred |
| `\def\foo{body}` | Plain TeX `\def`, 0 arguments |
| `\def\foo#1#2{body}` | `\def` with 1–9 positional arguments |
| `\def\foo#1#2\relax{body}` | `\def` with delimited argument (single-token only — see limitations) |
| `\edef\foo{body}` | Immediate expansion of body at definition time |
| `\DeclareMathOperator{\foo}{name}` | `amsmath`; expands to `\operatorname{name}` |
| `\DeclareMathOperator*{\foo}{name}` | Starred form (limits above/below) |
| `\newtheorem{env}{label}` | Theorem-like environments — preserved in preamble, not expanded |
| xparse `\NewDocumentCommand` | Basic positional and optional-with-default arguments |
| xparse `\DeclareDocumentCommand` | Same |
| `\expandafter\def\csname name\endcsname{body}` | Direct and one-level-deep via preamble call |

---

## API reference

### `demacro(tex)`

The main entry point. Parse, expand, and return.

```python
from texphage.demacro import demacro

expanded_body, packages, problems = demacro(raw_tex)
```

**Parameter:** `tex: str` — flat LaTeX string (typically produced by
[`unfold()`](unfold.md)). Should contain `\begin{document}…\end{document}`.

**Returns** `tuple[str, list, list]`

| Element | Type | Description |
|---------|------|-------------|
| `expanded_body` | `str` | Document body with all resolvable macros expanded. |
| `packages` | `list[str]` | Package names found in the preamble (via `\usepackage`). |
| `problems` | `list[tuple]` | `(csname, position, reason)` for each macro that could not be expanded. `reason` is `'pattern_mismatch'` or `'no_progress'`. |

---

### `preprocessing(tex)`

Normalise a raw LaTeX string through the 6-step contract above.

```python
from texphage.demacro import preprocessing

preamble, document, packages = preprocessing(raw_tex)
```

**Returns** `tuple[str, str, list]`: normalised preamble, normalised body,
package name list.

---

### `build_dictionary(preamble)`

Parse a preprocessed preamble and build the macro expansion dictionary.

```python
from texphage.demacro import build_dictionary

macro_dict, find_macro = build_dictionary(preamble)
```

**Returns** `tuple[dict, str]`

- `macro_dict` — maps `csname → [match_pattern, replacement_fn]`
- `find_macro` — compiled regex alternation string used by `expand()` to locate
  macro calls in the body

---

### `expand(document, macro_dict, find_macro)`

Expand all macro calls in a preprocessed document body.

```python
from texphage.demacro import expand

expanded, problems = expand(document, macro_dict, find_macro)
```

**Returns** `tuple[str, list]` — expanded body and problem list (same format as
`demacro()` above).

---

## Limitations

The following constructs are **not** expanded:

- **TeX conditionals** — `\if`, `\ifx`, `\ifnum`, `\ifdefined`, etc. are not
  evaluated; their branches are left as-is.
- **Package-defined macros** — only macros defined in the preamble of the
  source file are expanded; `\textbf`, `\frac`, etc. are left untouched.
- **`pgfkeys` / `\tikzset`** — key-value macro definitions are not supported.
- **Delimited `\def`** — `\def\foo#1\relax{body}` captures only a single
  token, not a multi-token sequence (see BUG-2).
- **xargs positional key `[i=default]`** — not supported (see BUG-1).
- **Single-character non-letter commands** — `\|`, `\!`, `\/` not handled.
- **Deeply nested `\csname`** — one-level-deep `\expandafter\def\csname…\endcsname`
  is supported; deeper nesting or dynamically computed names are not.

For the full list of open regressions, see [`BUGS.md`](../../BUGS.md).
