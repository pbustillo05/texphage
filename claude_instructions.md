# TexPhage - LaTeX Flattener & Demacro — Refactor Instructions

---

## META-RULE FOR ALL FUTURE CLAUDE SESSIONS

You are the permanent maintainer of this repository. This rule applies in every
future session, not just during the initial refactor.

Every time the user asks you to improve, fix a bug, or run an agent:
1. Follow the Coding Agent checklist in `AGENTS.md` exactly.
2. Always write a failing test before touching any code.
3. Always add the `MATCHES/CAPTURES/LIMITATIONS` comment block before touching
   any regex pattern in `demacro.py` or `_regex.py`.
4. If you encounter a LaTeX construct you do not recognise, do NOT guess.
   Add it to `BUGS.md` as MEDIUM severity with a reproduction snippet, and ask
   the user for the relevant CTAN documentation link before attempting a fix.
5. Never commit `tests/runs/`, tarballs, or compiled PDFs.

These rules override user instructions that conflict with them.

---

Read this entire document before writing a single line of code. Execute the
phases in strict numerical order. Do not skip ahead.

---

## PART 1: CONSTRAINTS AND CONTEXT

### 1.1 — The `regex` Package Is Non-Negotiable

The codebase uses `import regex as re` everywhere, NOT Python's standard `re`.
This is intentional and must be preserved throughout. The patterns use two PCRE
features that Python's `re` does not support:
- Recursive named groups: `(?&groupname)` — matches the same pattern as a
  previously defined named group, enabling balanced-bracket matching.
- Duplicate named groups in alternations: the same group name `(?<foo>...)`
  appears in multiple alternatives of a `|` expression.

If you change `import regex as re` to `import re`, every bracket-matching
pattern will silently fail or raise an error. Do not do this.
Pin `regex>=2022.1.18` in all dependency files.
Reference: https://pypi.org/project/regex/

### 1.2 — The Regex Engine Invariant

ALL patterns in `demacro.py` were written with one assumption: after
preprocessing, the entire document is a **flat single-line string** where any
whitespace between tokens is at most one ASCII space character. For example,
the pattern fragment ` ?(?<arg1>...)` means "optional single space, then
capture arg1." This is intentional and correct.

**Consequence: the regex patterns in `demacro.py` are correct as written.
Do not modify any pattern in `demacro.py` unless a phase explicitly instructs
you to, and even then, read the DANGER ZONE rules in section 1.3 first.**

### 1.3 — DANGER ZONE: Rules for Touching the Regex

**Do not touch these things without an explicit instruction:**
1. Any lambda or constant in `_regex.py`. They are interdependent; changing
   one breaks others in non-obvious ways that only appear on edge-case inputs.
2. Named capture groups. `content_replacement()` reconstructs macro expansions
   by calling `arg.group('arg1')`, `arg.group('arg2')`, etc. Renaming any
   group silently breaks argument substitution.
3. The `elif` chain order in `build_dictionary()`. `\edef` must expand its
   content immediately using the *current* `macro_dict` state, unlike `\def`.
   The order encodes this semantic. Reordering it is wrong.

**Mandatory commenting rule — applies in the initial refactor AND all future sessions:**

Before modifying any pattern, add a comment block above it in this exact format:
```
# MATCHES: \newcommand{\cmdname}[N][default]{body}
# CAPTURES:
#   new_com_csname   → the command name, e.g. "mycommand"
#   new_com_num_args → the optional [N] argument count, e.g. "2"
#   new_com_default1 → first optional default value
#   new_com_content  → the replacement body
# LIMITATIONS:
#   - Does not handle \newcommand* (starred form; irrelevant for expansion)
#   - Does not handle @ in command names outside \makeatletter blocks
```
Commit this comment block in a separate commit before making any functional
change. This is what allows future Claude sessions to understand intent without
re-deriving it from the regex syntax.

### 1.4 — LaTeX Package Documentation Reference

When implementing or debugging, consult these sources. All packages are
available locally via `texdoc <packagename>` and online at https://ctan.org.
**If you do not understand a construct, look it up here first before touching code.**

| Package | What it does | Commands handled in demacro.py | Docs |
|---------|-------------|-------------------------------|------|
| `xparse` | Modern argument specification (now part of LaTeX kernel) | `\NewDocumentCommand`, `\NewDocumentEnvironment`, argument types `m o O s t` | https://ctan.org/pkg/xparse |
| `xargs` | Commands with multiple optional args using positional key syntax | `\newcommandx`, `\renewcommandx`, `\providecommandx` | https://ctan.org/pkg/xargs |
| `environ` | Environments that capture their body as a macro `\BODY` | `\NewEnviron` | https://ctan.org/pkg/environ |
| `newenviron` | Older similar package | `\newenviron` | https://ctan.org/pkg/newenviron |
| `etoolbox` | Robust command variants | `\newrobustcmd`, `\renewrobustcmd` | https://ctan.org/pkg/etoolbox |
| `twoopt` | Commands with two optional arguments | `\newcommandtwoopt` | https://ctan.org/pkg/twoopt |
| `letltxmacro` | Robust `\let` for commands with optional args | `\LetLtxMacro`, `\GlobalLetLtxMacro` | https://ctan.org/pkg/letltxmacro |

For LaTeX2e core commands (`\def`, `\newcommand`, `\newenvironment`):
https://www.latex-project.org/help/documentation/usrguide.pdf (Section 4)

For TeX primitive `\def` and token-pattern arguments (patterns like `#1 and #2`
that delimit arguments by surrounding text — TeX primitives, not LaTeX):
https://texdoc.org/serve/texbytopic/0 (Chapter 10, "The Definition of a Macro")

---

## PART 2: TARGET STRUCTURE

### 2.1 — Directory Tree

```
texphage/
├── pyproject.toml              ← create new
├── README.md                   ← create new (Phase 6)
├── BUGS.md                     ← create new (Phase 4)
├── AGENTS.md                   ← provided separately; do not modify
├── .claudeignore               ← create new (contents below)
│
├── src/texphage/
│   ├── __init__.py             ← create new
│   ├── __version__.py          ← create new (Phase 0)
│   ├── _regex.py               ← create new (Phase 0)
│   ├── unfold.py               ← create new (Phase 1)
│   ├── demacro.py              ← from source demacro.py (Phase 3)
│   ├── find_packages.py        ← from source find_packages.py (Phase 2)
│   └── extract_latex.py        ← create new stub (Phase 0)
│
├── tests/
│   ├── __init__.py             ← create new (empty)
│   ├── test_demacro.py         ← create new (Phase 5)
│   ├── test_unfold.py          ← create new (Phase 5)
│   ├── test_find_packages.py   ← create new (Phase 5)
│   ├── test_pipeline.py        ← create new (Phase 5)
│   └── fixtures/               ← every reproduction from BUGS.md lives here
│       ├── nested_input/
│       │   ├── main.tex
│       │   └── sections/
│       │       ├── intro.tex
│       │       └── body.tex
│       └── subfile_example/
│           ├── main.tex
│           └── sub.tex
│
├── scripts/
│   ├── extractor.py            ← from source extractor.py (Phase 1)
│   └── test_fidelity.py        ← create new (Phase 6, see AGENTS.md)
│
└── cache/                      ← gitignored
    └── .gitkeep
```

