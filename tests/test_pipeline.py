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
    from texphage.pipeline import build_minimal_preamble as _build_minimal_preamble

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


def test_newcommandx_positional_defaults_regression_BUG1():
    """Regression BUG-1: xargs [i=val] positional-key default must not include the 'i=' prefix."""
    # Playground verified: \newcommandx{\greet}[2][1=Hello]{#1, #2!} + \greet{World}
    # → TeX produces "Hello, World!"
    preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
    expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
    assert 'Hello, World!' in expanded
    assert '1=Hello' not in expanded


def test_def_space_before_brace_regression_BUG10():
    """Regression BUG-10: \\def \\R {body} — trailing space in def_pattern must not require literal space."""
    expanded, _, problems = demacro(doc(r'\def \R {{\mathbb R}}', r'$f: X \to \R$.'))
    assert r'\R' not in expanded
    assert not problems


def test_def_delimited_pattern_regression_BUG2():
    """Regression BUG-2: \\def delimited params must use lazy match, not token()."""
    # Playground verified: \def\swap#1and#2{#2 and #1} + \swap Alice and Bob
    # → TeX produces "B and Alice ob" (#2 undelimited → one token B; ob left in stream)
    expanded, _, _ = demacro(doc(r'\def\swap#1and#2{#2 and #1}', r'\swap Alice and Bob'))
    assert 'B and Alice' in expanded
    assert r'\swap' not in expanded


def test_build_minimal_preamble_preserves_front_matter_BUG8():
    """BUG-8: \\title/\\author/\\date in preamble must not be stripped.

    amsart/amsbook put \\title, \\author, \\address, \\email, \\keywords,
    \\subjclass in the preamble (before \\begin{document}). Without them
    \\maketitle fails with "No \\title given."

    After the fix, build_minimal_preamble must include these commands verbatim
    from the raw preamble.

    Ref: BUGS.md BUG-8.
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{amsart}\n"
        "\\usepackage{amsmath}\n"
        "\\title{My Paper}\n"
        "\\author{John Doe}\n"
        "\\address{University}\n"
        "\\email{john@example.com}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    assert r'\title{My Paper}' in minimal
    assert r'\author{John Doe}' in minimal
    assert r'\address{University}' in minimal
    assert r'\email{john@example.com}' in minimal
    # \\usepackage must still be present
    assert r'\usepackage{amsmath}' in minimal
    # macro defs must not leak in
    assert r'\newcommand' not in minimal


def test_build_minimal_preamble_preserves_newtheorem_BUG11():
    """BUG-11: \\newtheorem declarations must not be stripped by build_minimal_preamble.

    build_minimal_preamble only kept \\documentclass, \\usepackage, and front-matter.
    \\newtheorem{thm}{Theorem}[section] was stripped, making \\begin{thm} undefined.

    Ref: BUGS.md BUG-11.
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{amsart}\n"
        "\\usepackage{amsthm}\n"
        "\\newtheorem{thm}{Theorem}[section]\n"
        "\\newtheorem*{lem}{Lemma}\n"
        "\\newcommand{\\foo}{bar}\n"
        "\\begin{document}\n"
        "\\begin{thm}Hello\\end{thm}\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    assert r'\newtheorem{thm}{Theorem}[section]' in minimal
    assert r'\newtheorem*{lem}{Lemma}' in minimal
    # Macro defs must not leak
    assert r'\newcommand' not in minimal


def test_canonical_tex_no_single_giant_line_BUG12():
    """BUG-12: canonical_tex body must not be a single line exceeding TeX's bufsize.

    preprocessing() collapses all whitespace to single spaces.  For large papers
    the expanded body becomes a single line >200k chars, hitting TeX's bufsize limit.
    After the fix, \\par tokens become \\par\\n so line lengths stay manageable.

    Ref: BUGS.md BUG-12.
    """
    from texphage.pipeline import texphage
    import tempfile, os

    # Build a synthetic 'paper' with enough paragraphs that the collapsed body
    # exceeds 10k chars (300 * ~40 chars each = ~12k) — enough to detect the bug.
    body_lines = '\n\n'.join(f'Paragraph number {i} with some filler content here.' for i in range(300))
    raw_tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        + body_lines + "\n"
        "\\end{document}"
    )
    with tempfile.TemporaryDirectory() as tmp:
        main = os.path.join(tmp, 'main.tex')
        with open(main, 'w') as f:
            f.write(raw_tex)
        canonical_tex, _ = texphage(tmp)  # auto-detect main.tex

    # The body section must not be a single line.
    body_start = canonical_tex.find(r'\begin{document}')
    body_end   = canonical_tex.find(r'\end{document}')
    body = canonical_tex[body_start:body_end]
    lines = body.splitlines()
    max_len = max(len(l) for l in lines)
    assert max_len < 10_000, (
        f"Body has a line of {max_len} chars — bufsize overflow risk"
    )


