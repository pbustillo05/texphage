# Benchmarking Pipeline — Unified Design Plan

> **Status:** Working draft — brainstorming in progress. Open questions at the bottom.

## Context

TODO.md carries two related items:
- **Note 5** (priority 4/5, accepted) — Per-run success rate tracking. *Status: substantially done.* `results.jsonl` is being written, `success_rate.py` exists.
- **Note 6** (priority 1/5, proposed) — Benchmark demacro against competing tools.

Goal: merge these into one coherent benchmarking system with three purposes:
1. **Tool survey** — Know exactly what macro types / file-resolution patterns each competing tool handles.
2. **Continuous rolling metrics** — See our own success rate evolve over time (already mostly done).
3. **Published benchmark** — A rigorous, reproducible comparison against the field.

**Important framing**: the two main tools in texphage — `demacro` and `unfold` — require *different* benchmark designs because they do fundamentally different things and have different sets of competitors.

---

## Design Decisions (confirmed)

| Question | Decision |
|---|---|
| Chunk strategy (demacro) | **Mixed**: character-count tier targets (200, 500, 1k, 2k, 5k, 10k, 20k, 50k chars), snapped forward to nearest structural unit boundary. |
| Tool survey depth | **Hybrid**: source survey all discovered tools → macro/feature coverage table; empirical run on top-2 rivals only. |
| Primary success metric | **Multi-tier**: compile%, exact%, near_exact% (text-diff ≤ 1 line AND SSIM ≥ 0.99), acceptable%. Headline = near_exact%. |

---

## Two Separate Benchmark Tracks

### Track 1 — `demacro` benchmark (complex, size-stratified)

Demacro's success is strongly size-dependent: a snippet with 3 macros almost always works; a full paper with 50 macros often fails. The decay curve reveals *where* the tool breaks down.

**Core idea**: for each paper, extract snippets at increasing body sizes (keeping whole preamble). Plot success-rate vs. log(body_chars). The tool whose curve stays high longest wins.

**What "success" means**: the snippet compiled AND near-exactly matches the baseline compilation of the same snippet.

### Track 2 — `unfold` benchmark (simpler, binary)

Unfold takes a multi-file LaTeX project (`\input`, `\include`, etc.) and merges it into one flat `.tex` file. Success is binary: does the merged file compile and produce an equivalent PDF?

There is no size-stratification needed here — either the whole project unfolds correctly or it doesn't. The interesting variation is across *project structures* (depth of nesting, use of `\inputfrom`, `\subimport`, conditional includes, etc.).

**What "success" means**: `unfold(project)` produces a single `.tex` that compiles to a near-identical PDF as the original multi-file project.

**Benchmark design**:
- Filter arXiv papers to those with ≥2 source files in the tarball.
- Compile the multi-file original as baseline.
- Run `unfold`, compile result, compare.
- No snippet extraction; just whole-project evaluation.
- Stratify by *nesting depth* and *number of files* rather than body size.

---

## Tool Survey (completed)

See **`docs/notes/tool_survey.md`** for the full survey, synthesized from 7 LLM research passes.
Raw LLM responses are in `docs/tool_comparison/`.

**Key findings relevant to the benchmark:**

- **Demacro track rivals**: `de-macro` (CTAN, Python, purpose-built), `expand-latex-macros`
  (PyPI, Python, NLP-focused, v2.0.0 Apr 2025), `flachtex` (PyPI, Python, macro substitution
  mode, v1.0.0 Nov 2025). Pandoc as an optional upper-bound reference.
- **Unfold track rivals**: `latexpand` (Perl, CTAN gold standard, v1.7.2), `flachtex` (Python,
  best modern alternative with `\subimport` support).
- **Key differentiator for unfold**: texphage handles `\import`/`\subimport`/`\inputfrom`
  (import package commands). Most rivals — including latexpand — do not.
- **Key differentiator for demacro**: texphage handles `\def`, `\let`, `\newenvironment`,
  counters, and starred variants. de-macro handles only `\newcommand`/`\newenvironment` with
  no `\def`/`\let`.

---

## What Already Exists (do not rebuild)

