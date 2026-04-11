"""Testing Agent — pipeline fidelity on real arXiv papers.

Run by saying "Run testing agent on seed 42" to Claude (see AGENTS.md),
or directly:

    python scripts/test_fidelity.py --seed 42
    python scripts/test_fidelity.py --ids 2401.12345 2312.09876

This script implements the Testing Agent protocol described in AGENTS.md:
  Step 1  — acquire lock
  Step 2  — sample papers
  Step 3  — compile baseline PDFs
  Step 4  — run the texphage pipeline
  Step 5  — compile pipeline output
  Step 6  — compare results (compile success, page count, SSIM, text diff)
  Step 7  — diagnose bugs (logged; human review via BUGS.md)
  Step 8  — write to BUGS.md (stubs; human fills in after reviewing logs)
  Step 9  — cleanup intermediate files
  Step 10 — release lock
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import logging
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pdfplumber
import regex as _re
from pdf2image import convert_from_path
from skimage.metrics import structural_similarity
from tqdm import tqdm

# Repository root is two levels above this script.
REPO_ROOT  = Path(__file__).parent.parent
RUNS_DIR   = REPO_ROOT / 'tests' / 'runs'
LOCK_FILE  = RUNS_DIR / '.agent.lock'
LOCK_TTL   = 4 * 3600   # seconds — stale lock threshold

# Paper distribution per run (see AGENTS.md Step 2).
# Legacy list kept for historical reproducibility (--sampling legacy).
_LEGACY_CATEGORIES = ['math.CT', 'math.CT', 'math.AT', 'math.AT', 'cs.LO']

# Path to the full arXiv category list (scripts/arxiv_categories.json).
_CATEGORIES_JSON = Path(__file__).parent / 'arxiv_categories.json'

# Append-only results log — written after each paper, never deleted.
RESULTS_JSONL = REPO_ROOT / 'tests' / 'runs' / 'results.jsonl'

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lock protocol (AGENTS.md §Locking Protocol)
# ---------------------------------------------------------------------------

def _acquire_lock(agent_name: str = 'test_fidelity') -> None:
    """Create the lock file, or raise if a live lock exists."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < LOCK_TTL:
            raise RuntimeError(
                f"Lock held — another agent run is active (age {age/3600:.1f}h). Waiting."
            )
        logger.warning("Stale lock (age %.1fh) — deleting and proceeding.", age / 3600)
        LOCK_FILE.unlink()
    LOCK_FILE.write_text(
        f"{agent_name}\n{datetime.datetime.utcnow().isoformat()}Z\n"
    )


def _release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 2 — Sample papers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _download_arxiv(arxiv_id: str, dest_dir: Path) -> Path:
    """Download arXiv source tarball to dest_dir. Returns path to tarball."""
    import tarfile

    import requests

    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    tarball = dest_dir / f"{arxiv_id}.tar.gz"
    if tarball.exists():
        logger.info("Tarball already exists: %s", tarball)
        return tarball
    logger.info("Downloading %s ...", url)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    tarball.write_bytes(r.content)
    # Extract
    raw_data = dest_dir / 'raw_data'
    raw_data.mkdir(exist_ok=True)
    try:
        with tarfile.open(tarball) as tf:
            tf.extractall(raw_data)
    except tarfile.TarError as e:
        logger.warning("Failed to extract tarball for %s: %s", arxiv_id, e)
    return tarball


def _load_all_categories() -> list[str]:
    """Load the full arXiv category list from arxiv_categories.json."""
    if _CATEGORIES_JSON.exists():
        return json.loads(_CATEGORIES_JSON.read_text())
    # Fallback to legacy list if the JSON is missing.
    logger.warning("arxiv_categories.json not found; falling back to legacy categories.")
    return _LEGACY_CATEGORIES


