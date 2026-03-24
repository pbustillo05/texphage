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


# --- \InputIfFileExists tests ---

def test_inputiffileexists_file_found(tmp_path):
    r"""\InputIfFileExists: when file exists, true-code and file content must both appear."""
    (tmp_path / 'config.tex').write_text('config content here')
    main = r'\InputIfFileExists{config.tex}{true code}{false code}'
    result = unfold(str(tmp_path), main=main)
    assert 'config content here' in result
    assert 'true code' in result
    assert 'false code' not in result


def test_inputiffileexists_file_missing(tmp_path):
    r"""\InputIfFileExists: when file is missing, only false-code is returned."""
    main = r'\InputIfFileExists{missing.tex}{true code}{false code}'
    result = unfold(str(tmp_path), main=main)
    assert 'false code' in result
    assert 'true code' not in result
    assert 'missing.tex' not in result


def test_inputiffileexists_true_code_before_file_content(tmp_path):
    r"""\InputIfFileExists: true-code must appear BEFORE file content (LaTeX semantics)."""
    (tmp_path / 'body.tex').write_text('FILE BODY')
    main = r'\InputIfFileExists{body.tex}{SETUP CODE}{}'
    result = unfold(str(tmp_path), main=main)
    assert result.index('SETUP CODE') < result.index('FILE BODY')


def test_inputiffileexists_empty_true_branch(tmp_path):
    r"""\InputIfFileExists with empty true-code — common idiom."""
    (tmp_path / 'extra.tex').write_text('extra content')
    main = r'\InputIfFileExists{extra.tex}{}{fallback}'
    result = unfold(str(tmp_path), main=main)
    assert 'extra content' in result
    assert 'fallback' not in result


def test_inputiffileexists_recursive_in_included_file(tmp_path):
    r"""\InputIfFileExists: included file is recursively unfolded."""
    (tmp_path / 'inner.tex').write_text(r'\input{leaf}')
    (tmp_path / 'leaf.tex').write_text('leaf content')
    main = r'\InputIfFileExists{inner.tex}{}{}'
    result = unfold(str(tmp_path), main=main)
    assert 'leaf content' in result


# --- \inputfrom and \subinputfrom tests ---

def test_inputfrom_basic(tmp_path):
    r"""\inputfrom{dir}{file} resolves like \import — sets dir as search root."""
    subdir = tmp_path / 'chapters'
    subdir.mkdir()
    (subdir / 'ch1.tex').write_text('chapter one content')
    main = r'\inputfrom{chapters/}{ch1}'
    result = unfold(str(tmp_path), main=main)
    assert 'chapter one content' in result


def test_subinputfrom_basic(tmp_path):
    r"""\subinputfrom{dir}{file} resolves like \subimport — dir relative to current file."""
    subdir = tmp_path / 'sections'
    subdir.mkdir()
    (subdir / 'sec1.tex').write_text('section one content')
    main = r'\subinputfrom{sections/}{sec1}'
    result = unfold(str(tmp_path), main=main)
    assert 'section one content' in result


def test_inputfrom_missing_file_leaves_command(tmp_path):
    r"""\inputfrom with missing file leaves the command unexpanded (like \input)."""
    main = r'\inputfrom{chapters/}{missing}'
    result = unfold(str(tmp_path), main=main)
    assert r'\inputfrom' in result


def test_inputfrom_tex_extension_auto_appended(tmp_path):
    r"""\inputfrom auto-appends .tex when no extension given."""
    subdir = tmp_path / 'sub'
    subdir.mkdir()
    (subdir / 'file.tex').write_text('auto ext content')
    result = unfold(str(tmp_path), main=r'\inputfrom{sub/}{file}')
    assert 'auto ext content' in result


def test_subinputfrom_nested_resolution(tmp_path):
    r"""\subinputfrom: file in subdir can itself use relative includes."""
    subdir = tmp_path / 'parts'
    subdir.mkdir()
    (subdir / 'part.tex').write_text(r'\input{detail}')
    (subdir / 'detail.tex').write_text('nested detail')
    result = unfold(str(tmp_path), main=r'\subinputfrom{parts/}{part}')
    assert 'nested detail' in result
