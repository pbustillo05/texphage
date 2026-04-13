# LaTeX Preprocessing Tools — Survey

> Synthesized from 7 LLM research passes (ChatGPT-4o × 2, Codex, DeepSeek, Grok, Meta AI,
> Perplexity), April 2026. Claims are graded **C** (confirmed from docs/source), **I** (inferred
> from tool purpose/design), or **?** (unknown/unverified). Conflicts between sources are noted.

---

## Preliminary caveat

True TeX macro expansion requires a TeX engine. Every standalone text-processing tool below
approximates expansion via regex or token parsing. They will silently mis-expand macros that
involve catcode changes, conditionals, `\expandafter`, or runtime redefinitions. The practical
question is not "does this tool implement TeX?" but "how much of the macro surface that appears
in real arXiv papers does it handle?"

---

## Category 1 — Macro expansion tools

Tools that take `.tex` source, read `\newcommand`/`\def`/etc. definitions, and substitute
call sites in the body. Ordered roughly by relevance to the texphage benchmark.

### Coverage matrix

| Tool | Lang | Status | `\newcommand` | opt-arg | `\renewcommand` | `\def`/`\edef` | `\let` | `\newenvironment` | `\DeclareRobustCommand` | xparse `\NewDocumentCommand` | Nested | Cross-file | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **[texphage](https://github.com/pbustillo05/texphage)** | Python | active | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ? | ✅ C | ✅ C (`unfold`) | **reference** |
| **[de-macro](https://ctan.org/pkg/de-macro)** | Python | v1.4.1, 2021 | ✅ C | ✅ C | ✅ C | ❌ C | ❌ C | ✅ C | ❌ C | ❌ C | ⚠️ C¹ | ⚠️ C² | CTAN-canonical, "private macros" scope only |
| **[expand-latex-macros](https://pypi.org/project/expand-latex-macros/)** | Python | v2.0.0, Apr 2025 | ✅ C | ? | ? | ✅ C | ❌ | ❌ | ❌ | ❌ | ? | ❌ C | NLP/ML focus; minimal API; no CLI |
| **[flachtex](https://pypi.org/project/flachtex/)** (macro mode) | Python | v1.0.0, Nov 2025 | ✅ C | ✅ C | ? | ❌ C | ❌ | ❌ C | ❌ | ❌ | ✅ C | ✅ C³ | Macro substitution is secondary; primarily a flattener |
| **[pandoc](https://github.com/jgm/pandoc)** (`latex_macros` ext.) | Haskell | active 2026 | ✅ C | ✅ C | ✅ C | ✅ C | ❌ | ❌ | ❌ | ❌ | ✅ C | ❌ C | Converter, not a source preserving tool; may mangle verbatim |
| **[latexpand](https://ctan.org/pkg/latexpand)** (`--define` flag) | Perl | v1.7.2, 2023 | ⚠️ I⁴ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | Primarily a flattener; `--define` is simple key→value substitution |
| **[xpandlatex](https://github.com/xpandlatex/xpandlatex)** | Perl | ~2016, abandoned | ✅ C | ? | ✅ C | ✅ C | ? | ? | ? | ? | ? | ? | Sparse docs; abandoned |
| **[LaTeXpander](https://github.com/LAKoubensky/LaTeXpander)** | Java | minimal activity | ✅ C | ? | ? | ✅ C | ✅ C | ✅ C | ? | ? | ✅ I | ✅ I (`\input`) | Personal project; less tested |
| **[latex.py](https://github.com/jobh/latex.py)** | Python | ~2010, abandoned | ✅ C (`-L`) | ✅ via Python | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | ⚠️ limited | Also supports inline Python blocks |
| **[delatex](https://github.com/mkropat/delatex)** | Python | 2015, abandoned | ✅ C | ? | ? | ✅ C | ? | ❌ | ❌ | ❌ | ⚠️ attempted | ⚠️ `\input` | Macro expansion is secondary/fragile feature |
| **[parseLatex](https://dmurdoch.github.io/parseLatex/)** (R pkg) | R | active | ✅ C | ? | ✅ C | ✅ C | ✅ C | ✅ C | ? | ? | toolkit | ? | Parser library; no CLI; user must implement expansion |
| **[pylatexenc](https://github.com/phfaist/pylatexenc)** | Python | v2.10, 2024 | ✅ I | ? | ? | ? | ? | ✅ I | ? | ? | partial I | ❌ | Library only; no out-of-box expander CLI |
| **[plasTeX](https://github.com/plastex/plastex)** | Python | v3.x, 2022–23 | ✅ I | ✅ I | ✅ I | ✅ I | ✅ C | ✅ I | ✅ C | ✅ C | ✅ C | ✅ I | Output is XML DOM, not `.tex`; heavyweight |
| **[LaTeXML](https://github.com/brucemiller/LaTeXML)** | Perl | active | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | Output is XML; very heavyweight; not a source expander |

**Notes:**
1. de-macro nested expansion: documented as "can be nested but do not be too clever" — recursive substitution works for simple cases.
2. de-macro cross-file: only scans `<document>-private.sty`; does **not** recursively follow arbitrary `\input` calls.
3. flachtex cross-file: flattens first (Category 2), then applies macro substitution to the merged file.
4. latexpand `--define` flag: simple `\foo → replacement` substitution, not `\newcommand` parsing.

### Tier classification for the benchmark

| Tier | Tools | Rationale |
|---|---|---|
| **A — true demacro** | de-macro, expand-latex-macros, texphage | Purpose-built; output is `.tex` source |
| **B — flattener + macro substitution** | flachtex, latexpand (`--define`) | Macro expansion is secondary; paired with flattening |
| **C — converter with expansion side-effect** | pandoc, plasTeX, LaTeXML | Output is not `.tex`; included as upper-bound references |
| **D — library / toolkit** | pylatexenc, parseLatex | Not CLI-ready without custom glue code |
| **E — abandoned / niche** | xpandlatex, LaTeXpander, latex.py, delatex | Not recommended for benchmark |

**Recommended for empirical run (demacro track):** de-macro, expand-latex-macros, flachtex (macro mode). Pandoc as an optional upper-bound reference.

---

## Category 2 — File flattening / unfolding tools

Tools that resolve `\input`, `\include`, and related commands into a single flat `.tex` file.
Ordered by relevance to the texphage unfold benchmark.

### Coverage matrix

| Tool | Lang | Status | `\input` | `\include` | `\includeonly` | `\import`/`\subimport` | `\inputfrom` | `\subfile` | Preserves comments | Conditional includes | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **[texphage unfold](https://github.com/pbustillo05/texphage)** | Python | active | ✅ C | ✅ C | ? | ✅ C | ✅ C | ? | ✅ C | ❌ | **reference** |
| **[latexpand](https://ctan.org/pkg/latexpand)** | Perl | v1.7.2, 2023 | ✅ C | ✅ C | ❌ C | ⚠️ C¹ | ? | ? | ⚠️ C² | ❌ C | The gold standard; used in arXiv/journal workflows |
| **[flachtex](https://pypi.org/project/flachtex/)** | Python | v1.0.0, Nov 2025 | ✅ C | ✅ C | ? | ✅ C (`\subimport`, `\subimport*`) | ? | ? | ✅ C | ⚠️ C³ | Most feature-rich modern Python flattener; also does macro substitution |
| **[FLaP](https://github.com/fchauvel/flap)** | Python | ~2020, inactive | ✅ C | ✅ C | ? | ✅ C (`\import`, `\subimport`) | ? | ? | ✅ I | ❌ | Merges into flat directory; handles import family |
| **[latex-make](https://github.com/fordsfords/latex-make)** (`lm_flatten`) | Perl | active | ✅ C | ✅ C | ? | ✅ C (`\import`, `\subimport`) | ✅ C | ? | ✅ C | ❌ | Part of build system; strongest import-family coverage |
| **[latexdiff](https://ctan.org/pkg/latexdiff)** (`--flatten`) | Perl | active 2026 | ✅ C | ✅ C | ? | ✅ C (`\import`, `\subimport`) | ? | ✅ C | ? | ❌ | Designed for diffs; `--flatten` is incidental; active |
| **[flatexpy](https://pypi.org/project/flatexpy/)** | Python | available | ✅ C | ✅ C | ? | ❌ | ? | ? | ✅ C | ❌ | Handles `\graphicspath` and circular deps; no `\subimport` |
| **[latex-flatten](https://pypi.org/project/latex-flatten/)** | Python | v0.3.0, Dec 2023 | ✅ C | ? | ? | ❌ | ? | ? | ✅ C | ❌ | Also replaces `\bibliography` with `.bbl` |
| **[lateflat](https://pypi.org/project/lateflat/)** | Python | v0.1.3, Sep 2025 | ✅ C | ? | ? | ❌ | ? | ? | ✅ I | ❌ | Very new; updates `\includegraphics` paths |
| **[flatex](https://ctan.org/pkg/flatex)** (C) | C | v1.21, old | ✅ C | ✅ C | ? | ❌ | ❌ | ❌ | ✅ C | ❌ | Classic; also inlines `.bbl`; no modern commands |
| **[flatten](https://ctan.org/tex-archive/support/flatten)** | C/flex | 1995, archival | ✅ C | ✅ C | ? | ❌ C⁴ | ❌ | ❌ | ✅ C | ❌ | Archival; ships with TeX Live; configurable command set |
| **[texexpand](https://www.latex2html.org/)** (latex2html) | Perl | 1986, archival | ✅ C | ✅ C | ? | ? | ? | ? | ✅ C | ❌ | Archival; still ships with TeX Live |
| **[texdirflatten](https://ctan.org/pkg/texdirflatten)** | Perl | v1.3, 2017 | ✅ C | ✅ C | ? | ? | ? | ? | ? | ❌ | Primarily a bundling tool; `--onetex` for flattening |
| **[texstrip](https://pypi.org/project/texstrip/)** | Python | v0.1.1, 2020 | via latexpand | via latexpand | — | — | — | — | — | — | Wrapper around latexpand |
| **[flatex](https://github.com/johnjosephhorton/flatex)** (Python) | Python | unmaintained | ✅ C | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | ❌ | Minimal one-off script |
| **[flat-tex](https://hackage.haskell.org/package/flat-tex)** | Haskell | ~2018, abandoned | ✅ C | ✅ C | ? | ❌ | ❌ | ❌ | ❌ C | ❌ | Removes all comments by design |
| **[Rubber](https://github.com/rubber-org/rubber)** (`--flatten`) | Python | slow development | ✅ C | ✅ C | ? | ? | ? | ? | ✅ C | ❌ | Full compilation system; flattening is incidental |

**Notes:**
1. latexpand and `\import`/`\subimport`: sources conflict. Official CTAN page only mentions `\input`/`\include`; some third-party docs claim partial import support. Treat as unverified until tested.
2. latexpand comment handling: strips comments by default; `--keep-comments` flag preserves them.
3. flachtex conditional handling: partial, via `%%FLACHTEX-SKIP-START/STOP` comment directives — not TeX-level conditional evaluation.
4. flatten and `\import` family: explicitly confirmed as NOT handled via a latexdiff GitHub issue (#172).

### Benchmark relevance for unfold track

The interesting benchmark axis for unfold is **`\import`/`\subimport` support**, since texphage's `unfold` handles these (unlike most competitors):

| Import-family support | Tools |
|---|---|
| ✅ Full (`\import`, `\subimport`, `\inputfrom`) | texphage, latex-make, latexdiff, FLaP |
| ✅ Partial (`\subimport` only) | flachtex |
| ❌ None | latexpand (likely), flatex, flatten, most Python tools |

**Recommended for empirical run (unfold track):** latexpand (gold standard baseline), flachtex (best modern Python rival).

---

## Cross-cutting notes

### Tools that do both (Category 1 + 2)

**flachtex** is the only tool that deliberately does both macro substitution and file flattening. It flattens first, then applies substitution. This makes it directly comparable to running latexpand + de-macro in sequence.

### Tools excluded from the benchmark

- **LaTeXML** and **plasTeX**: output XML, not `.tex`. Useful as fidelity oracles but not comparable to texphage.
- **pandoc**: output is a target-format document. Useful to show "how much does a popular converter handle?" but not a true source-preserving expander.
- **arara**: meta-tool; delegates to latexpand.
- **Make4ht** / **Rubber**: full compilation systems; flattening is incidental.

### The `import` package (CTAN)

The LaTeX `import` package (https://ctan.org/pkg/import) defines the commands
`\import`, `\subimport`, `\includefrom`, `\subincludefrom`, `\inputfrom`, `\subinputfrom`, and
starred variants. Many arXiv papers use these for subdirectory-structured projects. **Most
flatteners do not handle these commands** — this is the key differentiator where texphage's
`unfold` stands out.

### Reality check on macro expansion

No standalone text-processing tool fully handles the TeX macro surface. The ranking
of ambition is roughly:

> LaTeXML ≈ plasTeX >> pandoc > texphage ≈ de-macro > expand-latex-macros > flachtex (macro mode)

But LaTeXML and plasTeX are too heavyweight for source-preserving normalization. Among
source-preserving tools, texphage handles the widest surface (`\def`, `\let`, `\newenvironment`,
counters, environments, starred variants).
