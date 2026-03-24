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


# ---------------------------------------------------------------------------
# BUG-17 regression: duplicate \newtheorem deduplication
# ---------------------------------------------------------------------------

def test_build_minimal_preamble_deduplicates_newtheorem_BUG17():
    r"""BUG-17: duplicate \newtheorem declarations must be deduplicated.

    Playground verified:
      \usepackage{amsthm} + \newtheorem{remark}{Remark}[section] (single)
      + \begin{remark}Test remark.\end{remark}
      -> "Remark 0.1. Test remark."
    compile_snippet(preamble=..., body=...).pdf_text contains 'Remark 0.1. Test remark.'

    Duplicate \newtheorem{remark}{Remark}[section] causes:
      "! LaTeX Error: Command \remark already defined."
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{amsthm}\n"
        "\\newtheorem{remark}{Remark}[section]\n"
        "\\newtheorem{remark}{Remark}[section]\n"
        "\\newtheorem{thm}{Theorem}\n"
        "\\begin{document}\n"
        "\\begin{remark}Test\\end{remark}\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: \newtheorem{remark} must appear exactly once
    assert minimal.count(r'\newtheorem{remark}') == 1, (
        f"BUG-17: \\newtheorem{{remark}} appears {minimal.count(chr(92) + 'newtheorem{remark}')} times"
    )
    # Positive: \newtheorem{thm} must still be present (non-duplicate)
    assert r'\newtheorem{thm}{Theorem}' in minimal
    # Positive: full declaration preserved
    assert r'\newtheorem{remark}{Remark}[section]' in minimal


# ---------------------------------------------------------------------------
# BUG-18 regression: version package \excludeversion / \includeversion
# ---------------------------------------------------------------------------

def test_build_minimal_preamble_preserves_excludeversion_BUG18():
    r"""BUG-18: \excludeversion{name} and \includeversion{name} must be preserved.

    The version package defines environments via \excludeversion{name} (hidden)
    and \includeversion{name} (shown) in the preamble. Without them,
    \begin{name}...\end{name} in the body fails with "Environment name undefined."

    Playground verified:
      \usepackage{version} + \excludeversion{invisible}
      + \begin{invisible}hidden\end{invisible}Visible content.
      -> "Visible content."
    compile_snippet(preamble=..., body=...).pdf_text == 'Visible content.\n\n1'
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{version}\n"
        "\\excludeversion{invisible}\n"
        "\\begin{document}\n"
        "\\begin{invisible}hidden\\end{invisible}\n"
        "Visible content.\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: \excludeversion{invisible} must be in the minimal preamble
    assert r'\excludeversion{invisible}' in minimal, (
        f"BUG-18: \\excludeversion{{invisible}} stripped from minimal preamble:\n{minimal}"
    )
    # Positive: \usepackage{version} must still be present
    assert r'\usepackage{version}' in minimal


def test_build_minimal_preamble_preserves_includeversion_BUG18():
    r"""BUG-18: \includeversion{name} must also be preserved.

    Playground verified:
      \usepackage{version} + \includeversion{visible}
      + \begin{visible}Shown content.\end{visible}After.
      -> "Shown content.After."
    compile_snippet(preamble=..., body=...).pdf_text == 'Shown content.After.\n\n1'
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{version}\n"
        "\\includeversion{visible}\n"
        "\\begin{document}\n"
        "\\begin{visible}Shown content.\\end{visible}After.\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: \includeversion{visible} must be in the minimal preamble
    assert r'\includeversion{visible}' in minimal, (
        f"BUG-18: \\includeversion{{visible}} stripped from minimal preamble:\n{minimal}"
    )


def test_build_minimal_preamble_preserves_excludeversion_with_optional_arg_BUG18():
    r"""BUG-18: \excludeversion[replacement]{name} with optional arg must be preserved.

    Playground verified:
      \usepackage{version} + \excludeversion[(redacted)]{secret}
      + \begin{secret}classified\end{secret}Public.
      -> "(redacted)Public."
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{version}\n"
        "\\excludeversion[(redacted)]{secret}\n"
        "\\begin{document}\n"
        "\\begin{secret}classified\\end{secret}Public.\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: \excludeversion[(redacted)]{secret} must be preserved
    assert r'\excludeversion[(redacted)]{secret}' in minimal, (
        f"BUG-18: \\excludeversion with optional arg stripped:\n{minimal}"
    )


# ---------------------------------------------------------------------------
# BUG-20 regression: class-specific theorem-env definers (e.g. \newtheoremrm)
# ---------------------------------------------------------------------------

