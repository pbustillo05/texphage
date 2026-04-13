 Here is a **single giant markdown table** with the broadest **verified** set I can provide now, split into the two categories you asked for.

> ⚠️ I’m being explicit about unknowns rather than guessing. For “extremely exhaustive,” this is a strong v1 catalog with CTAN + PyPI + engine/converter tools + older utilities. I can keep extending it in passes if you want GitHub-only niche scripts next.

---

## Giant benchmark table (macro expansion + flatten/unfold)

| Category | Tool | URL | Language | Last meaningful activity / status | Commands/defs handled (verified) | Nested macro calls | Cross-file (`\input`/`\include` etc.) | Comments preserved | Conditional includes | Compiler compatibility | Known limitations / notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Macro expansion | **de-macro** | https://ctan.org/pkg/de-macro | Python | CTAN update 2021-04-10; version 1.4.1; copyright 2005–2020 | Explicitly targets private macros defined with `\(re)newcommand` and `\(re)newenvironment` | Not explicitly documented | CTAN says can use private package file; generic include traversal not clearly documented | N/A | N/A | Meant for LaTeX docs; no explicit per-engine matrix | Big limitation: scope appears centered on author/private macros, not full TeX primitive ecosystem (`\def`, `\let`, `\edef`, robust/xparse unknown). |
| Macro expansion | **LaTeXML** | https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html | Perl-based system (well-known; manual page is expansion API) | Active project (not giving exact commit date here) | Supports macro modeling via `DefMacro` and prototype syntax incl optional args | Yes (expansion engine model) | Yes in full pipeline, but this page is about expansion internals | N/A | N/A | Cross-engine compatibility is not “run under engine”; it emulates/implements TeX/LaTeX behavior for conversion | Not a simple “text in/text out demacro”; conversion-oriented; behavior depends on bindings/packages supported. |
| Macro expansion | **plasTeX** | https://plastex.github.io/plastex/ | Python | Active docs/site; maintenance ongoing | Parses/expands LaTeX macros within its DOM/conversion framework | Yes (framework-level) | Typically yes (document parser), exact command coverage depends on package support | Not a pure flattener feature | Not primary feature | Parser/converter compatibility, not literal engine compatibility | Not standalone “replace macros in source body” tool; semantic model may differ from TeX edge cases. |
| Macro expansion | **parseLatex (R package)** | https://dmurdoch.github.io/parseLatex/reference/parseLatex_fn.html | R | Docs available; package maintained in R ecosystem | `defcmd` defaults include `\newcommand`, `\renewcommand`, `\providecommand`, `\def`, `\let`; `defenv` includes `\newenvironment`, `\renewenvironment` | Parsing support yes; full textual recursive expansion behavior must be implemented by user | Not primarily an include expander | N/A | N/A | Parser-level; not engine-specific compiler tool | It is a parser toolkit, not turnkey “fully expanded .tex output” binary. |
| Macro expansion | **TeX engine primitives (pdfTeX/XeTeX/LuaTeX via plain TeX expansion workflows)** | (engine docs; no single package URL) | C/C++ engines + TeX macro language | Actively maintained as TeX distributions | Native handles `\def`, `\edef`, `\let`, conditionals, token expansion semantics | Yes (authoritative) | Yes with full TeX file loading | N/A | Yes (full TeX conditionals) | Highest semantic fidelity across TeX-family compilers (engine-dependent primitives/extensions differ) | You said “exclude full compilers”; this is the gold-standard baseline but violates standalone-text-tool preference. Keep as oracle baseline only. |
| Flatten/unfold | **latexpand** | https://ctan.org/pkg/latexpand | Perl | Version 1.7.2 (2023-02-27), active through 2023 | Explicit: `\input`, `\include`; explicit non-support for `\includeonly` | N/A | Yes (`\input`, `\include`) | Can be configured in workflow; CTAN blurb doesn’t fully specify comment policy | No (`\includeonly` unsupported) | Engine-agnostic text preprocessor | Limitation explicitly documented: no `\includeonly`. Some edge constructs need workarounds (README mentions `--makeatletter` workaround cases). |
| Flatten/unfold | **flatten** (CTAN support/flatten) | https://ctan.org/pkg/flatten and https://ctan.org/tex-archive/support/flatten | flex/C | Legacy; README dated 1995 | Default `\input`, `\include`; README says inclusion command set is modifiable | N/A | Yes | Not clearly documented | Not clearly documented | Generic TeX text files | Old/possibly abandoned; lexer approach may miss modern macro-generated include patterns. |
| Flatten/unfold | **flatex** | https://ctan.org/pkg/flatex | C | Version 1.21 (CTAN) | `\input`, `\include`, and includes `.bbl` when BibTeX used | N/A | Yes | Not clearly documented | Not clearly documented | Engine-agnostic preprocessor | Old-style parser behavior; not documented for `\subimport`, `\import`, `\inputfrom`, etc. |
| Flatten/unfold | **texdirflatten** | https://ctan.org/pkg/texdirflatten and https://ctan.org/tex-archive/support/texdirflatten | Perl | v1.3; copyright 2003–2017 | `--onetex` mode expands `\input` and `\include` in place; also bundles project assets | N/A | Yes (`\input`,`\include`) | Not clearly documented | Not clearly documented | Engine-agnostic tooling | Hybrid tool (bundle + optional flatten), so “single flat file” is optional mode. |
| Flatten/unfold | **flachtex** | https://pypi.org/project/flachtex/ | Python | PyPI project available (check release history for exact cadence) | Explicitly supports `\include`, `\input`, `\subimport`, `\subimport*`; manual explicit-import directive for hard cases | N/A | Yes, including subimport family | Has option to remove comments (implies preservation configurable) | Complex/evaluated include logic may not be auto-resolved | Engine-agnostic parser tool | Strong modern include coverage; limitation: dynamic/evaluated logic needs manual hints. |
| Flatten/unfold | **texstrip** | https://pypi.org/project/texstrip/ | Python | Latest PyPI release shown 2020 | Uses `latexpand` in its workflow | N/A | Indirect via latexpand | Not clearly documented | Inherits latexpand limits | Engine-agnostic preprocessor chain | Depends on latexpand; feature ceiling largely tied to latexpand support. |
| Flatten/unfold (related include command ecosystem) | **import package** (LaTeX package defining include-like commands) | https://ctan.org/tex-archive/macros/latex/contrib/import | TeX/LaTeX package | CTAN package available | Defines/uses commands like `\import`, `\subimport`, `\inputfrom`, etc. | N/A | N/A (this is command provider, not flattener) | N/A | N/A | Works in LaTeX package context | Important benchmark note: many flatteners do **not** fully parse these commands unless explicitly implemented. |

