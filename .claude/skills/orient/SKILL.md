# orient skill

## Trigger

Load this skill when:
- Starting a major new implementation effort (new feature, big refactor, new agent)
- In doubt about whether a proposed change conflicts with past decisions
- Asked to "check history", "orient yourself", "check what's been done", or
  "make sure we're not undoing something"
- Before implementing anything related to regex patterns, preamble preservation,
  preprocessing, or macro expansion — areas with subtle established invariants

## What to do

1. Read `docs/EVOLUTION.md` in full.
2. Run `git log --oneline -20` and note recent commits.
3. Check `BUGS.md` for any OPEN bugs related to the area you're about to touch.
4. Briefly summarize for the user (2–4 sentences):
   - What phase the project is in
   - What was most recently done
   - Any established decisions that constrain the proposed work
   - Any open bugs that are relevant

Do NOT start implementing until after this summary. If a proposed change would
violate an "Intentional Non-Decision" in `docs/EVOLUTION.md`, flag it explicitly.
