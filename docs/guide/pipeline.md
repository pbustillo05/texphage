# Pipeline — Public API

`pipeline.py` is the main entry point for texphage. It orchestrates the full
transformation: unfold a multi-file project → expand macros → reconstruct a
minimal compilable preamble → return a self-contained canonical document.

Most users only ever call `texphage()` or `texphage_to_dir()`.

---

## The canonical output format

Every texphage call produces a **5-line canonical document**:

```latex
\documentclass[...]{...}
% <minimal preamble: \usepackage calls, \newtheorem, color definitions, ...>
\begin{document}
% <macro-expanded body, one logical paragraph per line>
\end{document}
```

The preamble contains only what is strictly necessary to compile the document:
package imports, theorem declarations, color definitions, front-matter commands.
All custom macro definitions are stripped — the body has already been expanded.

---

## API reference

### `texphage(src_dir, main_tex=None)`

Process a LaTeX project into canonical 5-line form.

```python
from texphage import texphage

canonical_tex, attachments = texphage('/path/to/arxiv/source/')
```

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `src_dir` | `str \| Path` | Root directory of the LaTeX project. |
| `main_tex` | `str \| None` | Relative path to the main `.tex` file inside `src_dir`. Auto-detected if `None`. |

**Returns** `tuple[str, list[Attachment]]`

- `canonical_tex` — the 5-line canonical LaTeX string.
- `attachments` — list of [`Attachment`](#attachment) objects: files needed to
  compile the canonical document (images, `.bib` files, etc.). Paths are
  relative to `src_dir`.

**Important:** compile `canonical_tex` from `src_dir` as the working directory
so that relative image and bibliography paths resolve correctly.

---

### `texphage_to_dir(src_dir, output_dir, main_tex=None, *, attachments_subdir='unalienable')`

Write `canonical.tex` and all attachments to a self-contained output directory.

```python
from texphage import texphage_to_dir

canonical_path = texphage_to_dir(
    src_dir    = '/path/to/arxiv/source/',
    output_dir = '/path/to/output/',
)
# Writes:
#   /path/to/output/canonical.tex
#   /path/to/output/unalienable/figures/fig1.pdf
#   /path/to/output/unalienable/refs.bib
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `src_dir` | `str \| Path` | — | Root directory of the LaTeX project. |
| `output_dir` | `str \| Path` | — | Directory to write into (created if absent). |
| `main_tex` | `str \| None` | `None` | Main `.tex` file (auto-detected if `None`). |
| `attachments_subdir` | `str` | `'unalienable'` | Subdirectory name for attachments. |

**Returns** `Path` — path to the written `canonical.tex`.

Attachment references inside `canonical.tex` are rewritten to point into
`attachments_subdir/`, so the output directory is self-contained and can be
compiled directly without the original project.

---

### `build_minimal_preamble(raw_tex)`

Extract and return only the compilable declarations from a raw LaTeX preamble.

```python
from texphage import build_minimal_preamble

preamble = build_minimal_preamble(raw_tex)
```

**Parameter:** `raw_tex: str` — full raw LaTeX string (preamble + body).

**Returns** `str` — a minimal preamble string containing:
- `\documentclass` declaration
- `\usepackage` / `\usetikzlibrary` calls
- `\newtheorem` declarations (guarded against redefinition)
- Color definitions (`\definecolor`, `\colorlet`, etc.)
- Version/comment environment declarations (`\excludeversion`, etc.)
- Footnote declarations (`\DeclareNewFootnote`)
- Front-matter commands (`\title`, `\author`, `\date`, etc.)

All custom macro definitions (`\newcommand`, `\def`, etc.) are stripped — they
are not needed because the body has already been expanded.

You rarely need to call this directly; `texphage()` calls it internally.

---

### `Attachment`

A dataclass representing a file that `canonical.tex` needs to compile.

```python
@dataclass
class Attachment:
    tex_ref:  str   # reference as written in .tex (e.g. "figures/fig1")
    src_path: Path  # actual file path, relative to src_dir (e.g. "figures/fig1.pdf")
```

`tex_ref` has no extension for images (LaTeX resolves extensions at compile
time). `src_path` has the resolved extension.

---

## Examples

### Process a single arXiv tarball

```python
import tarfile, tempfile
from pathlib import Path
from texphage import texphage_to_dir

# Extract the tarball
with tempfile.TemporaryDirectory() as src:
    with tarfile.open('2301.12345.tar.gz') as t:
        t.extractall(src)

    canonical_path = texphage_to_dir(
        src_dir    = src,
        output_dir = 'output/2301.12345/',
    )
    print(canonical_path)          # output/2301.12345/canonical.tex
```

### Process in memory (no file writes)

```python
from texphage import texphage

canonical_tex, attachments = texphage('/path/to/source/')

# Inspect what attachments are needed
for att in attachments:
    print(att.tex_ref, '->', att.src_path)

# Pass canonical_tex to an NLP pipeline
tokens = tokenizer(canonical_tex)
```

---

## Known limitations

The pipeline's fidelity guarantee — that the output compiles to the same PDF —
depends on demacro's expansion coverage. See [demacro.md](demacro.md) for the
full list of supported macro definition styles and known limitations.

Open regressions are tracked in [`BUGS.md`](../../BUGS.md).
