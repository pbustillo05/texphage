# pgfkeys / tikzset Support — Implementation Plan

**Status:** Pre-implementation research complete. Gemini critique (2026-03-24) + Grok/Gemini second-pass critique (2026-03-25) reviewed and incorporated.
**Assigned to TODO.md:** `[ENHANCEMENT] pgfkeys Support`

---

## 0. Response to Gemini's Critique (2026-03-24)

Gemini raised 5 points. Verdicts:

**Point 1 — Generalize to `\<name>set` pattern: REJECTED.**
The premise is factually wrong. `\hypersetup` uses the `keyval` package, `\geometry` has its own parser, `\siunitx` uses LaTeX3 `l3keys`, `\lstset` uses `keyval`. None of these are pgfkeys-based. A generic `\<name>set{...}` regex would produce catastrophic false positives: `\subset{}`, `\reset{}`, `\dataset{}`, any user-defined `\myset{}`. The explicit-command approach is correct. New commands are added when empirically found to break arXiv papers, with a failing test as proof.

**Point 2 — Tikzstyle regex fragility: ACCEPTED.**
The original `_TIKZSTYLE_RE` tried to parse components it doesn't need. Simplified below.
Failure cases for the original: `\tikzstyle{foo}[scale=2, x=1]=[draw]` (default contains `=`);
`\tikzstyle{foo}=[/.tip=Latex[length=3mm]]` (nested brackets in options). The fix: don't
capture name/default/append separately. Use a "capture-all" pattern that matches
`\tikzstyle` + (anything not containing `=`) + `=` + balanced `[...]`.

**Point 3 — `.code` handler danger: REJECTED.**
Texphage never EXECUTES `.code` handlers — it preserves `\pgfkeys{...}` verbatim. The
"dangerous code" runs at TeX compile time identically in both original and minimal preamble.
Scanning `.code` blocks for `\let`/`\def` would create enormous false-positive noise;
nearly every real `.code` handler uses `\def`. No action needed.

**Point 4 — Macro expansion inside key values: ACCEPTED AS STEP 7.**
Real problem: `\newcommand{\mycolor}{blue}\tikzset{foo/.style={fill=\mycolor}}` — if `\mycolor`
is stripped, the preserved `\tikzset` is broken. Fix: before preservation, run `demacro.expand`
on the CONTENT of each `\pgfkeys`/`\tikzset` block argument. Added as Step 7.

