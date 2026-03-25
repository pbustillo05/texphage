# Agentic Workflow: Deep-Dive Analysis and Improvement Notes

_Written March 2026. Covers the Claude + Gemini dual-agent system as of the
`20c495a` commit (docs/workflow: establish Claude–Gemini agentic collaboration
framework). Also audits what from the deprecated `AGENTS.md` has been
translated and what has not._

---

## 1. Big picture: the two-agent architecture

The repo uses two AI assistants with complementary, non-overlapping roles:

| Aspect | Claude | Gemini |
|---|---|---|
| Role | Engineer — code, tests, debugging, investigation | Critic/architect/researcher — LaTeX expertise, gap analysis, ROI ranking |
| Entry point | `CLAUDE.md` (always-on) | `GEMINI.md` (always-on) |
| Agent specs | `.claude/agents/*.md` | `.gemini/agents/*.md` |
| Reusable knowledge | `.claude/skills/*.md` (lazy-loaded) | `.gemini/notes/*.md` (personal scratchpad) |
| Write access | Everything (but reads Gemini's outputs) | BUGS.md, TODO.md, macros.md, inclusions.md, .gemini/\*\*, `[inferred]` comment lines only |
| Code access | Full read + write | Zero — cannot touch Python, regex, tests, docs |
| Oracle | `latex_playground.py` (TeX ground truth) | Documentation + web + CTAN source |

The coordination channel is narrow and intentional: Gemini writes
structured entries to BUGS.md / TODO.md / macros.md / inclusions.md with
enough detail that Claude can act without asking questions. Claude writes
`[observed]` lines to limitation blocks; Gemini writes `[inferred]` lines.
Neither overwrites the other.

---

## 2. Claude's side — agents and skills

### 2a. Agents (`.claude/agents/`)

Three subagents, each as a `.md` file with frontmatter declaring `model`,
`tools`, and `skills`:

**`testing-agent`** (model: sonnet)
- Triggered by: "Run testing agent [on seed N / on IDs …]"
- Downloads 5 arXiv papers (2×math.CT, 2×math.AT, 1×cs.LO/math.AG),
  compiles baselines, runs pipeline, compares PDFs (compilation, page count,
  SSIM, text diff), diagnoses failures using the failure-taxonomy, writes
  BUGS.md entries, cleans up run directories.
- Skills loaded: failure-taxonomy, playground-protocol, bug-management

**`coding-agent`** (model: opus)
- Triggered by: "Fix next bug" or "Fix BUG-N"
- Selects highest-severity OPEN bug, runs texdef, classifies failure mode,
  verifies ground truth via playground, writes a failing test, fixes the
  code, verifies with pytest + linters, re-runs testing agent on original
  papers, closes the bug.
- Skills loaded: failure-taxonomy, playground-protocol, regex-danger-zone,
  bug-management

**`quarterly-audit`** (model: sonnet)
- Triggered by: "Run quarterly audit"
- Fetches recently-updated CTAN packages, runs find_all against them, checks
  for unrecognised patterns, computes coverage scores for top-50 arXiv math
  packages, writes BUGS.md entries + fixtures for patterns found in >3 packages.
- Skills loaded: bug-management, failure-taxonomy
- Never fixes in the same session as the audit — separation of concerns.

### 2b. Skills (`.claude/skills/`)

Four knowledge modules, loaded lazily (only when an agent declares them or
Claude explicitly loads them):

**`failure-taxonomy`** — The three-mode taxonomy (A: recognition, B: expansion,
C: preprocessing), full diagnostic paths for each error type including the
pattern probe code. This is the mental model every bug-fixing session starts from.

**`playground-protocol`** — The oracle contract: every test assertion must be
grounded in `compile_snippet` output. Contains Templates A (expansion check),
C (batch verification), D (variant characterisation). The `doc()` helper is
defined here.

**`regex-danger-zone`** — Mandatory rules before touching `_regex.py` or
`demacro.py`: don't rename groups, don't reorder the elif chain, always add
MATCHES/CAPTURES/LIMITATIONS comment first, commit that separately, run the
torture test. Also documents the ruff-ignore rationale so agents don't "fix"
intentional suppressions.

**`bug-management`** — BUGS.md entry format, TODO.md vs BUGS.md distinction,
fixture creation rule, duplicate-check protocol, commit message format, bug
lifecycle states, and the nine non-negotiable safety rules.

### 2c. CLAUDE.md always-on context

Contains: role statement, debugging hierarchy (texdef → playground → visual
diff → CTAN source), subagent trigger phrases, always-on rules (test-first,
regex comment block, no runs/ commits, full CI before commit), and the
[observed]/[inferred] tagging convention.

---

## 3. Gemini's side — agents and notes

### 3a. Agent specs (`.gemini/agents/`)

**`macro_coverage_agent`**
- Triggered by: "Update macros.md" or "Run macro coverage agent"
- Reads demacro.py + _regex.py thoroughly, builds a precise coverage
  inventory, optionally adds [inferred] limitation bullets to demacro.py,
  classifies all macro-definition commands as COVERED/PARTIAL/NOT COVERED,
  priority-ranks gaps by arXiv ROI, writes macros.md (Part 1: implemented
  table, Part 2: not-covered in priority order, Part 3: out of scope).
- Key constraint: architectural notes only — no regex syntax, no Python code.

**`inclusion_coverage_agent`**
- Triggered by: "Update inclusions.md" or "Run inclusion coverage agent"
- Same structure as macro coverage agent but for unfold.py / `_FIND_INPUT`.
- Categorises file-inclusion directives into A (content, unfold), B (verbatim,
  never unfold), C (assets, out of scope), D (package loading, partial).
- Optionally adds [inferred] bullets to unfold.py LIMITATIONS block.

### 3b. Notes (`.gemini/notes/`)

Gemini's personal scratchpad. Half-formed research, patterns noticed but not
yet ready for BUGS.md or TODO.md. The `macro_coverage_agent_design.md` note
documents key design decisions made during the Phase 0-6 refactor (and
confirms it was superseded by the definitive agent spec).

### 3c. GEMINI.md always-on context

Contains: role statement, full write-access rules (8 items with exact
constraints), the [observed]/[inferred] tagging convention mirroring CLAUDE.md,
agent trigger phrases, and common analysis triggers with expected output
locations.

---

## 4. Information flow and coordination protocol

```
Gemini research session
  │
  ├─ High confidence bug with repro snippet → BUGS.md (entry)
  │                                           tests/fixtures/bug_N_*/main.tex
  │
  ├─ Scoped enhancement with acceptance criterion → TODO.md (entry)
  │
  ├─ Coverage gap analysis → macros.md / inclusions.md
  │
  ├─ Half-formed / in-progress → .gemini/notes/<topic>.md
  │
  └─ [inferred] limitation discovered → [inferred] bullet in demacro.py / unfold.py
       │
       └─ Claude sees it, tests it empirically, upgrades to [observed] if confirmed

Claude acting on Gemini's output
  │
  ├─ "Fix BUG-N" → coding-agent → playground oracle → failing test → fix → FIXED
  │
  ├─ "Run testing agent" → testing-agent → new BUGS.md entries
  │
  └─ "Run quarterly audit" → quarterly-audit → new BUGS.md entries
```

The pipeline is **unidirectional** at the code level: Gemini feeds Claude,
not the other way around. The shared state is the tracked files (BUGS.md,
TODO.md, macros.md, inclusions.md) and the source comments.

---

## 5. Translation audit: what from AGENTS.md went where

AGENTS.md (now deprecated) was a 885-line monolith containing everything.
Here is a line-by-line accounting of where each section landed:

| AGENTS.md section | New home | Status |
|---|---|---|
| Always-on rules (test-first, regex comment, no runs/, CI) | CLAUDE.md `## Always-on rules` | ✓ translated |
| Failure Mode Taxonomy (A/B/C) with signal/fix-location | `failure-taxonomy` SKILL.md | ✓ translated + improved (pattern probe code added) |
| Locking Protocol | `testing-agent.md` + `coding-agent.md` | ✓ translated (duplicated in both, see §6c below) |
| TODO.md vs BUGS.md distinction | `bug-management` SKILL.md | ✓ translated |
| Testing Agent procedure (Steps 1–10) | `testing-agent.md` | ✓ translated; improved with skill references |
| Coding Agent procedure (Steps 1–7) | `coding-agent.md` | ✓ translated; improved with explicit skill-load instruction |
| Playground Templates A/C/D | `playground-protocol` SKILL.md | ✓ translated |
| Template B (pattern probe) | `failure-taxonomy` SKILL.md | ✓ translated (lives in diagnostic paths, not playground protocol — correct placement) |
| Quarterly Pattern Audit | `quarterly-audit.md` | ✓ translated |
| DANGER ZONE rules | `regex-danger-zone` SKILL.md | ✓ translated |
| Safety Rules (9 rules) | `bug-management` SKILL.md | ✓ translated |
| Run Directory Structure | `testing-agent.md` | ✓ translated |
| System Dependencies | `docs/project-context.md` `## System dependencies on PATH` | ✓ translated |
| Testing History table | **NOT translated** | ✗ orphaned (see §6a) |
| Advanced Agent Capabilities — RAG pipeline vision | **NOT translated** | ✗ orphaned (see §6b) |
| Advanced Agent Capabilities — Coverage dashboard | **NOT translated** | ✗ orphaned (see §6b) |

---

## 6. What is NOT yet translated / orphaned ideas

### 6a. Testing history table (AGENTS.md lines 874–884)

The table tracking which seeds have been used, dates, and bug counts has no
permanent home in the new framework. It's important for two reasons:

1. **Seed reuse prevention.** The table explicitly notes "Do not reuse a seed —
   the goal is broad coverage." Without the table, there's no record of which
   seeds have been tried. A future testing-agent run will not know to avoid seed
   42 or seed 7.

2. **Progress tracking.** The bug counts per run give a sense of convergence —
   are we finding fewer bugs per run over time?

**Recommendation:** Create `tests/runs/HISTORY.md` (committed, unlike
`tests/runs/<run_id>/`). The testing-agent's Step 8 / commit step should append
a row to this file. The file is in `.gitignore`'s parent directory but explicitly
committed (like `tests/fixtures/`). Alternatively, it could live in the repo root
as `TESTING_HISTORY.md`. Either way, it needs to exist as a dedicated committed
file — not inside a transient run directory.

### 6b. Advanced agent capabilities — RAG pipeline and coverage dashboard

AGENTS.md (lines 824–852) contained two "future vision" items:

**RAG pipeline for LaTeX package sources:**
The idea: vector-index CTAN `.sty` sources by macro definition, so that Mode A
failures (`undefined_control_sequence \foo`) can be diagnosed by querying the
vector DB with the macro name and getting back its exact definition. This would
transform Mode A from "look it up manually" to "retrieve automatically."

**Coverage dashboard:**
A persistent JSON tracking `{package: {total_defs, matched_defs, pct_covered}}`
updated after each quarterly audit, letting the user see improvement over time.

Neither of these is currently referenced in CLAUDE.md, GEMINI.md, any agent
spec, or any TODO.md entry. They're **orphaned**.

**Recommendation:** These belong in `TODO.md` as separate entries under a
"Future / Infrastructure" section, not as bugs. Gemini should formally triage
them with acceptance criteria and arXiv-ROI priority when capacity allows.

### 6c. Locking protocol duplication

The locking protocol (check/create/delete `tests/runs/.agent.lock`) is
duplicated verbatim in `testing-agent.md` and `coding-agent.md`. This is minor
but creates a maintenance hazard — if the protocol changes (e.g., the 4-hour
staleness threshold), both files must be updated in sync.

**Recommendation:** Extract to a `locking-protocol` skill. Both agents declare
it in their `skills:` frontmatter. The protocol content lives in one place.

### 6d. `demacro_report.json` schema not documented as a skill

The testing-agent.md Step 4 defines what `demacro_report.json` must contain:
`name`, `position`, `reason`, `definition_pattern`, `context`. The
`definition_pattern` and `context` fields are important for self-diagnosing
reports. But this schema is only in testing-agent.md. When the coding-agent
reads an existing run's report (Step 5.75), it must infer the schema from
context.

**Recommendation:** This belongs either as a skill
(`report-schema` or appended to `bug-management`) or as a docstring in
`pipeline.py` adjacent to the code that writes the report.

---

## 7. Structural observations on the new framework

### 7a. What the refactor got right

**Separation of concerns.** The monolith AGENTS.md mixed procedure (what to do),
knowledge (failure taxonomy, regex rules), and config (system deps, run structure).
The new split into agents (procedural) + skills (knowledge modules) is clean and
scalable. Adding a new skill doesn't require editing every agent.

**Lazy loading.** Skills are loaded on demand via the `skills:` frontmatter
declaration. The failure-taxonomy isn't in context during a routine conversation —
it's only loaded when an agent starts a bug-fixing session. This is good context
hygiene.

**Model selection per agent.** coding-agent uses `opus` (harder reasoning for
bug classification and regex work), testing-agent and quarterly-audit use
`sonnet` (throughput tasks). This is a meaningful distinction.

**The [observed]/[inferred] tagging system.** This is the most important
architectural element for long-term correctness. It creates an epistemic audit
trail in the source code: every LIMITATIONS bullet carries a provenance tag
readable by any future agent or human. Gemini cannot silently overwrite Claude's
empirically-verified facts. The rule is enforced in both CLAUDE.md and GEMINI.md
with identical text — good.

**Gemini write-access constraints.** The constraint that Gemini cannot write
Python code is not just a preference — it's a correctness guarantee. Gemini
does not run the playground, cannot check its own claims against TeX reality,
and therefore cannot own `[observed]` facts. The architectural note format
(describe the structure, not the code) in macro_coverage_agent.md is a good
operationalisation of this constraint.

**Self-diagnosing demacro_report.json.** The requirement that `demacro_report.json`
include `definition_pattern` and `context` around each problematic macro means
a fresh agent session can diagnose a bug without re-running the pipeline. This
is good design for async workflows where the testing-agent runs, logs a report,
and the coding-agent picks it up later.

### 7b. Potential friction points

**The Gemini trigger gap.** GEMINI.md lists "common analysis triggers" like
"What should we tackle next?" as informal prompts, but they don't have formal
agent specs the way "Update macros.md" does. The output goes to
`.gemini/notes/`. This is fine for exploratory research, but the line between
"ready for BUGS.md" and "still in notes" can be unclear.

Consider adding a lightweight `triage-agent` spec for Gemini: given the current
BUGS.md and TODO.md, produce a priority-ordered recommendation to `.gemini/notes/`
with explicit go/no-go criteria for promotion. This would give the "What should
we tackle next?" trigger the same structured output as the coverage agents.

**No handoff skill.** There's no skill documenting _how Gemini should write
BUGS.md entries_ to ensure Claude can act without questions. The bar is stated
("high bar: concrete reproduction and acceptance criterion") but the mechanics
are implicit. The `bug-management` skill covers Claude's side (reading/updating
entries) but not Gemini's side (writing them). GEMINI.md should reference
`bug-management` explicitly, or Gemini should declare it as a skill.

