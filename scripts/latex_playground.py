"""LaTeX playground — compile a .tex snippet and inspect the output.

Used by Claude as a debugging tool when the expected LaTeX behaviour is
unclear from docs alone. Cheaper and faster than reading all of
texbytopic; often the only reliable way to resolve edge-case questions.

Usage from Claude Code:
    from scripts.latex_playground import compile_snippet

    result = compile_snippet(r'''
        \\newcommand{\\greet}[1][World]{Hello, #1!}
        \\greet   \\greet[Alice]
    ''')
    print(result.pdf_text)   # extracted text from the output PDF
    print(result.log)        # full latexmk log (errors, warnings)
    print(result.ok)         # True if compiled successfully

Or from the command line (for quick one-off experiments):

    python scripts/latex_playground.py --body '\\textbf{hello}'
    python scripts/latex_playground.py --file my_test.tex

The full .tex file is printed so you can inspect exactly what was compiled.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Always wrap snippets in a minimal article so latexmk has a complete document.
_WRAPPER = r"""\documentclass{{article}}
\usepackage{{amsmath,amssymb,xparse,xargs}}
{preamble}
\begin{{document}}
{body}
\end{{document}}
"""

_STANDALONE_WRAPPER = r"""\documentclass[border=4pt]{{standalone}}
\usepackage{{amsmath,amssymb,xparse,xargs}}
{preamble}
\begin{{document}}
{body}
\end{{document}}
"""


@dataclass
class PlaygroundResult:
    tex_source: str          # The complete .tex file that was compiled
    ok: bool                 # True if latexmk exit code == 0
    exit_code: int
    log: str                 # Full latexmk stdout+stderr
    pdf_path: Path | None    # Path to output PDF if produced (in tmp dir)
    pdf_text: str            # Text extracted from PDF (via pdftotext), or ''
    error_lines: list[str]   # Lines from the log that look like errors
    png_path: Path | None = None  # Set when visual=True and compile succeeded


@dataclass
class CompareResult:
    results: list[PlaygroundResult]
    pngs: list[Path | None]                        # page 1 PNG per snippet
    diffs: dict[tuple[int, int], Path | None]       # (i,j) → diff PNG, i < j only
    ssim_scores: dict[tuple[int, int], float | None]
    labels: list[str]
    keep_dir: Path


def _compile_tex_file(tex_file: Path, work_dir: Path, tex_source: str,
                      timeout: int) -> PlaygroundResult:
    """Compile a .tex file already written to disk and return the result."""
    try:
        result = subprocess.run(
            ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
             tex_file.name],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,   # MANDATORY: TeX is Turing-complete and can loop
        )
        log = result.stdout + result.stderr
        ok = result.returncode == 0
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return PlaygroundResult(
            tex_source=tex_source, ok=False, exit_code=-1,
            log='[TIMEOUT]', pdf_path=None, pdf_text='',
            error_lines=[f'TIMEOUT after {timeout}s'],
        )

    # Extract text from PDF if produced.
    pdf = work_dir / tex_file.with_suffix('.pdf').name
    pdf_text = ''
    if pdf.exists():
        try:
            pt = subprocess.run(
                ['pdftotext', str(pdf), '-'],
                capture_output=True, text=True, timeout=10,
            )
            pdf_text = pt.stdout
        except Exception:
            pass

    error_lines = [
        line for line in log.splitlines()
        if any(kw in line.lower() for kw in
               ['error', 'undefined', 'missing', 'extra }', '! '])
    ]

    return PlaygroundResult(
        tex_source=tex_source,
        ok=ok,
        exit_code=exit_code,
        log=log,
        pdf_path=pdf if pdf.exists() else None,
        pdf_text=pdf_text,
        error_lines=error_lines,
    )


def _render_png(pdf_path: Path, out_path: Path, dpi: int = 150) -> Path:
    """Render page 1 of a PDF to a PNG file."""
    from pdf2image import convert_from_path

    images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=dpi)
    images[0].save(str(out_path))
    return out_path


def _make_diff(png_a: Path, png_b: Path, diff_out: Path) -> float:
    """Generate a visual diff image and return the SSIM score."""
    import numpy as np
    from PIL import Image
    from skimage.metrics import structural_similarity

    img_a = np.array(Image.open(png_a).convert('L'))
    img_b = np.array(Image.open(png_b).convert('L'))

    # Pad to same dimensions (outputs may differ in size)
    h = max(img_a.shape[0], img_b.shape[0])
    w = max(img_a.shape[1], img_b.shape[1])

    def pad(img):  # type: ignore[no-untyped-def]
        out = np.full((h, w), 255, dtype=np.uint8)
        out[:img.shape[0], :img.shape[1]] = img
        return out

    img_a, img_b = pad(img_a), pad(img_b)

    score, diff = structural_similarity(img_a, img_b, full=True)
    diff_vis = ((1.0 - diff) * 127.5).clip(0, 255).astype(np.uint8)
    Image.fromarray(diff_vis).save(str(diff_out))
    return float(score)


def compile_snippet(
    body: str,
    preamble: str = '',
    packages: list[str] | None = None,
    timeout: int = 30,
    keep_dir: Path | None = None,
    visual: bool = False,
    use_standalone: bool = False,
) -> PlaygroundResult:
    """Compile a LaTeX body snippet and return the result.

    Args:
        body:           LaTeX content inside \\begin{document}...\\end{document}.
        preamble:       Extra preamble lines (\\newcommand etc.) before \\begin{document}.
        packages:       Extra \\usepackage{...} names to add.
        timeout:        latexmk timeout in seconds (default 30; never omit — TeX can loop).
        keep_dir:       If set, write files here instead of a temp dir (for inspection).
        visual:         If True, render page 1 to PNG (requires keep_dir).
        use_standalone: If True, use standalone documentclass for tight cropping.

    Returns:
        PlaygroundResult with .ok, .log, .pdf_text, .error_lines, .png_path.
    """
    if visual and keep_dir is None:
        raise ValueError("keep_dir is required when visual=True")

    extra_pkgs = ''
    if packages:
        extra_pkgs = '\n'.join(r'\usepackage{' + p + '}' for p in packages)

    full_preamble = extra_pkgs + ('\n' if extra_pkgs and preamble else '') + preamble
    wrapper = _STANDALONE_WRAPPER if use_standalone else _WRAPPER
    tex = wrapper.format(preamble=full_preamble, body=body)

    def _run_in(work_dir: Path) -> PlaygroundResult:
        tex_file = work_dir / 'test.tex'
        tex_file.write_text(tex, encoding='utf-8')
        r = _compile_tex_file(tex_file, work_dir, tex, timeout)

        if visual and r.ok and r.pdf_path is not None:
            png = _render_png(r.pdf_path, work_dir / 'output.png')
            r.png_path = png

        return r

    if keep_dir:
        keep_dir.mkdir(parents=True, exist_ok=True)
        return _run_in(keep_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            return _run_in(Path(tmp))


def compare_snippets(
    snippets: list[str],
    keep_dir: Path,
    labels: list[str] | None = None,
    dpi: int = 150,
    timeout: int = 30,
) -> CompareResult:
    """Compile 2+ complete .tex strings and produce pairwise visual diffs.

    Args:
        snippets:  Complete .tex strings (documentclass included). No wrapping applied.
        keep_dir:  Directory to store all outputs (mandatory).
        labels:    Human-readable labels for each snippet. Auto-generated if None.
        dpi:       DPI for PNG rendering (default 150).
        timeout:   latexmk timeout per snippet in seconds.

    Returns:
        CompareResult with per-snippet results, PNGs, pairwise diffs, and SSIM scores.
    """
    if len(snippets) < 2:
        raise ValueError("compare_snippets requires at least 2 snippets")
    if labels is not None and len(labels) != len(snippets):
        raise ValueError(f"labels length ({len(labels)}) != snippets length ({len(snippets)})")

    if labels is None:
        labels = [f'snippet_{i}' for i in range(len(snippets))]

    keep_dir.mkdir(parents=True, exist_ok=True)

    results: list[PlaygroundResult] = []
    pngs: list[Path | None] = []

    for i, tex in enumerate(snippets):
        work_dir = keep_dir / f'snippet_{i}'
        work_dir.mkdir(parents=True, exist_ok=True)
        tex_file = work_dir / 'test.tex'
        tex_file.write_text(tex, encoding='utf-8')

        r = _compile_tex_file(tex_file, work_dir, tex, timeout)
        results.append(r)

        png: Path | None = None
        if r.ok and r.pdf_path is not None:
            png = keep_dir / f'snippet_{i}.png'
            _render_png(r.pdf_path, png, dpi=dpi)
        pngs.append(png)

    # Generate all pairwise diffs
    diffs: dict[tuple[int, int], Path | None] = {}
    ssim_scores: dict[tuple[int, int], float | None] = {}

    for i in range(len(snippets)):
        for j in range(i + 1, len(snippets)):
            if pngs[i] is not None and pngs[j] is not None:
                diff_path = keep_dir / f'diff_{i}_{j}.png'
                score = _make_diff(pngs[i], pngs[j], diff_path)
                diffs[(i, j)] = diff_path
                ssim_scores[(i, j)] = score
            else:
                diffs[(i, j)] = None
                ssim_scores[(i, j)] = None

    return CompareResult(
        results=results,
        pngs=pngs,
        diffs=diffs,
        ssim_scores=ssim_scores,
        labels=labels,
        keep_dir=keep_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Compile a LaTeX snippet and print the result.'
    )
    parser.add_argument('--body', default=r'\textbf{Hello, playground!}',
                        help='LaTeX body content (default: bold hello)')
    parser.add_argument('--preamble', default='',
                        help='Extra preamble lines')
    parser.add_argument('--file', type=Path, default=None,
                        help='Read body from a .tex file instead')
    parser.add_argument('--keep', type=Path, default=None,
                        help='Keep output in this directory for inspection')
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()

    body = args.body
    if args.file:
        body = args.file.read_text(encoding='utf-8')

    result = compile_snippet(
        body=body,
        preamble=args.preamble,
        timeout=args.timeout,
        keep_dir=args.keep,
    )

    print('=== SOURCE ===')
    print(result.tex_source)
    print(f'\n=== RESULT: {"OK" if result.ok else "FAILED"} (exit {result.exit_code}) ===')
    if result.pdf_text:
        print('\n=== PDF TEXT ===')
        print(result.pdf_text.strip())
    if result.error_lines:
        print('\n=== ERRORS/WARNINGS ===')
        for line in result.error_lines:
            print(line)
    if not result.ok:
        print('\n=== FULL LOG ===')
        print(result.log[-3000:])   # last 3000 chars is usually enough

    sys.exit(0 if result.ok else 1)


if __name__ == '__main__':
    main()
