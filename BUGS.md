# BUGS.md — Regression Tracker

Maintained by `scripts/test_fidelity.py` and Claude acting as Coding Agent.
See `AGENTS.md` for the full workflow.

## Severity Scale
- **CRITICAL**: Pipeline output fails to compile with LaTeX, or causes a TeX infinite loop
- **HIGH**: Compiles but page count changes, OR any page has SSIM < 0.85
  AND text diff > 5 lines on that page (both conditions required; layout-only
  shifts from macro expansion are expected and are not HIGH by themselves)
- **MEDIUM**: Any page SSIM 0.85–0.95, or total text diff 10–50 lines
- **LOW**: Text diff < 10 lines, cosmetic only

## Entry Schema
Required: title, severity, root_cause_pattern, seen_in (arXiv IDs or package
names), description, relevant_code_location, relevant_latex_docs, reproduction
(minimal .tex snippet — also added to tests/fixtures/), first_seen, last_seen,
status (OPEN / IN_PROGRESS / FIXED).

---
<!-- New entries appended below by test_fidelity.py or Claude -->

## BUG-1: xargs positional key [i=default] syntax not supported

- **severity**: LOW
- **root_cause_pattern**: `find_new_com` / `content_replacement` in `demacro.py`
- **seen_in**: packages using `xargs` — `\newcommandx{\cmd}[N][1=val]{body}`
- **description**: `\newcommandx` with positional key syntax `[i=default]` (e.g. `[1=Hello]`)
  is captured verbatim as the default value including the `i=` prefix. The `i=` should be
  parsed to associate the default with argument position `i`, not stored as part of the value.
- **relevant_code_location**: `src/texphage/demacro.py` — `build_dictionary()` `new_com`
  branch; `default_dict['1'] = macro.group('new_com_default1')` captures `[1=Hello]` → after
  stripping → `1=Hello` instead of `Hello`.
- **relevant_latex_docs**: https://ctan.org/pkg/xargs
- **reproduction**: `\newcommandx{\greet}[2][1=Hello]{#1, #2!}` + `\greet{World}` →
  produces `1=Hello, World!` instead of `Hello, World!`
- **fix**: In the `new_com` branch of `build_dictionary()`, when `new_com_xargs` is set,
  strip the leading `\d+=` prefix from each captured default before storing it.
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-2: `\def` delimited patterns only capture single tokens

- **severity**: LOW
- **root_cause_pattern**: `token()` in `_regex.py` / `build_dictionary()` `def` branch
- **seen_in**: `\def` with delimited argument patterns, e.g. `\def\swap#1and#2{#2 and #1}`
- **description**: In TeX, `\def\cmd#1<delim>{body}` captures everything up to `<delim>` as
  `#1`, including multi-character sequences. Our regex converts `#1` to `(?<arg1>token_pattern)`
  where `token_pattern` matches exactly ONE TeX token. Multi-char sequences like `Alice` are not
  captured in a single match.
- **relevant_code_location**: `src/texphage/_regex.py` — `token` lambda; `src/texphage/demacro.py`
  — `build_dictionary()` `def` branch, pattern construction via `re.sub(r'#(\d)', ...)`.
- **relevant_latex_docs**: TeXbook Ch.20; https://texdoc.org/serve/texbytopic/0 Ch.10
- **reproduction**: `\def\swap#1and#2{#2 and #1}` + `\swap Alice and Bob` →
  Playground verified: TeX produces `B and Alice ob` (`#1` = delimited → `Alice `,
  `#2` = undelimited → one token `B`; `ob` left in stream). Our pattern was producing
  a `pattern_mismatch` because `token()` only matches one char/token, not multi-char
  sequences like `Alice`. Fixed via `_def_param_pattern()` helper that uses lazy `.*?`
  for delimited params and `token()` for undelimited params.
- **fix**: Replace `re.sub(r'#(\d)', …)` in `def`/`edef` branches with new
  `_def_param_pattern()` helper that distinguishes delimited vs. undelimited params.
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-3: `pipeline_output.tex` written without preamble (body-only)