- `scripts/test_fidelity.py` — full per-paper fidelity harness with SSIM, text diff, severity.
- `tests/runs/results.jsonl` — append-only log, one JSON object per paper.
- `scripts/success_rate.py` — rolling success rate computer.
- `_compare()` in `test_fidelity.py` — severity classifier + SSIM + text diff. **Reuse for snippet comparisons.**
- `scripts/arxiv_categories.json` — full arXiv category list for uniform sampling.

---

## New Components to Build

### A. Snippet Extractor — demacro track only (`scripts/benchmark/snippets.py`)

**Purpose**: Given `(preamble: str, body: str)`, produce progressively larger body slices snapped to structural boundaries.

**Tier targets** (body chars): `[200, 500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000, ∞]`  
`∞` = full body (always included).

**Structural unit parsing** (using patterns from `_regex.py`):
1. Split body into units by scanning for these boundaries:
   - Paragraph: blank-line / `\par` (finest)
   - Environment: `\begin{...}...\end{...}` block
   - Subsection: `\subsection` / `\subsubsection` marker
   - Section: `\section` marker (coarsest)
2. For each tier T: walk units accumulating chars; when cumulative ≥ T, snap to end of current unit.
3. Skip tiers where body is shorter than T (no truncation = just the full body).

**Output type**:
```python
@dataclass
class SnippetSlice:
    tier_target_chars: int   # tier requested (or math.inf)
    actual_chars: int        # chars after boundary snap
    num_units: int
    body_content: str
```

**Key rule**: must use `import regex as re` — no stdlib re. New patterns go through the `regex-writing` skill protocol.

**Snapping direction**: always snap *forward* (include more content rather than less). Tiers near the top of a paper may collapse to the same slice — deduplicate before running.

---

### B. Benchmark Corpus (`docs/notes/benchmark_corpus_demacro.json`, `benchmark_corpus_unfold.json`)

**Fixed, committed corpus** for each track:
- Demacro: 50 papers, uniform category sampling, seed=2026, ≤2 per category.
- Unfold: 50 multi-file papers (≥2 source files in tarball), same sampling strategy.

`scripts/benchmark/corpus.py` exposes `load_corpus()`, `download_corpus()`, `generate_corpus()`.

---

### C. Tool Adapter Interface (`scripts/benchmark/adapters/`)

```python
class ToolAdapter(Protocol):
    name: str
    version: str
    def transform(self, tex: str) -> str: ...  # raises TransformError on failure
```

- `texphage.py` — wraps `texphage()` (demacro reference)
- `texphage_unfold.py` — wraps `unfold()` (unfold reference)
- Rival adapters added after survey.

**Adapter contract**: input is a complete `.tex` document string; output is a transformed `.tex`; `TransformError` counts as 0% on all metrics for that paper.

---

### D. Benchmark Runner (`scripts/benchmark/run_benchmark.py`)

```
python scripts/benchmark/run_benchmark.py \
    --track demacro|unfold \
    --tools texphage demacro_ctan \
    --corpus docs/notes/benchmark_corpus_demacro.json \
    --n 20 \
    --out tests/benchmark/ \
    --resume
```

**demacro inner loop** (per tool × paper × tier):
1. Extract snippet.
2. Compile *baseline* snippet (original, no transformation). Skip tier if baseline fails.
3. Run `tool.transform(snippet)`.
4. Compile transformed snippet.
5. Compute text_diff_lines (pdftotext), SSIM.
6. Classify: `compile_success`, `exact` (text_diff==0 AND SSIM==1.0), `near_exact` (text_diff≤1 AND SSIM≥0.99), `acceptable` (severity==OK).
7. Append to `tests/benchmark/results.jsonl`.

**unfold inner loop** (per tool × paper):
1. Count source files; skip if < 2.
2. Compile original multi-file project as baseline.
3. Run `tool.transform(project_dir)` → single `.tex`.
4. Compile output, compare.
5. Extra fields: `num_source_files`, `max_nesting_depth`.

**Parallelism**: papers in parallel (reuse locking protocol from `test_fidelity.py`). Tools run sequentially on same paper to share baseline PDF.

**Token efficiency**: only compute SSIM when both PDFs exist AND page count matches (CLAUDE.md rule).

---

### E. Benchmark Report Generator (`scripts/benchmark_report.py`)