**Testing-agent Step 5.75 is underspecified in coding-agent.** The coding-agent's
Step 5.75 says "Re-run the testing agent on the arXiv IDs from the bug's `seen_in`
list." But the arXiv IDs may no longer be cached locally — they were cleaned up.
The agent needs to re-download them. The step doesn't mention this explicitly,
which could cause a confusing failure mode (passing unit tests, no cached papers
to test against).

**inclusions.md is missing from the GEMINI.md write-access list header** (the
numbered list) — it's mentioned only in the text below as "same structure as
macros.md". This is a minor documentation inconsistency: line 40 in GEMINI.md
says `inclusions.md` but the write-access section ends at item 7 (`unfold.py`).
Actually re-reading: line 36 does list it as item 6. So it is there — but it's
easy to miss since the numbered list has 8 items and the last two (demacro.py,
unfold.py) have strong warnings. No action needed, just noting it.

---

## 8. Recommendations (prioritised)

_All recommendations below were implemented in the same session this document
was written. The table in §10 reflects the post-implementation state._

### HIGH — should do soon ✓ DONE

**H1. Add `tests/runs/HISTORY.md`.** ✓
Created with historical data from AGENTS.md. `.gitignore` updated with
`!tests/runs/HISTORY.md`. testing-agent.md updated with Step 8.5 to append
a row and include it in the run commit.

