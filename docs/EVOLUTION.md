# EVOLUTION.md — Project Direction Log

Read this file plus `git log --oneline -30` **before starting any major new
implementation effort**. It records *what was built*, *why decisions were made*,
and *what was intentionally rejected* — so we never accidentally undo past work
or re-litigate settled choices.

The companion `/orient` skill automates this check.

---

## Phase 0: Infrastructure Bootstrap (2026-03-21)

**Built:** `pipeline.py` public API (`texphage()`, `texphage_to_dir()`,
`build_minimal_preamble()`); `test_fidelity.py` run harness; `PackageCall`
dataclass and `find_explicit_package_calls()` in `find_packages.py`.

**Key decisions:**
- Pipeline contract: `demacro()` returns expanded body only; caller wraps it
  with `\documentclass` + minimal preamble from `build_minimal_preamble()`.
- `build_minimal_preamble` is *reactive*: add preservation rules only when
  empirically shown to change the PDF (backed by a failing test). No speculative
  preservation.

**Fixed in this phase:** BUG-1, BUG-3, BUG-4, BUG-5, BUG-6, BUG-7.

---

## Phase 1: Core Preprocessing & Macro Expansion Fixes (2026-03-22 to 2026-03-23)

**Built/fixed:** `_strip_par_in_groups()` (step 4.5 of preprocessing); BUG-12
`\par\n` line-break fix in `texphage()` and `test_fidelity.py`; `find_main_file()`
preferred-name heuristic; braceless `\input` support; `\DeclareMathOperator`
recognition; `\def` delimited-param handling.

**Key decisions:**
- Preprocessing order is sacred (see `CLAUDE.md` §Preprocessing contract).
  Never change step order; always protect verbatim before collapsing whitespace.
- `_strip_par_in_groups()` uses regex-driven tokenizer, not character loops.
  Brace depth + environment depth both tracked (BUG-16 added env depth).
- BUG-12 fix (`\par ` → `\par\n`) applied in `texphage()` post-expansion,
  not inside `demacro()`. Keeps the 200k-char bufsize limit from breaking large
  papers without affecting regex matching.

**Fixed in this phase:** BUG-2, BUG-8–BUG-16.

---

## Phase 2: Preamble Preservation Buildout (2026-03-23 to 2026-03-24)

**Built:** `_NEWTHEOREM_RE`, `_FRONT_MATTER_RE`, `\excludeversion`/`\includeversion`
preservation, csname/expandafter support, unfold `\inputfrom` variants,
deduplication of `\newtheorem` declarations, `\newtheoremstyle`/`\newtheoremrm`
support, `\definecolor`/`\colorlet` preservation, `\@ifundefined` guard wrapping.

**Key decisions:**
- `\newtheorem` in minimal preamble is guarded with `\@ifundefined{<env>}{...}{}`
  to prevent class-conflict errors (BUG-25). This is the standard, safe pattern.
- `\excludeversion`/`\includeversion` (from `version` package) must be preserved
  because they affect which content blocks are typeset (BUG-18).
- `\expandafter\def\csname...\endcsname` is parsed as a named `\def` (BUG-19);
  the csname is evaluated once at parse time. Full dynamic csname expansion is
  out of scope (would require a TeX interpreter).
- `\newtheoremrm` and similar class-specific definers: treated as `\newtheorem`
  wrappers, not macros to expand (BUG-20).

**Fixed in this phase:** BUG-17–BUG-25.

---

## Phase 3: Regex Centralization Refactor (2026-03-24)

**Built:** All compiled regex patterns moved exclusively to `_regex.py`.
Naming conventions enforced throughout: `_UPPER_SNAKE_CASE_RE` for compiled
objects, `_UPPER_SNAKE_CASE_PATTERN` for raw strings, `snake_case` for
builder lambdas. Helper functions (`new_csname`, `com_name`, `find_specific_com`,
etc.) moved from `demacro.py` to `_regex.py`. No `re.compile()` calls outside
`_regex.py`.

**Key decisions:**
- `import re` (stdlib) is banned everywhere; always `import regex as re`.
  PCRE features (recursive named groups, duplicate captures) are required for
  balanced-brace matching. Replacing `regex` with `re` silently breaks all
  `\{...\}` argument captures.
- All string pattern-finding goes through `regex` — no `str.find()`,
  `.startswith()`, character loops, etc. for structural detection.
- Pattern builder lambdas (`token`, `com_name`, etc.) stay as `snake_case`
  functions, not renamed to `_RE` — they are callables, not compiled objects.

**Completed TODO items:**
- [REFACTOR] Centralize and reorganize all regex patterns in `_regex.py`
- [REFACTOR] Replace all non-regex string pattern-finding with regex
- [REFACTOR] Consolidate regex helper functions
- [REFACTOR] `find_command` pattern reuse
- [ENHANCEMENT] `build_minimal_preamble` Phase 1 — unify parsing with `find_packages.py`

---

## Phase 4: Toolbox Reframe (2026-03-25)

