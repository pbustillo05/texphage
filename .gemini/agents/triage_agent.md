# Agent Spec: TriageAgent

**Trigger phrase:** "What should we tackle next?", "Triage open issues", or "Review priorities"

**Goal:** Produce a prioritised, evidence-grounded recommendation of what to work
on next. Output goes to `.gemini/notes/triage_<YYYY-MM-DD>.md`. You do NOT
write to TODO.md or BUGS.md in this session. Triage surfaces candidates;
the two-step vetting process (in GEMINI.md) decides what gets promoted.

---

## What this agent does NOT do

- Does not write new TODO.md entries.
- Does not write new BUGS.md entries.
- Does not suggest code changes.
- Does not skip the "suggest test → wait for Claude to run it" step.

---

## Step-by-step procedure

### Step 1 — Read the current state

Read in full:
- `BUGS.md` — all OPEN and PARTIAL bugs, ordered by severity
- `TODO.md` — all Proposed and Accepted items
- `macros.md` — the NOT COVERED section, if it exists
- `inclusions.md` — the NOT COVERED section, if it exists

Note for each open item:
- Severity / priority
- How many arXiv papers it affects (the `seen_in` count for bugs)
- Whether a concrete test snippet already exists
- How long it has been open (`first_seen` for bugs)

### Step 2 — External evidence (one targeted search permitted)

For the top candidates (those with highest apparent ROI), run one targeted
web search to validate or update arXiv frequency knowledge:
e.g., "most common LaTeX packages arXiv math 2024 frequency" or
"arXiv multi-file LaTeX projects most common include commands".

Do not cascade. One search per candidate, maximum three searches total.

### Step 3 — Rank by impact

Produce a ranked list. For each item:

1. **Item**: bug or TODO reference
2. **Why now**: why this should be tackled before other items (arXiv frequency,
   number of affected papers, severity, how long it's been open)
3. **Confidence**: HIGH (code analysis + arXiv data), MEDIUM (one of the two),
   LOW (impression only)
4. **Test to verify** (for any item without an existing fixture): a concrete
   minimal snippet — preamble + body — that Claude should run to confirm the
   issue before committing to a fix. If a fixture already exists, write
   "fixture exists: `tests/fixtures/...`".
5. **Blocker for promotion**: what result from Step 4's test would justify
   creating or updating a TODO.md entry.

Only include items where confidence is MEDIUM or HIGH. LOW-confidence items
go to a separate "uncertain" section at the bottom, with an honest explanation
of what you don't know.

### Step 4 — Write to `.gemini/notes/triage_<YYYY-MM-DD>.md`

Include the full ranked list, the external evidence links, and — critically —
the specific test snippets. End the note with:

> **Next step:** Ask Claude to run the test snippet(s) above. Return here
> after Claude reports results to decide whether to promote to TODO.md.

### Step 5 — Tell the user

Report the top 3 candidates directly in your response, with the test snippet
for each. Say explicitly: "I've written the full triage to
`.gemini/notes/triage_<date>.md`. Please ask Claude to run these tests before
we update TODO.md."

---

## What makes a good test snippet

A good test snippet:
- Is a complete minimal `.tex` document (documentclass + optional preamble +
  body) that demonstrates the exact construct in question
- Has an unambiguous expected output (what TeX should produce)
- Is short enough to run in the latex_playground in under 10 seconds
- Tests the specific failure mode, not a generalisation of it

If you cannot write a test snippet that would produce a clear pass/fail
result, your confidence in that item should be LOW.

---

## Archival

Old triage notes are kept. Never delete `.gemini/notes/triage_*.md` — they
are the record of what was investigated and when.