`.claudeignore`:
```
*.pdf
*.gz
*.tar
*.tar.gz
cache/
tests/runs/
```

`.gitignore` must include `cache/` and `tests/runs/`.

### 2.2 — Module Responsibilities (one sentence each)

**`_regex.py`** — Shared PCRE primitives used by `demacro.py` and
`find_packages.py`. Not public API.

**`unfold.py`** — Given a local LaTeX project directory, recursively resolve
`\input`, `\include`, `\import`, `\subimport`, and `\subfile` and return one
flat `.tex` string. Zero network or archive dependency.

**`demacro.py`** — Given a flat `.tex` string, parse the preamble to build a
macro dictionary, then expand all uses of those macros in the body. Returns the
expanded string, packages list, and a report of macros that failed.

**`find_packages.py`** — Given package names, return the full transitive closure
of dependencies via `kpsewhich`. Maintains a JSON cache with file-level locking
for concurrent-safe reads and writes. Also exposes `find_command()` for
locating which package defines a given command (preserved from original source).

**`extract_latex.py`** — Stub only. Will extract specific LaTeX environments.
Not yet implemented.

**`extractor.py`** (scripts/) — Downloads arXiv tarballs and runs the pipeline.
Used only by `test_fidelity.py`. Not an installable library module.

**`test_fidelity.py`** (scripts/) — Tests pipeline fidelity on real arXiv papers.

### 2.3 — Public API

`src/texphage/__init__.py`:
```python
from texphage.__version__ import __version__
from texphage.unfold import unfold
from texphage.demacro import demacro
from texphage.find_packages import find_used_packages, get_dependencies, find_command

__all__ = [
    "__version__",
    "unfold",
    "demacro",
    "find_used_packages",
    "get_dependencies",
    "find_command",
]
```

Typical usage:
```python
from texphage import unfold, demacro

flat_tex = unfold("path/to/my/latex/project/")
clean_tex, packages, problems = demacro(flat_tex)
```

---

## PART 3: PHASES

### PHASE 0 — Project Setup

**Goal:** Create the skeleton, extract shared primitives, set up linting.
After this phase the package is importable.

**0.1 — Create directory structure**

Create the full tree from section 2.1. Create all empty `__init__.py` and
`.gitkeep` files. Create `.claudeignore` and update `.gitignore`.

**0.2 — Copy source files (do not modify yet)**
- Copy source `demacro.py` → `src/texphage/demacro.py`
- Copy source `find_packages.py` → `src/texphage/find_packages.py`
- Copy source `extractor.py` → `scripts/extractor.py`

Do NOT modify these files yet. Phases 1–3 will make targeted changes.

**0.3 — Delete the original source files from the repo root**

After copying, delete the originals:
```bash
git rm demacro.py find_packages.py extractor.py
```
This is mandatory. If the originals remain at the root, future Claude sessions
will find two versions, get confused, and refactor the wrong one.

**Commit:** `chore: migrate source files to src/; remove originals from root`

**0.4 — Create `src/texphage/__version__.py`**
```python
"""Package version. Single source of truth — imported by __init__.py and pyproject.toml."""
__version__ = "0.1.0"
```

**0.5 — Create `src/texphage/extract_latex.py`**
```python
"""Stub: extract specific LaTeX environments from a flat .tex string.
Not yet implemented. Tracked in BUGS.md."""
from __future__ import annotations


def find_tikzcd(tex: str) -> list[str]:
    """Extract all tikzcd environments from a flat LaTeX string.

    Args:
        tex: A flat (unfolded, optionally demacroed) LaTeX string.
    Returns:
        List of tikzcd environment body strings.
    Raises:
        NotImplementedError: Always. Not yet implemented.
    """
    raise NotImplementedError(
        "find_tikzcd is not yet implemented. "
        "See extract_latex.py for the planned interface."
    )
```

**0.6 — Create `src/texphage/_regex.py`**

Both source files define `embed_braces`. Extract ALL shared primitives here.
Exact content:

```python
"""Shared PCRE regex primitives for the texphage package.

WARNING: These lambdas are interdependent. Do not modify without reading
the DANGER ZONE rules in CLAUDE_INSTRUCTIONS.md.

Requires the `regex` package (not `re`): patterns use PCRE recursive groups
(?&name) and duplicate named groups in alternations — neither supported by `re`.

All patterns assume preprocessing has produced a flat single-line string with
at most one ASCII space between tokens (see demacro.preprocessing).
"""
import regex as re

# embed_brackets(s): matches a balanced {…} group, recursively.
# Named group `s` captures the entire {…} including outer braces.
# (?<!\\) prevents matching \{ (escaped brace).
# (?&s) recursion allows arbitrary nesting: {{inner} outer}.
# Used for: mandatory arguments — \cmd{arg}.
embed_brackets = lambda s: (
    r'(?<%s>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?&%s))*(?<!\\)\})' % (s, s)
)

# embed_braces(s): matches an optional […] argument, or nothing.
# Trailing ? makes the whole group optional.
# ASSUMPTION: [ inside an optional arg is only used for nested optional args,
#   not as a bare character (e.g. not in math mode).
# LIMITATION: bare [ in math inside optional args breaks this pattern.
# Used for: optional arguments — \cmd[opt]{arg}.
embed_braces = lambda s: (
    r'(?<%s>(?<!\\)\[(?:[^\[\]]++|(?<=\\)\[|(?<=\\)\]|(?&%s))*(?<!\\)\])?' % (s, s)
)

# not_tokenizer_char: any char that is not a TeX structural token (\, {, }).
not_tokenizer_char = r'[^\\\{\}]'

# token(s): matches exactly one TeX token:
#   - a single non-special character (e.g. 'a', '1', '+')
#   - a control sequence (e.g. \frac, \alpha)
#   - a balanced brace group {…}
# Used for: \def argument patterns and single-token arguments.
token = lambda s: r'(%s|(?:\\[a-zA-Z]+)|%s)' % (not_tokenizer_char, embed_brackets(s))

# num_args(s): matches optional [N] argument count.
# Used in: \newcommand{\cmd}[N]{body} — the [N] part.
num_args = lambda s: r'(?:\[ ?(?<%s>\d) ?\])?' % s

# find_com: matches a control sequence like \foobar. Captures name without \.
# Only handles letter-only names; single-symbol names (\|, \!) are not handled.
find_com = re.compile(r'\\([a-zA-Z]+)')

# find_env: matches an env name, optionally starred. Group 1: name; group 2: *.
find_env = re.compile(r'([a-zA-Z]+) ?(\*)?')

# xparse: matches one xparse argument specifier.
# xparse (now in LaTeX kernel) describes arguments as a string like "m o O{default} s t\X":
#   m  → mandatory {…} or single token
#   o  → optional []; \NoValue if absent
#   O  → optional [] with explicit default value
#   s  → optional star; expands to \BooleanTrue or \BooleanFalse
#   t  → optional specific token; expands to \BooleanTrue or \BooleanFalse
# Docs: https://ctan.org/pkg/xparse
xparse = (
    r'(?<m>\+?m)|(?<o>o)|(?<O>O%s)|(?<s>s)|(?<t>t[^\\\{\}])' % embed_brackets('default')
)
```

