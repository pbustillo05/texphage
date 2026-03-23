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
| `\subfile{path}` | `subfiles` | `subfile` | COVERED — see `unfold.py` |
| `\subfileinclude{path}`| `subfiles` | `subfile` | COVERED — see `unfold.py` |

---

## Part 2: Not yet implemented — ordered by arXiv ROI

### HIGH Priority

#### `\InputIfFileExists`

**Package:** LaTeX2e kernel · [source2e §Input](https://ctan.org/pkg/source2e)
**Priority:** HIGH
**Status:** NOT COVERED

**Full syntax:**
`\InputIfFileExists{<filename>}{<true-code>}{<false-code>}`

**Semantics:** Tests whether `<filename>` exists on the TeX search path. If it does, TeX inputs it and then runs `<true-code>`; otherwise it runs `<false-code>`. The file content, if loaded, becomes part of the document body.

**arXiv note:** Used internally by many packages to load optional configuration or compatibility files. Authors rarely write it directly, but it appears in project-level `.sty` files that are unfolded when `inline_local_packages=True`. Its absence is a significant correctness gap for such projects.

**Architectural note:** Requires two-branch logic (file found / not found). The regex needs to capture all three arguments. The replacement function should attempt to resolve and open the file: on success, it should return the unfolded file content followed by the `<true-code>`; on `FileNotFoundError`, it should return only the `<false-code>`. Both `<true-code>` and `<false-code>` may contain further inclusion commands and must be recursively processed.

---

### MEDIUM Priority

#### `\inputfrom` and `\subinputfrom`

**Package:** `import` · [import.pdf §2](https://ctan.org/pkg/import)
**Priority:** MEDIUM
**Status:** NOT COVERED

**Full syntax:**
`\inputfrom{<dir>}{<file>}`
`\subinputfrom{<dir>}{<file>}`

**Semantics:** These are variants of `\import` and `\subimport` that behave like `\input` (i.e., no `\clearpage` wrapper like `\include`).
- `\inputfrom`: sets the search path to `<dir>` for the duration of the input.
- `\subinputfrom`: is the same as `\subimport`. The `import` package documentation itself says `\subinputfrom` is just an alias for `\subimport`.

**arXiv note:** Less common than `\import` and `\subimport`, which are already implemented. Supporting these would complete coverage for the `import` package.

**Architectural note:** The logic for `\subinputfrom` can be aliased directly to the existing `subimport` handler. The logic for `\inputfrom` is nearly identical to the existing `import_` handler. This is a low-effort, high-consistency addition.

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
