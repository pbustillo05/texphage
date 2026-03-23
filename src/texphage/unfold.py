"""Unfold a multi-file LaTeX project into a single flat .tex string.

The main entry point is unfold(). It recursively resolves \\input, \\include,
\\import, \\subimport, and \\subfile by reading referenced files and substituting
their content in place. Images and other non-.tex assets are left as-is.

This module has NO dependency on network access, archive extraction, or macro
expansion. Its only inputs are local filesystem paths.
"""
from __future__ import annotations

import glob
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# _FIND_INPUT — the single pattern that recognises all supported file-inclusion directives.
#
# MATCHES (one named branch per inclusion form):
#   input      → \input{path}
#   input_bare → \input path  (braceless, plain-TeX style; BUG-14)
#   include    → \include{path}          (.tex auto-appended; body wrapped in \clearpage)
#   usepkg     → \usepackage{pkg}        (only when inline_local_packages=True)
#   import_    → \import{dir}{file}      (import pkg; dir is absolute/root-relative)
#   subimport  → \subimport{dir}{file}   (import pkg; dir is relative to current file)
#   subfile    → \subfile{path} or \subfileinclude{path}   (subfiles pkg; own preamble stripped)
#
# CAPTURES (named groups):
#   input_path, input_bare_path, include_path, usepkg_path,
#   import_dir, import_file, subimport_dir, subimport_file, subfile_path
#
# LIMITATIONS:
#   [observed] The ^[^%\n]* guard prevents matching directives that start a line with
#              a comment, but a % occurring after real content on the same line will
#              still allow the directive to match even if it is preceded by a comment
#              marker mid-line (e.g., "text % \input{foo}" is matched).
#   [observed] \input auto-appends .tex only when the path has no extension (no dot in
#              the basename); paths with any extension are used verbatim.
#   [observed] \include always forces a .tex extension; there is no way to \include a
#              non-.tex file regardless of what extension the argument carries.
#   [observed] \subfileinclude is handled identically to \subfile (same branch).
#   [observed] \usepackage inlining is disabled by default (inline_local_packages=False)
#              and only resolves packages found as local .sty files in the project
#              directory; system packages are left as \usepackage{...}.
#   [inferred] \InputIfFileExists{file}{true}{false} not handled — conditional input
#              from the LaTeX2e kernel; the false-branch is silently ignored (source2e §Input).
#   [inferred] \input@path, \graphicspath and similar path-modifying commands not
#              tracked; unfold always resolves paths relative to the current file's
#              directory, which matches standard LaTeX behaviour for most documents.
#   [inferred] \RequirePackage and \LoadClass (common in .sty/.cls files) not handled —
#              they accept the same argument form as \usepackage but are used in package
#              and class code rather than in author documents.
#   [inferred] \verbatiminput, \lstinputlisting, \inputminted not handled — these insert
#              file content verbatim (as code listings) and should not be expanded into
#              the document body for NLP purposes anyway.
_FIND_INPUT = re.compile(r"""
    ^[^%\n]*
    (?:
        (?P<input>      \\input      \s*\{\s*(?P<input_path>      .*?)\s*\})  |
        (?P<input_bare> \\input      \s+(?P<input_bare_path>[^\s\{\}%]+))     |
        (?P<include>    \\include    \s*\{\s*(?P<include_path>    .*?)\s*\})  |
        (?P<usepkg>     \\usepackage \s*\{\s*(?P<usepkg_path>     .*?)\s*\})  |
        (?P<import_>    \\import     \s*\{\s*(?P<import_dir>      .*?)\s*\}\s*\{\s*(?P<import_file>    .*?)\s*\})  |
        (?P<subimport>  \\subimport  \s*\{\s*(?P<subimport_dir>   .*?)\s*\}\s*\{\s*(?P<subimport_file> .*?)\s*\})  |
        (?P<subfile>    \\subfile(?:include)?\s*\{\s*(?P<subfile_path>.*?)\s*\})
    )
""", re.MULTILINE | re.VERBOSE)

__all__ = ["unfold", "find_main_file"]


def find_main_file(directory: str | Path) -> str:
    """Locate the main .tex file in a LaTeX project directory.

    Search order (stops at first match):
    1. 00README.XXX file naming the toplevel (arXiv convention).
    2. Canonical names in order: main.tex, paper.tex, article.tex,
       manuscript.tex — if they contain \\documentclass.
    3. Any .tex file containing \\documentclass, sorted alphabetically
       for determinism across all operating systems.

    Returns file content as a string, or empty string if none found.
    """
    directory = str(directory)

    # 1. arXiv 00README.XXX
    try:
        readme = open(os.path.join(directory, '00README.XXX'), encoding='utf-8').read()
        m = re.search(r'^\s*(.*?)\.tex\s*toplevelfile\s*$', readme, flags=re.MULTILINE)
        if m:
            return open(
                os.path.join(directory, m.group(1) + '.tex'), encoding='utf-8'
            ).read()
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Error reading 00README.XXX in %s: %s", directory, e)

    # 2 & 3. Sort for determinism; prefer canonical names.
    all_tex = sorted(glob.glob('*.tex', root_dir=directory))
    preferred = ['main.tex', 'paper.tex', 'article.tex', 'manuscript.tex']

    # BUG-13: preferred canonical names are trusted root files even when \documentclass
    # lives in an \input'd preamble file (some arXiv papers delegate \documentclass to
    # an \input'd file).  Check preferred names first, unconditionally.  Only fall back
    # to the \documentclass check for non-preferred files (e.g. a standalone chapter.tex).
    for filename in preferred:
        if filename not in all_tex:
            continue
        try:
            return open(os.path.join(directory, filename), encoding='utf-8').read()
        except Exception as e:
            logger.warning("Could not read %s: %s", filename, e)

    # No preferred file found; accept any .tex file that contains \documentclass.
    for filename in sorted(f for f in all_tex if f not in preferred):
        try:
            content = open(os.path.join(directory, filename), encoding='utf-8').read()
            if re.search(r'\\documentclass', content):
                return content
        except Exception as e:
            logger.warning("Could not read %s: %s", filename, e)

    logger.warning("No main .tex file found in %s", directory)
    return ''


