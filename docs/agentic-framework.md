# texphage — Agentic Framework Reference

_Last updated: 2026-04-11. This document is the canonical reference for the agentic
infrastructure of the texphage project. Read it before brainstorming improvements or
before onboarding as a new contributor._

---

## 1. Project goal and the autonomy model

### What texphage does

texphage is a **LaTeX rearrangement toolbox**: a collection of transformations on LaTeX
source that leave the compiled PDF unchanged. The core insight is that the function
`latex → pdf` is highly non-injective — many distinct `.tex` files produce the same PDF.
texphage exploits the "automorphism group" of this map:

- **demacro** expands preamble macros into a canonical 5-line document
- **unfold** inlines `\input`/`\include` chains into a single flat file
- **xy→tikzcd** converts `xy`-pic diagrams to `tikz-cd` equivalents (in development)
- **pretty-printer** canonically reformats LaTeX source (planned)

Primary use: feeding NLP pipelines (embedding, search, extraction) with normalized LaTeX.

### The fully-autonomous development vision

The goal is a **self-improving repo**: the user describes a transformation they want, and
the agent system implements it, tests it against real-world arXiv papers, finds regressions,
and fixes them — without manual intervention beyond the initial request.

The key loop:

```
User: "I want a <transformation>"
  │
  ├─ Claude implements it (coding-agent or direct)
  │   └─ test-first, playground-verified, regex-safe
  │
  ├─ arxiv-fidelity (weekly auto + manual)
  │   └─ downloads arXiv papers → runs pipeline → diffs PDFs
  │       └─ new bugs → BUGS.md
  │
  ├─ coding-agent ("Fix next bug")
  │   └─ picks highest-severity OPEN bug → fixes → closes
  │
  ├─ triage-agent ("What should we tackle next?")
  │   └─ ranks BUGS.md + TODO.md → verifies with playground → promotes to TODO.md
  │
  ├─ coverage-agent ("Run coverage agent for demacro")
  │   └─ researches LaTeX syntax universe → produces test assets
  │
  └─ quarterly-audit ("Run quarterly audit")
      └─ scans new CTAN packages → finds unrecognised patterns → BUGS.md
```

The human's role is reduced to: (1) describing what transformations they want, and (2) reviewing
the BUGS.md entries that agents cannot self-resolve. Everything else is agent-driven.

---

## 2. Agents (`.claude/agents/`)

All agent specs live in `.claude/agents/`. Each is a Markdown file with YAML frontmatter
declaring `model`, `tools`, and `skills`. Claude Code spawns the appropriate subagent
when a trigger phrase is matched.

### 2.1 `arxiv-fidelity` — Pipeline fidelity tester

| Property | Value |
|----------|-------|
| **Model** | sonnet |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | locking-protocol, failure-taxonomy, playground-protocol, bug-management |
| **Trigger** | "Run fidelity agent", "Run arXiv fidelity agent", "Run fidelity agent on seed N", "Run fidelity agent on IDs ...", "Run fidelity tests on X papers" |

**What it does:**
1. Acquires the agent lock (`tests/runs/.agent.lock`)
2. Samples arXiv papers (default 5, random seed; or specific IDs; can filter by category prefix)
3. Compiles baseline PDFs with `latexmk` (timeout 120s)
4. Runs the texphage pipeline: unfold → demacro → build_minimal_preamble
5. Compiles pipeline output with `latexmk`
6. Compares: compile success, page count delta, text diff, SSIM (visual diff)
7. Diagnoses failures using the failure-taxonomy (Mode A/B/C)
8. Writes new BUGS.md entries with reproduction fixtures in `tests/fixtures/bug_N_*/`
9. Appends a row to `tests/runs/HISTORY.md`
10. Deletes run directories (keeps only HISTORY.md); releases lock

