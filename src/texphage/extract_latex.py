"""Stub: extract specific LaTeX environments from a flat .tex string.
Not yet implemented. Tracked in BUGS.md."""
from __future__ import annotations


def find_tikzcd(tex: str) -> list[str]:
    """Extract all tikzcd environments from a flat LaTeX string.

    Args:
        tex: A flat (unfolded, optionally demacroed) LaTeX string.
    Returns:
        List of tikzcd environment body strings.
    Raises:
        NotImplementedError: Always. Not yet implemented.
    """
    raise NotImplementedError(
        "find_tikzcd is not yet implemented. "
        "See extract_latex.py for the planned interface."
    )
