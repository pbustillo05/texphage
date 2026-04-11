# texphage as a modular toolbox — refactor plan

## Goals

Three concrete outcomes drive this redesign:

- **A. Easy third-party import** — any Python tool can `from texphage import X` and call a single
  well-typed function. No knowledge of the internal pipeline required.
- **B. Easy CLI** — a `texphage` command (and per-tool siblings) that humans and LLM agents can
  call from a shell. Machine-readable JSON output for scripting.
- **C. Clear documentation** — `docs/guide/` houses one page per tool; `README.md` shows both
  Python and CLI Quick Starts; `docs/guide/README.md` serves as an index.

---

## Status snapshot

| Item | Status |
|---|---|
| Public API: `unfold`, `demacro`, `build_minimal_preamble` exported from `__init__.py` | ✅ Done |
| `CLAUDE.md` updated to toolbox framing | ✅ Done |
| `docs/guide/` with pages for demacro, unfold, pipeline, find_packages | ✅ Done |
| `CONTRIBUTING.md` added | ✅ Done |
| CLI (`src/texphage/cli.py` + `[project.scripts]` in pyproject.toml) | ⬜ Not yet |
| `converters/` sub-package (`_xy_tikzcd.py`) | ⬜ Not yet (xy converter still in `scripts/`) |
| `formatter.py` (pretty-printer) | ⬜ Not yet |
| `pyproject.toml` description updated to toolbox framing | ⬜ Not yet |
| `format` optional dependency declared | ⬜ Not yet |
| `docs/guide/README.md` index page | ⬜ Not yet |

---

## Goal A — Easy third-party import

**Already done.** `src/texphage/__init__.py` exports the full public API:

```python
from texphage import texphage, texphage_to_dir   # full pipeline
from texphage import unfold                        # unfold only
from texphage import demacro, build_minimal_preamble  # demacro only
from texphage import find_explicit_package_calls, find_used_packages, get_dependencies
from texphage import PackageCall, Attachment
```

Nothing needs to change here. The remaining work is ensuring these symbols stay stable
and are covered by the type stubs / docstrings.

**Future additions** (not yet implemented — add when the modules exist):

```python
from texphage.converters import xy_to_tikzcd   # once converters/ exists
from texphage import format_tex                # once formatter.py exists
```

---

## Goal B — Easy CLI

**Not yet done.** Create `src/texphage/cli.py` and register console scripts.

### Entrypoints

```toml
# pyproject.toml
[project.scripts]
texphage         = "texphage.cli:main"          # full pipeline (unfold + demacro)
texphage-unfold  = "texphage.cli:main_unfold"   # unfold only
texphage-convert = "texphage.cli:main_convert"  # converters (subcommand: xy)
# texphage-format = "texphage.cli:main_format"  # add once formatter.py exists
```

### Interface design

All commands share the same positional argument: a source directory or a single `.tex` file.

```
texphage <src>            → writes canonical.tex to stdout (or --out path)
texphage <src> --json     → JSON: {"tex": "...", "attachments": [...]}
texphage <src> --out DIR  → writes canonical.tex + attachments to DIR

texphage-unfold <src>               → flat .tex to stdout
texphage-unfold <src> --out FILE    → writes flat .tex

texphage-convert xy <file.tex>      → converted .tex to stdout
texphage-convert xy <file.tex> --out FILE
```

### `--json` flag — the LLM-friendly interface

`--json` is the key addition for LLM agent use. It emits a single JSON object on stdout:

```json
{
  "tex": "<canonical latex string>",
  "attachments": [
    {"tex_ref": "fig1.pdf", "src_path": "figures/fig1.pdf"}
  ]
}
```

This lets an LLM agent call `texphage . --json` and parse the result without
interpreting stdout/stderr split or file layout conventions.

### Error handling

On failure, all commands write a JSON error to stderr:
```json
{"error": "No main .tex file found", "code": 1}
```
and exit with a non-zero status. This keeps agent pipelines debuggable.

