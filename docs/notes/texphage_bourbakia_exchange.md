# texphage / BourbakIA — Architectural Exchange Plan

> **Purpose.** Specifies exactly what code moves from BourbakIA to texphage,
> what new code is added to each repo, and how the two interact afterwards.
> Self-contained: an implementer can execute it without reading any other design file.
>
> **Status:** Design finalised through Q&A. Not yet implemented.
> **Supersedes:** the earlier draft in `BourbakIA/docs/texphage-exchange.md`.

---

## Architectural boundary

**texphage** = a collection of LaTeX morphisms (string → string transforms, string → dict
parsers, dict → string serializers). Every function it exposes is a pure algorithm that
operates on `.tex` content alone — no typed domain models, no LLM calls, no Claude Code
concepts, no BourbakIA dataclasses. Target consumers: NLP pipelines, human editors,
BourbakIA, and future tools yet unspecified. Each module is an independently usable
morphism; no single "master pipeline" is assumed.

**BourbakIA** = the orchestration layer. It calls texphage algorithms, maps plain-dict
outputs to typed dataclasses (`MathNode`, `SemanTexIndex`, …), stores artifacts, and
wires everything into Claude Code (MCP tools, LSP server, skills, hooks). It also owns
`semantex.sty` (until a potential CTAN submission).

**The boundary in one sentence:** if the algorithm runs on a `.tex` string using only
regex and string logic, it belongs in texphage; if it needs a typed domain model, an
LLM, or a Claude Code harness, it belongs in BourbakIA.

### Why `semantex.py` belongs in texphage despite its name

`texphage.semantex` only *reads* and *annotates* standard LaTeX structures — environments,
sections, display math, `\label`, `\iref`, `\decl`. It produces and consumes plain LaTeX
(specifically, standard `\label{…}` — not `\label*` from `semantex.sty`). This means
`texphage` has **no dependency on `semantex.sty`**; that file stays in BourbakIA. Any
`.tex` file can be passed to `texphage.semantex.parse()` without loading any extra
package — the module is opportunistic: it records what it finds.

---

## Current state

### texphage (`src/texphage/`)
- `_regex.py` — shared PCRE regex primitives (Sections 1–8)
- `demacro.py` — preprocessing, `build_dictionary()`, `expand()`, `demacro()`
- `unfold.py` — multi-file flattening
- `pipeline.py` — `texphage()`, `texphage_to_dir()`
- `formatter.py` — `texphage-format` CLI
- `xy_to_tikzcd.py` — `\xymatrix` → tikzcd converter
- `find_packages.py` — `kpsewhich`-based package discovery

### BourbakIA (`bourbakia/`)
- `model/__init__.py` — dataclasses + `SemanTexIndex`
- `lsp/parser.py` — regex scanner for SemanTex macros using manual brace-counting loops
- `lsp/rebuild_index.py` — project walker → `SemanTexIndex` → `build/index.json` + `build/deps.dot`
- `lsp/server.py` — pygls LSP server
- `mcp/` — MCP tools for Claude

---

## Part 1 — Changes to texphage

### 1a. `_regex.py` — two new sections

All compiled regex patterns used by new texphage modules must live in `_regex.py` with
the standard `MATCHES/CAPTURES/LIMITATIONS/USED BY` comment block. No `re.compile()`
calls elsewhere. No `import re` (stdlib) anywhere. Load `regex-writing` skill before
adding patterns; load `regex-danger-zone` before modifying existing ones.

#### Section 9 — SemanTex structural patterns (`semantex.py`)

Add patterns for:

- `_SEMANTEX_MACRO_RE` — finds `\label`, `\label*`, `\iref`, `\decl`, `\begin`, `\end`
  at call sites. Single compiled pattern fed to `regex.finditer()`.
- `_SECTION_CMD_RE` — finds `\chapter`, `\section`, `\subsection`, `\subsubsection`,
  `\paragraph`, `\subparagraph` with their mandatory `{title}` argument. Uses
  `embed_brackets('sarg')` for the title capture.
