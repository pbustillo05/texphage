# TODO.md — Future Improvements & Enhancements

This file tracks planned features, enhancements, and low-priority bugs that are not considered regressions for `BUGS.md`.

## Methodology
- **Proposed:** New ideas are added here first.
- **Accepted:** After user review, ideas are moved here. The user will prioritize them.
- **In Progress:** The agent moves an item here before starting work.
- **Done:** Completed tasks.

---

## Proposed

*   **[ENHANCEMENT] Truly minimal `\usepackage` list in `_build_minimal_preamble`**

    **Motivation.** `_build_minimal_preamble()` currently copies all `\usepackage`
    commands verbatim from the original preamble.  This is correct but not minimal:
    many packages load each other internally, so several of those `\usepackage` calls
    are redundant — the package would have been loaded anyway as a transitive
    dependency of another one.  The goal is to emit only the subset of `\usepackage`
    calls that are truly "roots" of the dependency tree.

    **Data already available.** `find_packages.py` already builds and caches the
    full transitive closure for each package via `get_dependencies(pkg)` (stored
    in `cache/texlive_dependencies.json` — note: JSON, not pickle).  Calling
    `get_dependencies('amsmath')` returns `['amsmath', 'amstext', 'amsgen', ...]`.

    **Three sub-problems to solve:**

    ---

    **Sub-problem 1 — Redundancy pruning.**

    Given the author's explicit package list `roots = [A, B, C, ...]` (in preamble
    order), a package `P` is redundant if it appears in the transitive closure of
    any other root `Q` (i.e. `P in get_dependencies(Q) and P != Q`).

    Algorithm:

    ```python
    def _minimal_roots(explicit_pkgs: list[str]) -> list[str]:
        # explicit_pkgs: package names in preamble order, one entry per \usepackage call.
        # Does not need to handle options — only names.
        from texphage.find_packages import get_dependencies
        result = []
        for pkg in explicit_pkgs:
            covered_by_other = any(
                pkg in get_dependencies(other) and other != pkg
                for other in explicit_pkgs
                if other != pkg
            )
            if not covered_by_other:
                result.append(pkg)
        return result  # preserves original order
    ```

    Note: `get_dependencies` may return `[pkg]` for unknown packages (e.g. custom
    `.sty` files not in TeX Live).  That is safe — the package won't appear in
    anyone's transitive closure, so it will always be kept.

    Also note: `\usepackage{A,B,C}` loads A, B, C independently.  The regex
    `_USEPACKAGE_RE` captures the whole call including the comma-list; we need to
    split on commas to get individual names before passing to `_minimal_roots`.

    ---

    **Sub-problem 2 — Preserving options for pruned packages.**

    If the author wrote `\usepackage[utf8]{inputenc}` and `inputenc` is a
    transitive dep of some other kept package `X`, we cannot simply drop the call:
    the options would be lost and `inputenc` would be loaded without `[utf8]`.

    LaTeX's mechanism for this is `\PassOptionsToPackage{utf8}{inputenc}`, which
    must appear *before* the package (or any package that loads it) is first
    loaded.

    Strategy:

    1.  For each pruned package `P` that had options, emit
        `\PassOptionsToPackage{<options>}{P}` at the very top of the
        generated preamble (before any `\usepackage`).
    2.  For each pruned package `P` that had *no* options, drop it silently.

    Edge case: if the author loaded the same package with different options in
    multiple `\usepackage` calls (unusual but legal via `\usepackage` splitting),
    collect all option sets and emit one `\PassOptionsToPackage` per option set.

    ---

    **Sub-problem 3 — Order sensitivity.**

    Some packages are order-sensitive (canonical example: `hyperref` must be
    loaded last; `babel` interacts with many packages that must be loaded after
    it).  The correct strategy is:

    1.  Preserve the original relative order of all kept packages.
    2.  Emit `\PassOptionsToPackage` calls before all `\usepackage` calls.
    3.  Use the testing framework (SSIM + text diff) to detect any remaining
        order-induced regressions — do **not** try to hard-code ordering rules.

    There is no known static analysis for ordering constraints; empirical testing
    on arXiv papers is the right verification method.

    ---

    **Coding strategy (step-by-step).**

    1.  **Extend `_USEPACKAGE_RE` parsing.**  The current regex captures the full
        `\usepackage[opts]{pkgs}` string.  Add a second pass to split each match
        into `(options_str | None, [pkg1, pkg2, ...])` tuples, so options and
        package names are available separately.

    2.  **Implement `_minimal_roots`** (algorithm above) and unit-test it in
        `test_pipeline.py` with hand-crafted transitive-dep scenarios (mock
        `get_dependencies` if needed to avoid network calls).

    3.  **Implement `\PassOptionsToPackage` emission** for pruned packages that
        had options.  Unit-test that options survive pruning.

    4.  **Rebuild `_build_minimal_preamble`** to call these helpers in order:
        parse → prune → emit `\PassOptionsToPackage` → emit minimal `\usepackage` list.

    5.  **Integration test with `latex_playground.py`.**  For each arXiv paper in
        `tests/runs/` (or a small hand-picked set), compile `_build_minimal_preamble`
        output and verify it compiles without errors.  A paper failing to compile
        here reveals either a pruning error or a missing ordering rule.

    6.  **End-to-end fidelity test.**  Run the testing agent (`test_fidelity.py`)
        on a fixed seed and verify SSIM and text-diff scores do not regress
        relative to the current baseline (full preamble copy).  Accept MEDIUM-or-lower
        regressions from layout reflow; reject any compilation failure or HIGH
        regression as a blocker.

    **Known risks / open questions.**

    -   `get_dependencies` shells out to `kpsewhich` for unknown packages and reads
        `.sty` files.  Calling it for every package in every paper during test runs
        may be slow; the JSON cache mitigates this after the first run.
    -   Custom `.sty` files bundled inside arXiv tarballs are not in TeX Live and
        will not appear in `texlive_dependencies.json`.  They should never be pruned
        (they appear in no one's transitive closure) — the algorithm above handles
        this correctly by construction.
    -   Package option conflicts (two kept packages both loading `inputenc` with
        different options) are a LaTeX-level error independent of our pruning;
        we inherit whatever the author's original preamble would have produced.

*   **[ENHANCEMENT] `pgfkeys` Support:** Add parsing support for `\pgfkeys` and `\tikzset`, which are used extensively in TikZ and other packages for key-value options. This is a major undertaking.
*   **[ENHANCEMENT] Conditional Support:** Add basic support for TeX conditionals like `\if...`, `\ifx...`, especially for handling starred versions of commands/environments where the logic is often `\newif\if@star ... \@ifstar{\@startrue...}{\@starfalse...}`.
*   **[REFACTOR] `demacro.py` cleanup:** The `build_dictionary` function is becoming very large. Investigate splitting the logic for each definition type (e.g., `_handle_new_com`, `_handle_def`) into separate helper functions.

## Accepted
*(Items to be prioritized by the user)*

## In Progress

## Done

