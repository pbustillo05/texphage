# texphage

The LaTeX compiler takes for input a LaTeX project and outputs a pdf. This mapping is highly non-injective and has lots of `endomorphisms` - transformations that modify the LaTeX code without affecting the pdf output. This repository is a **LaTeX rearrangement toolbox**, a collection of such transformations. The target user is both: a human wanting to clean his LaTeX project, and a NLP pipeline needing cleaned self-contained LaTeX snippets.

Current tools:
- **unfold** — resolve a large LaTeX project folder with `\input`/`\include` chains into a single flat `.tex` file
- **demacro** — expand all preamble-defined user-specific macros and produce a minimal
  preamble and body, yielding a self-contained 5-line canonical document:
  ```LaTeX
  \documentclass[...]{...}
  % <minimal preamble: mostly \usepackage commands>
  \begin{document}
  % <1-line demacro'd body>
  \end{document}
  ```
- **format** *(planned)* — reformat canonical output into human-readable LaTeX
  with consistent indentation
- **xy→tikzcd** *(in progress)* — translate legacy `\xymatrix` diagrams to
  modern tikzcd

All tools share the same regex engine, preprocessing pipeline, and fidelity
testing infrastructure. See `docs/user_applications.md` for the full catalogue of
current and planned applications (NLP pipelines, human editing tools, training
data generation, VSCode extension, …).

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

## Documentation

- [Pipeline API](docs/guide/pipeline.md) — main entry point: `texphage()`, `texphage_to_dir()`
- [demacro](docs/guide/demacro.md) — macro expansion engine: supported forms, preprocessing contract
- [unfold](docs/guide/unfold.md) — multi-file flattening: supported directives
- [find_packages](docs/guide/find_packages.md) — package discovery via kpsewhich
- [User applications](docs/user_applications.md) — full catalogue of current and planned use cases
- [Contributing](CONTRIBUTING.md) — setup, workflow, commit conventions, bug fix protocol

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

For the catalogue of applications and use cases, see `docs/user_applications.md`.
For AI workflow protocols, see `CLAUDE.md` and `.claude/`.
For bugs and future directions, see `BUGS.md` and `TODO.md`.

---