- `_DISPLAY_MATH_RE` — finds `\[…\]` and `$$…$$` display math blocks. The `\[…\]`
  variant uses `embed_brackets`-style recursive matching; `$$…$$` is simpler (no
  nesting). Must not match `\(…\)` (inline math).
- `_AUTO_LABEL_ID_RE` — matches texphage-generated label ids: `_{prefix}:_\d+$`.
  Used by BourbakIA to identify and replace machine-generated ids with LLM-chosen ones.

Use `embed_brackets` from Section 1 for all `{…}` argument captures. Do NOT write
manual brace-counting loops. The offset-table / line-number utilities (`_offset_table`,
`_offset_to_line`) are pure Python helpers, not regex — they live in `semantex.py`
directly (they manipulate the match positions returned by `regex`).

#### Section 10 — pgfkeys-lite key=value patterns (`semantex.py`, future `pgfkeys.py`)

Add a minimal key=value parser sufficient for `\decl[type=X, scope={a,b}]` option
strings. This is the foundation for the full pgfkeys plan
(`docs/notes/pgfkeys_implementation_plan.md`); the patterns here must be compatible with
that plan's later expansion.

- `_PGFKEYS_BRACE_VAL` — balanced `{…}` value using `embed_brackets('pgfv')`.
- `_PGFKEYS_PAIR_RE` — matches one `key=value` pair where value is either
  `_PGFKEYS_BRACE_VAL` or a sequence of non-comma, non-brace characters.
- `_PGFKEYS_ITEM_SEP_RE` — matches a top-level comma separator (not inside braces),
  used to split a key=value string into individual items.

These replace the manual character-loop in `bourbakia/lsp/parser.py::_parse_decl_options`.

---

### 1b. New module: `src/texphage/semantex.py`

Owns all regex-based reading and writing of SemanTex annotations. Three public functions.

#### `parse(source: str | Path, *, author: str = "unknown") -> dict`

Reads a `.tex` file (or string content) and returns a plain dict representing the
deterministic structural skeleton. Input is expected to be a single flat file (post
`unfold.py` if needed). Multi-file project navigation is deferred — see §Future.

**Return schema:**

```python
{
    "nodes": [
        {
            "id": str,           # content of \label{} or \label*{}
            "kind": str,         # "label" | "label_star"
            "node_type": str,    # "result" | "definition" | "proof" |
                                 # "subgraph" | "auxiliary" | "unknown"
            "env_name": str,     # raw LaTeX env name ("theorem", "proof", …)
                                 # or section command ("section", "chapter", …)
                                 # or "display_math" for \[…\] / $$…$$
            "file": str,         # absolute path (str); "" if source was a string
            "label_line": int,   # 1-indexed line of the \label macro
            "env_start": int,    # 1-indexed line of \begin{} or \section{};
                                 # 0 if label is outside any recognised structure
            "env_end": int,      # 1-indexed line of \end{}; 0 for sections/display
            "author": str,
        }
    ],
    "edges": [
        {
            "from_id": str,      # enclosing node's label id ("" if top-level)
            "to_id": str,        # referenced id; "project_id:node_id" for cross-project
            "kind": "iref",
            "file": str,
            "line": int,
            "author": str,
        }
    ],
    "variables": [
        {
            "symbol": str,
            "type_ref": str | None,   # \label id of a definition node
            "scope": list[str],        # list of subgraph node ids
            "file": str,
            "line": int,
            "author": str,
        }
    ],
}
```

**Implementation notes:**

- Use `_SEMANTEX_MACRO_RE` (Section 9 of `_regex.py`) as the main scanner via
  `regex.finditer()`.
- Use `_SECTION_CMD_RE` for a separate pass over section commands.
- Use `_DISPLAY_MATH_RE` for a separate pass over display math blocks.
- Brace argument extraction uses `embed_brackets`-based patterns from `_regex.py`,
  **not** manual `_read_brace_arg` character loops from `bourbakia/lsp/parser.py`.
