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
from dataclasses import dataclass, field
from pathlib import Path

# Always wrap snippets in a minimal article so latexmk has a complete document.
_WRAPPER = r"""\documentclass{{article}}
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


def compile_snippet(
    body: str,
    preamble: str = '',
    packages: list[str] | None = None,
    timeout: int = 30,
    keep_dir: Path | None = None,
) -> PlaygroundResult:
    """Compile a LaTeX body snippet and return the result.

    Args:
        body:      LaTeX content inside \\begin{document}...\\end{document}.
        preamble:  Extra preamble lines (\\newcommand etc.) before \\begin{document}.
        packages:  Extra \\usepackage{...} names to add.
        timeout:   latexmk timeout in seconds (default 30; never omit — TeX can loop).
        keep_dir:  If set, write files here instead of a temp dir (for inspection).

    Returns:
        PlaygroundResult with .ok, .log, .pdf_text, .error_lines.
    """
    extra_pkgs = ''
    if packages:
        extra_pkgs = '\n'.join(r'\usepackage{' + p + '}' for p in packages)

    full_preamble = extra_pkgs + ('\n' if extra_pkgs and preamble else '') + preamble
    tex = _WRAPPER.format(preamble=full_preamble, body=body)

    def _run_in(work_dir: Path) -> PlaygroundResult:
        tex_file = work_dir / 'test.tex'
        tex_file.write_text(tex, encoding='utf-8')

        try:
            result = subprocess.run(
                ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
                 'test.tex'],
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
                tex_source=tex, ok=False, exit_code=-1,
                log='[TIMEOUT]', pdf_path=None, pdf_text='',
                error_lines=['TIMEOUT after %ds' % timeout],
            )

        # Extract text from PDF if produced.
        pdf = work_dir / 'test.pdf'
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
            tex_source=tex,
            ok=ok,
            exit_code=exit_code,
            log=log,
            pdf_path=pdf if pdf.exists() else None,
            pdf_text=pdf_text,
            error_lines=error_lines,
        )

    if keep_dir:
        keep_dir.mkdir(parents=True, exist_ok=True)
        return _run_in(keep_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            return _run_in(Path(tmp))


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