def test_build_minimal_preamble_article_no_title_in_preamble_BUG8():
    """For plain article, \\title in the body is untouched by build_minimal_preamble."""
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{amsmath}\n"
        "\\newcommand{\\foo}{bar}\n"
        "\\begin{document}\n"
        "\\title{My Paper}\\maketitle content\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)
    # No \\title in preamble for article class — must not hallucinate one
    assert r'\newcommand' not in minimal
    assert r'\documentclass{article}' in minimal


def test_run_pipeline_raw_mode_applies_par_newline_BUG15():
    """BUG-15: _run_pipeline raw mode must apply the BUG-12 \\par line-break fix.

    _run_pipeline() in test_fidelity.py bypasses texphage() and builds
    canonical_tex directly from demacro() output. Without applying the
    \\par -> \\par\\n fix, the body is a single giant line that overflows
    TeX's bufsize on large papers.

    Playground verified: demacro() collapses paragraphs to '\\par ' without
    newlines; pipeline.texphage() fixes this but _run_pipeline() did not.
    """
    import tempfile

    from test_fidelity import _run_pipeline

    body_lines = '\n\n'.join(
        f'Paragraph number {i} with some filler content here.'
        for i in range(50)
    )
    raw_tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        + body_lines + "\n"
        "\\end{document}"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        raw_dir = tmp_path / 'raw'
        raw_dir.mkdir()
        (raw_dir / 'main.tex').write_text(raw_tex)
        run_dir = tmp_path / 'run'
        run_dir.mkdir()

        _run_pipeline(raw_dir, run_dir, mode='raw')

        output_tex = (run_dir / 'pipeline_output.tex').read_text()

    # Positive: \\par must be followed by newline, not just a space
    assert '\\par\n' in output_tex, (
        "BUG-15: _run_pipeline raw mode does not apply \\par -> \\par\\n fix"
    )
    # Negative: no line in the body should be excessively long
    body_start = output_tex.find('\\begin{document}')
    body_end = output_tex.find('\\end{document}')
    body = output_tex[body_start:body_end]
    lines = body.splitlines()
    max_len = max(len(l) for l in lines)
    assert max_len < 10_000, (
        f"Body has a line of {max_len} chars — bufsize overflow risk"
    )


# ---------------------------------------------------------------------------
# BUG-16 regression: \par inside math display environments
# ---------------------------------------------------------------------------

def test_par_stripped_inside_gather_BUG16():
    r"""BUG-16: \par inside \begin{gather}...\end{gather} must be removed.

    Playground verified:
      \begin{gather} A \to B \par C \to D \end{gather} -> compile error
      \begin{gather} A \to B \\ C \to D \end{gather} -> compiles OK
    compile_snippet(preamble=r'\usepackage{amsmath}',
                    body=r'\begin{gather} A \to B \\ C \to D \end{gather}').ok == True
    """
    from texphage.demacro import preprocessing

    raw = (
        "\\documentclass{article}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "\\begin{gather}\n"
        "A \\to B\n"
        "\n"
        "C \\to D\n"
        "\\end{gather}\n"
        "\\end{document}"
    )
    _preamble, body, _pkgs = preprocessing(raw)
    # Positive: the math content must survive
    assert '\\begin{gather}' in body
    assert 'A \\to B' in body
    assert 'C \\to D' in body
    # Negative: \par must NOT appear inside the gather environment
    # (it would cause "Paragraph ended before \gather was complete")
    gather_start = body.index('\\begin{gather}')
    gather_end = body.index('\\end{gather}')
    gather_content = body[gather_start:gather_end]
    assert '\\par' not in gather_content, (
        f"BUG-16: \\par survived inside gather: {gather_content!r}"
    )


def test_par_stripped_inside_align_BUG16():
    r"""BUG-16: \par inside \begin{align}...\end{align} must be removed."""
    from texphage.demacro import preprocessing

    raw = (
        "\\documentclass{article}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "\\begin{align}\n"
        "x &= 1\n"
        "\n"
        "y &= 2\n"
        "\\end{align}\n"
        "\\end{document}"
    )
    _preamble, body, _pkgs = preprocessing(raw)
    align_start = body.index('\\begin{align}')
    align_end = body.index('\\end{align}')
    align_content = body[align_start:align_end]
    assert '\\par' not in align_content, (
        f"BUG-16: \\par survived inside align: {align_content!r}"
    )


def test_par_preserved_outside_math_env_BUG16():
    r"""BUG-16: \par at top level (between paragraphs) must survive."""
    from texphage.demacro import preprocessing

    raw = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "First paragraph.\n"
        "\n"
        "Second paragraph.\n"
        "\\end{document}"
    )
    _preamble, body, _pkgs = preprocessing(raw)
    assert '\\par' in body, (
        "Top-level \\par between paragraphs must be preserved"
    )
