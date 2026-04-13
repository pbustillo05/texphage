Building a benchmark for LaTeX processing is a rabbit hole — most tools overlap, many are abandoned, and almost none do true TeX-level macro expansion without running TeX. Here is an exhaustive survey from CTAN, PyPI, GitHub, and Hackage, split by your two categories.

## Category 1: LaTeX macro expansion tools

These take `.tex` source and replace macro *uses* with definitions — they do **not** compile to DVI/PDF.

| Name | URL | Language | Last meaningful commit | Definitions handled | Nested calls | Cross-file | Known limitations |
| --- | --- | --- | --- |
| **de-macro** | https://ctan.org/pkg/de-macro | Python | 1.4.1 – 2021-04-10 | `\newcommand`, `\renewcommand`, `\newenvironment`, `\renewenvironment` | Yes – "can be nested but do not be too clever" | Yes – processes `\input{file}` and `\input file` recursively | No `\def`, `\edef`, `\let`, `\DeclareRobustCommand`, xparse `\NewDocumentCommand`; expansion order differs from TeX; ignores macros defined in class files unless in `-private.sty` |
| **flachtex** | https://pypi.org/project/flachtex/ | Python | 0.6.0 – 2023 (changelog shows 0.3.11+ fixes) | `\newcommand`, `\newcommand*`, plus optional substitution via `--newcommand` flag | Yes – substitutes recursively when enabled | Yes – expands `\input`, `\include`, `\subimport` before substitution | Only simple parameter replacement; does not parse TeX catcodes; fails on `\def`, `\let`, `\edef`, `\DeclareRobustCommand`, xparse; designed for analysis, not perfect fidelity |
| **pandoc** (latex_macros extension) | https://github.com/jgm/pandoc | Haskell | active – 2026 releases | `\newcommand`, `\renewcommand`, `\providecommand`, `\def` (with optional args) – bug reports show `\newcommand\foo[1][x]{...}` expansion | Yes – expands macros inside math and text | No – single-file parse, does not follow `\input` | Not a standalone expander; loses xparse and `\DeclareRobustCommand`; intended for conversion, so expansion can mangle verbatim |
| **plasTeX** | https://github.com/plastex/plastex | Python | 3.x – last major updates 2022-2023 | `\newcommand`, `\renewcommand`, `\newenvironment`, `\def`, `\edef`, `\let`, `\DeclareRobustCommand`, `\NewDocumentCommand` (via Python macro classes) | Yes – full macro processor | Yes – follows `\input`, `\include` | Heavyweight framework, not a simple text filter; requires writing Python classes for complex macros; output is XML DOM, not plain TeX |
| **pylatexenc** (latexwalker) | https://github.com/phfaist/pylatexenc | Python | 2.10 – 2024 | Parses `\newcommand` etc. via macro dictionary; user must supply expansion | Partial – can walk tokens recursively | No native `\input` handling | Library, not CLI; does not implement TeX expansion semantics; no `\edef` or xparse out of box |
| **latexml** (excluded as full processor, listed for completeness) | https://github.com/brucemiller/LaTeXML | Perl | active | Almost all LaTeX2e including xparse | Yes | Yes | Not "standalone text-processing" – builds full XML, very slow |


> Reality check: true TeX macro expansion requires a TeX engine. All standalone tools above approximate by regex/token parsing. de-macro remains the only CTAN-blessed tool purpose-built for this task.

## Category 2: LaTeX file flattening / unfolding tools

These resolve inclusion commands into one file.

| Name | URL | Language | Inclusion commands handled | Preserves comments | Conditional includes | Known limitations |
| --- | --- | --- | --- |
| **latexpand** | https://ctan.org/pkg/latexpand | Perl | `\input`, `\include`, `\includeonly` (excluded), `\import`, `\subimport`, `\includegraphics`, `\lstinputlisting` | Optional `--keep-comments` (default strips) | No – ignores `\if... \input` logic | Does not expand macros; version 1.7.2 (2023-02-27) |
| **flatex** (C) | https://ctan.org/pkg/flatex | C | `\input`, `\include` | Yes – copies verbatim | No | Also inlines `.bbl`; v1.21 by Sariel Har-Peled; no `\subimport`, no Unicode path handling |
| **flatten** | https://ctan.org/tex-archive/support/flatten | C (flex) | `\input`, `\include` (customizable) | Yes | No | From 1995-10-29; requires building with flex; no support for LaTeX3 syntax |
| **texexpand** | part of latex2html | Perl | `\input`, `\include` | Recognizes `%` as comment | No | Minimal; shipped with TeX Live since 1986 |
| **flatex** (Python, PyPI) | https://pypi.org/project/flatex/ | Python | `\input`, `\include` (top-level only) | Yes | No | Explicitly "will not handle nested include statements"; last release 2022-07-15 |
| **flatexpy** | https://pypi.org/project/flatexpy/ | Python | `\input`, `\include` recursively | Optional – `ignore_commented_lines` | No | Handles `\graphicspath`, circular deps; no `\subimport`, no bibtex yet |
| **lateflat** | https://pypi.org/project/lateflat/ | Python | `\input`, `\includegraphics` path updates | Yes | No | v0.1.3 (2025-09-06); merges files but keeps separate graphics |
| **latex-flatten** | https://pypi.org/project/latex-flatten/ | Python | `\input` | Yes | No | Also replaces `\bibliography` with `.bbl`; v0.1.0 (2023-12-14) |
| **flachtex** | https://pypi.org/project/flachtex/ | Python | `\input`, `\include`, `\subimport`, `\subimport*`, `%%FLACHTEX-EXPLICIT-IMPORT` | Optional `--comments` removes | Partial – via `%%FLACHTEX-SKIP-START/STOP` blocks | Traceable flattening; slower; also does macro substitution |
| **FLaP** | https://github.com/fchauvel/flap | Python | `\input`, `\include`, `\subimport`, `\import` | Yes | No | Merges into flat directory; last commit ~2020; no active maintenance |
| **flat-tex** | https://hackage.haskell.org/package/flat-tex | Haskell | `\input`, `\include` | No – removes all comments by design | No | GPL-2.0; unmaintained since ~2018 |


### Notes for benchmarking

- **Macro expansion vs flattening overlap**: flachtex is the only tool that deliberately does both, which makes it useful as a baseline but also means its macro substitution is intentionally lossy (see example where `\importantterm` becomes `\emph{ImportantTerm}\xspace`).
- **Abandoned niche tools**: `flatten` (1995) and `texexpand` (1986) still ship with TeX Live, so they appear in real workflows despite age.
- **No tool handles xparse perfectly** without a TeX engine. If your benchmark includes `\NewDocumentCommand` with complex argument specs, expect all standalone tools to fail – that is a feature of TeX, not a bug in the tools.