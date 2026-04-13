# Repository Review — texphage (2026-04-12)

## Scope

This note answers three questions:

1. What is this repository actually building?
2. Where is the current workflow strong or weak?
3. What global changes would most improve the project?

This review is based on reading the repository, its docs, and the main source
modules. No web searches were used. I also checked whether the documented local
quality gate was runnable in the current environment.

---

## Executive summary

`texphage` is building a **LaTeX normalization and rearrangement toolkit** with
one solid implemented core and a larger, still-partially-realized product
vision around it.

The implemented core is credible:

- flatten multi-file LaTeX projects (`unfold`)
- expand author-defined macros (`demacro`)
- reconstruct a compilable minimal preamble
- emit a canonical, self-contained artifact suitable for NLP and downstream
  tooling

The bigger ambition is more than a library. The repo is trying to become a
**self-improving agentic engineering loop** around LaTeX transformations:
playground verification, arXiv fidelity testing, structured bug harvesting, and
agent-driven repair.

That vision is interesting, but right now the workflow is ahead of the shipped
product. The repo has a strong maintenance philosophy, but some important
boundaries and invariants are not enforced in code. The main risk is not that
the core idea is wrong; it is that the project is accumulating too much process
and too many local rules before finishing the productization layer.

---

## What the repository is building

### The current product

The current shipped product is best understood as a **compiler-adjacent LaTeX
canonicalizer**.

The clearest description is in [README.md](../../README.md) and the pipeline
entrypoint in [src/texphage/pipeline.py](../../src/texphage/pipeline.py):

