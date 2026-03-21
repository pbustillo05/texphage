# BUGS.md — Regression Tracker

Maintained by `scripts/test_fidelity.py` and Claude acting as Coding Agent.
See `AGENTS.md` for the full workflow.

## Severity Scale
- **CRITICAL**: Pipeline output fails to compile with LaTeX, or causes a TeX infinite loop
- **HIGH**: Compiles but page count changes, OR any page has SSIM < 0.85
  AND text diff > 5 lines on that page (both conditions required; layout-only
  shifts from macro expansion are expected and are not HIGH by themselves)
- **MEDIUM**: Any page SSIM 0.85–0.95, or total text diff 10–50 lines
- **LOW**: Text diff < 10 lines, cosmetic only

## Entry Schema
Required: title, severity, root_cause_pattern, seen_in (arXiv IDs or package
names), description, relevant_code_location, relevant_latex_docs, reproduction
(minimal .tex snippet — also added to tests/fixtures/), first_seen, last_seen,
status (OPEN / IN_PROGRESS / FIXED).

---
<!-- New entries appended below by test_fidelity.py or Claude -->
