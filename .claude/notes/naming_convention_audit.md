# Naming Convention Audit — Claude's Plan

*Improving on Gemini's note at `.gemini/notes/naming_convention_audit.md`*

---

## What Gemini Got Right

- `_UPPER_SNAKE_CASE_RE` (as used in `pipeline.py`) is the right target convention for compiled regex objects.
- `is_tikzlib` → `is_tikz_lib` is a legitimate fix (missing word boundary in snake_case).
- Running `pytest` + `ruff` after every rename batch is correct.

---

## Where Gemini's Analysis Is Wrong or Imprecise

### 1. Type conflation: compiled objects vs. raw strings

Gemini proposes renaming `find_def` and `find_edef` to `_FIND_DEF_RE` and
`_FIND_EDEF_RE`, but notes in parentheses: *"These are raw strings, not
compiled regexes."* That parenthetical invalidates the rename.

**The `_RE` suffix must only be used for `regex.compile()`/`re.compile()`
return values.** Raw pattern strings that get assembled into larger patterns
should use a `_PATTERN` suffix instead. Giving a raw string the `_RE` suffix
is a lie that will confuse future readers who call `.match()` on it.

Correct classifications:

| Variable | File | Actual type | Target name |
|---|---|---|---|
| `find_com` | `_regex.py` | `re.compile()` object | `_FIND_COMMAND_RE` |
| `find_env` | `_regex.py` | `re.compile()` object | `_FIND_ENV_RE` |
| `find_file` | `find_packages.py` | `re.compile()` object | `_FIND_FILE_RE` |
| `find_pkg_lib` | `find_packages.py` | `re.compile()` object | `_FIND_PKG_LIB_RE` |
| `arxiv_id_regex` | `scripts/extractor.py` | `re.compile()` object (verify) | `_ARXIV_ID_RE` |
| `find_def` | `demacro.py` | raw pattern `str` | `_DEF_PATTERN` |
| `find_edef` | `demacro.py` | raw pattern `str` | `_EDEF_PATTERN` |

### 2. `lib_type` is not camelCase

Gemini flags `lib_type` as an inconsistency. It is already correct
`snake_case`. **Do not rename it.** The only real attribute issue is
`is_tikzlib` → `is_tikz_lib`.

### 3. Lambda builder functions in `_regex.py`

`_regex.py` also exports several *callable* helpers (`new_csname`, `com_name`,
`env_name`, `token`, etc.) that build and return pattern strings. These are
functions, not compiled objects, and follow `snake_case` correctly. Gemini did
not touch them — **keep them as-is.**

---

## Full Refactor Plan

### Prerequisites

Before any rename, grep for every call site:

```bash
# Find all usages before renaming
grep -rn 'find_com\b' src/ tests/ scripts/
grep -rn 'find_env\b' src/ tests/ scripts/
grep -rn 'find_file\b' src/ tests/ scripts/
grep -rn 'find_pkg_lib\b' src/ tests/ scripts/
grep -rn 'find_def\b' src/ tests/ scripts/
grep -rn 'find_edef\b' src/ tests/ scripts/
grep -rn 'arxiv_id_regex\b' src/ tests/ scripts/
grep -rn 'is_tikzlib\b' src/ tests/ scripts/
```

### Batch A — Class attribute (lowest risk)

| Old | New | File(s) |
|---|---|---|
| `is_tikzlib` | `is_tikz_lib` | `find_packages.py` + all call sites |

### Batch B — Raw pattern strings

| Old | New | File(s) |
|---|---|---|
| `find_def` | `_DEF_PATTERN` | `demacro.py` + all call sites |
| `find_edef` | `_EDEF_PATTERN` | `demacro.py` + all call sites |

### Batch C — Compiled regex objects

| Old | New | File(s) |
|---|---|---|
| `find_com` | `_FIND_COMMAND_RE` | `_regex.py` + all call sites |
| `find_env` | `_FIND_ENV_RE` | `_regex.py` + all call sites |
| `find_file` | `_FIND_FILE_RE` | `find_packages.py` + all call sites |
| `find_pkg_lib` | `_FIND_PKG_LIB_RE` | `find_packages.py` + all call sites |
| `arxiv_id_regex` | `_ARXIV_ID_RE` | `scripts/extractor.py` + all call sites |

### Verification after each batch

```bash
pytest tests/ -v && ruff check src/ scripts/ && mypy src/texphage/
```

### Final verification: no violations remain

```bash
# Should return zero hits for old names
grep -rn '\bfind_com\b\|\bfind_env\b\|\bfind_file\b\|\bfind_pkg_lib\b' src/ tests/ scripts/
grep -rn '\bfind_def\b\|\bfind_edef\b\|\barxiv_id_regex\b\|\bis_tikzlib\b' src/ tests/ scripts/
```

---

## Convention Reference (complete)

| Construct | Convention | Example |
|---|---|---|
| Module / file | `snake_case.py` | `find_packages.py` |
| Class | `PascalCase` | `PackageCall` |
| Function, method, variable | `snake_case` | `build_dictionary` |
| Attribute | `snake_case` | `is_tikz_lib` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_ITERATIONS` |
| Compiled `regex.compile()` object | `_UPPER_SNAKE_CASE_RE` | `_FIND_COMMAND_RE` |
| Raw regex pattern string | `_UPPER_SNAKE_CASE_PATTERN` | `_DEF_PATTERN` |
| Pattern-builder lambda/function | `snake_case` | `new_csname`, `token` |