**Direction shift:** The project goal broadened from "produce a canonical 5-line
NLP input" to a general **LaTeX rearrangement toolbox** — a family of tools that
restructure LaTeX source with no (or minimal) PDF impact, sharing one regex
engine and one test infrastructure.

**New artefacts:**
- `user_applications.md` — catalogue of all current and planned applications
  with implementation status, from NLP corpus generation to a VSCode LSP.
- `docs/notes/toolbox_refactor_plan.md` — the structural changes needed to
  support the wider scope: `converters/` sub-package, per-tool CLI entrypoints,
  composable `texphage()` flags, and updated public API surface.
- `xy_to_tikz_critique.md` rewritten as a full implementation plan for the
  xy→tikzcd converter — the first concrete instance of the "obsolete LaTeX
  modernisation" converter family.
- `pretty_printer_implementation.md` updated to reflect its role as a
  standalone human-facing tool, not only a post-pipeline formatter.

**Key decisions:**
- The existing demacro pipeline is unchanged — all changes are additive.
- Tool flags (`convert_xy`, `pretty_print`) default to `False` in `texphage()`;
  no existing caller is affected.
- The VSCode LSP extension is a separate project; it depends on texphage as a
  library but will not live in this repo.
- Converters are explicitly "approximate" transformations (PDF not guaranteed
  identical); this is a first-class concept documented in their `LIMITATIONS`
  blocks, unlike the core tools which guarantee PDF identity.

---

## Phase 5: CLI and Packaging (2026-04-13)

**Built:** `src/texphage/cli.py` with two console entrypoints:

- `texphage <src> [--out PATH|DIR] [--json] [--main FILE]` — full pipeline
  (unfold + demacro → canonical .tex). `--json` emits `{"tex": ..., "attachments": [...]}` for LLM agent pipelines.
- `texphage-unfold <src> [--out FILE] [--main FILE]` — unfold only.

Both registered under `[project.scripts]` in `pyproject.toml`. `pyproject.toml`
description and keywords updated to toolbox framing. CLI Quick Start section
added to `README.md`.

**Key decisions:**
- `texphage-convert` deferred until the xy converter is promoted to a packaged
  module; the plan requires ≥2 converters before creating the `converters/`
  sub-package.
- On any exception, all commands write `{"error": "...", "code": N}` to stderr
  and exit non-zero, keeping agent pipelines debuggable.
- `--json` + `--out DIR` emits `{"canonical_path": "..."}` (not the full tex
  string) because the files are already written to disk.

**Completed TODO items:**
- [PACKAGING] CLI entrypoint and package metadata

---

## Phase 6: Body Newline Invariant Enforcement (2026-04-13)

**Built:** Enforced the format contract that the content between
`\begin{document}` and `\end{document}` in `canonical_tex` contains `\n` only
at `\par` boundaries — no structural newlines injected by the assembly code.

**Root cause:** `pipeline.py` was assembling canonical_tex as
`'\n\\begin{document}\n' + expanded_body + '\n\\end{document}\n'`, injecting a
stray `\n` immediately after `\begin{document}` and another immediately before
`\end{document}`. These two `\n`s appear inside the body region and violate the
invariant that every body `\n` must be preceded by `\par`.

**Fix:** Changed the assembly delimiters to `'\n\\begin{document}' +
expanded_body + '\\end{document}\n'` — no injected `\n` inside the body region.
The expanded body already starts and ends with a space (from whitespace
collapsing), which is legal at those positions in LaTeX.

**Test fix:** The pre-existing `test_body_newlines_only_at_par` was masking the
bug with `.strip('\n')` before the assertion and used stdlib `import re` instead
of the required `import regex`. Both issues corrected: strip removed, import
fixed.

**Key decisions:**
- The invariant is enforced at the `texphage()` output level, not inside
  `demacro()`. Preprocessing (whitespace collapse) produces a naturally
  newline-free body; only the BUG-12 `\par\n` fix re-introduces `\n`, and those
  are always at `\par` boundaries.
- No stripping of `expanded_body` content — the fix is purely in the assembly
  delimiters, keeping the invariant exact with zero special-casing.

**Completed TODO items:**
- [ENHANCEMENT] Assert single-line body invariant (Note 1)

---

## Intentional Non-Decisions (things we chose NOT to do)

- **Full TeX interpreter:** Out of scope. We use regex + heuristics, not a
  full TeX tokenizer. Limitations are documented with `[observed]`/`[inferred]`
  tags in source comments.
- **Generic `\<name>set{...}` matching** (e.g. catching `\hypersetup`,
  `\geometry` etc. via a wildcard): Rejected due to catastrophic false positives
  (`\subset{}`, `\reset{}`, any user-defined `\myset{}`). Only explicit named
  commands are preserved, added when empirically proven by a failing arXiv test.
- **Dynamic csname evaluation:** Only static `\expandafter\def\csname<literal>\endcsname`
  is supported. Fully dynamic csname construction (runtime-computed strings) is
  out of scope.
- **Scanning `.code` handlers for `\let`/`\def`:** Would produce noise. pgfkeys
  `.code` blocks run at TeX compile time identically in both original and pipeline
  output; no scanning needed.