**Token-efficiency notes:**
- Visual diff (SSIM) is expensive: only computed when both PDFs compiled AND page count matches
- Text diff is cheap and always run; SSIM only when text diff is ambiguous
- Run directories are deleted after each session — no large blobs committed

**Output files:**
- `BUGS.md` — new entries with severity, failure mode, seen_in, reproduction
- `tests/fixtures/bug_N_<name>/main.tex` — minimal reproduction
- `tests/runs/HISTORY.md` — one committed row per run

---

### 2.2 `coding-agent` — Bug fixer

| Property | Value |
|----------|-------|
| **Model** | opus |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | locking-protocol, failure-taxonomy, playground-protocol, regex-danger-zone, bug-management |
| **Trigger** | "Fix next bug", "Fix BUG-N" |

**What it does (mandatory protocol, no deviation):**
1. Acquires lock
2. Selects target bug (highest severity OPEN; tie-break by `seen_in` count); marks IN_PROGRESS
3. Gets macro's ground truth from `.sty` source, `texdef`, or CTAN
4. Classifies failure mode precisely (A/B/C) using the pattern probe
5. Runs playground to confirm TeX ground truth (mandatory before writing any test)
6. Writes a **failing test** anchored to playground output (with `# Playground verified:` comment)
7. Fixes the code (surgical changes only; no refactoring)
8. Verifies: `pytest` + playground end-to-end + `expand()` trace with DEBUG logging
9. Re-runs fidelity agent on original arXiv IDs from the bug's `seen_in` list (re-downloads papers)
10. Moves test to `test_pipeline.py`, closes bug, updates `README.md` Known limitations
11. Adds case to `tests/fixtures/regex_torture_test.tex`
12. Releases lock

**Output files:**
- Fixed source in `src/texphage/`
- Test in `tests/test_pipeline.py`
- Updated `BUGS.md` (status → FIXED)
- Updated `README.md` Known limitations
- Commit: `fix(demacro): handle <construct> (BUG-N)`

---

### 2.3 `quarterly-audit` — CTAN pattern scanner

| Property | Value |
|----------|-------|
| **Model** | sonnet |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | bug-management, failure-taxonomy |
| **Trigger** | "Run quarterly audit" |

**What it does:**
1. Fetches recently updated CTAN packages (last 90 days, via CTAN JSON API)
2. Downloads primary `.sty` source for each package
3. Runs `demacro.find_all()` against each; identifies packages with zero matches
4. Computes coverage score for top-50 arXiv math packages
5. Checks high-value target patterns: `\cs_new:Npn`, `\pgfkeys{...}`, `\DeclareOption`, `\keys_define:nn`
6. For any unrecognised pattern found in >3 recent packages: adds BUGS.md entry + fixture

**Never fixes in the same session** — separation of concerns.

**Output files:**
- New `BUGS.md` entries (Severity: MEDIUM, Root cause: unrecognised_definition_pattern)
- `tests/fixtures/audit_<pattern_name>/main.tex`

---

### 2.4 `regex-audit` — Regex pattern auditor

| Property | Value |
|----------|-------|
| **Model** | opus |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | regex-writing, regex-danger-zone, playground-protocol |
| **Trigger** | "Run regex audit" |

**What it does (9-step procedure):**
1. Runs existing manifest test suites via `scripts/test_regex.py`
2. Reads full `_regex.py`; catalogues every named pattern + whether comment blocks are present
3. Audits comment blocks: adds missing MATCHES/CAPTURES/LIMITATIONS/USED BY fields
4. Identifies patterns lacking playground verification
5. Writes playground-backed tests in `tests/test_regex_audit.py`
6. Generates audit report at `docs/notes/regex_audit_<date>.md`
7. Verifies USED BY accuracy via grep
8. Checks for regex patterns outside `_regex.py` (hygiene violation)
9. Checks naming convention compliance (`_RE`, `_PATTERN`, `snake_case`)

**Does NOT auto-fix patterns** — if a pattern is wrong, creates a BUGS.md entry instead.

