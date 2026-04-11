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
- Preprocessing order is sacred (see `project-context.md` §The preprocessing
  contract). Never change step order; always protect verbatim before collapsing
  whitespace.
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
