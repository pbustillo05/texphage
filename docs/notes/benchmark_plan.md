# Benchmarking Pipeline — Implementation Specification

> **Status:** Design finalized — ready for implementation.

## Context

TODO.md carries two related items:
- **Note 5** (priority 4/5, accepted) — Per-run success rate tracking. *Status: substantially done.* `results.jsonl` is being written, `success_rate.py` exists.
- **Note 6** (priority 1/5, proposed) — Benchmark demacro against competing tools.

Merge these into one coherent benchmarking system with three purposes:
1. **Tool survey** — Know exactly what macro types / file-resolution patterns each competing tool handles.
2. **Continuous rolling metrics** — See our own success rate evolve over time (already mostly done).
3. **Published benchmark** — A reproducible comparison against the field.

**Important framing**: `demacro` and `unfold` require separate benchmark designs because they do fundamentally different things and have different competitor sets.

---

## Design Decisions (all resolved)

| Question | Decision |
|---|---|
| Chunk strategy (demacro) | **Mixed**: char-count tier targets `[200, 500, 1k, 2k, 5k, 10k, 20k, 50k, ∞]`, snapped forward to nearest structural unit boundary. |
| Tool inclusion | **All discovered tools**; if installation fails, record as `NOT_RUNNABLE` with reason — never silently exclude. |
| Primary fidelity metric | **Multi-tier**: compile%, near_exact%, acceptable%. See metric definitions below. |
| Primary completeness metric | **macro completeness** for demacro; **file completeness** for unfold. Report both. |
| Statistical rigor | Wilson score 95% CI on every percentage; intent-to-treat (baseline failures stay in denominator). |
| Unfold corpus filter | ≥3 source `.tex` files; nesting depth ≥2; annotate include-command families. |
| Report modes | Three separate outputs: engineering report, comparison report, coverage report. |
| Pandoc | Include as "upper-bound reference" labeled as a converter, not a tex→tex tool. |
| Decay curve x-axis | `log10(actual_body_chars)` primary; `num_structural_units` as annotation. |
| Environment | Record fingerprints in every result record; no mandatory Docker (optional). |

---

## Critical Design Constraint: The Identity Transform Problem

**A tool that leaves macros unexpanded scores perfect fidelity.** If a rival outputs its input unchanged, the compiled PDF is identical to baseline (macros are defined and used identically). It gets compile%=100, near_exact%=100 — but did nothing useful.

**Fix:** Add a **completeness** metric alongside fidelity:
- **demacro completeness** = `macros_expanded / macros_defined_in_preamble` (float 0–1)
- **unfold completeness** = `files_inlined / files_referenced` (float 0–1)

A no-op tool gets completeness = 0. Report both completeness and fidelity; never publish fidelity alone as the headline.

---

## Two Separate Benchmark Tracks

### Track 1 — `demacro` benchmark (size-stratified)

Demacro's success is strongly size-dependent. The decay curve reveals where the tool breaks down.

**Core idea**: for each paper, extract snippets at increasing body sizes (keeping whole preamble). Plot fidelity and completeness vs. `log10(body_chars)`. The tool whose curves stay high longest wins.

**Baseline**: compile the original snippet (macros present). Skip tier only if baseline fails — but record the failure in the denominator (intent-to-treat).

**Success**: snippet compiled AND near-exactly matches baseline AND completeness > 0.

### Track 2 — `unfold` benchmark (structure-stratified)

Unfold merges multi-file projects into one flat `.tex`. Success is binary per-project; the interesting variation is across project structures.

**Baseline**: compile the original multi-file project.

**Success**: `unfold(project)` produces a `.tex` that compiles to a near-identical PDF AND all referenced files were inlined (completeness = 1).

**Corpus stratification** (see Corpus section): by nesting depth, number of files, and include-command family.

---

## Tool Survey

See **`docs/notes/tool_survey.md`** for the full survey.

**Key findings:**

- **Demacro track rivals**: `de-macro` (CTAN), `expand-latex-macros` (PyPI), `flachtex` (macro substitution mode). Pandoc as upper-bound reference.
- **Unfold track rivals**: `latexpand` (Perl, CTAN gold standard), `flachtex` (Python, best modern alternative).
- **Key differentiator (unfold)**: texphage handles `\import`/`\subimport`/`\inputfrom`; most rivals do not.
- **Key differentiator (demacro)**: texphage handles `\def`, `\let`, `\newenvironment`, counters, starred variants; `de-macro` handles only `\newcommand`/`\newenvironment`.

