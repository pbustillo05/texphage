# Contributing to texphage

texphage is a **Claude-powered, self-improving repository**. The intended
contribution model is: you describe what you want, Claude agents implement it,
test it against real arXiv papers, find regressions, and fix them. Human
effort is mainly idea generation and review — not implementation.

This guide explains how to work with that model, and covers manual workflows
for those who want to go deeper.

---

## The agentic workflow (recommended)

The fastest way to contribute is to open Claude Code in this repo and describe
what you want in plain English. The agents handle the rest.

### Fix the next open bug

```
Fix next bug
```

The `coding-agent` reads `BUGS.md`, picks the highest-priority open item,
writes a failing test, fixes the code, verifies with the LaTeX playground, and
commits — following the test-first protocol automatically.

### Fix a specific bug

```
Fix BUG-14
```

### Run fidelity tests against arXiv papers

```
Run fidelity agent on seed 42
```

Downloads real arXiv papers, runs the pipeline on each, compares the output PDF
to the original with SSIM, and logs any regressions to `BUGS.md`. No manual
test-writing needed — real-world coverage on demand.

You can also target a subject area:

```
Run fidelity tests on 10 math papers
```

### Triage open issues

```
What should we tackle next?
```

The triage agent reads `BUGS.md` and `TODO.md`, verifies candidates in the
playground, and promotes the most impactful confirmed items.

### Add a new tool or feature

Describe the transformation you want — in terms of what the input LaTeX looks
like and what the output should look like. Claude will:
1. Check `docs/user_applications.md` and `TODO.md` for prior design work
2. Read `docs/EVOLUTION.md` for architectural decisions
3. Propose an implementation plan
4. Write tests, implement, verify fidelity

---

## Setup (required for any workflow)

```bash
git clone https://github.com/yourorg/texphage.git
cd texphage
pip install -e ".[dev,agents]"
```

System dependencies (TeX Live + poppler) are required for pipeline tests and
fidelity runs — see [README installation](README.md#installation).

Verify everything works:

```bash
pytest tests/ -v -k "not pipeline"   # no TeX required
pytest tests/ -v                      # requires latexmk
```

---

## Manual workflow

If you prefer to implement things yourself, the rules below apply. The agents
follow the same rules, so understanding them helps you review their output.

### Full gate (run before every commit)

```bash
pytest tests/ -v && ruff check src/ && mypy src/texphage/
```

All three must pass.

### Commit conventions

[Conventional Commits](https://www.conventionalcommits.org/) with a `BUG-N`
reference for regressions:

```
fix(demacro): handle \edef inside \newcommand (BUG-7)
test: add failing test for BUG-7 (fails before fix)
docs: update known limitations
```

Common prefixes: `fix`, `feat`, `test`, `docs`, `chore`, `refactor`.

### Bug fix protocol

1. Add/find the entry in [`BUGS.md`](BUGS.md). Mark it `IN_PROGRESS`.
2. Write a failing test. Run it — confirm failure.
3. Fix the code. Run the full gate.
4. Remove the limitation from `README.md` if it was listed there.
5. Move the entry from `BUGS.md` to [`docs/FIXED_BUGS.md`](docs/FIXED_BUGS.md).
6. Commit in order: `test:` → `fix:` → `docs:`.

### Adding a feature

1. Check [`TODO.md`](TODO.md) and [`docs/user_applications.md`](docs/user_applications.md).
2. Write tests first.
3. Implement. Run the full gate.
4. Update `docs/user_applications.md` status (e.g. 📋 → ✅).

### Working with regex patterns

**Do not edit `_regex.py` without reading the danger-zone rules first.** The
patterns use PCRE features that interact in non-obvious ways — reordering the
`elif` chain or renaming a named group can silently break unrelated patterns.

In Claude Code: load `regex-writing` before adding a new pattern; load
`regex-danger-zone` before modifying an existing one.

---

## Project structure

```
src/texphage/
├── pipeline.py      # Public API: texphage(), texphage_to_dir()
├── demacro.py       # Macro expansion engine
├── unfold.py        # Multi-file flattening
├── find_packages.py # Package discovery via kpsewhich
└── _regex.py        # All compiled regex patterns (DANGER ZONE)

tests/
├── test_demacro.py
├── test_unfold.py
├── test_pipeline.py
└── test_find_packages.py

scripts/
├── latex_playground.py   # Compile minimal LaTeX snippets; test oracle
└── test_fidelity.py      # Download arXiv papers, run pipeline, compare PDFs

.claude/
├── agents/               # Agent definitions (coding-agent, arxiv-fidelity, ...)
└── skills/               # Skill definitions (regex-writing, playground-protocol, ...)
```

---

## Tracking files

| File | Purpose |
|------|---------|
| [`BUGS.md`](BUGS.md) | Open regressions (OPEN / IN_PROGRESS only) |
| [`TODO.md`](TODO.md) | Planned features and enhancements |
| [`docs/FIXED_BUGS.md`](docs/FIXED_BUGS.md) | Archive of resolved bugs |
| [`docs/EVOLUTION.md`](docs/EVOLUTION.md) | Architectural decisions and intentional non-decisions |

Read `EVOLUTION.md` before starting any major effort.

---

## Module documentation

- [Pipeline API](docs/guide/pipeline.md) — `texphage()`, `texphage_to_dir()`, `build_minimal_preamble()`
- [demacro](docs/guide/demacro.md) — macro expansion: supported forms, preprocessing contract, API
- [unfold](docs/guide/unfold.md) — multi-file flattening: supported directives, API
- [find_packages](docs/guide/find_packages.md) — package discovery via kpsewhich