Reads `tests/benchmark/results.jsonl`, updates `docs/notes/benchmark_comparison.md`.

- **Table 1** — Per-tool summary: compile%, exact%, near_exact%, acceptable%
- **Table 2** — Decay curve: per tool × tier (demacro only)
- **Table 3** — Unfold success by project complexity (# files, nesting depth buckets)
- **Table 4** — Error breakdown per tool

---

### F. `results.jsonl` Schema Extension (backward compatible)

```json
{
  "...existing fields...",
  "snippet_tier_chars": null,   // null = whole paper; int = tier target
  "actual_body_chars": null,    // null = whole paper; int = actual after snap
  "benchmark_tool": null,       // null = rolling test; string = competitor name
  "benchmark_track": null       // null = rolling; "demacro" | "unfold"
}
```

`success_rate.py` filters to `snippet_tier_chars == null` — existing behavior unchanged.

---

## File Layout

```
docs/notes/
├── benchmark_plan.md                   ← this file
├── benchmark_comparison.md             ← committed; survey + auto-generated tables
├── benchmark_corpus_demacro.json       ← committed; fixed 50-paper corpus
├── benchmark_corpus_unfold.json        ← committed; fixed 50 multi-file papers

scripts/
├── benchmark/
│   ├── __init__.py
│   ├── corpus.py
│   ├── snippets.py                     ← size-stratified extractor (demacro only)
│   ├── run_benchmark.py                ← CLI; --track demacro|unfold
│   └── adapters/
│       ├── __init__.py
│       ├── base.py                     ← ToolAdapter protocol + TransformError
│       ├── texphage.py
│       ├── texphage_unfold.py
│       └── (rivals added after survey)
├── benchmark_report.py
└── success_rate.py                     ← existing, unchanged

tests/
└── benchmark/
    ├── results.jsonl                   ← gitignored
    └── .gitkeep
```

---

## Implementation Phases

### Phase A — Tool survey (prerequisite, no code)
- Send research prompt to multiple LLMs, collate.
- Write `docs/notes/benchmark_comparison.md` §Tool Inventory + §Macro/Feature Coverage Matrix.
- Decision: pick top-2 rivals for each track.

### Phase B — demacro baseline (1 session)
1. Commit `benchmark_corpus_demacro.json`.
2. Implement + test `snippets.py`.
3. Implement `adapters/texphage.py` + `run_benchmark.py` (texphage only).
4. Run on first 20 papers → initial decay table.

### Phase C — Rivals + comparison (1–2 sessions)
1. Implement adapters for top-2 demacro rivals.
2. Implement adapters for top-2 unfold rivals + `benchmark_corpus_unfold.json`.
3. Run empirical comparison on 20 papers per track.
4. Implement `benchmark_report.py`.

### Phase D — Full corpus + polish (1 session)
1. Run full 50-paper benchmark.
2. Merge Notes 5+6 in TODO.md.
3. Optional: `--snippet-mode` flag in `test_fidelity.py`.

---

## Acceptance Criterion

> `docs/notes/benchmark_comparison.md` exists with:
> (a) macro/feature coverage matrix for ≥5 demacro tools and ≥3 unfold tools,
> (b) empirical comparison table (compile%, exact%, near_exact%, acceptable%) for ≥3 tools on ≥20 papers,
> (c) decay curve table (demacro track) for ≥2 tools,
> (d) unfold success table stratified by number of source files.
>
> `python scripts/benchmark_report.py` regenerates (b)–(d) from `tests/benchmark/results.jsonl`.
>
> `python scripts/success_rate.py` still prints rolling whole-paper rate unchanged.

---

## Open Questions

1. **Unfold corpus filtering**: require ≥3 source files? At least one `\include`? Nesting depth ≥ 2? Which criterion best exercises the interesting cases?
2. **Pandoc**: include in source survey as a "lower bound" baseline (it converts rather than preserves), or exclude entirely?
3. **Tool installation complexity**: some rivals may have complex deps. Containerise (Docker) the benchmark runner, or just document per-tool install steps?
4. **Decay curve x-axis**: log10(actual_body_chars) — universal, works across all tools — vs. log2(num_structural_units) — more meaningful for texphage specifically. Which to use as the primary axis?