**H2. Move RAG pipeline and coverage dashboard to TODO.md.** ✓
Two `[INFRASTRUCTURE]` entries added to `TODO.md` with acceptance criteria and
priority justification.

**H3. Gemini agents updated re: BUGS.md.** ✓ (superseded by user feedback)
Instead of just adding `bug-management` as a skill, Gemini was prohibited from
creating BUGS.md entries entirely (see §user-changes below). Both Gemini agent
specs updated with explicit constraints.

### MEDIUM — worth doing when convenient ✓ DONE

**M1. Extract locking protocol to a skill.** ✓
`.claude/skills/locking-protocol/SKILL.md` created. Both testing-agent.md and
coding-agent.md updated to declare it and reference it instead of inline text.

**M2. Document `demacro_report.json` schema.** ✓
Added to `bug-management` skill under "Who may create BUGS.md entries" and a
new schema table.

**M3. Add re-download note to coding-agent Step 5.75.** ✓
coding-agent.md Step 5.75 now explains that run directories were deleted and
papers must be re-downloaded by passing IDs to the testing agent.

**M4. Add `triage-agent` spec for Gemini.** ✓
`.gemini/agents/triage_agent.md` created with structured procedure. GEMINI.md
`## Agent triggers` section updated with the new trigger phrases.

