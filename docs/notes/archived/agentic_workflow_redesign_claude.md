# Prompt for Opus: Complete Agentic Workflow Redesign

**Author:** Claude (Sonnet 4.6)
**Date:** 2026-03-25
**Purpose:** This note is a prompt for an Opus agent tasked with implementing
the redesigned agentic workflow for texphage. Read every section before
touching any file.

---

## 1. Background and Current State

texphage is a LaTeX rearrangement toolbox. Two AI agents collaborate on it:

- **Claude** (SWE): writes Python, writes/modifies `_regex.py`, writes pytest
  tests, runs the pipeline, owns all code changes.
- **Gemini** (LaTeX expert): researches CTAN/TexLive, identifies macro
  coverage gaps, writes `[inferred]` limitation bullets, proposes test
  snippets. NOT trusted to write Python or modify `_regex.py`.

**Current agents (before this redesign):**

| Agent | Owner | File | Role |
|---|---|---|---|
| triage_agent | Gemini | `.gemini/agents/triage_agent.md` | Prioritisation |
| macro_coverage_agent | Gemini | `.gemini/agents/macro_coverage_agent.md` | Demacro coverage |
| inclusion_coverage_agent | Gemini | `.gemini/agents/inclusion_coverage_agent.md` | Unfold coverage |
| regex-audit | Claude | `.claude/agents/regex-audit.md` | Pattern linting + playground tests |
| testing-agent | Claude | `.claude/agents/testing-agent.md` | End-to-end arXiv fidelity |
| coding-agent | Claude | `.claude/agents/coding-agent.md` | Bug fixes |
| quarterly-audit | Claude | `.claude/agents/quarterly-audit.md` | CTAN new package scan |

**New problems motivating the redesign:**
1. `macro_coverage_agent` and `inclusion_coverage_agent` don't scale as new
   tools are added (`xy_to_tikz`, pretty-printer, `find_packages`, …).
2. There is no systematic, persistent, growing unit-test suite for individual
   regex patterns. Claude's `regex-audit` is a linter + one-off playground
   verifier; it doesn't produce a durable test corpus.
3. Gemini's research output (coverage gaps, test snippets) has no structured
   path into the regex test suite.

**What Gemini has already done toward the redesign** (uncommitted files):
- `.gemini/agents/regex_audit_agent.md` — Gemini's proposed shared audit spec
- `.gemini/agents/researcher/TEMPLATE.md` — researcher agent template
- `scripts/test_regex.py` — a test runner script (details and issues below)

---

## 2. Guiding Principles (non-negotiable)

1. **Gemini's trust boundary is unchanged:** Gemini may write `.tex` snippets,
   markdown notes, `[inferred]` bullet points, and JSON manifest files. Gemini
   may NOT write Python, modify `_regex.py`, or commit code changes.
2. **`_regex.py` is module-independent.** All tools (`demacro`, `unfold`,
   `xy_to_tikz`, …) share the same regex engine. The regex test suite must
   likewise be module-independent — it tests patterns, not pipelines.
3. **The playground is the oracle for behavioral tests** (does a macro expand
   correctly?). A separate, lighter mechanism is needed for structural tests
   (does a pattern fire on valid LaTeX input?).
4. **Tests are persistent and growing.** Both agents can add test cases; the
   suite is committed and lives in `tests/regex_tests/`. It is never thrown away
   between runs.
5. **Claude owns all Python infrastructure.** If a new script or test file
   is needed, it is specified here but written by Claude's coding-agent or
   interactively by Claude — not by Gemini.

---

## 3. The New Agent Roster

| Agent | Owner | Spec file | Role |
|---|---|---|---|
| **triage_agent** | Gemini | `.gemini/agents/triage_agent.md` | Unchanged |
| **coverage_agent** | Gemini | `.gemini/agents/coverage_agent.md` | NEW: deep-dive research + test asset production (replaces researcher + regex_asset_agent) |
| **regex-audit** | Claude | `.claude/agents/regex-audit.md` | ENHANCED: runs test suite, updates `_regex.py` docs |
| **arxiv-fidelity** | Claude | `.claude/agents/arxiv-fidelity.md` | RENAMED from testing-agent, role unchanged |
| **coding-agent** | Claude | `.claude/agents/coding-agent.md` | Unchanged |
| **quarterly-audit** | Claude | `.claude/agents/quarterly-audit.md` | Unchanged |

The old `macro_coverage_agent` and `inclusion_coverage_agent` are **retired**
and replaced by the researcher framework. Delete them.

