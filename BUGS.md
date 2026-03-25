# BUGS.md — Regression Tracker

Maintained by `scripts/test_fidelity.py` and Claude acting as Coding Agent.
See `CLAUDE.md` for the full workflow.

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

## BUG-26: `\tikzset` style definitions stripped from minimal preamble

- **severity**: CRITICAL
- **root_cause_pattern**: package_stripping
- **failure_mode**: C
- **seen_in**: [2602.04425] — paper uses `\tikzset{curarrow/.style={...}}` in its
  preamble. The body uses `\arrow[curarrow=X]{...}` inside a `tikzcd` diagram.
  Pipeline output fails: `! Package pgfkeys Error: I do not know the key '/tikz/curarrow'`
- **description**: `build_minimal_preamble` only preserves `\usepackage` and
  `\usetikzlibrary` calls. It strips `\tikzset{...}` blocks entirely, even when they
  define new TikZ styles or keys used in the document body. When a `\tikzset` block
  defines a custom style (e.g. `curarrow/.style={...}`), every use of that style in
  the body causes a pgfkeys "unknown key" error. Similarly, `\pgfplotsset{...}`,
  `\pgfkeys{...}`, and `\tikzcdset{...}` configuration blocks are also stripped,
  which can cause silent changes or compile errors depending on what they configure.
- **relevant_code_location**: `src/texphage/pipeline.py` — `build_minimal_preamble()`,
  which collects only `\usepackage`/`\usetikzlibrary` calls and a fixed set of
  declaration types; no hook for `\tikzset` or related pgf configuration blocks.
- **relevant_latex_docs**: https://ctan.org/pkg/pgf (pgfmanual §88 — `\tikzset`,
  key-value configuration); https://ctan.org/pkg/pgfplots (pgfplots §4 — `\pgfplotsset`)
- **reproduction**: `tests/fixtures/bug_26_tikzset_stripped/main.tex`
- **first_seen**: 2026-03-25
- **last_seen**: 2026-03-25
- **status**: OPEN

---

## BUG-27: `\let\cmd\relax` guard-reset strips before package load

- **severity**: CRITICAL
- **root_cause_pattern**: package_stripping
- **failure_mode**: C
- **seen_in**: [2601.15214] — uses `llncs` document class (which defines `\proof` and
  `\endproof`). The source resets them with `\let\proof\relax\let\endproof\relax` before
  loading `\usepackage{amsthm}`, which also defines `\proof`. Without the reset,
  pipeline output fails: `! LaTeX Error: Command \proof already defined.`
- **description**: Some document classes (e.g. `llncs`, `beamer`) define environments
  such as `proof` internally. When authors load `amsthm` or another package that also
  defines `proof`, they must first reset the class-defined commands with
  `\let\proof\relax\let\endproof\relax`. The pipeline strips all `\let` declarations
  from the preamble (they are treated as custom macro definitions), but these particular
  `\let`-to-`\relax` resets are NOT macro definitions — they are package-load guards.
  Without them, the `\usepackage{amsthm}` in the minimal preamble triggers a "Command
  already defined" error. This is distinct from BUG-25: BUG-25 is about `\newtheorem`
  conflicting with class definitions; BUG-27 is about `amsthm` (or similar packages)
  being unable to load because the class has pre-defined environments they want to own.
- **relevant_code_location**: `src/texphage/pipeline.py` — `build_minimal_preamble()`;
  `\let` commands are not in any of the preserved-pattern lists.
- **relevant_latex_docs**: https://texdoc.org/serve/texbytopic/0 (Ch.11 — `\let`);
  llncs.cls source (defines `\newenvironment{proof}`)
- **reproduction**: `tests/fixtures/bug_27_let_relax_stripped/main.tex`
- **first_seen**: 2026-03-25
- **last_seen**: 2026-03-25
- **status**: OPEN

---

## BUG-28: `\theoremstyle` declarations stripped from minimal preamble

- **severity**: MEDIUM
- **root_cause_pattern**: package_stripping
- **failure_mode**: C
- **seen_in**: [2601.12450] — paper uses `\theoremstyle{definition}` between groups of
  `\newtheorem` declarations. After stripping, `definition`, `remark`, and `example`
  environments use `plain` style (italic body) instead of `definition` style (upright
  body), causing SSIM < 0.85 on affected pages and text_diff_lines = 264.
- **description**: `build_minimal_preamble` captures `\newtheorem` declarations and
  guards them with `\@ifundefined`. It does not capture `\theoremstyle{...}` commands
  that appear between them. In amsart/amsthm, `\theoremstyle` is sticky: it applies to
  all subsequent `\newtheorem` calls. When stripped, the theorem styles in the minimal
  preamble are wrong. Specifically, environments that the author declared after
  `\theoremstyle{definition}` (so their body text is upright/non-italic) are re-declared
  in the minimal preamble without a preceding `\theoremstyle{definition}`, so they
  inherit `plain` style and render in italics. This changes the visual output even
  though the text content is identical.
- **relevant_code_location**: `src/texphage/pipeline.py` — `build_minimal_preamble()`,
  `_NEWTHEOREM_RE` loop; `\theoremstyle` commands are not in `_NEWTHEOREM_RE` and not
  captured by any other preserved-pattern list.
- **relevant_latex_docs**: https://texdoc.org/pkg/amsthm (§3 — `\theoremstyle`)
- **reproduction**: `tests/fixtures/bug_28_theoremstyle_stripped/main.tex`
- **first_seen**: 2026-03-25
- **last_seen**: 2026-03-25
- **status**: OPEN
