"""Tests for texphage.demacro. No TeX installation required."""
import pytest

from texphage.demacro import demacro


def doc(preamble: str, body: str) -> str:
    return (f"\\documentclass{{article}}\n{preamble}\n"
            f"\\begin{{document}}\n{body}\n\\end{{document}}")


def test_newcommand_no_args():
    expanded, _, problems = demacro(doc(r'\newcommand{\hi}{Hello World}', r'\hi'))
    assert 'Hello World' in expanded and problems == []


def test_newcommand_mandatory_arg():
    expanded, _, _ = demacro(doc(r'\newcommand{\greet}[1]{Hello, #1!}', r'\greet{Alice}'))
    assert 'Hello, Alice!' in expanded


def test_newcommand_optional_with_default():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\greet}[1][World]{Hello, #1!}', r'\greet and \greet[Alice]'
    ))
    assert 'Hello, World!' in expanded
    assert 'Hello, Alice!' in expanded


def test_def_token_pattern():
    # Playground verified: \def\swap#1and#2{#2 and #1} + \swap Alice and Bob
    # → TeX produces "B and Alice ob"
    # #1 is delimited by 'and' → captures 'Alice ' (lazy match up to 'and')
    # #2 is undelimited → captures one token = 'B'; 'ob' is left in the stream
    # Ref: TeXbook Ch.20; https://texdoc.org/serve/texbytopic/0 Ch.10; BUGS.md BUG-2
    expanded, _, _ = demacro(doc(r'\def\swap#1and#2{#2 and #1}', r'\swap Alice and Bob'))
    assert 'B and Alice' in expanded
    # Pattern must not leave the call unexpanded.
    assert r'\swap' not in expanded


def test_let_alias():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\original}{ORIGINAL}\let\alias\original', r'\alias'
    ))
    assert 'ORIGINAL' in expanded


def test_let_alias_to_unknown_no_crash():
    """\\let\\foo\\cite — alias to unknown command must not raise 'bad escape' in regex.sub."""
    # \let\foo\cite: \cite is not defined in preamble, so stored as literal string '\cite'.
    # When expanded, re.sub must not interpret '\c' as a regex backreference escape.
    expanded, _, _ = demacro(doc(r'\let\foo\cite', r'\foo{ref1}'))
    assert '\\cite' in expanded or 'ref1' in expanded or expanded  # must not crash


def test_new_document_command_xparse():
    # xparse types: m=mandatory, o=optional(\NoValue default), O{x}=optional+explicit default
    # s=star boolean. Docs: https://ctan.org/pkg/xparse
    preamble = r'\NewDocumentCommand{\cmd}{m o O{default} s}{[#1][#2][#3][#4]}'
    expanded, _, _ = demacro(doc(preamble, r'\cmd{A}'))
    assert 'A' in expanded


def test_newenvironment():
    expanded, _, _ = demacro(doc(
        r'\newenvironment{myenv}{\textbf{BEGIN}}{\textbf{END}}',
        r'\begin{myenv}content\end{myenv}'
    ))
    assert 'BEGIN' in expanded and 'END' in expanded and 'content' in expanded


def test_new_document_environment():
    expanded, _, _ = demacro(doc(
        r'\NewDocumentEnvironment{myenv}{m}{\textit{#1:}}{\textit{done}}',
        r'\begin{myenv}{title}content\end{myenv}'
    ))
    assert 'title' in expanded and 'done' in expanded


def test_chained_expansion():
    expanded, _, _ = demacro(doc(
        r'\newcommand{\inner}{INNER}\newcommand{\outer}{\inner-OUTER}', r'\outer'
    ))
    assert 'INNER-OUTER' in expanded


def test_self_referential_no_loop():
    # \def\foo{\foo} would loop forever without the no-progress guard in expand().
    expanded, _, problems = demacro(doc(r'\def\foo{\foo}', r'\foo'))
    assert any(p[0] == 'foo' for p in problems)


def test_paragraph_break_preserved():
    tex = "\\documentclass{article}\\begin{document}\nFirst.\n\nSecond.\n\\end{document}"
    expanded, _, _ = demacro(tex)
    assert r'\par' in expanded and 'First.' in expanded and 'Second.' in expanded


def test_verbatim_content_preserved():
    """Whitespace inside \\begin{verbatim} must survive preprocessing unchanged."""
    body = '\\begin{verbatim}\n  indented   code\n  more code\n\\end{verbatim}'
    expanded, _, _ = demacro(doc('', body))
    assert '  indented   code' in expanded


def test_declare_math_operator():
    # \DeclareMathOperator{\myOp}{Op} (from amsmath) defines \myOp to expand to \operatorname{Op}.
    # Docs: https://ctan.org/pkg/amsmath (amsldoc.pdf §3.4)
    expanded, _, _ = demacro(doc(r'\DeclareMathOperator{\myOp}{Op}', r'$\myOp(x)$'))
    assert r'\operatorname{Op}' in expanded and r'\myOp' not in expanded


