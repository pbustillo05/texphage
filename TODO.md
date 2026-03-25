# TODO.md — Future Improvements & Enhancements

This file tracks planned features, enhancements, and low-priority bugs that are not considered regressions for `BUGS.md`.

## Methodology
- **Proposed:** New ideas are added here first.
- **Accepted:** After user review, ideas are moved here. The user will prioritize them.
- **In Progress:** The agent moves an item here before starting work.
- **Done:** Completed tasks.

---

## Proposed

*   **[INFRASTRUCTURE] RAG pipeline for LaTeX package sources**

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

    **Priority:** MEDIUM — significant engineering investment; highest value when
    the quarterly audit starts finding many Mode A patterns.

*   **[INFRASTRUCTURE] Coverage dashboard**

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

    **Priority:** LOW — useful for motivation and prioritisation but not urgent
    while the bug list is long.

*   **[REFACTOR] Create a shared `arxiv_utils` module**

    **Motivation:** Logic for downloading and processing arXiv sources is duplicated between `scripts/extractor.py` and `scripts/test_fidelity.py`. This makes maintenance harder and creates an unhealthy dependency where a test script imports from another script.

    **Plan:**
    1.  Create a new file: `src/texphage/arxiv_utils.py`.
    2.  Move `get_all_arxiv_ids` from `scripts/extractor.py` into `src/texphage/arxiv_utils.py`.
    3.  Create a new function `download_and_extract_source(arxiv_id, dest_dir)` in the new module. This function will contain the logic for downloading a tarball from `https://arxiv.org/e-print/` and extracting it. This logic should be merged from `scripts/extractor.py:process_arxiv_id` and `scripts/test_fidelity.py:_download_arxiv`. It should handle both `.tar.gz` and gzipped `.tex` files.
    4.  Refactor `scripts/extractor.py` and `scripts/test_fidelity.py` to import and use the new functions from `src/texphage/arxiv_utils.py`.