### LOW — nice to have ✓ DONE

**L1. Playground Template B cross-ref.** ✓
playground-protocol SKILL.md now opens with a note that Template B lives in
failure-taxonomy.

**L2. `README.md` Known limitations in CLAUDE.md.** ✓
Added to `## Always-on rules` in CLAUDE.md.

**L3. GEMINI.md trigger phrase consistency.** ✓
All trigger phrases in the new GEMINI.md use consistent quoting.

---

## 8b. User-requested changes (implemented alongside §8)

### Gemini cannot create BUGS.md entries

**Rationale (user):** A bug is something *observed through testing*. Gemini
cannot run code or compile TeX, so it cannot observe anything — it can only
*infer*. If Gemini finds something that looks wrong, the right output is a
note in `.gemini/notes/` with a test snippet, not a BUGS.md entry.

**What changed:**
- GEMINI.md `## Write access` section: BUGS.md removed from the list entirely.
- New section `## BUGS.md — read-only, with one exception`: explains the rule,
  permits adding a `**latex_analysis**:` field to existing entries only.
- `## What you must NOT do` updated to include: "Create new BUGS.md entries."
- Both `.gemini/agents/macro_coverage_agent.md` and
  `.gemini/agents/inclusion_coverage_agent.md`: added explicit "Important
  constraint" block at the top.