- `_parse_decl_options` is rewritten using `_PGFKEYS_PAIR_RE` / `_PGFKEYS_ITEM_SEP_RE`
  from Section 10. No character loops.
- `_offset_table` and `_offset_to_line` (pure Python binary-search helpers, not regex)
  may be copied from `bourbakia/lsp/parser.py` — they manipulate list indices, not
  LaTeX structure, and are therefore exempt from the regex-only rule.
- `_ENV_TO_TYPE` mapping lives in `semantex.py`.
- The env_stack is maintained via Python list (stateful scan), which is correct here:
  the scanner is inherently sequential and a regex alone cannot track nested state.
- `label*` outside a recognised environment records `node_type: "unknown"` rather than
  being silently dropped (deviation from current BourbakIA parser which drops them).

**Section node handling:**

`\section{title}`, `\subsection{title}`, etc. produce `node_type: "subgraph"` nodes.
`env_name` is set to the command name without backslash (e.g. `"section"`). `env_start`
is the line of the `\section` command. `env_end` is 0 — section boundaries are not
determinable by a single-pass scanner without full document structure. BourbakIA's LLM
pass handles logical section extent.

**Display math node handling:**

`\[…\]` and `$$…$$` produce `node_type: "auxiliary"` nodes with `env_name:
"display_math"`. A label is only recorded if one is found inside the block. `parse()`
does **not** insert labels — that is `annotate()`'s job. `env_end` records the closing
line.

---

#### `annotate(tex_str: str, *, prefix_map: dict[str, str] | None = None) -> str`

Inserts `\label{auto_id}` macros into every unlabeled structure that should be a
SemanTex node. Never modifies structures that already have a `\label` or `\label*`
inside. Returns the modified string.

**Auto-ID scheme:**

Generated ids take the form `{prefix}:_{N}` where:
- `prefix` comes from `prefix_map` (e.g. `"thm"` for theorem environments)
- `N` is an integer (no padding), starting at 1 per prefix, incremented globally
  across the document — never reusing a number even if the prefix differs

Examples: `thm:_1`, `sec:_2`, `eq:_3`.

**Why this scheme:** The underscore-then-number suffix is the machine-generation marker.
BourbakIA identifies auto-generated labels by matching `[^:]+:_\d+$` and replaces them
with LLM-chosen meaningful ids during its enrichment pass. Any label NOT matching this
pattern was written by the user and must never be overwritten by `annotate()`.

**Default `prefix_map`:**

```python
{
    # result environments
    "theorem": "thm", "thm": "thm",
    "lemma": "lem", "lem": "lem",
    "proposition": "prop", "prop": "prop",
    "corollary": "cor", "cor": "cor",
    "remark": "rem",
    # definition environments
    "definition": "def", "defn": "def",
    # proof environments
    "proof": "prf",
    # section commands
    "chapter": "chap",
    "section": "sec", "subsection": "sec",
    "subsubsection": "sec", "paragraph": "sec",
    # auxiliary environments
    "figure": "fig", "figure*": "fig",
    "equation": "eq", "equation*": "eq",
    "align": "eq", "align*": "eq",
    "table": "tab", "table*": "tab",
    "algorithm": "alg",
    # display math shorthand
    "display_math": "eq",
}
```

**Algorithm:**

1. Collect all existing `\label{…}` and `\label*{…}` ids to avoid duplication.
2. Find all `\begin{env}…\end{env}` blocks whose `env` is in `prefix_map`.
3. Find all section commands (`\section`, etc.) whose name is in `prefix_map`.
4. Find all `\[…\]` and `$$…$$` display math blocks (prefix `"display_math"`).
5. For each unlabeled structure:
   - Proof immediately following a labeled result: use `prf:{result_id}` (deterministic,
     not `prf:_N`). "Immediately following" means no non-whitespace content between
     `\end{result_env}` and `\begin{proof}`.
   - All other structures: use `{prefix}:_{N}`, incrementing the shared counter.
