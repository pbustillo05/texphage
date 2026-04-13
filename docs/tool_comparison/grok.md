**Category 1: LaTeX macro expansion tools**

These are standalone text-processing tools (not full TeX/LaTeX compilers or engines) that parse a `.tex` file, detect macro definitions (`\newcommand`/`\def`/etc.), and replace invocations in the body with their expanded forms. Very few general-purpose tools exist; most are simple parsers focused on common user-defined macros. No tool fully supports advanced features like `\edef`, `\let`, `\DeclareRobustCommand`, `xparse`'s `\NewDocumentCommand`, or complex expansion rules (e.g., protected/robust macros, verbatim contexts). Nested expansion and cross-file support are limited or undocumented in most cases.

- **de-macro**  
  **URL**: https://ctan.org/pkg/de-macro (also https://cs-web.bu.edu/faculty/gacs/software/de-macro/; sources in TeX Live/MiKTeX)  
  **Language**: Python  
  **Last meaningful commit / maintenance status**: Version 1.4.1 (copyright 2005–2020); still shipped in TeX Live and MiKTeX (no active GitHub development).  
  **Definition types it handles**: `\newcommand`, `\renewcommand`, `\newenvironment`, `\renewenvironment` (only those appearing in the main document or a “private” package file named `<document>-private.sty`). Does **not** handle `\def`, `\edef`, `\let`, `xparse`, optional arguments beyond basic `\newcommand` support, or kernel macros.  
  **Nested macro calls**: Not explicitly documented (simple string-based replacement; complex nesting may fail or require multiple passes).  
  **Cross-file expansion** (`\input`/`\include`): Partial — only scans the main file + its private `.sty` file; does not recursively process arbitrary `\input`ed files.  
  **Known limitations**: Extremely narrow scope (designed only for “private” author macros to satisfy journal editors). Ignores most TeX primitives and package-defined macros. No support for conditional expansion or catcode changes.

- **latex.py** (also called “latex preprocessor”)  
  **URL**: https://github.com/jobh/latex.py  
  **Language**: Python  
  **Last meaningful commit / maintenance status**: ~2010 (109 commits on master; no updates in over a decade — abandoned but functional).  
  **Definition types it handles**: `\newcommand` (via `-L` flag); also allows defining macros directly in Python (functions or strings with `#(arg)` syntax). Supports basic optional arguments via Python. Does **not** handle `\def`, `\edef`, `\let`, environments, `xparse`, or most TeX primitives.  
  **Nested macro calls**: Yes (expands recursively when `-L` is used).  
  **Cross-file expansion**: Yes for Python macro files (via `-i`); limited for LaTeX `\input` (treats them as plain text unless processed separately).  
  **Known limitations**: Dual-purpose (LaTeX macros + inline Python code blocks between `{%@ … %}@`); the Python mode is more powerful than pure LaTeX parsing. Old codebase; no support for modern LaTeX3/xparse syntax. Primarily intended for journal submission cleanup.

- **expand-latex-macros**  
  **URL**: https://pypi.org/project/expand-latex-macros/ (source tarball available; no public GitHub repo listed)  
  **Language**: Python  
  **Last meaningful commit / maintenance status**: Version 2.0.0 (April 24, 2025); actively used in recent academic NLP pipelines (e.g., LHCb corpus preprocessing).  
  **Definition types it handles**: `\def`, `\newcommand`. Does **not** handle `\edef`, `\let`, `\newenvironment`, `xparse`, optional arguments, or robust/DeclareRobustCommand.  
  **Nested macro calls**: Not documented (assumed basic substitution; may require multiple passes for deep nesting).  
  **Cross-file expansion** (`\input`/`\include`): Not documented (operates on a single string/source; no built-in recursion).  
  **Known limitations**: Extremely minimal API (`expand_latex_macros(latex_source)`); built for NLP/ML preprocessing (strip user macros before tokenization). No CLI, no handling of environments or complex TeX catcodes. Very recent but narrow scope.

