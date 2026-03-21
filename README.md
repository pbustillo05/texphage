# texphage

Unfold multi-file LaTeX projects into a single flat string and expand
user-defined macros — without running TeX.

**Primary use case:** preparing arXiv source tarballs for downstream NLP
pipelines (embedding, search, extraction) where you need clean text with
custom macros resolved but do not want to install a full TeX distribution in
your processing environment.

---

## Installation

### System dependencies (not installed by pip)

```bash
# Ubuntu/Debian:
sudo apt install texlive-full poppler-utils

# macOS:
brew install --cask mactex && brew install poppler
```

`kpsewhich` (from TeX Live) is used by `find_packages` for portable package
path resolution. `latexmk`, `pdftoppm`, and `pdfinfo` (from poppler) are
required only for the fidelity testing agent (`scripts/test_fidelity.py`).

### Python package

```bash
pip install texphage
# Or for development:
pip install -e ".[dev]"
# With fidelity testing agent dependencies:
pip install -e ".[dev,agents]"
```

---

## Quick start

```python
from texphage.unfold import unfold
from texphage.demacro import demacro

# Flatten a multi-file project into one string
tex = unfold('/path/to/arxiv/source/')

# Expand user-defined macros
expanded, packages, problems = demacro(tex)
```

`packages` is a list of `\usepackage` names found in the preamble.
`problems` is a list of `(csname, position, reason)` tuples for macros
that could not be expanded (self-referential or pattern mismatch).

---

## Why `regex` not `re`

texphage uses the third-party [`regex`](https://pypi.org/project/regex/)
package instead of Python's standard `re`. This is non-negotiable: the
bracket-matching patterns in `demacro.py` rely on two PCRE features that
Python's `re` does not support — recursive named groups `(?&name)`, which
enable balanced-brace matching without a parser, and duplicate named groups
in alternations, which allow the same capture name across multiple `|`
branches. Replacing `import regex as re` with `import re` would silently
break every `\{…\}` argument capture. Pin `regex>=2022.1.18`.

---

## The preprocessing contract

Before macro expansion, `demacro.preprocessing()` transforms the raw LaTeX
source through a strict 6-step pipeline:

1. **Protect verbatim** — `\begin{verbatim}…\end{verbatim}` (and variants:
   `Verbatim`, `lstlisting`, `minted`, `alltt`, `BVerbatim`, `LVerbatim`) are
   extracted and replaced with unique placeholder tokens. Their content must
   survive the subsequent steps unchanged.
2. **Strip comments** — `%…\n` sequences are removed. The `%` is a TeX
   comment delimiter; anything after it on a line is not source text.
3. **Paragraph preservation** — blank lines are replaced with `\par`. Without
   this step, collapsing all whitespace would destroy paragraph structure,
   making it impossible to recover paragraph breaks in the output.
4. **Whitespace collapse** — all remaining runs of whitespace (spaces, tabs,
   newlines) are collapsed to a single ASCII space. **This is the invariant
   that all regex patterns in `demacro.py` and `_regex.py` assume.** Every
   pattern is written to match tokens separated by at most one space. Patterns
   will silently mis-match if this step is skipped or run out of order.
5. **Restore verbatim** — placeholders are replaced back with the original
   verbatim content, preserving indentation and special characters.
6. **Split** — the preprocessed string is split on `\begin{document}` /
   `\end{document}` to separate preamble (macro definitions) from body.

**Anyone modifying `demacro.py` must re-read these six steps.** Breaking the
order — e.g. collapsing whitespace before protecting verbatim — will corrupt
verbatim content. Running comment stripping before verbatim protection will
strip `%` inside code listings.

---

## Known limitations

- `\expandafter` / `\csname…\endcsname` expansion not supported
- `\if`, `\ifx`, `\ifnum` and other TeX conditionals not evaluated
- Only preamble-defined macros are expanded; package-defined macros are not
- `pgfkeys` / `\tikzset` key-value macro definitions not supported
- Single-character non-letter command names (`\|`, `\!`) not handled
- `\def` with delimited patterns captures single tokens only, not multi-token
  sequences (see BUG-2 in `BUGS.md`)
- xargs positional key `[i=default]` syntax not supported (see BUG-1 in
  `BUGS.md`)

---

## Running tests

```bash
pytest tests/ -v                       # unit tests (no TeX required)
pytest tests/ -v -k "not pipeline"     # skip if latexmk unavailable
```

All unit tests in `test_unfold.py`, `test_demacro.py`, and
`test_find_packages.py` run without a TeX installation. `test_pipeline.py`
contains end-to-end regression tests that require `latexmk`.

---

## Continuous Improvement (Claude workflow)

When asking Claude to improve this codebase, Claude follows the protocol in
`agents.md`. Common triggers:

- `"Run testing agent on seed 42"` → downloads arXiv papers, compares PDF output
- `"Fix BUG-N"` → follows the Coding Agent checklist
- `"Fix next bug"` → picks the highest-severity OPEN entry in BUGS.md

Claude will always write a failing test before touching code, and will always
add `MATCHES/CAPTURES/LIMITATIONS` comments before touching regex patterns.
If Claude encounters a LaTeX construct it doesn't recognise, it will ask for
the CTAN documentation link rather than guessing.

---

## Optional: Automated CI

A basic GitHub Actions workflow can be added to run `pytest`, `ruff`, and
`mypy` on every push:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: ruff check src/
      - run: mypy src/texphage/
      - run: pytest tests/ -v
```

Note: tests that require `latexmk` (`test_pipeline.py` end-to-end) need a
TeX Live system package: `sudo apt install texlive-full` in the CI job.
