# texphage — Claude's operating context

@./docs/project-context.md

## Your role

You are the engineer on this project. You own implementation, testing,
debugging, and all hands-on investigation. This includes LaTeX debugging:
when a construct is unclear, use the full toolkit — the latex playground
(scripts/latex_playground.py), texdef, regex pattern probes, and visual
PDF diffs from the arXiv pipeline — to understand ground truth yourself.
Gemini supplies architectural ideas and research; you turn them into code.

## Debugging LaTeX constructs

**First, ask: do I know which package defines this macro?**

- **Yes — package known:** Go straight to the `.sty` source.
  Prefer CTAN online (always authoritative and up-to-date):
  `https://mirror.ctan.org/macros/latex/contrib/<pkg>/<pkg>.sty`
  The local TexLive at `/usr/local/texlive/` is also available via
  `kpsewhich <pkg>.sty`, but it may be outdated — prefer CTAN when there
  is any doubt.

- **No — package unknown:** Use `texdef -t latex -f \<csname>` to discover
  which package defines the macro and see TeX's internal representation of it.
  If the local TexLive is outdated, texdef output may not match current CTAN
  behaviour — cross-check with CTAN docs when the two disagree.

Then, in order:
1. `scripts/latex_playground.py` — compile a minimal snippet, inspect the
   PDF text output. This is your oracle: test assertions must be grounded
   in what the playground produces, not in what you think TeX should do.
2. Visual PDF diff — compile raw source and pipeline output, compare pages
   visually (multimodal) or with SSIM. A layout shift that looks wrong on
   screen is a bug even if the text diff is small.

Do not stop at "I'm not sure what this macro does." Investigate until you
know. If investigation genuinely bottoms out, write a minimal reproduction
to BUGS.md and note exactly what you tried — but this should be rare.

## Subagents

Invoke these with "Run testing agent", "Fix BUG-N", "Run quarterly audit",
or "Run regex audit". Claude Code will delegate automatically.
- `testing-agent`   — downloads arXiv papers, runs pipeline, logs bugs
- `coding-agent`    — fixes a specific bug in BUGS.md
- `quarterly-audit` — scans CTAN for unrecognised macro patterns
- `regex-audit`     — audits all patterns in `_regex.py`: adds missing
                      MATCHES/CAPTURES/LIMITATIONS/USED BY comments, writes
                      playground-backed tests, checks naming hygiene

## Always-on rules

- **"Write a note / write a prompt"** → always create or update a file in
  `.claude/notes/`. Load the `write-note` skill when this is requested.
- Write a failing test before touching any code.
- **All string pattern-finding and pattern-replacement must use `regex`.
  No exceptions.** Never use `str.find()`, `.startswith()`, `.endswith()`,
  `.isalpha()`, `.isdigit()`, `.index()`, character loops, or manual
  brace-counting to detect structure in a LaTeX string.
  - **Writing a new pattern?** Load the `regex-writing` skill first. It
    covers naming conventions (`_RE`/`_PATTERN`/`snake_case`), section
    placement in `_regex.py`, the mandatory `MATCHES/CAPTURES/LIMITATIONS/USED BY`
    comment block, sub-pattern reuse, and the preprocessing invariant.
  - **Modifying an existing pattern?** Load `regex-danger-zone` first. It
    covers interdependency warnings, named-capture renaming risks, the
    `build_dictionary()` elif-chain order, and the torture-test protocol.
  - All compiled patterns live exclusively in `src/texphage/_regex.py`.
    No `re.compile(...)` calls anywhere else. No `import re` (stdlib) anywhere.
  - The only exemptions are genuinely non-structural utility operations
    (stripping whitespace from a shell command result, splitting a Python path).
- Never commit `tests/runs/` content (except `tests/runs/HISTORY.md`), tarballs, or compiled PDFs.
- Run `pytest tests/ -v && ruff check src/ && mypy src/texphage/`
  after every change before committing.
- After any fix, update `README.md` "Known limitations": remove constructs
  that are now supported; add newly discovered limitations.

## Tagging limitation comments in demacro.py and unfold.py

Every bullet in a `LIMITATIONS` block in `demacro.py` or `unfold.py` must carry
one of two epistemic tags:

- `[observed]` — you verified this empirically (playground, texdef, or direct
  filesystem test). Gemini may never modify or delete an `[observed]` line.
- `[inferred]` — derived from documentation or code reading, not empirically
  tested. Gemini may add or update `[inferred]` lines.

Format example:

```python
# LIMITATIONS:
#   [observed] \newcommand* treated identically to unstarred; playground
#              confirms \par-in-args is irrelevant for text expansion.
#   [inferred] xargs positional key [1=Hello] not supported (xargs.pdf §2.3).
```

When you test something and it confirms or contradicts an `[inferred]` line,
update its tag to `[observed]` and amend the description.
Existing limitation bullets without a tag should be treated as `[observed]`
(they predate this convention and were written from code analysis).
