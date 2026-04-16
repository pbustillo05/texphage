"""Thin CLI wrapper around src/texphage/xy_to_tikzcd.py.

All conversion logic lives in the module.  This script exists only so that
tests written against scripts.xy_to_tikz continue to pass during Phase 2.
After Phase 3 (texphage-convert CLI), this file can be removed.
"""
from texphage.xy_to_tikzcd import convert_xy_body as xy_to_tikzcd  # noqa: F401

__all__ = ['xy_to_tikzcd']