6. Insert `\label{generated_id}\n` as the first line of the environment body
   (after `\begin{envname}`), or as the line immediately after `\section{title}`,
   or as the first line inside `\[` / after opening `$$`.
7. Ensure `\begin{envname}` is on its own line before insertion.

**Display math insertion details:**

`\label{eq:_N}` is inserted inside `\[…\]` and `$$…$$` without converting the
environment. This is valid standard LaTeX: `\label` inside an unnumbered display math
block defines the label without tying it to a float number. PDF output is unaffected.
Rationale: converting `\[…\]` to `\begin{equation}` would silently change behaviour if
the user has redefined the `equation` environment in their preamble. We don't touch the
display math syntax — only the label is added.

```latex
% Before:
\[
  E = mc^2
\]

% After:
\[
\label{eq:_1}
  E = mc^2
\]
```

---

#### `process(source: str | Path, *, author: str = "unknown", prefix_map: dict[str, str] | None = None) -> tuple[str, dict]`

Annotate then parse in one call.

```python
def process(source, *, author="unknown", prefix_map=None):
    """Annotate unlabeled structures then parse the result.

    If source is a Path, reads file content first.
    Returns (annotated_tex_str, graph_dict).
    """
    tex = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    annotated = annotate(tex, prefix_map=prefix_map)
    graph = parse(annotated, author=author)
    return annotated, graph
```

Note: `parse()` receives the annotated string, not a path — `file` fields in the
returned dict will be `""`. Pass a `Path` directly to `parse()` for file attribution.

---

#### Tests

Add `tests/test_semantex.py`:

- `parse`: minimal annotated snippet → correct node/edge/variable dicts
- `parse`: `\label*` sets `kind: "label_star"` correctly
- `parse`: cross-project `\iref{project:node}` passes through as-is
- `parse`: `\section{title}` produces `node_type: "subgraph"`, `env_name: "section"`
- `parse`: `\[…\]` with a label inside produces `node_type: "auxiliary"`, `env_name: "display_math"`
- `parse`: `\label` outside any recognised structure → `node_type: "unknown"` (not dropped)
- `annotate`: adds `\label{thm:_1}` to first unlabeled theorem
- `annotate`: does not touch environments that already have `\label` or `\label*`
- `annotate`: proof following `thm:foo` gets `prf:foo` (not `prf:_N`)
- `annotate`: `\section{title}` gets `sec:_N` label on the next line
- `annotate`: `\[…\]` gets `\label{eq:_N}` inserted inside without environment conversion
- `annotate`: auto-ids never collide even across different prefixes (shared counter)
- `process`: `parse(annotated)` matches graph returned by `process(raw)`

All test assertions grounded in `scripts/latex_playground.py` output (playground protocol).

---

### 1c. `demacro.py` — no changes required

`build_dictionary()` already returns exactly what BourbakIA needs: `(macro_dict,
find_macro)`. BourbakIA calls it directly and owns persistence via `dill` (see §2b–2c).
`demacro.py` is untouched by this plan.

---

## Part 2 — Changes to BourbakIA

### 2a. `bourbakia/lsp/parser.py` → thin adapter

Replace the current `parse_file()` implementation (~270 lines) with a call to
`texphage.semantex.parse()` and a mapping layer (~40 lines).