**Output files:**
- Updated `_regex.py` with complete comment blocks
- `tests/test_regex_audit.py` with playground tests
- `docs/notes/regex_audit_<date>.md` (audit report)

---

### 2.5 `coverage-agent` — LaTeX coverage researcher

| Property | Value |
|----------|-------|
| **Model** | sonnet |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | regex-writing, playground-protocol |
| **Trigger (deep-dive)** | "Run coverage agent for \<tool\> — deep dive" |
| **Trigger (fast-track)** | "Run coverage agent for \<PATTERN_NAME\>" |

**Two modes:**

**Deep-dive mode** — comprehensive periodic review of one tool's LaTeX coverage:
1. Reads `_regex.py`, `<tool>.py`, prior deep-dive notes
2. Researches the full universe of relevant syntax (CTAN docs, TexLive sources, texdoc)
3. Writes `docs/notes/deep-dives/<tool>_deep_dive.md` with gap analysis
4. Produces test assets for all patterns

**Fast-track mode** — quick test generation for a specific pattern after a bug/fix:
1. Reads existing MATCHES/CAPTURES/LIMITATIONS block for the target pattern
2. Produces test assets for that pattern only

**In both modes, produces:**
- `tests/regex_tests/<PATTERN_NAME>/manifest.json`
- `tests/regex_tests/<PATTERN_NAME>/<case_name>.tex`

**Token-efficiency notes:**
- Max 3 CTAN/web lookups per deep-dive session
- Prefer local TexLive (`kpsewhich`) before going to CTAN online
- Can compile `.tex` snippets itself with `latexmk` to validate test cases

**Does NOT modify `_regex.py` or any Python file.**

---

### 2.6 `triage-agent` — Issue prioritiser

| Property | Value |
|----------|-------|
| **Model** | opus |
| **Tools** | Read, Write, Edit, Bash, Glob, Grep |
| **Skills** | bug-management, failure-taxonomy, playground-protocol |
| **Trigger** | "What should we tackle next?", "Triage open issues", "Review priorities" |

**What it does (assess + verify + promote):**
1. Reads BUGS.md (OPEN/PARTIAL), TODO.md (Proposed/Accepted), `docs/notes/deep-dives/` gap analyses
2. Ranks candidates by impact: severity × seen_in count × age
3. Runs playground test for each of top 3 candidates to confirm the issue exists
4. **Promotes confirmed items directly**: writes TODO.md entry with verified test snippet + acceptance criterion
5. Writes full triage report to `docs/notes/triage/triage_<YYYY-MM-DD>.md`

**Promotion rules:**
- Playground confirms issue → write TODO.md entry (with test snippet as acceptance criterion)
- Playground shows no problem → record in report, do NOT promote
- Ambiguous → try 1 more variant, note result, do not promote

**Token-efficiency notes:**
- Max 3 web searches total per session
- Skip web search if BUGS.md + deep-dives already have enough signal

**Output files:**
- Updated `TODO.md` (promoted confirmed items only)
- `docs/notes/triage/triage_<YYYY-MM-DD>.md` (full ranked list + playground results)

---

## 3. Skills (`.claude/skills/`)

Skills are reusable knowledge modules loaded lazily — only when an agent or the main
context explicitly loads them. Each skill is a `.claude/skills/<name>/SKILL.md` file.

### 3.1 `bug-management`

**Loaded by:** coding-agent, arxiv-fidelity, triage-agent, quarterly-audit

**Contains:**
- BUGS.md entry format (all mandatory fields: severity, root_cause_pattern, failure_mode, seen_in, ...)
- `demacro_report.json` schema (fields: name, position, reason, definition_pattern, context)
- Bug lifecycle states: OPEN → IN_PROGRESS → PARTIAL → FIXED
- TODO.md vs BUGS.md distinction (bugs = regressions with reproduction; TODOs = features)
- Duplicate-check protocol (update existing entry if same pattern + context)
- Fixture creation rule (every bug needs `tests/fixtures/bug_N_<name>/main.tex`)
- Commit message format: `fix(demacro): handle <construct> (BUG-N)`
- 9 non-negotiable safety rules

