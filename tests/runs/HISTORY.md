# Testing History

Seeds select different random shuffles of recent arXiv papers in the sampled
categories (`math.CT`, `math.AT`, `cs.LO`). Each seed gives a reproducible
but distinct paper set. **Do not reuse a seed** — the goal is broad coverage.

The testing-agent appends a row here after every run (Step 8.5).

| Date       | Seed | Papers tested | New / updated bugs                    |
|------------|------|---------------|---------------------------------------|
| 2026-03-21 |   42 | 4             | BUG-3, BUG-4, BUG-5, BUG-6           |
| 2026-03-21 |    0 | (re-run)      | — (infra debugging, no new bugs)      |
| 2026-03-22 |    7 | 4             | BUG-7 (fixed), BUG-8, BUG-9          |
| 2026-03-23 |    1 | 4             | BUG-10, BUG-11, BUG-12               |
| 2026-03-23 |    2 | 4             | BUG-13, BUG-14 (new); BUG-12 updated (seen_in) |
| 2026-03-23 |    3 | 5             | BUG-15, BUG-16, BUG-17, BUG-18 (new) |
| 2026-03-23 |    4 | 3             | BUG-15, BUG-16 confirmed (seen_in updated) |
| 2026-03-23 |    5 | 2             | BUG-15 confirmed; BUG-12 symptom in 2601.14237 |
| 2026-03-23 |    6 | 4             | BUG-15, BUG-18 confirmed; \prop undefined in 2601.13325 |
| 2026-03-23 |    8 | 3             | BUG-17 confirmed (2602.04425); Missing $ in math mode (BUG-15 cascade) |
| 2026-03-23 |    1 | 4             | BUG-20, BUG-21 (new); 2501.00624 PDF-only (skipped); 2501.00319 success (HIGH page delta — layout-only) |
| 2026-03-24 |    9 | 5             | BUG-22, BUG-23, BUG-24, BUG-25 (new); 2601.02895 HIGH (layout shift from macro expansion) |
