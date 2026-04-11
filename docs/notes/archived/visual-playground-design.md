# Visual Playground — Implementation Brief

**For Opus:** Read this whole file, then implement the four tasks in the
"Your Tasks" section. Read the design context first — it explains *why*
decisions were made and will help you handle edge cases correctly.

**Read these files before writing any code:**
- `scripts/latex_playground.py`
- `.claude/skills/playground-protocol/SKILL.md`
- `.claude/agents/testing-agent.md`
- `pyproject.toml` (verify `pdf2image` and `scikit-image` are in `[agents]` extras)

**Environment:** use `.venv/bin/python` for all commands.

---

## Design Context

### The three visual workflows (keep these distinct)

**1. Playground single-snippet inspection**
Pure TeX behavioral probing: "What does `\global` do here? What happens if I
add a bracket?" You compile one tiny snippet and look at the rendered output.
No comparison, no differential. `standalone` is natural here. This is what
the playground is primarily for.

**2. Playground snippet comparison**
Claude authors two or more TeX variants and compares them: "Are these
equivalent?" The snippets are complete `.tex` files (documentclass included)
because Claude is deliberately crafting each one. No `_WRAPPER` applied.

**3. arXiv pipeline differential (testing-agent)**
Testing-agent compares raw arXiv source vs. texphage output. Already
implemented in Step 6c (SSIM + side-by-side PNGs saved to `visual_diff/`).
The only missing piece: Claude should `Read` those PNG files during Step 7
diagnosis. No new compilation needed there.

### Key design decisions

- `compile_snippet` gets `visual=True` (opt-in, not default) and
  `use_standalone=True` (opt-in). Raise `ValueError` if `visual=True` and
  `keep_dir is None` — files must survive long enough for Claude to `Read` them.

- `compare_snippets` takes **complete `.tex` strings** — do NOT apply
  `_WRAPPER` or `_STANDALONE_WRAPPER` to them. The caller controls the
  documentclass because they are deliberately crafting variants.

- No `compile_visual_pair(original, candidate)` function. That framing implies
  "original vs. modified" which is wrong for playground probing. Use
  `compare_snippets([a, b], ...)` instead, which also generalises to N > 2.

- **Diff-first protocol** (documented in Template F): always `Read` the diff
  image before loading individual PNGs. If diff is uniform → SSIM ≈ 1.0 →
  done. This keeps context costs low.

- No new skill file. Templates E and F go into the existing
  `playground-protocol` skill.

### `standalone` class tradeoffs

Use `standalone` when the snippet is a self-contained fragment (formula,
theorem, definition) and you want a tight crop. Do NOT use it when comparing
pipeline output (which uses `article`) — mismatched classes create spurious
visual diffs.

### Context budget

| Images loaded | Approx tokens |
|---|---|
| 1 diff PNG (standalone snippet) | ~1–3k |
| diff + 2 PNGs (standalone) | ~5–10k |
| diff + 2 PNGs (full article page) | ~30–50k |

---

## Your Tasks

### Task 1 — Extend `compile_snippet`

Add two parameters (both default to False/None — existing callers unaffected):

```python
def compile_snippet(
    body: str,
    preamble: str = '',
    packages: list[str] | None = None,
    timeout: int = 30,
    keep_dir: Path | None = None,
    visual: bool = False,           # NEW
    use_standalone: bool = False,   # NEW
) -> PlaygroundResult:
```

- If `visual=True` and `keep_dir is None`: raise `ValueError("keep_dir is required when visual=True")`
- If `use_standalone=True`: use `_STANDALONE_WRAPPER` (see below) instead of `_WRAPPER`
- If `visual=True` and compile succeeded: render page 1 to `keep_dir / 'output.png'`
  using `pdf2image.convert_from_path(..., first_page=1, last_page=1, dpi=150)`

Add `_STANDALONE_WRAPPER` constant alongside `_WRAPPER`:

```python
_STANDALONE_WRAPPER = r"""\documentclass[border=4pt]{{standalone}}
\usepackage{{amsmath,amssymb,xparse,xargs}}
{preamble}
\begin{{document}}
{body}
\end{{document}}
"""
```

Add one field to `PlaygroundResult` (keep all existing fields unchanged):

```python
png_path: Path | None = None   # set when visual=True and compile succeeded
```

---

### Task 2 — Add `compare_snippets`

New dataclass:

```python
@dataclass
class CompareResult:
    results: list[PlaygroundResult]
    pngs: list[Path | None]                       # page 1 PNG per snippet
    diffs: dict[tuple[int, int], Path | None]     # (i,j) → diff PNG, i < j only
    ssim_scores: dict[tuple[int, int], float | None]
    labels: list[str]
    keep_dir: Path
```