No other standalone tools were found after exhaustive searches of CTAN, GitHub, PyPI, TeX.SE, and academic literature. Niche/one-off scripts (e.g., a 2010-era Perl expander for WordPress conversion or an unlinked C# tool mentioned in old TeX.SE comments) exist but lack public URLs, general parsing of arbitrary `\newcommand`/`\def`, or maintenance — they are too custom/abandoned to list here.

**Category 2: LaTeX file flattening / unfolding tools**

These resolve `\input`, `\include`, etc., into a single flat `.tex` file. None are full TeX interpreters, so they cannot evaluate conditionals (`\if`, `\includeonly`, `\ifthenelse`, etc.) or expand macros inside paths. Most are simple string-based or lexer-based processors.

- **latexpand**  
  **URL**: https://ctan.org/pkg/latexpand (GitLab: https://gitlab.com/latexpand/latexpand)  
  **Language**: Perl  
  **Inclusion commands it handles**: `\input`, `\include` (and variants like `\inputfrom` in some contexts). Does **not** handle `\includeonly`, `\subimport`, `\import`, `\inputiffileexists`, or custom directives.  
  **Preserves comments**: Yes (pure text replacement; comments are copied verbatim).  
  **Handles conditional includes**: No (explicitly does not process `\includeonly`).  
  **Known limitations**: No recursion into conditional logic or package-specific commands (e.g., `import` package). Does not strip comments or expand macros. Simple and reliable for basic multi-file documents; still actively maintained in TeX Live (v1.7.2, 2023).

- **flachtex**  
  **URL**: https://github.com/d-krupke/flachtex (PyPI: `flachtex`)  
  **Language**: Python  
  **Inclusion commands it handles**: `\include`, `\input`, `\subimport`, `\subimport*`, plus custom `%%FLACHTEX-EXPLICIT-IMPORT[path/to/file]`.  
  **Preserves comments**: Yes by default (CLI flag `--comments` or API call to remove them).  
  **Handles conditional includes**: Yes via special comment directives (`%%FLACHTEX-EXCLUDE-START/STOP`, `%%FLACHTEX-UNCOMMENT-START/STOP`, `%%FLACHTEX-RAW-START/STOP`, `%%FLACHTEX-NO-FORMAT-START/STOP`).  
  **Known limitations**: No overlapping rules; path resolution can fail without explicit imports; some edge cases with escaped characters or `changes` package highlights. Very feature-rich and actively maintained (v1.0.0, Nov 2025; extensive tests).

- **latex-flatten**  
  **URL**: https://pypi.org/project/latex-flatten/ (GitHub: rekka/latex-flatten)  
  **Language**: Python  
  **Inclusion commands it handles**: Standard `\input`/` \include` (designed for nested project structures; recurses into included files).  
  **Preserves comments**: Yes (text-based inlining).  
  **Handles conditional includes**: No.  
  **Known limitations**: Basic functionality focused on submission-ready flattening; no support for `\subimport` or custom directives. Last release Dec 2023 (v0.3.0).

- **flatex** (C version)  
  **URL**: https://ctan.org/pkg/flatex (sources in /support/flatex)  
  **Language**: C  
  **Inclusion commands it handles**: `\input`, `\include`; automatically includes the `.bbl` file if BibTeX is detected.  
  **Preserves comments**: Yes.  
  **Handles conditional includes**: No.  
  **Known limitations**: Very old (pre-2000s); no support for modern commands like `\subimport`; outputs to stdout or `.flt` file. Still available on CTAN but unmaintained.

- **flatten** (by Peter Wilson)  
  **URL**: https://ctan.org/tex-archive/support/flatten  
  **Language**: C (generated from flex lexer)  
  **Inclusion commands it handles**: `\input`, `\include` (customizable set of inclusion commands).  
  **Preserves comments**: Yes (lexer-based).  
  **Handles conditional includes**: No.  
  **Known limitations**: Last updated 1995; obsolete compared to modern tools; no `\subimport` or BibTeX `.bbl` handling. Purely archival/abandoned.

- **flat-tex**  
  **URL**: https://hackage.haskell.org/package/flat-tex (GitHub: jwaldmann/flat-tex)  
  **Language**: Haskell  
  **Inclusion commands it handles**: `\input` (recursive) and `\bibliography`.  
  **Preserves comments**: No — explicitly removes all comments and `\todo{…}` commands.  
  **Handles conditional includes**: No.  
  **Known limitations**: Opinionated (comment/todos stripping is mandatory); no `\subimport` or advanced directives. Niche/abandoned for general use but useful for clean single-file archives.

- **flatex** (Python version by johnjosephhorton)  
  **URL**: https://github.com/johnjosephhorton/flatex  
  **Language**: Python  
  **Inclusion commands it handles**: `\input` only (simple line-by-line replacement).  
  **Preserves comments**: Yes.  
  **Handles conditional includes**: No.  
  **Known limitations**: Extremely minimal (no recursion depth control, no `\include`, no `.bbl`); one-off script for quick flattening. Unmaintained.

No other dedicated flattening tools (niche, abandoned, or CTAN packages) turned up in exhaustive searches. Tools like `latexmk`, `arara`, or full converters (`latexml`, Pandoc) were excluded as they are not standalone text processors. Most flattening tools ignore macro expansion entirely — combine with a Category 1 tool if needed.