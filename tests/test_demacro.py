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


@pytest.mark.xfail(
    reason="\\def delimited patterns: token() matches one token at a time, "
           "not multi-char sequences like 'Alice' — see BUGS.md"
)
def test_def_token_pattern():
    # TeX primitive: #1 grabs all tokens up to the literal token "and".
    # This is a TeX (not LaTeX) feature. Ref: TeXbook Ch.20 / texbytopic Ch.10
    # https://texdoc.org/serve/texbytopic/0
    expanded, _, _ = demacro(doc(r'\def\swap#1and#2{#2 and #1}', r'\swap Alice and Bob'))
    assert 'Bob and Alice' in expanded


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


@pytest.mark.xfail(
    reason="xargs positional key [i=default] syntax not yet implemented — see BUGS.md"
)
def test_newcommandx_positional_defaults():
    # \newcommandx with [i=default] syntax. Docs: https://ctan.org/pkg/xargs
    # \newcommandx{\greet}[2][1=Hello]{#1, #2!}
    # \greet{World} → Hello, World!  (arg 1 uses default "Hello")
    preamble = r'\newcommandx{\greet}[2][1=Hello]{#1, #2!}'
    expanded, _, _ = demacro(doc(preamble, r'\greet{World}'))
    # Correct output: arg 1 uses default "Hello" (not "1=Hello"), arg 2 receives "World"
    assert 'Hello, World!' in expanded and '1=Hello' not in expanded
