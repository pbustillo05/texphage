# TODO.md — Future Improvements & Enhancements

This file tracks planned features, enhancements, and low-priority bugs that are not considered regressions for `BUGS.md`.

## Methodology
- **Proposed:** New ideas are added here first.
- **Accepted:** After user review, ideas are moved here. The user will prioritize them.
- **In Progress:** The agent moves an item here before starting work.
- **Done:** Completed tasks.

## Priority scale (0–5)

| Score | Meaning |
|---|---|
| **5** | Fix immediately — CRITICAL correctness regression or compile failure (use BUGS.md instead) |
| **4** | High impact; tackle this sprint — breaks a format contract or blocks measurement |
| **3** | Medium impact; tackle after 4-items — removes architectural debt or enables key workflows |
| **2** | Nice to have — improves quality but not blocking anything |
| **1** | Speculative or very long-term — significant investment for uncertain payoff |
| **0** | Parking lot only |

> **Bugs (BUGS.md) for reference:** BUG-27 `\let\relax` stripped — **5/5**; BUG-26 `\tikzset` stripped — **5/5**; BUG-28 `\theoremstyle` stripped — **4/5**.

---

## Proposed

*   **[INFRASTRUCTURE] RAG pipeline for LaTeX package sources** `priority: 1/5`

    **Motivation:** When the testing-agent or coding-agent encounters an
    `undefined_control_sequence \foo` from an unrecognised package, the current
    diagnostic path is texdef → docs (manual lookup). A RAG system would make
    Mode A failures near-automatic to diagnose:

    1. **Knowledge base:** Scan CTAN for the top N most-used packages. Download
       their `.sty`/`.cls` sources, chunk by macro definition, store in a vector
       database.
    2. **Query on failure:** For `\undefined_control_sequence \foo`, query:
       "definition, argument spec, and expansion of `\foo` in package `<pkg>`".
    3. **Retrieval:** The coding-agent gets the actual source of `\foo` as context.
    4. **Fix generation:** With ground-truth source in context, the agent writes
       the correct regex branch and test without manual doc lookup.

    **Acceptance criterion:** For a set of 10 Mode A bugs whose macros come from
    known packages, the agent successfully retrieves the correct definition in
    at least 8/10 cases without any manual lookup step.

    **Priority: 1/5** — significant engineering investment; highest value when
    the quarterly audit starts finding many Mode A patterns.

*   **[INFRASTRUCTURE] Coverage dashboard** `priority: 2/5`

    **Motivation:** Track pipeline improvement over time. After each quarterly
    audit, we should be able to see whether coverage has improved.

    **Plan:**
    1. Create `coverage.json` in the project root with the schema:
       `{package_name: {total_defs: N, matched_defs: M, pct: F, last_updated: date}}`
    2. The quarterly-audit agent updates this file after each run.
    3. A simple `scripts/coverage_report.py` reads it and prints a sorted table.

    **Acceptance criterion:** After a quarterly audit run, `coverage.json` exists
    and `scripts/coverage_report.py` prints a table showing per-package coverage
    percentages for the top 50 arXiv math packages.

    **Priority: 2/5** — useful for motivation and prioritisation but not urgent
    while the bug list is long.

*   **[REFACTOR] Create a shared `arxiv_utils` module** `priority: 3/5`

    **Motivation:** Logic for downloading and processing arXiv sources is duplicated between `scripts/extractor.py` and `scripts/test_fidelity.py`. This makes maintenance harder and creates an unhealthy dependency where a test script imports from another script.

    **Plan:**
    1.  Create a new file: `src/texphage/arxiv_utils.py`.
    2.  Move `get_all_arxiv_ids` from `scripts/extractor.py` into `src/texphage/arxiv_utils.py`.
    3.  Create a new function `download_and_extract_source(arxiv_id, dest_dir)` in the new module. This function will contain the logic for downloading a tarball from `https://arxiv.org/e-print/` and extracting it. This logic should be merged from `scripts/extractor.py:process_arxiv_id` and `scripts/test_fidelity.py:_download_arxiv`. It should handle both `.tar.gz` and gzipped `.tex` files.
    4.  Refactor `scripts/extractor.py` and `scripts/test_fidelity.py` to import and use the new functions from `src/texphage/arxiv_utils.py`.

