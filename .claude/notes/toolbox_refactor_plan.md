# Refactor plan: texphage as a modular toolbox

## Why refactor

The project's stated goal has shifted from "produce a canonical 5-line NLP
input" to a **general LaTeX rearrangement toolbox** — a family of tools that
share the same regex engine, preprocessing contract, and testing
infrastructure, but can be used independently of each other.

The current codebase was designed around a single pipeline:
`unfold → demacro → build_minimal_preamble`. This is fine as one tool, but
several planned applications (pretty-printer, xy→tikzcd converter, future
structure extractors) are not sub-steps of that pipeline — they are
independent transformations that happen to reuse the same engine.

This note describes the structural changes needed to support that wider scope
without breaking what already works.

---

## What needs to change

### 1. Public API surface: distinguish tools from pipeline

**Current:** `pipeline.py` exposes `texphage()` and `texphage_to_dir()`.
These are monolithic: unfold + demacro + preamble extraction in one call.

**Target:** Each tool should be independently importable:

```python
from texphage import unfold          # unfold only
from texphage import demacro         # demacro only (body + preamble)
from texphage import format_tex      # pretty-printer
from texphage.converters import xy_to_tikzcd   # package-dep converter
from texphage import texphage        # the full pipeline (convenience wrapper)
```

The convenience `texphage()` function remains and keeps its current
signature. It is just a thin orchestrator over the individual tools —
which it already essentially is.

**Concrete change needed:** expose `unfold()`, `demacro()`, and
`build_minimal_preamble()` directly from `texphage/__init__.py` as
first-class public API, not as internal implementation details of
`pipeline.py`.

---

### 2. Module layout: add `converters/` sub-package

**Current:** `src/texphage/` is flat. There is no home for converters.

**Target:**

```
src/texphage/
  __init__.py          ← re-export all public API
  __version__.py
  _regex.py            ← compiled patterns (unchanged)
  unfold.py            ← unchanged
  demacro.py           ← unchanged
  pipeline.py          ← orchestrator, thin wrapper
  formatter.py         ← NEW: pretty-printer
  find_packages.py     ← unchanged
  extract_latex.py     ← unchanged
  converters/
    __init__.py
    _xy_tikzcd.py      ← xy→tikzcd pure string functions
    # future: _eqnarray.py, _psfig.py, …
  data/
    latexindent_texphage.yaml   ← NEW: bundled config for formatter
```

This layout makes it clear that `converters/` is a family of optional
transformations, while `demacro`, `unfold`, and `formatter` are core tools.

**Alternative considered:** keep everything flat and prefix with `_` for
internal modules. Rejected: converters have a qualitatively different
contract (lossy / approximate) from the core tools (must be PDF-identical),
and grouping them makes that boundary visible.

---

### 3. `texphage()` signature: composable tool flags

**Current:**
```python
def texphage(src_dir, main_tex=None) -> tuple[str, list[Attachment]]
```

**Target:** add optional, independently controllable tool flags:

```python
def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
    *,
    # core tools (all on by default)
    unfold: bool = True,
    demacro: bool = True,
    # optional transformations (all off by default)
    convert_xy: bool = False,
    pretty_print: bool = False,
    max_line_length: int | None = None,
    sentence_model: str | None = None,
) -> tuple[str, list[Attachment]]:
```

All flags default to the current behaviour. Adding a flag never breaks
existing callers.

**Ordering constraint (from `xy_to_tikz_implementation.md` §2.3):** `convert_xy`
must run BEFORE `demacro.preprocessing()` because preprocessing collapses
whitespace and destroys `\\` row separators inside `\xymatrix`. The internal
call order is:
```
unfold → convert_xy → preprocessing → demacro → build_minimal_preamble
                                                      → pretty_print
```

---

### 4. CLI: one entrypoint per tool

**Current:** No CLI entrypoints (aside from test scripts).

**Target:**

```toml
[project.scripts]
texphage          = "texphage.cli:main"         # full pipeline
texphage-format   = "texphage.cli:main_format"  # pretty-printer only
texphage-unfold   = "texphage.cli:main_unfold"  # unfold only
texphage-convert  = "texphage.cli:main_convert" # converters (subcommand: xy)
```

`texphage-format` and `texphage-unfold` are useful standalone tools for
humans who do not need the full pipeline. `texphage-convert` is a generic
entry point for all converters (with subcommands as new converters are added).

All CLI entrypoints should share a common `src/texphage/cli.py` module.
This module does not exist yet; create it during formatter implementation.

---

### 5. Optional dependencies: make tools independently installable

**Current:** `[dev]` and `[agents]` extras. No extras for specific tools.

**Target:**

```toml
[project.optional-dependencies]
dev    = [...]                        # unchanged
agents = [...]                        # unchanged
format = ["ollama>=0.3"]              # for sentence_model LLM pass
# no extra needed for xy converter — it's pure regex
```

The formatter (with LLM sentence detection) is the only tool that adds a
non-trivial runtime dependency. Everything else runs on the already-required
`regex` and stdlib.

---

### 6. `CLAUDE.md` and `docs/project-context.md`: update framing

`project-context.md` §"Project goal" currently reads:

> texphage takes an arXiv LaTeX tarball and produces a canonical 5-line
> document … Primary use: feeding NLP pipelines …

This should be updated to describe the toolbox framing (see `docs/user_applications.md`).
The 5-line pipeline description should move to a §"Core tool: demacro" subsection,
not serve as the project-level lede.

`CLAUDE.md` §"Your role" needs a corresponding update to mention the formatter
and converters as in-scope implementation work, alongside the existing pipeline.

---

## What does NOT need to change

- `_regex.py` layout and naming conventions — already correct, shared by all tools
- `demacro.py` internals — the preprocessing contract is unchanged
- `unfold.py` internals — already a clean standalone module
- Test structure (`tests/test_demacro.py`, etc.) — add parallel test files
  for new modules, don't reorganise existing ones
- The `testing-agent` / `coding-agent` / `quarterly-audit` workflow — applies
  equally to all tools

---

## Suggested implementation order

1. **Now (no code change):** Update `project-context.md` framing and `CLAUDE.md`.
   This costs nothing and aligns all future work. (Tracked: TODO.md)
2. **With formatter:** Create `src/texphage/cli.py` and `formatter.py`.
   Add `texphage-format` CLI entrypoint. This is the next concrete tool to
   implement (see `.claude/notes/pretty_printer_implementation.md`).
3. **With xy converter:** Create `src/texphage/converters/` sub-package and
   move/rewrite `scripts/xy_to_tikz.py` into it. Add `texphage-convert xy`
   CLI. (See `.claude/notes/xy_to_tikz_implementation.md`.)
4. **After both:** Update `texphage/__init__.py` to expose the new public API
   surface and update the `texphage()` signature with tool flags.
5. **Later:** LSP server / VSCode extension — this is the most novel piece and
   should wait until the core tools are stable.

---

## Risks and non-goals

- **Don't break the existing pipeline.** All changes are additive or
  signature-compatible. Never remove or rename existing public symbols.
- **Don't over-abstract prematurely.** The `converters/` sub-package only
  makes sense once there are at least two converters. Until then, a single
  `_xy_tikzcd.py` file is sufficient.
- **The LSP server is a separate project.** It would depend on `texphage` as
  a library but live in its own repo. Don't try to fit it inside this package.
