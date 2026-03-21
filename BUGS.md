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