- **severity**: CRITICAL
- **root_cause_pattern**: `_run_pipeline` in `scripts/test_fidelity.py`
- **seen_in**: all papers (infrastructure bug, not paper-specific)
- **description**: `demacro()` returns the expanded document body only (the content between
  `\begin{document}...\end{document}`). The testing agent wrote this body directly to
  `pipeline_output.tex` without a `\documentclass` or preamble, so every `latexmk` compile
  of the pipeline output failed with "LaTeX Error: Missing \begin{document}." This is a misunderstanding of how to use demacro(). The point is that the whole latex code can be replaced by changing the preamble to simply calling all `\usepackage{...}` found by `find_packages.py` (without ANY custom macros) and by replacing the body by the demacro'ed body. And our goal is that this should return the exact same pdf output. See the first few lines of "README.md" for a precise formulation of the goal of this repo.
- **relevant_code_location**: `scripts/test_fidelity.py` — `_run_pipeline()`, preamble reconstruction;
  `src/texphage/demacro.py` — `demacro()` return contract
- **relevant_latex_docs**: N/A (infrastructure bug)
- **reproduction**: Any paper — `pipeline_output.tex` from earlier test runs lacks `\documentclass`
- **fix**: Use `find_packages.py` to replace the preamble by the appropriate concatenation of `\usepackage{...}` commands. It might be important to preserve order, and it's certainly important to preserve options. One might need to experiment further to find the appropriate modifications to make.
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-21
- **status**: FIXED

---

## BUG-4: `\let` alias to unknown command causes `bad escape` in `re.sub`

- **severity**: CRITICAL
- **root_cause_pattern**: `expand()` in `src/texphage/demacro.py`
- **seen_in**: any paper using `\let\foo\unknownCmd` where `\unknownCmd` is not defined in preamble
- **description**: `\let\foo\cite` stores the literal string `\cite` as the replacement in
  `macro_dict`. When passed as the `repl` argument to `re.sub()`, Python interprets `\c` as a
  regex backreference escape and raises `regex._regex_core.error: bad escape \c at position 0`.
- **relevant_code_location**: `src/texphage/demacro.py` — `expand()`, string vs. callable check
- **relevant_latex_docs**: https://texdoc.org/serve/texbytopic/0 Ch.11 (`\let`)
- **reproduction**: `\let\foo\cite` in preamble + `\foo{ref1}` in body → crash
- **fix**: In `expand()`, wrap non-callable replacements in a lambda:
  `if not callable(repl): repl = lambda m, r=repl: r`
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-21
- **status**: FIXED

---

## BUG-5: `\DeclareMathOperator` not recognized — macros left unexpanded

- **severity**: HIGH
- **root_cause_pattern**: `find_all` / `build_dictionary()` in `src/texphage/demacro.py`
- **seen_in**: papers using `amsmath` — `\DeclareMathOperator{\UJ}{UJ}` etc.
- **description**: `\DeclareMathOperator{\myOp}{Op}` (from `amsmath`) was not listed in
  `find_all`, so `build_dictionary()` never saw it, and the macro `\myOp` remained in the
  output unexpanded, potentially causing compilation failures or wrong output.
- **relevant_code_location**: `src/texphage/demacro.py` — `find_dmo` pattern definition,
  `find_all` alternation, `build_dictionary()` `dmo` branch
- **relevant_latex_docs**: https://ctan.org/pkg/amsmath (amsldoc.pdf §3.4)
- **reproduction**: `\DeclareMathOperator{\myOp}{Op}` + `$\myOp(x)$` → `\myOp` in output
- **fix**: Added `find_dmo` pattern (`\\DeclareMathOperator ?(\*)?{csname}{symbol}`) to
  `find_all` and a corresponding `elif macro.group('dmo')` branch in `build_dictionary()`
  that expands to `\operatorname{symbol}`
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-21
- **status**: FIXED

---

## BUG-6: `\begin{comment}...\end{comment}` environments not protected from whitespace collapsing

