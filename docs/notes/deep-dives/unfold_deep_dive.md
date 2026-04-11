# unfold Deep Dive

> Last updated: 2026-03-25 by coverage_agent
> Authoritative per-directive limitations live in `unfold.py`'s `_FIND_INPUT` docstring.
> This note is the coverage_agent's research base for unfold.

---

## 1. Current Coverage (from unfold.py)

The `unfold` tool uses a single, comprehensive regex `_FIND_INPUT` defined locally within `unfold.py`. It does **not** use patterns from the shared `_regex.py` module.

The `_FIND_INPUT` pattern is an alternation of named branches, one for each supported inclusion directive. The existing deep-dive note's table of coverage is accurate and complete.

| Directive(s) | Package | Branch in _FIND_INPUT | Status |
|---|---|---|---|
| `\input{path}` | TeX primitive | `input` | COVERED |
| `\input path` | TeX primitive | `input_bare` | COVERED |
| `\include{path}` | LaTeX2e | `include` | COVERED |
| `\usepackage{pkg}` | LaTeX2e | `usepkg` | PARTIAL — local `.sty` only, opt-in flag |
| `\import{dir}{file}` | `import` | `import_` | COVERED |
| `\subimport{dir}{file}` | `import` | `subimport` | COVERED |
| `\inputfrom{dir}{file}` | `import` | `inputfrom` | COVERED |
| `\subinputfrom{dir}{file}` | `import` | `subinputfrom` | COVERED |
| `\subfile{path}` | `subfiles` | `subfile` | COVERED |
| `\subfileinclude{path}` | `subfiles` | `subfile` | COVERED |
| `\InputIfFileExists{f}{t}{e}` | LaTeX2e kernel | `inputiffileexists` | COVERED |

---

## 2. Universe of Syntax & Test Snippets

The previous analysis was correct; coverage is very good. The primary gap is the `\include` variants from the `import` package.

### Priority: MEDIUM

#### `\includefrom` and `\subincludefrom`

- **Package:** `import` · [import.pdf §2](https://ctan.org/pkg/import)
- **Description:** These are variants of `\import` and `\subimport` that behave like `\include` (i.e., they wrap the imported content in `\clearpage`). `\includefrom{dir}{file}` is the `\include` version of `\import`, and `\subincludefrom{dir}{file}` is the `\include` version of `\subimport`.
- **Gap:** The `_FIND_INPUT` regex in `unfold.py` lacks branches for these two commands.
- **Test Snippets:** These snippets require a file structure to test resolution. The test runner would need to create `sections/chapter1.tex`.

  - **`includefrom.tex`** (main file):
    ```latex
    \documentclass{article}
    \usepackage{import}
    \begin{document}
    This is the main file.
    \includefrom{sections/}{chapter1.tex}
    End of main file.
    \end{document}
    ```
    - **`sections/chapter1.tex`** (included file):
      ```latex
      This is chapter 1.
      ```

  - **`subincludefrom.tex`** (main file):
    ```latex
    \documentclass{article}
    \usepackage{import}
    \begin{document}
    This is the main file.
    \subincludefrom{sections/}{chapter1.tex}
    End of main file.
    \end{document}
    ```
    - **`sections/chapter1.tex`** (included file):
      ```latex
      This is chapter 1.
      ```

### Priority: LOW

#### `\loadglsentries`

- **Package:** `glossaries` · [glossaries.pdf](https://ctan.org/pkg/glossaries)
- **Description:** `\loadglsentries[<type>]{<filename>}` loads glossary definitions. For unfolding purposes, it can be treated identically to `\input`.
- **Gap:** No branch in `_FIND_INPUT`.
- **Test Snippet:**

  - **`loadglsentries.tex`** (main file):
    ```latex
    \documentclass{article}
    \usepackage{glossaries}
    \begin{document}
    \loadglsentries{myglossary.tex}
    A test.
    \end{document}
    ```
    - **`myglossary.tex`** (included file):
      ```latex
      \newglossaryentry{test}{name=test,description={a test}}
      ```

---

## 3. Summary & Recommendations

### Gap analysis

Coverage is nearly complete. The only remaining gaps are:
1.  **`\includefrom`/`\subincludefrom`**: Completes `import` package support. Low complexity to add.
2.  **`\loadglsentries`**: Simple to add, but low impact on final document text.

### Prioritised implementation order

| Priority | Item | Complexity |
|---|---|---|
| MEDIUM | `\includefrom` / `\subincludefrom` | Low — add two branches to `_FIND_INPUT` regex, copy logic from `import_`/`subimport` handlers. |
| LOW | `\loadglsentries` | Very Low — add branch to regex, treat as alias for `input`.|

### Out of scope — intentional non-coverage

The out-of-scope list from the previous analysis remains correct. These directives should **not** be unfolded.

- **Category: Verbatim / listing inclusion**
  - `\verbatiminput`, `\VerbatimInput` (`verbatim` package)
  - `\lstinputlisting` (`listings` package)
  - `\inputminted` (`minted` package)

- **Category: Asset references (not LaTeX source)**
  - `\includegraphics`
  - `\bibliography` (BibTeX)
  - `\addbibresource` (BibLaTeX)
  - `\includepdf` (`pdfpages` package)

- **Category: Package / class loading**
  - `\documentclass`
  - `\RequirePackage`
  - `\LoadClass`