```python
# bourbakia/lsp/parser.py  (new content)

from pathlib import Path
import texphage.semantex as _tex
from bourbakia.model import DependencyEdge, MathNode, VariableRecord
from dataclasses import dataclass

@dataclass
class ParseResult:
    nodes: list[MathNode]
    edges: list[DependencyEdge]
    variables: list[VariableRecord]

def parse_file(path: Path, author: str = "unknown") -> ParseResult:
    raw = _tex.parse(path, author=author)
    nodes = [MathNode(id=n["id"], type=n["node_type"], file=n["file"],
                      line=n["label_line"], author=n["author"],
                      env_start=n["env_start"], env_end=n["env_end"])
             for n in raw["nodes"]]
    edges = [DependencyEdge(from_id=e["from_id"], to_id=e["to_id"],
                            kind=e["kind"], author=e["author"])
             for e in raw["edges"]]
    variables = [VariableRecord(symbol=v["symbol"], type_ref=v["type_ref"],
                                scope=v["scope"],
                                declared_at={"file": v["file"], "line": v["line"]},
                                author=v["author"])
                 for v in raw["variables"]]
    return ParseResult(nodes=nodes, edges=edges, variables=variables)
```

`rebuild_index.py` continues calling `parse_file()` — no changes there.

---

### 2b. `bourbakia/model/__init__.py` — add `MacroCache`

`build_dictionary()` output contains Python closures and lambdas — not JSON-serializable.
`dill` (added to BourbakIA's dependencies) serializes them transparently.

```python
import hashlib
from dataclasses import dataclass
from pathlib import Path
import dill  # type: ignore[import-untyped]

@dataclass
class MacroCache:
    """Pickled macro dictionary for a project's preamble.

    Stored in build/macros.pkl. Used by the LSP and MCP tools to expand
    macros in hover snippets without re-parsing the preamble on every request.
    Invalidated when the preamble sha256 changes.
    """
    macro_dict: dict        # csname → [pattern_str, content_fn]
    find_macro: str         # compiled-ready alternation string
    preamble_hash: str      # sha256 of the preprocessed preamble string
    file: str               # absolute path of the main .tex file

    def save(self, path: Path) -> None:
        with path.open("wb") as f:
            dill.dump(self, f)

    @classmethod
    def load(cls, path: Path) -> "MacroCache":
        with path.open("rb") as f:
            return dill.load(f)

    def is_stale(self, current_preamble: str) -> bool:
        return hashlib.sha256(current_preamble.encode()).hexdigest() != self.preamble_hash
```

`dill` goes in BourbakIA's `pyproject.toml` regular dependencies (not optional — the LSP
always needs it). It does not become a texphage dependency.

---

### 2c. `bourbakia/lsp/rebuild_index.py` — also build `build/macros.pkl`

The main `.tex` file path is given as a parameter. No hard-coded assumptions.

```python
from texphage.demacro import preprocessing, build_dictionary
from bourbakia.model import MacroCache
import hashlib

def _build_macro_cache(main_tex: Path) -> MacroCache:
    """Parse macro definitions from the preamble of the main .tex file."""
    raw = main_tex.read_text(encoding="utf-8", errors="replace")
    preamble, _, _ = preprocessing(raw)
    macro_dict, find_macro = build_dictionary(preamble)
    preamble_hash = hashlib.sha256(preamble.encode()).hexdigest()
    return MacroCache(
        macro_dict=macro_dict,
        find_macro=find_macro,
        preamble_hash=preamble_hash,
        file=str(main_tex),
    )
```

In `rebuild()`, after building the SemanTexIndex:

```python
main_tex = _resolve_main_tex(project_dir)
if main_tex:
    _build_macro_cache(main_tex).save(build_dir / "macros.pkl")
```

`_resolve_main_tex`: the path is passed in from the caller; falls back to the `.tex`
file sharing the project directory name; falls back to the first `.tex` file found.

---

### 2d. `bourbakia/lsp/server.py` — richer LSP features

#### Hover over a custom macro → demacro'd expansion

Load `MacroCache` alongside `_index`. Keep `(macro_dict, find_macro)` in module-level
variables and update them on every rebuild.

