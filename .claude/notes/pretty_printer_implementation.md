# Implement `texphage-format`: a LaTeX pretty-printer for canonical output

## Context

The texphage pipeline produces a "canonical 5-line" `.tex` file: a minimal
preamble followed by a fully macro-expanded body, all on a single line (except
`\par`-delimited paragraph breaks added by the BUG-12 fix). This is ideal for
machine consumption but unreadable for humans. We want a formatter that makes
the output inspectable without altering the compiled PDF.

### What the input looks like (post-pipeline)

```latex
\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\begin{document}
We prove that $f$ is continuous.\par Let $\epsilon > 0$. Then \begin{align*} \lim_{n \to \infty} a_n = L \end{align*} follows immediately.\par
\end{document}
```

The preamble is **already** one command per line (produced by
`build_minimal_preamble()`). Only the body needs formatting.

### Safety envelope

The formatter operates on **post-demacro** LaTeX: all user-defined macros are
already expanded. This means:
- No macro can "eat" the whitespace we add.
- The only unsafe whitespace is inside math mode (a newline without a trailing
  `%` introduces a spurious token-space in some positions).
- Verbatim environments have already been processed and are not present in the
  output (they were protected and then restored by `demacro.preprocessing()`).

**Invariant:** The formatter must never change the compiled PDF. Only add
whitespace (newlines, blank lines) in positions where LaTeX treats them as
equivalent to a space or nothing.

---

## Key design decision: wrap latexindent vs. pure Python

`latexindent.pl` is shipped with TeX Live, which is already a required system
dependency of texphage. It is actively maintained (v3.24, Aug 2025), documented
at https://latexindentpl.readthedocs.io/, and handles:
- Environment indentation
- Sentence-per-line (via `manipulateSentences: 1`)
- Math mode line breaks with automatic `%` insertion
- Delimiter alignment in `tabular`/`align`

The recommendation is a **two-tier strategy**:
1. **Primary:** call `latexindent.pl` via `subprocess` with a bundled YAML config.
2. **Fallback:** if `latexindent` is not on PATH (unlikely given TeX Live, but
   possible in minimal installs), use a pure-Python regex formatter that
   handles the most important cases.

This avoids re-implementing sentence boundary detection, math line-break
safety, and alignment logic that latexindent already handles correctly.

---

## Implementation plan

### Step 1: Bundle a latexindent YAML config

Create `src/texphage/data/latexindent_texphage.yaml` with these settings:

```yaml
# latexindent config for texphage canonical output
defaultIndent: "  "       # 2-space indent inside environments

modifyLineBreaks:
  oneSentencePerLine:
    manipulateSentences: 1
    removeSentenceLineBreaks: 1
    # Don't break on common LaTeX abbreviations
    sentencesEndWith:
      basicFullStop: 1
      # Exclude: i.e., e.g., Fig., Thm., Cor., Prop., Def., Lem., cf., vs.
      betterFullStop: 1
    sentencesFollow:
      blankLine: 1
      fullStop: 1
      other: "(?<![A-Z][a-z]{0,3})\\.\\s"  # negative lookbehind for abbrevs
  environments:
    # Put \begin{env} and \end{env} on their own lines, indent contents
    equation:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
      EndFinishesWithLineBreak: 1
    "equation*":
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
      EndFinishesWithLineBreak: 1
    align:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
      EndFinishesWithLineBreak: 1
    "align*":
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
      EndFinishesWithLineBreak: 1
    gather:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    "gather*":
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    itemize:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    enumerate:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    figure:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    table:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    theorem:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    lemma:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1
    proof:
      BeginStartsOnOwnLine: 1
      EndStartsOnOwnLine: 1

lookForAlignDelims:
  # Align ampersands in align/tabular environments
  align:
    delims: 1
    alignDoubleBackSlash: 1
  "align*":
    delims: 1
    alignDoubleBackSlash: 1
```

