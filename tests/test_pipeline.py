"""End-to-end pipeline regression tests.

When a bug in BUGS.md is fixed, its reproduction test moves here from
test_demacro.py (xfail marker removed). These tests are permanent regressions
that must never fail again.

Tests here use only hand-crafted fixture strings — no arXiv downloads.
"""
import sys
from pathlib import Path

import pytest

from texphage.demacro import demacro

# Allow importing helpers from scripts/ without making it a package.
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def doc(preamble: str, body: str) -> str:
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")


# ---------------------------------------------------------------------------
# BUG-3 regression: minimal preamble reconstruction
# ---------------------------------------------------------------------------

def test_build_minimal_preamble_BUG3():
    """BUG-3: pipeline must emit \\documentclass + \\usepackage only, no macro defs."""
    from test_fidelity import _build_minimal_preamble

    raw_tex = doc(
        r'\usepackage{amsmath}' + '\n'
        r'\usepackage[utf8]{inputenc}' + '\n'
        r'\newcommand{\foo}{bar}',
        r'\foo',
    )
    minimal = _build_minimal_preamble(raw_tex)

    assert r'\documentclass{article}' in minimal
    assert r'\usepackage{amsmath}' in minimal
    assert r'\usepackage[utf8]{inputenc}' in minimal
    # Macro definitions must NOT appear in the minimal preamble.
    assert r'\newcommand' not in minimal


def test_pipeline_output_has_expanded_body_BUG3():
    """BUG-3 regression: demacro() body must have macros expanded (not just copied)."""
    raw_tex = doc(r'\newcommand{\foo}{bar}', r'\foo')
    expanded, _, _ = demacro(raw_tex)
    assert 'bar' in expanded
    assert r'\foo' not in expanded


# Add fixed-bug regression tests here when bugs are closed.
# Example (add when BUG-N is fixed):
#
# def test_newcommandx_regression_BUG_N():
#     """Regression: xargs positional default was not expanded. Fixed in BUG-N."""
#     preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
#     expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
#     assert 'Hello' in expanded and 'World' in expanded