---

## 4. The Regex Test Suite Architecture

This is the most important design decision in the redesign.

**Important:** the existing `tests/` suite — unit tests, pipeline/fidelity
tests, `test_regex_audit.py` — is unchanged and remains the primary testing
layer. The regex test suite described here is purely **additive**: a new
`tests/regex_tests/` subtree containing per-pattern unit tests driven by
`.tex` snippets and manifests. Both layers run together under `pytest tests/ -v`.

### 4.1 Directory layout

```
tests/
  regex_tests/              ← NEW subtree; everything else in tests/ is untouched
    <PATTERN_NAME>/
      manifest.json          ← expected outcomes (see §4.2)
      <case_name>.tex        ← one minimal compilable .tex snippet per case
      ...
    NEW_COMMAND_RE/
      manifest.json
      basic_newcommand.tex
      starred_variant.tex
      optional_arg_absent.tex
      nested_braces.tex
      at_in_name.tex
      ...
```

Each `<PATTERN_NAME>` subdirectory corresponds to exactly one exported name
from `src/texphage/_regex.py`.

### 4.2 Manifest format (`manifest.json`)

```json
{
  "pattern": "NEW_COMMAND_RE",
  "description": "Matches \\newcommand and variants in the preamble",
  "target": "preprocessed_preamble",
  "cases": [
    {
      "file": "basic_newcommand.tex",
      "description": "Standard \\newcommand with two args",
      "compilation": "required",
      "expect": "match",
      "captures": {
        "name": "\\foo",
        "nargs": "2",
        "body": "#1 + #2"
      }
    },
    {
      "file": "starred_variant.tex",
      "description": "\\newcommand* — star variant",
      "compilation": "required",
      "expect": "match",
      "captures": {
        "name": "\\bar"
      }
    },
    {
      "file": "body_no_definition.tex",
      "description": "Plain body text — must NOT match",
      "compilation": "required",
      "expect": "no_match"
    },
    {
      "file": "unbalanced_brace.tex",
      "description": "Unbalanced brace — pattern must not catastrophically match",
      "compilation": "invalid",
      "expect": "no_match"
    }
  ]
}
```

Key fields:
- `target`: string enum specifying what input to feed the regex:
  - `"preprocessed_preamble"` — after the full 6-step preprocessing pipeline,
    preamble part. Used for all current demacro patterns.
  - `"preprocessed_body"` — after full preprocessing, body part.
  - `"raw"` — raw source before any preprocessing. Used for unfold patterns
    (`\input`, `\include`) and future tools that operate pre-preprocessing.
- `compilation`: one of three values:
  - `"required"` — this snippet represents valid LaTeX; Gemini must compile it
    successfully before adding the case to the manifest. Compilation is the
    ground truth that the example is real, not a syntax error.
  - `"invalid"` — this snippet is **deliberately malformed** (e.g., unbalanced
    braces, incomplete definition). It will not and should not compile. These
    cases are essential for verifying robustness against bad input.
  - `"skip"` — compilation is not applicable (e.g., a fragment, not a full
    document). Use sparingly; prefer `"required"` or `"invalid"`.
- `expect`: `"match"` or `"no_match"`.
- `captures`: optional dict of named group → expected value. Any group listed
  here must match exactly; unlisted groups are ignored. These values are
  derived from the LaTeX source itself (after preprocessing), so Gemini must
  account for the preprocessing contract (whitespace collapse, etc.) when
  writing them.

### 4.3 The test runner: `scripts/test_regex.py`

Gemini wrote a first version. It needs the following changes (Claude implements):

1. **Accept manifest mode:** `python scripts/test_regex.py --manifest tests/regex_tests/NEW_COMMAND_RE/manifest.json`
   runs all cases in the manifest and reports PASS/FAIL per case.
2. **Target selection:** read the `target` field from the manifest and apply
   the appropriate preprocessing:
   - `"preprocessed_preamble"` / `"preprocessed_body"` — run the full 6-step
     `demacro.preprocessing()` pipeline, then split on `\begin{document}`.
   - `"raw"` — use the file content as-is with no preprocessing.
3. **Compilation handling:** for `"compilation": "required"` cases, assert the
   `.tex` file exists (Gemini verified it compiles; the runner does not
   recompile on every run). For `"compilation": "invalid"` cases, no
   compilation check is performed — the snippet is deliberately broken.
4. **Capture assertions:** compare actual captured groups against the `captures`
   dict in the manifest entry. Report mismatches as FAIL with diff.
