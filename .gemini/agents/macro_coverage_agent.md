# Agent Spec: MacroCoverageAgent

**Trigger phrase:** "Update macros.md" or "Run macro coverage agent"

**Goal:** Produce or update `macros.md` — a slim, permanent implementation reference
that shows (1) what demacro.py already covers (pointer to code for limitations) and
(2) what is not yet covered, ordered by arXiv ROI, with enough detail for Claude to
implement each item without asking questions.

**Also permitted:** Adding `[inferred]` limitation bullets to existing LIMITATIONS
blocks in `src/texphage/demacro.py` when documentation reveals gaps Claude hasn't
noted. Never touch `[observed]` lines. Never touch code.

---

## Division of responsibility

| Concern | Where it lives | Who writes it |
|---|---|---|
| What each regex matches, captures, and its proven limits | `demacro.py` MATCHES/CAPTURES/LIMITATIONS comments | Claude (`[observed]`), Gemini (`[inferred]`) |
| What is implemented (summary) | `macros.md` Part 1 | Gemini |
| What is not yet implemented, in priority order | `macros.md` Part 2 | Gemini |

`macros.md` does NOT duplicate the LIMITATIONS text from demacro.py. It says
"see demacro.py comments" and moves on.

---

## Step-by-step procedure

### Step 1 — Read the source thoroughly

Read in full:
- `src/texphage/demacro.py` — every regex with its MATCHES/CAPTURES/LIMITATIONS block,
  the `find_all` union pattern, and the full `build_dictionary` elif chain.
- `src/texphage/_regex.py` — the shared primitives.
- Current `macros.md` — do not discard structure that is already correct.

Build a precise inventory of what is actually handled:

```
Pattern name       Commands matched                  In find_all?  build_dictionary branch?
find_def           \def \gdef                        yes           elif m['def']
find_edef          \edef \xdef                       yes           elif m['edef']
find_let           \let \LetLtxMacro \GlobalLet…     yes           elif m['let']
find_new_com       \newcommand \renewcommand …        yes           elif m['new_com']
find_new_env       \newenvironment \renewenvironment  yes           elif m['new_env']
find_new_doc_com   \NewDocumentCommand …              yes           elif m['new_doc_com']
find_new_doc_env   \NewDocumentEnvironment …          yes           elif m['new_doc_env']
find_dmo           \DeclareMathOperator               yes           elif m['dmo']
find_New_Environ   \NewEnviron \RenewEnviron          NO (special)  special path in build_dictionary
find_new_environ   \newenviron \renewenviron          NO (special)  special path in build_dictionary
```

A command is COVERED only if it appears in `find_all` (or a documented special path)
AND `build_dictionary` has a branch that handles the captured groups correctly.
String-matching the command name inside the regex source is not sufficient.

### Step 2 — Identify gaps in demacro.py comments (optional but encouraged)

For each LIMITATIONS block in `demacro.py`, cross-reference the official documentation.
If you find a gap or edge case that is not yet documented:
- Add an `[inferred]` bullet explaining the limitation and citing the doc (e.g.,
  "xargs.pdf §2.3" or "etoolbox.pdf p.8").
- Never touch, relabel, or reword any `[observed]` line or any untagged line
  (untagged = treat as `[observed]`).
- Never touch Python code.

### Step 3 — Classify every command in the LaTeX macro universe

Using the six-level taxonomy already in `macros.md` as your starting list, classify
each command:

- **COVERED** — handled by a named pattern + build_dictionary branch (or special path).
- **PARTIAL** — matched but the handler is silently incomplete for some forms.
  State which forms work and which don't.
- **NOT COVERED** — not matched, or matched but not handled.

### Step 4 — Priority-rank NOT COVERED commands

Rank by expected impact on real arXiv math paper preambles. Framework:

1. **HIGH** — commands that appear in author-written preambles of common arXiv
   papers (e.g., etoolbox's `\newrobustcmd`, xparse's unsupported argument types,
   pgfkeys-based `\tikzset` definitions). Authors use these directly to define macros.
2. **MEDIUM** — commands used by heavily-loaded packages but rarely written directly
   by authors (e.g., LaTeX3 internal definition forms, `\NewEnviron` variants).
3. **LOW** — commands that are technically macro-defining but extremely rare in arXiv
   preambles in practice.
4. **OUT OF SCOPE** — commands that demacro.py will never handle by design (active
   characters, `\globaldefs`, `\futurelet`, catcode manipulation). Brief rationale only.

One targeted web search is permitted to validate or update arXiv frequency knowledge
(e.g., "most common LaTeX packages arXiv math 2023 frequency"). Do not cascade.