- **severity**: CRITICAL
- **root_cause_pattern**: `preprocessing()` in `src/texphage/demacro.py` — `_VERBATIM_ENVS` list
- **seen_in**: 2602.05689 (uses `\usepackage{comment}`)
- **description**: The `comment` package defines a `comment` environment whose content is
  excluded from output. Its implementation scans verbatim line-by-line looking for
  `\end{comment}` at the beginning of a line. When `preprocessing()` collapses all whitespace
  (step 4), the content of `\begin{comment}...\end{comment}` is joined into a single line.
  The comment package's scanner (`\next`) then reaches EOF without finding `\end{comment}`,
  causing: `! File ended while scanning use of \next.`
  The fix is to add `comment` (and similar environments: `IEEEproof`, user-defined via `\excludecomment`)
  to `_VERBATIM_ENVS` so their content is stashed and restored intact.
- **relevant_code_location**: `src/texphage/demacro.py` — `_VERBATIM_ENVS` pattern at line ~281
- **relevant_latex_docs**: https://ctan.org/pkg/comment
- **reproduction**: `\usepackage{comment}` + `\begin{comment}\nsome text\n\end{comment}` in
  body → after whitespace collapse → `\begin{comment} some text \end{comment}` on one line
  → `latexmk` error: `! File ended while scanning use of \next.`
- **fix**: Strip `\begin{comment}...\end{comment}` blocks entirely in `preprocessing()` step 2b
  (before whitespace collapse), since they produce no output — same treatment as `%` line comments.
- **first_seen**: 2026-03-21
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-7: `pipeline_output.tex` compiled from wrong directory — `.bib` files not found

- **severity**: CRITICAL
- **root_cause_pattern**: `_run_pipeline` / `_compile_latex` in `scripts/test_fidelity.py`
- **seen_in**: 2601.05479, 2601.08474 (any paper with a `.bib` bibliography)
- **description**: `pipeline_output.tex` is compiled with latexmk running in `paper_dir/`
  (the per-paper results directory), but `.bib` files live in `raw_data/` (where the arXiv
  tarball was extracted). LaTeX cannot find the bibliography, so all citations are undefined
  and latexmk exits with an error.
- **relevant_code_location**: `scripts/test_fidelity.py` — Step 5 compile call; `_run_pipeline`
  writes `pipeline_output.tex` only to `paper_dir/`
- **relevant_latex_docs**: N/A (infrastructure bug)
- **reproduction**: Any paper with `\bibliography{refs}` — `refs.bib` is in `raw_data/` but
  latexmk runs in `paper_dir/`
- **fix**: Write `pipeline_output.tex` to `raw_data_dir` as well, and compile from there using
  `_compile_latex(raw_data_dir, ..., tex_file='pipeline_output.tex')`.
- **first_seen**: 2026-03-22
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-8: `build_minimal_preamble` strips `\title`/`\author`/`\date` — `\maketitle` fails

- **severity**: CRITICAL
- **root_cause_pattern**: `build_minimal_preamble` in `src/texphage/pipeline.py`
- **seen_in**: 2601.19200 (any `amsart`/`amsbook` paper — they put `\title`, `\author`,
  `\address`, `\email`, `\keywords`, `\subjclass` in the preamble, not the body)
- **description**: `build_minimal_preamble` keeps only `\documentclass` and `\usepackage`
  calls, stripping all other preamble commands including `\title{...}`, `\author{...}`,
  `\date{...}`, etc. For `article` class these commands usually appear in the body, but for
  `amsart`/`amsbook` they are preamble commands. After stripping them, `\maketitle` in the
  body has nothing to typeset and LaTeX errors with "No `\title` given."
- **relevant_code_location**: `src/texphage/pipeline.py` — `build_minimal_preamble()`;
  `find_explicit_package_calls` in `find_packages.py` (only returns `\usepackage` calls)
- **relevant_latex_docs**: https://www.ams.org/arc/tex/amsart/amsart.pdf (§2 — front matter)
- **reproduction**: `amsart` paper with `\title{Foo}`, `\author{Bar}` in preamble, `\maketitle`
  in body → after `build_minimal_preamble`, preamble has no `\title` → "No `\title` given"
- **fix**: In `build_minimal_preamble`, add `_FRONT_MATTER_RE` pattern that matches
  `\title`, `\author`, `\date`, `\address`, `\email`, `\keywords`, `\subjclass`,
  `\dedicatory`, `\thanks` from the raw preamble (using balanced-brace matching) and
  appends them after the package lines.
