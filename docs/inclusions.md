# inclusions.md — LaTeX File Inclusion: Implementation Reference

> Authoritative limitations for each implemented form live in the
> MATCHES/CAPTURES/LIMITATIONS comment in `src/texphage/unfold.py`.
> This file covers (1) what is implemented and (2) what is not, in priority order.

---

## Part 1: Implemented

| Directive(s) | Package | Branch in _FIND_INPUT | Status |
|---|---|---|---|
| `\input{path}` | TeX primitive | `input` | COVERED — see `unfold.py` |
| `\input path` | TeX primitive | `input_bare` | COVERED — see `unfold.py` |
| `\include{path}` | LaTeX2e | `include` | COVERED — see `unfold.py` |
| `\usepackage{pkg}` | LaTeX2e | `usepkg` | PARTIAL — local `.sty` only, opt-in flag required. See `unfold.py`. |
| `\import{dir}{file}` | `import` | `import_` | COVERED — see `unfold.py` |
| `\subimport{dir}{file}`| `import` | `subimport` | COVERED — see `unfold.py` |
| `\inputfrom{dir}{file}`| `import` | `inputfrom` | COVERED — see `unfold.py` |
| `\subinputfrom{dir}{file}`| `import` | `subinputfrom` | COVERED — see `unfold.py` |
| `\subfile{path}` | `subfiles` | `subfile` | COVERED — see `unfold.py` |
| `\subfileinclude{path}`| `subfiles` | `subfile` | COVERED — see `unfold.py` |
| `\InputIfFileExists{f}{t}{e}` | LaTeX2e kernel | `inputiffileexists` | COVERED — see `unfold.py` |

---

## Part 2: Not yet implemented — ordered by arXiv ROI

### MEDIUM Priority

#### `\includefrom` and `\subincludefrom`

**Package:** `import` · [import.pdf §2](https://ctan.org/pkg/import)
**Priority:** MEDIUM
**Status:** NOT COVERED

**Full syntax:**
`\includefrom{<dir>}{<file>}`
`\subincludefrom{<dir>}{<file>}`

**Semantics:** These are variants of `\import` and `\subimport` that behave like `\include` (i.e., they wrap the included content in `\clearpage`).
- `\includefrom`: sets the search path to `<dir>` for the duration of the inclusion. It is an `\include` version of `\import`.
- `\subincludefrom`: is the `\include` version of `\subimport`.

**arXiv note:** Less common than `\import` and `\subimport`, but their absence represents an incomplete implementation of the `import` package, which is frequently used in multi-file projects.

**Architectural note:** The logic would be a near-copy of the existing `import_` and `subimport` handlers, but wrapping the unfolded content in `\clearpage\n...\n\clearpage`, just as the `include` handler does for `\input`.

---

### LOW Priority

#### `\loadglsentries`

**Package:** `glossaries` · [glossaries.pdf](https://ctan.org/pkg/glossaries)
**Priority:** LOW
**Status:** NOT COVERED

**Full syntax:**
`\loadglsentries[<type>]{<filename>}`

**Semantics:** Loads glossary definitions from `<filename>`. The file typically contains `
ewglossaryentry` commands, but can contain arbitrary LaTeX. For the purpose of unfolding, it can be treated like `\input`.

**arXiv note:** The `glossaries` package is common, but this command is used for populating definitions, not including primary document content. The impact on understanding the main text of a paper is likely minimal.

---

## Part 3: Intentionally Out of Scope

This section lists directives that look like file inclusion but should NOT be unfolded into the main document body for NLP purposes.

### Category B — Verbatim / listing inclusion (never unfold)

These commands insert file content as literal, non-interpreted text (e.g., for code listings). Expanding them would pollute the semantic content of the document with source code that is not part of the paper's narrative.

- `\verbatiminput` (`verbatim` package)
- `\VerbatimInput` (`verbatim` package)
- `\lstinputlisting` (`listings` package)
- `\inputminted` (`minted` package)

### Category C — Asset references (not LaTeX source)

These commands reference external files that are not LaTeX source (e.g., images, bibliographies, PDFs). They are essential for compilation but are not part of the unfoldable text content.

- `\includegraphics`
- `\bibliography` (BibTeX)
- `\addbibresource` (BibLaTeX)
- `\includepdf` (`pdfpages` package)

### Category D — Package / class loading (potential future scope)

These load foundational `.sty` and `.cls` files. While `\usepackage` is partially handled for *local* packages, full handling of system packages is complex and stateful. These are generally considered out of scope for simple unfolding.

- `\documentclass`
- `\RequirePackage`
- `\LoadClass`
- `\ProvidesPackage`
