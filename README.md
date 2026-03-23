# texphage

Unfold multi-file LaTeX projects into a single 5-lines document of the form:
```LaTeX
\documentclass[...]{...}
% <minimal preamble containing mostly a list of \usepackage[...]{...} commands>
\begin{document}
% <1-line demacro'ed body>
\end{document}
```
without changing the PDF output at all.

**Primary use case:** preparing arXiv source tarballs for downstream NLP
pipelines (embedding, search, extraction) where custom macros must be resolved
so that a snippet can be compiled and understood with a minimal preamble.

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
`texdef` (from `texlive-extra-utils` or MacTeX) is used by agents for
debugging macro definitions.

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
from texphage import texphage, texphage_to_dir

# --- Option A: get the canonical .tex string and attachment list ---
# Compile canonical_tex from src_dir so relative image paths resolve.
canonical_tex, attachments = texphage('/path/to/arxiv/source/')
# canonical_tex  — the 5-line .tex string (compile from src_dir)
# attachments    — list of Attachment(tex_ref, src_path) for images, .bib, etc.

# --- Option B: write everything to a self-contained output directory ---
canonical_path = texphage_to_dir(
    src_dir    = '/path/to/arxiv/source/',
    output_dir = '/path/to/output/',
    # attachments_subdir='unalienable'  ← default
)
# Writes:
#   /path/to/output/canonical.tex          ← 5-line canonical document
#   /path/to/output/unalienable/figures/   ← images, .bib files, etc.
# Paths inside canonical.tex are rewritten to point into unalienable/.
```

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

## Known limitations

- `\expandafter` / `\csname…\endcsname`: the common `\expandafter\def\csname name\endcsname{body}` idiom is supported (direct and one-level-deep via preamble call expansion); deeply nested or dynamically computed names are not
- `\if`, `\ifx`, `\ifnum` and other TeX conditionals not evaluated
- Only preamble-defined macros are expanded; package-defined macros are not
- `pgfkeys` / `\tikzset` key-value macro definitions not supported
- Single-character non-letter command names (`\|`, `\!`) not handled
- `\def` with delimited patterns captures single tokens only, not multi-token
  sequences (see BUG-2 in `BUGS.md`)
- xargs positional key `[i=default]` syntax not supported (see BUG-1 in
  `BUGS.md`)

---

For AI workflow protocols, see `CLAUDE.md`, `.claude/`, `GEMINI.md` and `.gemini/`.
For bugs and future directions, see `BUGS.md` and `TODO.md`.

---
