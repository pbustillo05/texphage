# MacroCoverageAgent — design notes (archived)

This file was the original design draft. It has been superseded by the definitive
agent spec at `.gemini/agents/macro_coverage_agent.md`.

Key decisions made during design review:

- LIMITATIONS for existing patterns stay in `demacro.py` comments, not in `macros.md`.
  Gemini may add `[inferred]` bullets; Claude owns `[observed]` bullets.
- `macros.md` is slim: Part 1 = coverage table (pointer to code), Part 2 = not-covered
  in arXiv-ROI priority order with full syntax and doc links.
- Importance metric = arXiv paper preamble frequency, not TeX Live inter-package
  dependency counts (the original Phase 4 approach was measuring the wrong thing).
- No "implementation instructions for Claude" in macros.md — architecture notes only.
  High-ROI uncovered commands → TODO.md entries.