```python
from texphage.demacro import expand, preprocessing, build_dictionary
from bourbakia.model import MacroCache

_macro_cache: MacroCache | None = None

def _load_macro_cache(project_root: Path) -> None:
    global _macro_cache
    pkl = project_root / "build" / "macros.pkl"
    if pkl.exists():
        _macro_cache = MacroCache.load(pkl)

# In hover handler, after SemanTex-macro checks:
import regex as _re
cs = _re.search(r'\\([a-zA-Z]+)', line[max(0, col-15):col+15])
if cs and _macro_cache and cs.group(1) in _macro_cache.macro_dict:
    csname = cs.group(1)
    sample = _make_sample_args(csname, _macro_cache.macro_dict[csname])
    expanded, _ = expand(sample, _macro_cache.macro_dict, _macro_cache.find_macro)
    return types.Hover(contents=types.MarkupContent(
        kind=types.MarkupKind.Markdown,
        value=f"**macro** `\\{csname}` → `{expanded}`"
    ))
```

`_make_sample_args(csname, macro_def)` generates placeholder argument strings (`{?}`,
`[?]`) based on the pattern string in `macro_def[0]`.

#### Code action: convert `\xymatrix` to tikzcd

```python
from texphage.xy_to_tikzcd import convert_xy_body, convert_xy_preamble

@server.feature(types.TEXT_DOCUMENT_CODE_ACTION)
def code_action(ls, params):
    # Detect \xymatrix in the cursor range
    # Offer WorkspaceEdit that replaces the block with tikzcd output
    # Also replaces \usepackage{xy} → \usepackage{tikz-cd} in preamble
    ...
```

---

### 2e. Ingest pipeline — future

When `bourbakia/ingest/` is built, Stage 0.5–0.7 will be:

```python
from texphage.semantex import annotate, parse
from texphage.demacro import preprocessing, build_dictionary

# Stage 0 output: unfold'd + demacro'd flat .tex string
flat_tex = texphage(src_dir)

# Stage 0.5: annotate with deterministic labels
annotated_tex = annotate(flat_tex)

# Stage 0.6: parse deterministic skeleton
graph_dict = parse(annotated_tex, author=ingestion_model_name)

# Stage 0.7: build macro cache for hover expansion
preamble, _, _ = preprocessing(flat_tex)
macro_dict, find_macro = build_dictionary(preamble)
MacroCache(macro_dict, find_macro, sha256(preamble), file=str(src)).save(out / "macros.pkl")

# Stage 1+: LLM enrichment (BourbakIA-owned)
```

---

## New build artifacts

After this refactoring, a SemanTex project's `build/` directory contains:

```
build/
├── index.json      # SemanTexIndex (unchanged schema)
├── deps.dot        # Graphviz DOT (unchanged)
└── macros.pkl      # MacroCache: dill-pickled (macro_dict, find_macro) + preamble hash
```

`macros.pkl` is a `dill`-pickled `MacroCache` dataclass. It is not human-readable.
Invalidation: on load, compare `MacroCache.preamble_hash` against the sha256 of the
current preprocessed preamble; rebuild if they differ. Stale or corrupt files should
be deleted and rebuilt — `MacroCache.load()` raises on unpickle errors.

---

## Migration order

Each step leaves both repos in a working state. Steps 1–3 and 4 are independent
and can be developed in parallel once Step 1 is complete.

### Step 1 — `_regex.py`: Sections 9 and 10

1. Add Section 9 (SemanTex structural patterns) to `_regex.py`.
2. Add Section 10 (pgfkeys-lite key=value patterns).
3. Load `regex-writing` skill. Add each pattern with full comment block.
4. Run test suite; all existing tests must pass.

### Step 2 — `semantex.py`: `parse()`

1. Create `src/texphage/semantex.py`.
2. Implement `parse()` using Section 9 patterns and `_offset_table`/`_offset_to_line`.
3. Implement `_parse_decl_options` using Section 10 patterns (no character loops).
4. Add `tests/test_semantex.py` covering parse cases.
5. Export `parse` from `texphage/__init__.py`.
6. Run full test suite. Bump texphage version (minor).

