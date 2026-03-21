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
- **first_seen**: 2026-03-21
- **last_seen**: 2026-03-21
- **status**: OPEN

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
  pattern mismatch; `Bob and Alice` not produced
- **first_seen**: 2026-03-21
- **last_seen**: 2026-03-21
- **status**: OPEN

---

## BUG-3: `pipeline_output.tex` written without preamble (body-only)

- **severity**: CRITICAL
- **root_cause_pattern**: `_run_pipeline` in `scripts/test_fidelity.py`
- **seen_in**: all papers (infrastructure bug, not paper-specific)
- **description**: `demacro()` returns the expanded document body only (the content between
  `\begin{document}...\end{document}`). The testing agent wrote this body directly to
  `pipeline_output.tex` without a `\documentclass` or preamble, so every `latexmk` compile
  of the pipeline output failed with "LaTeX Error: Missing \begin{document}."
- **relevant_code_location**: `scripts/test_fidelity.py` — `_run_pipeline()`, preamble reconstruction;
  `src/texphage/demacro.py` — `demacro()` return contract
- **relevant_latex_docs**: N/A (infrastructure bug)
- **reproduction**: Any paper — `pipeline_output.tex` from earlier test runs lacks `\documentclass`
- **fix**: Call `preprocessing(tex)` to extract the preamble, then write
  `preamble + \begin{document} + expanded_body + \end{document}` to `pipeline_output.tex`
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
- **first_seen**: 2026-03-21
- **last_seen**: 2026-03-21
- **status**: OPEN
