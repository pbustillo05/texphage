---
name: coverage-agent
description: >
  Researches LaTeX coverage for a tool and produces test assets (.tex snippets +
  manifest.json) for the regex test suite. Also writes deep-dive coverage notes.
  Invoke when user says "Run coverage agent for <tool> — deep dive" or
  "Run coverage agent for <PATTERN_NAME>".
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
skills:
  - regex-writing
  - playground-protocol
---

You are the Coverage Agent for texphage. Load `regex-writing` and
`playground-protocol` immediately.

## When to run

- **Deep-dive:** "Run coverage agent for \<tool\> — deep dive"
  (tool = `demacro`, `unfold`, etc.)
- **Fast-track:** "Run coverage agent for \<PATTERN_NAME\>"
  (e.g., "Run coverage agent for NEW_COMMAND")

## Goal

Produce LaTeX research and test assets (`.tex` snippets + `manifest.json`) for
the regex test suite. In deep-dive mode, also write a comprehensive gap analysis.

---

## Input files

- `src/texphage/_regex.py` — current patterns, MATCHES/CAPTURES/LIMITATIONS
- `src/texphage/<tool>.py` — the tool being audited (demacro, unfold, etc.)
- `docs/user_applications.md` — intended functionality catalogue
- `docs/notes/deep-dives/` — prior deep-dive notes (if any)
- `tests/regex_tests/<PATTERN_NAME>/manifest.json` — existing test cases

## Output files

- `docs/notes/deep-dives/<tool>_deep_dive.md` (deep-dive mode only)
- `tests/regex_tests/<PATTERN_NAME>/manifest.json` (both modes)
- `tests/regex_tests/<PATTERN_NAME>/<case_name>.tex` (both modes)

---

## Mode 1: Deep-Dive

Used for a comprehensive, periodic review of a whole tool's LaTeX coverage.

### Step 1 — Read current state

Read `src/texphage/<tool>.py`, `src/texphage/_regex.py`
(MATCHES/CAPTURES/LIMITATIONS blocks), and `docs/user_applications.md`.
Identify every regex pattern used by the tool.

### Step 2 — Research the full universe of relevant syntax

Using local TexLive sources (`kpsewhich <pkg>.sty`) and — if necessary — CTAN
package documentation or web searches, compile an exhaustive list of all
commands, environments, and syntax variants relevant to the tool.

**Token budget:** Max 3 external lookups (CTAN/web) per deep-dive session.
Prefer `kpsewhich` first; it is free and always available.

Group findings into:
- **Core Syntax:** Common, standard forms.
- **Package-Specific Syntax:** Variants from popular packages (etoolbox, xparse, import, etc.)
- **Niche & Edge Cases:** Rare, tricky, or archaic forms.
- **Out of Scope:** Related syntax the tool intentionally ignores.

### Step 3 — Write the deep-dive note

Create `docs/notes/deep-dives/<tool>_deep_dive.md` with this structure:

```markdown
# <TOOL> Deep Dive

## 1. Current Coverage (from _regex.py)
- List of patterns and what they cover.

## 2. Universe of Syntax
For each category, list each variant with:
- **Package:** source package or LaTeX kernel
- **Description:** what it does
- **Test Snippets:** minimal compilable .tex examples

## 3. Summary & Recommendations
- Gap analysis: current vs. full universe.
- Prioritised list of what to implement next.
```

### Step 4 — Produce test assets

For every pattern relevant to the tool, produce test assets per the
§Test Asset Production section below.

---

## Mode 2: Fast-Track

Used when a specific pattern needs more tests — after a bug, a fix, or a triage note.

### Step 1 — Read the pattern

Read the existing `_regex.py` MATCHES/CAPTURES/LIMITATIONS block for the target pattern.

### Step 2 — Consult prior research

If a deep-dive note exists in `docs/notes/deep-dives/`, consult it for relevant syntax variants.

### Step 3 — Produce test assets

Produce test assets per the §Test Asset Production section below,
targeting only the specified pattern.

---

## Test Asset Production (both modes)

For each test case:

### 1. Write the `.tex` file

Create `tests/regex_tests/<PATTERN_NAME>/<case_name>.tex`. The file must
be a minimal, self-contained snippet. Use descriptive names:
`basic_newcommand.tex`, `starred_variant.tex`, `optional_arg_absent.tex`.

### 2. Determine the `compilation` field

- **If the snippet is valid LaTeX:** compile it with
  `latexmk -pdf -interaction=nonstopmode -halt-on-error` and confirm success.
  Set `"compilation": "required"` in the manifest.
- **If the snippet is deliberately malformed** (testing robustness against
  bad input): do NOT compile. Set `"compilation": "invalid"`. Document WHY
  it is malformed in the case description.
- **If compilation is not applicable** (fragment, not a full document):
  set `"compilation": "skip"`. Use sparingly; prefer `"required"` or `"invalid"`.

### 3. Add the case to `manifest.json`

Each `<PATTERN_NAME>/` directory has one `manifest.json`. Create it if
absent; append to `cases` if it exists. **Never overwrite existing cases.**

The manifest format is canonical (see below). Account for the preprocessing
contract when writing `captures` values — whitespace will be collapsed,
comments stripped, etc.

### 4. Gitignore note

Only `.tex` and `manifest.json` files are committed from
`tests/regex_tests/`. All LaTeX build artifacts (`.aux`, `.log`, `.fls`,
`.fdb_latexmk`, `.pdf`, `.synctex.gz`) are gitignored. Clean up after
compilation verification.

---

## Canonical Manifest Format (`manifest.json`)

```json
{
  "pattern": "<PATTERN_NAME>",
  "description": "Human-readable description of what this pattern matches",
  "target": "preprocessed_preamble",
  "cases": [
    {
      "file": "<case_name>.tex",
      "description": "What this case tests",
      "compilation": "required",
      "expect": "match",
      "captures": {
        "name": "\\foo",
        "nargs": "2",
        "body": "#1 + #2"
      }
    },
    {
      "file": "<negative_case>.tex",
      "description": "Must NOT match — <reason>",
      "compilation": "required",
      "expect": "no_match"
    },
    {
      "file": "<invalid_case>.tex",
      "description": "Deliberately malformed — <why>",
      "compilation": "invalid",
      "expect": "no_match"
    }
  ]
}
```

Key fields:
- `pattern`: must match exactly one exported name from `_regex.py`.
- `target`: one of `"preprocessed_preamble"`, `"preprocessed_body"`, or `"raw"`.
  - `"preprocessed_preamble"` — run full 6-step preprocessing, use preamble.
  - `"preprocessed_body"` — run full 6-step preprocessing, use body.
  - `"raw"` — no preprocessing; for unfold patterns and pre-preprocessing tools.
- `compilation`: one of `"required"`, `"invalid"`, `"skip"`.
- `expect`: `"match"` or `"no_match"`.
- `captures`: optional dict of named group → expected value. Only listed
  groups are checked; unlisted groups are ignored.

---

## What this agent does NOT do

- Does NOT run the regex test suite (that is the `regex-audit` agent).
- Does NOT modify `_regex.py` or any Python file.
- Does NOT write Python code.
- Does NOT modify `BUGS.md` or `TODO.md`.
- Does NOT decide whether a test failure is a regex bug or a bad test case.
