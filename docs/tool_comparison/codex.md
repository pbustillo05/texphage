Here is a **broad, include-inferred/unknown** catalog you can use immediately for benchmarking.

I’ll label each claim as:
- **C** = confirmed from docs/source pages
- **I** = inferred (likely, based on tool purpose/implementation style)
- **U** = unknown/not documented clearly

---

## Category 1 — LaTeX macro expansion tools (standalone, not full compilers)

## 1) expand-latex-macros
- **URL:** https://pypi.org/project/expand-latex-macros/
- **Language:** Python
- **Maintenance:** active (PyPI release 2.0.0 on 2025-04-24) **(C)**
- **Definition support:**
  - `\newcommand` basic: **C**
  - `\newcommand` optional arg: **I**
  - `\def`: **U**
  - `\edef`: **U**
  - `\let`: **U**
  - `\newenvironment`: **U**
  - `\DeclareRobustCommand`: **U**
  - `\NewDocumentCommand` (xparse): **U**
- **Nested macro calls:** **I**
- **Cross-file expansion (`\input`/`\include`):** **U**
- **Known limitations:** exact grammar coverage not fully documented publicly; likely source-level, non-TeX-engine semantics.

---

## 2) plasTeX (as preprocessing/macro-expansion-capable parser pipeline)
- **URL:** https://github.com/plastex/plastex
- **Language:** Python
- **Maintenance:** active project historically, check current commit for benchmark timestamp **(I/C depending on your scrape)**
- **Definition support:** parses LaTeX macros extensively; explicit replacement-to-plain-tex output as a standalone “expander” is not its primary mode.
  - `\newcommand`: **I**
  - `\def`: **I**
  - `\let`: **U**
  - `\newenvironment`: **I**
  - xparse robust declarations: **U**
- **Nested macro calls:** **I**
- **Cross-file:** **I** (`\input` parsing is typical)
- **Known limitations:** architected as a document parser/renderer, not a pure text-rewrite expander; may require custom renderer to emit expanded source.

---

## 3) pylatexenc / latexwalker-based custom expanders
- **URL:** https://github.com/phfaist/pylatexenc
- **Language:** Python
- **Maintenance:** active historically; verify exact date in your run
- **Definition support:** library-level; depends on user implementation.
  - `\newcommand`: **I**
  - others (`\def`, `\let`, etc.): **U/I** (possible with custom logic)
- **Nested calls:** **I**
- **Cross-file:** **U**
- **Known limitations:** not an out-of-box “expand all macros in file” CLI; often requires building a tool on top.

---

## 4) LaTeXML (macro expansion exists internally; not “just a compiler”, but converter engine)
- **URL:** https://github.com/brucemiller/LaTeXML
- **Language:** Perl
- **Maintenance:** active historically
- **Definition support:** broad TeX/LaTeX macro processing internally **(I/C from project scope)**
- **Nested calls:** **C/I**
- **Cross-file:** **C/I**
- **Known limitations:** heavyweight conversion pipeline (XML/HTML focus), not a lightweight source-to-source macro expander.

---

## 5) texexpand / kpsewhich-ecosystem scripts (various small scripts on GitHub)
- **URL:** varies (multiple repos; search term: “latex macro expand script”)
- **Language:** mostly Python/Perl/Shell
- **Maintenance:** mixed, often abandoned
- **Definition support:** usually `\newcommand` only **(I)**
- **Nested calls:** **U/I**
- **Cross-file:** **U/I**
- **Known limitations:** ad-hoc regex parsers; fragile with optional args, category codes, xparse commands.

---

## 6) Generic macro-expander packages (non-LaTeX-specific; usually exclude from final benchmark)
- **Example URL:** https://pypi.org/project/macro-expander/
- **Language:** Python
- **Maintenance:** varies
- **Definition support:** not TeX macro semantics
- **Known limitations:** generally unsuitable for authentic LaTeX macro benchmark unless you include “non-TeX approximators.”

---

### Category 1 note
True standalone “expand defined macros and rewrite body” tools are relatively scarce; many serious projects are parsers/converters rather than clean source expanders.

---

## Category 2 — LaTeX flattening / unfolding tools (`\input`/`\include` resolution)

