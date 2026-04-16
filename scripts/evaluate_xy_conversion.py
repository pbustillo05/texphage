"""Evaluate XY-to-tikzcd conversion quality by compiling before/after PDFs
and reporting SSIM and MSE per page.

Usage:
    python scripts/evaluate_xy_conversion.py <path_to_tex_file>
        [--out-dir DIR]              # default: tests/runs/xy_eval_<timestamp>/
        [--ssim-threshold 0.97]      # PASS/FAIL cutoff (default 0.97)

The script:
  1. Copies the source directory to out_dir/original/ and compiles it.
  2. Runs xy_to_tikzcd() + preamble fixup; writes converted.tex.
  3. Compiles converted.tex from out_dir/converted/.
  4. Rasterises both PDFs at 150 dpi (one PNG per page).
  5. Computes SSIM and MSE for each page pair.
  6. Prints a per-page table and a final SUCCESS / FAILURE verdict.

Requirements: pdf2image, scikit-image, numpy  (pip install texphage[agents])

# SSIM baseline log (appended after each benchmark run):
# Date         Input file                    Pages  Min-SSIM  Verdict
# (run this script on real arXiv xy papers and paste results here)
"""
from __future__ import annotations

import argparse
import datetime
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import regex as _re
from pdf2image import convert_from_path
from skimage.metrics import structural_similarity

# Repository root (two levels above this script: scripts/ → repo root)
REPO_ROOT = Path(__file__).parent.parent
RUNS_DIR = REPO_ROOT / "tests" / "runs"

# Prepend repo root so that `scripts.xy_to_tikz` is importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.xy_to_tikz import xy_to_tikzcd  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Pattern to swap \usepackage[...]{xy} → \usepackage{tikz-cd}
_XY_PKG_RE = _re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{xy\}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compile_latex(src_dir: Path, tex_filename: str, log_path: Path) -> dict:
    """Run latexmk -pdf in *src_dir* on *tex_filename*. Return a status dict."""
    t0 = time.time()
    cmd = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        tex_filename,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(src_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        log_path.write_text(result.stdout + "\n" + result.stderr)
        stem = Path(tex_filename).stem
        pdf = src_dir / f"{stem}.pdf"
        produced = pdf.exists()
        return {
            "exit_code": result.returncode,
            "duration_s": round(time.time() - t0, 1),
            "timeout": False,
            "pdf_produced": produced,
            "pdf": pdf if produced else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "duration_s": 120.0,
            "timeout": True,
            "pdf_produced": False,
            "pdf": None,
        }


def _page_count(pdf: Path) -> int | None:
    """Return page count via pdfinfo, or None on error."""
    try:
        out = subprocess.check_output(["pdfinfo", str(pdf)], text=True, timeout=10)
        for line in out.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":")[1].strip())
    except Exception:
        pass
    return None


def _rasterise(pdf: Path) -> list[np.ndarray]:
    """Rasterise *pdf* at 150 dpi; return list of grayscale uint8 arrays."""
    images = convert_from_path(str(pdf), dpi=150, grayscale=True)
    return [np.array(img) for img in images]