def _filter_categories(pool: list[str], prefixes: list[str]) -> list[str]:
    """Return the subset of *pool* whose category starts with any of *prefixes*.

    A prefix matches if the category string starts with ``prefix + '.'`` or
    equals the prefix exactly (for single-segment categories like ``'gr-qc'``
    or ``'quant-ph'``).  Comparison is case-insensitive.

    Examples::

        _filter_categories(pool, ['math'])      # math.AG, math.NT, …
        _filter_categories(pool, ['cs', 'math']) # cs.* and math.*
        _filter_categories(pool, ['hep'])        # hep-th, hep-ph, hep-lat, hep-ex
    """
    normed = [p.lower() for p in prefixes]
    result = []
    for cat in pool:
        cat_lower = cat.lower()
        for p in normed:
            if cat_lower == p or cat_lower.startswith(p + '.') or cat_lower.startswith(p + '-'):
                result.append(cat)
                break
    return result


def _sample_categories(n: int, strategy: str, rng: random.Random,
                       category_filter: list[str] | None = None) -> list[str]:
    """Return n category strings according to *strategy*.

    Args:
        n:               Number of category slots to fill.
        strategy:        ``'uniform'`` — draw uniformly from the category pool;
                         ``'legacy'`` — repeat the original five-category list.
        rng:             Seeded RNG instance for reproducibility.
        category_filter: Optional list of prefix strings (e.g. ``['math']``,
                         ``['cs', 'math']``).  When given, only categories
                         matching at least one prefix are included in the pool.
                         Ignored when *strategy* is ``'legacy'``.

    Returns:
        List of n category strings (may contain duplicates if n > pool size).
    """
    if strategy == 'legacy':
        cats = (_LEGACY_CATEGORIES * ((n // len(_LEGACY_CATEGORIES)) + 1))[:n]
        rng.shuffle(cats)
        return cats

    pool = _load_all_categories()
    if category_filter:
        filtered = _filter_categories(pool, category_filter)
        if filtered:
            pool = filtered
        else:
            logger.warning(
                "Category filter %r matched no known categories — using full pool.",
                category_filter,
            )

    # Uniform sampling without replacement as far as possible, then wrap.
    rng.shuffle(pool)
    cats = (pool * ((n // len(pool)) + 1))[:n]
    rng.shuffle(cats)
    return cats


def _sample_papers(n: int, seed: int, sampling: str = 'uniform',
                   category_filter: list[str] | None = None) -> list[dict]:
    """Return n paper metadata dicts, downloading from arXiv.

    Args:
        n:               Number of papers to sample.
        seed:            Random seed for reproducibility.
        sampling:        Category sampling strategy — ``'uniform'`` (default)
                         draws from all ~170 arXiv categories; ``'legacy'``
                         uses the original five-category list.
        category_filter: Optional list of prefix strings passed to
                         :func:`_sample_categories` (e.g. ``['math']``).
    """
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from extractor import get_all_arxiv_ids  # type: ignore[import]

    rng = random.Random(seed)
    cats = _sample_categories(n, sampling, rng, category_filter=category_filter)

    papers = []
    used: set[str] = set()
    year = datetime.date.today().strftime('%y')
    for cat in cats:
        ids = get_all_arxiv_ids(50, cat, year)
        if not ids:
            # Sparse category — try any other category from the (filtered) pool.
            fallback_pool = _load_all_categories()
            if category_filter:
                filtered = _filter_categories(fallback_pool, category_filter)
                if filtered:
                    fallback_pool = filtered
            rng.shuffle(fallback_pool)
            for fb_cat in fallback_pool:
                ids = get_all_arxiv_ids(50, fb_cat, year)
                if ids:
                    cat = fb_cat
                    break
        rng.shuffle(ids)
        for arxiv_id in ids:
            if arxiv_id not in used:
                papers.append({'arxiv_id': arxiv_id, 'category': cat})
                used.add(arxiv_id)
                break
    return papers


# ---------------------------------------------------------------------------
# Step 3 — Compile baseline
# ---------------------------------------------------------------------------

def _compile_latex(src_dir: Path, output_pdf: Path, log_path: Path,
                   tex_file: str | None = None) -> dict:
    """Run latexmk in src_dir. Returns status dict.

    Args:
        src_dir:    Working directory for latexmk.
        output_pdf: Destination path for the produced PDF.
        log_path:   Path to write combined stdout+stderr log.
        tex_file:   If given, compile only this specific .tex file (e.g.
                    'pipeline_output.tex').  When None, latexmk picks the
                    default document in src_dir.
    """
    t0 = time.time()
    try:
        cmd = ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error']
        if tex_file:
            cmd.append(tex_file)
        result = subprocess.run(
            cmd,
            cwd=str(src_dir),
            capture_output=True,
            timeout=120,   # MANDATORY: TeX is Turing-complete and can loop forever
        )
        # TeX logs can contain latin-1 characters; decode with replacement.
        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        duration = time.time() - t0
        log_path.write_text(stdout + stderr)
        # Find the produced PDF: prefer the named target, fall back to any PDF.
        if tex_file:
            pdf_name = tex_file.replace('.tex', '.pdf')
            pdfs = list(src_dir.glob(pdf_name)) or list(src_dir.glob('*.pdf'))
        else:
            pdfs = list(src_dir.glob('*.pdf'))
        if pdfs:
            shutil.copy(pdfs[0], output_pdf)
        return {
            'exit_code': result.returncode,
            'duration_s': round(duration, 1),
            'timeout': False,
            'pdf_produced': bool(pdfs),
        }
    except subprocess.TimeoutExpired:
        return {'exit_code': -1, 'duration_s': 120, 'timeout': True, 'pdf_produced': False}


def _page_count(pdf: Path) -> int | None:
    """Return page count via pdfinfo, or None on error."""
    try:
        out = subprocess.check_output(['pdfinfo', str(pdf)], text=True, timeout=10)
        for line in out.splitlines():
            if line.startswith('Pages:'):
                return int(line.split(':')[1].strip())
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Step 4 — Run the pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(raw_data_dir: Path, run_dir: Path,
                  mode: str = 'raw') -> dict:
    """Run the texphage pipeline on *raw_data_dir*.

    Args:
        raw_data_dir: Extracted arXiv source directory.
        run_dir:      Per-paper output directory (logs, tex, report written here).
        mode:         ``'raw'``       — build canonical_tex manually, write to
                                        raw_data_dir/pipeline_output.tex, compile
                                        from raw_data_dir (all attachments in place).
                      ``'canonical'`` — call texphage_to_dir(), which copies all
                                        attachments into a self-contained subdirectory
                                        run_dir/canonical_output/ and rewrites paths.
                                        Compiles from that directory.

    Returns:
        Report dict with 'packages', 'problematic_macros', and (in canonical
        mode) 'canonical_output_dir'.
    """
    import logging as _logging

    from texphage.demacro import demacro
    from texphage.pipeline import build_minimal_preamble, texphage_to_dir
    from texphage.unfold import unfold

    log_path = run_dir / 'pipeline.log'
    _logging.basicConfig(level=_logging.DEBUG, filename=str(log_path), force=True)

    tex = unfold(raw_data_dir)
    expanded_tex, packages, problems = demacro(tex)
    # BUG-15 / BUG-12: preprocessing collapses the entire body to one line.
    # TeX's bufsize is 200k chars/line; large papers overflow it. Restore
    # newlines at \par boundaries — mirrors the fix in pipeline.texphage().
    expanded_tex = expanded_tex.replace(r'\par ', '\\par' + '\n')

    report = {
        'packages': packages,
        'problematic_macros': [
            {'name': name, 'position': pos, 'reason': reason}
            for name, pos, reason in problems
        ],
    }

    if mode == 'canonical':
        canonical_output_dir = run_dir / 'canonical_output'
        texphage_to_dir(raw_data_dir, canonical_output_dir)
        report['canonical_output_dir'] = str(canonical_output_dir)
    else:
        canonical_tex = (
            build_minimal_preamble(tex)
            + '\n\\begin{document}\n'
            + expanded_tex
            + '\n\\end{document}\n'
        )
        # Write to run_dir for archiving, and to raw_data_dir for compilation.
        # Compiling from raw_data_dir ensures that relative paths to .bib files,
        # images, etc. resolve correctly (BUG-7).
        (run_dir / 'pipeline_output.tex').write_text(canonical_tex)
        (raw_data_dir / 'pipeline_output.tex').write_text(canonical_tex)

    (run_dir / 'demacro_report.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    return report


# ---------------------------------------------------------------------------
# Step 6 — Compare results
# ---------------------------------------------------------------------------

def compare_pdfs_ssim(baseline_pdf: Path, output_pdf: Path) -> list[float]:
    """Return per-page SSIM scores (grayscale, 150 dpi)."""
    b_pages = convert_from_path(str(baseline_pdf), dpi=150, grayscale=True)
    o_pages = convert_from_path(str(output_pdf),   dpi=150, grayscale=True)
    n = max(len(b_pages), len(o_pages))

    def to_arrays(pages: list, target: int) -> list[np.ndarray]:
        blank = np.zeros_like(np.array(pages[0]))
        arrays = [np.array(p) for p in pages[:target]]
        while len(arrays) < target:
            arrays.append(blank)
        return arrays

    return [
        float(structural_similarity(b, o))
        for b, o in zip(to_arrays(b_pages, n), to_arrays(o_pages, n))
    ]


def text_diff(baseline_pdf: Path, output_pdf: Path) -> list[str]:
    """Return unified diff lines between text extracted from both PDFs."""
    def extract(path: Path) -> list[str]:
        with pdfplumber.open(str(path)) as pdf:
            return [
                line
                for page in pdf.pages
                for line in (page.extract_text() or '').splitlines()
            ]
    return list(difflib.unified_diff(
        extract(baseline_pdf), extract(output_pdf),
        fromfile='baseline', tofile='output',
    ))


def _save_visual_diff(
    baseline_pdf: Path,
    output_pdf: Path,
    diff_dir: Path,
    ssim_scores: list[float],
) -> None:
    """Save side-by-side PNGs for pages with SSIM < 0.95."""
    b_pages = convert_from_path(str(baseline_pdf), dpi=150, grayscale=True)
    o_pages = convert_from_path(str(output_pdf),   dpi=150, grayscale=True)
    n = max(len(b_pages), len(o_pages))
    diff_dir.mkdir(exist_ok=True)

    from PIL import Image

    blank_arr: np.ndarray | None = None

    for i, score in enumerate(ssim_scores):
        if score >= 0.95:
            continue
        _blank = blank_arr if blank_arr is not None else np.zeros((100, 100), dtype=np.uint8)
        b_arr = np.array(b_pages[i]) if i < len(b_pages) else _blank
        o_arr = np.array(o_pages[i]) if i < len(o_pages) else _blank
        if blank_arr is None:
            blank_arr = np.zeros_like(b_arr)

        # Resize to same shape if needed.
        h = max(b_arr.shape[0], o_arr.shape[0])
        w = max(b_arr.shape[1], o_arr.shape[1])

        def pad(a: np.ndarray) -> np.ndarray:
            out = np.full((h, w), 255, dtype=np.uint8)
            out[:a.shape[0], :a.shape[1]] = a
            return out

        b_padded, o_padded = pad(b_arr), pad(o_arr)
        diff_arr = np.clip(
            np.abs(b_padded.astype(int) - o_padded.astype(int)) * 5, 0, 255
        ).astype(np.uint8)

        combined = np.concatenate([b_padded, o_padded, diff_arr], axis=1)
        Image.fromarray(combined).save(str(diff_dir / f'page_{i+1}_diff.png'))

    _ = n  # suppress unused-variable warning


def _classify_compile_error(log_text: str) -> str:
    """Classify a failed compile into a root-cause category."""
    log = log_text.lower()
    if 'undefined control sequence' in log:
        return 'undefined_control_sequence'
    elif 'missing {' in log or 'extra }' in log or 'missing }' in log:
        return 'missing_brace'
    elif '\\begin' in log and '\\end' in log and 'mismatch' in log:
        return 'environment_mismatch'
    elif 'file not found' in log or 'package not found' in log:
        return 'package_missing'
    return 'other'


def _compare(paper_dir: Path, baseline_pdf: Path, output_pdf: Path,
             baseline_compile: dict, output_compile: dict) -> dict:
    """Run all comparisons. Return a comparison dict."""
    comp: dict = {
        'baseline_compile': baseline_compile,
        'output_compile': output_compile,
    }

    # 6a — Compilation success
    if output_compile.get('timeout'):
        comp['error_type'] = 'compilation_timeout'
        comp['severity'] = 'CRITICAL'
        return comp

    if output_compile.get('exit_code', 0) != 0:
        log_path = paper_dir / 'output_compile.log'
        log_text = log_path.read_text() if log_path.exists() else ''
        comp['error_type'] = _classify_compile_error(log_text)
        comp['severity'] = 'HIGH'
        return comp

    if not output_pdf.exists() or not baseline_pdf.exists():
        comp['error_type'] = 'pdf_missing'
        comp['severity'] = 'HIGH'
        return comp

    # 6b — Page count
    baseline_pages = _page_count(baseline_pdf) or 0
    output_pages   = _page_count(output_pdf) or 0
    page_delta = abs(output_pages - baseline_pages)
    comp['baseline_pages'] = baseline_pages
    comp['output_pages']   = output_pages
    comp['page_delta']     = page_delta

    # 6c — SSIM
    try:
        ssim_scores = compare_pdfs_ssim(baseline_pdf, output_pdf)
    except Exception as e:
        logger.warning("SSIM comparison failed: %s", e)
        ssim_scores = []
    comp['ssim_per_page'] = ssim_scores
    min_ssim = min(ssim_scores) if ssim_scores else 1.0

    # 6d — Text diff
    try:
        diff_lines = text_diff(baseline_pdf, output_pdf)
    except Exception as e:
        logger.warning("Text diff failed: %s", e)
        diff_lines = []
    comp['text_diff_lines'] = len(diff_lines)

    # Severity classification (AGENTS.md §6c/6d)
    severity = 'OK'
    if page_delta > 2:
        severity = 'HIGH'
    elif min_ssim < 0.85 and comp['text_diff_lines'] > 5:
        severity = 'HIGH'
    elif min_ssim < 0.95:
        severity = 'MEDIUM'
    elif comp['text_diff_lines'] > 50:
        severity = 'HIGH'
    elif comp['text_diff_lines'] > 10:
        severity = 'MEDIUM'
    elif comp['text_diff_lines'] > 0:
        severity = 'LOW'
    comp['severity'] = severity

    # Save visual diffs for pages with SSIM < 0.95
    if ssim_scores:
        vis_dir = paper_dir / 'visual_diff'
        try:
            _save_visual_diff(baseline_pdf, output_pdf, vis_dir, ssim_scores)
        except Exception as e:
            logger.warning("Could not save visual diff: %s", e)

    return comp


# ---------------------------------------------------------------------------
# Step 9 — Cleanup
# ---------------------------------------------------------------------------

_KEEP_LOGS = frozenset([
    'baseline_compile.log', 'output_compile.log', 'pipeline.log',
])


def cleanup_run(id_run_dir: Path) -> None:
    """Delete intermediate build artifacts; keep key outputs."""
    shutil.rmtree(id_run_dir / 'raw_data', ignore_errors=True)
    for ext in ['aux', 'log', 'fls', 'fdb_latexmk', 'out', 'toc',
                'bbl', 'blg', 'synctex.gz']:
        for f in id_run_dir.glob(f'**/*.{ext}'):
            if f.name not in _KEEP_LOGS:   # preserve our named log files
                f.unlink(missing_ok=True)
    # Keep: baseline.pdf, pipeline_output.tex, pipeline_output.pdf,
    #        demacro_report.json, pipeline.log, baseline_compile.log,
    #        output_compile.log, comparison.json, visual_diff/


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def _append_result(entry: dict) -> None:
    """Append a single result dict as one JSON line to results.jsonl."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSONL, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _rolling_success_rate(window: int = 20) -> float | None:
    """Return rolling success rate over the last *window* papers, or None."""
    if not RESULTS_JSONL.exists():
        return None
    lines = RESULTS_JSONL.read_text(encoding='utf-8').splitlines()
    recent = lines[-window:]
    if not recent:
        return None
    successes = sum(
        1 for line in recent
        if json.loads(line).get('success', False)
    )
    return successes / len(recent) * 100


def run(arxiv_ids: list[str] | None = None, seed: int = 0, n: int = 5,
        keep_runs: bool = False, pipeline_mode: str = 'raw',
        sampling: str = 'uniform',
        category_filter: list[str] | None = None) -> dict:
    """Run the full testing agent. Returns the manifest dict.

    Args:
        pipeline_mode:   ``'raw'`` (default) or ``'canonical'``.  See
                         :func:`_run_pipeline` for details.
        sampling:        Category sampling strategy — ``'uniform'`` (default)
                         draws from all ~170 arXiv categories; ``'legacy'``
                         uses the original five-category list.
        category_filter: Optional list of category prefixes (e.g. ``['math']``,
                         ``['cs', 'math']``).  Restricts sampling to matching
                         categories.  Ignored when *arxiv_ids* is given or
                         *sampling* is ``'legacy'``.
    """
    _acquire_lock()
    try:
        run_id = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S') + f'_{seed}'
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Step 2 — Acquire papers
        if arxiv_ids:
            papers = [{'arxiv_id': aid, 'category': 'user-provided'} for aid in arxiv_ids]
        else:
            papers = _sample_papers(n, seed, sampling=sampling,
                                    category_filter=category_filter)

        manifest: dict = {
            'run_id': run_id,
            'seed': seed,
            'pipeline_mode': pipeline_mode,
            'sampling': sampling,
            'category_filter': category_filter or [],
            'papers': [],
        }

        results_summary: list[dict] = []

        for paper in tqdm(papers, desc='Papers'):
            arxiv_id = paper['arxiv_id']
            paper_dir = run_dir / arxiv_id
            paper_dir.mkdir(exist_ok=True)
            raw_data = paper_dir / 'raw_data'

            # Download
            try:
                tarball = _download_arxiv(arxiv_id, paper_dir)
                sha = _sha256(tarball)
            except Exception as e:
                logger.error("Download failed for %s: %s", arxiv_id, e)
                results_summary.append({'arxiv_id': arxiv_id, 'status': 'download_failed'})
                continue

            ts = datetime.datetime.utcnow().isoformat() + 'Z'
            manifest['papers'].append({
                'arxiv_id': arxiv_id,
                'category': paper.get('category', ''),
                'download_timestamp': ts,
                'tarball_sha256': sha,
            })

            # Step 3 — Baseline compile
            baseline_pdf = paper_dir / 'baseline.pdf'
            baseline_log = paper_dir / 'baseline_compile.log'
            baseline_compile = _compile_latex(raw_data, baseline_pdf, baseline_log)
            if baseline_compile.get('timeout'):
                logger.warning("%s: baseline compile timeout — skipping", arxiv_id)
                results_summary.append({'arxiv_id': arxiv_id, 'status': 'baseline_compile_timeout'})
                continue
            if baseline_compile.get('exit_code', 0) != 0:
                logger.warning("%s: baseline compile failed — skipping", arxiv_id)
                results_summary.append({'arxiv_id': arxiv_id, 'status': 'baseline_compile_failed'})
                continue

            # Step 4 — Run pipeline
            try:
                _run_pipeline(raw_data, paper_dir, mode=pipeline_mode)
            except Exception as e:
                logger.error("%s: pipeline failed: %s", arxiv_id, e, exc_info=True)
                results_summary.append({
                    'arxiv_id': arxiv_id, 'status': 'pipeline_failed', 'error': str(e),
                })
                continue

            # Step 5 — Compile pipeline output.
            # raw mode:       compile pipeline_output.tex from raw_data so that
            #                 .bib / image paths resolve (BUG-7).
            # canonical mode: compile canonical.tex from the self-contained
            #                 canonical_output/ directory created by texphage_to_dir.
            output_pdf = paper_dir / 'pipeline_output.pdf'
            output_log = paper_dir / 'output_compile.log'
            if pipeline_mode == 'canonical':
                output_compile = _compile_latex(
                    paper_dir / 'canonical_output', output_pdf, output_log,
                    tex_file='canonical.tex',
                )
            else:
                output_compile = _compile_latex(
                    raw_data, output_pdf, output_log, tex_file='pipeline_output.tex'
                )

            # Step 6 — Compare
            comp = _compare(
                paper_dir, baseline_pdf, output_pdf,
                baseline_compile, output_compile,
            )
            (paper_dir / 'comparison.json').write_text(
                json.dumps(comp, indent=2, ensure_ascii=False)
            )

            result = {'arxiv_id': arxiv_id, 'status': 'ok', **comp}
            results_summary.append(result)
            severity = comp.get('severity', 'unknown')
            min_ssim = min(comp.get('ssim_per_page', [1.0]) or [1.0])
            logger.info(
                "%s: severity=%s, pages=%s→%s, min_ssim=%.3f, text_diff=%s",
                arxiv_id,
                severity,
                comp.get('baseline_pages', '?'),
                comp.get('output_pages', '?'),
                min_ssim,
                comp.get('text_diff_lines', '?'),
            )

            # Append to the persistent rolling results log (results.jsonl).
            _append_result({
                'arxiv_id': arxiv_id,
                'date': datetime.datetime.utcnow().isoformat() + 'Z',
                'category': paper.get('category', ''),
                'success': severity == 'OK',
                'severity': severity,
                'text_diff_lines': comp.get('text_diff_lines', 0),
                'min_ssim': round(min_ssim, 4),
                'failure_mode': comp.get('error_type'),
            })

            # Step 9 — Cleanup
            cleanup_run(paper_dir)

        manifest['results'] = results_summary
        (run_dir / 'manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False)
        )

        # Summary
        severities = [r.get('severity', 'unknown') for r in results_summary]
        print(f"\nRun {run_id} complete.")
        print(f"  Papers: {len(results_summary)}")
        print(f"  CRITICAL: {severities.count('CRITICAL')}")
        print(f"  HIGH:     {severities.count('HIGH')}")
        print(f"  MEDIUM:   {severities.count('MEDIUM')}")
        print(f"  LOW:      {severities.count('LOW')}")
        print(f"  OK:       {severities.count('OK')}")
        rolling = _rolling_success_rate(window=20)
        if rolling is not None:
            print(f"  Rolling success rate (last 20): {rolling:.1f}%")
        if keep_runs:
            print(f"\nResults written to: {run_dir}")
            print("Review comparison.json and visual_diff/ for each paper.")
        else:
            shutil.rmtree(run_dir, ignore_errors=True)
            print("\n(Run directory deleted — use --keep-runs to preserve for debugging.)")
        print("Add bugs to BUGS.md (see AGENTS.md Step 8).")

        return manifest

    finally:
        # Step 10 — Release lock
        _release_lock()


def main() -> None:
    parser = argparse.ArgumentParser(description='texphage Testing Agent')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--seed', type=int, default=0,
                       help='Random seed for paper sampling (default: 0)')
    group.add_argument('--ids', nargs='+', metavar='ARXIV_ID',
                       help='Specific arXiv IDs to test instead of sampling')
    parser.add_argument('--n', type=int, default=5,
                        help='Number of papers to sample (default: 5)')
    parser.add_argument('--keep-runs', action='store_true',
                        help='Keep run directory after completion (default: delete)')
    parser.add_argument('--pipeline', choices=['raw', 'canonical'], default='raw',
                        help=(
                            'raw (default): compile pipeline_output.tex from raw_data; '
                            'canonical: use texphage_to_dir — creates a self-contained '
                            'canonical_output/ directory with attachments copied in'
                        ))
    parser.add_argument('--sampling', choices=['uniform', 'legacy'], default='uniform',
                        help=(
                            'uniform (default): sample papers from all ~170 arXiv categories; '
                            'legacy: use the original five-category list (math.CT/AT, cs.LO) '
                            'for historical reproducibility'
                        ))
    parser.add_argument('--categories', nargs='+', metavar='PREFIX',
                        help=(
                            'Restrict sampling to categories matching one or more prefixes. '
                            'E.g. --categories math  samples only math.* categories; '
                            '--categories cs math  samples from cs.* and math.*; '
                            '--categories hep  samples hep-th, hep-ph, hep-lat, hep-ex. '
                            'Ignored when --ids is given or --sampling legacy is used.'
                        ))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    run(arxiv_ids=args.ids, seed=args.seed or 0, n=args.n,
        keep_runs=args.keep_runs, pipeline_mode=args.pipeline,
        sampling=args.sampling, category_filter=args.categories)


if __name__ == '__main__':
    main()
