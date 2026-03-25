# texphage — shared project context

## Project goal

texphage is a **LaTeX rearrangement toolbox**: a collection of tools that
restructure LaTeX source with no (or minimal, documented) impact on the
compiled PDF. All tools share the same regex engine (`_regex.py`), the same
preprocessing contract (see §The preprocessing contract), and the same fidelity
testing infrastructure.

Current tools: **unfold** (resolve `\input`/`\include` chains), **demacro**
(expand preamble macros → canonical 5-line document). Planned tools: a
**pretty-printer** (`texphage-format`), an **xy→tikzcd converter**, and more
(see `docs/user_applications.md` for the full catalogue).

### Core tool: demacro

The demacro tool takes an arXiv LaTeX tarball and produces a canonical 5-line
document (documentclass + minimal usepackage + 1-line demacro'd body) without
changing the PDF output. Primary uses: feeding NLP pipelines (embedding,
search, extraction), and as the basis for any downstream tool that needs
macros resolved first.

## The 5-line output format

```LaTeX
\documentclass[...]{...}
% <minimal preamble containing mostly a list of \usepackage[...]{...} commands>
\begin{document}
% <1-line demacro'ed body>
\end{document}
```

## Why `regex` not `re`

texphage uses the third-party [`regex`](https://pypi.org/project/regex/)
package instead of Python's standard `re`. This is non-negotiable: the
bracket-matching patterns in `demacro.py` rely on two PCRE features that
Python's `re` does not support — recursive named groups `(?&name)`, which
enable balanced-brace matching without a parser, and duplicate named groups
in alternations, which allow the same capture name across multiple `|`
branches. Replacing `import regex as re` with `import re` would silently
break every `\{…\}` argument capture. Pin `regex>=2022.1.18`.

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

## Stack

- **Runtime:** Python ≥3.10, `regex>=2022.1.18`, `filelock>=3.12`
- **Dev:** `ruff>=0.4`, `mypy>=1.8`, `pytest>=7.4`, `pytest-cov`
- **Agents extras:** `pdf2image`, `pdfplumber`, `scikit-image`, `numpy`, `tqdm`, `requests`

## System dependencies on PATH

```
latexmk      — TeX Live; compiles baseline and pipeline output PDFs
kpsewhich    — TeX Live; used by find_packages.py for portable package path resolution
pdftoppm     — poppler-utils; used by pdf2image for PDF→PNG conversion
pdfinfo      — poppler-utils; for page count extraction
texdef       — texlive-extra-utils or MacTeX; macro introspection (TeX-internal definition)
pdftotext    — poppler-utils; used by latex_playground.py for text extraction
```

Install: `sudo apt install texlive-full poppler-utils` (Linux) or
`brew install --cask mactex && brew install poppler` (macOS).

## Key source modules

- **`src/texphage/unfold.py`** — recursively resolves `\input`/`\include` directives to produce a single flat `.tex` string from a multi-file project.
- **`src/texphage/demacro.py`** — main macro expansion engine: preprocessing, `find_all`, `build_dictionary`, and `expand`.
- **`src/texphage/_regex.py`** — compiled regex patterns and lambda pattern-builders used by `demacro.py`; the DANGER ZONE.
- **`src/texphage/pipeline.py`** — public API (`texphage()`, `texphage_to_dir()`, `build_minimal_preamble()`); orchestrates unfold → demacro → preamble extraction.
- **`src/texphage/find_packages.py`** — discovers which LaTeX packages a document uses via `kpsewhich` path resolution.

## Test commands

```bash
pytest tests/ -v                       # unit tests (no TeX required)
pytest tests/ -v -k "not pipeline"     # skip if latexmk unavailable
```

## Commit convention

Conventional Commits + BUG-N reference:
```
fix(demacro): handle <construct> in <definition style> (BUG-N)
test: add failing test for BUG-N (fails before fix)
docs: update known limitations
```

## Tracking files

- **`BUGS.md`** — open regressions only (OPEN/IN_PROGRESS). Fixed bugs live in `docs/FIXED_BUGS.md`.
- **`docs/FIXED_BUGS.md`** — read-only archive of resolved bugs. Do not reopen entries here.
- **`TODO.md`** — planned features, enhancements, and low-priority edge cases. Never mix with BUGS.md.
- **`docs/EVOLUTION.md`** — project direction log: completed phases, key architectural decisions, and intentional non-decisions. Read before starting any major new effort (use `/orient` skill).
- **`docs/macros.md`** — implementation reference for macro definition coverage (updated by macro_coverage_agent).
- **`docs/inclusions.md`** — implementation reference for file inclusion coverage (updated by inclusion_coverage_agent).
- **`docs/user_applications.md`** — catalogue of all current and planned toolbox applications with status.