---

## Practical benchmark guidance (based on your constraints)

1. **Macro-expansion benchmark tiers**
   - **Tier A (true demacro tools):** de-macro.
   - **Tier B (conversion engines with expansion):** LaTeXML, plasTeX.
   - **Tier C (parser toolkits you can build expansion on):** parseLatex.
   - **Tier D (oracle baseline):** native TeX engine expansion (excluded from “tool” list but critical for correctness comparison).

2. **Critical limitation flags to encode**
   - “Expands only user/private macros vs package/CTAN macros”
   - “Understands primitives (`\def`, `\edef`, `\let`) or not”
   - “Understands modern interfaces (`\DeclareRobustCommand`, `\NewDocumentCommand`)”
   - “Executes TeX conditionals / catcode effects vs static parse”

3. **Flatten benchmark flags**
   - Explicit command set coverage: `\input`, `\include`, `\includeonly`, `\import`, `\subimport`, `\inputfrom`
   - Dynamic include resolution (macro-generated paths, conditionals)
   - Comment and whitespace fidelity
   - Asset handling (`.bbl`, images, bib files, style files)

---

## Sources
- https://ctan.org/pkg/de-macro  
- https://ctan.org/pkg/latexpand  
- https://ctan.org/tex-archive/support/latexpand  
- https://ctan.org/pkg/flatten  
- https://ctan.org/tex-archive/support/flatten  
- https://ctan.org/pkg/flatex  
- https://ctan.org/pkg/texdirflatten  
- https://ctan.org/tex-archive/support/texdirflatten  
- https://pypi.org/project/flachtex/  
- https://pypi.org/project/texstrip/  
- https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html  
- https://dmurdoch.github.io/parseLatex/reference/parseLatex_fn.html  
- https://ctan.org/tex-archive/macros/latex/contrib/import  