### Step 3 — BourbakIA: swap `parser.py`

1. Add texphage as a dependency in BourbakIA's `pyproject.toml`.
   Development: `pip install -e ../texphage`.
2. Replace `bourbakia/lsp/parser.py` with the thin adapter.
3. Run BourbakIA test suite; verify `rebuild_index` produces identical `index.json`.

### Step 4 — `semantex.py`: `annotate()` + `process()`

1. Add `annotate()` to `semantex.py`.
2. Add `process()` wrapper.
3. Extend `tests/test_semantex.py` with annotate cases (including display math and
   section annotation, grounded in playground output).
4. Bump texphage version.

### Step 5 — BourbakIA: `MacroCache` + `build/macros.pkl`

1. Add `dill` to BourbakIA's `pyproject.toml` dependencies.
2. Add `MacroCache` dataclass to `bourbakia/model/__init__.py`.
3. Update `rebuild_index.py` to call `preprocessing()` + `build_dictionary()` and
   write `build/macros.pkl` via `MacroCache.save()`.
4. Update `server.py` to call `_load_macro_cache()` after every rebuild.

### Step 6 — BourbakIA: LSP macro hover

1. Add macro-expansion hover branch to `server.py` (calls `expand()` directly with
   the in-memory `macro_dict` and `find_macro` from `_macro_cache`).
2. Test manually in VS Code: hover over a custom macro → expansion shown.

### Step 7 — BourbakIA: LSP code action for xy→tikzcd (optional, v2)

1. Add `textDocument/codeAction` handler.
2. Test manually in VS Code.

### Step 8 — BourbakIA: ingest pipeline (when `ingest/` is built)

1. Wire `annotate()` as Stage 0.5.
2. Wire `parse()` as Stage 0.6.
3. Wire `build_dictionary()` + `MacroCache.save()` as Stage 0.7.

---

## What does NOT move

| Component | Stays in | Why |
|-----------|----------|-----|
| `semantex.sty` | BourbakIA | `annotate()` uses standard `\label{}` — texphage has no dependency on this file |
| `bourbakia/model/__init__.py` | BourbakIA | Typed dataclasses + `SemanTexIndex` graph queries |
| `bourbakia/lsp/rebuild_index.py` | BourbakIA | Project walker + index builder depends on `model` |
| `bourbakia/lsp/server.py` | BourbakIA | pygls LSP server, VS Code / Claude integration |
| `bourbakia/mcp/` | BourbakIA | MCP tools for Claude |
| `bourbakia/ingest/` | BourbakIA | LLM orchestration; calls texphage but owns the pipeline |

---

## Future enhancements (not in this plan)

**`unfold.py` project navigation object.** Currently `unfold.py` returns a single flat
`.tex` string. Eventually it should also return a Python object that records the
file-origin of each text span, enabling `semantex.parse()`, `demacro.expand()`, and
other morphisms to file-hop rather than work on a single flat string. `parse()` would
then populate `"file"` fields accurately even in multi-file projects. This is a
significant refactor of `unfold.py` deferred until the single-file path is solid.

**Full pgfkeys support.** Section 10 of `_regex.py` is intentionally scoped to `\decl`
option strings. Full pgfkeys support (handling `\pgfkeys`, `\tikzset`, `.code` handlers,
key inheritance) is specified in `docs/notes/pgfkeys_implementation_plan.md` and will
build on the Section 10 foundation.

---

## New public API in texphage after this plan

```python
# texphage.semantex  (new module)
from texphage.semantex import parse, annotate, process

graph_dict          = parse("path/to/annotated.tex", author="pablo")
annotated_str       = annotate(raw_tex_str)
ann_str, graph_dict = process("path/to/raw.tex", author="pablo")
```

`texphage.demacro` is **unchanged**: `demacro()`, `build_dictionary()`, `expand()`,
and `preprocessing()` keep their existing signatures. BourbakIA calls them directly.