---

### 3.2 `failure-taxonomy`

**Loaded by:** coding-agent, arxiv-fidelity, quarterly-audit, triage-agent

**Contains:**

| Mode | Definition | Signal | Fix location |
|------|-----------|--------|--------------|
| **A** | `_FIND_ALL_RE` doesn't match definition | `pattern_mismatch` in demacro_report | `_FIND_ALL_RE` in `_regex.py` |
| **B** | Definition found but expansion wrong | Macro IS in macro_dict but output wrong | `build_dictionary()`, `content_replacement()`, or `expand()` |
| **C** | Preprocessing corrupts source | Content mangled in verbatim-like env | `_VERBATIM_ENVS` in `demacro.py` |

Also contains: pattern probe code templates, diagnostic paths for each mode,
multi-macro interaction testing protocol.

---

### 3.3 `locking-protocol`

**Loaded by:** arxiv-fidelity, coding-agent

**Contains:**
- Lock file path: `tests/runs/.agent.lock`
- On startup: if exists + < 4 hours old → abort; if > 4 hours → delete (stale) + proceed; if absent → create
- Release: always in `finally` block
- Purpose: prevents two parallel agent sessions from corrupting the same run directories

---

### 3.4 `playground-protocol`

**Loaded by:** coding-agent, regex-audit, coverage-agent, triage-agent

**Contains:**
- The oracle contract: every test assertion must be grounded in `scripts/latex_playground.py` output
- Templates:
  - **A** — expansion check (does `expand(body)` produce expected text?)
  - **C** — batch verification (run multiple snippets, check all pass)
  - **D** — variant characterisation (compare starred vs. unstarred, optional vs. required arg, etc.)
  - **E** — preprocessing invariant check
  - **F** — compile-and-extract (run full latexmk, extract PDF text)
- Note: Template B (pattern probe) lives in `failure-taxonomy`

---

### 3.5 `regex-danger-zone`

**Loaded by:** coding-agent, regex-audit

**Contains:**
- Mandatory rules before touching `_regex.py` or `demacro.py`
- Never rename named capture groups (breaks every caller)
- Never reorder the `build_dictionary()` elif-chain (order is semantic)
- Always add MATCHES/CAPTURES/LIMITATIONS comment block first (separate commit)
- Run the torture test (`tests/fixtures/regex_torture_test.tex`) after any change
- Documents the `ruff: noqa` annotations and why they must not be removed

---

### 3.6 `regex-writing`

**Loaded by:** coding-agent (when writing a new pattern), coverage-agent

**Contains:**
- Naming conventions: `_UPPER_SNAKE_CASE_RE` for compiled patterns, `_PATTERN` for raw strings, `snake_case` for builder functions
- Section placement in `_regex.py`
- Mandatory comment block format:
  ```python
  # MATCHES:   what LaTeX construct this matches
  # CAPTURES:  named group → what it captures
  # LIMITATIONS: [observed] / [inferred] edge cases
  # USED BY:   which functions in demacro.py / unfold.py use this
  ```
- Sub-pattern reuse guidelines
- The preprocessing invariant: patterns assume whitespace has been collapsed to single spaces

---

### 3.7 `orient`

**Loaded by:** Anyone starting a major new effort

**Contains:**
- Instruction to read `docs/EVOLUTION.md` in full before starting
- Run `git log --oneline -20`
- Check `BUGS.md` for related open bugs
- Summarize: current phase, recent work, established constraints, relevant open bugs

---

### 3.8 `write-note`

**Loaded by:** Main context, any agent wanting to capture working notes

