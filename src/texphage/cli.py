"""Command-line interface for texphage.

Entrypoints
-----------
texphage <src>                  → canonical.tex to stdout
texphage <src> --out PATH       → write canonical.tex to PATH
texphage <src> --out DIR        → write canonical.tex + attachments to DIR
texphage <src> --json           → JSON {"tex": "...", "attachments": [...]}

texphage-unfold <src>           → flat .tex to stdout
texphage-unfold <src> --out PATH → write flat .tex to PATH
"""
from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

from texphage.pipeline import texphage, texphage_to_dir
from texphage.unfold import unfold


def _error(msg: str, code: int = 1) -> None:
    """Write a JSON error to stderr and exit."""
    json.dump({"error": msg, "code": code}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def main() -> None:
    """Full pipeline: unfold + demacro → canonical .tex."""
    parser = ArgumentParser(
        prog="texphage",
        description=(
            "Process a LaTeX project into canonical form "
            "(unfold multi-file → expand macros → minimal preamble)."
        ),
    )
    parser.add_argument("src", help="Source .tex file or project directory.")
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help=(
            "Output destination. If PATH ends with .tex, write canonical.tex there. "
            "Otherwise treat PATH as a directory and write canonical.tex + attachments into it."
        ),
    )
    parser.add_argument(
        "--main",
        metavar="FILE",
        default=None,
        help="Main .tex filename inside src (auto-detected if omitted).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON {\"tex\": ..., \"attachments\": [...]} instead of plain .tex.",
    )
    args = parser.parse_args()

    src = Path(args.src)
    if not src.exists():
        _error(f"Source not found: {src}")

    # If src is a file, treat its parent as src_dir and the file as main_tex.
    if src.is_file():
        src_dir = src.parent
        main_tex = src.name
    else:
        src_dir = src
        main_tex = args.main

    try:
        if args.out and not Path(args.out).suffix == ".tex":
            # Directory output: write canonical.tex + attachments
            out = Path(args.out)
            canonical_path = texphage_to_dir(src_dir, out, main_tex)
            if args.json:
                json.dump({"canonical_path": str(canonical_path)}, sys.stdout)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(f"Written: {canonical_path}\n")
        else:
            canonical_tex, attachments = texphage(src_dir, main_tex)
            if args.out:
                out = Path(args.out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(canonical_tex, encoding="utf-8")
                if not args.json:
                    sys.stdout.write(f"Written: {out}\n")
            elif args.json:
                payload = {
                    "tex": canonical_tex,
                    "attachments": [
                        {"tex_ref": a.tex_ref, "src_path": str(a.src_path)}
                        for a in attachments
                    ],
                }
                json.dump(payload, sys.stdout)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(canonical_tex)
    except Exception as exc:  # noqa: BLE001
        _error(str(exc))


def main_unfold() -> None:
    """Unfold only: flatten multi-file project → single .tex string."""
    parser = ArgumentParser(
        prog="texphage-unfold",
        description="Flatten a multi-file LaTeX project into a single .tex file.",
    )
    parser.add_argument("src", help="Source .tex file or project directory.")
    parser.add_argument(
        "--out",
        metavar="FILE",
        default=None,
        help="Write output to FILE instead of stdout.",
    )
    parser.add_argument(
        "--main",
        metavar="FILE",
        default=None,
        help="Main .tex filename inside src (auto-detected if omitted).",
    )
    args = parser.parse_args()

    src = Path(args.src)
    if not src.exists():
        _error(f"Source not found: {src}")

    if src.is_file():
        src_dir = src.parent
        main_tex = src.name
    else:
        src_dir = src
        main_tex = args.main

    try:
        flat = unfold(src_dir, main_tex)
    except Exception as exc:  # noqa: BLE001
        _error(str(exc))
        return  # unreachable; satisfies type checkers

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(flat, encoding="utf-8")
        sys.stdout.write(f"Written: {out}\n")
    else:
        sys.stdout.write(flat)
