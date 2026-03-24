# This will read a latex file and recursively find all of its package dependencies.
# It also slowly build up a file that encodes the tree structure of latex packages dependencies, and a file that stores filepaths for these packages.
# The goal is that this creates a "minimal" list of packages to load to compile some document.
from __future__ import annotations

import argparse
import atexit
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import regex as re
from filelock import FileLock

from texphage._regex import (
    embed_braces,
)

logger = logging.getLogger(__name__)

# MATCHES: individual package/library name tokens inside a comma-separated list
# CAPTURES: the full match is one package name, e.g. "amsmath" or "defs_pp1"
# LIMITATIONS:
#   [observed] CTAN packages do not use underscores, but arXiv bundled .sty
#              files routinely do (e.g. defs_pp1.sty). Underscore is required.
find_file = re.compile(r'[a-z0-9\+\-\._]+')

# MATCHES: \usepackage[opts]{pkg1,pkg2}, \RequirePackage[opts]{pkg},
#          \usetikzlibrary{lib1,lib2}, \usepgflibrary{lib}
# CAPTURES:
#   (group 1)  → "usepackage" or "RequirePackage"
#   options    → optional [...] argument (via embed_braces)
#   packages   → comma-separated package names
#   type       → "tikz" or "pgf" (for library calls)
#   libraries  → comma-separated library names
# LIMITATIONS:
#   [observed] Underscore in package names is needed for bundled .sty files
#              (BUG-21: defs_pp1.sty, my_defs.sty).
#   [inferred] Does not match \usepackage with @ in name (rare).
find_pkg_lib = re.compile(
    r'^[^%%\n]*(?:\\(usepackage|RequirePackage)\s*%s\s*\{(?<packages>(?:[a-z0-9\+\-\._]+| |,)+)\}'
    r'|\\use(?<type>tikz|pgf)library\s*\{(?<libraries>(?:[a-z0-9\+\-\._]+| |,)+)\})' % embed_braces('options'),
    flags=re.MULTILINE,
)

# ---------------------------------------------------------------------------
# PackageCall — structured representation of one \usepackage call
# ---------------------------------------------------------------------------

@dataclass
class PackageCall:
    """One \\usepackage (or \\usetikzlibrary / \\usepgflibrary) call from a preamble.

    Attributes:
        names:      Package or library names, e.g. ``['amsmath']`` or
                    ``['amsmath', 'amsthm']`` for a comma-list call.
        options:    Options string *without* surrounding brackets, e.g. ``'utf8'``.
                    Empty string when no options were given.
        is_tikzlib: True for ``\\usetikzlibrary`` / ``\\usepgflibrary`` calls.
        lib_type:   ``'tikz'`` or ``'pgf'`` for library calls; ``''`` for packages.
    """
    names: list[str]
    options: str
    is_tikzlib: bool = False
    lib_type: str = ''

    @property
    def verbatim(self) -> str:
        """Reconstruct a canonical \\usepackage or \\usetikzlibrary call string."""
        if self.is_tikzlib:
            return r'\use%slibrary{%s}' % (self.lib_type, ','.join(self.names))
        opts = ('[%s]' % self.options) if self.options else ''
        return r'\usepackage%s{%s}' % (opts, ','.join(self.names))


def find_explicit_package_calls(preamble: str) -> list[PackageCall]:
    """Return structured :class:`PackageCall` objects for every ``\\usepackage``
    and ``\\usetikzlibrary`` found in *preamble*, in document order.

    Only the author's *explicit* calls are returned — transitive dependencies are
    **not** expanded.  Options and multi-package comma-lists are preserved.

    Args:
        preamble: The raw LaTeX preamble string (text before ``\\begin{document}``).

    Returns:
        A list of :class:`PackageCall` objects, one per ``\\usepackage`` /
        ``\\usetikzlibrary`` line, in the order they appear in *preamble*.
    """
    result: list[PackageCall] = []
    for match in find_pkg_lib.finditer(preamble):
        opts_raw = match.group('options')          # e.g. '[utf8]' or None
        options  = opts_raw[1:-1] if opts_raw else ''  # strip surrounding []

        if match.group('packages'):
            names = [m.group(0) for m in find_file.finditer(match.group('packages'))]
            if names:
                result.append(PackageCall(names=names, options=options))
        elif match.group('libraries'):
            lib_type = match.group('type')         # 'tikz' or 'pgf'
            names = [m.group(0) for m in find_file.finditer(match.group('libraries'))]
            if names:
                result.append(PackageCall(names=names, options=options,
                                          is_tikzlib=True, lib_type=lib_type))
    return result