**Tool survey verification**: before running the benchmark, run the qualification micro-suite (Component G below) on every discovered tool to replace documentation claims with observed behavior.

---

## What Already Exists (do not rebuild)

- `scripts/test_fidelity.py` — full per-paper fidelity harness with SSIM, text diff, severity.
- `tests/runs/results.jsonl` — append-only log, one JSON object per paper.
- `scripts/success_rate.py` — rolling success rate computer.
- `_compare()` in `test_fidelity.py` — severity classifier + SSIM + text diff. **Reuse for snippet comparisons.**
- `scripts/arxiv_categories.json` — full arXiv category list for uniform sampling.

---

## Components to Build

### A. Snippet Extractor — demacro track only (`scripts/benchmark/snippets.py`)

**Purpose**: Given `(preamble: str, body: str)`, produce progressively larger body slices snapped to structural boundaries.

**Tier targets** (body chars): `[200, 500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000, math.inf]`  
`math.inf` = full body (always included).

**Structural unit parsing** (using patterns from `_regex.py`):
1. Split body into units by scanning for these boundaries:
   - Paragraph: blank-line / `\par` (finest)
   - Environment: `\begin{...}...\end{...}` block
   - Subsection: `\subsection` / `\subsubsection` marker
   - Section: `\section` marker (coarsest)
2. For each tier T: walk units accumulating chars; when cumulative ≥ T, snap to end of current unit.
3. Skip tiers where body is shorter than T (no truncation needed → merge into full-body tier).
4. Deduplicate tiers that collapse to the same actual content after snapping.

**Output type**:
```python
@dataclass
class SnippetSlice:
    tier_target_chars: int   # tier requested (or math.inf)
    actual_chars: int        # chars after boundary snap
    num_units: int
    body_content: str
    is_full_body: bool       # True when tier_target >= actual body length
```

**Determinism requirement**: the extractor must be deterministic — same input always produces same slices. Write a test that asserts this.

**Key rule**: `import regex as re` — no stdlib re. New patterns go through the `regex-writing` skill protocol.

**Snapping direction**: always forward (include more rather than less). Document this as "context-enriched snippets" — tools with broader lookahead may benefit, and this is intentional (real-world users always have full preamble context).

---

### B. Benchmark Corpus (`docs/notes/benchmark_corpus_demacro.json`, `benchmark_corpus_unfold.json`)

**Fixed, committed corpus** for each track with exact arXiv IDs and archive SHA256 hashes.

**Demacro corpus — 50 papers**:
- Sampling: uniform arXiv category sampling, seed=2026, ≤2 per category.
- Filter: paper must define ≥1 user macro (`\newcommand`, `\def`, `\let`, or `\newenvironment`) to exclude trivially macro-free papers.
- Annotate each paper with `macro_stats` (see schema below).

**Unfold corpus — 50 papers**:
- Filter: ≥3 source `.tex` files in tarball AND nesting depth ≥2.
- Annotate each paper with `include_families` (see schema below).
- Ensure ≥15 papers use `\import`/`\subimport` (the key differentiator).

**Corpus JSON schema** (one object per paper):
```json
{
  "paper_id": "2501.12345",
  "track": "demacro",
  "source_url": "https://arxiv.org/abs/2501.12345",
  "archive_sha256": "abc123...",
  "category": "math.AG",
  "year": 2025,
  "seed": 2026,
  "selection_rule": "uniform_category_stratified",
  "macro_stats": {
    "user_macro_count": 17,
    "newcommand_count": 14,
    "def_count": 2,
    "let_count": 1,
    "newenvironment_count": 3,
    "optional_arg_macros": 5,
    "starred_forms": 2
  },
  "include_families": ["\\input", "\\import"],
  "num_source_files": 4,
  "max_nesting_depth": 2
}
```

`scripts/benchmark/corpus.py` exposes `load_corpus()`, `download_corpus()`, `generate_corpus()`. `generate_corpus()` must log every download and rejection with reason.

---

### C. Tool Adapter Interface (`scripts/benchmark/adapters/`)

