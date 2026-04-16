"""Tests for texphage.formatter.pretty_print.

All tests use use_latexindent=False (pure Python path) and
semantic_linebreaks=False (default) unless stated otherwise.
No TeX installation required.
"""
from __future__ import annotations

import pytest

from texphage.formatter import pretty_print


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body(tex: str) -> str:
    """Wrap a body snippet in a minimal document and return the formatted body."""
    full = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        + tex
        + "\n\\end{document}\n"
    )
    result = pretty_print(full)
    # Extract body between \begin{document} and \end{document}
    start = result.index("\\begin{document}") + len("\\begin{document}")
    end = result.index("\\end{document}")
    return result[start:end].strip()


# ---------------------------------------------------------------------------
# \par → blank line
# ---------------------------------------------------------------------------

def test_par_becomes_blank_line() -> None:
    out = _body(r"First paragraph.\par Second paragraph.")
    assert "\n\n" in out
    assert r"\par" not in out


def test_par_with_space_becomes_blank_line() -> None:
    out = _body(r"First.\par  Second.")
    assert "\n\n" in out
    assert r"\par" not in out


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------

def test_begin_on_own_line() -> None:
    out = _body(r"Text before \begin{align*} x = 1 \end{align*} text after.")
    lines = out.splitlines()
    begin_lines = [l for l in lines if "\\begin{align*}" in l]
    assert len(begin_lines) == 1
    assert begin_lines[0].strip() == "\\begin{align*}"


def test_end_on_own_line() -> None:
    out = _body(r"Text \begin{align*} x = 1 \end{align*} after.")
    lines = out.splitlines()
    end_lines = [l for l in lines if "\\end{align*}" in l]
    assert len(end_lines) == 1
    assert end_lines[0].strip().startswith("\\end{align*}")


def test_env_contents_indented() -> None:
    out = _body(r"\begin{align*} x = 1 \end{align*}")
    lines = out.splitlines()
    content_lines = [l for l in lines if "x = 1" in l]
    assert content_lines, "Content line not found"
    assert content_lines[0].startswith("  "), "Content should be indented 2 spaces"


def test_env_contents_indented_custom_indent() -> None:
    tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\begin{align*} x = 1 \\end{align*}\n"
        "\\end{document}\n"
    )
    result = pretty_print(tex, indent="    ")
    lines = result.splitlines()
    content_lines = [l for l in lines if "x = 1" in l]
    assert content_lines[0].startswith("    "), "Custom 4-space indent not applied"


def test_prose_after_end_stays_on_same_line() -> None:
    """Text immediately following \\end{env} stays on same line."""
    out = _body(r"Then \begin{align*} x=1 \end{align*} follows.")
    lines = out.splitlines()
    end_lines = [l for l in lines if "\\end{align*}" in l]
    assert len(end_lines) == 1
    assert "follows." in end_lines[0], (
        "Prose after \\end{align*} should stay on same line; "
        f"got: {end_lines[0]!r}"
    )


def test_inline_envs_not_isolated() -> None:
    """minipage, mbox, etc. should NOT be placed on their own lines."""
    out = _body(r"Foo \begin{minipage}{0.5\textwidth} bar \end{minipage} baz.")
    # All on one line (no newline around minipage)
    assert "\\begin{minipage}" not in "\n".join(
        l for l in out.splitlines() if l.strip() == "\\begin{minipage}{0.5\\textwidth}"
    ), "minipage should not be isolated on its own line"


# ---------------------------------------------------------------------------
# Adjacent / nested environments
# ---------------------------------------------------------------------------

def test_display_math_with_nested_env() -> None:
    r"""\\[\begin{tikzcd}...\end{tikzcd}\\] — no newline between \[ and \begin."""
    out = _body(r"\[ \begin{tikzcd} A \ar[r] & B \end{tikzcd} \]")
    lines = out.splitlines()
    open_lines = [l for l in lines if "\\[" in l]
    assert len(open_lines) == 1, f"Expected 1 line with \\[, got: {open_lines}"
    assert "\\begin{tikzcd}" in open_lines[0], (
        r"\[ and \begin{tikzcd} should be on the same line; "
        f"got: {open_lines[0]!r}"
    )


def test_display_math_close_merged_with_end() -> None:
    r"""\\end{tikzcd}\\] should be on same line."""
    out = _body(r"\[ \begin{tikzcd} A \ar[r] & B \end{tikzcd} \]")
    lines = out.splitlines()
    close_lines = [l for l in lines if "\\]" in l]
    assert len(close_lines) == 1, f"Expected 1 line with \\], got: {close_lines}"
    assert "\\end{tikzcd}" in close_lines[0], (
        r"\end{tikzcd} and \] should be on the same line; "
        f"got: {close_lines[0]!r}"
    )


def test_adjacent_begins_merged() -> None:
    r"""\\begin{outer}\\begin{inner} on same line — no newline between."""
    out = _body(r"X \begin{figure} \begin{center} img \end{center} \end{figure} Y")
    lines = out.splitlines()
    open_lines = [l for l in lines if "\\begin{figure}" in l]
    assert len(open_lines) == 1
    assert "\\begin{center}" in open_lines[0], (
        r"\begin{figure} and \begin{center} should be on the same line"
    )


def test_adjacent_ends_merged() -> None:
    r"""\\end{inner}\\end{outer} on same line — no newline between."""
    out = _body(r"X \begin{figure} \begin{center} img \end{center} \end{figure} Y")
    lines = out.splitlines()
    close_lines = [l for l in lines if "\\end{figure}" in l]
    assert len(close_lines) == 1
    assert "\\end{center}" in close_lines[0], (
        r"\end{center} and \end{figure} should be on the same line"
    )