**Important:** Test this YAML against several arxiv papers from the test suite
before committing. latexindent's poly-switches interact in non-obvious ways;
the `oneSentencePerLine` + `modifyLineBreaks` combo especially needs empirical
validation. Use the latex playground to verify the PDF is unchanged.

### Step 2: Create `src/texphage/formatter.py`

```python
"""Pretty-printer for texphage canonical output.

Two-tier strategy:
  1. If latexindent is on PATH, call it with the bundled YAML config.
  2. Otherwise, use the pure-Python fallback (handles \par, environments,
     but NOT sentence-per-line).
"""
```

Public API:
```python
def pretty_print(
    tex: str,
    *,
    use_latexindent: bool = True,
    max_line_length: int | None = None,
    sentence_model: str | None = None,
) -> str:
    """Format a texphage canonical string for human readability.

    Args:
        tex:              The canonical .tex string from texphage().
        use_latexindent:  If True and latexindent is available, use it.
                          Set to False to force the Python fallback.
        max_line_length:  If given, wrap prose lines to at most this many
                          characters. Default None = unbounded. Passed to
                          latexindent as columns (textWrapOptions) or applied
                          as a post-pass in the Python fallback.
        sentence_model:   Optional Ollama/HuggingFace model identifier for
                          the LLM sentence-boundary second pass (e.g.
                          "qwen2.5:0.5b"). If None, only deterministic rules
                          are used. See "Sentence detection" section below.

    Returns:
        Formatted .tex string. PDF output is identical to the input.
    """
```

**latexindent path (primary):**
1. Check `shutil.which("latexindent")`.
2. Write `tex` to a temp file.
3. Run `latexindent -l <bundled_yaml> -m <tempfile>` (the `-m` flag enables
   `modifyLineBreaks`; without it, sentence-per-line is inactive).
4. Read stdout (latexindent writes formatted output to stdout by default with
   `-o` flag, or use `-o=-` to print to stdout).
5. On any `subprocess` error, fall through to the Python fallback.

**Python fallback (secondary):**
Steps, applied to the body only (preamble is already correct):

1. **`\par` → blank line paragraph:**
   Replace `\par` (standalone token, possibly preceded/followed by space) with
   `\n\n`. The BUG-12 fix already converts `\par ` → `\par\n`, so this is
   mostly a cleanup step.

2. **Environment isolation:**
   For a hardcoded list of block-level environments (`equation`, `align`,
   `gather`, `itemize`, `enumerate`, `figure`, `table`, `theorem`, `lemma`,
   `proof`, plus their `*` variants), insert `\n` before `\begin{env}` and
   after `\end{env}`. Use regex with `re.escape` and `\*?` for starred variants.

3. **`\item` isolation:**
   Insert `\n` before each `\item`. This makes list contents readable.

4. **Collapse multiple blank lines:**
   Replace `\n{3,}` with `\n\n` to avoid excessive vertical whitespace.

5. **`\label` and `\caption` placement:**
   These must stay on the same line as the thing they label — never add
   whitespace before `\label{...}` or `\caption{...}`. Specifically:
   - `\end{env}\n\label{...}` → keep together: `\end{env} \label{...}` on
     same line, or `\label` on the very next line with no blank line between.
   - After `\\` in math: `\\ \label{...}` stays together.
   - `\caption{...}\label{...}` stays together, no newline between them.
   The rule: `\label` and `\caption` are never separated from their anchor
   by a blank line. A single newline (no blank line) is acceptable.