def test_verbatim_percent_not_treated_as_comment():
    """% inside verbatim is literal output, not a LaTeX comment."""
    body = '\\begin{verbatim}\n100% complete\n% this is verbatim\n\\end{verbatim}'
    expanded, _, _ = demacro(doc('', body))
    assert '100% complete' in expanded
    assert '% this is verbatim' in expanded


def test_newcommandx_positional_defaults():
    # Playground verified: \newcommandx{\greet}[2][1=Hello]{#1, #2!} + \greet{World}
    # → TeX produces "Hello, World!" (arg 1 uses default "Hello", arg 2 = "World")
    # BUG-1 regression: xargs [i=val] positional-key syntax, fixed 2026-03-22.
    # Docs: https://ctan.org/pkg/xargs
    preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
    expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
    assert 'Hello, World!' in expanded
    assert '1=Hello' not in expanded


def test_def_space_before_brace_BUG10():
    """BUG-10: \\def \\R {{\\mathbb R}} — space in def_pattern must not require a literal space.

    TeX ignores whitespace between a command name and the opening { of the body.
    The find_def pattern captures that space into def_pattern, and before the fix
    _def_param_pattern would emit a required \\ in the call-site regex, so \\R
    before $ or } would fail to expand.

    Failure mode: B (expansion failure).
    Ref: BUGS.md BUG-10.
    """
    # Space before { in definition — same as \def\R{{\mathbb R}} semantically.
    expanded, _, problems = demacro(doc(r'\def \R {{\mathbb R}}', r'$f: X \to \R$.'))
    assert r'\R' not in expanded, f"\\R unexpanded: {expanded!r}"
    assert not problems, f"unexpected problems: {problems}"


def test_preprocessing_no_par_in_braced_args_BUG9():
    """BUG-9: blank line inside a command argument must NOT become \\par.

    When a comment line is stripped from inside \\title{...}, the remaining
    blank line was converted to \\par by preprocessing step 3, producing
    \\title{ \\par My Title} which causes "Paragraph ended before \\title".
    After the fix, \\par must be absent from the preamble when it only occurs
    inside braced groups.

    Failure mode: Mode C (preprocessing corruption).
    Ref: BUGS.md BUG-9.
    """
    from texphage.demacro import preprocessing

    # \title{<blank line after comment strip>My Title} is the canonical trigger.
    raw = (
        "\\documentclass{article}\n"
        "\\title{\n"
        "% a comment\n"
        "My Paper Title}\n"
        "\\begin{document}\\maketitle\\end{document}"
    )
    preamble, _body, _ = preprocessing(raw)
    # \par must not appear inside \title{...}
    assert r'\par' not in preamble, (
        f"\\par found inside \\title{{}} — preprocessing inserted spurious paragraph break.\n"
        f"preamble: {preamble!r}"
    )


def test_preprocessing_par_still_preserved_at_top_level_BUG9():
    """Regression guard: top-level blank lines (between paragraphs) must still become \\par."""
    from texphage.demacro import preprocessing

    raw = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "First paragraph.\n"
        "\n"
        "Second paragraph.\n"
        "\\end{document}"
    )
    _preamble, body, _ = preprocessing(raw)
    assert r'\par' in body, "Top-level blank line must still produce \\par in body"


def test_csname_expandafter_indirect_define_BUG19():
    # Playground verified: \newcommand{\definecommand}[1]{\expandafter\def\csname#1\endcsname{Hello, #1!}}
    # + \definecommand{world} + \world → TeX produces "Hello, world" (pdftotext strips !)
    # Current demacro leaves \world unexpanded; fix must register \world via preamble execution.
    preamble = (
        r'\newcommand{\definecommand}[1]{'
        r'\expandafter\def\csname#1\endcsname{Hello, #1!}'
        r'}'
        '\n'
        r'\definecommand{world}'
    )
    expanded, _, problems = demacro(doc(preamble, r'\world'))
    assert 'Hello, world!' in expanded  # positive: expansion succeeded
    assert r'\world' not in expanded    # negative: call must not survive unexpanded


def test_csname_expandafter_direct_BUG19():
    # Playground verified: \expandafter\def\csname mytest\endcsname{Direct!} + \mytest
    # → TeX produces "Direct" (pdftotext strips !)
    # Tests the direct (non-nested) \expandafter\def\csname form in the preamble.
    preamble = r'\expandafter\def\csname mytest\endcsname{Direct content}'
    expanded, _, problems = demacro(doc(preamble, r'\mytest'))
    assert 'Direct content' in expanded
    assert r'\mytest' not in expanded
