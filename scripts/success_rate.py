"""Print rolling success rate from tests/runs/results.jsonl.

Usage:
    python scripts/success_rate.py
    python scripts/success_rate.py --window 20
    python scripts/success_rate.py --batches 10

This script reads the append-only results log written by test_fidelity.py
and reports:
  - Rolling success rate over the last N papers (default 20).
  - Per-failure-mode breakdown.
  - A simple trend: success rate for each of the last B batches of papers
    (default batches of 5), oldest to newest.

Success definition: severity == 'OK' (zero or negligible text diff, SSIM >= 0.95,
correct page count).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO_ROOT    = Path(__file__).parent.parent
RESULTS_FILE = REPO_ROOT / 'tests' / 'runs' / 'results.jsonl'


def load_results() -> list[dict]:
    """Return all result records from results.jsonl, oldest first."""
    if not RESULTS_FILE.exists():
        return []
    records = []
    for line in RESULTS_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def success_rate(records: list[dict]) -> float:
    """Return success rate (0–100) for a list of records."""
    if not records:
        return 0.0
    return sum(1 for r in records if r.get('success', False)) / len(records) * 100


def main() -> None:
    parser = argparse.ArgumentParser(description='texphage success rate reporter')
    parser.add_argument('--window', type=int, default=20,
                        help='Number of recent papers for rolling rate (default 20)')
    parser.add_argument('--batches', type=int, default=10,
                        help='Number of batches to show in trend (default 10)')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='Papers per trend batch (default 5)')
    args = parser.parse_args()

    records = load_results()

    if not records:
        print(f"No results found in {RESULTS_FILE}")
        print("Run the testing agent first: say 'Run testing agent on seed 42'")
        return

    total = len(records)
    recent = records[-args.window:]
    rolling = success_rate(recent)

    print(f"\ntexphage success rate — {total} total papers tested")
    print("=" * 52)
    print(f"  Rolling rate (last {min(len(recent), args.window)}): {rolling:.1f}%   "
          f"[target: 90.0%]  {'✓' if rolling >= 90 else '✗'}")
    print()

    # Failure mode breakdown for the rolling window.
    failures = [r for r in recent if not r.get('success', False)]
    if failures:
        mode_counts: Counter[str] = Counter(
            r.get('severity', 'unknown') for r in failures
        )
        error_counts: Counter[str] = Counter(
            r.get('failure_mode') or 'none' for r in failures if not r.get('success')
        )
        print(f"  Failures in last {len(recent)} ({len(failures)} total):")
        for severity in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'unknown'):
            count = mode_counts.get(severity, 0)
            if count:
                print(f"    {severity:10s}: {count}")
        print()
        print("  Error type breakdown:")
        for error_type, count in error_counts.most_common():
            print(f"    {error_type:40s}: {count}")
        print()
    else:
        print(f"  All {len(recent)} recent papers succeeded.")
        print()

    # Trend: last B batches of batch_size papers.
    batch_size = args.batch_size
    n_batches  = args.batches
    available  = total // batch_size
    show       = min(available, n_batches)

    if show < 2:
        print("  (Not enough data for trend — need at least 2 completed batches.)")
        return

    print(f"  Trend (last {show} batches of {batch_size}):")
    bar_width = 30
    for i in range(show):
        # Index from oldest to newest within the last show*batch_size records.
        offset = total - show * batch_size + i * batch_size
        batch = records[offset: offset + batch_size]
        rate  = success_rate(batch)
        filled = round(rate / 100 * bar_width)
        bar    = '█' * filled + '░' * (bar_width - filled)
        start_date = batch[0].get('date', '')[:10]
        print(f"    {start_date}  [{bar}]  {rate:5.1f}%")
    print()

    # Per-category breakdown (top failures).
    cat_totals: Counter[str] = Counter(r.get('category', '') for r in recent)
    cat_fails:  Counter[str] = Counter(
        r.get('category', '') for r in recent if not r.get('success', False)
    )
    if cat_fails:
        print("  Categories with most failures (rolling window):")
        for cat, fail_count in cat_fails.most_common(5):
            total_cat = cat_totals[cat]
            print(f"    {cat:20s}: {fail_count}/{total_cat} failed")
        print()


if __name__ == '__main__':
    main()