- `bug-management` skill: added "Who may create BUGS.md entries" section.

**What Gemini should do instead:** Write to `.gemini/notes/` with a concrete
test snippet, ask Claude to run it, and only after Claude confirms the failure
does Claude create the BUGS.md entry.

### Higher bar for Gemini's TODO.md entries

**Rationale (user):** Writing "high bar" as a phrase is not the same as
actually having a high bar. Gemini should check, double-check, suggest tests
first, and only after Claude runs them should it suggest a formal TODO entry.

**What changed:**
- GEMINI.md `## Write access` list: TODO.md now has an explicit gate
  annotation: "only after completing the two-step vetting process (see below)."
- New section `## The two-step vetting process for TODO.md`: replaces the old
  "The bar for writing to BUGS.md or TODO.md is high" paragraph with a three-
  step concrete gate: (1) notes-first always, (2) ask Claude to run the test,
  (3) promote only on confirmed evidence.
- Coverage agents exception: macro/inclusion coverage agents may write HIGH-
  priority TODO entries directly *if* they include a concrete test snippet as
  acceptance criterion — their source-code analysis is itself empirical.
- Common analysis triggers: updated to explicitly say "Do NOT promote to
  TODO.md in this session" for ad-hoc research.
- New `triage_agent.md`: includes the rule that it outputs to `.gemini/notes/`
  only, never to TODO.md.

---

## 9. AGENTS.md deprecation status

All _operational_ content from AGENTS.md has been translated. The deprecated file
should remain as-is (it has the `# DEPRECATED — see CLAUDE.md and .claude/agents/`
header), but **two pieces of future-vision content have not been formally
migrated**:

1. The **Testing History table** → migrate to `tests/runs/HISTORY.md` (H1 above)
2. The **Advanced Agent Capabilities section** → migrate to `TODO.md` entries (H2 above)

Once H1 and H2 are done, AGENTS.md can be deleted or reduced to a one-line
pointer. Until then, it serves as the only record of those two items.

---

## 10. Summary table: agent framework completeness

_State after implementing all recommendations and user-requested changes._

| Component | Exists | Complete | Notes |
|---|---|---|---|
| Claude testing-agent | ✓ | ✓ | HISTORY.md step added; locking-protocol skill |
| Claude coding-agent | ✓ | ✓ | Re-download note added; locking-protocol skill |
| Claude quarterly-audit | ✓ | ✓ | |
| Claude failure-taxonomy skill | ✓ | ✓ | |
| Claude playground-protocol skill | ✓ | ✓ | Template B cross-ref added |
| Claude regex-danger-zone skill | ✓ | ✓ | |
| Claude bug-management skill | ✓ | ✓ | Report schema added; Gemini write-access note |
| Claude locking-protocol skill | ✓ | ✓ | Extracted from agents |
| Gemini macro_coverage_agent | ✓ | ✓ | BUGS.md constraint + TODO.md test-first rule |
| Gemini inclusion_coverage_agent | ✓ | ✓ | BUGS.md constraint + TODO.md test-first rule |
| Gemini triage_agent | ✓ | ✓ | New spec; outputs to .gemini/notes/ only |
| Gemini BUGS.md constraint | ✓ | ✓ | Cannot create entries; may add latex_analysis field |
| Gemini TODO.md two-step vetting | ✓ | ✓ | Notes-first + test-first before any TODO entry |
| Testing history log | ✓ | ✓ | tests/runs/HISTORY.md committed |
| RAG pipeline vision | ✓ | ✓ | In TODO.md [INFRASTRUCTURE] |
| Coverage dashboard vision | ✓ | ✓ | In TODO.md [INFRASTRUCTURE] |