- **first_seen**: 2026-03-22
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-9: Preprocessing inserts `\par` inside `\title{...}` — "Paragraph ended before `\title`"

- **severity**: CRITICAL
- **root_cause_pattern**: `preprocessing()` in `src/texphage/demacro.py` — step 3 (blank
  lines → `\par`)
- **seen_in**: 2602.15358 (any paper with a blank line inside a command argument in the body)
- **description**: Step 3 of `preprocessing()` replaces every blank line with `\par`. If the
  source has a blank line between the opening `{` and the content of a command argument
  (e.g. `\title{\n\n  My Title}` or `\title[short]{\n% comment\n  My Title}`), the blank
  line (or comment removal leaving a blank line) becomes `\par`, producing
  `\title[short]{ \par My Title}`. In `\title`, `\section`, and many other commands,
  `\par` inside the mandatory argument is forbidden and causes "Paragraph ended before
  `\title` was complete."
- **relevant_code_location**: `src/texphage/demacro.py` — `preprocessing()` step 3;
  `re.sub(r'\n[ \t]*\n+', r' \\par ', tex)`
- **relevant_latex_docs**: https://texdoc.org/serve/texbytopic/0 Ch.5 (paragraphs, `\par`)
- **reproduction**:
  ```latex
  \title{
  % a comment
  My Paper Title}
  ```
  After comment stripping the comment line becomes blank → blank line → `\par` →
  `\title{ \par My Paper Title}` → "Paragraph ended before `\title` was complete."
- **fix**: Add `_strip_par_in_groups()` helper (called as preprocessing step 4.5) that
  scans the flat string and removes `\par` tokens at brace depth > 0, while leaving
  top-level `\par` tokens (between body paragraphs) intact.
- **first_seen**: 2026-03-22
- **fixed**: 2026-03-22
- **status**: FIXED

---

## BUG-10: `\def \foo {body}` — trailing space in `def_pattern` causes pattern_mismatch for zero-arg macros

- **severity**: HIGH
- **root_cause_pattern**: `build_dictionary()` `def`/`edef` branch — `_def_param_pattern` receives whitespace-only `def_pattern`
- **failure_mode**: B
- **seen_in**: [2601.18343] — `\def \R {{\mathbb R}}`, `\def \cl {{\mathrm{\bf cl}}}` (312 problematic macros)
- **description**: The `find_def` regex captures `def_pattern` as `[^\{]*`, which greedily
  includes the space between the command name and the opening `{` of the body. For a zero-arg
  macro like `\def \R {{\mathbb R}}`, `def_pattern` is `' '` (a single space) rather than `''`.
  `_def_param_pattern(' ')` escapes the space to `'\ '` and appends it to the call-site
  pattern, producing `\\R(?![a-zA-Z])\ `. This pattern requires `\R` to be followed by a
  literal space, so it fails whenever `\R` appears before `$`, `}`, `)`, `.`, etc.
  texdef confirms: `\def \R {{\mathbb R}}` and `\def\R{{\mathbb R}}` are identical in TeX.
- **relevant_code_location**: `src/texphage/demacro.py` — `build_dictionary()` `def` branch
  (line ~550): `_def_param_pattern(macro.group('def_pattern'))` is called without first
  stripping whitespace from `def_pattern`.
- **relevant_latex_docs**: TeXbook Ch. 20 — spaces in parameter text before `{` are ignored
  for zero-argument definitions.
- **reproduction**:
  ```latex
  \documentclass{article}
  \usepackage{amsmath}
  \def \R {{\mathbb R}}
  \begin{document}
  $f: X \to \R$.
  \end{document}
  ```
  Pipeline produces `\R` unexpanded in body (pattern_mismatch), causing
  `Undefined control sequence \R` at compile.
- **fix**: In `build_dictionary()`, strip whitespace from `def_pattern` and `edef_pattern`
  before passing to `_def_param_pattern`. Alternatively, strip inside `_def_param_pattern`
  itself. The stripped string `''` produces the correct empty pattern for zero-arg macros.
- **first_seen**: 2026-03-23
- **last_seen**: 2026-03-23
- **status**: OPEN

---

