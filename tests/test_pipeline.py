"""End-to-end pipeline regression tests.

When a bug in BUGS.md is fixed, its reproduction test moves here from
test_demacro.py (xfail marker removed). These tests are permanent regressions
that must never fail again.

Tests here use only hand-crafted fixture strings — no arXiv downloads.
"""
import pytest

from texphage.demacro import demacro


def doc(preamble: str, body: str) -> str:
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")


# Add fixed-bug regression tests here when bugs are closed.
# Example (add when BUG-N is fixed):
#
# def test_newcommandx_regression_BUG_N():
#     """Regression: xargs positional default was not expanded. Fixed in BUG-N."""
#     preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
#     expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
#     assert 'Hello' in expanded and 'World' in expanded
