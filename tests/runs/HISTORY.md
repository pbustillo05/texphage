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
