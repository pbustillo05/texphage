import shutil

import pytest
from pathlib import Path
from scripts.latex_playground import compile_snippet, compare_snippets

pytestmark = pytest.mark.skipif(
    not __import__('shutil').which('latexmk'),
    reason='latexmk not available'
)


def test_visual_requires_keep_dir():
    with pytest.raises(ValueError, match='keep_dir'):
        compile_snippet(body=r'hello', visual=True)


def test_compile_snippet_visual_standalone(tmp_path):
    result = compile_snippet(
        body=r'\textbf{hello}',
        use_standalone=True,
        visual=True,
        keep_dir=tmp_path,
    )
    assert result.ok
    assert result.png_path is not None
    assert result.png_path.exists()


def test_compare_snippets_requires_two():
    with pytest.raises(ValueError):
        compare_snippets(
            [r'\documentclass{standalone}\begin{document}x\end{document}'],
            keep_dir=Path('/tmp'),
        )


def test_compare_snippets_label_mismatch():
    tex = r'\documentclass{standalone}\begin{document}x\end{document}'
    with pytest.raises(ValueError):
        compare_snippets([tex, tex], keep_dir=Path('/tmp'), labels=['only_one'])


def test_compare_snippets_identical(tmp_path):
    tex = (r'\documentclass[border=4pt]{standalone}'
           r'\begin{document}hello\end{document}')
    r = compare_snippets([tex, tex], keep_dir=tmp_path)
    assert all(res.ok for res in r.results)
    assert r.ssim_scores[(0, 1)] > 0.99
    assert r.diffs[(0, 1)] is not None and r.diffs[(0, 1)].exists()


def test_compare_snippets_different(tmp_path):
    a = (r'\documentclass[border=4pt]{standalone}'
         r'\begin{document}\textbf{hello}\end{document}')
    b = (r'\documentclass[border=4pt]{standalone}'
         r'\begin{document}hello\end{document}')
    r = compare_snippets([a, b], keep_dir=tmp_path, labels=['bold', 'plain'])
    assert r.labels == ['bold', 'plain']
    assert r.ssim_scores[(0, 1)] < 0.99
    assert r.diffs[(0, 1)] is not None


def test_compare_snippets_three(tmp_path):
    def make(body):
        return (r'\documentclass[border=4pt]{standalone}'
                rf'\begin{{document}}{body}\end{{document}}')
    snippets = [make(r'\textbf{x}'), make(r'\textit{x}'), make('x')]
    r = compare_snippets(snippets, keep_dir=tmp_path)
    assert len(r.results) == 3
    for pair in [(0, 1), (0, 2), (1, 2)]:
        assert pair in r.diffs
        assert pair in r.ssim_scores