```python
@dataclass
class TransformResult:
    output: str | None          # None on failure
    status: ToolStatus          # see enum below
    failure_code: FailureCode   # see enum below
    runtime_sec: float
    exit_code: int | None
    stderr: str

class ToolStatus(str, Enum):
    SUCCESS = "success"
    NOT_RUNNABLE = "not_runnable"    # install failed
    TIMEOUT = "timeout"              # exceeded timeout_sec
    CRASH = "crash"                  # uncaught exception / signal
    UNSUPPORTED = "unsupported"      # tool reported unsupported feature
    INVALID_OUTPUT = "invalid_output"  # output fails basic LaTeX parse

class ToolAdapter(Protocol):
    name: str
    version: str                     # detected at runtime
    def transform(self, tex: str, timeout_sec: float = 30.0) -> TransformResult: ...
```

- `adapters/texphage.py` — wraps `texphage()` (demacro reference)
- `adapters/texphage_unfold.py` — wraps `unfold()` (unfold reference)
- One adapter per rival tool discovered in survey.

**Adapter contract**: input is a complete `.tex` document string (preamble + body); output is `TransformResult`. Never let the benchmark runner crash on a tool failure — all failures must produce a structured result.

---

### D. Failure Taxonomy

Every result record carries exactly one `failure_code` from this enum:

```
none                      — full success
not_runnable              — tool could not be installed
timeout                   — exceeded 30s wall-clock limit
crash                     — uncaught exception or signal
unsupported_feature       — tool explicitly reported unsupported feature
invalid_output_tex        — output failed basic LaTeX structural check
baseline_compile_fail     — original snippet did not compile (tier skipped, counted in denominator)
transformed_compile_fail  — tool output did not compile
pdf_page_count_mismatch   — page counts differ (SSIM not computed)
fidelity_fail             — compiled but SSIM or text-diff threshold not met
completeness_zero         — tool performed no expansion/inlining (identity transform)
```

The last two are separate from compile failures. A no-op tool gets `completeness_zero`.

---

### E. Completeness Counter (`scripts/benchmark/completeness.py`)

**Purpose**: measure how much actual transformation a tool performed.

**Demacro completeness**:
1. Count macros defined in the preamble of the input snippet: `macros_defined = count(\newcommand + \def + \let + \newenvironment)`.
2. Count the same patterns remaining in the tool's output preamble: `macros_remaining`.
3. `completeness = (macros_defined - macros_remaining) / macros_defined` (clamp to [0, 1]).
4. A tool that expands nothing: completeness = 0.
5. A tool that expands some but not all: completeness ∈ (0, 1) — record as `PARTIAL`.

**Unfold completeness**:
1. Count `\input`, `\include`, `\subfile`, `\import`, `\subimport` references in original source: `files_referenced`.
2. Count how many are absent from the flat output (inlined): `files_inlined`.
3. `completeness = files_inlined / files_referenced`.

Must use `import regex as re` — new patterns go through `regex-writing` skill protocol.

---

### F. Benchmark Runner (`scripts/benchmark/run_benchmark.py`)

```
python scripts/benchmark/run_benchmark.py \
    --track demacro|unfold \
    --tools texphage de_macro flachtex ... \
    --corpus docs/notes/benchmark_corpus_demacro.json \
    --n 20 \
    --out tests/benchmark/ \
    --timeout 30 \
    --resume
```

**demacro inner loop** (per tool × paper × tier):
1. Extract all snippet tiers for this paper.
2. For each tier:
   a. Compile baseline snippet. If it fails → record `failure_code: baseline_compile_fail`, count in denominator, skip comparison.
   b. Count `macros_defined` in baseline preamble.
   c. Run `tool.transform(snippet)` with timeout.
   d. Compile transformed output.
   e. Compute `text_diff_lines` (pdftotext), SSIM if page counts match (CLAUDE.md rule).
   f. Count `macros_remaining` in tool output preamble → `completeness`.
   g. Classify using metric definitions below.
   h. Append full record to `tests/benchmark/results.jsonl`.

**unfold inner loop** (per tool × paper):
1. Count source files; if < 3, skip (but this should be filtered at corpus generation time).
2. Compile original multi-file project as baseline.
3. Run `tool.transform(project_dir)` → single `.tex`.
4. Compile output, compare, compute completeness.
5. Extra fields: `num_source_files`, `max_nesting_depth`, `include_families`.

**Parallelism**: papers in parallel (reuse locking protocol from `test_fidelity.py`). Tools run sequentially on same paper to share baseline PDF.

**Token efficiency**: only compute SSIM when both PDFs exist AND page count matches (CLAUDE.md rule). Log `pdf_page_count_mismatch` when page counts differ.