**Point 5 — `.estyle`/`.ecode` priority: ACCEPTED AS REFINEMENT OF STEP 7.**
`.estyle`/`.ecode` REQUIRE expansion — TeX runs `\edef` at definition time, so if `\mycolor`
is undefined in the minimal preamble, `\tikzset{foo/.estyle={\mycolor}}` throws an error.
`.style` is lower priority (fails silently, renders wrong but doesn't crash). Step 7 must
prioritize `.estyle`/`.ecode` values. Demacro's expansion is equivalent to `\edef` for the
subset of macros it handles (preamble `\newcommand`/`\def`); diverges only for registers,
`\the`, and `\noexpand` — rare in arXiv papers.

---

## 0b. Response to Second-Pass Critique (Gemini + Grok, 2026-03-25)

Three concerns raised; two new ones accepted.

**Gemini A — "Raw preamble vs. comments" trap: ACCEPTED AS LIMITATION + STEP 7 FIX.**
`embed_brackets` uses PCRE `(?&name)` recursion which does NOT understand LaTeX `%` comments.
A `{` inside a comment inside `\tikzset{...}` would unbalance the brace count:
  ```latex
  \tikzset{ mynode/.style={draw} % { spurious opening brace
  }
  ```
For Steps 1-3 (preservation on raw preamble): this is a known limitation; added to Section 6.
This is extremely rare in practice — `% {` comments inside `\tikzset{}` are unusual.
For Step 7 (expansion): the fix is to run finditer on `preamble_flat` (preprocessed, comments
already stripped by `_COMMENT_RE`) rather than `raw_preamble`. Updated in Step 7.
**NOT a blocker for Steps 1-3.** The case "comment with unbalanced brace inside tikzset" is
pathological enough to document but not worth the architectural cost of full preprocessing
in `build_minimal_preamble` (which works on raw text for other preserved items too).

**Gemini B — `_TIKZSTYLE_RE` bare name misses hyphens: ACCEPTED.**
`\tikzstyle every-node=[...]` is common. `[a-zA-Z0-9 ]*` misses `-`.
Slashes in *bare* names (i.e., without braces) do not exist — `/` is pgfkeys namespace
notation and only appears inside braced arguments, where `[^}]*` already handles it.
Fix: expand bare-name character class to include `-`.

**Gemini C — `str.index('{')` in Step 7: ALREADY HANDLED.**
The plan already has an "Implementation note" saying to use named capture groups instead.
The code stub showed the naive version. Updated code stub to directly use `m.group('tikzset_arg')`.

**Grok — `.cd` inside `\tikzset` test case: ACCEPTED.**
`\tikzset{/tikz/.cd, foo/.style={draw}}` is valid and not tested. Added to Step 1 tests.

**Grok — `str.index('{')` fix approach correction: NOTED.**
Grok's `full_call.replace(arg_bracketed, '{' + expanded + '}')` is better than
`full_call[:cmd_end + 1] + expanded + '}'` because it doesn't require finding cmd_end.
Updated Step 7 code stub to use this approach.

---

## 1. Background and Requirements

### What the feature is

arXiv papers using TikZ extensively define custom node/edge/path styles in their preamble
using one of three idioms:

```latex
% Form A — modern (post-2013)
\tikzset{mynode/.style={draw, circle, fill=blue!20}}
\tikzset{myedge/.style={->, thick, draw=#1}}      % parameterised

% Form B — deprecated but extremely common in papers 2005-2018
\tikzstyle{mynode}=[draw, circle]
\tikzstyle{myedge}=[->, thick]

% Form C — raw pgfkeys
\pgfkeys{/tikz/mynode/.style={draw, circle}}
\pgfkeys{/tikz/.cd, myedge/.style={->, thick}}
```

These definitions are NOT LaTeX macros — they are entries in the pgfkeys *key-value database*
that TikZ reads at runtime. They CANNOT be expanded textually by demacro the way `\newcommand`
definitions can.

### The bug

`build_minimal_preamble` (in `pipeline.py`) strips ALL preamble content except:
- `\documentclass`, `\usepackage`, `\usetikzlibrary`
- `\title`, `\author`, etc. (front-matter)
- `\newtheorem` declarations
- `\excludeversion` / `\includeversion`
- `\definecolor`, `\colorlet`

`\tikzset`, `\pgfkeys`, and `\tikzstyle` are **not in this list**, so they are silently
dropped. The result: any paper with custom TikZ styles compiles to a broken PDF that is
missing node shapes, colours, and arrow styles.

### What demacro does (and doesn't do) with pgfkeys

`build_dictionary` has an `else: pass` branch ostensibly for tikzset, but since there are
no pgfkeys patterns in `_FIND_ALL_RE`, no `\tikzset`/`\pgfkeys` call ever reaches that
branch. It is dead code. The commands are silently ignored in macro scanning — which is
**correct** (we don't want to expand them as if they were `\newcommand`) — but the preamble
preservation is still broken.

### Design decision: preserve, don't expand

For virtually all cases in arXiv papers, the correct behaviour is:
- **Keep `\tikzset{...}`, `\pgfkeys{...}`, and `\tikzstyle{...}` verbatim in the
  minimal preamble.**
- **Do NOT attempt to expand TikZ style invocations in the document body.**

The only exception (covered in advanced steps below) is when a `.code` handler
inside `\pgfkeys` defines a LaTeX macro via `\def`/`\newcommand`. This is rare,
complex, and out of scope for Steps 1-3.

---

## 2. pgfkeys Vocabulary — What Opus Needs to Know

**Authoritative references:**
- TikZ/pgfkeys manual §87 (key handlers): https://tikz.dev/pgfkeys
- `\tikzstyle` legacy parsing: `tikz.code.tex` in the TeX Live installation
  (`kpsewhich tikz.code.tex`), or CTAN: https://mirror.ctan.org/graphics/pgf/base/tex/generic/pgf/frontendlayer/tikz/tikz.code.tex

### The key-value system

`\pgfkeys{⟨key-list⟩}` processes a comma-separated list of `key=value` pairs.
Keys are hierarchical paths: `/tikz/line width`, `/my/pkg/option`.

**`\tikzset{⟨list⟩}`** is exactly `\pgfkeys{/tikz/.cd, ⟨list⟩}` — sets the default
path to `/tikz/` then processes the list. Relative keys like `mynode` become `/tikz/mynode`.

**`\pgfqkeys{/path}{⟨list⟩}`** is a faster variant of `\pgfkeys{/path/.cd, ⟨list⟩}`.

### Key handlers — what appears in arXiv preambles

| Handler | Meaning |
|---|---|
| `key/.style={list}` | Stores `list` as code to run when `[key]` is used. Most common. |
| `key/.style 2 args={list}` | Two-argument variant; `#1`, `#2` filled from `{a}{b}` value |
| `key/.estyle={list}` | Like `.style` but list is `\edef`-expanded at definition time |
| `key/.code={code}` | Arbitrary TeX code; `#1` = value provided at invocation |
| `key/.code 2 args={code}` | Two-argument code handler |
| `key/.code args={pattern}{code}` | Arbitrary TeX argument pattern |
| `key/.ecode={code}` | Like `.code` but `\edef`-expanded at definition |
| `key/.initial=val` | Stores `val` as the key's default value (readable later) |
| `key/.default=val` | Value used when key invoked without `=` |
| `key/.append style={list}` | Appends to existing style; non-destructive extension |
| `key/.prefix style={list}` | Prepends to existing style |
| `key/.add style={pre}{app}` | Prepends `pre` and appends `app` to existing style |
| `key/.is if=ifname` | `key=true` → `\ifnametrue`; `key=false` → `\ifnamefalse` |
| `key/.is choice` | `key=val` dispatches to subkey `key/val` |
| `key/.store in=\macro` | On `key=val`, runs `\def\macro{val}` |
| `key/.estore in=\macro` | Like `.store in` but uses `\edef` |
| `key/.forward to=other` | After own code, also sets `other` key |
| `key/.cd` | Changes default path to `key` for subsequent keys in same call |
| `key/.is family` | Declares key as a fast-path family root |

### Deprecated `\tikzstyle` grammar

```
\tikzstyle{name}=[options]             % define style (most common)
\tikzstyle{name}+=[options]            % append to existing style
\tikzstyle{name}[default]=[options]    % define with default value
\tikzstyle name=[options]              % bare name (no braces)
```

This is parsed by TikZ and desugared to `\pgfkeys{/tikz/name/.style={options}}` or
`\pgfkeys{/tikz/name/.append style={options}}`. It lives in the `/tikz/` namespace.

### What requires preamble preservation

ALL `\tikzset{...}`, `\pgfkeys{...}`, `\tikzstyle{...}` calls that appear in the
original preamble must survive to the minimal preamble. There is no way to know at
static analysis time which style invocations the body uses.

---

## 3. Codebase Map

| File | Relevant part |
|---|---|
| `src/texphage/_regex.py` | Section 7 (Preamble-building patterns) — add new regexes here |
| `src/texphage/pipeline.py` | `build_minimal_preamble()` — add preservation logic here |
| `src/texphage/demacro.py` | `build_dictionary()` — `else: pass` branch; no changes in Steps 1-3 |
| `tests/test_pipeline.py` | Add new preservation tests here |

### Naming conventions (from CLAUDE.md)
- Compiled patterns: `_UPPER_SNAKE_CASE_RE`
- Raw pattern strings: `_UPPER_SNAKE_CASE_PATTERN`
- Pattern-builder lambdas: `snake_case`

### The `embed_brackets`/`embed_braces` confusion
**Critical:** in this codebase the naming is reversed from intuition:
- `embed_brackets(s)` → matches **`{...}`** (curly braces, mandatory args)
- `embed_braces(s)` → matches **`[...]`** (square brackets, optional args)

Both use PCRE recursion (`(?&name)`) for balanced matching. Both work correctly on
multi-line text (character classes like `[^\{\}]` match newlines even without DOTALL).

---

## 4. Implementation Steps

Each step is a valid stopping point. Steps 1-3 deliver the core fix.
Steps 4-6 are progressively more advanced.

---

### Step 1 — Playground Verification + Failing Tests

**Goal:** Confirm empirically that dropping `\tikzset`/`\pgfkeys`/`\tikzstyle` breaks
compilation, and write failing tests before touching any production code.

**Playground experiments to run** (using `scripts/latex_playground.py`):

**Experiment A: tikzset style dropped**
```latex
% WITH tikzset in preamble (should compile fine)
\documentclass{article}
\usepackage{tikz}
\tikzset{mynode/.style={draw, circle, fill=blue!20, minimum size=8mm}}
\begin{document}
\begin{tikzpicture}
  \node[mynode] {A};
\end{tikzpicture}
\end{document}
```
vs. the same without the `\tikzset` line. Expected: without it, TeX warns about unknown
style `mynode` and the node lacks draw/circle/fill.

**Experiment B: tikzstyle dropped**
```latex
\documentclass{article}
\usepackage{tikz}
\tikzstyle{myedge}=[->, thick, draw=red]
\begin{document}
\begin{tikzpicture}
  \draw[myedge] (0,0) -- (2,0);
\end{tikzpicture}
\end{document}
```

**Experiment C: parameterised style dropped**
```latex
\tikzset{nodecolor/.style={fill=#1!20, draw=#1!80}}
% body uses \node[nodecolor=blue]{text};
```

**Failing tests to write (in `tests/test_pipeline.py`):**

```python
# ---- pgfkeys Step 1 failing tests ----

def test_tikzset_preserved_in_minimal_preamble():
    """\\tikzset definitions must survive to the minimal preamble (Step 1)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzset{mynode/.style={draw, circle, fill=blue!20}}' + '\n'
        r'\begin{document}' + '\n'
        r'\begin{tikzpicture}\node[mynode]{A};\end{tikzpicture}' + '\n'
        r'\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\tikzset' in minimal
    assert 'mynode' in minimal


def test_tikzstyle_preserved_in_minimal_preamble():
    """\\tikzstyle definitions must survive to the minimal preamble (Step 1)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzstyle{myedge}=[->, thick, draw=red]' + '\n'
        r'\begin{document}' + '\n'
        r'\begin{tikzpicture}\draw[myedge](0,0)--(1,0);\end{tikzpicture}' + '\n'
        r'\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\tikzstyle' in minimal
    assert 'myedge' in minimal


def test_pgfkeys_preserved_in_minimal_preamble():
    """\\pgfkeys definitions must survive to the minimal preamble (Step 1)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\pgfkeys{/tikz/mykey/.style={fill=blue}}' + '\n'
        r'\begin{document}' + '\n'
        r'\begin{tikzpicture}\node[mykey]{A};\end{tikzpicture}' + '\n'
        r'\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\pgfkeys' in minimal
    assert 'mykey' in minimal


def test_tikzset_multiline_preserved():
    """Multi-key \\tikzset block (spanning multiple lines) must be preserved whole."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        '\\tikzset{\n'
        '  nodeA/.style={draw, circle},\n'
        '  nodeB/.style={draw, rectangle, fill=red!20}\n'
        '}' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\tikzset' in minimal
    assert 'nodeA' in minimal
    assert 'nodeB' in minimal


def test_tikzstyle_append_preserved():
    """\\tikzstyle with += (append) must be preserved."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzstyle{mynode}=[draw]' + '\n'
        r'\tikzstyle{mynode}+=[fill=blue]' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert minimal.count(r'\tikzstyle') == 2   # both lines preserved


def test_parameterised_tikzset_preserved():
    """Parameterised \\tikzset styles (using #1) must be preserved."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzset{nodecolor/.style={fill=#1!20, draw=#1!80}}' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert 'nodecolor' in minimal


def test_tikzset_with_cd_preserved():
    """\\tikzset using .cd to set default path must be preserved (Grok concern)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzset{/tikz/.cd, mynode/.style={draw, circle}}' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\tikzset' in minimal
    assert 'mynode' in minimal


def test_tikzstyle_hyphenated_name_preserved():
    """\\tikzstyle with hyphenated bare name must be preserved (Gemini B)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\tikzstyle every-node=[font=\small, draw]' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert r'\tikzstyle' in minimal
    assert 'every-node' in minimal
```

All of these should **fail** before implementation. Commit the failing tests with message:
`test: add failing tests for pgfkeys/tikzset preamble preservation (Step 1)`

---

### Step 2 — Add Regex Patterns to `_regex.py`

**Location:** Section 7 (Preamble-building patterns), after `_VERSION_ENV_RE`.

Load `regex-writing` skill before touching `_regex.py`.
Load `regex-danger-zone` skill if modifying existing patterns (not needed for additions).

#### Pattern 1: `_TIKZSET_RE`

Matches `\tikzset{...}` with balanced braces (handles multi-line, nested braces).

```python
# _TIKZSET_RE: matches a complete \tikzset{...} call.
# MATCHES: \tikzset followed by a balanced-brace argument.
#          Handles multi-line content and arbitrarily nested {} inside.
#          Does NOT match \tikzsetfoo (negative lookahead after 'tikzset').
# CAPTURES:
#   tikzset_arg → the complete {…} argument including outer braces.
#                 Use m.group(0) for the full \tikzset{...} call.
# LIMITATIONS:
#   [inferred] Does not distinguish \tikzset in the body from \tikzset in
#              the preamble; caller must restrict to raw_preamble.
#   [inferred] \pgfqkeys{/tikz}{...} (equivalent to \tikzset) not matched;
#              handled by _PGFKEYS_RE or _PGFQKEYS_RE.
_TIKZSET_RE = re.compile(
    r'\\tikzset(?![a-zA-Z])\s*'
    + embed_brackets('tikzset_arg'),
    re.DOTALL,
)
```

**Note on DOTALL:** `embed_brackets` generates `[^\{\}]++` which already matches newlines.
But the `\s*` between `\tikzset` and `{` needs DOTALL-free matching — `\s` always matches
`\n`. So `re.DOTALL` is technically not needed but doesn't hurt. Include it for clarity.

#### Pattern 2: `_PGFKEYS_RE`

```python
# _PGFKEYS_RE: matches a complete \pgfkeys{...} call.
# MATCHES: \pgfkeys followed by a balanced-brace argument.
#          Content may contain key=value pairs, commas, nested {}, /tikz/.cd idioms.
# CAPTURES:
#   pgfkeys_arg → the complete {…} argument.
#                 Use m.group(0) for the full call.
# LIMITATIONS:
#   [inferred] \pgfqkeys{/path}{...} not matched; use _PGFQKEYS_RE for that.
#   [inferred] \pgfkeyssetvalue and other internal commands not matched (not needed).
_PGFKEYS_RE = re.compile(
    r'\\pgfkeys(?![a-zA-Z])\s*'
    + embed_brackets('pgfkeys_arg'),
    re.DOTALL,
)
```

#### Pattern 3: `_PGFQKEYS_RE`

```python
# _PGFQKEYS_RE: matches \pgfqkeys{/path}{...} — quick-path pgfkeys variant.
# MATCHES: \pgfqkeys{path}{arg-list}.
#          Semantically equivalent to \pgfkeys{path/.cd, arg-list}.
# CAPTURES:
#   pgfqkeys_path → the path argument {…}
#   pgfqkeys_arg  → the key-list argument {…}
# LIMITATIONS:
#   [inferred] \pgfqkeysalso not matched (used inside code bodies, not preamble).
_PGFQKEYS_RE = re.compile(
    r'\\pgfqkeys(?![a-zA-Z])\s*'
    + embed_brackets('pgfqkeys_path')
    + r'\s*'
    + embed_brackets('pgfqkeys_arg'),
    re.DOTALL,
)
```

#### Pattern 4: `_TIKZSTYLE_RE`

**Simplified per Gemini critique (accepted).** The original design parsed sub-components
(name, default, options) separately — fragile because the `[default]` argument can contain
`=` signs and nested brackets.

Concrete failure cases for a parsed approach:
- `\tikzstyle{foo}[scale=2, x=1]=[draw]` — default `[scale=2, x=1]` contains `=`,
  which breaks any naive `[^=]+` attempt to find the final `=`.
- `\tikzstyle{arr}=[->, >=Latex[length=3mm]]` — nested brackets in the options value.

Since the goal is **preservation only** (not interpretation), we capture the whole statement
without parsing sub-components. Name and optional default are consumed as part of the match;
only the final balanced `[options]` needs to be precisely matched (to know where the statement ends).

```python
# _TIKZSTYLE_RE: matches \tikzstyle definitions (deprecated TikZ syntax).
# Goal: PRESERVATION. Captures the complete statement from \tikzstyle to the
# closing ] of the options block. Sub-components (name, default, +) not captured.
# MATCHES all forms:
#   \tikzstyle{name}=[options]              (simple define)
#   \tikzstyle{name}+=[options]             (append)
#   \tikzstyle{name}[default]=[options]     (define with default)
#   \tikzstyle name=[options]               (bare name, no braces)
#   \tikzstyle every node=[opts]            (multi-word bare name with space)
#   \tikzstyle{foo}[x=1]=[draw]             (default containing =, key failure case)
#   \tikzstyle{arr}=[->, >=Latex[length=3mm]] (nested brackets in options)
# CAPTURES:
#   (none — use m.group(0) for the full statement)
# LIMITATIONS:
#   [inferred] [default] bracket match uses non-recursive [^\[\]]* — triple-nested
#              brackets inside a default value (extremely rare) would fail.
#   [inferred] \tikzstyle with a bare name containing punctuation other than
#              letters, digits, spaces, and hyphens is not matched. Slashes in
#              bare names do not exist in practice (they only appear in pgfkeys
#              namespace paths, which are always braced).
_TIKZSTYLE_RE = re.compile(
    r'\\tikzstyle\s*'
    # Name: {braced content} or letters/digits/spaces/hyphens (bare multi-word).
    # Hyphens are common: \tikzstyle every-node=[...]. Slashes only occur in
    # pgfkeys namespace paths ({/tikz/foo}) which are always braced, so [^}]* covers them.
    r'(?:\{[^}]*\}|[a-zA-Z][a-zA-Z0-9 \-]*)'
    r'\s*'
    # Optional [default] — non-recursive [^\[\]]* is fine; defaults are simple scalars
    r'(?:\[[^\[\]]*\]\s*)?'
    # Optional + for append, then =
    r'\+?\s*=\s*'
    # Required [options] with PCRE balanced bracket recursion
    r'(?P<tikzstyle_opts>(?<!\\)\[(?:[^\[\]]++|(?<=\\)\[|(?<=\\)\]|(?P&tikzstyle_opts))*(?<!\\)\])',
    re.DOTALL,
)
```

**`(?P&tikzstyle_opts)` is PCRE self-recursion** — handles `>=Latex[length=3mm]` style nested
brackets. The `regex` module supports this. `m.group(0)` gives the entire statement.

**Torture tests — all must pass before committing:**
```python
import regex as re
from texphage._regex import _TIKZSTYLE_RE

assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{mynode}=[draw, circle, fill=blue!20]')
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle myedge=[->, thick]')        # bare name
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle every node=[font=\small]')  # multi-word bare
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle every-node=[font=\small]')  # hyphenated bare name
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{foo}+=[fill=red]')           # append form
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{foo}[scale=2]=[draw]')       # default with =
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{arr}=[->, >=Latex[length=3mm]]')  # nested [
# Full-text capture: m.group(0) should be the entire statement
m = re.search(_TIKZSTYLE_RE, r'\tikzstyle{mynode}=[draw, circle]')
assert m.group(0) == r'\tikzstyle{mynode}=[draw, circle]'
# Must NOT match \tikzstyle inside a word (but this is restricted by context in caller)
# No false positive on empty options
assert not re.search(_TIKZSTYLE_RE, r'\tikzstyle{foo}={}')  # {} not [], should not match
```

#### Exports

Add all four to the `__all__`-equivalent imports in `pipeline.py`:

```python
from texphage._regex import (
    ...
    _PGFKEYS_RE,
    _PGFQKEYS_RE,
    _TIKZSET_RE,
    _TIKZSTYLE_RE,
)
```

---

### Step 3 — Update `build_minimal_preamble` in `pipeline.py`

After the patterns pass unit tests, update `build_minimal_preamble`:

```python
# pgfkeys / TikZ key-value definitions must survive preamble stripping.
# \tikzset{name/.style={...}}, \pgfkeys{/tikz/name/.style={...}}, and the
# deprecated \tikzstyle{name}=[...] all define named TikZ styles that are
# referenced by name in the document body. They are TikZ runtime data, not
# LaTeX macros; they cannot be expanded by demacro and must be preserved verbatim.
tikzset_defs  = [m.group(0).strip() for m in _TIKZSET_RE.finditer(raw_preamble)]
pgfkeys_defs  = [m.group(0).strip() for m in _PGFKEYS_RE.finditer(raw_preamble)]
pgfqkeys_defs = [m.group(0).strip() for m in _PGFQKEYS_RE.finditer(raw_preamble)]
tikzstyle_defs = [m.group(0).strip() for m in _TIKZSTYLE_RE.finditer(raw_preamble)]

parts = (
    [docclass]
    + pkg_lines
    + newtheorems
    + version_envs
    + color_defs
    + tikzset_defs
    + pgfkeys_defs
    + pgfqkeys_defs
    + tikzstyle_defs
    + front_matter
)
```

**Order matters:** pgfkeys/tikzset definitions must come AFTER package declarations
(since `tikz` must be loaded before `\tikzset`), but BEFORE `\begin{document}`.
Front-matter last (as currently). This ordering is correct above.

**Update the docstring** of `build_minimal_preamble` to mention the new preserved items.

**Run tests:** `pytest tests/ -v && ruff check src/ && mypy src/texphage/`

**Commit:** `fix(pipeline): preserve \\tikzset/\\pgfkeys/\\tikzstyle in minimal preamble`

---

### Step 4 — `\pgfplotsset` and Similar pgfkeys-Based APIs (Optional but High Value)

**Context:** `pgfplots` is extremely common in arXiv math papers. It uses its own
`\pgfplotsset{...}` command (which wraps `\pgfqkeys{/pgfplots}{...}`). Other examples:
- `\pgfplotsset{...}` — pgfplots styles
- `\ctikzset{...}` — circuitikz (electrical circuits)
- `\pgfplotssettemplate{...}` — pgfplots template
- `\pgfooobj` / `\pgfoonew` — pgfoo (rare)

**Approach:** Rather than adding individual regexes for every pgfkeys-based command,
define a **generic pgfkeys-based command pattern** that matches any `\<name>set{...}`
or `\pgf<name>set{...}` command. OR add the most important ones explicitly.

**Recommended approach:** Add `_PGFPLOTSSET_RE` explicitly (high value, clear scope),
and document others as limitations.

```python
# _PGFPLOTSSET_RE: matches \pgfplotsset{...} (pgfplots package key-value setup).
# Semantically equivalent to \pgfkeys{/pgfplots/.cd, ...}.
# MATCHES: \pgfplotsset with balanced-brace argument.
# LIMITATIONS:
#   [inferred] pgfplots-specific handlers (e.g., /pgfplots/compat) not
#              parsed; entire call preserved verbatim for runtime.
_PGFPLOTSSET_RE = re.compile(
    r'\\pgfplotsset(?![a-zA-Z])\s*'
    + embed_brackets('pgfplotsset_arg'),
    re.DOTALL,
)
```

And similarly for `\ctikzset`:
```python
_CTIKZSET_RE = re.compile(
    r'\\ctikzset(?![a-zA-Z])\s*'
    + embed_brackets('ctikzset_arg'),
    re.DOTALL,
)
```

Add to `build_minimal_preamble` similarly to Step 3.

**Tests:**
```python
def test_pgfplotsset_preserved():
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{pgfplots}' + '\n'
        r'\pgfplotsset{compat=1.18, width=8cm}' + '\n'
        r'\begin{document}body\end{document}'
    )
    assert r'\pgfplotsset' in build_minimal_preamble(raw)
```

---

### Step 5 — `build_dictionary` Recognises pgfkeys (Demacro Integration)

**Context:** This step makes `build_dictionary` aware of pgfkeys, so it can:
1. Correctly skip `\tikzset`/`\pgfkeys`/`\tikzstyle` (currently they're skipped by
   not being in `_FIND_ALL_RE` — which is correct but invisible)
2. Optionally extract macro-defining `.code` handlers (advanced)

**Why bother?** Two reasons:
- Currently `build_dictionary` has `else: pass` which is dead code. Making the skip
  explicit improves correctness.
- Prevents a future regression if someone adds a pgfkeys pattern to `_FIND_ALL_RE`
  in an incorrect way.

**What to add to `_FIND_ALL_RE`:** A branch that matches `\tikzset{...}`,
`\pgfkeys{...}`, and `\tikzstyle{...}` and routes to the `else: pass` branch with
a named group `pgfkeys`.

Actually: the current `_FIND_ALL_RE` does NOT match these at all, which is why
`else: pass` is never reached by them. The `else: pass` branch actually handles
`_WEIRD_STUFF_PATTERN` (see the pattern union in `_FIND_ALL_RE`). But wait —
looking at `_FIND_ALL_RE`, `_WEIRD_STUFF_PATTERN` is NOT included either!
The `else: pass` is genuinely unreachable. The `else` fires only if `_FIND_ALL_RE`
matches something whose top-level group name is NOT any of the listed names —
which can't happen by construction.

**Conclusion for Step 5:** No change to `build_dictionary` is needed for correctness.
The `else: pass` branch is dead code and can be removed in a future cleanup. Leave it
for now; it's harmless and documents intent.

**One small addition (low effort, high value):** Update the comment near the `else: pass`
in `demacro.py` to explicitly say that `\tikzset`/`\pgfkeys`/`\tikzstyle` are handled by
preservation in `pipeline.py` (Steps 1-3), NOT by `build_dictionary`. This prevents a
future contributor from incorrectly adding pgfkeys patterns to `_FIND_ALL_RE` in an attempt
to "fix" the `else: pass`. Example:
```python
# Intentionally no pgfkeys/tikzset patterns in _FIND_ALL_RE.
# \tikzset{...}, \pgfkeys{...}, \tikzstyle{...} are preserved verbatim by
# build_minimal_preamble() in pipeline.py (Steps 1-3 of pgfkeys implementation).
# DO NOT add them here — they are not LaTeX macro definitions and cannot be
# expanded textually by demacro.
else:
    pass
```

**Optional (low priority):** Add a `tikzset` branch to `_FIND_ALL_RE` and route to
`else: pass` explicitly, making the intent visible. This is a documentation/clarity
change only.

---

### Step 6 — Extract Macro-Defining `.code` Handlers (Advanced, Out of Scope for v1)

**Context:** Some papers use pgfkeys `.code` handlers to define LaTeX macros:

```latex
\pgfkeys{
  /my/option/.code={%
    \def\myMacro{#1}%
    \setcounter{myctr}{0}%
  }
}
```

When `[my/option=foo]` is processed in the body, this defines `\myMacro{foo}`.
Demacro cannot expand `\myMacro` because it was never registered in `macro_dict`.

**Why this is hard:**
1. The macro is defined lazily (at key invocation time, not at definition time)
2. The key might be invoked in the body (`[my/option=bar]` inside a `tikzpicture`)
3. To know what value `#1` takes, we'd need to trace all invocations

**Approach for a future implementation:**
1. Add a `_PGFKEYS_CODE_RE` pattern that matches `.code={\def...}` content
2. In `build_dictionary`, when a `.code` body contains `\def` or `\newcommand`,
   extract the defined macros and register them with `#1` as the argument
3. This is analogous to the `csname_def` preamble execution pass already in
   `build_dictionary` (lines ~541-552 of `demacro.py`)

**Status:** Out of scope for this feature. Document as known limitation.

---

### Step 7 — Expand Custom Macros Inside pgfkeys Values Before Preservation

**Context (accepted from Gemini critique point 4, sharpened by point 5):**

The "preserve verbatim" strategy of Steps 2-3 has a gap:

```latex
\newcommand{\mycolor}{blue!80!white}
\tikzset{cool node/.style={fill=\mycolor, draw=\mycolor!70!black}}
```

After Steps 2-3, the minimal preamble contains:
- `\tikzset{cool node/.style={fill=\mycolor, draw=\mycolor!70!black}}` ← preserved
- NO `\newcommand{\mycolor}{...}` ← stripped by demacro

Result: compilation error — `\mycolor` undefined.

For `.estyle`/`.ecode` values the problem is worse: TeX runs `\edef` AT DEFINITION TIME,
so an undefined `\mycolor` inside `.estyle={...}` is a HARD ERROR, not just a visual glitch.

**Fix: expand pgfkeys values before preservation.** The pipeline already builds a macro
dictionary (`build_dictionary`) and expansion function (`expand`) in `demacro.py`. These
are public functions. We can apply expansion to the content of each `\pgfkeys`/`\tikzset`
block before preserving it.

**Architecture:** This requires coordinating `demacro.py` and `pipeline.py`. The key insight:
`build_dictionary(preamble)` and `expand(text, macro_dict, find_macro)` are already public.
The `pipeline.texphage()` function calls `demacro(raw_tex)` which internally calls both.
We need to expose the intermediate state.

**Proposed changes to `pipeline.py`:**

```python
def build_minimal_preamble(raw_tex: str) -> str:
    # ... existing code ...
    # NEW: build macro dictionary from preamble for expansion of pgfkeys values
    from texphage.demacro import preprocessing, build_dictionary, expand
    preamble_flat, _, _ = preprocessing(raw_tex)   # only need preamble portion
    # Actually: preprocessing() returns (preamble, body, packages)
    # preamble_flat is already the preprocessed preamble string
    macro_dict, find_macro = build_dictionary(preamble_flat)

    def _expand_pgfkeys_arg(m: re.Match, arg_group: str) -> str:
        """Expand custom macros inside a pgfkeys/tikzset argument.

        Uses the named capture group (arg_group) from the match to locate
        the balanced {…} argument precisely — no string-index gymnastics.
        This is safe per CLAUDE.md (regex-based, no str.index/str.find).
        """
        full_call = m.group(0)
        arg_bracketed = m.group(arg_group)   # e.g. m.group('tikzset_arg')
        arg_content = arg_bracketed[1:-1]    # strip outer { }
        expanded, _ = expand(arg_content, macro_dict, find_macro,
                             log_level=logging.DEBUG)
        # Replace only the bracketed argument; leaves command name intact
        return full_call.replace(arg_bracketed, '{' + expanded + '}', 1)

    # Apply expansion before collecting preserved lines.
    # Run finditer on preamble_flat (preprocessed, comments stripped) — NOT raw_preamble.
    # This avoids Gemini A: a { inside a % comment inside \tikzset{...} would otherwise
    # confuse embed_brackets' PCRE brace-counting recursion.
    tikzset_defs = [
        _expand_pgfkeys_arg(m, 'tikzset_arg').strip()
        for m in _TIKZSET_RE.finditer(preamble_flat)
    ]
    pgfkeys_defs = [
        _expand_pgfkeys_arg(m, 'pgfkeys_arg').strip()
        for m in _PGFKEYS_RE.finditer(preamble_flat)
    ]
    # ... etc. for pgfqkeys ...
```

**Priority order for expansion:**
1. `.estyle`/`.ecode` values MUST be expanded — TeX's `\edef` runs at definition time,
   so undefined macros inside these values cause hard errors even in the minimal preamble.
2. `.style` values SHOULD be expanded — failure is soft (visual glitch, not crash), but
   still wrong.
3. Plain value storage (`.initial`, `.default`) should also be expanded.

**Divergence between `demacro.expand` and `\edef`:**
`\edef` expands ALL tokens except `\noexpand`-guarded and unexpandable commands (registers,
`\the`, `\relax`, etc.). `demacro.expand` only substitutes macros in its dictionary —
preamble `\newcommand`/`\def` macros. They agree on the common arXiv case where
`.estyle` values reference simple user-defined macros. They diverge on `\the\count0`,
`\pgfmathresult`, etc. — acceptable for the first implementation.

**Implementation note:** The code stub above uses `m.group('tikzset_arg')` (named capture
group from `_TIKZSET_RE`) to locate the `{…}` argument. Do NOT use `str.index('{')` or
`str.find('{')` — these are structural string detection and violate CLAUDE.md. The named
group approach also handles whitespace between the command name and `{` correctly.
The `replace(..., 1)` call replaces only the first occurrence of `arg_bracketed` in
`full_call`, which is safe because `full_call` starts with the command name.

**Status:** Not implemented in Steps 1-3. Defer to after Steps 1-4 are stable. Add as a
separate commit: `fix(pipeline): expand custom macros in pgfkeys values before preservation`.

**Tests to add for Step 7:**
```python
def test_tikzset_with_custom_macro_expanded_before_preservation():
    """\\tikzset value referencing a stripped \\newcommand must be expanded."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\newcommand{\mycolor}{blue!80!white}' + '\n'
        r'\tikzset{mynode/.style={fill=\mycolor}}' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    # The expanded value must be in the minimal preamble; the bare \mycolor must not
    assert 'blue!80!white' in minimal
    # The \newcommand itself should still be stripped
    assert r'\newcommand' not in minimal


def test_tikzset_estyle_expanded():
    """.estyle values require expansion (hard error if \mycolor undefined under \\edef)."""
    from texphage.pipeline import build_minimal_preamble
    raw = (
        r'\documentclass{article}' + '\n'
        r'\usepackage{tikz}' + '\n'
        r'\newcommand{\myfill}{fill=blue}' + '\n'
        r'\tikzset{mynode/.estyle={\myfill, draw=black}}' + '\n'
        r'\begin{document}body\end{document}'
    )
    minimal = build_minimal_preamble(raw)
    assert 'fill=blue' in minimal
```

---

## 5. Testing and Commit Protocol

### Mandatory test-first protocol
Per CLAUDE.md: **Write failing tests before touching production code.**

For each step:
1. Write test(s) → confirm they FAIL
2. Commit: `test: add failing test for pgfkeys Step N`
3. Implement fix
4. Confirm tests pass
5. Run full suite: `pytest tests/ -v && ruff check src/ && mypy src/texphage/`
6. Commit: `fix(pipeline): preserve ... (pgfkeys Step N)`

### Playground verification
For any regex pattern that matches LaTeX constructs, MUST verify with:
```bash
.venv/bin/python scripts/latex_playground.py "..." --text
```

Use Template A (simple expansion test) or Template C (visual comparison).

Key experiments to run before implementing:
- Does `\tikzset` work on its own (without `\tikzstyle` package loaded)?
  → `\tikzset` requires `tikz`. If tikz is loaded, it's defined.
- Does `\tikzstyle` work without `\tikzstyle` package?
  → `\tikzstyle` is part of TikZ, defined in `tikz.code.tex`. No extra package needed.
- Does `\pgfkeys` work without tikz?
  → `\pgfkeys` is in the `pgf` core. It's available with `\usepackage{pgf}` or
     `\usepackage{tikz}` (tikz loads pgf).

### Memory aids for pattern testing
```python
import regex as re
from src.texphage._regex import _TIKZSET_RE, _PGFKEYS_RE, _TIKZSTYLE_RE

# Basic smoke test
assert re.search(_TIKZSET_RE, r'\tikzset{foo/.style={draw}}')
assert re.search(_TIKZSET_RE, '\n\\tikzset{\n  foo/.style={draw, circle}\n}')
assert re.search(_PGFKEYS_RE, r'\pgfkeys{/tikz/foo/.style={draw}}')
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{mynode}=[draw, circle]')
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle{mynode}+=[fill=blue]')
assert re.search(_TIKZSTYLE_RE, r'\tikzstyle myedge=[->]')   # bare name

# Edge cases
assert not re.search(_TIKZSET_RE, r'\tikzsetfoo{bar}')  # not a match
assert re.search(_TIKZSET_RE, r'\tikzset{a/.style={f={g={h}}}}')  # triple nesting
```

---

## 6. Known Limitations and Non-Goals for This Feature

**`\tikzset`/`\pgfkeys` with `%`-comments containing unbalanced braces (Steps 1-3 only).**
`build_minimal_preamble` runs patterns on the raw (unpreprocessed) preamble. `embed_brackets`
uses PCRE brace-recursion which counts ALL `{` and `}` characters including those after `%`.
Example: `\tikzset{foo/.style={draw} % spurious { comment\n}` — PCRE would see an extra `{`
and either fail to match or swallow text after the `}`. This is an extremely rare case
(users don't normally write unbalanced braces in LaTeX comments inside `\tikzset`), and is
documented here rather than fixed architecturally. Step 7 avoids this entirely by running
on `preamble_flat` (preprocessed, comments stripped).

**Cannot expand TikZ style invocations in the body.**
`\node[mynode]{text}` — the `mynode` style is dispatched by TikZ at runtime.
Demacro cannot replicate TikZ's pgfkeys dispatch engine statically.
The correct fix (implemented in Steps 2-3) is to preserve the style definition.

**`.code` handlers defining macros not supported (Steps 1-3).**
`\pgfkeys{/key/.code={\newcommand{\foo}{...}}}` — the `\foo` macro is NOT added to
`macro_dict` and will not be expanded. The pgfkeys call itself IS preserved in the
minimal preamble (so TikZ can define `\foo` at runtime when the key is invoked),
but demacro won't know about `\foo`. Handled in Step 6 (future).

**`\tikzset` values referencing stripped `\newcommand` macros (Steps 1-3).**
`\newcommand{\mc}{blue}\tikzset{foo/.style={fill=\mc}}` — after Steps 1-3, `\mc` is
undefined in the minimal preamble. This is the broken case from Gemini critique point 4.
Fixed in Step 7. For `.estyle`/`.ecode`, this is a hard error; for `.style`, a visual glitch.

**`\pgfplotsset` out of scope for Steps 1-3.** Added in Step 4.

**`\ctikzset`, `\pgfooobj`, and other pgfkeys-based commands** not covered.
Document as limitations in README.md after implementation.

**`\hypersetup`, `\geometry`, `\lstset` are NOT pgfkeys-based** — they use `keyval` or
`l3keys`. They are handled (or not) separately. Do NOT add a generic `\<name>set` regex.

**Style inheritance chains opaque.**
If `foo/.style={bar, baz}` and `bar` is itself a pgfkeys style, texphage cannot trace
the chain. TikZ handles this at runtime. Texphage just preserves the definition.

**Preamble-only detection.**
`build_minimal_preamble` is called with `raw_preamble = raw_tex[:begin_doc_m.start()]`.
Any `\tikzset`/`\pgfkeys` calls inside the document body are not preserved —
but they should not be, since `build_minimal_preamble` only processes preamble content.

---

## 7. README.md Updates

After completing Steps 2-3, remove from "Known limitations":
- Any bullet about TikZ styles / pgfkeys being unsupported

Add to "Supported":
- `\tikzset{name/.style={...}}` — TikZ style definitions
- `\pgfkeys{/tikz/name/.style={...}}` — raw pgfkeys style definitions
- `\tikzstyle{name}=[...]` — deprecated TikZ style syntax (still common)

Add to "Known limitations":
- `\pgfkeys{/key/.code={\def\macro{...}}}` — macro-defining code handlers not extracted
- `\pgfplotsset` preserved only from Step 4 onwards
- Style invocations in the body (`[mynode]`) cannot be statically expanded; require TikZ at compile time

---

## 8. Quick Reference: Files to Touch

| Step | Files modified | Stopping point? |
|---|---|---|
| 1 | `tests/test_pipeline.py` (new failing tests only) | Yes — proves the bug |
| 2 | `src/texphage/_regex.py` (add 4 new patterns to Section 7) | Yes — patterns ready |
| 3 | `src/texphage/pipeline.py` (update `build_minimal_preamble`) | **Yes — core fix** |
| 4 | `src/texphage/_regex.py`, `src/texphage/pipeline.py` (`_PGFPLOTSSET_RE`, `_CTIKZSET_RE`) | Yes — pgfplots support |
| 5 | None (cleanup only; optional) | Yes — dead code removal |
| 6 | Future work (extract `.code` macro definitions) | — |
| 7 | `src/texphage/pipeline.py` (expand macros inside pgfkeys values) | Yes — after Steps 1-4 stable |

---

## 9. Self-Contained Context for Opus

**What this codebase does:** Takes an arXiv LaTeX tarball, expands preamble-defined macros
(`\newcommand`, `\def`, etc.) in the document body, then produces a minimal 5-line
document. The minimal preamble keeps only `\documentclass`, `\usepackage`, and a few
other essential items.

**Why pgfkeys is different from `\newcommand`:** pgfkeys definitions (`\tikzset`,
`\pgfkeys`, `\tikzstyle`) are TikZ runtime data, not LaTeX macros. The pgfkeys engine
processes them, not TeX's macro expander. Demacro cannot expand style invocations like
`[mynode]` — it can only preserve the definitions so TikZ can expand them at compile time.

**The fix is entirely in `build_minimal_preamble`:** Add regex patterns that match
`\tikzset{...}`, `\pgfkeys{...}`, `\tikzstyle{...}` calls in the raw preamble, and
include their full text in the preserved output. No changes to `demacro.py` needed
for Steps 1-3.

**The `embed_brackets` and `embed_braces` naming confusion:** In this codebase,
`embed_brackets(s)` matches `{curly braces}` and `embed_braces(s)` matches `[square brackets]`.
This is backwards from the natural English meaning. Both use PCRE recursion.

**Always use `.venv/bin/python`**, not system Python.
