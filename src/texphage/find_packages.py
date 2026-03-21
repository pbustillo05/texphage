# This will read a latex file and recursively find all of its package dependencies.
# It also slowly build up a file that encodes the tree structure of latex packages dependencies, and a file that stores filepaths for these packages.
# The goal is that this creates a "minimal" list of packages to load to compile some document.
from __future__ import annotations

import argparse
import atexit
import json
import logging
import subprocess
from pathlib import Path

import regex as re
from filelock import FileLock

from texphage._regex import (
    embed_brackets, embed_braces, token, not_tokenizer_char,
    num_args, find_com, find_env, xparse,
)

logger = logging.getLogger(__name__)

find_file = re.compile(r'[a-z0-9\+\-\.]+')
find_pkg_lib = re.compile(
    r'^[^%%\n]*(?:\\(usepackage|RequirePackage)\s*%s\s*\{(?<packages>(?:[a-z0-9\+\-\.]+| |,)+)\}'
    r'|\\use(?<type>tikz|pgf)library\s*\{(?<libraries>(?:[a-z0-9\+\-\.]+| |,)+)\})' % embed_braces('options'),
    flags=re.MULTILINE,
)

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

def get_path(file: str, tracker: bool = False) -> str:
    if file in texlive_path:
        return texlive_path[file]
    else:
        if tracker:
            print("get_path: Getting location for " + file)
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


def get_dependencies(file: str, dependencies: list | None = None, tracker: bool = False) -> list:
    if dependencies is None:
        dependencies = []
    if file in texlive_dependencies:
        return texlive_dependencies[file]
    else:
        if tracker:
            print("get_dependencies: Getting dependencies for " + file)
        root = (dependencies == [])
        dependencies.append(file)
        try:
            path = get_path(file, tracker=tracker)
            code = open(path, 'r').read()
        except FileNotFoundError:
            print("FileNotFoundError: Couldn't find the package or library " + file + " at " + path)
            return [file]
        except UnicodeDecodeError:
            print("UnicodeDecodeError: Couldn't decode the package or library " + file + " at " + path)
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


def find_used_packages(tex: str, tracker: bool = False) -> list:
    list_packages = []
    for match in find_pkg_lib.finditer(tex):
        for package in find_file.finditer(match.group('packages') or ''):
            if package[0] not in list_packages:
                list_packages += [
                    i for i in get_dependencies(package[0], tracker=tracker)
                    if i not in list_packages
                ]
        for library in find_file.finditer(match.group('libraries') or ''):
            if library[0] not in list_packages:
                list_packages += [
                    i for i in get_dependencies(
                        match.group('type') + 'library:' + library[0], tracker=tracker
                    )
                    if i not in list_packages
                ]
    return list_packages


def find_command(csname: str, list_packages: list[str], tracker: bool = False) -> str:
    """Find which package in list_packages defines the command \\csname.

    Searches packages in reverse order (last loaded = highest priority in LaTeX).
    Returns the package name, or empty string if not found.

    Args:
        csname: Command name without backslash, e.g. "tikzcd".
        list_packages: List of package names to search, in load order.
        tracker: If True, log each package being searched at DEBUG level.

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
        if tracker:
            print('find_command: Searching for the command %s in %s' % (csname, package))
        try:
            path = get_path(package, tracker=tracker)
            code = open(path, 'r').read()
            if pattern.search(code):
                return package
        except FileNotFoundError:
            print("FileNotFoundError: Couldn't find the package " + package + " at " + path)
        except UnicodeDecodeError:
            print("UnicodeDecodeError: Couldn't decode package " + package + " at " + path)
    print(r"Couldn't find command %s in the provided list of packages" % csname)
    return ''


__all__ = [
    "find_used_packages",
    "get_dependencies",
    "find_command",
    "save_cache",
]


def main(args: argparse.Namespace) -> None:
    tex = open(args.texfile, 'r').read()
    print('\nKnown Dependencies:')
    print(texlive_dependencies)
    print('\nKnown Paths:')
    print(texlive_path)
    if args.mode == 'tex':
        print(find_used_packages(tex, tracker=True))
    elif args.mode == 'cs':
        if args.cs:
            list_packages = find_used_packages(tex, tracker=True)
            print(list_packages)
            print(find_command(args.cs, list_packages, tracker=True))
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
