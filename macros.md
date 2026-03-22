# The Ultimate Hierarchy of Macro Definition Mechanisms in TeX & LaTeX

This is an exhaustive reference list for developers, compiled specifically for the architecture of a "demacro" expansion tool. To parse LaTeX reliably, one must handle a vast spectrum of command instantiation methods, ranging from deep TeX primitives to high-level package interfaces. 

> **Documentation Note:** For verification of low-level primitives, refer to [*The TeXbook*](https://ctan.org/pkg/texbook) by Donald Knuth or [*TeX by Topic*](https://ctan.org/pkg/texbytopic) by Victor Eijkhout. For package-specific macros, refer to their respective [CTAN](https://ctan.org/) documentation.

---

## LEVEL 1: Plain TeX Primitives (The Engine Room)
These are the fundamental, low-level ways to create control sequences directly within the TeX compiler.

### Core Definitions
* **`\def`**: Defines a macro. Replacement text is not expanded until the macro is used.
* **`\edef`**: Expanded definition. Replacement text is fully expanded at definition time.
* **`\gdef`**: Equivalent to `\global\def`. Persists outside the current local group.
* **`\xdef`**: Equivalent to `\global\edef`.

### Prefixes for Definitions
* **`\long`**: Allows macro arguments to contain paragraph breaks (`\par` tokens). *Demacro Note: Can generally be ignored during string expansion.*
* **`\outer`**: Forbids the macro from being used inside another definition or incomplete conditional. *Demacro Note: Should never be used when writing macros, but if encountered during parsing, it can be safely ignored as it doesn't change the expansion meaning.*
* **`\global`**: Makes the definition global. *Demacro Note: Usually safe to ignore for simple substitution.*
* **`\protected`**: (From e-TeX) Prevents expansion in expansion-only contexts (like `\edef` or `\write`).
* **`\expandafter`**: Forces the expansion of the second token before the first. *Demacro Note: **DANGER.** This drastically alters parsing order and is notoriously difficult to model. The only safe and necessary pattern to explicitly support is building command names via `\expandafter\def\csname ... \endcsname`.*

### Aliasing and Lookahead
* **`\let`**: Creates a direct alias. `\let\foo=\bar` makes `\foo` have the exact same meaning as `\bar` at that instant. Also used to alias a command to a single character token.
* **`\futurelet`**: A lookahead mechanism. `\futurelet\nexttoken\foo\bar` executes `\foo`, but inside `\foo`'s definition, `\nexttoken` is `\let` to `\bar`. *Demacro Note: Looks crazy. Highly complex to implement properly; proceed with extreme caution.*

### Registers, Fonts, and Character Defs
* **`\chardef`, `\mathchardef`**: Defines a command as a number representing a character code.
* **`\letcharcode`, `\charsubdef`, `\charsubdefmax`**: Binds behaviors to specific character codes (highly relevant in XeTeX or specialized input encodings).
* **`\newfont`**: Plain TeX/early LaTeX method to load and alias a font.
* **`\countdef`, `\dimendef`, `\skipdef`, `\muskipdef`, `\toksdef`**: Aliases a command name to a specific register number.
* **`\globaldefs`**: A parameter that forces all assignments to be global if non-zero. *Demacro Note: Crazy edge case. Safe to ignore unless parsing highly defensive TeX code.*

---

## LEVEL 2: Standard LaTeX2e Helpers (The User-Friendly Layer)
These wrappers around TeX primitives provide error checking and a simpler interface.

### Commands and Environments
* **`\newcommand`, `\renewcommand`, `\providecommand`**: Define, redefine, or conditionally define a macro. Supports one optional argument.
* **`\newenvironment`, `\renewenvironment`**: Counterparts for defining environments (essentially automating `\name` and `\endname`).
* **`\DeclareRobustCommand`**: Defines a command protected from premature expansion in "moving arguments."
* **`\DeclareMathOperator`**: (From `amsmath` - [Source](https://ctan.org/tex-archive/macros/latex/required/amsmath)) Specialized for custom math operators; handles spacing strictly.

### Counters, Lengths, and Boxes
* **`\newcounter`**, **`\newlength`**, **`\newsavebox`**: LaTeX's user-friendly abstractions for creating TeX registers.

---

## LEVEL 3: LaTeX3 / xparse (The Modern Standard)
The `xparse` architecture (now natively integrated into the LaTeX kernel) is the modern standard. [Source](https://github.com/latex3/latex2e/tree/develop/base)

### Document Commands
* **`\NewDocumentCommand`, `\RenewDocumentCommand`, `\ProvideDocumentCommand`, `\DeclareDocumentCommand`**: Support rich argument specifications (`m` for mandatory, `o` for optional, `s` for star, `O{default}`).
* **`\NewExpandableDocumentCommand`, `\RenewExpandableDocumentCommand`, `\ProvideExpandableDocumentCommand`, `\DeclareExpandableDocumentCommand`**: Variants that work purely via expansion. *Demacro Note: Must be supported.*

### Environments
* **`\NewDocumentEnvironment`, `\RenewDocumentEnvironment`, `\ProvideDocumentEnvironment`, `\DeclareDocumentEnvironment`**.

### Conditionals and Parsing Utilities
* **`\IfNoValue(TF)`, `\IfValue(TF)`, `\IfBoolean(TF)`**: Used inside `xparse` definitions to branch logic. *Demacro Note: Requires robust conditional statement evaluation implementation.*
* **`xtemplate`**: The LaTeX3 template system for object-oriented-like macro definitions.

---

## LEVEL 4: Key-Value Packages
Macros where the logic is defined by a key-parsing function. 
* **`pgfkeys`** ([Source](https://github.com/pgf-tikz/pgf)): Used heavily by TikZ/PGF (`\tikzset{key=value}`). Extremely powerful. *Demacro Note: Needs dedicated support implementation.*
* **`l3keys(2e)`** ([Source](https://github.com/latex3/latex3/tree/main/l3kernel)): The LaTeX3 key-value system.
* **Other key-val engines**: `expkv` ([Source](https://ctan.org/tex-archive/macros/generic/expkv)), `keyval` & `xkeyval` ([Source](https://ctan.org/tex-archive/macros/latex/contrib/xkeyval)), `ltxkeys`, `kvsetkeys` (used by `keycommand`), `kvdefinekeys`, `options`, `simplekv`, `yax`, `kvoptions`.

---

## LEVEL 5: Specialized Definition Packages
Packages that extend core definition capabilities.

### Advanced Arguments
* **`xargs`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/xargs)): `\newcommandx`, `\renewcommandx`, `\newenvironmentx`, `\renewenvironmentx`, `\providecommandx`, `\DeclareRobustCommandx`. Uses a key list instead of default values for multiple optional arguments.
* **`twoopt`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/twoopt)): `\newcommandtwoopt`, `\renewcommandtwoopt`, `\providecommandtwoopt`. Explicitly provides support for exactly 2 optional arguments.
* **`letltxmacro`** ([Source](https://github.com/ho-tex/letltxmacro)): `\LetLtxMacro`. A robust version of `\let` that properly handles macros with optional arguments.
* **`namedef`** ([Source](https://github.com/PhelypeOleinik/namedef)): `\named\def`. Allows defining macros with semantic named parameters (e.g., `#[arg]`) instead of numerical `#1`.

### Hooks and Patching
* **`etoolbox`** ([Source](https://github.com/josephwright/etoolbox)): `\newrobustcmd(*)`, `\renewrobustcmd(*)`, `\providerobustcmd(*)`. Also handles command manipulation (`\patchcmd`, `\apptocmd`, `\pretocmd`). *Note: Supersedes the obsolete `ifthen` package.*
* **`cmdhook` / `lthooks`** ([Source](https://github.com/latex3/latex2e/tree/develop/base)): Allows hooking code before/after commands (e.g., `\AddToHook`). 

### Environment Capturing
* **`environ`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/environ)): `\NewEnviron{<name>}`. Captures the entire body of the environment into a macro called `\BODY` (or `\environbodyname`). Also supports `\environfinalcode`.
* **`newenviron`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/newenviron)): `\newenviron`. Very similar to `environ`, but stores the body in `\envbody` or `\<envname>body`.

### Meta-Command Utilities
* **`suffix`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/bigfoot)): `\WithSuffix`. Defines variants of a command using a suffix token. (Found within the `bigfoot` package bundle).
* **`storecmd`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/storecmd)): `\defsavecmd`, `\newsavecmd`. Saves the name of the defined command into a container while defining it.
* **`eoldef`** ([Source](https://ctan.org/tex-archive/macros/latex/contrib/carlisle)): `\eoldef`. Creates macros where the argument is delimited by the end-of-line character.

---

## LEVEL 6: Indirect & Meta-Level Definitions (The Twilight Zone)
These methods manipulate the parser itself and require state-tracking in a demacro tool.

### Dynamic Generation
* **`\csname ... \endcsname`**: Dynamically constructs a command name from tokens. *Demacro Note: Must be evaluated natively during expansion. Almost always coupled with `\expandafter`.*

### Evaluation Contexts & Conditionals
* **Grouping & Starred Contexts**: *Demacro Note: The parser must maintain state for local groups (`{...}`) and handle conditional statements properly to differentiate starred vs. unstarred environment definitions.*
* **`\mathpalette`**: Used to build math macros that scale with the surrounding math style. *Demacro Note: A viable hack is to replace the first argument with `\currentmathstyle` if the `mathstyle` package is present (Warning: this is known to break the `xy` package).*
* **`\every...` Token Registers**: `\everypar`, `\everymath`, `\everydisplay`. Tokens placed here execute automatically at state changes.

### Catcode Manipulation
* **Active Characters**: A character can be given category code 13 ("active") and then be `\def`'d like a normal macro (e.g., the tilde `~` for non-breaking spaces).
* **`\makeatletter` and `\makeatother`**: Changes the catcode of `@` to 11 (letter), allowing it in macro names. *Demacro Note: Can be handled easily by simply executing them to update the parser's state during expansion.*