**Contains:**
- Output path: `docs/notes/<descriptive_slug>.md`
- Rule: update existing file if relevant one exists; create new file otherwise
- What does NOT go in notes: bugs → BUGS.md, enhancements → TODO.md, memory → memory system

---

## 4. Scripts (`scripts/`)

### `scripts/latex_playground.py` — TeX oracle

**Purpose:** Compile a `.tex` snippet and inspect the output. The ground-truth oracle for
all test assertions — never assert what TeX should do without running this first.

**Used by:** playground-protocol skill (all agents that load it); coding-agent; coverage-agent; triage-agent

**Python API:**
```python
from scripts.latex_playground import compile_snippet

result = compile_snippet(r'''
    \newcommand{\greet}[1][World]{Hello, #1!}
    \greet   \greet[Alice]
''')
print(result.ok)        # True if compiled successfully
print(result.pdf_text)  # extracted text from the output PDF
print(result.log)       # full latexmk log
```

**CLI:**
```bash
python scripts/latex_playground.py --body '\textbf{hello}'
python scripts/latex_playground.py --file my_test.tex
```

**Cost:** Requires `latexmk` + TeX Live. Each call compiles a full PDF — use judiciously.
One compile per assertion, not one per agent session.

---

### `scripts/test_fidelity.py` — Pipeline fidelity harness

**Purpose:** Download arXiv papers, run the full texphage pipeline, compare baseline vs.
pipeline PDFs (compile success, page count, SSIM, text diff).

**Used by:** arxiv-fidelity agent

**CLI:**
```bash
python scripts/test_fidelity.py --seed 42           # 5 papers, random seed
python scripts/test_fidelity.py --seed 42 --n 10    # 10 papers
python scripts/test_fidelity.py --ids 2401.12345 2312.09876   # specific IDs
python scripts/test_fidelity.py --seed 42 --keep-runs          # don't delete run dirs
python scripts/test_fidelity.py --seed 42 --category math      # filter by category
```

**Output:**
- `tests/runs/<run_id>/` (deleted by default; preserved with `--keep-runs`)
- `tests/runs/<run_id>/demacro_report.json` — per-paper pipeline diagnostics
- `tests/runs/<run_id>/pipeline.log` — DEBUG-level pipeline log
- `tests/runs/results.jsonl` — append-only success/failure log (for success_rate.py)

---

### `scripts/test_regex.py` — Single-pattern regex tester

**Purpose:** Test one regex pattern from `_regex.py` against one `.tex` file, applying
the full preprocessing contract. Used by the manifest-driven test suite.

**Used by:** regex-audit agent; `pytest` test runner (indirectly via test_pipeline.py)

**CLI:**
```bash
python scripts/test_regex.py _NEW_COMMAND_RE tests/regex_tests/NEW_COMMAND/basic.tex
```

**Behavior:**
1. Compiles the `.tex` file to verify it is valid LaTeX
2. Applies preprocessing (protect verbatim → strip comments → collapse whitespace → ...)
3. Runs the named pattern against the preprocessed preamble
4. Prints match/captures or "no match"

---

### `scripts/success_rate.py` — Pipeline success rate tracker

**Purpose:** Read the append-only `tests/runs/results.jsonl` log and report the rolling
success rate, per-failure-mode breakdown, and batch trend.

**CLI:**
```bash
python scripts/success_rate.py                 # last 20 papers
python scripts/success_rate.py --window 50     # last 50 papers
python scripts/success_rate.py --batches 10    # trend over last 10 batches
```

**Success definition:** severity == 'OK' (zero/negligible text diff, SSIM ≥ 0.95, correct page count).

---

### `scripts/extractor.py` — PDF text extraction utilities

**Purpose:** Wraps `pdftotext` and `pdfplumber` for reliable PDF text extraction. Used
internally by `test_fidelity.py` and the playground.

---

### `scripts/xy_to_tikz.py` — xy→tikzcd converter (in development)

