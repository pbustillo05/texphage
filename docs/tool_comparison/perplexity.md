Below is an as-exhaustive-as-practical catalog of standalone LaTeX preprocessing tools I could verify for your two categories. I’m including both active and niche/abandoned projects that explicitly flatten includes or expand macros, and I’ll call out where a tool is only partially relevant or where the docs don’t support a feature claim. [ctan](https://ctan.org/tex-archive/support/flatten)

## Category 1: Macro expansion tools

### xpandlatex
- **URL:** [GitHub](https://github.com/xpandlatex/xpandlatex) [github](https://github.com/xpandlatex/xpandlatex)
- **Language:** Perl, based on the repository/docs style and CTAN-era distribution; the project is presented as a LaTeX processor script. [github](https://github.com/xpandlatex/xpandlatex)
- **Maintenance status:** Appears old/abandoned; the visible GitHub snapshot is from 2016 and no recent maintenance signal was surfaced in search results. [github](https://github.com/xpandlatex/xpandlatex)
- **Definitions handled:** Explicitly supports `\def`, `\newcommand`, and `\renewcommand`; the project description says it can do macro handling, but the verified snippet does not confirm optional arguments, `\let`, `\edef`, `\newenvironment`, `\DeclareRobustCommand`, or xparse commands. [github](https://github.com/xpandlatex/xpandlatex)
- **Nested macro calls:** The repo describes macro processing, but I did not find a verified statement that it recursively expands nested user macros. Treat as **unverified/likely limited**. [github](https://github.com/xpandlatex/xpandlatex)
- **Cross-file expansion:** Not verified from the surfaced docs. [github](https://github.com/xpandlatex/xpandlatex)
- **Known limitations:** Documentation surfaced here is sparse, so the safest characterization is that it is a lightweight macro processor, not a full TeX engine, and feature coverage beyond basic macro definitions is unconfirmed. [github](https://github.com/xpandlatex/xpandlatex)

### expand-latex-macros
- **URL:** [PyPI](https://pypi.org/project/expand-latex-macros/) [pypi](https://pypi.org/project/expand-latex-macros/)
- **Language:** Python. [pypi](https://pypi.org/project/expand-latex-macros/)
- **Maintenance status:** Actively packaged on PyPI with a recent release page visible in 2025. [pypi](https://pypi.org/project/expand-latex-macros/)
- **Definitions handled:** The project says it “removes all user-defined macros” and substitutes their definitions back in, but the surfaced description does not enumerate supported definition forms. Verified support for `\newcommand`-style user macros is implied; support for optional args, `\def`, `\edef`, `\let`, `\newenvironment`, `\DeclareRobustCommand`, and xparse commands is **not verified** from the retrieved page. [pypi](https://pypi.org/project/expand-latex-macros/)
- **Nested macro calls:** Not verified from the surfaced description. [pypi](https://pypi.org/project/expand-latex-macros/)
- **Cross-file expansion:** Not verified. [pypi](https://pypi.org/project/expand-latex-macros/)
- **Known limitations:** Intended for preprocessing LaTeX source for NLP, so it is likely narrower than a full TeX expansion model; the PyPI page does not document support for advanced TeX conditionals or package-defined command semantics. [pypi](https://pypi.org/project/expand-latex-macros/)

### latexpand
- **URL:** [CTAN](https://ctan.org/tex-archive/support/latexpand) [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Language:** Perl. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)
- **Maintenance status:** Actively maintained enough to have a CTAN directory updated in 2026. [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Definitions handled:** The verified docs say it **flattens** by expanding `\include` and `\input`, and it also has a `--define <key>=<val>` option to replace macro occurrences like `\foo`; the surfaced docs do not show it parsing arbitrary TeX macro definitions such as `\newcommand`, `\def`, `\let`, `\edef`, `\newenvironment`, `\DeclareRobustCommand`, or xparse commands. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)
- **Nested macro calls:** Not verified as a general macro expander; its core feature is inclusion flattening plus simple replacement definitions. [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Cross-file expansion:** Yes for `\input` and `\include`; the docs explicitly state that those are expanded into a single file. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)
- **Known limitations:** It is primarily a flattener; the page emphasizes comment removal and simple macro substitution rather than full semantic expansion, so it is not a substitute for TeX’s own macro engine. [ctan](https://ctan.org/tex-archive/support/latexpand)

### latexdiff
- **URL:** [CTAN](https://ctan.org/tex-archive/support/latexdiff) [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Language:** Perl. [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Maintenance status:** Actively maintained; CTAN package and docs are current in 2026. [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Definitions handled:** Not a macro-expansion tool per se, but its `--flatten` mode expands included files for diffing. It is not documented here as a general `\newcommand`/`\def` expander. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)
- **Nested macro calls:** Not the focus; no verified support claim from the surfaced docs. [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Cross-file expansion:** Yes, via `--flatten`; the manual says flatten is recursive and can handle `\input`, `\import`, `\subimport`, and `\subfile` includes. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)
- **Known limitations:** It processes LaTeX source for revision markup, not generic TeX; the package notes restrictions and minor caveats. [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)

### pandoc
- **URL:** I did not retrieve an official page in this pass, but the searched issue threads show relevant behavior discussions. [github](https://github.com/jgm/pandoc/issues/4253)
- **Language:** Haskell.  
- **Maintenance status:** Active upstream project, but I did not verify this directly from a primary source in this pass.  
- **Definitions handled:** Search results show support/discussion for `\newcommand`-like definitions and macro expansion behavior, but the surfaced evidence is not enough to treat it as a purpose-built LaTeX macro-expansion tool. [github](https://github.com/jgm/pandoc/issues/4470)
- **Nested macro calls:** Likely limited and context-dependent; the search result explicitly references “nested LaTeX macro expansions” as an issue, which suggests this is not complete TeX-like expansion. [github](https://github.com/jgm/pandoc/issues/4253)
- **Cross-file expansion:** Not verified in this pass.  
- **Known limitations:** It is primarily a document converter, not a standalone LaTeX macro expander; I would include it in a benchmark only if you want “incidental” macro handling, not as a core macro-engine baseline. [github](https://github.com/jgm/pandoc/issues/4470)

## Category 2: File flattening / unfolding tools

### flatten
- **URL:** [CTAN](https://ctan.org/tex-archive/support/flatten) [ctan](https://ctan.org/pkg/flatten?lang=en)
- **Language:** C / lex-based program built from `flatten.l` and a Makefile, according to the CTAN source instructions. [ctan](https://ctan.org/tex-archive/support/flatten)
- **Inclusion commands handled:** By default `\input` and `\include`; CTAN says the set of inclusion commands is configurable. [ctan](https://ctan.org/tex-archive/support/flatten)
- **Preserves comments:** Not indicated in the surfaced CTAN text, so treat as **unverified**. [ctan](https://ctan.org/tex-archive/support/flatten)
- **Conditional includes:** Not verified. [ctan](https://ctan.org/tex-archive/support/flatten)
- **Known limitations:** The docs emphasize flattening inclusion files into one root file; it is not documented here as understanding complex TeX conditionals or macro-generated file names. A GitHub issue on latexdiff notes that `flatten` does **not** handle `import` package commands like `\import` and `\subimport`, which is a useful limitation to benchmark against. [github](https://github.com/ftilmann/latexdiff/issues/172)

### latexpand
- **URL:** [CTAN](https://ctan.org/tex-archive/support/latexpand) [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Language:** Perl. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)
- **Inclusion commands handled:** Expands `\input` and `\include`; the docs also mention `--expand-usepackage` and other options, but the core flattening is around those two commands. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)
- **Preserves comments:** No; the docs explicitly say it removes comments and outputs a single LaTeX file with no comments by default. [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Conditional includes:** Not verified. [ctan](https://ctan.org/tex-archive/support/latexpand)
- **Known limitations:** It is a practical flattener, not a full parser; it supports extra options like `--empty-comments` and `--expand-bbl`, which highlights that it solves common preprocessing tasks rather than arbitrary TeX semantics. [ctan.math.utah](https://ctan.math.utah.edu/ctan/tex-archive/support/latexpand/latexpand)

### latexdiff
- **URL:** [CTAN](https://ctan.org/tex-archive/support/latexdiff) [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Language:** Perl. [ctan](https://ctan.org/tex-archive/support/latexdiff?lang=en)
- **Inclusion commands handled:** Its `--flatten` mode handles `\input`, recursively nested `\input`, the `import` package commands `\import` and `\subimport`, and `\subfile`. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)
- **Preserves comments:** Not verified from the surfaced docs. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)
- **Conditional includes:** Not verified. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)
- **Known limitations:** Designed for diffing, not general-purpose file unfolding; the manual notes that it is for LaTeX, not generic TeX, and that there are caveats around flattening. [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0)

### import package
- **URL:** [CTAN](https://ctan.org/pkg/import) [ctan](https://ctan.org/pkg/import?lang=en)
- **Language:** TeX macro package, not a standalone flattener. [ctan](https://ctan.org/pkg/import?lang=en)
- **Inclusion commands handled:** It provides `\import`, `\subimport`, `\includefrom`, `\subincludefrom`, and starred variants, all of which establish relative-path input behavior through standard LaTeX mechanisms. [ctan](https://ctan.org/pkg/import?lang=en)
- **Preserves comments:** Not applicable as a flattener itself.  
- **Conditional includes:** Not a flattener; it changes how inclusion works. [ctan](https://ctan.org/pkg/import?lang=en)
- **Known limitations:** Use this as a benchmark target for flattener support because many flatteners fail on it; `flatten` was specifically noted as not handling these commands in an issue thread. [github](https://github.com/ftilmann/latexdiff/issues/172)

## Practical benchmark notes

| Tool | Category | Main strength | Main gap |
|---|---|---|---|
| xpandlatex | Macro expansion | Basic LaTeX macro processing | Sparse docs; advanced TeX features unverified  [github](https://github.com/xpandlatex/xpandlatex) |
| expand-latex-macros | Macro expansion | Simple user-macro substitution | Advanced definition forms unverified  [pypi](https://pypi.org/project/expand-latex-macros/) |
| latexpand | Flattening | `\input`/`\include` flattening and comment removal | Not a full macro expander  [ctan](https://ctan.org/tex-archive/support/latexpand) |
| flatten | Flattening | Classic standalone flattener | Doesn’t handle `import` package commands well  [ctan](https://ctan.org/tex-archive/support/flatten) |
| latexdiff --flatten | Flattening | Recursive flattening, including `import` and `subfile` | Purpose-built for diffs, not general unfolding  [texdoc](https://texdoc.org/serve/latexdiff-man.pdf/0) |

## What I would add next
If you want, I can do a second pass and turn this into a more benchmark-friendly spreadsheet with columns like:
- tool,
- category,
- URL,
- active/abandoned,
- supported commands,
- recursion,
- cross-file handling,
- comment preservation,
- conditional handling,
- and a short “benchmark risk” note.

I can also keep digging for more niche CTAN, GitHub, and PyPI projects specifically mentioned in TeX Stack Exchange or old mailing-list threads, but within the sources verified here, these are the concrete standalone tools I could substantiate. [ctan](https://ctan.org/tex-archive/support/flatten)