# ---------------------------------------------------------------------------
# \item isolation
# ---------------------------------------------------------------------------

def test_item_on_own_line() -> None:
    out = _body(r"\begin{itemize} \item First \item Second \end{itemize}")
    lines = out.splitlines()
    item_lines = [l for l in lines if "\\item" in l]
    assert len(item_lines) == 2, f"Expected 2 \\item lines, got: {item_lines}"
    for l in item_lines:
        assert l.strip().startswith("\\item")


# ---------------------------------------------------------------------------
# \label stays on same line as anchor
# ---------------------------------------------------------------------------

def test_label_stays_on_same_line_as_end() -> None:
    r"""\\label must NOT be on a separate line after \\end{env}."""
    out = _body(r"\begin{align*} f(x) = x^2 \end{align*}\label{eq:main}")
    lines = out.splitlines()
    label_lines = [l for l in lines if "\\label{eq:main}" in l]
    assert len(label_lines) == 1
    end_lines = [l for l in lines if "\\end{align*}" in l]
    assert len(end_lines) == 1
    assert end_lines[0] == label_lines[0], (
        r"\label should be on the same line as \end{align*}; "
        f"got end line: {end_lines[0]!r}, label line: {label_lines[0]!r}"
    )


def test_label_not_separated_by_blank_line() -> None:
    out = _body(r"\begin{align*} f(x) = x \end{align*}\label{eq:1}")
    # No blank line immediately before \label
    label_idx = None
    lines = out.splitlines()
    for i, l in enumerate(lines):
        if "\\label{eq:1}" in l:
            label_idx = i
            break
    assert label_idx is not None
    if label_idx > 0:
        assert lines[label_idx - 1].strip() != "", "Blank line before \\label is not allowed"


# ---------------------------------------------------------------------------
# Multiple blank lines collapsed
# ---------------------------------------------------------------------------

def test_multiple_blank_lines_collapsed() -> None:
    out = _body("A.\n\n\n\n\nB.")
    assert "\n\n\n" not in out, "3+ consecutive blank lines should be collapsed to 2"


def test_three_blank_lines_become_two() -> None:
    out = _body("A.\n\n\nB.")
    assert out.count("\n\n") >= 1
    assert "\n\n\n" not in out


# ---------------------------------------------------------------------------
# Preamble untouched
# ---------------------------------------------------------------------------

def test_preamble_unchanged() -> None:
    preamble = "\\documentclass{article}\n\\usepackage{amsmath}\n"
    tex = preamble + "\\begin{document}\nHello.\n\\end{document}\n"
    result = pretty_print(tex)
    assert result.startswith(preamble), "Preamble should be left untouched"


# ---------------------------------------------------------------------------
# No \\begin{document} / \\end{document} — treat as body
# ---------------------------------------------------------------------------

def test_no_document_env_treated_as_body() -> None:
    tex = r"\begin{align*} x = 1 \end{align*}"
    result = pretty_print(tex)
    assert "\\begin{align*}" in result
    # Should not crash


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotent() -> None:
    """pretty_print applied twice gives same result as once."""
    tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "We prove $f$ is continuous.\\par Let $\\epsilon > 0$. Then "
        "\\begin{align*} \\lim_{n} a_n = L \\end{align*} follows.\\par "
        "The next result shows.\n"
        "\\end{document}\n"
    )
    once = pretty_print(tex)
    twice = pretty_print(once)
    assert once == twice, "pretty_print should be idempotent"


# ---------------------------------------------------------------------------
# --semantic-linebreaks (opt-in)
# ---------------------------------------------------------------------------

def test_semantic_linebreaks_splits_sentences() -> None:
    """Three clear sentences become three lines."""
    result = pretty_print(
        "\\documentclass{article}\n\\begin{document}\n"
        "We prove that $f$ is continuous. "
        "Let $\\epsilon > 0$. "
        "Then $f(x) > 0$.\n"
        "\\end{document}\n",
        semantic_linebreaks=True,
    )
    # Extract body
    start = result.index("\\begin{document}") + len("\\begin{document}")
    end = result.index("\\end{document}")
    body = result[start:end].strip()
    prose_lines = [l for l in body.splitlines() if l.strip() and not l.strip().startswith("\\")]
    assert len(prose_lines) >= 3, (
        f"Expected at least 3 sentence lines, got {len(prose_lines)}: {prose_lines}"
    )


def test_semantic_linebreaks_no_break_after_abbrev() -> None:
    """'Thm. 1 shows...' must NOT get a line break after 'Thm.'"""
    result = pretty_print(
        "\\documentclass{article}\n\\begin{document}\n"
        "Thm. 1 shows that $f$ is continuous.\n"
        "\\end{document}\n",
        semantic_linebreaks=True,
    )
    lines = result.splitlines()
    thm_lines = [l for l in lines if "Thm." in l]
    assert thm_lines, "Line with Thm. not found"
    assert "shows" in thm_lines[0], (
        "Line break after 'Thm.' is wrong; got: " + repr(thm_lines[0])
    )


def test_semantic_linebreaks_no_break_in_inline_math() -> None:
    """No sentence break should be inserted inside $...$"""
    result = pretty_print(
        "\\documentclass{article}\n\\begin{document}\n"
        "We have $a.b.$ and more text. Next sentence.\n"
        "\\end{document}\n",
        semantic_linebreaks=True,
    )
    # $a.b.$ should not be split
    assert "$a.b.$" in result or "a.b." in result.replace("\n", " ")
