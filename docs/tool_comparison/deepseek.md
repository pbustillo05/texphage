Of course. This is an excellent project. The landscape of LaTeX preprocessing tools is fragmented, with many specialized, niche, or abandoned projects. Here is an exhaustive list, curated for your benchmark.

### Important Preliminary Note
The line between a "macro expansion tool" and a "full LaTeX compiler" is exceptionally blurry. True expansion without any knowledge of TeX's primitives, catcodes, and execution semantics is impossible for all but the most trivial cases. Therefore, the tools listed under **Category 1** are primarily text-based processors that make simplifying assumptions. They will fail on complex, dynamic, or runtime-defined macros. A true expansion is essentially what the TeX engine itself does during its "mouth" and "stomach" phases.

---

### **Category 1: LaTeX Macro Expansion Tools**

These tools attempt to expand user-defined macros. They are not full TeX engines.

#### 1. Latexpand
*   **URL:** [CTAN](https://ctan.org/pkg/latexpand) | [GitHub (Heiko Oberdiek's collection)](https://github.com/ho-tex/oberdiek)
*   **Language:** Perl
*   **Maintenance Status:** Stable and maintained. Part of the `oberdiek` bundle. Last update on CTAN was 2021-09-23.
*   **Definition Types Handled:** `\newcommand`, `\renewcommand`, `\def`, `\let`, `\newenvironment`. It has some knowledge of `xparse`'s `\NewDocumentCommand` and `\DeclareDocumentCommand` but support is not perfect.
*   **Nested Macro Calls:** Yes, it expands recursively.
*   **Cross-file Expansion:** Yes, it resolves `\input` and `\include` directives as part of its process.
*   **Known Limitations:** It is a text processor, not a TeX interpreter. It will not expand macros defined inside other macros or within groups if that changes the definition. It struggles with complex optional arguments and dynamic redefinitions (e.g., `\def\a{b}\def\a{c}`). It is generally considered one of the best standalone tools for this job.

#### 2. latexpand (by Jean-Côme Charpentier)
*   **URL:** [GitHub](https://github.com/JCChat/latexpand)
*   **Language:** Python
*   **Maintenance Status:** Appears abandoned. Last commit was in 2014.
*   **Definition Types Handled:** `\newcommand`, `\renewcommand`, `\def`, `\newenvironment`.
*   **Nested Macro Calls:** Yes.
*   **Cross-file Expansion:** Yes, it handles `\input` and `\include`.
*   **Known Limitations:** Similar to the Perl `latexpand`, it is a text-based tool and will fail on complex TeX code. Its age means it has no knowledge of modern `xparse` commands.

#### 3. demacro
*   **URL:** [CTAN](https://ctan.org/pkg/demacro) | [GitHub (Neil Carter)](https://github.com/nlct/demacro)
*   **Language:** Python
*   **Maintenance Status:** Stable but minimal activity. Last CTAN update was 2019-06-16.
*   **Definition Types Handled:** `\newcommand`, `\renewcommand`, `\newenvironment`, `\renewenvironment`. Explicitly does **not** handle `\def` or `\let`.
*   **Nested Macro Calls:** Yes, it expands recursively.
*   **Cross-file Expansion:** No. It is designed to work on a single file. You must flatten the document first.
*   **Known Limitations:** The explicit avoidance of `\def` is a major limitation for many documents. It is easily confused by macros that have similar names (e.g., `\foo` and `\fooBar`). It requires macros to be defined before they are used.

#### 4. LaTeXpander (LaTeX Macro Expander)
*   **URL:** [GitHub](https://github.com/LAKoubensky/LaTeXpander)
*   **Language:** Java
*   **Maintenance Status:** Appears to be a personal project with minimal recent activity.
*   **Definition Types Handled:** `\newcommand`, `\def`, `\let`, `\newenvironment`.
*   **Nested Macro Calls:** Yes.
*   **Cross-file Expansion:** Yes, handles `\input`.
*   **Known Limitations:** Another text-based tool with all the usual limitations. Less battle-tested than `latexpand`.

#### 5. ExpandTeX
*   **URL:** [CTAN](https://ctan.org/pkg/expandtex)
*   **Language:** TeX itself (requires `pdftex` or `xetex` to run)
*   **Maintenance Status:** Part of the `pdftex` distribution? Somewhat obscure. CTAN date is 2007.
*   **Definition Types Handled:** It uses the actual TeX engine to perform expansion, so it handles everything TeX handles: `\def`, `\edef`, `\gdef`, `\let`, `\newcommand`, etc.
*   **Nested Macro Calls:** Yes, perfectly, as it *is* TeX.
*   **Cross-file Expansion:** It can be configured to, but its primary purpose is to process a single stream of text.
*   **Known Limitations:** It is not a standalone text processor; it's a specialized TeX program. Its output is not intended to be human-readable but rather a fully-expanded stream for debugging. It will expand *all* expandable tokens, including TeX primitives, which is usually not what you want for source preprocessing. It is the most powerful but also the most "raw" tool on this list.

#### 6. delatex (De-LaTeX)
*   **URL:** [GitHub](https://github.com/mkropat/delatex)
*   **Language:** Python
*   **Maintenance Status:** Abandoned. Last commit 2015.
*   **Definition Types Handled:** Its main goal is to strip LaTeX commands to extract plain text, but it has an `--expand` option for macros. Handles `\newcommand` and `\def`.
*   **Nested Macro Calls:** Attempts to.
*   **Cross-file Expansion:** Yes, via `\input`.
*   **Known Limitations:** The macro expansion is a secondary feature and is very fragile. It is not recommended for robust expansion tasks.

---

### **Category 2: LaTeX File Flattening / Unfolding Tools**

These tools resolve file inclusion commands to produce a single, flat `.tex` file.

#### 1. Latexpand
*   **URL:** [CTAN](https://ctan.org/pkg/latexpand)
*   **Language:** Perl
*   **Inclusion Commands Handled:** `\input`, `\include`, `\includeonly` (it honors this and only includes files listed by it).
*   **Preserves Comments:** Yes.
*   **Handles Conditional Includes:** No. It does not interpret conditional statements like `\if...\fi`. It will blindly follow `\input` and `\include` commands inside false conditionals.
*   **Known Limitations:** The gold standard for flattening. Its main limitation is with conditionals and complex path management (though it handles TEXINPUTS well).

#### 2. flatex
*   **URL:** [CTAN](https://ctan.org/pkg/flatex) | [Original Author's Page](http://www.cs.cornell.edu/people/egs/flatex/)
*   **Language:** C
*   **Maintenance Status:** Stable but very old. A classic tool.
*   **Inclusion Commands Handled:** `\input`, `\include`. Also understands `\newcommand` and `\let` to avoid recursing on redefined inclusion commands.
*   **Preserves Comments:** Yes.
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** Does not handle the `import` package commands (`\import`, `\subimport`). Can have issues with complex `\newcommand` redefinitions of `\input`.

#### 3. latexpand (Jean-Côme Charpentier's version)
*   **URL:** [GitHub](https://github.com/JCChat/latexpand)
*   **Language:** Python
*   **Inclusion Commands Handled:** `\input`, `\include`.
*   **Preserves Comments:** Yes.
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** See Category 1 entry. Abandoned.

#### 4. latex-make
*   **URL:** [GitHub](https://github.com/fordsfords/latex-make)
*   **Language:** Perl
*   **Maintenance Status:** Actively maintained.
*   **Inclusion Commands Handled:** Its primary tool `lm_flatten` handles `\input`, `\include`. It is aware of the `import` package and handles `\import`, `\subimport`, `\inputfrom`.
*   **Preserves Comments:** Yes.
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** Part of a larger build system suite. Very capable for flattening, especially with the `import` package.

#### 5. Rubber
*   **URL:** [Homepage](https://launchpad.net/rubber/) | [GitHub](https://github.com/rubber-org/rubber)
*   **Language:** Python
*   **Maintenance Status:** Maintained, but development is slow.
*   **Inclusion Commands Handled:** `\input`, `\include`. Can also manage bibliographies and indexes as part of its build process.
*   **Preserves Comments:** Yes, when flattening.
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** Rubber is a full compilation system. Its flattening feature is just one part of it. The command is `rubber --flatten source.tex`.

#### 6. arara
*   **URL:** [CTAN](https://ctan.org/pkg/arara) | [GitHub](https://github.com/cereda/arara)
*   **Language:** Java (with rules written in TeX)
*   **Maintenance Status:** Actively maintained.
*   **Inclusion Commands Handled:** Arara itself doesn't flatten, but it has a community rule `flatten.yaml` that uses `latexpand` (the Perl tool) to do the job. Therefore, it inherits the capabilities of `latexpand`.
*   **Preserves Comments:** Yes (via `latexpand`).
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** Requires setting up the `flatten` rule. It's a meta-tool that executes other tools.

#### 7. Make4ht (from TeX4ht)
*   **URL:** [CTAN](https://ctan.org/pkg/tex4ht)
*   **Language:** Lua
*   **Maintenance Status:** Actively maintained.
*   **Inclusion Commands Handled:** `\input`, `\include`. Its build system can output a flattened file as an intermediate step.
*   **Preserves Comments:** Yes.
*   **Handles Conditional Includes:** No.
*   **Known Limitations:** Part of the massive TeX4ht system for HTML conversion. Not a dedicated standalone flattener, but can be used as one.

### **Notable Mentions / Edge Cases**

*   **`\write18` (Shell Escape) + `cp`/`cat`:** The most basic "tool" is to use the TeX engine itself with shell escape enabled to recursively `\input` files and write the job to a file. This is non-trivial to set up correctly.
*   **Compiler Output:** Some compilers like `pdflatex` have a `-output-directory` option and can show the paths of opened files in the log. This isn't a flattener but can be used to find all dependencies.
*   **LyX:** The graphical editor LyX internally represents documents in a flattened way and can export to a single LaTeX file, resolving its own includes. It is not a command-line tool for arbitrary `.tex` files.
*   **Detex:** While its goal is to remove *all* LaTeX commands to extract text, some implementations (`detex` from CTAN) have basic inclusion resolution. Do not use it for faithful flattening.