### Step 5 — Write the NOT COVERED entries

For each uncovered command (in priority order), write a self-contained entry:

```markdown
#### `\newrobustcmd` · `\renewrobustcmd` · `\providerobustcmd`

**Package:** `etoolbox` · [CTAN](https://ctan.org/pkg/etoolbox) · etoolbox.pdf §4.1
**Priority:** HIGH
**Status:** NOT COVERED

**Full syntax:**
\newrobustcmd[*]{\csname}[<nargs>][<default>]{<body>}
  │             │          │         │          └─ replacement text (same as \newcommand)
  │             │          │         └─ optional default for arg #1
  │             │          └─ optional argument count 0–9
  │             └─ the new command name
  └─ optional star: disallows \par in arguments (ignored for macro expansion)

**Semantics:** Expansion behaviour is identical to \newcommand. The "robust"
modifier only affects how TeX serialises the command into write/edef contexts;
it does not change what the macro expands to.

**arXiv note:** etoolbox is loaded directly by ~40% of arXiv math papers.
\newrobustcmd is the recommended modern replacement for \DeclareRobustCommand
and appears frequently in author-written preamble headers.

**Architectural note:** The argument structure is identical to find_new_com.
The fix is additive: extend the command-name alternation in find_new_com to
include these three commands. No new capture groups or build_dictionary logic
are needed.
```

The "Architectural note" describes the structure of the change, not the code.
Do not write regex syntax, Python, or implementation instructions.

### Step 6 — Write macros.md

```markdown
# macros.md — LaTeX Macro Definition: Implementation Reference

> Authoritative limitations for each implemented pattern live in the
> MATCHES/CAPTURES/LIMITATIONS comments in `src/texphage/demacro.py`.
> This file covers (1) what is implemented and (2) what is not, in priority order.

---

## Part 1: Implemented

| Command(s) | Package(s) | Pattern in demacro.py | Status |
|---|---|---|---|
| \def, \gdef | TeX primitive | find_def | COVERED |
| \edef, \xdef | TeX primitive | find_edef | COVERED |
| \let, \LetLtxMacro, \GlobalLetLtxMacro | TeX / letltxmacro | find_let | COVERED |
| \newcommand, \renewcommand, \providecommand, \DeclareRobustCommand, \newrobustcmd…, \newcommandtwoopt… | LaTeX2e / etoolbox / twoopt (+ xargs x-variants) | find_new_com | COVERED — see demacro.py for limitations |
| \newenvironment, \renewenvironment (+ x-variants) | LaTeX2e / xargs | find_new_env | COVERED — see demacro.py |
| \NewDocumentCommand, \RenewDocumentCommand, \ProvideDocumentCommand, \DeclareDocumentCommand (+ Expandable variants) | xparse (LaTeX kernel) | find_new_doc_com | COVERED — see demacro.py |
| \NewDocumentEnvironment, \RenewDocumentEnvironment, \ProvideDocumentEnvironment, \DeclareDocumentEnvironment | xparse (LaTeX kernel) | find_new_doc_env | COVERED — see demacro.py |
| \DeclareMathOperator, \DeclareMathOperator* | amsmath | find_dmo | COVERED — see demacro.py |
| \NewEnviron, \RenewEnviron | environ | find_New_Environ (special path, not in find_all) | PARTIAL — see demacro.py |
| \newenviron, \renewenviron | newenviron | find_new_environ (special path, not in find_all) | PARTIAL — see demacro.py |

---

## Part 2: Not yet implemented — ordered by arXiv ROI

[entries from Step 5, grouped HIGH / MEDIUM / LOW]

---

## Part 3: Out of scope

[commands demacro.py will never handle, with rationale]
```

---

## What NOT to do

- Do not copy LIMITATIONS text from demacro.py into macros.md. Refer to it.
- Do not write Python code, regex patterns, or implementation instructions anywhere
  in macros.md. Architecture notes (structural descriptions) are fine.
- Do not grep TeX Live to measure importance.
- Do not refetch CTAN documentation that is already linked in macros.md.
- If you believe an `[observed]` limitation is wrong, write a `.gemini/notes/` entry
  explaining the discrepancy — do not edit the `[observed]` line.

---

## Outputs

1. `macros.md` (project root) — replaced with the new version.
2. Optionally: new `[inferred]` bullets added to LIMITATIONS blocks in `demacro.py`.
3. Optionally: one or more `TODO.md` entries for HIGH-priority uncovered commands
   that are clearly scoped enough to act on immediately.