5. **Single-case mode** (keep existing): `python scripts/test_regex.py PATTERN_NAME file.tex`
   for quick interactive checks.

### 4.4 Pytest integration: `tests/test_regex_suite.py`

Claude writes a pytest file that:
- Discovers all `manifest.json` files under `tests/regex_tests/`.
- Parameterises one test per manifest case.
- Calls the same logic as `scripts/test_regex.py` (shared helper, not duplicated).
- Integrates with `pytest tests/ -v` like all other tests.

This means `pytest tests/ -v` runs the entire regex test suite automatically.
The test IDs should be human-readable, e.g.:
`tests/test_regex_suite.py::test_regex[NEW_COMMAND_RE/starred_variant]`.

---

## 5. Gemini's Coverage Agent (merged researcher + asset creation)

The original proposal had two separate Gemini agents — a `researcher` and a
`regex_asset_agent`. Gemini correctly pointed out these overlap: both find
coverage gaps and produce test snippets. They are merged into one:
**`coverage_agent`**.

**Two modes, one agent:**

### 5.1 Deep-dive mode

**Trigger:** "Run coverage agent for \<tool\> — deep dive"

Used for a comprehensive, periodic review of a whole tool's LaTeX coverage.
Gemini performs CTAN/TexLive research first, then produces test assets.

Procedure:
1. Read `src/texphage/<tool>.py`, `src/texphage/_regex.py` MATCHES/LIMITATIONS,
   and `docs/user_applications.md`.
2. Research the full universe of relevant LaTeX syntax (CTAN, package docs,
   edge cases). Write findings to `.gemini/notes/deep_dives/<tool>_deep_dive.md`
   (the two-step vetting protocol still applies: this note, not TODO.md, is
   the output; Pablo promotes items).
3. For each syntax variant identified, produce test assets directly
   (see §5.3).

### 5.2 Fast-track mode

**Trigger:** "Run coverage agent for \<PATTERN_NAME\>" (no "deep dive")

Used when a specific pattern needs more tests — e.g., after a bug is found,
after a fix, or when a triage note surfaces a specific gap. No deep-dive note
required.

Procedure:
1. Read the existing `_regex.py` MATCHES/CAPTURES/LIMITATIONS for the pattern.
2. If a deep dive note exists in `.gemini/notes/deep_dives/`, consult it.
3. Produce test assets directly (see §5.3) for the targeted pattern.

### 5.3 Test asset production (both modes)

For each test case:
1. Write `.tex` file to `tests/regex_tests/<PATTERN_NAME>/<case_name>.tex`.
2. Determine the `compilation` field:
   - If the snippet is meant to represent valid LaTeX: run
     `latexmk -pdf -interaction=nonstopmode -halt-on-error` on it.
     If compilation fails, fix the snippet before proceeding. Set
     `"compilation": "required"` in the manifest.
   - If the snippet is deliberately malformed (testing robustness): do not
     compile. Set `"compilation": "invalid"`. Document WHY it's malformed.
   - If compilation is not applicable (fragment): set `"compilation": "skip"`.
3. Add the case to `manifest.json` with the correct `compilation`, `expect`,
   and `captures` fields.
4. Do NOT overwrite existing test cases. Only add new ones.

**What it does NOT do:**
- Does NOT run the regex tests (that's Claude's regex-audit)
- Does NOT modify `_regex.py`
- Does NOT modify Python files

**Spec file location:** `.gemini/agents/coverage_agent.md`
(the old `researcher/TEMPLATE.md`, `researcher/demacro_agent.md`,
`researcher/unfold_agent.md`, and `regex_asset_agent.md` are superseded by
this single spec with per-tool trigger phrasing).

---

## 7. Claude's Enhanced Regex Audit Agent

Claude's `.claude/agents/regex-audit.md` gets these additions (keep everything
currently there, add):

**New Step 0 — Check for test assets:**
Before writing new playground tests, check `tests/regex_tests/<PATTERN_NAME>/`
for existing manifests from Gemini. If a manifest exists, run it first via
`scripts/test_regex.py --manifest ...` and incorporate results.

**New Step after Step 4 — Generate an audit report (do NOT auto-edit `_regex.py`):**
After running the manifest suite, produce a structured report listing every
failure: pattern name, case file, expected vs. actual result, and captured
group diffs. A test failure is a signal that requires interpretation — it
could be a bug in the regex, a flaw in Gemini's test case, or a genuine
confirmed limitation. The regex-audit agent does NOT decide which.

