# find_packages — Package Discovery

`find_packages.py` identifies which LaTeX packages a document uses and can
resolve transitive dependencies via `kpsewhich`. It also provides
`find_explicit_package_calls()`, which powers the minimal preamble
reconstruction in the texphage pipeline.

Most users do not call this module directly — `texphage()` calls it
internally. Use it directly when you need package metadata (e.g. to build a
minimal TeX installation for batch compilation).

---

## Key concepts

**Explicit calls** — `\usepackage{amsmath}` and `\usetikzlibrary{arrows}` as
written by the author. `find_explicit_package_calls()` returns these, in
document order, preserving options and multi-package comma-lists.

**Transitive dependencies** — packages often load other packages internally.
`find_used_packages()` walks the dependency tree via `kpsewhich` and returns
the complete set. Results are cached in `cache/` across runs.

**Why `kpsewhich`?** Text scanning alone cannot know which packages a
`\usepackage` call will ultimately load — that depends on the installed TeX
distribution. `kpsewhich` asks TeX Live directly, giving an accurate answer
without parsing `.sty` source.

---

## System requirement

`kpsewhich` must be on `PATH` (it is part of TeX Live / MacTeX). The
`find_used_packages()` and `get_dependencies()` functions fail gracefully when
`kpsewhich` is unavailable, returning empty results. `find_explicit_package_calls()`
does **not** require `kpsewhich` — it is a pure text scan.

---

## API reference

### `find_explicit_package_calls(preamble)`

Return structured `PackageCall` objects for every `\usepackage` and
`\usetikzlibrary` found in a preamble string.

```python
from texphage.find_packages import find_explicit_package_calls

calls = find_explicit_package_calls(raw_preamble)
for call in calls:
    print(call.verbatim)
# \usepackage[utf8]{inputenc}
# \usepackage{amsmath,amsthm}
# \usetikzlibrary{arrows}
```

**Parameter:** `preamble: str` — raw LaTeX preamble (text before `\begin{document}`).

**Returns** `list[PackageCall]` — one object per `\usepackage` /
`\usetikzlibrary` line, in document order.

Only the author's explicit calls are returned — transitive dependencies are not
expanded. This is the function used by `build_minimal_preamble()` to
reconstruct the package list.

---

### `PackageCall`

A dataclass representing one `\usepackage` or `\usetikzlibrary` call.

```python
@dataclass
class PackageCall:
    names:      list[str]  # e.g. ['amsmath'] or ['amsmath', 'amsthm']
    options:    str        # e.g. 'utf8'; empty string when no options
    is_tikzlib: bool       # True for \usetikzlibrary / \usepgflibrary
    lib_type:   str        # 'tikz' or 'pgf'; '' for packages
```

`call.verbatim` reconstructs the canonical LaTeX call string.

---

### `find_used_packages(tex)`

Return all packages (and transitive dependencies) used in a LaTeX string.

```python
from texphage.find_packages import find_used_packages

all_pkgs = find_used_packages(flat_tex)
# ['amsmath', 'amsthm', 'amsfonts', 'amssymb', ...]
```

**Parameter:** `tex: str` — LaTeX string (preamble + body).

**Returns** `list[str]` — package names including transitive dependencies.
Results are cached in `cache/texlive_dependencies.json` across runs.

Requires `kpsewhich` on `PATH`.

---

### `find_command(csname, list_packages)`

Find which package in `list_packages` defines `\csname`.

```python
from texphage.find_packages import find_command

pkg = find_command('align', ['amsmath', 'mathtools'])
# 'amsmath'
```

Searches packages in reverse load order (last loaded = highest priority in
LaTeX). Returns the package name, or `''` if not found.

---

## Caching

`find_used_packages()` and related dependency lookups are expensive (each
`kpsewhich` call is a subprocess). Results are cached in `cache/` as JSON
files, protected by file locks for concurrent safety. The cache is written on
clean exit (`atexit`) or when `save_cache()` is called explicitly.

The `cache/` directory is gitignored — it is a local build artifact.
