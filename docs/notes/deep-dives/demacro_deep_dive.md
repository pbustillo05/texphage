# demacro Deep Dive

> Last updated: 2026-03-25 by coverage_agent
> Authoritative per-pattern limitations live in `_regex.py`'s docstrings.
> This note is the coverage_agent's research base for demacro.

---

## 1. Current Coverage (from _regex.py and demacro.py)

The `demacro` tool's macro-finding logic is centralized in `demacro.build_dictionary`, which iterates through matches of the `_FIND_ALL_RE` regex. This regex is a union of individual patterns for different definition commands.

- **`_DEF_PATTERN`**: Handles `\def`, `\gdef`.
- **`_EDEF_PATTERN`**: Handles `\edef`, `\xdef`.
- **`_LET_PATTERN`**: Handles `\let` and `letltxmacro` variants.
- **`_NEW_COM_PATTERN`**: Handles `\newcommand` and a wide variety of related commands from `etoolbox`, `twoopt`, and `xargs`.
- **`_NEW_DOC_COM_PATTERN`**: Handles `xparse`'s `\NewDocumentCommand` and its variants.
- **`_NEW_ENV_PATTERN`**: Handles `\newenvironment`.
- **`_NEW_DOC_ENV_PATTERN`**: Handles `xparse`'s `\NewDocumentEnvironment`.
- **`_DMO_PATTERN`**: Handles `\DeclareMathOperator` from `amsmath`.
- **`_CSNAME_DEF_RE`**: A separate regex to handle the specific `\expandafter\def\csname name\endcsname{...}` idiom. It's used in a second pass within `build_dictionary`.

The `demacro_deep_dive.md` note provides a good table of coverage status. This analysis will build upon it.

---

## 2. Universe of Syntax & Test Snippets

Here we catalogue the full universe of syntax, focusing on the high-priority gaps identified in previous analyses. Each entry includes test snippets suitable for use in `tests/regex_tests/`.

### Priority: HIGH

#### `\csname ... \endcsname` Idioms

The current implementation has a special-case regex `_CSNAME_DEF_RE` for `\expandafter\def\csname...\endcsname`. This is too specific and misses many common variants. A robust solution would likely involve a pre-pass to resolve `\csname` constructions before the main `_FIND_ALL_RE` is run.

- **Package:** TeX primitive
- **Description:** Constructs a control sequence from tokens, often for names containing `@` or other special characters, or for dynamically generated names.
- **Test Snippets:**

  - **`expandafter_let.tex`**:
    ```latex
    \documentclass{article}
    \begin{document}
    \makeatletter
    \let\old@section\section
    \expandafter\let\csname texphage@replacement\endcsname\old@section
    \makeatother
    \texphage@replacement{Hello}
    \end{document}
    ```

  - **`nested_csname.tex`**:
    ```latex
    \documentclass{article}
    \begin{document}
    \def\makename#1{my#1command}
    \expandafter\def\csname\makename{test}\endcsname{Success}
    \mytestcommand
    \end{document}
    ```

  - **`expandafter_newenvironment.tex`**:
    ```latex
    \documentclass{article}
    \begin{document}
    \expandafter\newenvironment\csname mytestenv\endcsname{\center}{\endcenter}
    \begin{mytestenv}Centered\end{mytestenv}
    \end{document}
    ```

#### `xparse` Advanced Syntax (`NEW_DOC_COM_PATTERN`)

The current pattern `_NEW_DOC_COM_PATTERN` only supports `m`, `o`, `O`, `s`, `t` argument specifiers. The full `xparse` is much richer. Also, conditional logic (`\IfBooleanTF`, `\IfNoValueTF`) is not evaluated.

- **Package:** `xparse` (LaTeX3 Kernel)
- **Description:** Advanced argument parsing and conditional logic.
- **Test Snippets for Gaps:**

  - **`arg_spec_r.tex`** (delimited argument):
    ```latex
    \documentclass{article}
    \usepackage{xparse}
    \begin{document}
    \NewDocumentCommand{\interval}{r()}{Interval from #1}
    \interval(1,5)
    \end{document}
    ```

  - **`arg_spec_R.tex`** (delimited argument with default):
    ```latex
    \documentclass{article}
    \usepackage{xparse}
    \begin{document}
    \NewDocumentCommand{\interval}{R(){-1,1}}{Interval from #1}
    \interval() \quad \interval(0,1)
    \end{document}
    ```
  - **`arg_spec_v.tex`** (verbatim argument):
    ```latex
    \documentclass{article}
    \usepackage{xparse}
    \begin{document}
    \NewDocumentCommand{\verbprint}{v}{\texttt{#1}}
    \verbprint|\foo^{bar}|
    \end{document}
    ```

  - **`conditional_IfNoValueTF.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{xparse}
    \begin{document}
    \NewDocumentCommand{\mycmd}{o}{\IfNoValueTF{#1}{No Value}{Got #1}}
    \mycmd \quad \mycmd[Value]
    \end{document}
    ```

  - **`conditional_IfBooleanTF.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{xparse}
    \begin{document}
    \NewDocumentCommand{\mycmd}{s}{\IfBooleanTF{#1}{Starred}{Unstarred}}
    \mycmd \quad \mycmd*
    \end{document}
    ```


