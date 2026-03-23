# macros.md — LaTeX Macro Definition: Implementation Reference

> Authoritative limitations for each implemented pattern live in the
> MATCHES/CAPTURES/LIMITATIONS comments in `src/texphage/demacro.py`.
> This file covers (1) what is implemented and (2) what is not, in priority order.

---

## Part 1: Implemented

| Command(s) | Package(s) | Pattern in demacro.py | Status |
|---|---|---|---|
| `\def`, `\gdef` | TeX primitive | `find_def` | COVERED |
| `\edef`, `\xdef` | TeX primitive | `find_edef` | COVERED |
| `\let`, `\LetLtxMacro`, `\GlobalLetLtxMacro` | TeX / letltxmacro | `find_let` | COVERED |
| `\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareRobustCommand` | LaTeX2e | `find_new_com` | PARTIAL — see demacro.py for limitations on `*` form and `xargs` key-value syntax |
| `\newrobustcmd`, `\renewrobustcmd`, `\providerobustcmd` | etoolbox | `find_new_com` | PARTIAL — see `\newcommand` |
| `\newcommandtwoopt`, `\renewcommandtwoopt` | twoopt | `find_new_com` | PARTIAL — see `\newcommand` |
| `\newcommandx`, `\renewcommandx`, `\providecommandx`, `\DeclareRobustCommandx` | xargs | `find_new_com` | PARTIAL — `x` suffix is matched, but key-value optional arguments like `[1=default]` are not supported. |
| `\newenvironment`, `\renewenvironment`, `\newenvironmentx`, `\renewenvironmentx` | LaTeX2e / xargs | `find_new_env` | PARTIAL — `xargs` key-value syntax is not supported. |
| `\NewDocumentCommand`, `\RenewDocumentCommand`, `\ProvideDocumentCommand`, `\DeclareDocumentCommand` | xparse | `find_new_doc_com` | PARTIAL — Only `m, o, O, s, t` arg-specifiers are supported. Conditionals (`\IfBooleanTF` etc.) are not evaluated. |
| `\NewExpandableDocumentCommand` and variants | xparse | `find_new_doc_com` | PARTIAL — Same limitations as `\NewDocumentCommand`. |
| `\NewDocumentEnvironment`, `\RenewDocumentEnvironment`, `\ProvideDocumentEnvironment`, `\DeclareDocumentEnvironment` | xparse | `find_new_doc_env` | PARTIAL — Same argument specifier and conditional limitations as `\NewDocumentCommand`. |
| `\DeclareMathOperator`, `\DeclareMathOperator*` | amsmath | `find_dmo` | COVERED |
| `\NewEnviron`, `\RenewEnviron` | environ | `find_New_Environ` | PARTIAL — The regex exists but is not used in the main parser (`find_all`). If it were, `\BODY` substitution is not implemented. See `demacro.py`. |
| `\newenviron`, `\renewenviron` | newenviron | `find_new_environ` | PARTIAL — The regex exists but is not used in the main parser (`find_all`). If it were, `\envbody` substitution is not implemented. See `demacro.py`. |

---

## Part 2: Not yet implemented — ordered by arXiv ROI

### HIGH Priority

#### `\csname ... \endcsname` and `\expandafter`
**Package:** TeX primitive
**Priority:** HIGH
**Status:** NOT COVERED

**Semantics:** `\csname` constructs a control sequence name from tokens, and is almost always preceded by `\expandafter` to ensure the name is formed before another command (like `\def` or `\let`) tries to use it. This is fundamental for dynamic macro creation.
**Example:** `\expandafter\def\csname my@command\endcsname{...}` defines `\my@command`.
**Architectural Note:** Handling this requires a pre-parsing step or a modification to the main regex loop to resolve `\csname ... \endcsname` into a literal command token before pattern matching.

#### `xparse` advanced argument specifiers and conditionals
**Package:** xparse (LaTeX kernel)
**Priority:** HIGH
**Status:** NOT COVERED