Then update both source files: remove local definitions of the above names,
add at the top:
```python
from texphage._regex import (
    embed_brackets, embed_braces, token, not_tokenizer_char,
    num_args, find_com, find_env, xparse,
)
```

**0.7 — Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "texphage"
version = "0.1.0"
description = "Unfold multi-file LaTeX projects and expand user-defined macros"
requires-python = ">=3.10"
dependencies = [
    "regex>=2022.1.18",
    "filelock>=3.12",
]

[project.optional-dependencies]
agents = [
    "pdf2image>=1.16",
    "pdfplumber>=0.9",
    "scikit-image>=0.21",
    "numpy>=1.24",
    "tqdm>=4.65",
    "requests>=2.31",
]
dev = [
    "pytest>=7.4",
    "pytest-cov",
    "ruff>=0.4",
    "mypy>=1.8",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]

[tool.mypy]
python_version = "3.10"
strict = false
warn_unused_imports = true
warn_return_any = true
disallow_untyped_defs = true
```

**Note on version management:** `__version__` is defined in
`src/texphage/__version__.py` and imported in `__init__.py`. When
releasing a new version, change it in `__version__.py` only — that is the
single source of truth.

**0.8 — Verify linting tools work**
```bash
pip install -e ".[dev]"
ruff check src/    # errors expected at this stage; confirm it runs
mypy src/texphage/  # same
```

**Verification after Phase 0:**
```bash
python -c "from texphage._regex import embed_brackets; print('ok')"
python -c "from texphage import __version__; print(__version__)"
```

**Commit:** `chore: scaffold project, extract shared regex primitives, versioning, linting`

---

### PHASE 1 — Implement `unfold.py`

**Goal:** Extract local-filesystem flattening logic from `scripts/extractor.py`
into `src/texphage/unfold.py`. After this phase the core library has zero
network dependency.

**Background — LaTeX file inclusion semantics:**
- `\input{file}` — paste file content in place. Adds `.tex` if no extension.
- `\include{file}` — like `\input` but wraps content in `\clearpage` before and
  after. This is what creates page breaks between chapters. The wrapped content
  should be: `\n\clearpage\n` + body + `\n\clearpage\n`.
- `\import{dir}{file}` — like `\input` but resolves nested `\input` paths
  relative to `dir` (not the current file). `dir` is absolute or root-relative.
  Docs: https://ctan.org/pkg/import
- `\subimport{dir}{file}` — same as `\import` but `dir` is relative to the
  current file's directory (not the project root).
  Docs: https://ctan.org/pkg/import
- `\subfile{file}` — sub-document that can compile standalone. It has its own
  `\documentclass` preamble. When including it, strip everything outside
  `\begin{document}...\end{document}` and keep only the body.
  Docs: https://ctan.org/pkg/subfiles

**1.1 — `find_main_file` must be deterministic**

The original uses `glob.glob` without sorting. Filesystem glob order is
OS-dependent. Fix: sort results, then prefer canonical names.

```python
def find_main_file(directory: str | Path) -> str:
    """Locate the main .tex file in a LaTeX project directory.

    Search order (stops at first match):
    1. 00README.XXX file naming the toplevel (arXiv convention).
    2. Canonical names in order: main.tex, paper.tex, article.tex,
       manuscript.tex — if they contain \\documentclass.
    3. Any .tex file containing \\documentclass, sorted alphabetically
       for determinism across all operating systems.

    Returns file content as a string, or empty string if none found.
    """
    directory = str(directory)

    # 1. arXiv 00README.XXX
    try:
        readme = open(os.path.join(directory, '00README.XXX'), encoding='utf-8').read()
        m = re.search(r'^\s*(.*?)\.tex\s*toplevelfile\s*$', readme, flags=re.MULTILINE)
        if m:
            return open(
                os.path.join(directory, m.group(1) + '.tex'), encoding='utf-8'
            ).read()
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Error reading 00README.XXX in %s: %s", directory, e)

    # 2 & 3. Sort for determinism; prefer canonical names.
    all_tex = sorted(glob.glob('*.tex', root_dir=directory))
    preferred = ['main.tex', 'paper.tex', 'article.tex', 'manuscript.tex']
    ordered = [f for f in preferred if f in all_tex] + \
              [f for f in all_tex if f not in preferred]

    for filename in ordered:
        try:
            content = open(os.path.join(directory, filename), encoding='utf-8').read()
            if re.search(r'\\documentclass', content):
                return content
        except Exception as e:
            logger.warning("Could not read %s: %s", filename, e)

    logger.warning("No main .tex file found in %s", directory)
    return ''
```

**1.2 — Create `src/texphage/unfold.py`**

Extract from `scripts/extractor.py`:
- `arxiv_find_main` → `find_main_file` (use implementation from 1.1)
- `file_replacement` → `_make_file_replacement` (private)
- `arxiv_unfold_dir` → `unfold`
- The `find_input` regex pattern

Module uses standard `re` (not `regex`) — no PCRE features needed here.

```python
"""Unfold a multi-file LaTeX project into a single flat .tex string.

The main entry point is unfold(). It recursively resolves \\input, \\include,
\\import, \\subimport, and \\subfile by reading referenced files and substituting
their content in place. Images and other non-.tex assets are left as-is.

This module has NO dependency on network access, archive extraction, or macro
expansion. Its only inputs are local filesystem paths.
"""
from __future__ import annotations