**Purpose:** Standalone converter from `xy`-pic diagrams to `tikz-cd` equivalents.
See `docs/notes/xy_to_tikz_implementation.md` for implementation notes.

---

## 5. Test infrastructure

### `tests/test_pipeline.py`

Unit + integration tests for the full pipeline. Tests are anchored to playground-verified
expected outputs (every test includes a `# Playground verified:` comment). Requires
`latexmk` for pipeline tests; skip with `-k "not pipeline"`.

```bash
pytest tests/ -v                        # all tests
pytest tests/ -v -k "not pipeline"      # skip TeX-dependent tests
pytest tests/ -v -k "test_bug_26"       # single test
```

### `tests/regex_tests/`

Manifest-driven regex tests. One directory per pattern name:

```
tests/regex_tests/
└── NEW_COMMAND/
    ├── manifest.json          # test cases + expected captures
    ├── basic_newcommand.tex   # minimal valid snippet
    ├── starred_variant.tex
    └── optional_arg_absent.tex
```

`manifest.json` format:
```json
{
  "pattern": "NEW_COMMAND",
  "description": "...",
  "target": "preprocessed_preamble",
  "cases": [
    {
      "file": "basic_newcommand.tex",
      "description": "Basic \\newcommand",
      "compilation": "required",
      "expect": "match",
      "captures": {"name": "\\foo", "nargs": "2", "body": "#1 + #2"}
    }
  ]
}
```

`target` field: `"preprocessed_preamble"` (most patterns), `"preprocessed_body"`, or `"raw"` (unfold patterns).

### `tests/fixtures/`

One fixture directory per closed bug: `tests/fixtures/bug_N_<short_name>/main.tex`.
These are regression tests — if the pipeline breaks them again, `pytest` catches it.

### `tests/runs/HISTORY.md`

Committed log of every arxiv-fidelity run. Format:
```
| Date | Seed | Papers | Bugs found |
|------|------|--------|------------|
| 2026-03-25 | 42 | 5 | BUG-26, BUG-27, BUG-28 |
```

`tests/runs/` itself is gitignored (large run dirs); only `HISTORY.md` is committed via
`.gitignore` exception (`!tests/runs/HISTORY.md`).

---

## 6. Tracking files

| File | Purpose | Who writes |
|------|---------|-----------|
| `BUGS.md` | OPEN/IN_PROGRESS regressions | arxiv-fidelity, quarterly-audit (creates); coding-agent (closes) |
| `docs/FIXED_BUGS.md` | Read-only archive of resolved bugs | coding-agent (moves entries here) |
| `TODO.md` | Planned features and enhancements | triage-agent (promotes confirmed items); human |
| `docs/EVOLUTION.md` | Architectural decision log | Human only |
| `docs/user_applications.md` | Catalogue of all current and planned tools | Human + coding-agent (after milestones) |
| `docs/notes/deep-dives/` | Per-tool LaTeX coverage analysis | coverage-agent |
| `docs/notes/triage/` | Dated prioritisation reports | triage-agent |
| `docs/notes/` | Working notes, implementation plans | write-note skill; human |
| `tests/runs/HISTORY.md` | Fidelity run history | arxiv-fidelity |

### The `[observed]` / `[inferred]` tagging convention

Every bullet in a `LIMITATIONS` block in `demacro.py` or `unfold.py` carries a tag:

- `[observed]` — empirically verified (playground, texdef, filesystem test). Only Claude agents can write/modify these.
- `[inferred]` — derived from documentation or code reading, not tested. May be added by coverage-agent.

If an `[inferred]` line is tested and confirmed, upgrade it to `[observed]`.

---

## 7. Token efficiency principles

**Critical constraints** — these are not preferences, they are architectural requirements:

### 7.1 Visual diff (SSIM) — expensive
- SSIM is only computed when **both** baseline and pipeline PDFs compiled successfully
  **and** page count matches.
