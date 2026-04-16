# `texphage-format`: LaTeX pretty-printer

## Context (updated 2026-04-14)

`texphage-format` is the **human-facing counterpart to the demacro pipeline**.
It is one of the core tools in the texphage toolbox (see `docs/user_applications.md`
§6 and `toolbox_refactor_plan.md`).

The demacro pipeline produces a "canonical 5-line" `.tex` file: a minimal
preamble followed by a fully macro-expanded body, all on a single line. This is
ideal for machine consumption, but unreadable for humans. The formatter makes the
output inspectable and editable without altering the compiled PDF.

**Two independent uses:**
1. **Post-pipeline:** format the output of `texphage()` for human review or
   editing. The input has already been demacro'd — no custom macros remain.
2. **Standalone:** format any `.tex` file that a human wants to clean up,
   even without running the full pipeline first.

---

## Design decisions (final)

| Question | Decision |
|----------|----------|
| Default prose behavior | **Paragraph-per-line**: prose stays as one line per paragraph; only structure is isolated |
| External dependencies | **None** — pure Python only (no latexindent.pl) |
| Config file | **None** — CLI flags only |
| LLM sentence detection | **Cut** — formatters must be deterministic |
| `--semantic-linebreaks` | Available as opt-in flag; deterministic rule-based abbreviation detection |

---

## What the formatter does

### Default behaviour (no flags)

Input (post-pipeline body — all on one long line):

```
We prove that $f$ is continuous.\par Let $\epsilon > 0$. Then \begin{align*} \lim_{n \to \infty} a_n = L \end{align*} follows immediately.\par The next result shows...
```

Output:

```latex
We prove that $f$ is continuous.

Let $\epsilon > 0$. Then
\begin{align*}
  \lim_{n \to \infty} a_n = L
\end{align*} follows immediately.

The next result shows...
```

Rules applied in order:
1. `\par` → `\n\n` (blank line)
2. Block `\begin{X}` on its own line (preceded by `\n` if needed, followed by `\n`)
3. Block `\end{X}` on its own line (preceded by `\n`; prose after it stays on same line)
4. `\[` on its own line (preceded and followed by `\n`)
5. `\]` on its own line (preceded by `\n`)
6. Adjacent env boundaries merged: `\begin{A}\n\begin{B}` → `\begin{A}\begin{B}` (and same for closes, `\[`/`\]`)
7. `\item` on its own line
8. `\label`/`\caption`: remove any newlines inserted before them (they stay on same line as their anchor)
9. Depth-based indentation: each block environment indents contents by one level
10. Collapse 3+ consecutive blank lines → 2

**Core invariant:** The formatter never changes the compiled PDF. Every
whitespace insertion is LaTeX-safe (single newlines between tokens; never inside
math braces or argument groups).

### Adjacent / nested environment rule

When environments directly wrap one another, no newline separates their boundaries:

```latex
% Input:  \[ \begin{tikzcd} A \ar[r] & B \end{tikzcd} \]
% Output:
\[\begin{tikzcd}
  A \ar[r] & B
\end{tikzcd}\]
```

- `\begin{A}` immediately followed by `\begin{B}` → same line
- `\end{A}` immediately followed by `\end{B}` → same line
- `\[` immediately followed by `\begin{X}` → same line
- `\end{X}` immediately followed by `\]` → same line

Adjacent merging is applied iteratively until stable (handles triple nesting).

For indentation purposes, a "pure env" line (containing only env markers) counts
as one nesting level regardless of how many adjacent begins/ends it contains.

### `\label` rule

`\label{...}` is **never** placed on its own line. It stays on the same line as
its anchor. The isolation pass may insert a `\n` before `\label`; a subsequent
pass removes those newlines.

```latex
\begin{align*}
  f(x) = x^2
\end{align*}\label{eq:main}    % correct — no newline before \label
```

### Inline environments (not isolated)

`minipage`, `mbox`, `makebox`, `fbox`, `parbox`, `math`, `displaymath` are
treated as inline and are NOT placed on their own lines.

---

## `--semantic-linebreaks` (opt-in)

Adds a deterministic sentence-splitting pass over prose runs. Not applied by
default.

Split triggers: after `. `, `? `, `! ` where the next character is uppercase or `\`.

Suppressed if `.` is preceded by:
- A known abbreviation: `Fig`, `Thm`, `Lem`, `Cor`, `Prop`, `Def`, `Rem`, `Sec`,
  `Ch`, `App`, `cf`, `vs`, `resp`, `wrt`, `iff`, `i.e`, `e.g`, `et al`, `a.s`,
  `w.p`, `s.t`, `w.r.t`
- A single uppercase letter (initials)
- A digit

Math regions (`$...$`, `\(...\)`) and `\cite{}`/`\ref{}`/`\eqref{}` are protected
before splitting (replaced with placeholders, restored after).

The deterministic pass handles common cases. Unusual abbreviation patterns or
math-heavy papers may still have edge cases.

---

## Safety envelope

In **post-demacro mode** (formatting `texphage()` output):
- All user-defined macros are already expanded.
- Verbatim environments are not present (they were processed by `demacro.preprocessing()`).
- The only whitespace that could alter output is inside math mode — the formatter
  never inserts newlines inside `$...$` or `\[...\]` content.

In **standalone mode** (formatting arbitrary `.tex`):
- Macros are still present. The formatter treats all `\begin{}` / `\end{}` boundaries
  uniformly — it never adds whitespace inside `{...}` or `[...]` argument groups.
- Verbatim environments are NOT currently protected. If the input contains
  `\begin{verbatim}...\end{verbatim}`, the verbatim content may be reformatted.
  **Known limitation [inferred]:** Use standalone mode only on verbatim-free files
  until verbatim protection is added.

---

## Implementation

**File:** `src/texphage/formatter.py`

**Public API:**

```python
def pretty_print(
    tex: str,
    *,
    semantic_linebreaks: bool = False,
    indent: str = "  ",
) -> str:
    """Format a .tex string for human readability.

    Args:
        tex:                 The .tex string to format.
        semantic_linebreaks: If True, split prose into one sentence per line.
        indent:              Indentation string inside block environments.

    Returns:
        Formatted .tex string. PDF output is identical to input.
    """
```

**CLI:** `texphage-format` (registered in `pyproject.toml`)

```
texphage-format [OPTIONS] INPUT

Arguments:
  INPUT     Path to .tex file, or - for stdin

Options:
  -o, --output FILE           Write output to FILE (default: stdout)
  --semantic-linebreaks       One sentence per line (opt-in)
  --indent STR                Indentation string [default: 2 spaces]
```

---

## Testing

Tests live in `tests/test_formatter.py`. No TeX installation required.

Test coverage includes:
- `\par` → blank line
- Block environment isolation and indentation
- Inline environments not isolated (`minipage`, etc.)
- Adjacent/nested environment merging (`\[\begin{tikzcd}`)
- Prose after `\end{env}` stays on same line
- `\label` stays on same line as anchor
- `\item` on own line
- Multiple blank line collapse
- Preamble left untouched
- Idempotency (applying twice gives same result)
- `--semantic-linebreaks`: sentence splitting
- `--semantic-linebreaks`: abbreviation suppression (`Thm. 1` not split)
- `--semantic-linebreaks`: no split inside `$...$`

**Integration tests** (PDF round-trip via `latexmk`) are not yet implemented.
They should use `scripts/latex_playground.py` as the oracle and be marked
`pytest.mark.skipif(shutil.which("latexmk") is None, ...)`.
