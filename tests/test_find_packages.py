"""Tests for texphage.find_packages. Mocks subprocess; no TeX needed."""
from unittest.mock import MagicMock, patch

from texphage.find_packages import find_command, find_used_packages, get_dependencies


def _kpsewhich_mock(args, **kw):
    pkg = args[1].replace('.sty', '')
    m = MagicMock()
    m.stdout = f'/tex/{pkg}/{pkg}.sty\n'
    return m


def test_single_package():
    assert 'tikz' in find_used_packages(
        r'\documentclass{article}\usepackage{tikz}\begin{document}\end{document}'
    )


def test_package_with_options():
    pkgs = find_used_packages(r'\usepackage[option]{tikz,pgf}')
    assert 'tikz' in pkgs and 'pgf' in pkgs


def test_tikzlibrary():
    assert any('cd' in p for p in find_used_packages(r'\usetikzlibrary{cd}'))


def test_no_mutable_default_bleed():
    """Consecutive calls must not share state (mutable default bug)."""
    with patch('subprocess.run', side_effect=_kpsewhich_mock):
        with patch('builtins.open', MagicMock(
            return_value=MagicMock(__enter__=lambda s: s,
                                   __exit__=lambda s, *a: False,
                                   read=lambda: '')
        )):
            r1 = get_dependencies('pkg_a')
            r2 = get_dependencies('pkg_b')
    assert 'pkg_b' not in r1
    assert 'pkg_a' not in r2


def test_find_command_preserved():
    """find_command must exist and be callable (preserved from original source)."""
    assert callable(find_command)
