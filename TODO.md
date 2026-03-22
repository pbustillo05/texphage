# TODO.md — Future Improvements & Enhancements

This file tracks planned features, enhancements, and low-priority bugs that are not considered regressions for `BUGS.md`.

## Methodology
- **Proposed:** New ideas are added here first.
- **Accepted:** After user review, ideas are moved here. The user will prioritize them.
- **In Progress:** The agent moves an item here before starting work.
- **Done:** Completed tasks.

---

## Proposed

*   **[REFACTOR] Create a shared `arxiv_utils` module**

    **Motivation:** Logic for downloading and processing arXiv sources is duplicated between `scripts/extractor.py` and `scripts/test_fidelity.py`. This makes maintenance harder and creates an unhealthy dependency where a test script imports from another script.

    **Plan:**
    1.  Create a new file: `src/texphage/arxiv_utils.py`.
    2.  Move `get_all_arxiv_ids` from `scripts/extractor.py` into `src/texphage/arxiv_utils.py`.
    3.  Create a new function `download_and_extract_source(arxiv_id, dest_dir)` in the new module. This function will contain the logic for downloading a tarball from `https://arxiv.org/e-print/` and extracting it. This logic should be merged from `scripts/extractor.py:process_arxiv_id` and `scripts/test_fidelity.py:_download_arxiv`. It should handle both `.tar.gz` and gzipped `.tex` files.
    4.  Refactor `scripts/extractor.py` and `scripts/test_fidelity.py` to import and use the new functions from `src/texphage/arxiv_utils.py`.

*   **[REFACTOR] Consolidate regex helper functions**

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

    **Motivation:** The `find_command` function in `src/texphage/find_packages.py` defines its own complex regex patterns for matching macro definitions, which are very similar to the `find_all` pattern in `src/texphage/demacro.py`. This is a form of code duplication.

    **Plan:**
    1.  Expose the component patterns of `find_all` in `demacro.py` (e.g., `find_def`, `find_new_com`) in a way that they can be imported.
    2.  Refactor the `pattern_env` and `pattern_cmd` regexes in `find_packages.py:find_command` to be built by combining the imported patterns from `demacro.py` with a specific `csname`. This is lower priority as it is more involved.


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

*   **[ENHANCEMENT] `build_minimal_preamble` Phase 1 — unify parsing with `find_packages.py`**

    Added `PackageCall` dataclass and `find_explicit_package_calls(preamble)` to
    `find_packages.py`.  `build_minimal_preamble` now uses these instead of its own
    duplicated `_USEPACKAGE_RE` regex.  Result is functionally identical to before
    (same `\usepackage` calls, same options, same order) but parsing is unified and
    structured data (`names`, `options`) is available for Phase 2 pruning.