---

## Goal C — Clear documentation

**Partially done.** `docs/guide/` has four pages. Missing: an index.

### What to add

- `docs/guide/README.md` — index listing all guide pages with one-line descriptions
- Update `README.md` Quick Start to show CLI usage alongside Python import
- Update `pyproject.toml` `description` field from the current stale value to:
  `"A modular toolbox for LaTeX rearrangement: unfold, demacro, convert, format"`

### Existing guide pages (keep as-is)

- `docs/guide/pipeline.md` — full pipeline (texphage / texphage_to_dir)
- `docs/guide/demacro.md` — macro expansion
- `docs/guide/unfold.md` — multi-file flattening
- `docs/guide/find_packages.md` — package discovery

---

## Module layout (target)

```
src/texphage/
  __init__.py          ← stable public API (done)
  __version__.py
  _regex.py            ← all compiled patterns (done)
  unfold.py            ← done
  demacro.py           ← done
  pipeline.py          ← done
  cli.py               ← NEW: console entrypoints
  formatter.py         ← FUTURE: pretty-printer
  find_packages.py     ← done
  extract_latex.py     ← done
  converters/          ← FUTURE: when xy converter is ready
    __init__.py
    _xy_tikzcd.py      ← move + fix from scripts/xy_to_tikz.py
  data/
    order_usepackages.json
```

**Boundary note:** `converters/` only makes sense once there are ≥2 converters. Until then,
`scripts/xy_to_tikz.py` can stay where it is. Create the sub-package when moving it in.

---

## `texphage()` signature — composable flags (unchanged from earlier design)

Still the right target. Implement when formatter and xy converter exist:

```python
def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
    *,
    unfold: bool = True,
    demacro: bool = True,
    convert_xy: bool = False,
    pretty_print: bool = False,
    max_line_length: int | None = None,
    sentence_model: str | None = None,
) -> tuple[str, list[Attachment]]:
```

**Ordering constraint:** `convert_xy` must run before `demacro.preprocessing()` because
preprocessing collapses whitespace and destroys `\\` row separators inside `\xymatrix`:

```
unfold → convert_xy → preprocessing → demacro → build_minimal_preamble → pretty_print
```

---

## Optional dependencies

```toml
[project.optional-dependencies]
dev    = [...]         # unchanged
agents = [...]         # unchanged
format = ["ollama>=0.3"]   # future: only needed for sentence_model LLM pass
```

The formatter with LLM sentence detection is the only tool that adds a non-trivial runtime
dependency. Everything else (unfold, demacro, xy converter, CLI) runs on the already-required
`regex` package and stdlib.

---

## Implementation order

1. **CLI** (`src/texphage/cli.py` + `[project.scripts]`) — unblocks Goal B. Start with `main`
   and `main_unfold` (they wrap existing functions). Add `--json` output for LLM use.
2. **Docs landing page** (`docs/guide/README.md`) + README Quick Start CLI section + pyproject
   description fix — completes Goal C.
3. **xy converter** — fix known bugs in `scripts/xy_to_tikz.py`, move to
   `src/texphage/converters/`, wire up `texphage-convert xy`.
4. **Formatter** — implement `src/texphage/formatter.py`, add `texphage-format` CLI,
   add `format` optional dependency.
5. **VSCode LSP server** — separate project depending on `texphage` as a library. Out of scope
   for this repo.

---

## What does NOT need to change

- `_regex.py` layout and naming conventions — already correct, shared by all tools
- `demacro.py` and `unfold.py` internals — clean standalone modules
- Test structure — add parallel test files for new modules, don't reorganise existing ones
- Agent workflow (`arxiv-fidelity`, `coding-agent`, `quarterly-audit`) — applies equally to all tools
- The preprocessing contract (six ordered steps) — unchanged, documented in `CLAUDE.md`