6. **Sentence-per-line (deterministic pass):**
   Apply to all prose text runs — including inside theorem, lemma, definition,
   proof, and remark environments, not only top-level paragraphs. The
   deterministic pass uses these rules (applied in order within each prose run):

   a. Split candidate positions: after `. `, `? `, `! ` where the next
      non-space character is uppercase or `\`.
   b. **Suppress** the split if the `.` is preceded by any of:
      - A known abbreviation: `Fig`, `Thm`, `Lem`, `Cor`, `Prop`, `Def`,
        `Rem`, `Sec`, `Ch`, `App`, `cf`, `vs`, `i\.e`, `e\.g`, `et al`,
        `resp`, `wrt`, `iff`, `w\.r\.t`, `s\.t`.
      - A single uppercase letter (initials): `[A-Z]\.`
      - A digit (numbered item): `[0-9]\.`
      - A closing brace/bracket/paren that itself is part of a math/citation:
        `\}`, `\)`, `\]` — i.e. the sentence end is inside a math expression.
   c. **Do not split** inside math mode (`$...$`, `\(...\)`, `\[...\]`,
      or inside any math environment). Track math depth with a simple state
      machine, not regex.
   d. **Do not split** inside `\cite{...}`, `\ref{...}`, `\eqref{...}`.

   This deterministic pass handles the common cases. Math-heavy papers with
   unusual abbreviation patterns may still have false positives/negatives.

7. **Sentence-per-line (LLM second pass, optional):**
   If `sentence_model` is provided, run a second pass over each paragraph to
   verify and correct sentence boundaries. Recommended approach:

   a. Chunk the body into paragraphs (split on blank lines).
   b. For each paragraph, strip LaTeX markup to produce a plain-text version
      (replace `$...$` with `MATH`, `\cite{...}` with `CITE`, etc.).
   c. Send to the model with a simple prompt:
      ```
      Return the 0-indexed character positions of sentence endings in the
      following text. Output only a JSON array of integers, nothing else.
      Text: "<plain_text>"
      ```
   d. Map the returned positions back to the original LaTeX paragraph and
      insert line breaks at those positions.
   e. If the model call fails or returns invalid JSON, keep the deterministic
      result.

   **Recommended models (fast, small, local via Ollama):**
   - `qwen2.5:0.5b` — 500M params, runs in ~200ms/paragraph on CPU
   - `smollm2:135m` — 135M params, fastest option, good for simple sentence splitting
   - `llama3.2:1b` — 1B params, better on math-adjacent prose

   The model is purely advisory: it cannot introduce formatting errors because
   it only suggests *positions* for line breaks, which are then inserted by
   Python. If a suggested position is inside math mode or an argument, it is
   silently ignored.

   **Dependency:** Ollama must be running locally (`ollama serve`). The
   `sentence_model` parameter accepts either an Ollama model tag (e.g.
   `"qwen2.5:0.5b"`) or a HuggingFace pipeline path for offline use. Add
   `ollama` (Python client) as an optional dependency in `pyproject.toml`
   under `[project.optional-dependencies]` (e.g. `format = ["ollama>=0.3"]`).

8. **Collapse multiple blank lines:**
   Replace `\n{3,}` with `\n\n` to avoid excessive vertical whitespace.

### Step 3: Register CLI tool

In `pyproject.toml`, add:
```toml
[project.scripts]
texphage-format = "texphage.cli:main_format"
```

Create `main_format()` in `src/texphage/cli.py` using `argparse`:
- Positional `input` argument: path to `.tex` file (or `-` for stdin).
- `-o` / `--output`: path to write output (default: stdout).
- `--no-latexindent`: flag to force Python fallback.

### Step 4: Integrate into `pipeline.py`

Add `pretty_print: bool = False` and forwarding kwargs to `texphage()`:

```python
def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
    *,
    pretty_print: bool = False,
    max_line_length: int | None = None,
    sentence_model: str | None = None,
) -> tuple[str, list[Attachment]]:
    ...
    if pretty_print:
        from texphage.formatter import pretty_print as fmt
        canonical_tex = fmt(
            canonical_tex,
            max_line_length=max_line_length,
            sentence_model=sentence_model,
        )
    return canonical_tex, attachments
