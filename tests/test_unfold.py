"""Tests for texphage.unfold. No network. No TeX installation."""
from pathlib import Path

import pytest

from texphage.unfold import unfold

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
