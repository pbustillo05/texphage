---
name: regex-writing
description: >
  Hygiene rules, naming conventions, and organization for writing and modifying
  regex patterns in texphage. Load whenever you need to write a NEW regex
  pattern or move an existing pattern into _regex.py. For testing and danger
  warnings on existing patterns, also load regex-danger-zone.
---

## The golden rule

**All pattern-finding and pattern-replacement is done exclusively via the
`regex` module. No exceptions.**

Never use `str.find()`, `.startswith()`, `.endswith()`, `.isalpha()`,
`.isdigit()`, `.index()`, character loops, or manual brace-counting to detect
structure in a LaTeX string. Every structural test on LaTeX source text must
be expressed as a compiled `regex` pattern.

The only exemptions are genuinely non-structural utility operations:
stripping whitespace from a shell-command result, splitting a Python file
path — things that have nothing to do with LaTeX token structure.

---

## Where every regex lives

**All compiled regex objects and raw pattern strings belong in
`src/texphage/_regex.py`.** No other file may define a compiled pattern.
`demacro.py`, `pipeline.py`, `find_packages.py`, `unfold.py`, and all other
modules import from `_regex.py` and call `.search()`, `.finditer()`,
`.sub()` etc. on the imported objects.

This rule exists because patterns are interdependent and the preprocessing
invariant (see below) must be respected globally. Scattering patterns across
files makes it impossible to audit invariant compliance or catch accidental
`re` vs `regex` mix-ups.

---

## Section organization of `_regex.py`

`_regex.py` is divided into eight numbered sections. Every new pattern goes
into the section that matches its purpose:

| § | Section name | What belongs here |
|---|---|---|
| 1 | **General primitives** | Sub-patterns (`embed_brackets`, `embed_braces`, `token`, `num_args`, `_NOT_TOKEN_CHAR_PATTERN`) reused as f-string fragments across other sections |
| 2 | **CS matchers** | `_FIND_COMMAND_RE`, `_FIND_ENV_RE`, `_XPARSE_PATTERN` — call-site matchers used in `expand()` |
| 3 | **CS helpers** | Builder functions: `new_csname`, `com_name`, `env_name`, `find_specific_com`, `find_specific_env` — compile a dynamic pattern from a runtime string |
| 4 | **Package-finding** | `_FIND_PKG_LIB_RE`, `_FIND_FILE_RE`, `_LETTERS_RE`, `_TIKZ_PREFIX_RE`, `_COLON_RE`, `_CMD_DEF_KEYWORDS_PATTERN`, `_ENV_DEF_KEYWORDS_PATTERN` |
| 5 | **Preprocessing** | `_VERBATIM_ENVS_RE`, `_COMMENT_RE`, `_BLOCK_COMMENT_RE`, `_BLANK_LINE_RE`, `_WHITESPACE_RE`, `_DOCUMENT_SPLIT_RE`, `_BEGIN_DOCUMENT_RE`, `_PAR_TOKENIZER_RE`, `_DEF_PARAM_PIECE_RE`, `_OUTER_DELIMITERS_RE` |
| 6 | **Macro-definition** | All `_DEF_*`, `_NEW_COM_*`, `_NEW_ENV_*`, `_FIND_ALL_RE`, `_CSNAME_DEF_RE`, `_ARG_REF_RE`, `_XARGS_*` patterns |
| 7 | **Preamble-building** | `_DOCCLASS_RE`, `_FRONT_MATTER_RE`, `_NEWTHEOREM_RE`, `_VERSION_ENV_RE`, `_DEFINECOLOR_RE` |
| 8 | **Attachment-finding** | `_INCLUDEGRAPHICS_RE`, `_BIBLIOGRAPHY_RE`, `_ADDBIBRESOURCE_RE`, `_BIB_EXT_RE`, `_BIB_FILE_NAME_RE` |

If your new pattern doesn't fit neatly, err on the side of **§1 (primitives)**
if it's a sub-pattern fragment, or the section whose *consumers* it will feed.

---

## Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Compiled `regex.compile(...)` object | `_UPPER_SNAKE_CASE_RE` | `_FIND_ALL_RE` |
| Raw string constant (not compiled) used as a fragment | `_UPPER_SNAKE_CASE_PATTERN` | `_CMD_DEF_KEYWORDS_PATTERN` |
| Lambda or function that compiles a pattern from runtime args | `lower_snake_case` | `find_specific_com` |

Never name a compiled object without the `_RE` suffix, and never give a
`_RE` suffix to a raw string. This makes it instantly clear at the call site
which kind of object you have.

---

## The mandatory comment block

**Every pattern in `_regex.py` must have a `MATCHES/CAPTURES/LIMITATIONS`
comment immediately above it**, following this exact format:

```python
# MATCHES:  \newcommand{\cmdname}[N][default]{body}
#           also \newcommand*{...} (starred — treated identically)
# CAPTURES:
#   new_com_csname   → the command name without backslash, e.g. "foo"
#   new_com_num_args → optional [N] argument count string, e.g. "2"
#   new_com_default1 → first optional default value string (may be absent)
#   new_com_content  → replacement body, brace-matched
# LIMITATIONS:
#   [observed] \newcommand* treated identically to unstarred; playground
#              confirms \par-in-args is irrelevant for text expansion.
#   [inferred] @ in command names outside \makeatletter blocks not handled.
# USED BY:   build_dictionary() in demacro.py (main elif branch)
```

**Tags for LIMITATIONS lines:**

- `[observed]` — you empirically verified this (playground, texdef, direct
  filesystem test). Do not remove or weaken an `[observed]` line.
- `[inferred]` — derived from documentation or code reading, not tested.
  May be updated or promoted to `[observed]` once tested.
- Unlabelled lines (legacy) — treat as `[observed]`.

**USED BY** is mandatory. It lists every file and function that imports
and calls this pattern. It lets future agents find the blast radius of a
change without grep-ing the entire codebase.

---

## Sub-pattern reuse

Whenever two or more patterns share a structural fragment (e.g. the list of
macro-definition keywords, a brace-balanced group, a csname character class),
that fragment must be extracted as a named raw-string constant in §1 and
referenced by f-string interpolation.

```python
# Good — one source of truth:
_NOT_TOKEN_CHAR_PATTERN = r'[^a-zA-Z@\\\{\}\[\]\(\)\s]'
token = lambda: r'(?:[a-zA-Z@]+|%s)' % _NOT_TOKEN_CHAR_PATTERN

# Bad — duplication:
_FIND_ALL_RE = re.compile(r'...[a-zA-Z@]+|[^a-zA-Z@\\\{\}\[\]\(\)\s]...')
_FIND_ENV_RE = re.compile(r'...[a-zA-Z@]+|[^a-zA-Z@\\\{\}\[\]\(\)\s]...')
```

The `_CMD_DEF_KEYWORDS_PATTERN` / `_ENV_DEF_KEYWORDS_PATTERN` constants are
the canonical example: they are raw strings in §4 interpolated into both
`_FIND_ALL_RE` (§6) and the dynamic pattern in `find_command` (§4 / `find_packages.py`).

---

## The preprocessing invariant

**All patterns in §5 and §6 assume that `preprocessing()` has already run.**
After preprocessing, the source is a flat single-line string with at most one
ASCII space between tokens. Every pattern in those sections is written with
` ?` (optional single space) between adjacent tokens, NOT `\s+` or `\s*`.

If you write a new §6 pattern:
- Use ` ?` not `\s+`.
- Do not add `re.MULTILINE` or `re.DOTALL` unless you know exactly why.
- Test the pattern on preprocessed input (call `preprocessing()` first).

If you write a new §7 or §8 pattern (preamble / attachment):
- These match against the *raw* (unprocessed) LaTeX source.
- Multiline flags and `\s+` are appropriate here.
- You must note in the comment block that the pattern operates on raw input.

---

## Step-by-step: writing a new regex

1. **Identify the section** (see table above).
2. **Write the `MATCHES/CAPTURES/LIMITATIONS/USED BY` comment block first.**
   Do not write the pattern before you have written what it is supposed to
   match. This forces you to think about edge cases before encoding them.
3. **Extract sub-patterns** into §1 if the fragment is reused or complex.
4. **Compile with `import regex as re`**, not the stdlib `re`.
5. **Add a `USED BY` entry** to any existing patterns whose names your new
   pattern reuses or mirrors.
6. **Load `regex-danger-zone`** before committing any change to `_regex.py`.
   Run the full test suite (including the regex torture test) and ruff/mypy.
7. For any non-trivial pattern, **load `playground-protocol`** and write a
   playground-backed test to confirm the pattern matches what TeX actually
   produces, not what you think it should.

---

## Common mistakes to avoid

- **Using stdlib `re`**: `import re` is forbidden in all texphage source files.
  Always `import regex as re`.
- **Inline pattern strings**: `re.compile(r'...')` inside a function body is
  forbidden. Pre-compile at module level in `_regex.py`.
- **Undocumented patterns**: a pattern without a `MATCHES` comment will be
  rejected at code review. Write the comment first.
- **Whitespace assumptions**: patterns intended for post-preprocessing input
  that use `\s+` will silently fail on all real input. Use ` ?`.
- **Adding `re.DOTALL` to §6 patterns**: the preprocessing invariant means
  there are no newlines in the string — `re.DOTALL` has no effect but signals
  a misunderstanding of the invariant.