The report goes to `.claude/notes/regex_audit_<date>.md`. The developer (or
coding-agent, when invoked explicitly) reads it and decides:
1. If it's a regex bug → coding-agent fixes the pattern.
2. If Gemini's test case is wrong → Gemini's coverage_agent updates the asset.
3. If it's a confirmed limitation → coding-agent updates the `[observed]` tag
   in `_regex.py`.

**The boundary:** Claude's regex-audit runs the test suite and writes reports.
All changes to `_regex.py` are made only by the coding-agent, explicitly
invoked after a human reviews the report.

---

## 8. The ArXiv Fidelity Agent

Rename `.claude/agents/testing-agent.md` → `.claude/agents/arxiv-fidelity.md`.
Update the `name:` field from `testing-agent` to `arxiv-fidelity`.
The trigger phrase updates from "Run testing agent" to "Run fidelity agent"
(also accept "Run arXiv fidelity agent").
Role and procedure: **unchanged**.

Update `CLAUDE.md` trigger phrase accordingly.

---

## 9. Handoff Protocol Between Agents

**Deep-dive path** (new construct, comprehensive coverage):
```
1. Gemini triage_agent → surfaces gap → .gemini/notes/
2. Pablo promotes → TODO.md entry
3. Gemini coverage_agent (deep-dive mode) → CTAN research → deep_dive note
                                          → test assets in tests/regex_tests/
4. Claude regex-audit → runs manifests → produces audit report
5. Developer reviews report → invokes coding-agent if needed
6. Claude coding-agent → fixes regex / updates [observed] tags → tests pass
```

**Fast-track path** (known bug or small gap):
```
1. Any source surfaces a bug (arXiv fidelity, triage, direct observation)
2. Gemini coverage_agent (fast-track mode) → adds failing test case to manifest
3. Claude regex-audit (or coding-agent directly) → confirms failure, fixes
```

For the arXiv pipeline path:
```
1. Claude arxiv-fidelity → runs 20 papers → finds unexpected failure → BUGS.md entry
2. Claude coding-agent → fixes → regex test suite updated with the new case
```

---

## 10. What Opus Should Produce

Your job is to implement this redesign by creating or rewriting the agent spec
files. Produce exactly the following files:

### Delete
- `.gemini/agents/macro_coverage_agent.md`
- `.gemini/agents/inclusion_coverage_agent.md`
- `.gemini/agents/researcher/TEMPLATE.md` (superseded by coverage_agent)
- `.gemini/agents/regex_asset_agent.md` (superseded by coverage_agent)
- `.claude/agents/testing-agent.md`

### Create or rewrite
- `.gemini/agents/coverage_agent.md` — new unified spec per §5 (deep-dive +
  fast-track modes; supersedes researcher template and regex_asset_agent)
- `.gemini/agents/regex_audit_agent.md` — rewrite Gemini's version to scope it
  correctly: coverage_agent writes assets; regex_audit_agent is now Claude-only
  (delete the Gemini copy or leave as a stub pointing to coverage_agent)
- `.claude/agents/regex-audit.md` — enhance per §7
- `.claude/agents/arxiv-fidelity.md` — renamed + updated trigger per §8

### Update
- `CLAUDE.md` subagent trigger phrases to match new names

### Do NOT write
- `scripts/test_regex.py` enhancements (Claude will do this interactively)
- `tests/test_regex_suite.py` (Claude will do this interactively)
- Any actual `.tex` test files or manifests (those are Gemini's job, triggered
  separately)

### Note on build artifacts in `tests/regex_tests/`
Add `.aux`, `.log`, `.fls`, `.fdb_latexmk`, `.pdf`, and other latexmk build
artifacts to `.gitignore` for `tests/regex_tests/`. Only `.tex` and
`manifest.json` are committed. Opus should include this `.gitignore` note in
the regex_asset_agent spec.

---

## 11. Constraints and Warnings

- Do NOT change the `coding-agent` or `quarterly-audit` specs.
- The `triage_agent.md` is NOT touched by this redesign — it's already correct.
- The `regex-danger-zone` and `regex-writing` skills remain mandatory for
  Claude's regex-audit agent. Keep those `skills:` frontmatter entries.
- Keep the locking-protocol skill reference in coding-agent and testing agents.
- The `manifest.json` format defined in §4.2 is canonical. All specs that
  reference test assets must reference this format, not invent their own.
- Every new agent spec must include: Trigger phrase, Goal, Input files,
  Output files, Step-by-step procedure, What it does NOT do.
