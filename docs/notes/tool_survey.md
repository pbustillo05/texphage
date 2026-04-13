# LaTeX Preprocessing Tools — Survey

> Synthesized from 7 LLM research passes (ChatGPT-4o × 2, Codex, DeepSeek, Grok, Meta AI,
> Perplexity), April 2026; fact-checked by 5 independent LLM critiques (ChatGPT-4o, Gemini,
> Grok, Meta AI, Perplexity, Claude), April 13 2026. Claims graded **C** (confirmed from
> docs/source), **I** (inferred from tool purpose/design), or **?** (unknown/unverified).
> Cells marked **⚠️ VERIFY** are disputed across fact-checker sources; see the verification
> queue at the end of this file.

---

## Preliminary caveat

True TeX macro expansion requires a TeX engine. Every standalone text-processing tool below
approximates expansion via regex or token parsing. They will silently mis-expand macros that
involve catcode changes, conditionals, `\expandafter`, or runtime redefinitions. The practical
question is not "does this tool implement TeX?" but "how much of the macro surface that appears
in real arXiv papers does it handle?"

> **Scope definition:** This survey covers *source-preserving `.tex`-to-`.tex` rewrites* and
> *file-graph flattening* only. Tools that output XML/HTML/other formats (LaTeXML, plasTeX,
> pandoc) are included only as upper-bound references and are not directly comparable to texphage.

---

## Category 1 — Macro expansion tools

Tools that take `.tex` source, read `\newcommand`/`\def`/etc. definitions, and substitute
call sites in the body. Ordered roughly by relevance to the texphage benchmark.

### Coverage matrix