*   **[RESEARCH] Audit all preamble constructs that must survive `build_minimal_preamble` (Note 2)** `priority: 3/5`

    **Motivation.** `build_minimal_preamble` grew its preservation list reactively
    (one BUGS entry at a time: `\newtheorem`, `\title`, `\definecolor`, etc.).  There
    is no systematic inventory of what else changes the PDF when stripped.  The
    result is a long tail of silent failures in arXiv tests.

    **Goal.** Produce a definitive table: for each preamble construct category, classify
    it as KEEP, DROP, NORMALIZE, or CONDITIONAL, backed by playground evidence.

    **Known candidates to investigate (each requires a `latex_playground.py` test):**

    | Construct | Package | Hypothesis | Status |
    |---|---|---|---|
    | `\newtheoremstyle{...}` | amsthm | Changes theorem formatting | `[inferred]` KEEP |
    | `\declaretheoremstyle{...}` | thmtools | Same | `[inferred]` KEEP |
    | `\theoremstyle{...}` | amsthm | Affects subsequent `\newtheorem` style | `[inferred]` KEEP (adjacent to kept `\newtheorem`) |
    | `\numberwithin{counter}{parent}` | amsmath | Changes equation numbering | `[inferred]` KEEP |
    | `\bibliographystyle{...}` | LaTeX base | Selects bib style; changes reference rendering | `[inferred]` KEEP |
    | `\geometry{...}` | geometry | Sets page dimensions | `[inferred]` KEEP or NORMALIZE (see Note 4 TODO) |
    | `\hypersetup{...}` | hyperref | Sets link colours, PDF metadata | `[inferred]` KEEP |
    | `\setmainfont{...}` | fontspec | Changes main font | `[inferred]` KEEP |
    | `\setmathfont{...}` | unicode-math | Changes math font | `[inferred]` KEEP |
    | `\setlength{\parskip}{...}` | LaTeX base | Changes vertical spacing | `[inferred]` KEEP |
    | `\linespread{...}` | LaTeX base | Changes line spacing | `[inferred]` KEEP |
    | `\AtBeginDocument{...}` | LaTeX base | Deferred setup | `[inferred]` CONDITIONAL |

    **Protocol:** For each row, run a `latex_playground.py` snippet that shows the PDF
    changes when the line is stripped.  Tag each row `[observed]` after testing.

    **Deliverable:**
    -   `docs/preamble-preservation.md` — the filled-in table with evidence notes.
    -   Corresponding additions to `build_minimal_preamble` for all KEEP rows not
        yet implemented, each with a regression test.

    **Priority: 3/5** — systematic, not urgent, but will catch many arXiv failures
    that are currently silent.

*   **[INFRASTRUCTURE] Uniform arXiv category sampling in `test_fidelity.py` (Note 3)** `priority: 3/5`

    **Motivation.** `_DEFAULT_CATEGORIES = ['math.CT', 'math.CT', 'math.AT', 'math.AT', 'cs.LO']`
    samples almost exclusively from category-theoretic mathematics and logic.  arXiv
    has ~170 active categories spanning physics, CS, stats, biology, etc.  A biased
    sample cannot measure the 90%+ success-rate target reliably and misses macro
    patterns dominant in other fields.

    **Plan:**
    1.  Create `scripts/arxiv_categories.json` — a list of all active arXiv category
        IDs.  This is the pool for uniform sampling.
    2.  Add `_sample_categories(n, strategy, rng)` to `test_fidelity.py` supporting:
        - `"uniform"` — draw uniformly from all categories (best for coverage).
        - `"legacy"` — current five-category list (for historical reproducibility).
    3.  Add `--sampling uniform|legacy` CLI flag (default `uniform`).
    4.  When a sampled category yields no papers (sparse category), retry with a
        different category rather than skipping the slot.
    5.  Log the category distribution of each run to the run's `manifest.json` and
        to `tests/runs/HISTORY.md`.

    **Acceptance criterion:** A run with `--sampling uniform -n 20` produces at most 2
    papers from any single category; the manifest shows the sampled distribution.

    **Priority: 3/5** — needed for meaningful success-rate measurement (Note 5).