def _make_file_replacement(
    directory: str,
    visited: set[str],
    inline_local_packages: bool,
):
    """Return a re.sub replacement callable for resolving file inclusions."""
    def _prefix(match: re.Match, group: str) -> str:
        """Text on the same line before the directive (e.g. 'Some text ' in 'Some text \\input{f}')."""
        return match.group(0)[:match.start(group) - match.start()]

    def replacement(match: re.Match) -> str:
        if match.group('input_bare'):
            # BUG-14: braceless \input <word> (plain-TeX style) — same resolution as \input{word}
            path = match.group('input_bare_path')
            if '.' not in os.path.basename(path):
                path += '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\input: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\input (braceless) not found: %s", full)
                return match.group(0)
            return _prefix(match, 'input_bare') + unfold(os.path.dirname(full), main=content,
                                                          _visited=visited | {full})
        elif match.group('input'):
            path = match.group('input_path')
            if '.' not in os.path.basename(path):
                path += '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\input: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\input not found: %s", full)
                return match.group(0)
            return _prefix(match, 'input') + unfold(os.path.dirname(full), main=content,
                                                     _visited=visited | {full})

        elif match.group('include'):
            path = match.group('include_path') + '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\include: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\include not found: %s", full)
                return match.group(0)
            body = unfold(os.path.dirname(full), main=content,
                          _visited=visited | {full})
            # \include = \input + \clearpage wrapper (creates chapter page breaks)
            return _prefix(match, 'include') + '\n\\clearpage\n' + body + '\n\\clearpage\n'

        elif match.group('import_') or match.group('subimport'):
            # \import{dir}{file}: dir absolute/root-relative; changes search root.
            # \subimport{dir}{file}: dir relative to current file's directory.
            # Docs: https://ctan.org/pkg/import
            if match.group('import_'):
                imp_dir, imp_file = match.group('import_dir'), match.group('import_file')
                grp = 'import_'
            else:
                imp_dir, imp_file = match.group('subimport_dir'), match.group('subimport_file')
                grp = 'subimport'
            if '.' not in os.path.basename(imp_file):
                imp_file += '.tex'
            full_dir = os.path.realpath(os.path.join(directory, imp_dir))
            full     = os.path.realpath(os.path.join(full_dir, imp_file))
            if full in visited:
                logger.warning("Circular \\import: %s — leaving unexpanded", full)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\import not found: %s", full)
                return match.group(0)
            return _prefix(match, grp) + unfold(full_dir, main=content, _visited=visited | {full})

        elif match.group('subfile'):
            # \subfile: sub-document has its own \documentclass preamble.
            # Strip it; keep only \begin{document}...\end{document} body.
            # Docs: https://ctan.org/pkg/subfiles
            path = match.group('subfile_path')
            if '.' not in os.path.basename(path):
                path += '.tex'
            full = os.path.realpath(os.path.join(directory, path))
            if full in visited:
                logger.warning("Circular \\subfile: %s — leaving unexpanded", path)
                return match.group(0)
            try:
                content = open(full, encoding='utf-8').read()
            except FileNotFoundError:
                logger.warning("\\subfile not found: %s", full)
                return match.group(0)
            body_m = re.search(
                r'\\begin\s*\{document\}(.*?)\\end\s*\{document\}',
                content, flags=re.DOTALL,
            )
            if body_m:
                content = body_m.group(1)
            return _prefix(match, 'subfile') + unfold(os.path.dirname(full), main=content,
                                                      _visited=visited | {full})

        elif match.group('usepkg') and inline_local_packages:
            result = ''
            for pkg in re.finditer(r'[a-z0-9\+\-\.]+', match.group('usepkg_path')):
                sty = os.path.join(directory, pkg[0] + '.sty')
                try:
                    sty_content = open(sty, encoding='utf-8').read()
                    result += '\n\\makeatletter\n' + \
                              unfold(directory, main=sty_content, _visited=visited) + \
                              '\n\\makeatother\n'
                except FileNotFoundError:
                    result += r'\usepackage{' + pkg[0] + '}\n'
            return result

        return match.group(0)
    return replacement


def unfold(
    directory: str | Path,
    main: str | None = None,
    inline_local_packages: bool = False,
    _visited: set[str] | None = None,
) -> str:
    """Flatten a multi-file LaTeX project into a single .tex string.

    Resolves \\input, \\include, \\import, \\subimport, and \\subfile
    recursively. Safe against circular includes (second occurrence left
    unexpanded with a warning logged).

    Args:
        directory: Project directory; relative paths resolve here.
        main: Main .tex content. If None, find_main_file() is called.
        inline_local_packages: If True, local .sty files are inlined.
            Off by default — risky for complex packages.
        _visited: Internal only. Do not pass from outside.

    Returns:
        A single flat .tex string with all resolvable includes substituted.
    """
    directory = str(directory)
    if main is None:
        main = find_main_file(directory)
    if _visited is None:
        _visited = set()
    repl = _make_file_replacement(directory, _visited, inline_local_packages)
    return re.sub(_FIND_INPUT, repl, main)