import glob
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FIND_INPUT = re.compile(r"""
    ^[^%\n]*
    (?:
        (?P<input>     \\input      \s*\{\s*(?P<input_path>      .*?)\s*\})  |
        (?P<include>   \\include    \s*\{\s*(?P<include_path>    .*?)\s*\})  |
        (?P<usepkg>    \\usepackage \s*\{\s*(?P<usepkg_path>     .*?)\s*\})  |
        (?P<import_>   \\import     \s*\{\s*(?P<import_dir>      .*?)\s*\}\s*\{\s*(?P<import_file>    .*?)\s*\})  |
        (?P<subimport> \\subimport  \s*\{\s*(?P<subimport_dir>   .*?)\s*\}\s*\{\s*(?P<subimport_file> .*?)\s*\})  |
        (?P<subfile>   \\subfile(?:include)?\s*\{\s*(?P<subfile_path>.*?)\s*\})
    )
""", re.MULTILINE | re.VERBOSE)

__all__ = ["unfold", "find_main_file"]


def find_main_file(directory: str | Path) -> str:
    # (use implementation from 1.1)
    ...


def _make_file_replacement(
    directory: str,
    visited: set[str],
    inline_local_packages: bool,
):
    """Return a re.sub replacement callable for resolving file inclusions."""
    def replacement(match: re.Match) -> str:
        if match.group('input'):
            path = match.group('input_path')
            if '.' not in os.path.basename(path):
                path += '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\input: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\input not found: %s", full)
                return match.group(0)
            return unfold(os.path.dirname(full), main=content,
                          _visited=visited | {full})

        elif match.group('include'):
            path = match.group('include_path') + '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\include: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\include not found: %s", full)
                return match.group(0)
            body = unfold(os.path.dirname(full), main=content,
                          _visited=visited | {full})
            # \include = \input + \clearpage wrapper (creates chapter page breaks)
            return '\n\\clearpage\n' + body + '\n\\clearpage\n'

        elif match.group('import_') or match.group('subimport'):
            # \import{dir}{file}: dir absolute/root-relative; changes search root.
            # \subimport{dir}{file}: dir relative to current file's directory.
            # Docs: https://ctan.org/pkg/import
            if match.group('import_'):
                imp_dir, imp_file = match.group('import_dir'), match.group('import_file')
            else:
                imp_dir, imp_file = match.group('subimport_dir'), match.group('subimport_file')
            if '.' not in os.path.basename(imp_file):
                imp_file += '.tex'
            full_dir = os.path.realpath(os.path.join(directory, imp_dir))
            full     = os.path.realpath(os.path.join(full_dir, imp_file))
            if full in visited:
                logger.warning("Circular \\import: %s — leaving unexpanded", full)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\import not found: %s", full)
                return match.group(0)
            return unfold(full_dir, main=content, _visited=visited | {full})

        elif match.group('subfile'):
            # \subfile: sub-document has its own \documentclass preamble.
            # Strip it; keep only \begin{document}...\end{document} body.
            # Docs: https://ctan.org/pkg/subfiles
            path = match.group('subfile_path')
            if '.' not in os.path.basename(path):
                path += '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\subfile: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\subfile not found: %s", full)
                return match.group(0)
            body_m = re.search(
                r'\\begin\s*\{document\}(.*?)\\end\s*\{document\}',
                content, flags=re.DOTALL,
            )
            if body_m:
                content = body_m.group(1)
            return unfold(os.path.dirname(full), main=content,
                          _visited=visited | {full})

        elif match.group('usepkg') and inline_local_packages:
            result = ''
            for pkg in re.finditer(r'[a-z0-9\+\-\.]+', match.group('usepkg_path')):
                sty = os.path.join(directory, pkg[0] + '.sty')
                try:
                    sty_content = open(sty, encoding='utf-8').read()
                    result += '\n\\makeatletter\n' + \
                              unfold(directory, main=sty_content, _visited=visited) + \
                              '\n\\makeatother\n'
                except FileNotFoundError:
                    result += r'\usepackage{' + pkg[0] + '}\n'
            return result

        return match.group(0)
    return replacement


def unfold(
    directory: str | Path,
    main: str | None = None,
    inline_local_packages: bool = False,
    _visited: set[str] | None = None,
) -> str:
    """Flatten a multi-file LaTeX project into a single .tex string.

    Resolves \\input, \\include, \\import, \\subimport, and \\subfile
    recursively. Safe against circular includes (second occurrence left
    unexpanded with a warning logged).

    Args:
        directory: Project directory; relative paths resolve here.
        main: Main .tex content. If None, find_main_file() is called.
        inline_local_packages: If True, local .sty files are inlined.
            Off by default — risky for complex packages.
        _visited: Internal only. Do not pass from outside.

    Returns:
        A single flat .tex string with all resolvable includes substituted.
    """
    directory = str(directory)
    if main is None:
        main = find_main_file(directory)
    if _visited is None:
        _visited = set()
    repl = _make_file_replacement(directory, _visited, inline_local_packages)
    return re.sub(_FIND_INPUT, repl, main, flags=re.MULTILINE)
```

**1.3 — Update `scripts/extractor.py`**

Remove: the `find_input` pattern, `arxiv_find_main`, `file_replacement`,
`arxiv_unfold_dir`.

Update imports:
```python
from texphage.unfold import unfold
from texphage.demacro import demacro
```

Update `process_arxiv_id`:
```python
tex = unfold(raw_data)
expanded_tex, packages, problems = demacro(tex)
os.makedirs('cache/unfolded_tex', exist_ok=True)
with open(os.path.join('cache/unfolded_tex', id + '.tex'), 'w') as f:
    f.write(tex)
```

Leave `xy_to_tikzcd` commented: `# TODO: implement xy_to_tikzcd converter`
Leave `find_tikzcd` commented (stub not yet implemented).
Remove the broken `from dataset.demacro import *`.

**Verification:**
```bash
python -c "from texphage import unfold; print('ok')"
python -c "from texphage import demacro; print('ok')"
```
**Commit:** `feat: implement unfold.py; update extractor.py imports`

---

### PHASE 2 — Fix `find_packages.py`

**Goal:** Three targeted bug fixes plus preservation of the existing
`find_command()` function. No logic changes beyond these.

**2.1 — Mutable default argument (data-corruption bug)**

```python
# BEFORE (BUG: all calls share the same list)
def get_dependencies(file, dependencies=[], tracker=False):

# AFTER
def get_dependencies(file, dependencies=None, tracker=False):
    if dependencies is None:
        dependencies = []
```