*   **[ENHANCEMENT] Normalize `\geometry`/`\hypersetup` into `\usepackage` options (Note 4)** `priority: 2/5`

    **Motivation.** Several LaTeX packages support both load-time options
    (`\usepackage[margin=1in]{geometry}`) and a post-load configuration command
    (`\geometry{margin=1in}`).  `build_minimal_preamble` currently strips the
    post-load form, silently changing page layout.  The same applies to
    `\hypersetup{...}`, `\mathtoolsset{...}`, `\lstset{...}`, `\captionsetup{...}`.

    **Verification step (mandatory before any code):** Use `latex_playground.py` to
    confirm that `\usepackage[margin=1in]{geometry}` and
    `\geometry{margin=1in}` (after `\usepackage{geometry}`) produce identical PDFs.
    Do the same for `\hypersetup`.  Tag results `[observed]` in a comment in
    `pipeline.py`.  If a package does *not* support load-time equivalence, classify
    it as KEEP in the preamble audit (Note 2) instead.

    **Plan (if verification passes):**
    1.  Build `CONFIG_COMMANDS: dict[str, str]` mapping config command → package:
        ```python
        CONFIG_COMMANDS = {
            r'\geometry':      'geometry',
            r'\hypersetup':    'hyperref',
            r'\mathtoolsset':  'mathtools',
            r'\lstset':        'listings',
            r'\captionsetup':  'caption',
        }
        ```
    2.  In `build_minimal_preamble`, scan the raw preamble for `CONFIG_COMMANDS`
        calls.  For each found call, emit
        `\PassOptionsToPackage{<opts>}{<pkg>}` before the corresponding `\usepackage`
        line (or add the package if it's not already present).
    3.  Unit-test: preamble with `\usepackage{geometry}\geometry{margin=2cm}` →
        output contains `\PassOptionsToPackage{margin=2cm}{geometry}`.

    **Risk.** `\hypersetup` often contains macro-valued keys (title strings, author
    names) that reference undefined commands in the minimal preamble.  Consider
    keeping `\hypersetup` as-is rather than normalizing it if the playground
    confirms this risk.

    **Priority: 2/5** — requires playground verification first; the preamble audit
    (Note 2) must discover the full list of affected commands.

*   **[INFRASTRUCTURE] CI enforcement (pytest / ruff / mypy / import guards)** `priority: 3/5`

    **Motivation.** CLAUDE.md declares that `import re` (stdlib) is banned under `src/`,
    `sys.path.insert` is banned under `src/` and `tests/`, and the full gate
    (`pytest && ruff check && mypy`) must pass before every commit. None of this is
    machine-enforced. The repo itself currently violates the `import re` rule in
    `src/texphage/unfold.py` and several scripts. Rules only documented in prose drift.

    **Plan:**
    1.  Add `.github/workflows/ci.yml` running `pytest tests/ -v`, `ruff check src/`,
        and `mypy src/texphage/` on every push and pull request.
    2.  Add a `ruff` rule (or a small `scripts/check_imports.py`) that fails if
        `import re` or `from re import` appears anywhere under `src/`.
    3.  Add a similar check that fails if `sys.path.insert` or `sys.path.append` appears
        under `src/` or `tests/`.
    4.  Fix the existing violations in `src/texphage/unfold.py` to unblock CI.

    **Acceptance criterion:** A PR that adds `import re` to any file under `src/` causes
    CI to fail with a clear error message.

    **Priority: 3/5** — turns documented rules into enforced invariants; stops rule drift.

*   **[BUGFIX] xy_to_tikz Phase 0: mechanical correctness fixes** `priority: 3/5`

    **Motivation.** `scripts/xy_to_tikz.py` has at least four mechanical bugs that make
    it unreliable as an experimental tool: it uses stdlib `re` (violating CLAUDE.md
    invariant), has `print()` calls at module import time, and contains `match.grouo`
    typos (runtime `AttributeError` on any match that hits those branches). These are
    easy, low-risk fixes.

    **Plan:**
    1.  Replace `import re` with `import regex as re` throughout `scripts/xy_to_tikz.py`.
    2.  Remove or guard all `print()` calls that execute at import time.
    3.  Fix all `match.grouo` → `match.group` typos (search for `grouo`).
    4.  Run the existing test suite (if any) or add a smoke test that imports the module
        without side effects.

    **Acceptance criterion:** `python -c "import scripts.xy_to_tikz"` produces no output
    and no error; `ruff check scripts/xy_to_tikz.py` passes.

    **Priority: 3/5** — 4 mechanical fixes; low risk; makes the script minimally correct
    and good entry-point work.

*   **[REFACTOR] Declarative preservation layer for `build_minimal_preamble`** `priority: 2/5`

    **Motivation.** `build_minimal_preamble()` is growing as a reactive exception ledger —
    one bug-number comment per rule (front matter, theorems, counters, colors, tikzset,
    let-resets, etc.). As the list grows, it becomes harder to audit and easier to miss
    interactions. The systematic preamble audit (Note 2) will make this worse if the
    output is just more ad-hoc rules bolted in.

    **Plan:**
    1.  Define a small `PreservationHandler` protocol:
        `def match(self, line: str, context: PreambleContext) -> bool`
        `def emit(self, line: str, context: PreambleContext) -> list[str]`
    2.  Create a registry `PRESERVATION_HANDLERS: list[PreservationHandler]` with one
        handler per category (UsepackageHandler, NewtheoremHandler, TheoremstyleHandler,
        TikzsetHandler, LetRelaxHandler, etc.).
    3.  Replace the current monolithic loop with a dispatch over the registry.
    4.  Tests target handler categories, not only specific bugs.

    **Acceptance criterion:** All existing regression tests pass; adding a new preamble
    construct requires adding one handler class, not editing a monolithic function.

    **Priority: 2/5** — important long-term architecture, but all current bugs are fixable
    in the existing structure. Do after the bug queue clears.

*   **[INFRASTRUCTURE] Stable / Experimental / Planned tool tiers** `priority: 2/5`

    **Motivation.** The toolbox narrative (README, `docs/user_applications.md`) treats
    `xy_to_tikz` and the core pipeline as peers. They are not: one is a tested, packaged
    library; the other is an experimental script with known correctness issues. This blur
    makes the repo harder to trust for new users and harder to document accurately.

    **Plan:**
    1.  Define three tiers in `docs/user_applications.md` and `README.md`:
        - **Stable** — packaged modules in `src/texphage/`, covered by the full quality gate.
        - **Experimental** — scripts that are useful but not part of the supported API.
        - **Planned** — notes and specs only, no runnable code yet.
    2.  Tag each tool in `docs/user_applications.md` with its tier.
    3.  Add a one-sentence disclaimer to `README.md` for experimental tools.

    **Acceptance criterion:** `README.md` clearly marks which tools are stable vs
    experimental; `docs/user_applications.md` tier column is filled in for all tools.

    **Priority: 2/5** — documentation/organizational; reduces false expectations.

*   **[RESEARCH] Benchmark demacro against other LaTeX normalization tools (Note 6)** `priority: 1/5`

    **Motivation.** Pablo notes (Note 6): we should compare our success rate to similar
    tools. This would (a) calibrate our 90% target, (b) identify techniques used
    elsewhere that we could adopt, and (c) serve as external validation for the project.

    **Plan:**
    1.  Survey extensively existing LaTeX macro-expansion or other latex normalization tools (e.g. `https://github.com/JamesMcGreivy/expand-latex-macros`, `https://github.com/hl-ren/Latex-newcommand-expander`, `https://github.com/xpandlatex/xpandlatex`, `https://github.com/neolaf2/latex-expander`, `https://ctan.org/pkg/de-macro`, Pandoc's LaTeX reader,...)
    2.  Define a shared benchmark: a python script randomly downloading a set of 50 arXiv papers, extracts snippets of various sizes (each time keep the whole preamble but take a subset of the body), success measured with the following metrics: compiles (Y/N), criticality of errors in log files (to be made precise), and similarity score (SSIM).
    3.  Run each tool on the benchmark set and record an initial success rate comparison.
    4.  Write up results in `docs/notes/benchmark_comparison.md`.

    **Acceptance criterion:** `docs/notes/benchmark_comparison.md` exists with a table
    comparing at least 3 tools on the shared benchmark set.

    **Priority: 1/5** — research/future value; do after the success-rate tracking
    infrastructure (Note 5) exists to make our own measurement credible.

## Accepted
*(Items to be prioritized by the user)*

*   **[INFRASTRUCTURE] Per-run success rate tracking (Note 5)** `priority: 4/5` ← PROMOTED 2026-04-11

    **Motivation.** There is no quantitative measure of pipeline quality over time.
    The target is ≥90% of tested papers producing near-identical PDF text.  Without
    tracking, it is impossible to see whether bug fixes are actually improving
    coverage or whether regressions are being introduced.

    **Definition of success:** A paper is a *success* if its pipeline output (a)
    compiles without error and (b) has `severity == 'OK'` (zero or negligible text
    diff and SSIM ≥ 0.95).

    **Plan:**
    1.  After each paper in `run()`, append one JSON object to
        `tests/runs/results.jsonl` (append-only, one object per line):
        ```json
        {"arxiv_id": "...", "date": "...", "success": true,
         "severity": "OK", "text_diff_lines": 0, "min_ssim": 1.0,
         "failure_mode": null, "category": "math.CT"}
        ```
    2.  Create `scripts/success_rate.py` that reads `results.jsonl`, computes:
        - Rolling 20-paper success rate (%).
        - Per-failure-mode breakdown (compile error / HIGH / MEDIUM / LOW).
        - A simple trend line (last 10 runs or 10 batches of 5).
        Prints a formatted table to stdout.
    3.  Print the current rolling rate at the end of each `run()` call.
    4.  Add `tests/runs/results.jsonl` to `.gitignore` (it is local run data, not
        source; `tests/runs/HISTORY.md` is the committed summary).

    **Acceptance criterion:** After two testing-agent runs,
    `python scripts/success_rate.py` prints a rolling success rate and trend.

    **Priority: 4/5** — needed to measure progress toward the 90% target.

*   **[ENHANCEMENT] Truly minimal `\usepackage` list in `build_minimal_preamble` — Phase 2 (beta pruning)** `priority: 3/5`

    Phase 1 (unify parsing with `find_packages.py`, preserve options+order) is **Done** — see Done section.

    **Motivation.** `build_minimal_preamble()` emits the author's explicit `\usepackage`
    calls verbatim (correct, same options, same order).  But it is not minimal: many
    packages load each other internally, so several calls are redundant — the package
    would be loaded anyway as a transitive dependency.  The goal of Phase 2 is to emit
    only the "root" subset.

    **Data already available.** `find_packages.py` caches the full transitive closure per
    package in `cache/texlive_dependencies.json` via `get_dependencies(pkg)`.
    `find_explicit_package_calls(preamble)` (added in Phase 1) returns structured
    `PackageCall` objects with `names` and `options` already parsed.

    ---

    **Sub-problem 1 — Redundancy pruning.**

    Given the author's explicit list `roots = [A, B, C, ...]`, a package `P` is
    redundant if it appears in the transitive closure of any other root `Q`
    (`P in get_dependencies(Q) and P != Q`).

    ```python
    def _minimal_roots(explicit_pkgs: list[str]) -> list[str]:
        from texphage.find_packages import get_dependencies
        result = []
        for pkg in explicit_pkgs:
            if not any(
                pkg in get_dependencies(other) and other != pkg
                for other in explicit_pkgs if other != pkg
            ):
                result.append(pkg)
        return result  # preserves preamble order
    ```

    Note: `\usepackage{A,B}` loads A and B independently — use `PackageCall.names`
    (already split) when calling `_minimal_roots`.

    ---

    **Sub-problem 2 — Preserving options for pruned packages.**

    If `\usepackage[utf8]{inputenc}` is pruned (because some kept package loads it
    transitively), the options would be silently lost.  Fix: emit
    `\PassOptionsToPackage{utf8}{inputenc}` before all `\usepackage` calls for every
    pruned package that had non-empty options.

    ---

    **Sub-problem 3 — Order sensitivity.**

    Preserve the original relative order of kept packages.  Emit `\PassOptionsToPackage`
    calls first.  Use the fidelity test suite (SSIM + text diff) to catch
    order-induced regressions — do **not** hard-code ordering rules.

    ---

    **Sub-problem 4 — Topological sort via `order_usepackages.json`.**

    Pruning to root packages is necessary but not sufficient: the *relative order*
    of the surviving packages can also matter.  `src/texphage/data/order_usepackages.json`
    encodes known constraints: its keys are packages that must appear
    *after* everything in their value list.  Example: `cleveref` must come after
    `hyperref`, `varioref`, `amsthm`, etc.

    *Implementation:*
    1.  Load `order_usepackages.json` at import time (or lazily) as
        `MUST_COME_AFTER: dict[str, list[str]]`.
    2.  After pruning, apply a topological sort of the surviving package list that
        respects the constraints.  Packages not mentioned in the JSON keep their
        original relative order (stable-sort fallback so we never reorder
        unconstrained packages unnecessarily).
    3.  If the sort detects a cycle (shouldn't happen for well-formed LaTeX), log a
        warning and fall back to the original order.
    4.  Unit-test: given `[cleveref, amsmath, hyperref]` (out of order), assert the
        sorted output places `hyperref` before `cleveref`.

    *Note:* `order_usepackages.json` is preliminary and incomplete; it is a data
    file the code consumes, not a hardcoded list.  Extend it as new ordering
    constraints are discovered during arXiv testing.

    ---

    **Coding strategy.**

    1.  Implement `_minimal_roots` and unit-test it (mock `get_dependencies` to avoid
        network/disk calls in CI).
    2.  Implement `\PassOptionsToPackage` emission for pruned-but-optioned packages;
        unit-test options survive pruning.
    3.  Add `build_minimal_preamble_beta(raw_tex)` in `pipeline.py` that calls
        parse → prune → emit PassOptions → emit minimal `\usepackage` list.
    4.  Fidelity-test on a fixed seed; accept MEDIUM regressions from layout reflow,
        reject CRITICAL/HIGH as blockers.

    **Known risks.**

    -   `get_dependencies` shells out to `kpsewhich` on first call; JSON cache
        mitigates cost after first run.
    -   Custom `.sty` files bundled in arXiv tarballs are not in TeX Live and will
        never be pruned (they appear in no transitive closure) — safe by construction.
    -   Package option conflicts are a LaTeX-level error inherited from the original
        preamble; our pruning does not introduce new conflicts.

*   **[ENHANCEMENT] `pgfkeys` Support** `priority: 2/5` — Add parsing support for `\pgfkeys` and `\tikzset`, which are used extensively in TikZ and other packages for key-value options. This is a major undertaking.
*   **[ENHANCEMENT] Conditional Support** `priority: 2/5` — Add basic support for TeX conditionals like `\if...`, `\ifx...`, especially for handling starred versions of commands/environments where the logic is often `\newif\if@star ... \@ifstar{\@startrue...}{\@starfalse...}`.
*   **[REFACTOR] `demacro.py` cleanup** `priority: 2/5` — The `build_dictionary` function is becoming very large. Investigate splitting the logic for each definition type (e.g., `_handle_new_com`, `_handle_def`) into separate helper functions.

## In Progress

## Done

See `docs/EVOLUTION.md` for the full history of completed phases and key decisions.

*   [ENHANCEMENT] Assert single-line body invariant (Note 1) — **Phase 6** in EVOLUTION.md
*   [REFACTOR] Centralize all regex in `_regex.py` + naming conventions — **Phase 3** in EVOLUTION.md
*   [REFACTOR] Replace all non-regex string pattern-finding with regex — **Phase 3**
*   [REFACTOR] Consolidate regex helper functions (`new_csname`, `com_name`, etc.) — **Phase 3**
*   [REFACTOR] `find_command` pattern reuse via `_CMD_DEF_KEYWORDS_PATTERN` — **Phase 3**
*   [ENHANCEMENT] `build_minimal_preamble` Phase 1 — unified parsing via `PackageCall` — **Phase 3**
*   [PACKAGING] CLI entrypoint and package metadata (`texphage`, `texphage-unfold`, `--json`) — **Phase 5** in EVOLUTION.md