## BUG-11: `\newtheorem` declarations stripped by `build_minimal_preamble` — theorem environments undefined

- **severity**: CRITICAL
- **root_cause_pattern**: `build_minimal_preamble` in `src/texphage/pipeline.py`
- **failure_mode**: A
- **seen_in**: [2601.11263, 2601.17623] — `\newtheorem{thm}{Theorem}[section]` etc.
- **description**: `build_minimal_preamble` keeps only `\documentclass`, `\usepackage`,
  `\usetikzlibrary`, and front-matter commands (`\title`, `\author`, etc.). It strips
  `\newtheorem{thm}{Theorem}[section]` and related declarations. The document body then
  uses `\begin{thm}...\end{thm}`, which fails with `! LaTeX Error: Environment thm undefined.`
  `\newtheorem` is not a macro to be expanded; it defines a LaTeX environment that must
  remain in the preamble for the body to compile correctly.
  `find_all` also does not recognise `\newtheorem` (confirmed: no matches in pattern probe),
  so the theorem environment names are never expanded or removed from the body either.
- **relevant_code_location**: `src/texphage/pipeline.py` — `build_minimal_preamble()`;
  `_FRONT_MATTER_RE` does not include `\newtheorem`.
- **relevant_latex_docs**: https://texdoc.org/pkg/amsthm; LaTeX2e companion §6.3
- **reproduction**:
  ```latex
  \documentclass{amsart}
  \newtheorem{thm}{Theorem}[section]
  \begin{document}
  \begin{thm}
    Hello world.
  \end{thm}
  \end{document}
  ```
  After `build_minimal_preamble`, `\newtheorem` is gone → compile error
  `Environment thm undefined`.
- **fix**: Add `\newtheorem` (and `\newtheorem*`) calls to the set of preamble lines
  preserved by `build_minimal_preamble`. A `_NEWTHEOREM_RE` pattern matching
  `\newtheorem{name}{print-name}[optional-counter]` and
  `\newtheorem*{name}{print-name}` should be added to the scan and its matches
  appended after the package lines.
- **first_seen**: 2026-03-23
- **last_seen**: 2026-03-23
- **status**: OPEN

---

## BUG-12: Whitespace collapse produces lines exceeding TeX's `bufsize` — compile fails for large papers

- **severity**: CRITICAL
- **root_cause_pattern**: `preprocessing()` in `src/texphage/demacro.py` — step 4 (whitespace collapse)
- **failure_mode**: C
- **seen_in**: [2602.08480] — 2,894-line source collapsed to single 218,126-character line
- **description**: Step 4 of `preprocessing()` collapses all whitespace (spaces, tabs,
  newlines) into single spaces, turning the entire document body into essentially one
  very long line. TeX's internal buffer (`bufsize`) defaults to 200,000 characters per
  line. For large papers (≥~200k characters in body), TeX aborts with:
  `! Unable to read an entire line---bufsize=200000. Please increase buf_size in texmf.cnf.`
  The paper 2602.08480 has a 2,894-line source; the pipeline output has a single 218,126-
  character body line, exceeding the limit by ~18k characters. The baseline compiles fine
  since the original source respects natural line breaks.
- **relevant_code_location**: `src/texphage/demacro.py` — `preprocessing()` step 4;
  `re.sub(r'[ \t]+', ' ', tex)` and the preceding newline collapse.
- **relevant_latex_docs**: https://texdoc.org/serve/texbytopic/0 §1.1 — TeX input processor
  reads one line at a time; `bufsize` is the maximum characters per line.
- **reproduction**: Any paper whose body exceeds 200,000 characters when collapsed to a
  single line. 2602.08480 (`Greg-MFO-notes3.tex`, 2,894 lines) is a confirmed case.
- **fix**: After demacro expansion, insert `\n` line breaks at `\par` boundaries in the
  output before writing `pipeline_output.tex`. The `\par` tokens in the expanded body
  represent paragraph boundaries — replacing them with `\n\n` would restore newlines
  without disrupting any regex patterns (the expansion is already complete at that point).
  Alternatively, insert `\n` after every `\par ` in the final pipeline output string.
- **first_seen**: 2026-03-23
- **last_seen**: 2026-03-23
- **status**: OPEN
