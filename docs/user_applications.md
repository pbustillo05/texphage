# texphage — Applications and Use Cases

texphage is a **LaTeX rearrangement toolbox**: a collection of tools that
restructure LaTeX source with no (or minimal, documented) impact on the
compiled PDF. All tools share the same regex engine, the same preprocessing
pipeline, and the same testing infrastructure.

This file tracks every concrete application we've identified, its
implementation status, and where the relevant code or plan lives.

---

## Status legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and tested |
| 🔧 | Partially implemented (code exists, gaps noted) |
| 📋 | Designed / planned (note or spec exists, no code yet) |
| 💡 | Idea only (no design yet) |

---

## NLP / machine learning uses

### 1. Demacro for batch corpus compilation ✅

**Goal:** Given an arXiv tarball, produce a compilable 5-line `.tex` snippet
with a minimal preamble so that a large corpus of snippets can all be compiled
with the same minimal LaTeX installation.

**Why it matters:** Custom macros are the main obstacle to batch-compiling
arXiv snippets. Once expanded, snippets are self-contained and shareable
without sending the full preamble.

**Implemented in:** `src/texphage/pipeline.py` (`texphage()`,
`texphage_to_dir()`), `src/texphage/demacro.py`, `src/texphage/unfold.py`.

**Known gaps:** See `BUGS.md` (open regressions) and `README.md` §Known
limitations.

---

### 2. Training data for TikZ diagram generation 💡

**Goal:** Build a dataset of `(drawing image, tikz source)` pairs for
training or fine-tuning a vision-language model that generates TikZ diagrams
from sketches or images.

**Why it matters:** TikZ source in arXiv papers is buried inside macros.
After demacro, every TikZ environment is self-contained and can be compiled
with just `\usepackage{tikz}`.

**Needed on top of existing pipeline:**
- Extract only TikZ environments from the demacro'd body.
- Compile each environment to a standalone image (using the `standalone`
  document class).
- Filter for quality (no overfull boxes, SSIM ≥ threshold vs. original).

**No code yet.** Would naturally live in `scripts/extract_tikz_corpus.py`.

---

### 3. Training data for mathematical definition/theorem writing 💡

**Goal:** Extract a corpus of `(theorem/definition/lemma, proof)` pairs,
properly demacro'd, for language model training on mathematical writing style.

**Why it matters:** Math environments often use custom macros
(`\R`, `\norm`, `\inner`, etc.) that must be expanded before the text is
meaningful to a model.

**Needed on top of existing pipeline:**
- Segment the demacro'd body by theorem/lemma/proof environments.
- Associate each theorem with its proof (based on ordering and `\label`/`\ref`
  linkage).

**No code yet.** Regex patterns for environment extraction already exist in
`_regex.py` as a by-product of the `build_minimal_preamble` work; the
segmentation logic is new.

---

### 4. Structural analysis of mathematical documents 💡

**Goal:** Extract document structure (sections, theorems, proofs, figures,
tables, citations) from arXiv papers in a machine-readable form.

**Why it matters:** Structural metadata enables downstream tasks like
citation graph analysis, theorem dependency mapping, or section-level
embedding.

**Needed:** A structured extractor that consumes the demacro'd body and
returns a tree or JSON. No code yet.

---

## Human-facing tools

### 5. Unfold multi-file project into a single `.tex` ✅

**Goal:** Resolve all `\input`, `\include`, `\inputfrom`, etc. into a single
flat `.tex` file, with a record of which original file each line came from.

**Why it matters:** Many arXiv submissions are multi-file projects. Humans
editing or reviewing someone else's code benefit from seeing everything in
one place.

**Implemented in:** `src/texphage/unfold.py`.

**Known gaps:** `\subimport`, some exotic `\include` variants. See `TODO.md`.

---

### 6. LaTeX pretty-printer (`texphage-format`) 📋

**Goal:** Reformat a demacro'd document into idiomatic, human-readable LaTeX:
one sentence per line, environments on their own lines, consistent 2-space
indentation.

**Why it matters:** The pipeline output is a machine-optimised single line.
For human inspection (reviewing demacro output, editing, or diffing), it
needs to be formatted.

**Design:** `src/texphage/formatter.py`, wrapping `latexindent.pl` as primary
with a pure-Python regex fallback. Full spec in
`docs/notes/pretty_printer_implementation.md`.

**No code yet.** Ready to implement.

---

### 7. Translate `\xymatrix` diagrams to tikzcd 🔧

**Goal:** Replace legacy XY-pic commutative diagrams with tikzcd equivalents,
removing the `xy` package dependency.

**Why it matters:** `xy.sty` is old and poorly maintained; tikzcd is the
modern standard. Many arXiv papers from the 2000s–2010s use `\xymatrix` that
authors want to modernise.

**Partially implemented in:** `scripts/xy_to_tikz.py` (standalone, never
integrated). Has known bugs: wrong `import re`, five `match.grouo` typos,
module-level `print`, silent fallback on unknown operators.

**Full implementation plan:** `docs/notes/xy_to_tikz_implementation.md`.

---

### 8. VSCode extension: inline macro expansion 💡

**Goal:** When a user hovers over or clicks a macro call (e.g. `\mylemma`),
show the fully expanded definition in a tooltip or side panel. Optionally,
allow jumping to the definition site.

**Why it matters:** Reading someone else's LaTeX is hard when macros are
opaque. This makes texphage's expansion capability interactive.

**Needed:**
- A language server protocol (LSP) server that wraps `demacro.py` and
  `unfold.py` to answer "what does this macro expand to at this position?"
- A VSCode extension that sends hover/definition requests to the LSP.
- A live-update mode so the expanded definition reflects the current preamble
  state, not a stale snapshot.

**No code yet.** This is the most architecturally novel application; it
requires real-time incremental expansion rather than the current batch model.

---

### 9. Obsolete LaTeX modernisation (general) 💡

**Goal:** A general framework for translating deprecated LaTeX constructs to
modern equivalents. The `xy` → tikzcd converter (§7) is the first instance;
other candidates include:

- `\psfig{...}` → `\includegraphics{...}` (deprecated since 1994)
- `\epsfig{...}` → `\includegraphics{...}`
- `eqnarray` → `align` (inferior spacing, universally discouraged)
- `\over`, `\atop` (TeX primitives) → `\frac`, `\binom`
- `\rm`, `\bf`, `\it` (2-letter font commands) → `\textrm`, `\textbf`,
  `\textit`

Each translator is a pure string→string function with: known-supported
constructs, documented limitations, an evaluation script, and a feature flag
in `texphage()`.

**No general framework yet.** The xy→tikzcd converter is the prototype.

---

## Cross-cutting notes

All of the above share:

1. **The same regex engine** (`src/texphage/_regex.py`) — patterns are written
   once and reused across demacro, formatter, converters, and extractors.
2. **The same preprocessing contract** — whitespace collapse, verbatim
   protection, `\par` preservation (see `CLAUDE.md` §Preprocessing contract).
3. **The same testing infrastructure** — `scripts/latex_playground.py` as the
   oracle; pytest + ruff + mypy as the gate.
4. **The same fidelity guarantee** — every transformation must either preserve
   the PDF exactly (verified by SSIM) or document precisely what changes and
   why.

This shared foundation is why all these tools belong in the same package
rather than separate projects.