# ---------------------------------------------------------------------------
# Cache — JSON files under cache/, protected by file locks for concurrent safety
# ---------------------------------------------------------------------------

_CACHE_DIR  = Path(__file__).parent.parent.parent / 'cache'
_DEP_FILE   = _CACHE_DIR / 'texlive_dependencies.json'
_PATH_FILE  = _CACHE_DIR / 'texlive_path.json'
_DEP_LOCK   = _CACHE_DIR / 'texlive_dependencies.lock'
_PATH_LOCK  = _CACHE_DIR / 'texlive_path.lock'


def _load_json(path: Path, lock: Path) -> dict:
    """Read a JSON cache file under a file lock. Returns {} if missing/corrupt."""
    with FileLock(str(lock), timeout=10):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def save_cache() -> None:
    """Write in-memory caches to disk under file locks.

    Uses FileLock so concurrent processes cannot corrupt each other's writes.
    Registered with atexit (fires on clean exit when used as a library) and
    called explicitly at the end of main() when used as a CLI tool.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with FileLock(str(_DEP_LOCK), timeout=10):
        _DEP_FILE.write_text(json.dumps(texlive_dependencies, indent=2), encoding='utf-8')
    with FileLock(str(_PATH_LOCK), timeout=10):
        _PATH_FILE.write_text(json.dumps(texlive_path, indent=2), encoding='utf-8')


_CACHE_DIR.mkdir(parents=True, exist_ok=True)
texlive_dependencies: dict = _load_json(_DEP_FILE, _DEP_LOCK)
texlive_path: dict         = _load_json(_PATH_FILE, _PATH_LOCK)

atexit.register(save_cache)

## This ones doesn't work (weird encoding) so you need to manually add it the first time
# texlive_dependencies['contour'] = ['contour', 'color', 'trig']

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_path(file: str) -> str:
    if file in texlive_path:
        return texlive_path[file]
    else:
        logger.debug("get_path: Getting location for %s", file)
        if re.search(':', file):
            filename = re.sub(':', '', file) + '.code.tex'
        else:
            filename = file + '.sty'
        result = subprocess.run(['kpsewhich', filename], capture_output=True, text=True)
        path = result.stdout.strip()
        if path == '' and re.match('tikz', filename):
            filename = 'pgf' + filename[4:]
            result = subprocess.run(['kpsewhich', filename], capture_output=True, text=True)
            path = result.stdout.strip()
        texlive_path[file] = path
        return path


def get_dependencies(file: str, dependencies: list | None = None) -> list:
    if dependencies is None:
        dependencies = []
    if file in texlive_dependencies:
        return texlive_dependencies[file]
    else:
        logger.debug("get_dependencies: Getting dependencies for %s", file)
        root = (dependencies == [])
        dependencies.append(file)
        try:
            path = get_path(file)
            code = open(path).read()
        except FileNotFoundError:
            logger.error("Couldn't find the package or library %s at %s", file, path)
            return [file]
        except UnicodeDecodeError:
            logger.error("Couldn't decode the package or library %s at %s", file, path)
            return [file]
        else:
            for match in find_pkg_lib.finditer(code):
                for package in find_file.finditer(match.group('packages') or ''):
                    if package[0] not in dependencies:
                        dependencies = get_dependencies(package[0], dependencies)
                for library in find_file.finditer(match.group('libraries') or ''):
                    if library[0] not in dependencies:
                        dependencies = get_dependencies(
                            match.group('type') + 'library:' + library[0], dependencies
                        )
            if root:
                texlive_dependencies[file] = dependencies
            return dependencies

## TODO: Modify `find_used_packages` to also return options passed to packages and libraries, so that we can later use the same options in our minimalist preamble.
def find_used_packages(tex: str) -> list:
    """Return all packages (and transitive dependencies) used in a LaTeX string."""
    list_packages = []
    for match in find_pkg_lib.finditer(tex):
        for package in find_file.finditer(match.group('packages') or ''):
            if package[0] not in list_packages:
                list_packages += [
                    i for i in get_dependencies(package[0])
                    if i not in list_packages
                ]
        for library in find_file.finditer(match.group('libraries') or ''):
            if library[0] not in list_packages:
                list_packages += [
                    i for i in get_dependencies(
                        match.group('type') + 'library:' + library[0]
                    )
                    if i not in list_packages
                ]
    return list_packages


def find_command(csname: str, list_packages: list[str]) -> str:
    """Find which package in list_packages defines the command \\csname.

    Searches packages in reverse order (last loaded = highest priority in LaTeX).
    Returns the package name, or empty string if not found.

    Args:
        csname: Command name without backslash, e.g. "tikzcd".
        list_packages: List of package names to search, in load order.

    Returns:
        The name of the package that defines \\csname, or '' if not found.
    """
    if re.search(r'[a-zA-Z]', csname):
        pattern_csname = r'(?:\{\s*\\%s\s*\}|\\%s[^a-zA-Z])' % (csname, csname)
    elif len(csname) == 1:
        pattern_csname = r'(?:\{\s*\\%s\s*\}|\\%s)' % (csname, csname)
    else:
        raise Exception(
            'Incorrect Latex Command Format: the command must be either composed of letters only '
            '(as in [a-zA-Z]+) or of a single non-letter character (as in [^a-zA-Z])'
        )
    pattern_env = r'''\\
        (
            (re)?newenvironmentx?    |
            (Declare|New|Renew|Provide)DocumentEnvironment  |
            NewEnviron    |
            newenviron
        )
        \s* \*? \s*
        %s
        ''' % pattern_csname
    pattern_cmd = r'''\\
        (
            (e|x|g)?def    |
            let     |
            ((re)?new|provide)commandx?     |
            (DeclareRobust|Check)Commandx?    |
            (New|Renew|Provide|Declare)(Expandable)?DocumentCommand
        )
        \s* \*? \s*
        %s
        ''' % pattern_csname
    pattern = re.compile(re.sub(r'\s+', '', pattern_env + '|' + pattern_cmd))
    for package in reversed(list_packages):
        logger.debug('find_command: Searching for \\%s in %s', csname, package)
        try:
            path = get_path(package)
            code = open(path).read()
            if pattern.search(code):
                return package
        except FileNotFoundError:
            logger.error("Couldn't find the package %s at %s", package, path)
        except UnicodeDecodeError:
            logger.error("Couldn't decode package %s at %s", package, path)
    logger.warning("Couldn't find command \\%s in the provided list of packages", csname)
    return ''


__all__ = [
    "PackageCall",
    "find_explicit_package_calls",
    "find_used_packages",
    "get_dependencies",
    "find_command",
    "save_cache",
]


def main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.DEBUG)
    tex = open(args.texfile).read()
    print('\nKnown Dependencies:')
    print(texlive_dependencies)
    print('\nKnown Paths:')
    print(texlive_path)
    if args.mode == 'tex':
        print(find_used_packages(tex))
    elif args.mode == 'cs':
        if args.cs:
            list_packages = find_used_packages(tex)
            print(list_packages)
            print(find_command(args.cs, list_packages))
        else:
            print("The argument '-c STRING' (where STRING is a latex command to find) is necessary for the 'cs' mode")
    save_cache()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find LaTeX packages')
    parser.add_argument('-m', '--mode', required=True, choices=['tex', 'cs'],
                        help='Two different operating modes: \n \
                                tex:  find all packages and tikz libraries called in a tex document\n \
                                cs:  finds in which package a specific command is defined within a document')
    parser.add_argument('-i', '--texfile', type=str, required=True, help='LateX source code file location')
    parser.add_argument('-c', '--cs', type=str, help='Command to find definition of in cs mode')
    main(parser.parse_args())