| Tool | Lang | Status | `\newcommand` | opt-arg | `\renewcommand` | `\def`/`\edef` | `\let` | `\newenvironment` | `\DeclareRobustCommand` | xparse `\NewDocumentCommand` | Nested | Cross-file | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **[texphage](https://github.com/pbustillo05/texphage)** | Python | active | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ? | ✅ C | ✅ C (`unfold`) | **reference** |
| **[de-macro](https://ctan.org/pkg/de-macro)** | Python | v1.4.1, 2020 | ✅ C | ✅ I¹ | ✅ C | ❌ C | ❌ C | ✅ C | ❌ C | ❌ C | ⚠️ C² | ⚠️ C³ | CTAN-canonical; "private macros" scope only |
| **[latexpp](https://github.com/phfaist/latexpp)** | Python | low activity | ✅ C | ✅ I | ✅ C | ❌ C | ❌ C | ? | ❌ C | ❌ C | ✅ C | ✅ C⁴ | pylatexenc backbone; YAML config; `newcommand` fix reads defs from source automatically |
| **[expand-latex-macros](https://pypi.org/project/expand-latex-macros/)** | Python | v2.0.0, Apr 2025 | ✅ C | ? | ? | ⚠️ VERIFY⁵ | ❌ | ❌ | ❌ | ❌ | ? | ❌ C | NLP/ML focus; minimal API; no CLI; ~80 LOC |
| **[flachtex](https://pypi.org/project/flachtex/)** (macro mode) | Python | ⚠️ VERIFY⁶ | ✅ C | ✅ I⁷ | ✅ C | ❌ C | ❌ | ❌ C | ❌ | ❌ | ✅ C | ✅ C⁸ | Macro substitution secondary; primarily a flattener |
| **[pandoc](https://github.com/jgm/pandoc)** (`latex_macros` ext.) | Haskell | v3.9, active 2026 | ✅ C | ✅ C | ✅ C | ✅ C | ❌ | ❌ | ❌ | ❌ | ✅ C | ❌ C | Converter, not source-preserving; macro expansion applies to math/raw LaTeX blocks only; may mangle verbatim |
| **[latexpand](https://ctan.org/pkg/latexpand)** (`--define` flag) | Perl | v1.7.2, 2023 | ⚠️ I⁹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | Primarily a flattener; `--define` is simple key→value substitution, not `\newcommand` parsing |
| **[xpandlatex](https://github.com/xpandlatex/xpandlatex)** | ⚠️ VERIFY¹⁰ | ~2016, abandoned | ✅ C | ? | ✅ C | ✅ C | ? | ✅ C | ? | ? | ? | ? | Language unconfirmed (survey said Perl; README may use Python-style argparse); sparse docs |
| **[LaTeXpander](https://github.com/LAKoubensky/LaTeXpander)** | Java | 404 / unavailable | ✅ C | ? | ? | ✅ C | ✅ C | ✅ C | ? | ? | ✅ I | ✅ I (`\input`) | GitHub page 404 as of Apr 2026 — cannot verify current state |
| **[latex.py](https://github.com/jobh/latex.py)** | Python | ~2010, abandoned | ✅ C (`-L`) | ?¹¹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | ⚠️ limited | Main feature is inline Python blocks; `-L` flag for `\newcommand`; opt-arg in `-L` mode undocumented |
| **[delatex](https://github.com/mkropat/delatex)** | Python | 404 / unavailable | ✅ C | ? | ? | ✅ C | ? | ❌ | ❌ | ❌ | ⚠️ attempted | ⚠️ `\input` | GitHub 404 as of Apr 2026; macro expansion secondary/fragile |
| **[parseLatex](https://dmurdoch.github.io/parseLatex/)** (R pkg) | R | active | ✅ C | ? | ✅ C | ✅ C | ✅ C | ✅ C | ? | ? | toolkit | ? | Parser library; no CLI; user must implement expansion |
| **[pylatexenc](https://github.com/phfaist/pylatexenc)** | Python | v2.10 (2021); v3.0 alpha active | ✅ I | ? | ? | ? | ? | ✅ I | ? | ? | partial I | ❌ | Library only; no out-of-box expander CLI; see latexpp for a CLI wrapper |
| **[plasTeX](https://github.com/plastex/plastex)** | Python | v3.1, Jan 2024; slow pace | ✅ I | ✅ I | ✅ I | ✅ I | ✅ C | ✅ I | ✅ C | ✅ C | ✅ C | ✅ I | Output is XML DOM, not `.tex`; project's own site notes "very slow" development pace |
| **[LaTeXML](https://github.com/brucemiller/LaTeXML)** | Perl | active | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | ✅ C | Output is XML; very heavyweight; not a source expander |

**Notes:**
1. de-macro opt-arg: CTAN README says only "`\newcommand` and `\renewcommand` are understood" without explicitly mentioning optional-argument support. Downgraded from C to I.
2. de-macro nested expansion: documented as "can be nested but do not be too clever" — recursive substitution works for simple cases.
3. de-macro cross-file: reads macro definitions only from `<document>-private.sty` (located via `\usepackage{<name>-private}` in the document). No arbitrary `\input` chain is followed for macro discovery.
4. latexpp: the `input.EvalInput` fix inlines `\input`/`\include` (cross-file flattening); the `newcommand` fix auto-reads `\newcommand` definitions from source; a separate `macro_subst.Subst` fix requires manual YAML listing.
5. expand-latex-macros `\def` support: **disputed** — Perplexity says supported; Grok says PyPI description is one sentence with no mention of `\def`. See V3 in the verification queue.
6. flachtex version: **disputed** — Claude and Perplexity confirm v1.0.0, Nov 2025; Grok reports v0.6.0. See V5 in the verification queue.
7. flachtex opt-arg: changelog notes "newcommand should work reliably with multiple arguments now (hopefully)" — hedged language suggests treating as I rather than C.
8. flachtex cross-file: flattens first (Category 2), then applies macro substitution to the merged file.
9. latexpand `--define` flag: simple `\foo → replacement` substitution, not `\newcommand` parsing.
10. xpandlatex language: survey originally said Perl. One fact-checker notes the README and CLI flags use Python-style argparse syntax. Cannot confirm without reading the source. See V4 in the verification queue.
11. latex.py opt-arg: the original survey listed "✅ via Python" but opt-arg support in `-L` mode (`\newcommand` expansion) is not documented. Downgraded to ?.

### Tier classification for the benchmark

| Tier | Tools | Rationale |
|---|---|---|
| **A — true demacro** | de-macro, latexpp, expand-latex-macros, texphage | Purpose-built; output is `.tex` source |
| **B — flattener + macro substitution** | flachtex, latexpand (`--define`) | Macro expansion is secondary; paired with flattening |
| **C — converter with expansion side-effect** | pandoc, plasTeX, LaTeXML | Output is not `.tex`; included as upper-bound references |
| **D — library / toolkit** | pylatexenc, parseLatex | Not CLI-ready without custom glue code |
| **E — abandoned / niche** | xpandlatex, LaTeXpander, latex.py, delatex | Not recommended for benchmark |

**Recommended for empirical run (demacro track):** de-macro, expand-latex-macros, flachtex (macro mode), latexpp. Pandoc as optional upper-bound reference.

---

## Category 2 — File flattening / unfolding tools

Tools that resolve `\input`, `\include`, and related commands into a single flat `.tex` file.
Ordered by relevance to the texphage unfold benchmark.

> **Flattening vs bundling:** *Flattening/unfolding* inlines file contents into a single
> continuous `.tex` string. *Bundling* copies files into a flat directory and updates path
> arguments without inlining content. `lateflat` and `texdirflatten` are bundlers and appear
> in a separate table at the end of this section.

### Coverage matrix

| Tool | Lang | Status | `\input` | `\include` | `\includeonly` | `\import`/`\subimport` | `\inputfrom` | `\subfile` | Preserves comments | Conditional includes | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **[texphage unfold](https://github.com/pbustillo05/texphage)** | Python | active | ✅ C | ✅ C | ? | ✅ C | ✅ C | ? | ✅ C | ❌ | **reference** |
| **[latexpand](https://ctan.org/pkg/latexpand)** | Perl | v1.7.2, 2023 | ✅ C | ✅ C | ❌ C¹ | ⚠️ VERIFY² | ? | ? | ⚠️ C³ | ❌ C | Widely used operational baseline |
| **[flachtex](https://pypi.org/project/flachtex/)** | Python | ⚠️ VERIFY⁴ | ✅ C | ✅ C | ? | ✅ C (`\subimport`, `\subimport*` only; bare `\import` ❌) | ❌ C | ? | ✅ C | ⚠️ C⁵ | Most feature-rich modern Python flattener; also does macro substitution |
| **[latexpp](https://github.com/phfaist/latexpp)** | Python | low activity | ✅ C | ✅ C | ? | ❌ I | ? | ? | ✅ C | ❌ | `input.EvalInput` fix inlines `\input`/`\include`; also handles `.bbl` inlining |
| **[FLaP](https://github.com/fchauvel/flap)** | Python | ~2020, inactive | ✅ C | ✅ C | ? | ✅ C (`\import`, `\subimport`) | ? | ? | ✅ I | ❌ | Handles import family |
| **[latex-make](https://github.com/fordsfords/latex-make)** (`lm_flatten`) | Perl | 404 / unverifiable | ✅ C | ✅ C | ? | ✅ C (`\import`, `\subimport`) | ✅ C | ? | ✅ C | ❌ | GitHub 404 as of Apr 2026; claimed strongest import-family coverage |
| **[latexdiff](https://ctan.org/pkg/latexdiff)** (`--flatten`) | Perl | v1.3.3, active 2024 | ✅ C | ✅ C | ? | ⚠️ VERIFY⁶ | ? | ✅ C | ? | ❌ | `--flatten` delegates to latexpand internally; import support depends on latexpand (see V1) |
| **[flatexpy](https://pypi.org/project/flatexpy/)** | Python | available (unverifiable) | ✅ I | ✅ I | ? | ❌ | ? | ? | ✅ I | ❌ | PyPI page unverifiable by two independent fact-checkers; downgraded C→I; handles `\graphicspath` and circular deps |
| **[latex-flatten](https://pypi.org/project/latex-flatten/)** | Python | v0.3.0, Dec 2023; inactive | ✅ C | ? | ? | ❌ | ? | ? | ✅ C | ❌ | Also replaces `\bibliography` with `.bbl`; no new releases in 12+ months |
| **[flatex](https://ctan.org/pkg/flatex)** (C) | C | v1.21, old | ✅ C | ✅ C | ? | ❌ | ❌ | ❌ | ✅ C | ❌ | Classic; also inlines `.bbl`; no modern commands |
| **[flatten](https://ctan.org/tex-archive/support/flatten)** | C/flex | 1995, archival | ✅ C | ✅ C | ? | ❌ C⁷ | ❌ | ❌ | ✅ C | ❌ | Ships with TeX Live; configurable command set |
| **[texexpand](https://www.latex2html.org/)** (latex2html) | Perl | 1986, archival | ✅ C | ✅ C | ? | ? | ? | ? | ✅ C | ❌ | Archival; still ships with TeX Live |
| **[texstrip](https://pypi.org/project/texstrip/)** | Python | v0.1.1, 2020 | via latexpand | via latexpand | — | — | — | — | — | — | Wrapper around latexpand |
| **[flatex](https://github.com/johnjosephhorton/flatex)** (Python) | Python | lightly maintained | ✅ C | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ C | ❌ | Minimal script; active repo (~70 stars) |
| **[flat-tex](https://hackage.haskell.org/package/flat-tex)** | Haskell | v0.8.2, Jan 2026; **active** | ✅ C | ✅ C | ? | ❌ | ❌ | ❌ | ❌ C | ❌ | Removes all comments and `\todo`/`\reminder` by design; previously thought abandoned |
| **[Rubber](https://github.com/rubber-org/rubber)** (`--flatten`) | Python | slow development (GitHub 404) | ✅ C | ✅ C | ? | ? | ? | ? | ✅ C | ❌ | Full compilation system; flattening is incidental |

**Notes:**
1. latexpand `\includeonly`: CTAN page explicitly states "The script does not deal with `\includeonly` commands." ❌ confirmed.
2. latexpand `\import`/`\subimport`: **disputed across fact-checkers.** Grok claims support was added in v1.4-1 (2018). Claude and Perplexity say the CTAN page only documents `\input`/`\include`. See V1 in the verification queue.
3. latexpand comment handling: strips comments by default; `--keep-comments` flag preserves them.
4. flachtex version: **disputed** — Claude and Perplexity confirm v1.0.0, Nov 2025; Grok reports v0.6.0. See V5.
5. flachtex conditional handling: partial, via `%%FLACHTEX-EXCLUDE-START/STOP` comment directives (**not** `%%FLACHTEX-SKIP-*` as previously stated — corrected from fact-check) — not TeX-level conditional evaluation.
6. latexdiff `\import`/`\subimport`: original survey marked ✅ C but `--flatten` delegates to latexpand internally, so support is entirely derivative of latexpand's own handling, which is disputed. Downgraded to ⚠️ VERIFY. See V2.
7. flatten and `\import` family: explicitly confirmed as NOT handled via a latexdiff GitHub issue (#172).

### Directory bundling tools

These tools reorganize a multi-file project by copying files into a flat directory and updating
path references. They do **not** inline file contents into a single `.tex` string, and are
not interchangeable with the flatteners above.

| Tool | Lang | Status | Notes |
|---|---|---|---|
| **[lateflat](https://pypi.org/project/lateflat/)** | Python | v0.1.3, Sep 2025 | PyPI description: "flatten a LaTeX project into a single root directory" — copies files, updates `\input`/`\include`/`\includegraphics` paths; does NOT inline content. Categorical error in previous version of this survey (listed as content inliner). |
| **[texdirflatten](https://ctan.org/pkg/texdirflatten)** | Perl | v1.3, 2017 | Also a bundler; `--onetex` mode approximates content inlining. |

### Benchmark relevance for unfold track

The interesting benchmark axis for unfold is **`\import`/`\subimport` support**, since texphage's
`unfold` handles these (unlike most competitors):

| Import-family support | Tools |
|---|---|
| ✅ Full (`\import`, `\subimport`, `\inputfrom`) | texphage, FLaP, latex-make |
| ✅ Partial (`\subimport` only) | flachtex |
| ⚠️ Disputed | latexpand, latexdiff (`--flatten`) |
| ❌ None | flatex, flatten, most Python tools |

**Recommended for empirical run (unfold track):** latexpand (common operational baseline), flachtex (best modern Python rival).

---

## Cross-cutting notes

### Tools that do both (Category 1 + 2)

**flachtex** and **latexpp** are the only tools that deliberately do both macro substitution
and file flattening. flachtex flattens first, then applies substitution. latexpp applies
both via distinct "fix" modules controlled by a YAML config file. This makes flachtex directly
comparable to running latexpand + de-macro in sequence.

### Tools excluded from the benchmark

- **LaTeXML** and **plasTeX**: output XML, not `.tex`. Useful as fidelity oracles but not comparable to texphage.
- **pandoc**: output is a target-format document; macro expansion applies only in math/raw LaTeX scope, not to normal text macros. Useful to show "how much does a popular converter handle?" but not a true source-preserving expander.
- **arara**: general-purpose TeX task runner (orchestrates compilation toolchains like `latexmk`); not a source transformer. Can be configured to invoke latexpand, but does not perform flattening or expansion itself.
- **Make4ht** / **Rubber**: full compilation systems; flattening is incidental.
- **latexmk**: gathers dependencies but does not stitch them into a single `.tex` file.

### The `import` package (CTAN)

The LaTeX `import` package (https://ctan.org/pkg/import) defines the commands
`\import`, `\subimport`, `\includefrom`, `\subincludefrom`, `\inputfrom`, `\subinputfrom`, and
starred variants (`\import*`, `\subimport*`, etc.). Many arXiv papers use these for
subdirectory-structured projects. **Most flatteners do not handle these commands** — this is
the key differentiator where texphage's `unfold` stands out.

### Reality check on macro expansion

No standalone text-processing tool fully handles the TeX macro surface. The ranking
of ambition is roughly:

> LaTeXML ≈ plasTeX >> pandoc > texphage ≈ de-macro > expand-latex-macros > flachtex (macro mode)

But LaTeXML and plasTeX are too heavyweight for source-preserving normalization. Among
source-preserving tools, texphage targets the widest surface (`\def`, `\let`, `\newenvironment`,
counters, environments, starred variants).

---

## Verification queue

The following claims are **disputed across fact-checkers** or were **inaccessible during
fact-checking**. Each is a candidate for a targeted web-search agent run.

| # | Tool | Claim in dispute | Evidence for | Evidence against |
|---|---|---|---|---|
| **V1** | **latexpand** (Cat 2) | `\import`/`\subimport` support | Grok: changelog entry "Support for import and subimport" in v1.4-1 (2018-04-18) | Claude, Perplexity: CTAN page only lists `\input`/`\include`; Perplexity cites latexdiff issue #172 as confirming NOT handled |
| **V2** | **latexdiff `--flatten`** (Cat 2) | `\import`/`\subimport` support | Original survey: ✅ C | Claude: `--flatten` delegates to latexpand; if latexpand doesn't support import, neither does this. Depends on V1. |
| **V3** | **expand-latex-macros** (Cat 1) | `\def` support | Perplexity: ✅ (PyPI description confirms `\newcommand` and `\def`) | Grok: PyPI description is one sentence, no `\def` mentioned; Grok marks ❌ |
| **V4** | **xpandlatex** (Cat 1) | Implementation language | Survey: Perl | Claude: GitHub README CLI flags use Python-style argparse syntax — may be Python |
| **V5** | **flachtex** (Cat 1 + 2) | Version number | Claude, Perplexity: v1.0.0, Nov 17 2025 (confirmed from PyPI/GitHub) | Grok: v0.6.0 with "Significant refactoring" changelog entry; no v1.0.0 found |
| **V6** | **lateflat** (Cat 2) | Content inliner vs directory bundler | Claude: PyPI description says "flatten into a single root directory" = copies files, not inlines content | Already moved to bundler table; verify PyPI description directly |
| **V7** | **flatexpy** (Cat 2) | All capability claims | Original survey: ✅ C for `\input`, `\include`, comment preservation | Claude: PyPI page unverifiable; Perplexity: page returned no results. Downgraded to I. |
| **V8** | **de-macro** (Cat 1) | Optional-argument support | Original survey: ✅ C | Claude: CTAN README only says "`\newcommand` and `\renewcommand` are understood" — no explicit mention of opt-args. Downgraded to ✅ I. |
