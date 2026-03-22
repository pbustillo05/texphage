"""Main texphage pipeline: unfold → demacro → minimal canonical document.

Public API
----------
texphage(src_dir, main_tex=None)
    → (canonical_tex: str, attachments: list[Attachment])

texphage_to_dir(src_dir, output_dir, main_tex=None, *, attachments_subdir='unalienable')
    → Path  (path to the written canonical.tex)

build_minimal_preamble(raw_tex)
    → str   (\\documentclass + \\usepackage calls, nothing else)

Attachment
    Dataclass: tex_ref (str) + src_path (Path relative to src_dir).
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import regex as _re

from texphage.demacro import demacro
from texphage.find_packages import find_explicit_package_calls
from texphage.unfold import unfold

__all__ = [
    'texphage',
    'texphage_to_dir',
    'build_minimal_preamble',
    'Attachment',
]


# ---------------------------------------------------------------------------
# Preamble reconstruction
# ---------------------------------------------------------------------------

_DOCCLASS_RE = _re.compile(r'\\documentclass\s*(?:\[[^\]]*\])?\s*\{[^}]*\}')


def build_minimal_preamble(raw_tex: str) -> str:
    """Return a minimal LaTeX preamble extracted from raw_tex.

    Keeps only the \\documentclass declaration and all \\usepackage /
    \\usetikzlibrary calls (with their options), in original order.
    All custom macro definitions are stripped.

    Package parsing is delegated to
    :func:`texphage.find_packages.find_explicit_package_calls`, which uses the
    same ``find_pkg_lib`` regex as the rest of the package-analysis machinery.
    """
    begin_doc = raw_tex.find(r'\begin{document}')
    raw_preamble = raw_tex[:begin_doc] if begin_doc != -1 else raw_tex
    docclass_m = _DOCCLASS_RE.search(raw_preamble)
    docclass = docclass_m.group(0) if docclass_m else r'\documentclass{article}'
    pkg_lines = [call.verbatim for call in find_explicit_package_calls(raw_preamble)]
    return docclass + '\n' + '\n'.join(pkg_lines)


# ---------------------------------------------------------------------------
# Attachment discovery
# ---------------------------------------------------------------------------

# LaTeX image-search extensions, tried in order when no extension is given.
_IMAGE_EXTS = ['.pdf', '.eps', '.png', '.jpg', '.jpeg', '.tikz', '.pgf', '.svg']

_INCLUDEGRAPHICS_RE = re.compile(
    r'\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}'
)
_BIBLIOGRAPHY_RE    = re.compile(r'\\bibliography\s*\{([^}]+)\}')
_ADDBIBRESOURCE_RE  = re.compile(r'\\addbibresource\s*\{([^}]+)\}')


@dataclass
class Attachment:
    """A file that canonical.tex needs to compile but cannot be inlined.

    tex_ref  — the reference as written in the .tex source (e.g. ``figures/fig1``
               for images, ``refs`` for bibliography).  No extension for images
               (LaTeX resolves extensions itself at compile time).
    src_path — actual file path on disk, *relative to the project root* (e.g.
               ``figures/fig1.pdf``).
    """
    tex_ref: str
    src_path: Path


def find_attachments(tex: str, src_dir: str | Path) -> list[Attachment]:
    """Return all external files referenced in *tex* that must travel with it.

    Scans for ``\\includegraphics``, ``\\bibliography``, ``\\addbibresource``.
    Resolves actual file paths by probing the filesystem (trying image
    extensions for graphics).  References that cannot be resolved on disk are
    silently skipped.

    Args:
        tex:     LaTeX source string (typically the already-expanded canonical_tex).
        src_dir: Root directory of the project; all paths are resolved relative
                 to this directory.
    """
    src_dir = Path(src_dir)
    attachments: list[Attachment] = []
    seen: set[str] = set()

    def _add(tex_ref: str, actual: Path) -> None:
        if tex_ref not in seen:
            seen.add(tex_ref)
            attachments.append(Attachment(tex_ref=tex_ref, src_path=actual.relative_to(src_dir)))

    # --- Images ---
    for m in _INCLUDEGRAPHICS_RE.finditer(tex):
        ref = m.group(1).strip()
        candidate = src_dir / ref
        if candidate.exists():
            _add(ref, candidate)
            continue
        for ext in _IMAGE_EXTS:
            with_ext = candidate.parent / (candidate.name + ext)
            if with_ext.exists():
                _add(ref, with_ext)
                break

    # --- \bibliography{file1,file2,...} ---
    for m in _BIBLIOGRAPHY_RE.finditer(tex):
        for name in m.group(1).split(','):
            name = name.strip()
            bib = src_dir / (name if name.endswith('.bib') else name + '.bib')
            if bib.exists():
                _add(name, bib)

    # --- \addbibresource{file.bib} (biblatex) ---
    for m in _ADDBIBRESOURCE_RE.finditer(tex):
        ref = m.group(1).strip()
        candidate = src_dir / ref
        if candidate.exists():
            _add(ref, candidate)

    return attachments


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def texphage(
    src_dir: str | Path,
    main_tex: str | None = None,
) -> tuple[str, list[Attachment]]:
    """Process a LaTeX project into canonical 5-line form.

    Unfolds a multi-file project, expands all user-defined macros, and
    reconstructs a minimal compilable document whose PDF output is identical
    to the original.

    Args:
        src_dir:  Root directory of the LaTeX project.
        main_tex: Relative path to the main .tex file inside *src_dir*.
                  Auto-detected via ``unfold.find_main_file`` if None.

    Returns:
        ``(canonical_tex, attachments)`` where:

        - *canonical_tex* is the 5-line canonical LaTeX string.  Compile it
          from *src_dir* (so that relative paths to images etc. resolve).
        - *attachments* is the list of :class:`Attachment` objects — files
          that must be present alongside *canonical_tex* for it to compile
          (images, bib files, …).  Each path is relative to *src_dir*.
    """
    src_dir = Path(src_dir)
    raw_tex = unfold(src_dir, main_tex)
    expanded_body, _packages, _problems = demacro(raw_tex)
    minimal_preamble = build_minimal_preamble(raw_tex)
    canonical_tex = (
        minimal_preamble
        + '\n\\begin{document}\n'
        + expanded_body
        + '\n\\end{document}\n'
    )
    attachments = find_attachments(canonical_tex, src_dir)
    return canonical_tex, attachments


def texphage_to_dir(
    src_dir: str | Path,
    output_dir: str | Path,
    main_tex: str | None = None,
    *,
    attachments_subdir: str = 'unalienable',
) -> Path:
    """Write ``canonical.tex`` and all attachments to *output_dir*.

    Attachments are copied to ``output_dir/attachments_subdir/``, preserving
    their relative path structure from *src_dir*.  All references to
    attachments inside ``canonical.tex`` are rewritten to point to the new
    ``attachments_subdir/…`` paths.

    Args:
        src_dir:            Root directory of the LaTeX project.
        output_dir:         Directory to write into (created if absent).
        main_tex:           Relative path to main .tex (auto-detected if None).
        attachments_subdir: Subdirectory name for attachments (default:
                            ``'unalienable'``).

    Returns:
        Path to the written ``canonical.tex``.
    """
    src_dir    = Path(src_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_tex, attachments = texphage(src_dir, main_tex)

    for att in attachments:
        new_ref = f'{attachments_subdir}/{att.tex_ref}'
        # Rewrite the exact brace-delimited reference in the tex source.
        canonical_tex = canonical_tex.replace(
            '{' + att.tex_ref + '}',
            '{' + new_ref + '}',
        )
        dest = output_dir / attachments_subdir / att.src_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_dir / att.src_path, dest)

    canonical_path = output_dir / 'canonical.tex'
    canonical_path.write_text(canonical_tex, encoding='utf-8')
    return canonical_path
