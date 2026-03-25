# Agent Spec: InclusionCoverageAgent

**Trigger phrase:** "Update inclusions.md" or "Run inclusion coverage agent"

**Goal:** Produce or update `inclusions.md` — a slim, permanent implementation
reference that shows (1) what `unfold.py` already handles for file inclusions
(pointer to code for limitations) and (2) what is not yet handled, ordered by
arXiv ROI, with enough detail for Claude to implement each item without questions.

**Also permitted:** Adding `[inferred]` limitation bullets to the LIMITATIONS
block of `_FIND_INPUT` in `src/texphage/unfold.py` when documentation reveals
gaps Claude hasn't noted. Never touch `[observed]` lines. Never touch code.

**Important constraint:** You may NOT create new BUGS.md entries. If you find
a directive that looks like it's handled incorrectly (not just missing), write
a test suggestion to `.gemini/notes/` and ask Claude to verify it. Only
Claude's agents may create BUGS.md entries.

**TODO.md entries from this agent:** May be written directly for HIGH-priority
uncovered directives, but only if the entry includes a concrete test snippet
as its acceptance criterion (a minimal multi-file project that would pass/fail
measurably). MEDIUM and LOW items go to `.gemini/notes/` first and must go
through the two-step vetting process before becoming TODO entries.

---

## Division of responsibility

| Concern | Where it lives | Who writes it |
|---|---|---|
| What `_FIND_INPUT` matches and its proven limits | `unfold.py` MATCHES/CAPTURES/LIMITATIONS comment | Claude (`[observed]`), Gemini (`[inferred]`) |
| What is implemented (summary) | `inclusions.md` Part 1 | Gemini |
| What is not yet implemented, in priority order | `inclusions.md` Part 2 | Gemini |

`inclusions.md` does NOT duplicate the LIMITATIONS text from `unfold.py`. It
says "see unfold.py comments" and moves on.

---

## Background: the structure of unfold.py

Unlike `demacro.py` (which has many separate named patterns), `unfold.py` uses
a **single regex `_FIND_INPUT`** with six named branches, each handled by a
corresponding `elif` block in the `replacement()` closure. The MATCHES/CAPTURES/
LIMITATIONS block lives directly above the `_FIND_INPUT = re.compile(...)` line.

When classifying coverage, a directive is COVERED only if:
1. `_FIND_INPUT` has a named branch that matches its full syntax, **and**
2. The corresponding `elif match.group('<branch>')` block in `replacement()`
   resolves the file correctly.

---

## Step-by-step procedure

### Step 1 — Read the source thoroughly

Read in full:
- `src/texphage/unfold.py` — the `_FIND_INPUT` regex with its MATCHES/CAPTURES/
  LIMITATIONS comment, the `replacement()` closure's `elif` chain, and the
  `find_main_file()` logic.
- Current `docs/inclusions.md` (if it exists) — do not discard structure that is
  already correct.

Build a precise inventory:

```
Branch name  Directive(s)                      In _FIND_INPUT?  replacement() branch?
input        \input{path}                      yes              elif match.group('input')
include      \include{path}                    yes              elif match.group('include')
usepkg       \usepackage{pkg}                  yes (opt-in)     elif match.group('usepkg') and inline_local_packages
import_      \import{dir}{file}                yes              elif match.group('import_')
subimport    \subimport{dir}{file}             yes              elif match.group('subimport')
subfile      \subfile{p}, \subfileinclude{p}   yes              elif match.group('subfile')
```

Note carefully any PARTIAL cases — e.g., `\usepackage` is matched but only
inlined when `inline_local_packages=True`, and only for local `.sty` files.

### Step 2 — Identify gaps in unfold.py comments (optional but encouraged)

Cross-reference the `_FIND_INPUT` LIMITATIONS block against official documentation
for all known file-inclusion forms in LaTeX. If you find an undocumented gap:
- Add an `[inferred]` bullet citing the doc (e.g., "LaTeX2e source §Input",
  "import.pdf §3", "subfiles.pdf §2.1").
- Never touch, relabel, or reword any `[observed]` line or any untagged line
  (untagged = treat as `[observed]`).
- Never touch Python code.

### Step 3 — Survey the full universe of LaTeX file-inclusion mechanisms

Use your LaTeX knowledge (web search is permitted for arXiv frequency data) to
compile a complete list of directives that can include or reference external
files in a LaTeX document. Organise them into categories:

**Category A — Content inclusion (unfold these; they affect document text)**
File-inclusion directives whose resolved content becomes part of the typeset
document. These are what unfold.py is designed for.
Examples: `\input`, `\include`, `\subfile`, `\import`, etc.

**Category B — Verbatim / listing inclusion (do NOT unfold)**
Directives that insert file content verbatim or as a code listing. Expanding
these into the document body would corrupt the NLP output.
Examples: `\verbatiminput`, `\lstinputlisting`, `\inputminted`, `\VerbatimInput`.

**Category C — Asset references (intentionally out of scope)**
References to non-tex assets (images, bibliography files, data files). These are
not LaTeX source and should never be inlined.
Examples: `\includegraphics`, `\bibliography`, `\addbibresource`.

**Category D — Package / class loading (potential future scope)**
Package and class loading directives, relevant when inlining local `.sty`/`.cls`
files. Currently `\usepackage` is PARTIAL; others are not handled.
Examples: `\RequirePackage`, `\LoadClass`, `\documentclass`.