- [README.md](../../README.md#L3-L24) frames the repo as a "LaTeX rearrangement
  toolbox"
- [src/texphage/pipeline.py](../../src/texphage/pipeline.py#L223-L262)
  implements the actual end-to-end contract:
  - unfold a project
  - expand preamble-defined macros
  - rebuild a minimal preamble
  - produce canonical LaTeX plus a list of attachments

That is already a coherent library.

### The intended product

The intended product is broader than the code currently ships.

The repo wants to become a modular toolbox containing:

- the current normalization pipeline
- a formatter / pretty-printer
- LaTeX modernization converters like `xy` to `tikzcd`
- agent-oriented CLI surfaces
- eventually a broader ecosystem of downstream tools and maybe editor support

This broader direction is explicit in:

- [docs/user_applications.md](../user_applications.md)
- [docs/EVOLUTION.md](../EVOLUTION.md#L92-L125)
- [docs/notes/toolbox_refactor_plan.md](toolbox_refactor_plan.md)

The gap is that the **toolbox framing is ahead of the packaging reality**. The
repo mostly ships one strong library path today, not yet the toolbox promised
by the planning docs.

### The deeper idea

The most original idea in the repo is not just "expand LaTeX macros". It is the
combination of:

- a common regex/preprocessing substrate
- empirically verified transformations against actual TeX behavior
- real-world regression discovery on arXiv papers

That is a strong research-engineering loop. The fidelity harness in
[scripts/test_fidelity.py](../../scripts/test_fidelity.py) and the playground in
[scripts/latex_playground.py](../../scripts/latex_playground.py) are the right
kind of tools for this domain.

---

## What is strong

### 1. The repo is testing against reality, not theory

This is the best part of the project.

LaTeX behavior is full of edge cases and folklore. The repo uses:

- a minimal compilation playground for ground truth:
  [scripts/latex_playground.py](../../scripts/latex_playground.py)
- end-to-end fidelity comparison on real papers:
  [scripts/test_fidelity.py](../../scripts/test_fidelity.py)

That is the correct instinct. In this domain, "what TeX actually does" matters
more than elegant internal theories.

### 2. The core library surface is reasonably coherent

The public API in [src/texphage/__init__.py](../../src/texphage/__init__.py)
and the composition in
[src/texphage/pipeline.py](../../src/texphage/pipeline.py) make sense.

The pipeline contract is understandable:

- `unfold` handles project flattening
- `demacro` handles macro expansion
- `build_minimal_preamble` tries to preserve only what is needed
- `texphage_to_dir` handles asset copying and path rewriting

This is a good library skeleton.

### 3. The docs capture intent unusually well

Compared to most small research-style repos, this one has much better written
intent:

- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [CLAUDE.md](../../CLAUDE.md)
- [docs/EVOLUTION.md](../EVOLUTION.md)
- [docs/guide/agentic-framework.md](../guide/agentic-framework.md)

Even when I disagree with parts of the workflow, I rarely had to guess what the
maintainer wants.

### 4. The bug protocol is concrete

Using `BUGS.md`, fixtures, permanent regressions in
[tests/test_pipeline.py](../../tests/test_pipeline.py), and the "playground
verified" habit is a good maintenance pattern for something this heuristic.

---

## Workflow criticism

### 1. The workflow is more mature than the product surface

The repo spends a lot of energy describing the agent system and the operating
model, but the package still lacks basic productization pieces already
identified as necessary.

Examples:

- The toolbox plan says the repo needs a CLI and console scripts:
  [docs/notes/toolbox_refactor_plan.md](toolbox_refactor_plan.md#L57-L110)
- The package metadata still describes the narrower old scope:
  [pyproject.toml](../../pyproject.toml#L5-L13)
- There is no shipped `src/texphage/cli.py`
- The README offers Python usage, but not the CLI the planning docs say should
  exist:
  [README.md](../../README.md#L58-L79)

This creates a mismatch between "how the repo talks about itself" and "what a
new user can actually install and run".

### Why this matters

It is easier to trust and extend an agentic workflow once the product surface is
boring and stable. Right now, some foundational packaging work is still pending
while the workflow documentation is already highly elaborate.

### 2. Repo rules are not consistently enforced

The project has strong rules, but some are violated inside the repo itself.

The clearest example:

- [CLAUDE.md](../../CLAUDE.md#L73-L91) says all structural pattern work must
  use the third-party `regex` package, with **no stdlib `re` anywhere**
- But [src/texphage/unfold.py](../../src/texphage/unfold.py#L13-L17) imports
  stdlib `re`
- [scripts/extractor.py](../../scripts/extractor.py#L1-L16) also imports stdlib
  `re`
- [scripts/xy_to_tikz.py](../../scripts/xy_to_tikz.py#L1-L4) also imports
  stdlib `re`

Maybe some of these are harmless in practice. That is not the point. The point
is that the repo claims certain invariants are existentially important, but does
not actually enforce them.

### Why this matters

When a repo has many local rules, violating them in-tree damages the credibility
of all the other rules too.

### 3. Architecture boundaries are leaky

Several parts of the repo cross boundaries by importing from scripts or
manipulating `sys.path`.

Examples:

- [scripts/test_fidelity.py](../../scripts/test_fidelity.py#L196-L239) inserts
  `scripts/` into `sys.path` and imports `extractor`
- [tests/test_pipeline.py](../../tests/test_pipeline.py#L16-L18) inserts
  `scripts/` into `sys.path`
- [scripts/extractor.py](../../scripts/extractor.py#L16-L16) mutates
  `sys.path` too

The repo already recognizes this as a problem:

- [TODO.md](../../TODO.md#L56-L64) explicitly calls for a shared
  `arxiv_utils` module because logic is duplicated and a test script imports
  from another script

This is exactly the right diagnosis. Scripts should be thin wrappers around
library code, not an alternate internal module system.

### 4. `build_minimal_preamble()` is becoming a reactive exception ledger

The function in
[src/texphage/pipeline.py](../../src/texphage/pipeline.py#L56-L142) is doing
important work, but its growth pattern is risky.

It is accumulating preservation rules one bug at a time:

- front matter
- theorem declarations
- counters
- version environments
- color declarations
- footnote declarations
- guards for theorem redefinition conflicts

This has worked so far, but the repo itself already notes the underlying issue:

- [TODO.md](../../TODO.md#L66-L80) says there is no systematic audit of what
  must survive the preamble reconstruction step

### Why this matters

The current strategy is defensible as an early-phase tactic, but brittle as a
long-term architecture. It turns `build_minimal_preamble()` into a growing list
of exceptions rather than a declarative model of preamble semantics.

### 5. The repo over-documents process relative to enforcement

The docs are detailed about:

- agent roles
- trigger phrases
- mandatory sequences
- testing rituals
- lock behavior
- bug lifecycles

But there is little visible enforcement infrastructure in the repo itself.

I did not find CI configuration in the repository root or a `.github/workflows/`
tree. The docs say contributors must run the full gate before every commit:

- [CONTRIBUTING.md](../../CONTRIBUTING.md#L95-L101)
- [CLAUDE.md](../../CLAUDE.md#L99-L104)

But on this machine, the documented gate was not runnable because `pytest`,
`ruff`, and `mypy` were not installed on `PATH`, and there was no project-local
venv checked into the repo.

That is not a code bug by itself. It is a workflow smell: the "happy path" is
documented, but not yet made automatic or self-checking.

### 6. Some planned features should stay clearly experimental

The repo is honest that `xy` to `tikzcd` is in progress, but the current script
is not close to the standards applied elsewhere:

- [scripts/xy_to_tikz.py](../../scripts/xy_to_tikz.py#L1-L278) uses stdlib
  `re`
- it contains `print()` at module import time
- it contains multiple `match.grouo` typos
- it lives in `scripts/` rather than a real package module

This is fine as an experiment. It is not fine if the repo presents the toolbox
as already unified while including clearly non-production subtools under the
same conceptual umbrella.

The right answer is not "remove it". The right answer is to keep a strict line
between:

- shipping library code
- experimental prototypes

### 7. The repo currently depends a lot on Markdown as operational state

`BUGS.md`, `TODO.md`, `EVOLUTION.md`, triage reports, and plan notes are all
useful. The problem is not that they exist; the problem is how much operational
truth lives only there.

For example:

- planning state lives in `TODO.md`
- open bug lifecycle lives in `BUGS.md`
- architecture intent lives in `EVOLUTION.md`
- workflow rules live in `CLAUDE.md`

This is manageable at small scale, but it is fragile for the autonomous loop
the repo wants. Agents are more reliable when some state is machine-readable and
enforceable instead of purely narrative.

---

## Global changes I would recommend

### 1. Finish productization before expanding the agent system

The next milestone should be making the current core feel like a finished tool,
not adding more workflow meta-structure.

Priority items:

1. Implement `src/texphage/cli.py`
2. Add `[project.scripts]` in `pyproject.toml`
3. Add README CLI examples
4. Update package metadata to match the toolbox framing

The plan already exists in
[docs/notes/toolbox_refactor_plan.md](toolbox_refactor_plan.md#L57-L124). It
should be executed, not re-planned.

### 2. Pull reusable logic out of `scripts/` into `src/texphage/`

This is the most important structural cleanup.

Create real library modules for:

- arXiv download and extraction
- category sampling / metadata fetching
- fidelity helpers that are reusable from tests and CLI entrypoints
- possibly playground helpers, if parts should be public or semi-public

Then make `scripts/` thin wrappers only.

This would remove:

- `sys.path` hacks
- script-to-script imports
- duplicated arXiv download logic

The repo already knows this for the arXiv path:
[TODO.md](../../TODO.md#L56-L64).

### 3. Turn repo rules into checks

Right now too many norms are conventional rather than enforced.

I would add:

- CI for `pytest`, `ruff`, and `mypy`
- a check that forbids stdlib `re` under `src/`
- a check that forbids `sys.path.insert` / `sys.path.append` under `src/` and
  `tests/`, except in narrowly-approved cases
- a check that scripts do not define logic duplicated in package modules

If a rule matters enough to appear in `CLAUDE.md`, it should usually have a
machine check behind it.

### 4. Refactor `build_minimal_preamble()` into a declarative preservation layer

I would not immediately rewrite the pipeline, but I would change how this part
grows.

Instead of one growing function with bug-number comments, move toward:

- a small registry of preservation handlers
- explicit categories like `KEEP`, `DROP`, `NORMALIZE`, `CONDITIONAL`
- tests that target categories, not only isolated bugs

This aligns with the repo's own proposed systematic audit in
[TODO.md](../../TODO.md#L66-L80).

The immediate goal is not academic purity. It is to stop the function from
becoming a permanent one-off exception pile.

### 5. Separate stable and experimental tools more clearly

I would define three tiers:

- **Stable**: packaged modules in `src/texphage/`, covered by the normal gate
- **Experimental**: scripts that are useful but not part of the supported API
- **Planned**: notes/specs only

Then reflect those tiers in README and docs.

That would prevent the current blur where the toolbox narrative includes tools
that are conceptually part of the vision but operationally not ready.

### 6. Reduce Markdown-only operational state where it matters

I would keep the prose docs, but add machine-readable artifacts for the pieces
the autonomous workflow really depends on.

Candidates:

- structured bug metadata
- structured coverage or success-rate data
- structured inventory of preserved preamble constructs

The repo already points in this direction with proposals like success-rate
tracking and a coverage dashboard in [TODO.md](../../TODO.md).

### 7. Add a real onboarding path that works on a fresh machine

The docs currently describe setup, but the repo should make the first success
path tighter:

- one install command
- one smoke-test command
- one CLI example

If the repo wants to be agent-first, this matters even more. Agents also need a
predictable bootstrap path.

---

## Suggested execution order

If I were sequencing the next major improvements, I would do them in this order:

1. **CLI and packaging**
   - finish `cli.py`
   - add console scripts
   - update README and metadata

2. **Boundary cleanup**
   - create `src/texphage/arxiv_utils.py`
   - remove script-to-script imports
   - remove `sys.path` manipulation where possible

3. **Enforcement**
   - add CI
   - add guardrails for `re` / `sys.path` / packaging hygiene

4. **Preamble architecture cleanup**
   - audit preserved constructs
   - refactor `build_minimal_preamble()` into something more declarative

5. **Experimental tool graduation**
   - either harden `xy_to_tikz` into package code or keep it explicitly
     experimental until it meets the same standards as the core

---

## Bottom line

This repository is building something real and technically interesting. The core
idea is good, and the choice to validate against actual TeX output is stronger
than most projects in this space.

The main problem is not conceptual. It is organizational:

- the product surface is still behind the stated vision
- the workflow rules are ahead of their enforcement
- some boundaries that should already be clean are still improvised

My overall judgment is:

- **core technical direction**: strong
- **testing philosophy**: strong
- **workflow discipline on paper**: strong
- **workflow enforcement in code**: weaker than the docs imply
- **productization / packaging**: incomplete

If the next phase focuses on packaging, boundaries, and enforcement rather than
more process sophistication, the repo will get substantially stronger.