## 1) flatten (CTAN)
- **URL:** https://ctan.org/pkg/flatten
- **Language:** C (lexer/flex-based) **(C)**  
- **Maintenance:** old/original but still distributed on CTAN; check CTAN metadata date for your snapshot.
- **Inclusion commands:**
  - `\input`: **C**
  - `\include`: **C**
  - custom inclusion command set: **C** (“facilities for modifying this set” from README)
  - `\subimport`, `\inputfrom`, `\import`: **U/I** (unless configured/customized)
  - `\includeonly`: **U**
- **Preserves comments:** **U**
- **Conditional includes:** **U** (likely limited)
- **Known limitations:** lexical/text approach, not full TeX conditional execution.

Source basis: CTAN package + directory README.

---

## 2) flatex (CTAN)
- **URL:** https://ctan.org/pkg/flatex
- **Language:** C **(C)**
- **Maintenance:** legacy tool, still on CTAN
- **Inclusion commands:**
  - `\input`: **C**
  - `\include`: **C**
  - BibTeX `.bbl` inclusion: **C**
  - `\subimport` family: **U**
  - `\includeonly`: **U**
- **Preserves comments:** **U**
- **Conditional includes:** **U**
- **Known limitations:** mainly classic include/input flattening; modern import-package commands may not be handled natively.

---

## 3) latexpand (CTAN / script ecosystem)
- **URL:** https://ctan.org/pkg/latexpand
- **Language:** Perl
- **Maintenance:** used in arXiv/journal prep workflows; verify latest commit date for your sheet.
- **Inclusion commands:**
  - `\input`: **C**
  - `\include`: **C**
  - `\subimport`, `\import`, `\inputfrom`: **I/U** (tool-option/extension dependent)
  - `\includeonly`: **U**
- **Preserves comments:** **I** (often configurable)
- **Conditional includes:** **U**
- **Known limitations:** preprocessing behavior is option-dependent; not full TeX interpreter.

---

## 4) arXiv submission helper scripts (community variants of flatteners)
- **URL:** various GitHub repos (search: “arxiv latex flatten script”)
- **Language:** Python/Perl/Shell
- **Maintenance:** mixed, frequently abandoned
- **Inclusion commands:**
  - `\input`,`\include`: **I/C per repo**
  - import-package commands: **U**
- **Comments:** **U/I**
- **Conditionals:** **U**
- **Known limitations:** brittle regex; often project-specific assumptions.

---

## 5) latexmk-based custom dependency+concatenate workflows (not a single canonical tool)
- **URL:** latexmk + user scripts
- **Language:** Perl + shell
- **Maintenance:** latexmk itself active; flatten script layer custom
- **Inclusion commands:** via dependency graph possible **I**
- **Comments/conditionals:** depends on custom script
- **Known limitations:** no standard flatten behavior across setups.

---

## 6) TeX-directory collection tools (related but not true flatteners)
- **Examples:** `texdirflatten` (CTAN-related ecosystem mention)
- **Purpose:** gather files into one dir, not always inlining includes.
- **Inclusion commands/comments/conditionals:** often N/A for true unfolding.
- **Limitation:** good for packaging, not equivalent to single-file expansion.

---

## Important cross-reference for inclusion command family
The `import` package defines:
- `\import`, `\subimport`, `\inputfrom`, `\subinputfrom`, `\includefrom`, `\subincludefrom` **(C from CTAN import docs)**  
URL: https://ctan.org/pkg/import

Use these commands in your benchmark tests; many flatteners will fail or partially support them.

---

## Suggested benchmark matrix columns (so inferred/unknown is explicit)

For each tool, add columns:
- `supports_newcommand_basic`
- `supports_newcommand_optional`
- `supports_def`
- `supports_edef`
- `supports_let`
- `supports_newenvironment`
- `supports_declarerobustcommand`
- `supports_newdocumentcommand`
- `nested_expansion`
- `cross_file_expansion`
- `supports_input`
- `supports_include`
- `supports_import_family`
- `supports_includeonly`
- `preserves_comments`
- `conditional_handling`
- `status_confidence` (`confirmed` / `inferred` / `unknown`)
- `last_meaningful_activity_date`

---

## Sources used
- https://ctan.org/pkg/flatten  
- https://ctan.org/tex-archive/support/flatten  
- https://ctan.org/pkg/flatex  
- https://ctan.org/pkg/latexpand  
- https://ctan.org/pkg/import  
- https://pypi.org/project/expand-latex-macros/