### Step 4 — Classify every Category A directive

For each Category A directive, assign:
- **COVERED** — `_FIND_INPUT` branch matches + `replacement()` handles correctly.
- **PARTIAL** — matched or partially handled but with important caveats.
- **NOT COVERED** — not matched, or matched but not handled.

### Step 5 — Priority-rank NOT COVERED directives

Rank by expected impact on real arXiv math paper projects. Framework:

1. **HIGH** — directives used frequently in arXiv multi-file papers
   (e.g., `\InputIfFileExists` which some packages use to load optional files,
   or `\RequirePackage` for projects with local package files).
2. **MEDIUM** — directives from commonly-loaded packages but rarely authored
   directly (e.g., `\subinputfrom`, `\inputfrom` from the import package).
3. **LOW** — directives that are technically content-including but extremely rare
   in arXiv source.
4. **OUT OF SCOPE** — Category B (verbatim) and Category C (assets) directives.
   These belong in Part 3 of inclusions.md with a clear rationale.

One targeted web search is permitted to check arXiv multi-file paper frequency
(e.g., "arXiv LaTeX multi-file projects most common include commands"). Do not
cascade.

### Step 6 — Write the NOT COVERED entries

For each uncovered Category A directive, write a self-contained entry:

```markdown
#### `\InputIfFileExists`

**Package:** LaTeX2e kernel · [source2e §Input](https://ctan.org/pkg/source2e)
**Priority:** MEDIUM
**Status:** NOT COVERED

**Full syntax:**
\InputIfFileExists{<filename>}{<true-code>}{<false-code>}
  │                │            │             └─ executed if file does NOT exist
  │                │            └─ executed if file exists (after the \input)
  │                └─ the file to test and input
  └─ no extension auto-append; file must be given with full name

**Semantics:** Tests whether <filename> exists on the TeX search path. If it
does, inputs it and runs <true-code>; otherwise runs <false-code>. The file
content, if loaded, becomes part of the document body — so unfold.py should
inline it when found, and suppress it (or inline <false-code>) when not.

**arXiv note:** Used internally by many packages to load optional configuration
files. Authors rarely write it directly, but it appears in project-level
`.sty` files that are unfolded when inline_local_packages=True.

**Architectural note:** Requires two-branch logic (file found / not found) unlike
\input. The regex needs to capture all three arguments. The replacement function
should attempt to open the file: on success, unfold and prepend true-code; on
FileNotFoundError, emit false-code only.
```

### Step 7 — Write inclusions.md

```markdown
# inclusions.md — LaTeX File Inclusion: Implementation Reference

> Authoritative limitations for each implemented form live in the
> MATCHES/CAPTURES/LIMITATIONS comment in `src/texphage/unfold.py`.
> This file covers (1) what is implemented and (2) what is not, in priority order.

---

## Part 1: Implemented

| Directive(s) | Package | Branch in _FIND_INPUT | Status |
|---|---|---|---|
| \input{path} | TeX primitive | input | COVERED — see unfold.py |
| \include{path} | LaTeX2e | include | COVERED — see unfold.py |
| \usepackage{pkg} | LaTeX2e | usepkg | PARTIAL — local .sty only, opt-in flag required — see unfold.py |
| \import{dir}{file} | import | import_ | COVERED — see unfold.py |
| \subimport{dir}{file} | import | subimport | COVERED — see unfold.py |
| \subfile{path}, \subfileinclude{path} | subfiles | subfile | COVERED — see unfold.py |

---

## Part 2: Not yet implemented — ordered by arXiv ROI

[Category A entries from Step 6, grouped HIGH / MEDIUM / LOW]

---

## Part 3: Out of scope

### Category B — Verbatim / listing inclusion (never unfold)

[List of \verbatiminput, \lstinputlisting, \inputminted, etc. with brief
rationale: content is literal text that should not be expanded into the NLP body]

### Category C — Asset references (not LaTeX source)

[List of \includegraphics, \bibliography, \addbibresource, etc. with brief
rationale: binary or data files, not LaTeX source]

### Category D — Package / class loading (potential future scope)

[List of \RequirePackage, \LoadClass, \documentclass with note that
\usepackage is already PARTIAL; these are lower priority since they appear
mainly in .sty/.cls files, not author documents]
```

---

## What NOT to do

- Do not copy LIMITATIONS text from `unfold.py` into `inclusions.md`. Refer to it.
- Do not write Python code, regex patterns, or implementation instructions
  anywhere in `inclusions.md`. Architecture notes (structural descriptions) are fine.
- Do not include Category B or C directives in Part 2 — they belong in Part 3.
- Do not grep TeX Live to measure importance; use arXiv document frequency.
- If you believe an `[observed]` limitation is wrong based on documentation, write
  a `.gemini/notes/` entry explaining the discrepancy — do not edit the line.

---

## Outputs

1. `docs/inclusions.md` — created or replaced.
2. Optionally: new `[inferred]` bullets added to the LIMITATIONS block in `unfold.py`.
3. Optionally: one or more `TODO.md` entries for HIGH-priority uncovered directives
   that are clearly scoped enough to act on immediately, each with a concrete
   test snippet as acceptance criterion.
4. Optionally: notes to `.gemini/notes/` for MEDIUM/LOW items or anything that
   requires a test from Claude before promotion to TODO.md.