**Full syntax:** `r<tok1><tok2>`, `R`, `v`, `b`, `e`, `E`, `+m`, `+o`, etc.
**Semantics:** These specifiers allow for delimited arguments, verbatim arguments, and other complex parsing behaviors that are common in modern packages. Furthermore, conditional commands like `\IfNoValueTF{...}{...}` or `\IfBooleanTF{...}{...}` inside macro bodies are not evaluated, leading to incorrect expansions.
**Architectural Note:** Supporting more arg-specifiers requires extending the `xparse` regex in `_regex.py` and adding corresponding logic in `build_dictionary`. Supporting conditionals requires a recursive expansion model that can evaluate these branching commands.

#### `pgfkeys` (`\tikzset`, etc.)
**Package:** `pgf`
**Priority:** HIGH
**Status:** NOT COVERED

**Full syntax:** `\pgfkeys{/path/.style={...}}`, `\tikzset{key=value, ...}`
**Semantics:** Defines styles and settings for PGF/TikZ graphics by manipulating a key-value tree. These are effectively macro definitions scoped to the PGF system.
**arXiv Note:** TikZ is extremely common for figures in math and physics papers. Not expanding `\tikzset` definitions means custom drawing commands and styles are missed.
**Architectural Note:** Requires a dedicated parser for the `pgfkeys` syntax, which is substantially different from standard macro definitions. It would likely need its own `find_tikzset` pattern and a new branch in `build_dictionary` that populates a separate dictionary for TikZ styles.

### MEDIUM Priority

#### `environ` and `newenviron` body-capturing environments
**Package:** `environ`, `newenviron`
**Priority:** MEDIUM
**Status:** PARTIAL

**Semantics:** `\NewEnviron` captures its content into `\BODY`; `\newenviron` captures it into `\envbody`. The current implementation has regexes for these but does not use them, and the logic to substitute `\BODY` or `\envbody` during expansion is missing.
**Architectural Note:** The `find_New_Environ` and `find_new_environ` patterns need to be added to the `find_all` union. The `build_dictionary` logic for environments needs to be adapted to handle this; it would involve a regex substitution for `\BODY` inside the captured content *after* the main arguments are processed.

#### `etoolbox` patching commands
**Package:** `etoolbox`
**Priority:** MEDIUM
**Status:** NOT COVERED

**Full syntax:** `\patchcmd{<cmd>}{<search>}{<replace>}{<success>}{<failure>}`
**Also:** `\pretocmd`, `\apptocmd`
**Semantics:** These commands dynamically modify the replacement text of existing macros. This is a form of run-time re-definition.
**Architectural Note:** This is very difficult to model statically. It would require storing all macro bodies as strings and performing regex replacements on them when a `\patchcmd` is found. This could have significant performance implications and complex interactions.

### LOW Priority
*   **`\futurelet`**: Complex lookahead mechanism. (TeX primitive)
*   **`\mathpalette`**: For math-style-sensitive macros.
*   **`\makeatletter` / `\makeatother`**: Catcode changes. While common, they are often handled by packages already, and the core issue is parsing names with `@`.
*   **Register/font/char definitions**: `\chardef`, `\newfont`, `\newcounter`, etc. These do not define text-replacement macros in the same way `\def` does.
*   **`namedef`**: Defines macros with named parameters.
*   **`suffix`**: Defines command variants with suffixes.

---

## Part 3: Out of Scope
The following mechanisms are considered too complex, rare, or state-dependent to be reliably handled by a regex-based static analysis tool.

*   **Active Characters**: Defining single characters to act as macros (e.g., `\catcode'\_=13 \def_{\textunderscore}`). This requires tracking catcodes globally. The `~` active character is an exception often handled by default.
*   **`\every...` token registers**: e.g., `\everypar`, `\everymath`. These are global state changes that are difficult to attribute to a single definition.
*   **`\globaldefs`**: Global override for definition scope.
*   **`xtemplate`**: The full LaTeX3 object-oriented templating system.
*   **`\aftergroup`, `\afterassignment`**: TeX primitives that rely on deep parser state.