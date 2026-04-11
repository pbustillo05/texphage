# unfold — Multi-File Flattening

`unfold.py` recursively resolves all file-inclusion directives in a LaTeX
project and produces a single flat `.tex` string. It is the first step in the
texphage pipeline, run before macro expansion.

Most users get unfolding for free via [`texphage()`](pipeline.md). Call
`unfold()` directly when you only need a flat source — without macro expansion
— or when building a custom pipeline.

---

## Why unfolding matters

arXiv LaTeX projects are almost always multi-file: a `main.tex` that pulls in
sections via `\input{sections/intro}`, macros via `\input{macros}`, and
subfiles via `\include{appendix}`. Processing these with a single-file tool
fails silently — references are left unresolved.

Unfolding produces one string that contains everything, with all includes
substituted in place, safe against circular includes.

---

## Supported directives

| Directive | Source | Behaviour |
|-----------|--------|-----------|
| `\input{path}` | LaTeX2e | Inline verbatim; `.tex` auto-appended if no extension |
| `\input path` | plain TeX | Braceless form; same rules |
| `\include{path}` | LaTeX2e | Inline with `\clearpage` guards; forces `.tex` extension |
| `\import{dir}{file}` | `import` pkg | `dir` is absolute or root-relative |
| `\inputfrom{dir}{file}` | `import` pkg | Alias for `\import` |
| `\subimport{dir}{file}` | `import` pkg | `dir` is relative to the current file |
| `\subinputfrom{dir}{file}` | `import` pkg | Alias for `\subimport` |
| `\subfile{path}` | `subfiles` pkg | Own preamble stripped; body inlined |
| `\subfileinclude{path}` | `subfiles` pkg | Same as `\subfile` |
| `\InputIfFileExists{file}{true}{false}` | LaTeX2e kernel | Inlines file if found; emits true-code before content |
| `\usepackage{pkg}` | LaTeX2e | Inlined only when `inline_local_packages=True` and `.sty` found locally |

---

## API reference

### `unfold(directory, main=None, inline_local_packages=False)`

Flatten a multi-file LaTeX project into a single `.tex` string.

```python
from texphage.unfold import unfold

flat_tex = unfold('/path/to/project/')
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | `str \| Path` | — | Root directory of the project. All relative paths resolve here. |
| `main` | `str \| None` | `None` | Main `.tex` file content. If `None`, auto-detected via `find_main_file()`. |
| `inline_local_packages` | `bool` | `False` | If `True`, local `.sty` files are inlined as well. Off by default — risky for complex packages. |

**Returns** `str` — a single flat `.tex` string with all resolvable includes
substituted. Unresolvable references are left as-is with a warning logged.

**Circular includes** are detected: the second occurrence of a file is left
unexpanded and a warning is logged.

---

## Examples

### Flatten only (no macro expansion)

```python
from texphage.unfold import unfold

flat_tex = unfold('/path/to/multi-file-project/')
# flat_tex contains the merged .tex; macros are still intact
```

### Inline local `.sty` files too

```python
flat_tex = unfold('/path/to/project/', inline_local_packages=True)
```

Use with care: complex packages define internal commands that interact badly
with demacro's expansion.

---

## Known gaps

The following directives are **not** handled:

- `\includefrom` / `\subincludefrom` (import package variants)
- `\RequirePackage` / `\LoadClass` (package/class code)
- `\verbatiminput` / `\lstinputlisting` / `\inputminted` — intentionally
  excluded: verbatim file content should not be inlined for NLP purposes
- `\input@path`, `\graphicspath` and similar path-modifying commands — paths
  are always resolved relative to the current file's directory

See [`TODO.md`](../../TODO.md) for planned improvements.