New function:

```python
def compare_snippets(
    snippets: list[str],           # 2+ COMPLETE .tex strings (documentclass included)
    keep_dir: Path,                # mandatory — no default
    labels: list[str] | None = None,
    dpi: int = 150,
    timeout: int = 30,
) -> CompareResult:
```

Implementation rules:
- Raise `ValueError` if `len(snippets) < 2`
- Raise `ValueError` if `labels` provided but `len(labels) != len(snippets)`
- Auto-generate labels `['snippet_0', 'snippet_1', ...]` if `labels` is None
- Write each snippet verbatim (no wrapping) to `keep_dir / f'snippet_{i}' / 'test.tex'`
- Factor out `_compile_tex_file(tex_file, work_dir, timeout) -> PlaygroundResult`
  from `compile_snippet`'s closure so both functions share it
- If compile succeeded, render page 1 to `keep_dir / f'snippet_{i}.png'`
- After all compiles, generate all pairwise diffs:

```python
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

def _make_diff(png_a: Path, png_b: Path, diff_out: Path) -> float:
    img_a = np.array(Image.open(png_a).convert('L'))
    img_b = np.array(Image.open(png_b).convert('L'))

    # Pad to same dimensions (outputs may differ in size)
    h = max(img_a.shape[0], img_b.shape[0])
    w = max(img_a.shape[1], img_b.shape[1])
    def pad(img):
        out = np.full((h, w), 255, dtype=np.uint8)
        out[:img.shape[0], :img.shape[1]] = img
        return out
    img_a, img_b = pad(img_a), pad(img_b)

    score, diff = structural_similarity(img_a, img_b, full=True)
    diff_vis = ((1.0 - diff) * 127.5).clip(0, 255).astype(np.uint8)
    Image.fromarray(diff_vis).save(str(diff_out))
    return float(score)
```

- If either PNG is missing (compile failed), set `ssim_scores[(i,j)] = None`,
  `diffs[(i,j)] = None` — still populate all other fields

---

### Task 3 — Add Templates E and F to `playground-protocol` skill

Append to `.claude/skills/playground-protocol/SKILL.md`:

~~~markdown
---

## Template E — Single snippet visual inspection

**Question:** What does this TeX fragment actually render as?

Use when `pdf_text` is insufficient (math symbols, spacing, fonts).
`use_standalone=True` gives a tight crop for self-contained fragments.
Do NOT use standalone when the snippet depends on page geometry or floats.

```python
from pathlib import Path
import shutil
from scripts.latex_playground import compile_snippet

keep = Path('/tmp/pg_probe')
result = compile_snippet(
    body=r'\( \int_0^1 x^2 \, dx = \tfrac{1}{3} \)',
    preamble=r'\usepackage{amsmath}',
    use_standalone=True,
    visual=True,
    keep_dir=keep,
)

if result.ok:
    # Use the Read tool on result.png_path — multimodal, no extra steps.
    print(result.png_path)
else:
    print(result.error_lines)

shutil.rmtree(keep)   # always clean up
```

Context cost: standalone PNG at 150 DPI ≈ 1–3k tokens.

---

## Template F — Multi-snippet visual comparison

**Question:** Are these TeX variants visually equivalent?

Snippets must be COMPLETE `.tex` strings (documentclass included).
Protocol: **diff first** — read the diff image before loading individual PNGs.

```python
from pathlib import Path
import shutil
from scripts.latex_playground import compare_snippets

snippets = [
    r"""\documentclass[border=4pt]{standalone}
\begin{document}$\frac{d}{dx}\sin x = \cos x$\end{document}""",

    r"""\documentclass[border=4pt]{standalone}
\begin{document}$(\sin x)' = \cos x$\end{document}""",
]

keep = Path('/tmp/pg_compare')
result = compare_snippets(snippets, keep_dir=keep, labels=['Leibniz', 'Prime'])

print(f"SSIM(0,1): {result.ssim_scores[(0, 1)]:.4f}")

# Step 1: Read result.diffs[(0, 1)] first.
#   Uniform/dark image → visually identical → done.
#   Bright regions → proceed to step 2.
# Step 2: Read result.pngs[0] and result.pngs[1].

shutil.rmtree(keep)
```

Context budget:

| Images loaded | Approx tokens |
|---|---|
| 1 diff PNG (standalone) | ~1–3k |
| diff + both PNGs (standalone) | ~5–10k |
| diff + both PNGs (full page) | ~30–50k |
~~~