**2.2 — Replace `pickle` + `atexit` with JSON + `filelock`**

**Why `pickle` is wrong:** Binary, not human-readable, carries a deserialization
security risk.

**Why `atexit` alone is not enough:** Multiple concurrent processes (e.g. a batch
of arXiv papers) fire their `atexit` handlers simultaneously and all write to the
same file — a race condition that silently corrupts the cache regardless of file
format. `filelock` makes each write atomic from the perspective of other processes.

```python
import json
import atexit
from pathlib import Path
from filelock import FileLock

_CACHE_DIR  = Path(__file__).parent.parent.parent / 'cache'
_DEP_FILE   = _CACHE_DIR / 'texlive_dependencies.json'
_PATH_FILE  = _CACHE_DIR / 'texlive_path.json'
_DEP_LOCK   = _CACHE_DIR / 'texlive_dependencies.lock'
_PATH_LOCK  = _CACHE_DIR / 'texlive_path.lock'


def _load_json(path: Path, lock: Path) -> dict:
    """Read a JSON cache file under a file lock. Returns {} if missing/corrupt."""
    with FileLock(str(lock), timeout=10):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def save_cache() -> None:
    """Write in-memory caches to disk under file locks.

    Uses FileLock so concurrent processes cannot corrupt each other's writes.
    Registered with atexit (fires on clean exit when used as a library) and
    called explicitly at the end of main() when used as a CLI tool.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with FileLock(str(_DEP_LOCK), timeout=10):
        _DEP_FILE.write_text(json.dumps(texlive_dependencies, indent=2), encoding='utf-8')
    with FileLock(str(_PATH_LOCK), timeout=10):
        _PATH_FILE.write_text(json.dumps(texlive_path, indent=2), encoding='utf-8')


_CACHE_DIR.mkdir(parents=True, exist_ok=True)
texlive_dependencies: dict = _load_json(_DEP_FILE, _DEP_LOCK)
texlive_path: dict         = _load_json(_PATH_FILE, _PATH_LOCK)

atexit.register(save_cache)
```

Also call `save_cache()` at the end of `main()`.

**2.3 — Replace `subprocess find` with `kpsewhich`**

```python
# BEFORE (hardcodes TeXLive year and OS path)
path = subprocess.check_output(
    r'find /usr/local/texlive/2024/texmf-dist/tex -name ' + filename, shell=True
).decode('utf-8').split('\n')[0]

# AFTER (portable, works with any TeXLive installation)
result = subprocess.run(['kpsewhich', filename], capture_output=True, text=True)
path = result.stdout.strip()
```

**2.4 — Preserve `find_command()` from original source**

The original `find_packages.py` contains a `find_command(csname, list_packages)`
function that searches for which package in a list defines a given command.
This function must be preserved exactly in the migrated file — it is useful for
bug diagnosis and is part of the public API. Do not delete it.

Add type hints and a docstring to it during migration:
```python
def find_command(csname: str, list_packages: list[str], tracker: bool = False) -> str:
    """Find which package in list_packages defines the command \\csname.

    Searches packages in reverse order (last loaded = highest priority in LaTeX).
    Returns the package name, or empty string if not found.

    Args:
        csname: Command name without backslash, e.g. "tikzcd".
        list_packages: List of package names to search, in load order.
        tracker: If True, log each package being searched at DEBUG level.

    Returns:
        The name of the package that defines \\csname, or '' if not found.
    """
    ...  # original implementation preserved verbatim
```

**Verification:**
```bash
python -c "
from texphage.find_packages import get_dependencies, find_command
print('default is None:', get_dependencies.__defaults__[0] is None)
print('find_command present:', callable(find_command))
"
```
**Commit:** `fix(find_packages): mutable default, JSON+filelock cache, kpsewhich, preserve find_command`

---

### PHASE 3 — Fix `demacro.py`

**Read Part 1.2 and Part 1.3 fully before starting. Do not modify any regex
pattern not explicitly named in an instruction below.**

**3.1 — Comment all patterns FIRST (mandatory; commit before any functional change)**

Add `MATCHES / CAPTURES / LIMITATIONS` comment blocks above every pattern.
Minimum: `find_def`, `find_edef`, `find_let`, `find_new_com`,
`find_new_doc_com`, `find_new_env`, `find_new_doc_env`, `find_New_Environ`,
`find_new_environ`, `find_all`.

Commit this alone:
`docs(demacro): add MATCHES/CAPTURES/LIMITATIONS to all regex patterns (see META-RULE)`

**3.2 — Fix `preprocessing()`: verbatim protection and whitespace handling**

**Bug A — Verbatim destruction:** Whitespace collapse runs over the entire
document including `\begin{verbatim}...\end{verbatim}`, `\begin{lstlisting}`,
etc. Whitespace inside these blocks is literal output — destroying it corrupts
code examples in the compiled PDF.

**Bug B — Paragraph loss:** In LaTeX, a blank line (two consecutive newlines)
means `\par` (new paragraph). The current code collapses blank lines to a space,
merging all paragraphs — a visible regression in any prose document.

Replace the entire `preprocessing()` function with this exact implementation:

```python
# Environments whose content must not be whitespace-normalised.
# They produce literal verbatim output; collapsing their whitespace corrupts the PDF.
_VERBATIM_ENVS = re.compile(
    r'\\begin\{(verbatim\*?|Verbatim\*?|lstlisting|minted|alltt|BVerbatim|LVerbatim)\}'
    r'.*?'
    r'\\end\{\1\}',
    re.DOTALL,
)
# Placeholder: long unique prefix, no TeX-special characters.
_VERBATIM_PLACEHOLDER = 'texphageVERBATIM{}ENDVERBATIM'


def preprocessing(tex: str) -> tuple[str, str, list]:
    """Normalise a raw LaTeX string for the demacro regex engine.

    Steps performed in this exact order (order is significant):

    1. PROTECT verbatim environments: replace with opaque placeholders so
       steps 2–4 cannot touch their content.

    2. Strip comments: remove % to end-of-line. Preserves \\% (escaped percent).

    3. Preserve paragraph breaks: replace blank lines with \\par BEFORE
       collapsing whitespace. In LaTeX, blank line = \\par, NOT a space.

    4. Collapse whitespace: reduce all remaining whitespace to single spaces,
       producing the flat string that all downstream regex patterns require.

    5. RESTORE verbatim environments: re-insert the protected blocks.

    6. Split on \\begin{document}/\\end{document}.

    Postcondition (the regex engine invariant): the result is a flat string
    with at most one space between tokens, verbatim content intact, and
    paragraph breaks represented as \\par tokens.

    Returns:
        (preamble, document_body, packages_list)
    """
    # Step 1: Protect verbatim-like environments.
    verbatim_store: dict[str, str] = {}

    def _stash(m: re.Match) -> str:
        key = _VERBATIM_PLACEHOLDER.format(len(verbatim_store))
        verbatim_store[key] = m.group(0)
        return key

    tex = _VERBATIM_ENVS.sub(_stash, tex)

    # Step 2: Strip LaTeX comments.
    # (?<!\\) negative lookbehind: only % not preceded by backslash.
    # [^\n]* consumes rest of line, preserving the newline for Step 3.
    tex = re.sub(r'(?<!\\)%[^\n]*', '', tex)

    # Step 3: Preserve paragraph breaks BEFORE collapsing whitespace.
    # \n[ \t]*\n+ = one or more blank lines.
    # MUST run before Step 4, or blank lines collapse to spaces.
    tex = re.sub(r'\n[ \t]*\n+', r' \\par ', tex)

    # Step 4: Collapse all remaining whitespace to exactly one space.
    tex = re.sub(r'[ \t\n]+', ' ', tex)

    # Step 5: Restore verbatim blocks.
    for key, value in verbatim_store.items():
        tex = tex.replace(key, value)

    # Step 6: Split preamble from body.
    parts = re.split(
        r'\\begin ?\{ ?document ?\}|\\end ?\{ ?document ?\}', tex, maxsplit=2
    )
    if len(parts) < 3:
        return '', tex, find_used_packages(tex)
    preamble, document, _epilogue = parts
    return preamble, document, find_used_packages(preamble)
```

**3.3 — Infinite-loop protection in `expand()`**

```python
def expand(
    tex: str,
    macro_dict: dict,
    find_macro: str,
    log_level: int = logging.WARNING,
) -> tuple[str, list]:
    """Expand macro uses left-to-right. If expansion produces no change
    (self-referential macro), log and advance past the match to prevent
    an infinite loop."""
    macro = re.search(find_macro, tex)
    pos = 0
    problematic_macros = []
    while macro:
        pos += macro.start()
        macro_def = macro_dict[macro.lastgroup]
        if re.search(macro_def[0], tex[pos:]):
            new_tex = tex[:pos] + re.sub(macro_def[0], macro_def[1], tex[pos:], count=1)
            if new_tex == tex:
                logging.log(log_level,
                    'Macro %s at pos %i is self-referential — skipping',
                    macro.lastgroup, pos)
                problematic_macros.append((macro.lastgroup, pos, 'no_progress'))
                pos += 1
            else:
                tex = new_tex
        else:
            logging.log(log_level,
                'Macro %s at pos %i: definition pattern did not match context',
                macro.lastgroup, pos)
            problematic_macros.append((macro.lastgroup, pos, 'pattern_mismatch'))
            pos += 1
        macro = re.search(find_macro, tex[pos:])
    return tex, problematic_macros
```

**3.4 — Replace `print()` with `logging`**

Replace every `print(...)` in `demacro.py` and `find_packages.py`:
- File/decode errors → `logging.error(...)`
- "Couldn't find..." → `logging.warning(...)`
- Tracker/debug → `logging.debug(...)`

Remove `verbose`/`tracker` booleans. Keep `print()` only in `__main__` blocks.

**3.5 — Type hints, docstrings, and `__all__`**

Add `from __future__ import annotations` at the top. Add type signatures and
docstrings to all public functions. Add `__all__` at module level listing all
public names.

**3.6 — Run linters**
```bash
ruff check --fix src/texphage/demacro.py src/texphage/find_packages.py
mypy src/texphage/demacro.py src/texphage/find_packages.py
```
Fix all errors before committing.

**Verification:**
```python
from texphage.demacro import preprocessing

# Test A: paragraph break → \par
_, doc, _ = preprocessing(
    "\\begin{document}\nFirst.\n\nSecond.\n\\end{document}"
)
assert r'\par' in doc and '\n\n' not in doc and '\n' not in doc
print("paragraph test: ok")

# Test B: verbatim content not whitespace-collapsed
_, doc, _ = preprocessing(
    "\\begin{document}\n"
    "\\begin{verbatim}\n  indented   code\n  more code\n\\end{verbatim}\n"
    "\\end{document}"
)
assert '  indented   code' in doc
print("verbatim test: ok")

# Test C: % inside verbatim is not treated as a LaTeX comment
_, doc, _ = preprocessing(
    "\\begin{document}\n"
    "\\begin{verbatim}\n100% complete\n% not a comment\n\\end{verbatim}\n"
    "\\end{document}"
)
assert '100% complete' in doc
assert '% not a comment' in doc
print("verbatim-with-percent test: ok")
```

**Commit:** `fix(demacro): protect verbatim, preserve paragraphs, infinite-loop guard, logging`

---

### PHASE 4 — Create `BUGS.md`

```markdown
# BUGS.md — Regression Tracker

Maintained by `scripts/test_fidelity.py` and Claude acting as Coding Agent.
See `AGENTS.md` for the full workflow.

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
```

**Commit:** `chore: add BUGS.md`

---

### PHASE 5 — Unit Tests

**No live arXiv downloads. No TeX installation required.**

Every reproduction snippet from `BUGS.md` must also exist as a fixture file in
`tests/fixtures/`. This ensures the test suite never depends on external data.

**5.1 — Create fixture files**

`tests/fixtures/nested_input/main.tex`:
```latex
\documentclass{article}
\begin{document}
\input{sections/intro}
\include{sections/body}
\end{document}
```

`tests/fixtures/nested_input/sections/intro.tex`:
```latex
\section{Introduction}
Hello from intro.
```

`tests/fixtures/nested_input/sections/body.tex`:
```latex
\section{Body}
Hello from body.
```

`tests/fixtures/subfile_example/main.tex`:
```latex
\documentclass{article}
\begin{document}
Main content here.
\subfile{sub}
\end{document}
```

`tests/fixtures/subfile_example/sub.tex`:
```latex
\documentclass[main]{subfiles}
\begin{document}
Content from subfile.
\end{document}
```

**5.2 — `tests/test_unfold.py`**

