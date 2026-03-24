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

# Front-matter commands that must survive preamble stripping.
# amsart/amsbook put \title, \author, \address, \email, \keywords, \subjclass,
# \dedicatory in the preamble (before \begin{document}); without them
# \maketitle raises "No \title given."  Standard article class may also use
# \title, \author, \date in the preamble (optional in that class).
# Pattern uses regex balanced-brace group for the mandatory argument so that
# nested braces inside \title{A {B} C} are captured correctly.
_FRONT_MATTER_RE = _re.compile(
    r'\\(?:title|author|date|address|email|keywords|subjclass|dedicatory|thanks)'
    r'(?:\[[^\]]*\])?'          # optional [short] argument
    r'\s*'
    r'(?P<arg>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?P&arg))*(?<!\\)\})',
    _re.DOTALL,
)

# \newtheorem{name}{print-name}[numbered-within]  and  \newtheorem*{name}{print-name}
# These define LaTeX theorem environments that must remain in the preamble;
# they are NOT macro definitions that demacro can expand away.
# Docs: https://texdoc.org/pkg/amsthm
# MATCHES: \newtheorem{envname}{Print Name}[numbered-within]
#          \newtheorem*{envname}{Print Name}
#          \newtheoremrm{envname}{Print Name}  (tac.cls)
#          \newtheoremit{envname}{Print Name}  (class-specific variants)
# CAPTURES:
#   nt_env → the environment name, e.g. "remark"
# LIMITATIONS:
#   [observed] Does not handle \theoremstyle{} — that is a separate command,
#              not part of the \newtheorem declaration itself.
#   [observed] BUG-20: \newtheoremrm (tac.cls) was missed before \w* was added.
#   [observed] BUG-22: \newtheoremstyle (amsthm) has 9 args; must be excluded
#              via negative lookahead to avoid partial capture.
#   [observed] BUG-23: print-name may contain nested braces (e.g. \ref{...});
#              must use balanced-brace group, not [^}]*.
_NEWTHEOREM_RE = _re.compile(
    r'\\newtheorem(?!style)\w*\*?'
    r'\s*\{(?P<nt_env>[^}]*)\}' # {environment-name} — captured for deduplication
    r'\s*(?:\[[^\]]*\])?'       # optional [numbered-within] before print-name
    # {print-name} — balanced braces for nested \ref{...} etc. (BUG-23)
    r'\s*(?P<nt_title>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?P&nt_title))*(?<!\\)\})'
    r'\s*(?:\[[^\]]*\])?',      # optional [numbered-within] after print-name
    _re.DOTALL,
)


# \excludeversion{name} and \includeversion{name} from the version package.
# These define LaTeX environments by name in the preamble. Without them,
# \begin{name}...\end{name} in the body fails with "Environment name undefined."
# Also matches the optional-argument form \excludeversion[replacement]{name}.
# The comment package provides \includecomment / \excludecomment (same semantics).
# Docs: https://ctan.org/pkg/version, https://ctan.org/pkg/comment
# MATCHES: \excludeversion{invisible}
#          \excludeversion[(redacted)]{secret}
#          \includeversion{visible}
#          \includecomment{name}
#          \excludecomment{name}
# CAPTURES: full match only (no named groups needed)
# LIMITATIONS:
#   [observed] \excludeversion optional arg [text] captured correctly.
#   [inferred] Nested braces in optional arg not supported (unlikely in practice).
_VERSION_ENV_RE = _re.compile(
    r'\\(?:exclude|include)(?:version|comment)'
    r'\s*(?:\[[^\]]*\])?'   # optional [replacement text] (excludeversion only)
    r'\s*\{[^}]*\}',
    _re.DOTALL,
)


def build_minimal_preamble(raw_tex: str) -> str:
    """Return a minimal LaTeX preamble extracted from raw_tex.

    Keeps the \\documentclass declaration, all \\usepackage / \\usetikzlibrary
    calls (with their options), front-matter commands (\\title, \\author,
    \\date, \\address, \\email, \\keywords, \\subjclass, \\dedicatory, \\thanks),
    \\newtheorem declarations, and version/comment environment declarations
    (\\excludeversion, \\includeversion, \\excludecomment, \\includecomment)
    that appear in the original preamble.  All custom macro definitions are
    stripped.

    Front-matter commands are preserved because amsart/amsbook (and similar
    document classes) require \\title and \\author to be declared in the
    preamble; stripping them causes "No \\title given" at \\maketitle.

    Package parsing is delegated to
    :func:`texphage.find_packages.find_explicit_package_calls`, which uses the
    same ``find_pkg_lib`` regex as the rest of the package-analysis machinery.
    """
    begin_doc = raw_tex.find(r'\begin{document}')
    raw_preamble = raw_tex[:begin_doc] if begin_doc != -1 else raw_tex
    docclass_m = _DOCCLASS_RE.search(raw_preamble)
    docclass = docclass_m.group(0) if docclass_m else r'\documentclass{article}'
    pkg_lines = [call.verbatim for call in find_explicit_package_calls(raw_preamble)]
    front_matter = [m.group(0) for m in _FRONT_MATTER_RE.finditer(raw_preamble)]
    # BUG-17: multi-file projects may have duplicate \newtheorem declarations
    # after unfold merges the source. Deduplicate by environment name (first
    # occurrence wins) to avoid "Command \foo already defined" errors.
    _seen_nt: set[str] = set()
    newtheorems: list[str] = []
    for m in _NEWTHEOREM_RE.finditer(raw_preamble):
        env_name = m.group('nt_env')
        if env_name not in _seen_nt:
            _seen_nt.add(env_name)
            newtheorems.append(m.group(0).strip())
    # BUG-18: version/comment package environment declarations must survive.
    # \excludeversion{name} / \includeversion{name} define environments;
    # stripping them causes "Environment name undefined" in the body.
    version_envs = [m.group(0).strip() for m in _VERSION_ENV_RE.finditer(raw_preamble)]
    parts = [docclass] + pkg_lines + newtheorems + version_envs + front_matter
    return '\n'.join(parts)


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
    # BUG-12: preprocessing collapses the entire body to one line. TeX's bufsize
    # is 200k chars/line; large papers overflow it. Restore newlines at \par
    # boundaries — macro expansion is already complete so this is safe.
    expanded_body = expanded_body.replace(r'\par ', r'\par' + '\n')
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