#### `pgfkeys` (`\tikzset`, `\pgfkeys`)

This is a major system for defining configuration options and styles, primarily used by TikZ but also by other packages. It's effectively a key-value database with its own macro-like "style" definitions. This is a total gap.

- **Package:** `pgf`
- **Description:** Key-value system for defining styles and options.
- **Test Snippets:**

  - **`tikzset_basic_style.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{tikz}
    \begin{document}
    \tikzset{my style/.style={draw=blue, thick}}
    \begin{tikzpicture}\node[my style] {Hi}; \end{tikzpicture}
    \end{document}
    ```

  - **`tikzset_style_with_args.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{tikz}
    \begin{document}
    \tikzset{mystyle/.style args={#1 and #2}{label=#1, fill=#2}}
    \begin{tikzpicture}\node[mystyle=left and yellow] {Hi}; \end{tikzpicture}
    \end{document}
    ```

  - **`pgfkeys_handler.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{pgf}
    \begin{document}
    \pgfkeys{/handlers/.myhandler/.code={You said #1}}
    \pgfkeys{/my key/.myhandler=World}
    \end{document}
    ```

  - **`pgfkeys_style_multiple.tex`**
    ```latex
    \documentclass{article}
    \usepackage{pgf}
    \begin{document}
    \pgfkeys{
      /my styles/.cd,
      style a/.style = {font=\Large},
      style b/.style = {font=\small},
    }
    \pgfkeys{/my styles/style a} Large text.
    \end{document}
    ```

### Priority: MEDIUM

#### `environ` and `newenviron` packages

Regexes `_NEW_ENVIRON_PATTERN` and `_NEW_ENVIRON_PKG_PATTERN` exist in `_regex.py` but are not included in the main `_FIND_ALL_RE` union, and the logic to substitute `\BODY` or `\envbody` is missing from `build_dictionary`.

- **Package:** `environ`, `newenviron`
- **Description:** Alternative ways to define environments, capturing the body content for manipulation.
- **Test Snippets:**

  - **`environ_BODY.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{environ}
    \begin{document}
    \NewEnviron{mybox}{\fbox{\BODY}}
    \begin{mybox}
      Here is the content.
    \end{mybox}
    \end{document}
    ```

  - **`newenviron_envbody.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{newenviron}
    \begin{document}
    \newenviron{myquote}{\quote\itshape}{\endquote}
    \begin{myquote}
      Some quote.
    \end{myquote}
    \end{document}
    ```

#### `etoolbox` patching commands

- **Package:** `etoolbox`
- **Description:** Dynamically modify existing macros. This is very hard to model statically.
- **Priority:** MEDIUM (high impact, but very high complexity)
- **Test Snippet:**
  - **`patchcmd.tex`**:
    ```latex
    \documentclass{article}
    \usepackage{etoolbox}
    \begin{document}
    \def\original{abc}
    \patchcmd{\original}{b}{X}{}{\errmessage{failed}}
    \original % Should produce aXc
    \end{document}
    ```

---

## 3. Summary & Recommendations

The gap analysis from the previous note holds. The highest-ROI items are:

1.  **`\csname`/`\expandafter`**: Fundamental to how LaTeX works internally. Current support is too specific. A pre-pass to resolve these before the main regex matching seems most robust.
2.  **`xparse` advanced features**: `\NewDocumentCommand` is the modern standard. Our partial support is a significant weakness. Expanding `_XPARSE_PATTERN` and adding logic to `content_replacement` to handle conditionals is necessary.
3.  **`pgfkeys`/`\tikzset`**: Ubiquitous in papers with diagrams. This is a total blind spot. A dedicated `PGFKEYS_PATTERN` and a new branch in `build_dictionary` are needed.

The test snippets provided above should be used to create test assets in `tests/regex_tests/` to guide and validate implementation of these features.
