"""Tests for texphage.unfold. No network. No TeX installation."""
from pathlib import Path

import pytest

from texphage.unfold import unfold, find_main_file

FIXTURES = Path(__file__).parent / 'fixtures'


def test_nested_input_both_sections():
    result = unfold(FIXTURES / 'nested_input')
    assert 'Hello from intro.' in result
    assert 'Hello from body.' in result


def test_single_file_unchanged():
    content = '\\begin{document}Hello\\end{document}'
    assert unfold(FIXTURES / 'nested_input', main=content) == content


def test_missing_input_leaves_command():
    result = unfold(FIXTURES / 'nested_input', main='\\input{nonexistent}')
    assert '\\input{nonexistent}' in result


def test_circular_input_terminates(tmp_path):
    """Circular \\input must not infinite-loop."""
    (tmp_path / 'a.tex').write_text('A \\input{b}')
    (tmp_path / 'b.tex').write_text('B \\input{a}')
    result = unfold(tmp_path, main='\\input{a}')
    assert 'A' in result and 'B' in result


def test_include_adds_clearpage():
    assert '\\clearpage' in unfold(FIXTURES / 'nested_input')


def test_subfile_strips_preamble():
    result = unfold(FIXTURES / 'subfile_example')
    assert 'Content from subfile.' in result
    assert result.count('\\documentclass') == 1


def test_main_file_detection_deterministic(tmp_path):
    """main.tex must be preferred over other files with \\documentclass."""
    (tmp_path / 'other.tex').write_text('\\documentclass{article} OTHER')
    (tmp_path / 'main.tex').write_text('\\documentclass{article} MAIN')
    result = unfold(tmp_path)
    assert 'MAIN' in result
    assert 'OTHER' not in result


def test_find_main_file_docclass_in_input_BUG13(tmp_path):
    """BUG-13: find_main_file must return main.tex even when \\documentclass is only in an \\input'd file.

    Some arXiv papers have main.tex containing only \\input{preamble} where preamble.tex
    holds the \\documentclass. The old code rejected main.tex because the \\documentclass
    check was False for main.tex (which has no \\documentclass directly — not even in comments).

    Ref: BUGS.md BUG-13.
    """
    # main.tex: no \documentclass at all (not even in comments)
    (tmp_path / 'main.tex').write_text('\\input{preamble}\n\\begin{document}\nHello\n\\end{document}')
    (tmp_path / 'preamble.tex').write_text('\\documentclass{article}\n\\usepackage{amsmath}')

    content = find_main_file(str(tmp_path))
    assert content != '', 'find_main_file returned empty string for canonical main.tex — BUG-13'
    assert r'\input{preamble}' in content, (
        f'Expected main.tex content, got: {content[:100]!r}'
    )


def test_unfold_docclass_in_input_BUG13(tmp_path):
    """BUG-13 integration: unfold() must produce the full document including \\documentclass from an \\input'd file."""
    (tmp_path / 'main.tex').write_text('\\input{preamble}\n\\begin{document}\nHello world\n\\end{document}')
    (tmp_path / 'preamble.tex').write_text('\\documentclass{article}')

    result = unfold(str(tmp_path))
    assert '\\documentclass' in result
    assert 'Hello world' in result


def test_braceless_input_BUG14(tmp_path):
    """BUG-14: \\input xy (no braces, plain-TeX style) must be recognised by unfold/_FIND_INPUT.

    The fix: _FIND_INPUT must match braceless \\input <word> in addition to \\input{path}.
    After the fix, unfold tries to resolve 'xy' as a file (warns if not found, but does
    NOT silently leave it as an unrecognised command in the output without trying).

    Specifically: with a local file 'local_pkg.tex', braceless '\\input local_pkg' should
    inline the file content, just like '\\input{local_pkg}' does.

    Ref: BUGS.md BUG-14.
    """
    (tmp_path / 'main.tex').write_text(
        '\\documentclass{article}\n'
        '\\input local_pkg\n'
        '\\begin{document}Main body\\end{document}'
    )
    (tmp_path / 'local_pkg.tex').write_text('% local package content\n\\usepackage{amsmath}')

    result = unfold(str(tmp_path))
    # After fix: 'local package content' should be inlined from local_pkg.tex
    assert 'local package content' in result, (
        f'Braceless \\input local_pkg not resolved. Result: {result!r}'
    )