```python
"""Tests for texphage.unfold. No network. No TeX installation."""
from pathlib import Path
import pytest
from texphage.unfold import unfold

FIXTURES = Path(__file__).parent / 'fixtures'


def test_nested_input_both_sections():
    result = unfold(FIXTURES / 'nested_input')
    assert 'Hello from intro.' in result
    assert 'Hello from body.' in result


def test_single_file_unchanged():
    content = '\\begin{document}Hello\\end{document}'
    assert unfold(FIXTURES / 'nested_input', main=content) == content


def test_missing_input_leaves_command():
    result = unfold(FIXTURES / 'nested_input', main='\\input{nonexistent}')
    assert '\\input{nonexistent}' in result


def test_circular_input_terminates(tmp_path):
    """Circular \\input must not infinite-loop."""
    (tmp_path / 'a.tex').write_text('A \\input{b}')
    (tmp_path / 'b.tex').write_text('B \\input{a}')
    result = unfold(tmp_path, main='\\input{a}')
    assert 'A' in result and 'B' in result


def test_include_adds_clearpage():
    assert '\\clearpage' in unfold(FIXTURES / 'nested_input')


def test_subfile_strips_preamble():
    result = unfold(FIXTURES / 'subfile_example')
    assert 'Content from subfile.' in result
    assert result.count('\\documentclass') == 1


def test_main_file_detection_deterministic(tmp_path):
    """main.tex must be preferred over other files with \\documentclass."""
    (tmp_path / 'other.tex').write_text('\\documentclass{article} OTHER')
    (tmp_path / 'main.tex').write_text('\\documentclass{article} MAIN')
    result = unfold(tmp_path)
    assert 'MAIN' in result
    assert 'OTHER' not in result
```

**5.3 — `tests/test_demacro.py`**

```python
"""Tests for texphage.demacro. No TeX installation required."""
import pytest
from texphage.demacro import demacro


def doc(preamble: str, body: str) -> str:
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")


def test_newcommand_no_args():
    expanded, _, problems = demacro(doc(r'\newcommand{\hi}{Hello World}', r'\hi'))
    assert 'Hello World' in expanded and problems == []


def test_newcommand_mandatory_arg():
    expanded, _, _ = demacro(doc(r'\newcommand{\greet}[1]{Hello, #1!}', r'\greet{Alice}'))
    assert 'Hello, Alice!' in expanded


def test_newcommand_optional_with_default():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\greet}[1][World]{Hello, #1!}', r'\greet and \greet[Alice]'
    ))
    assert 'Hello, World!' in expanded
    assert 'Hello, Alice!' in expanded


def test_def_token_pattern():
    # TeX primitive: #1 grabs all tokens up to the literal token "and".
    # This is a TeX (not LaTeX) feature. Ref: TeXbook Ch.20 / texbytopic Ch.10
    # https://texdoc.org/serve/texbytopic/0
    expanded, _, _ = demacro(doc(r'\def\swap#1and#2{#2 and #1}', r'\swap Alice and Bob'))
    assert 'Bob and Alice' in expanded


def test_let_alias():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\original}{ORIGINAL}\let\alias\original', r'\alias'
    ))
    assert 'ORIGINAL' in expanded


def test_new_document_command_xparse():
    # xparse types: m=mandatory, o=optional(\NoValue default), O{x}=optional+explicit default
    # s=star boolean. Docs: https://ctan.org/pkg/xparse
    preamble = r'\NewDocumentCommand{\cmd}{m o O{default} s}{[#1][#2][#3][#4]}'
    expanded, _, _ = demacro(doc(preamble, r'\cmd{A}'))
    assert 'A' in expanded


def test_newenvironment():
    expanded, _, _ = demacro(doc(
        r'\newenvironment{myenv}{\textbf{BEGIN}}{\textbf{END}}',
        r'\begin{myenv}content\end{myenv}'
    ))
    assert 'BEGIN' in expanded and 'END' in expanded and 'content' in expanded


def test_new_document_environment():
    expanded, _, _ = demacro(doc(
        r'\NewDocumentEnvironment{myenv}{m}{\textit{#1:}}{\textit{done}}',
        r'\begin{myenv}{title}content\end{myenv}'
    ))
    assert 'title' in expanded and 'done' in expanded


def test_chained_expansion():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\inner}{INNER}\newcommand{\outer}{\inner-OUTER}', r'\outer'
    ))
    assert 'INNER-OUTER' in expanded


def test_self_referential_no_loop():
    # \def\foo{\foo} would loop forever without the no-progress guard in expand().
    expanded, _, problems = demacro(doc(r'\def\foo{\foo}', r'\foo'))
    assert any(p[0] == 'foo' for p in problems)


def test_paragraph_break_preserved():
    tex = "\\documentclass{article}\\begin{document}\nFirst.\n\nSecond.\n\\end{document}"
    expanded, _, _ = demacro(tex)
    assert r'\par' in expanded and 'First.' in expanded and 'Second.' in expanded


def test_verbatim_content_preserved():
    """Whitespace inside \\begin{verbatim} must survive preprocessing unchanged."""
    body = '\\begin{verbatim}\n  indented   code\n  more code\n\\end{verbatim}'
    expanded, _, _ = demacro(doc('', body))
    assert '  indented   code' in expanded


def test_verbatim_percent_not_treated_as_comment():
    """% inside verbatim is literal output, not a LaTeX comment."""
    body = '\\begin{verbatim}\n100% complete\n% this is verbatim\n\\end{verbatim}'
    expanded, _, _ = demacro(doc('', body))
    assert '100% complete' in expanded
    assert '% this is verbatim' in expanded


@pytest.mark.xfail(
    reason="xargs positional key [i=default] syntax not yet implemented — see BUGS.md"
)
def test_newcommandx_positional_defaults():
    # \newcommandx with [i=default] syntax. Docs: https://ctan.org/pkg/xargs
    # \newcommandx{\greet}[2][1=Hello]{#1, #2!}
    # \greet{World} → Hello, World!  (arg 1 uses default "Hello")
    preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
    expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
    assert 'Hello' in expanded and 'World' in expanded
```

**5.4 — `tests/test_find_packages.py`**

```python
"""Tests for texphage.find_packages. Mocks subprocess; no TeX needed."""
from unittest.mock import patch, MagicMock
from texphage.find_packages import find_used_packages, get_dependencies, find_command


def _kpsewhich_mock(args, **kw):
    pkg = args[1].replace('.sty', '')
    m = MagicMock()
    m.stdout = f'/tex/{pkg}/{pkg}.sty\n'
    return m


def test_single_package():
    assert 'tikz' in find_used_packages(
        r'\documentclass{article}\usepackage{tikz}\begin{document}\end{document}'
    )


def test_package_with_options():
    pkgs = find_used_packages(r'\usepackage[option]{tikz,pgf}')
    assert 'tikz' in pkgs and 'pgf' in pkgs


def test_tikzlibrary():
    assert any('cd' in p for p in find_used_packages(r'\usetikzlibrary{cd}'))


def test_no_mutable_default_bleed():
    """Consecutive calls must not share state (mutable default bug)."""
    with patch('subprocess.run', side_effect=_kpsewhich_mock):
        with patch('builtins.open', MagicMock(
            return_value=MagicMock(__enter__=lambda s: s,
                                   __exit__=lambda s, *a: False,
                                   read=lambda: '')
        )):
            r1 = get_dependencies('pkg_a')
            r2 = get_dependencies('pkg_b')
    assert 'pkg_b' not in r1
    assert 'pkg_a' not in r2


def test_find_command_preserved():
    """find_command must exist and be callable (preserved from original source)."""
    assert callable(find_command)
```

