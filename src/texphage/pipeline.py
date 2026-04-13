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

import shutil
from dataclasses import dataclass
from pathlib import Path

from texphage._regex import (
    _ADDBIBRESOURCE_RE,
    _BEGIN_DOCUMENT_RE,
    _BIB_EXT_RE,
    _BIB_FILE_NAME_RE,
    _BIBLIOGRAPHY_RE,
    _DECLARE_NEW_FOOTNOTE_RE,
    _DEFINECOLOR_RE,
    _DOCCLASS_RE,
    _FRONT_MATTER_RE,
    _INCLUDEGRAPHICS_RE,
    _NEWCOUNTER_RE,
    _NEWTHEOREM_RE,
    _THE_COUNTER_RE,
    _VERSION_ENV_RE,
)
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


def build_minimal_preamble(raw_tex: str) -> str:
    """Return a minimal LaTeX preamble extracted from raw_tex.

    Keeps the \\documentclass declaration, all \\usepackage / \\usetikzlibrary
    calls (with their options), front-matter commands (\\title, \\author,
    \\date, \\address, \\email, \\keywords, \\subjclass, \\dedicatory, \\thanks),
    \\newtheorem declarations, version/comment environment declarations
    (\\excludeversion, \\includeversion, \\excludecomment, \\includecomment),
    xcolor color definitions (\\definecolor, \\colorlet, \\DefineNamedColor,
    \\providecolor, \\preparecolor), and manyfoot footnote declarations
    (\\DeclareNewFootnote)
    that appear in the original preamble.  All custom macro definitions are
    stripped.

    Front-matter commands are preserved because amsart/amsbook (and similar
    document classes) require \\title and \\author to be declared in the
    preamble; stripping them causes "No \\title given" at \\maketitle.

    Package parsing is delegated to
    :func:`texphage.find_packages.find_explicit_package_calls`, which uses the
    same ``_FIND_PKG_LIB_RE`` regex as the rest of the package-analysis machinery.
    """
    begin_doc_m = _BEGIN_DOCUMENT_RE.search(raw_tex)
    raw_preamble = raw_tex[:begin_doc_m.start()] if begin_doc_m else raw_tex
    docclass_m = _DOCCLASS_RE.search(raw_preamble)
    docclass = docclass_m.group(0) if docclass_m else r'\documentclass{article}'
    pkg_lines = [call.verbatim for call in find_explicit_package_calls(raw_preamble)]
    front_matter = [m.group(0) for m in _FRONT_MATTER_RE.finditer(raw_preamble)]
    # BUG-17: multi-file projects may have duplicate \newtheorem declarations
    # after unfold merges the source. Deduplicate by environment name (first
    # occurrence wins) to avoid "Command \foo already defined" errors.
    # BUG-25: document classes (lipics-v2021, beamer, elsarticle, etc.) may
    # predefine common theorem environments (theorem, lemma, corollary, ...).
    # Wrapping each \newtheorem in \@ifundefined{envname}{...}{} prevents
    # "Command \foo already defined" when the class already provides it.
    _seen_nt: set[str] = set()
    _needed_counters: set[str] = set()
    newtheorems: list[str] = []
    for m in _NEWTHEOREM_RE.finditer(raw_preamble):
        env_name = m.group('nt_env')
        if env_name not in _seen_nt:
            _seen_nt.add(env_name)
            decl = m.group(0).strip()
            # Guard: only define if the environment does not already exist.
            guarded = (r'\makeatletter\@ifundefined{' + env_name
                       + r'}{' + decl + r'}{}\makeatother')
            newtheorems.append(guarded)
            # BUG-31: if \newtheorem uses [counter] syntax, track the counter
            # so we can preserve \newcounter{counter} and \renewcommand{\thecounter}.
            shared_counter = m.group('nt_counter')
            if shared_counter:
                _needed_counters.add(shared_counter.strip())
    # BUG-31: preserve \newcounter and \renewcommand{\the<counter>} for counters
    # referenced by \newtheorem[counter]{...} declarations.
    # Deduplicate by counter name to avoid "Command \c@name already defined"
    # (the regex may match inside comments in the raw preamble).
    counter_decls: list[str] = []
    _seen_nc: set[str] = set()
    if _needed_counters:
        for m in _NEWCOUNTER_RE.finditer(raw_preamble):
            name = m.group('nc_name').strip()
            if name in _needed_counters and name not in _seen_nc:
                _seen_nc.add(name)
                counter_decls.append(m.group(0).strip())
        _seen_tc: set[str] = set()
        for m in _THE_COUNTER_RE.finditer(raw_preamble):
            name = m.group('tc_name').strip()
            if name in _needed_counters and name not in _seen_tc:
                _seen_tc.add(name)
                counter_decls.append(m.group(0).strip())
    # BUG-18: version/comment package environment declarations must survive.
    # \excludeversion{name} / \includeversion{name} define environments;
    # stripping them causes "Environment name undefined" in the body.
    version_envs = [m.group(0).strip() for m in _VERSION_ENV_RE.finditer(raw_preamble)]
    # BUG-24: xcolor color definition commands must survive.
    # \definecolor{name}{model}{spec}, \colorlet{name}{color-expr}, etc.
    # define named colors; stripping them causes "Undefined color 'name'".
    color_defs = [m.group(0).strip() for m in _DEFINECOLOR_RE.finditer(raw_preamble)]
    # BUG-30: manyfoot \DeclareNewFootnote declarations must survive.
    # \DeclareNewFootnote{A}[arabic] defines \footnoteA; stripping it causes
    # "Undefined control sequence" for all \footnoteA calls in the body.
    footnote_decls = [m.group(0).strip() for m in _DECLARE_NEW_FOOTNOTE_RE.finditer(raw_preamble)]
    parts = (
        [docclass] + pkg_lines + counter_decls + newtheorems + version_envs
        + color_defs + footnote_decls + front_matter
    )
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Attachment discovery
# ---------------------------------------------------------------------------

# LaTeX image-search extensions, tried in order when no extension is given.
_IMAGE_EXTS = ['.pdf', '.eps', '.png', '.jpg', '.jpeg', '.tikz', '.pgf', '.svg']


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
        for name in _BIB_FILE_NAME_RE.findall(m.group(1)):
            bib = src_dir / (name if _BIB_EXT_RE.search(name) else name + '.bib')
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
    # BUG-12: preprocessing collapses the entire body to one line. TeX's bufsize
    # is 200k chars/line; large papers overflow it. Restore newlines at \par
    # boundaries — macro expansion is already complete so this is safe.
    expanded_body = expanded_body.replace(r'\par ', r'\par' + '\n')
    # Body invariant: the content between \begin{document} and \end{document}
    # must contain \n only at \par boundaries (no structural newlines injected
    # by assembly). Omit the \n that would otherwise appear immediately after
    # \begin{document} and immediately before \end{document}.
    canonical_tex = (
        minimal_preamble
        + '\n\\begin{document}'
        + expanded_body
        + '\\end{document}\n'
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