**Environment fingerprint**: capture once per run and embed in every result record:
```python
env = {
    "texphage_git_commit": get_git_commit(),
    "texlive_version": get_texlive_version(),    # `tex --version`
    "poppler_version": get_poppler_version(),    # `pdfinfo --version`
    "python_version": sys.version,
    "os": platform.platform(),
    "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    "benchmark_commit": get_git_commit(),        # same field if no separate submodule
}
```

---

### G. Qualification Micro-Suite (`scripts/benchmark/qualify.py`)

**Purpose**: replace documentation claims in `tool_survey.md` with observed behavior. Run this before the main benchmark to produce an empirical capability matrix.

**Synthetic test fixtures** (one `.tex` per macro family):
```
tests/benchmark/fixtures/
├── newcommand_simple.tex          # \newcommand{\foo}{bar}
├── newcommand_optional_arg.tex    # \newcommand{\foo}[1][default]{...#1...}
├── def_simple.tex                 # \def\foo{bar}
├── let_alias.tex                  # \let\oldfoo\foo
├── newenvironment.tex             # \newenvironment{myenv}{...}{...}
├── starred_form.tex               # \newcommand*{\foo}{bar}
├── nested_macro.tex               # \newcommand{\a}{\newcommand{\b}{...}}
├── input_basic.tex                # \input{file}
├── include_basic.tex              # \include{file}
├── import_subimport.tex           # \import{dir/}{file}
└── subfile.tex                    # \subfile{child}
```

For each tool × fixture:
1. Run the tool.
2. Check: does the output compile? Does the relevant macro/include command disappear from output?
3. Record `PASS` / `FAIL` / `NOT_APPLICABLE` / `NOT_RUNNABLE`.

Output: `docs/notes/benchmark_capabilities.md` — one row per tool, one column per fixture. This is the feature coverage matrix (replaces LLM-synthesized claims).

---

### H. Benchmark Report Generator (`scripts/benchmark_report.py`)

Reads `tests/benchmark/results.jsonl`, writes three separate reports.

**`benchmark_report_engineering.md`** — for internal use:
- Regression table: per-tool fidelity vs previous run
- Failure breakdown by error code
- Runtime statistics (median, p90 per tool)

**`benchmark_report_comparison.md`** — for external claims:
- **Table 1** — Per-tool summary: compile%, near_exact%, acceptable%, completeness (mean), with Wilson 95% CI on all percentages
- **Table 2** — Demacro decay curve: per tool × tier (actual_chars median) × near_exact% and completeness
- **Table 3** — Unfold success by project structure (file count bucket, nesting depth bucket, include family)
- **Table 4** — Failure breakdown: per tool × failure_code (count, %)
- **Note**: "n=50 papers; intended for internal engineering use; not statistically powered for publication claims."

**`benchmark_report_capabilities.md`** — generated from qualification micro-suite:
- Feature coverage matrix: tool × fixture → PASS/FAIL/NOT_RUNNABLE
- Replaces the LLM-synthesized tool_survey capability claims

---

### I. `results.jsonl` Schema Extension (backward compatible)

```json
{
  "...existing rolling-test fields...",

  "snippet_tier_chars": null,
  "actual_body_chars": null,
  "benchmark_tool": null,
  "benchmark_track": null,
  "benchmark_version": null,

  "failure_code": null,
  "macros_defined": null,
  "macros_remaining": null,
  "completeness": null,
  "runtime_sec": null,

  "env": {
    "texphage_git_commit": null,
    "texlive_version": null,
    "poppler_version": null,
    "python_version": null,
    "os": null,
    "timestamp_utc": null
  },

  "paper_arxiv_id": null,
  "paper_archive_sha256": null,
  "corpus_version": null,
  "corpus_seed": null
}
```

`success_rate.py` filters to `benchmark_tool == null` — existing behavior unchanged.

---

## File Layout