def _save_diff_png(orig: np.ndarray, conv: np.ndarray, path: Path) -> None:
    """Write a side-by-side PNG comparing *orig* (left) and *conv* (right)."""
    from PIL import Image

    gap = 10
    h = max(orig.shape[0], conv.shape[0])
    w = orig.shape[1] + gap + conv.shape[1]
    canvas = np.full((h, w), 200, dtype=np.uint8)  # light-grey gap
    canvas[: orig.shape[0], : orig.shape[1]] = orig
    canvas[: conv.shape[0], orig.shape[1] + gap :] = conv
    Image.fromarray(canvas).save(str(path))


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def evaluate(tex_path: Path, out_dir: Path, ssim_threshold: float) -> bool:
    """Compile original + converted, compare page-by-page.  Return True on SUCCESS."""
    tex_path = tex_path.resolve()
    tex_filename = tex_path.name
    src_dir = tex_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Output directory: %s", out_dir)

    # ── 1. Copy source tree ──────────────────────────────────────────────────
    orig_dir = out_dir / "original"
    conv_dir = out_dir / "converted"
    for d in (orig_dir, conv_dir):
        if d.exists():
            shutil.rmtree(d)
    shutil.copytree(src_dir, orig_dir)
    shutil.copytree(src_dir, conv_dir)

    # ── 2. Compile original ──────────────────────────────────────────────────
    log.info("Compiling original (%s) ...", tex_filename)
    orig_result = _compile_latex(orig_dir, tex_filename, out_dir / "original.log")
    log.info(
        "  exit=%s  %.1fs  pdf=%s",
        orig_result["exit_code"],
        orig_result["duration_s"],
        orig_result["pdf_produced"],
    )
    if not orig_result["pdf_produced"]:
        log.error("Original failed to compile — check %s", out_dir / "original.log")
        return False
    orig_pdf = out_dir / "original.pdf"
    shutil.copy(orig_result["pdf"], orig_pdf)  # type: ignore[arg-type]

    # ── 3. Convert ───────────────────────────────────────────────────────────
    log.info("Running xy_to_tikzcd ...")
    source = tex_path.read_text()
    converted = xy_to_tikzcd(source)
    # Fix preamble: swap \usepackage[...]{xy} → \usepackage{tikz-cd}
    converted = _XY_PKG_RE.sub(r"\\usepackage{tikz-cd}", converted)

    (out_dir / "converted.tex").write_text(converted)
    (conv_dir / tex_filename).write_text(converted)

    # ── 4. Compile converted ─────────────────────────────────────────────────
    log.info("Compiling converted (%s) ...", tex_filename)
    conv_result = _compile_latex(conv_dir, tex_filename, out_dir / "converted.log")
    log.info(
        "  exit=%s  %.1fs  pdf=%s",
        conv_result["exit_code"],
        conv_result["duration_s"],
        conv_result["pdf_produced"],
    )
    if not conv_result["pdf_produced"]:
        log.error("Converted failed to compile — check %s", out_dir / "converted.log")
        return False
    conv_pdf = out_dir / "converted.pdf"
    shutil.copy(conv_result["pdf"], conv_pdf)  # type: ignore[arg-type]

    # ── 5. Page-count sanity check ───────────────────────────────────────────
    n_orig = _page_count(orig_pdf)
    n_conv = _page_count(conv_pdf)
    log.info("Page count: original=%s  converted=%s", n_orig, n_conv)
    if n_orig != n_conv:
        log.error(
            "Page count mismatch (%s vs %s) — this IS the confirmed bug; skipping SSIM.",
            n_orig,
            n_conv,
        )
        return False

    # ── 6. Rasterise ─────────────────────────────────────────────────────────
    log.info("Rasterising PDFs at 150 dpi ...")
    orig_pages = _rasterise(orig_pdf)
    conv_pages = _rasterise(conv_pdf)

    # ── 7. Compute SSIM / MSE per page ───────────────────────────────────────
    diff_dir = out_dir / "diffs"
    diff_dir.mkdir(exist_ok=True)

    header = f"{'PAGE':>4}  {'SSIM':>6}  {'MSE':>10}  {'STATUS':>6}  DIFF"
    print()
    print(header)
    print("-" * len(header))

    all_pass = True
    for i, (orig_arr, conv_arr) in enumerate(zip(orig_pages, conv_pages)):
        # Trim to common size (150-dpi rounding can cause ±1px differences)
        h = min(orig_arr.shape[0], conv_arr.shape[0])
        w = min(orig_arr.shape[1], conv_arr.shape[1])
        o = orig_arr[:h, :w]
        c = conv_arr[:h, :w]

        ssim_val = float(structural_similarity(o, c, data_range=255))
        mse_val = float(np.mean((o.astype(np.float64) - c.astype(np.float64)) ** 2))
        passed = ssim_val >= ssim_threshold
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        diff_path = diff_dir / f"page_{i + 1:03d}.png"
        _save_diff_png(orig_arr, conv_arr, diff_path)

        print(f"{i + 1:>4}  {ssim_val:>6.4f}  {mse_val:>10.2f}  {status:>6}  {diff_path.name}")

    print()
    verdict = "SUCCESS" if all_pass else "FAILURE"
    print(f"Verdict: {verdict}  (threshold SSIM≥{ssim_threshold})")
    print(f"Diffs:   {diff_dir}")
    print(f"Outputs: {out_dir}")
    print()
    return all_pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate XY-to-tikzcd conversion quality via SSIM/MSE."
    )
    parser.add_argument("tex_file", type=Path, help="Path to the .tex file to evaluate")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: tests/runs/xy_eval_<timestamp>/)",
    )
    parser.add_argument(
        "--ssim-threshold",
        type=float,
        default=0.97,
        help="SSIM threshold for PASS/FAIL (default: 0.97)",
    )
    args = parser.parse_args()

    if args.out_dir is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.out_dir = RUNS_DIR / f"xy_eval_{ts}"

    success = evaluate(args.tex_file, args.out_dir, args.ssim_threshold)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