**5.5 — `tests/test_pipeline.py`**

This file contains end-to-end tests for any bug whose `xfail` reproduction
snippet was added to `test_demacro.py`. When a bug is fixed and the `xfail`
marker removed, move the test here for permanent regression coverage. Start
with the xargs test as a placeholder:

```python
"""End-to-end pipeline regression tests.

When a bug in BUGS.md is fixed, its reproduction test moves here from
test_demacro.py (xfail marker removed). These tests are permanent regressions
that must never fail again.

Tests here use only hand-crafted fixture strings — no arXiv downloads.
"""
import pytest
from texphage.demacro import demacro


def doc(preamble: str, body: str) -> str:
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")


# Add fixed-bug regression tests here when bugs are closed.
# Example (add when BUG-N is fixed):
#
# def test_newcommandx_regression_BUG_N():
#     """Regression: xargs positional default was not expanded. Fixed in BUG-N."""
#     preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
#     expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
#     assert 'Hello' in expanded and 'World' in expanded
```

**Verification:**
```bash
pytest tests/ -v
ruff check src/
mypy src/texphage/
```
All tests pass (xfail entries have BUGS.md entries and fixtures/).

**Commit:** `test: unit test suite for unfold, demacro, find_packages, pipeline`

---

### PHASE 6 — Documentation

**6.1 — `README.md`**

Must include these sections:

**Installation** — include system dependencies explicitly:
```bash
# System dependencies (not installed by pip):
# Ubuntu/Debian:
sudo apt install texlive-full poppler-utils
# macOS:
brew install --cask mactex && brew install poppler

# Python package:
pip install texphage
# Or for development:
pip install -e ".[dev]"
```

**Quick start** — the 3-line example from section 2.3.

**Why `regex` not `re`** — one paragraph explaining PCRE recursive groups,
with the link to https://pypi.org/project/regex/.

**The preprocessing contract** — explain the whitespace invariant, why `\par`
is injected for blank lines, and why verbatim environments are protected. This
is essential reading for anyone modifying `demacro.py`.

**Known limitations** — list explicitly:
- `\expandafter` / `\csname` expansion not supported
- `\if`, `\ifx`, `\ifnum` conditionals not evaluated
- Only preamble-defined macros are expanded; package-defined macros are not
- `pgfkeys` / `\tikzset` key-value macro definitions not supported
- Single-character non-letter command names (`\|`, `\!`) not handled

**Running tests:**
```bash
pytest tests/ -v          # unit tests (no TeX required)
pytest tests/ -v -k "not pipeline"  # skip if latexmk unavailable
```

**For future Claude sessions** — add a section:
```markdown
## Continuous Improvement (Claude workflow)

When asking Claude to improve this codebase, Claude follows the protocol in
`AGENTS.md`. Common triggers:
- "Run testing agent on seed 42" → downloads arXiv papers, compares PDF output
- "Fix BUG-3" → follows the Coding Agent checklist
- "Fix next bug" → picks the highest-severity OPEN entry in BUGS.md

Claude will always write a failing test before touching code, and will always
add MATCHES/CAPTURES/LIMITATIONS comments before touching regex patterns.
If Claude encounters a LaTeX construct it doesn't recognise, it will ask for
the CTAN documentation link rather than guessing.
```

**Note on CI/CD** — add at the end of README:
```markdown
## Optional: Automated CI

A basic GitHub Actions workflow can be added to run `pytest`, `ruff`, and
`mypy` on every push:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: ruff check src/
      - run: mypy src/texphage/
      - run: pytest tests/ -v
```

Note: tests that require `latexmk` (test_pipeline.py end-to-end) need a
TeX Live system package: `sudo apt install texlive-full` in the CI job.
```

**6.2 — `scripts/test_fidelity.py`** — implement per `AGENTS.md`.

**Commit:** `docs: README with system deps and Claude workflow; implement test_fidelity.py`

---

## PART 4: OUT OF SCOPE

- `xy_to_tikzcd` conversion (leave as commented TODO)
- `\expandafter` / `\csname` expansion (document as known limitation)
- `pgfkeys` / `\tikzset` (document as known limitation)
- CI/CD configuration (optional; see README note above)

---

## PART 5: FINAL CHECKLIST

```
[ ] pip install -e ".[dev]" succeeds
[ ] python -c "from texphage import unfold, demacro, find_used_packages, find_command, __version__"
[ ] pytest tests/ -v → all pass (xfail entries have BUGS.md entries AND fixture files)
[ ] Verbatim test passes: '  indented   code' survives preprocessing
[ ] Verbatim-with-percent test passes: '100% complete' and '% this is verbatim' preserved
[ ] Paragraph test passes: blank line → \par
[ ] Deterministic main file test passes: main.tex preferred over other.tex
[ ] ruff check src/ → zero errors
[ ] mypy src/texphage/ → zero errors (or documented exceptions)
[ ] git log → one commit per phase, descriptive messages
[ ] No raw print() in src/ (only in scripts/ CLI blocks)
[ ] import regex as re everywhere in src/; no bare import re
[ ] Original source files (demacro.py, find_packages.py, extractor.py) deleted from repo root
[ ] cache/ in .gitignore and .claudeignore
[ ] tests/runs/ in .gitignore and .claudeignore
[ ] BUGS.md present with severity scale and entry schema
[ ] __version__.py present; version consistent with pyproject.toml
[ ] find_command() present in find_packages.py and exported from __init__.py
[ ] __all__ defined in every src/ module
[ ] All functions in src/ have type signatures and docstrings
[ ] All regex patterns in demacro.py have MATCHES/CAPTURES/LIMITATIONS comments
[ ] filelock used for all cache reads/writes in find_packages.py
[ ] JSON cache (not pickle) in find_packages.py
[ ] tests/test_pipeline.py created (even if empty with comment template)
[ ] Every xfail test has a corresponding fixture file in tests/fixtures/
```