```

Also expose these in `texphage_to_dir()` with the same forwarding pattern.

---

## Testing plan

### Unit tests for Python fallback (no TeX required)

Test `formatter.py` with `use_latexindent=False`:
- `\par` → blank line conversion
- `\begin{align}...\end{align}` isolation
- `\item` isolation
- Multiple blank line collapse
- Preamble left untouched

### Integration tests (require latexindent)

Use `pytest.mark.skipif(shutil.which("latexindent") is None, reason=...)`:
- Round-trip: formatted output compiles to the same PDF as unformatted.
  Use `scripts/latex_playground.py` as the oracle.
- Sentence-per-line: a paragraph with 3 sentences produces 3 lines.
- Abbreviation safety: "Thm. 1 shows..." does not get a line break after "Thm."

### Regression: never change PDF

For every test case, compile both the unformatted and formatted `.tex` with
`latexmk`, compare PDFs with SSIM. Any SSIM < 0.999 on text content is a bug.

---

## Community guidelines summary (for reference during implementation)

Based on research into latexindent, tex-fmt, prettier-plugin-latex, and
academic LaTeX style guides:

1. **One sentence per line** (the "semantic linebreak" convention) is the
   standard in math/CS research communities for git-collaborative writing.
   Rationale: git diffs, merge conflicts, and editor line operations all work
   at sentence granularity. Use latexindent's `manipulateSentences`, not regex.

2. **`\begin{env}` / `\end{env}` on their own lines**, contents indented 2
   spaces. Universal consensus across all style guides.

3. **`\par` vs blank lines:** In document body, blank lines are idiomatic.
   `\par` inside macros is correct but macros are already expanded in texphage
   output, so convert `\par` to blank lines.

4. **Math environments:** Opening and closing delimiters on their own lines,
   contents indented. In multi-line math, line break before each `=` or `<`.
   Newlines inside math require trailing `%` in some positions — let
   latexindent handle this.

5. **Never `$$...$$`** (TeX primitive). texphage output should already use
   `\[...\]` or named environments, but if `$$` survives, do not reformat it
   — it is potentially load-bearing and conversion is out of scope for the
   formatter.

6. **Prettier philosophy note:** A Prettier-style formatter would reflow prose
   to fill `printWidth` columns and discard all existing line breaks. That is
   the wrong model for LaTeX: we want to *add* line breaks, not reflow. The
   sentence-per-line convention is the opposite of Prettier's paragraph-reflow.
   The Python fallback should not attempt any line-length-based reflowing.

---

## Resolved design decisions

1. **Scope of sentence-per-line:** Apply everywhere — top-level prose AND inside
   theorem/lemma/definition/proof/remark environments. Use the LLM second pass
   for difficult cases.

2. **Line length:** `max_line_length: int | None = None`. Default is unbounded.
   Sentence-per-line already breaks most lines naturally; wrapping is a separate
   optional concern.

3. **`\label`/`\caption` placement:** Never add whitespace before these. They stay
   immediately after their anchor (same line, or next line with no blank line in
   between).

4. **LLM sentence detection:** Use a tiny local model (Ollama, e.g. `qwen2.5:0.5b`)
   as an optional second pass after deterministic rules. The model only suggests
   character positions for line breaks; it cannot corrupt LaTeX.

5. **`\item` indentation:** Yes, indent item content 2 spaces relative to `\item`.

## Open questions (resolve before implementing)

1. **Idempotency of LLM pass:** The deterministic path must be idempotent.
   The LLM pass is stochastic — decide whether to seed it (for determinism)
   or accept that a second call may differ. Recommendation: document that
   `sentence_model` is non-deterministic and idempotency is only guaranteed
   without it.

2. **latexindent + LLM interaction:** If latexindent is the primary path,
   should the LLM second pass run on top of latexindent's output, or only on
   the Python fallback output? Recommendation: always run LLM pass last,
   since latexindent's abbreviation list may miss domain-specific math terms.

3. **Math-mode depth across `\par` boundaries:** The state machine tracking
   math depth (for step 6c above) must reset at each paragraph boundary.
   An unclosed `$` in one paragraph cannot bleed into the next (TeX would
   error). Verify and add a test for this edge case.

4. **CLI `--sentence-model` UX:** Error clearly if `sentence_model` is given
   but Ollama is not reachable. Do not auto-start Ollama.