```
docs/notes/
├── benchmark_plan.md                     ← this file
├── benchmark_comparison.md               ← committed; auto-generated comparison report
├── benchmark_capabilities.md             ← committed; auto-generated from micro-suite
├── benchmark_corpus_demacro.json         ← committed; fixed 50-paper corpus
├── benchmark_corpus_unfold.json          ← committed; fixed 50 multi-file papers

scripts/
├── benchmark/
│   ├── __init__.py
│   ├── corpus.py
│   ├── snippets.py                       ← size-stratified extractor (demacro only)
│   ├── completeness.py                   ← macro/file completeness counter
│   ├── qualify.py                        ← qualification micro-suite runner
│   ├── run_benchmark.py                  ← CLI; --track demacro|unfold
│   └── adapters/
│       ├── __init__.py
│       ├── base.py                       ← ToolAdapter protocol + ToolStatus + FailureCode
│       ├── texphage.py
│       ├── texphage_unfold.py
│       ├── de_macro.py
│       ├── expand_latex_macros.py
│       ├── flachtex.py
│       ├── latexpand.py
│       └── pandoc.py                     ← upper-bound reference only; labeled as converter
├── benchmark_report.py
└── success_rate.py                       ← existing, unchanged

tests/
├── benchmark/
│   ├── results.jsonl                     ← gitignored
│   ├── fixtures/                         ← qualification micro-suite .tex files
│   └── .gitkeep
```

---

## Metric Definitions

```
compile%       = runs where transformed output compiled / total runs (incl. baseline_compile_fail)
near_exact%    = runs where: compile AND text_diff_lines ≤ 1 AND SSIM ≥ 0.99 / total runs
acceptable%    = runs where: compile AND severity == OK (existing _compare() definition) / total runs
exact%         = runs where: compile AND text_diff_lines == 0 AND SSIM ≥ 0.9999 / total runs
completeness   = mean(macros_expanded / macros_defined) across all runs with macros_defined > 0
```

**Intent-to-treat**: `total runs` includes tiers where baseline failed. A tier where baseline fails contributes 0 to all success metrics.

**Wilson CI**: compute 95% confidence interval for all percentage metrics using Wilson score interval. Report as `XX.X% [YY.Y, ZZ.Z]`.

**Never publish fidelity alone.** Always report completeness alongside fidelity. A tool with near_exact%=100 and completeness=0 is a no-op.

---

## Implementation Phases

### Phase A — Qualification micro-suite (prerequisite, no main-benchmark code)

1. Write 11 fixture `.tex` files in `tests/benchmark/fixtures/`.
2. Implement `qualify.py` — runs each adapter on each fixture, records PASS/FAIL/NOT_RUNNABLE.
3. Run qualification on all adapters.
4. Write `docs/notes/benchmark_capabilities.md` from results — this replaces the disputed LLM survey claims with observed facts.
5. Decision: confirm or revise the rival list based on what actually runs.

### Phase B — demacro baseline (1 session)

1. Commit `benchmark_corpus_demacro.json` (50 papers with macro_stats annotations).
2. Implement + test `snippets.py`.
3. Implement `completeness.py` (demacro side).
4. Implement `adapters/base.py` + `adapters/texphage.py`.
5. Implement `run_benchmark.py` (texphage only, demacro track).
6. Run on first 20 papers → initial decay table with completeness.

### Phase C — Rivals + comparison (1–2 sessions)

1. Implement adapters for all runnable demacro rivals.
2. Implement `adapters/texphage_unfold.py` + `adapters/latexpand.py` + `adapters/flachtex.py`.
3. Commit `benchmark_corpus_unfold.json` (50 papers with include_families annotations).
4. Implement `completeness.py` (unfold side).
5. Run empirical comparison on 20 papers per track.
6. Implement `benchmark_report.py` with all three report modes.

### Phase D — Full corpus + polish (1 session)

1. Run full 50-paper benchmark for both tracks.
2. Merge Notes 5+6 in TODO.md.
3. Update `docs/notes/tool_survey.md` to mark LLM-inferred claims as confirmed/refuted based on qualification micro-suite.

---

## Acceptance Criterion

> **`benchmark_capabilities.md`** exists with observed PASS/FAIL for each tool × fixture combination (not LLM-inferred).
>
> **`benchmark_comparison.md`** exists with:
> (a) empirical comparison table (compile%, near_exact%, acceptable%, completeness with Wilson CI) for ≥3 tools on ≥20 papers,
> (b) decay curve table (demacro track) for ≥2 tools,
> (c) unfold success table stratified by nesting depth and include-command family.
>
> **`python scripts/benchmark_report.py`** regenerates (a)–(c) from `tests/benchmark/results.jsonl`.
>
> **`python scripts/success_rate.py`** still prints rolling whole-paper rate unchanged.
>
> **Every result record** includes: `failure_code`, `completeness`, `env` fingerprint, `paper_archive_sha256`.
>
> **No tool is silently excluded** — all discovered tools appear in results with a `failure_code` (even if `not_runnable`).