*   **[ENHANCEMENT] Assert single-line body invariant (Note 1)**

    **Motivation.** The 5-line output format requires that the expanded body contain no
    `\n` except those inserted at `\par` boundaries (BUG-12 intentionally adds
    `\par\n` to avoid TeX's 200k-char bufsize limit).  Any other source of newlines —
    verbatim restore re-introducing bare `\n`, output-assembly code joining lines, or
    macro expansions that produce literal newlines — violates the format contract
    silently.  Pablo reported that this invariant is currently broken.

    **Correct invariant (given BUG-12):** In non-verbatim regions of the body, every
    `\n` must be immediately preceded by `\par`.  Verbatim environments legitimately
    contain `\n` and are exempt.

    **Plan:**
    1.  Add a pytest test (`test_body_newlines_only_at_par`) that runs `texphage()` on
        a multi-paragraph document with no verbatim environments, extracts the body
        section from `canonical_tex`, and asserts that every `\n` is immediately
        preceded by `\par`.  Use `regex.findall(r'(?<!\\\\par)\\n', body)` to find
        violators.
    2.  Run the test — it should fail if the invariant is broken, confirming the
        regression.
    3.  Trace the source of stray `\n`: check verbatim restore (step 5 of
        preprocessing), macro expansion output, and the BUG-12 replacement line in
        `pipeline.py`.  The most likely culprits are: (a) `\par` without trailing
        space (so `\par ` → `\par\n` misses it), or (b) a secondary newline insertion
        somewhere in the pipeline.
    4.  Fix the root cause and verify the test passes.

    **Acceptance criterion:** `regex.findall(r'(?<!\\\\par)\\n', body)` returns `[]`
    for any document with no verbatim environments.

    **Priority:** HIGH — correctness regression; the format contract is explicitly
    stated in project-context.md.

*   **[RESEARCH] Audit all preamble constructs that must survive `build_minimal_preamble` (Note 2)**

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

    **Priority:** MEDIUM — systematic, not urgent, but will catch many arXiv failures
    that are currently silent.

*   **[INFRASTRUCTURE] Uniform arXiv category sampling in `test_fidelity.py` (Note 3)**

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

    **Priority:** MEDIUM — needed for meaningful success-rate measurement (Note 5).

*   **[ENHANCEMENT] Normalize `\geometry`/`\hypersetup` into `\usepackage` options (Note 4)**

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

    **Priority:** LOW — requires playground verification first; the preamble audit
    (Note 2) must discover the full list of affected commands.

*   **[INFRASTRUCTURE] Per-run success rate tracking (Note 5)**

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

    **Priority:** HIGH — needed to measure progress toward the 90% target.


## Accepted
*(Items to be prioritized by the user)*

*   **[ENHANCEMENT] Truly minimal `\usepackage` list in `build_minimal_preamble` — Phase 2 (beta pruning)**

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
    of the surviving packages can also matter.  `order_usepackages.json` (at the
    project root) encodes known constraints: its keys are packages that must appear
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

*   **[ENHANCEMENT] `pgfkeys` Support:** Add parsing support for `\pgfkeys` and `\tikzset`, which are used extensively in TikZ and other packages for key-value options. This is a major undertaking.
*   **[ENHANCEMENT] Conditional Support:** Add basic support for TeX conditionals like `\if...`, `\ifx...`, especially for handling starred versions of commands/environments where the logic is often `\newif\if@star ... \@ifstar{\@startrue...}{\@starfalse...}`.
*   **[REFACTOR] `demacro.py` cleanup:** The `build_dictionary` function is becoming very large. Investigate splitting the logic for each definition type (e.g., `_handle_new_com`, `_handle_def`) into separate helper functions.

## In Progress

## Done

*   **[REFACTOR] Centralize and reorganize all regex patterns in `_regex.py`** — implementing naming conventions, section organization, and pattern reuse as a foundational change.

    **Completed.** All regex now lives in `_regex.py`, organized into 8 sections. Naming conventions applied throughout (`_RE`, `_PATTERN`, `snake_case`).

*   **[REFACTOR] Replace all non-regex string pattern-finding with regex**

    **Completed.** Replaced char loops in `_strip_par_in_groups`, `_def_param_pattern`; char-index access in `_strip_delimiters`; `str.find()` in `build_minimal_preamble`; `str.endswith()` / `str.split(',')` in `find_attachments`.

    **Motivation:** The codebase rule is that all pattern-finding and pattern-replacement
    in strings must go through the `regex` module for homogeneity, auditability, and
    consistency with the MATCHES/CAPTURES/LIMITATIONS comment convention.

    The following production functions currently use ad-hoc string operations for
    structural pattern detection and must be migrated to regex:

    | Function | File | Current technique |
    |---|---|---|
    | `_strip_par_in_groups` | `src/texphage/demacro.py` | Character-by-character loop + slicing to detect `\par`, `\begin`, `\end`, brace depth |
    | `_def_param_pattern` | `src/texphage/demacro.py` | Character loop over `#N` placeholders and delimiter spans |
    | `_strip_delimiters` | `src/texphage/demacro.py` | Index access + char comparison to detect outer `{}`/`[]` |
    | `build_minimal_preamble` | `src/texphage/pipeline.py` | `str.find()` to locate `\begin{document}` |
    | `find_attachments` | `src/texphage/pipeline.py` | `str.endswith()` / `str.split(',')` for file-extension and bibliography parsing |

    **Plan:**
    1.  For each function, write a regex equivalent (with `MATCHES/CAPTURES/LIMITATIONS`
        comment) that produces identical results on the existing test suite.
    2.  Replace the ad-hoc implementation, run `pytest tests/ -v`, confirm green.
    3.  The hardest case is `_strip_par_in_groups`: it tracks brace depth and math
        environments, which requires a stateful approach — consider using a regex-driven
        tokenizer loop rather than a single compiled pattern.

    **Acceptance criterion:** `grep -rn 'str\.find\|\.startswith\|\.endswith\|\.isalpha\|\.isdigit\|\.index(' src/texphage/` returns zero hits used for structural pattern detection (utility uses such as path manipulation are exempt).

    **Priority:** LOW — correctness is unaffected; this is a code-quality / convention
    alignment task.

*   **[REFACTOR] Consolidate regex helper functions**

    **Completed.** Moved `new_csname`, `com_name`, `env_name`, `find_specific_com`, `find_specific_env` from `demacro.py` to `_regex.py`. All macro-definition pattern strings also moved.

    **Motivation:** The file `src/texphage/demacro.py` contains several small, regex-related helper functions (`new_csname`, `com_name`, `env_name`, etc.) that are conceptually part of the regex toolkit, which lives in `src/texphage/_regex.py`.

    **Plan:**
    1.  Move the following functions from `src/texphage/demacro.py` to `src/texphage/_regex.py`:
        - `new_csname` (lambda)
        - `com_name`
        - `env_name`
        - `find_specific_com`
        - `find_specific_env`
    2.  Update `src/texphage/demacro.py` to import these functions from `_regex.py`.

*   **[REFACTOR] `find_command` pattern reuse**

    **Completed.** Refactored `find_command` in `find_packages.py` to use `_CMD_DEF_KEYWORDS_PATTERN` and `_ENV_DEF_KEYWORDS_PATTERN` from `_regex.py`.

    **Motivation:** The `find_command` function in `src/texphage/find_packages.py` defines its own complex regex patterns for matching macro definitions, which are very similar to the `find_all` pattern in `src/texphage/demacro.py`. This is a form of code duplication.

    **Plan:**
    1.  Expose the component patterns of `find_all` in `demacro.py` (e.g., `find_def`, `find_new_com`) in a way that they can be imported.
    2.  Refactor the `pattern_env` and `pattern_cmd` regexes in `find_packages.py:find_command` to be built by combining the imported patterns from `demacro.py` with a specific `csname`. This is lower priority as it is more involved.

*   **[ENHANCEMENT] `build_minimal_preamble` Phase 1 — unify parsing with `find_packages.py`**

    Added `PackageCall` dataclass and `find_explicit_package_calls(preamble)` to
    `find_packages.py`.  `build_minimal_preamble` now uses these instead of its own
    duplicated `_USEPACKAGE_RE` regex.  Result is functionally identical to before
    (same `\usepackage` calls, same options, same order) but parsing is unified and
    structured data (`names`, `options`) is available for Phase 2 pruning.
