# Note for Claude: Python Naming Convention Audit and Refactoring Plan

**To:** Claude
**From:** Gemini
**Date:** 2026-03-23
**Subject:** Full-repo Python naming convention refactor.

## 1. Analysis of Current State

I have conducted a full-repository review of the Python code (`.py` files) to assess the consistency of our naming conventions.

**The Good:**
- **File Names:** Consistently use `snake_case.py` (e.g., `find_packages.py`). This is correct.
- **Class Names:** Consistently use `PascalCase` (e.g., `PackageCall`). This is correct.
- **Function/Method Names:** Mostly use `snake_case()` (e.g., `find_explicit_package_calls`).

**The Inconsistencies:**

1.  **Attribute Names:** Some data classes use `camelCase` for attributes instead of `snake_case`.
    - **File:** `src/texphage/find_packages.py`
    - **Class:** `PackageCall`
    - **Attributes:** `is_tikzlib`, `lib_type`.

2.  **Compiled Regex Variable Names:** This is the biggest area of inconsistency. We have at least three different styles in use.
    - **Style 1 (The Goal):** `_UPPER_SNAKE_CASE_RE` in `src/texphage/pipeline.py` (e.g., `_DOCCLASS_RE`, `_NEWTHEOREM_RE`). This is an excellent, unambiguous convention that we will adopt globally.
    - **Style 2:** `snake_case` in `src/texphage/_regex.py` and `find_packages.py` (e.g., `find_com`, `find_env`, `find_file`, `find_pkg_lib`).
    - **Style 3:** `snake_case_regex` in `scripts/extractor.py` (e.g., `arxiv_id_regex`).

## 2. The New Unified Naming Convention

To improve code clarity and maintainability, all Python code in this repository must adhere to the following conventions, based on PEP 8.

| Construct Type                      | Naming Convention             | Example                  |
| ----------------------------------- | ----------------------------- | ------------------------ |
| Modules / Files                     | `snake_case.py`               | `demacro.py`             |
| Classes                             | `PascalCase`                  | `PackageCall`            |
| Functions, Methods, Variables       | `snake_case`                  | `build_dictionary`       |
| Attributes                          | `snake_case`                  | `is_tikz_lib`            |
| Constants                           | `UPPER_SNAKE_CASE`            | `MAX_ITERATIONS`         |
| **Compiled Regex Objects**          | `_UPPER_SNAKE_CASE_RE`        | `_FIND_PACKAGES_RE`      |

The leading underscore for regex objects indicates they are module-internal, which is generally true for our usage.

## 3. Refactoring Prompt for You (Claude)

Your task is to refactor the entire Python codebase to strictly enforce the unified naming convention defined above. This is a sensitive, repo-wide change that requires precision. Proceed with extreme care.

### **Mandatory Action Plan:**

1.  **Do not commit any changes.** Your work is a refactoring pass that must be reviewed before it is merged.
2.  For each inconsistency identified below, perform a **project-wide, case-sensitive, whole-word search and replace**. Using an IDE's "refactor/rename" feature is strongly recommended over a simple text search to ensure all call sites, definitions, and usages are updated simultaneously and correctly.

### **List of Refactoring Tasks:**

**Task A: Rename Class Attributes**

1.  In `src/texphage/find_packages.py`:
    - Rename the attribute `is_tikzlib` to `is_tikz_lib`.
    - Update all usages of this attribute within the file.

**Task B: Unify Compiled Regex Variable Names**

Rename the following compiled regex variables across the project to the `_UPPER_SNAKE_CASE_RE` format. Ensure you find and update every usage of each variable.

1.  **File:** `src/texphage/_regex.py`
    - Rename `find_com` to `_FIND_COMMAND_RE`.
    - Rename `find_env` to `_FIND_ENV_RE`.

2.  **File:** `src/texphage/find_packages.py`
    - Rename `find_file` to `_FIND_FILE_RE`.
    - Rename `find_pkg_lib` to `_FIND_PACKAGE_LIB_RE`.

3.  **File:** `scripts/extractor.py`
    - Rename `arxiv_id_regex` to `_ARXIV_ID_RE`.

4.  **File:** `src/texphage/demacro.py`
    - Rename `find_def` to `_FIND_DEF_RE`.
    - Rename `find_edef` to `_FIND_EDEF_RE`.
    - *(Note: These are raw strings, not compiled regexes, but their intent is the same. Let's make them consistent.)*

### **Verification:**

After completing all renames, you must verify that the codebase is still functional and compliant:

1.  **Run the Linter:** Execute `ruff check . --fix` and `ruff format .` to catch any new style issues and ensure consistent formatting.
2.  **Run the Test Suite:** Execute `pytest tests/ -v`. All tests must pass. If any test fails, you must debug and fix the issue caused by the renaming before concluding your work.

This is a critical infrastructure task. Precision is paramount. Do not proceed until you have a clear plan to execute these renames safely.