def test_build_minimal_preamble_preserves_newtheoremrm_BUG20():
    r"""BUG-20: \newtheoremrm and other class-specific theorem-env definers
    must not be stripped by build_minimal_preamble.

    tac.cls provides \newtheoremrm (roman-body theorems). The pattern
    _NEWTHEOREM_RE only matched \newtheorem and \newtheorem*, so
    \newtheoremrm{rem}{Remark} was stripped and \begin{rem} became undefined.

    Playground verified: \newtheorem{rem}{Remark} + \begin{rem}...\end{rem}
      -> "Remark 1. This is a remark."
    compile_snippet(preamble=..., body=...).pdf_text == 'Remark 1. This is a remark.\n\n1'
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{amsthm}\n"
        "\\newtheoremrm{rem}{Remark}\n"
        "\\begin{document}\n"
        "\\begin{rem}This is a remark.\\end{rem}\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: \newtheoremrm{rem}{Remark} must be in the minimal preamble
    assert r'\newtheoremrm{rem}{Remark}' in minimal, (
        f"BUG-20: \\newtheoremrm{{rem}}{{Remark}} stripped from preamble:\n{minimal}"
    )
    # Standard \newtheorem must still work
    raw_tex2 = (
        "\\documentclass{article}\n"
        "\\usepackage{amsthm}\n"
        "\\newtheorem{thm}{Theorem}\n"
        "\\begin{document}\n"
        "\\begin{thm}Hello\\end{thm}\n"
        "\\end{document}"
    )
    minimal2 = build_minimal_preamble(raw_tex2)
    assert r'\newtheorem{thm}{Theorem}' in minimal2


# ---------------------------------------------------------------------------
# BUG-21 regression: underscore in package name
# ---------------------------------------------------------------------------

def test_underscore_package_name_BUG21():
    """BUG-21: find_pkg_lib must match package names with underscores.

    Playground verified: \\newcommand{\\myMacro}{\\mathcal{M}} + $\\myMacro$ -> "M"
    compile_snippet(preamble=..., body=...).pdf_text contains 'M'
    """
    from texphage.find_packages import find_explicit_package_calls

    preamble = (
        r'\usepackage{amsmath}' + '\n'
        r'\usepackage{my_defs}' + '\n'
        r'\usepackage{defs_pp1}' + '\n'
        r'\usepackage{a_b_c}' + '\n'
    )
    calls = find_explicit_package_calls(preamble)
    all_names = [n for c in calls for n in c.names]

    # Positive: packages with underscores must be found
    assert 'my_defs' in all_names, f"my_defs not found in {all_names}"
    assert 'defs_pp1' in all_names, f"defs_pp1 not found in {all_names}"
    assert 'a_b_c' in all_names, f"a_b_c not found in {all_names}"

    # Negative: normal packages must still work
    assert 'amsmath' in all_names, f"amsmath not found in {all_names}"


def test_underscore_package_in_minimal_preamble_BUG21():
    """BUG-21: build_minimal_preamble must preserve \\usepackage{pkg_with_underscore}."""
    from texphage.pipeline import build_minimal_preamble

    raw_tex = doc(
        r'\usepackage{amsmath}' + '\n'
        r'\usepackage{my_defs}' + '\n'
        r'\newcommand{\foo}{bar}',
        r'\foo',
    )
    minimal = build_minimal_preamble(raw_tex)
    assert r'\usepackage{my_defs}' in minimal, (
        f"\\usepackage{{my_defs}} missing from minimal preamble:\n{minimal}"
    )


def test_newtheoremstyle_not_captured_BUG_22():
    r"""BUG-22: \newtheoremstyle must NOT be matched by _NEWTHEOREM_RE.

    Playground verified:
        \usepackage{amsthm}
        \newtheoremstyle{TheoremNum}{}{}{}{}{\bfseries}{.}{ }{}
        \theoremstyle{TheoremNum}
        \newtheorem{thm}{Theorem}
        \newtheorem{example}[thm]{Example}
        + \begin{thm}Hello.\end{thm}\begin{example}An example.\end{example}
        -> "Theorem 1. Hello.\nExample 2. An example."
    compile_snippet(...).pdf_text contains 'Theorem 1. Hello.'
    """
    from texphage.pipeline import build_minimal_preamble

    raw_tex = (
        "\\documentclass{article}\n"
        "\\usepackage{amsthm}\n"
        "\\newtheoremstyle{TheoremNum}\n"
        "  {}{}{}{}{\\bfseries}{.}{ }{}\n"
        "\\theoremstyle{TheoremNum}\n"
        "\\newtheorem{thm}{Theorem}\n"
        "\\newtheorem{example}[thm]{Example}\n"
        "\\begin{document}\n"
        "\\begin{thm}Hello.\\end{thm}\n"
        "\\begin{example}An example.\\end{example}\n"
        "\\end{document}"
    )
    minimal = build_minimal_preamble(raw_tex)

    # Positive: real \newtheorem declarations must be present
    assert r'\newtheorem{thm}{Theorem}' in minimal
    assert r'\newtheorem{example}[thm]{Example}' in minimal

    # Negative: \newtheoremstyle must NOT be partially captured as a \newtheorem
    # The env name "TheoremNum" should not appear as a newtheorem env
    assert 'TheoremNum' not in minimal, (
        f"\\newtheoremstyle was incorrectly matched as \\newtheorem:\n{minimal}"
    )