- If page count differs → that IS the confirmed bug; SSIM adds no information. Skip.
- If compile failed → skip SSIM. Record compile failure as the bug.

### 7.2 Web searches — hard cap
- **3 searches maximum per agent session**, total.
- Prefer local TexLive (`kpsewhich <pkg>.sty`) before going to CTAN online.
- Prefer CTAN source files over documentation web pages (more machine-readable).
- If BUGS.md + deep-dive notes already cover the question, skip the search entirely.

### 7.3 Image reads — narrow use
- Only for PDF visual diff (comparing rendered pages).
- Never for routine file inspection, source reading, or log analysis.

### 7.4 Model choice — match complexity to cost
| Task | Model | Reason |
|------|-------|--------|
| Bug fixing, triage, regex work | **opus** | Requires careful multi-step reasoning |
| Fidelity testing, quarterly audit, coverage research | **sonnet** | Throughput tasks; pattern recognition |

### 7.5 Compile budget
- Each `latex_playground.py` call compiles a full PDF. Budget: max ~10 compile calls per agent session.
- Batch test assertions (Template C) instead of one call per assertion.
- Cache playground results within a session where the same snippet is tested twice.

---

## 8. Collaborator onboarding

### Prerequisites

```bash
# Python deps
pip install -e ".[agents]"

# System deps (macOS)
brew install --cask mactex && brew install poppler

# System deps (Linux)
sudo apt install texlive-full poppler-utils texlive-extra-utils
```

Required system tools: `latexmk`, `kpsewhich`, `pdftoppm`, `pdfinfo`, `texdef`, `pdftotext`

Verify setup (no TeX required):
```bash
pytest tests/ -v -k "not pipeline"
```

### Everything is in the repo

All agent specs (`.claude/agents/`), skills (`.claude/skills/`), and scripts (`scripts/`)
are committed. No user-specific configuration is needed. Opening the repo in Claude Code
is sufficient to use all agents.

### Using agents

In a Claude Code session, type the trigger phrase:
- `"Run fidelity agent"` → arxiv-fidelity downloads and tests 5 random papers
- `"Fix next bug"` → coding-agent picks the highest-severity OPEN bug and fixes it
- `"What should we tackle next?"` → triage-agent ranks and promotes confirmed items
- `"Run coverage agent for demacro — deep dive"` → coverage-agent researches gaps
- `"Run quarterly audit"` → quarterly-audit scans new CTAN packages
- `"Run regex audit"` → regex-audit validates all patterns in `_regex.py`

### Standard CI check

Run after every change before committing:
```bash
pytest tests/ -v && ruff check src/ && mypy src/texphage/
```

---

## 9. Architecture principles

These are the "Intentional Non-Decisions" that shape the design. Read `docs/EVOLUTION.md`
for the full history.

1. **No full TeX interpreter.** texphage uses regex, not a TeX parser. This is a deliberate
   trade-off: complete coverage is impossible, but 90%+ coverage of real arXiv papers is
   achievable with manageable complexity. Mode A bugs (missed patterns) are the expected cost.

2. **`regex` over `re`.** The `regex` package (not stdlib `re`) is non-negotiable: recursive
   named groups (`(?&name)`) enable balanced-brace matching without a parser. Replacing
   `import regex as re` with `import re` would silently break all `\{…\}` argument capture.

3. **Preprocessing invariant.** All patterns assume the 6-step preprocessing contract has run
   (whitespace collapsed to single space, verbatim protected, comments stripped). Never write
   a pattern that relies on multi-space or newline separation.

4. **Reactive preamble preservation.** `build_minimal_preamble` only adds preservation rules
   when empirically proven necessary. No speculative preservation.

5. **Test-first, playground-anchored.** No code fix without a failing test. No test assertion
   without a playground-verified expected output.

6. **Agents own observation; skills own knowledge.** Agents are procedural (what to do).
   Skills are knowledge modules (how to reason). Neither overlaps with the other.