---

### Task 4 — Update testing-agent Step 7 visual diagnosis

In `.claude/agents/testing-agent.md`, find:

```
#### For visual diff pages (SSIM < 0.95)

Open `visual_diff/page_N_diff.png`. Determine: is the difference a content
change (wrong text) or a layout shift (same text, different position)?
```

Replace with:

```
#### For visual diff pages (SSIM < 0.95)

Use the `Read` tool to load `visual_diff/page_N_diff.png` directly — Claude's
multimodal capability processes it natively. Cap at **3 pages per paper**; if
more than 3 pages have SSIM < 0.95, load the 3 with the lowest scores.

Determine: is the difference a content change (wrong text) or a layout shift
(same text, different position)?
```

Leave the rest of that section unchanged.

---

## Tests to write

Create `tests/test_visual_playground.py`:

```python
import shutil
import pytest
from pathlib import Path
from scripts.latex_playground import compile_snippet, compare_snippets

pytestmark = pytest.mark.skipif(
    not __import__('shutil').which('latexmk'),
    reason='latexmk not available'
)


def test_visual_requires_keep_dir():
    with pytest.raises(ValueError, match='keep_dir'):
        compile_snippet(body=r'hello', visual=True)


def test_compile_snippet_visual_standalone(tmp_path):
    result = compile_snippet(
        body=r'\textbf{hello}',
        use_standalone=True,
        visual=True,
        keep_dir=tmp_path,
    )
    assert result.ok
    assert result.png_path is not None
    assert result.png_path.exists()


def test_compare_snippets_requires_two():
    with pytest.raises(ValueError):
        compare_snippets(
            [r'\documentclass{standalone}\begin{document}x\end{document}'],
            keep_dir=Path('/tmp'),
        )


def test_compare_snippets_label_mismatch():
    tex = r'\documentclass{standalone}\begin{document}x\end{document}'
    with pytest.raises(ValueError):
        compare_snippets([tex, tex], keep_dir=Path('/tmp'), labels=['only_one'])


def test_compare_snippets_identical(tmp_path):
    tex = (r'\documentclass[border=4pt]{standalone}'
           r'\begin{document}hello\end{document}')
    r = compare_snippets([tex, tex], keep_dir=tmp_path)
    assert all(res.ok for res in r.results)
    assert r.ssim_scores[(0, 1)] > 0.99
    assert r.diffs[(0, 1)] is not None and r.diffs[(0, 1)].exists()


def test_compare_snippets_different(tmp_path):
    a = (r'\documentclass[border=4pt]{standalone}'
         r'\begin{document}\textbf{hello}\end{document}')
    b = (r'\documentclass[border=4pt]{standalone}'
         r'\begin{document}hello\end{document}')
    r = compare_snippets([a, b], keep_dir=tmp_path, labels=['bold', 'plain'])
    assert r.labels == ['bold', 'plain']
    assert r.ssim_scores[(0, 1)] < 0.99
    assert r.diffs[(0, 1)] is not None


def test_compare_snippets_three(tmp_path):
    def make(body):
        return (r'\documentclass[border=4pt]{standalone}'
                rf'\begin{{document}}{body}\end{{document}}')
    snippets = [make(r'\textbf{x}'), make(r'\textit{x}'), make('x')]
    r = compare_snippets(snippets, keep_dir=tmp_path)
    assert len(r.results) == 3
    for pair in [(0, 1), (0, 2), (1, 2)]:
        assert pair in r.diffs
        assert pair in r.ssim_scores
```

---

## What NOT to do

- Do NOT apply `_WRAPPER` or `_STANDALONE_WRAPPER` in `compare_snippets` —
  snippets are already complete `.tex` files.
- Do NOT make `visual=True` the default in `compile_snippet`.
- Do NOT change any existing `compile_snippet` behavior for callers that don't
  pass the new parameters.
- Do NOT touch `demacro.py`, `_regex.py`, `pipeline.py`, or `unfold.py`.
- Do NOT create a new skill file — add Templates E and F to the existing
  `playground-protocol` skill only.
- Do NOT load baseline+candidate PNGs in Template F before reading the diff.

## After implementing

```bash
.venv/bin/python -m pytest tests/test_visual_playground.py -v
.venv/bin/python -m pytest tests/ -v
.venv/bin/ruff check src/ scripts/
.venv/bin/mypy src/texphage/
```

If `pdf2image` or `skimage` are not importable: `.venv/bin/pip install -e '.[agents]'`
