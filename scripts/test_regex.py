#!/usr/bin/env python
import argparse
import importlib
import subprocess
import sys
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from texphage.demacro import preprocessing

def main():
    """
    Tests a single regex pattern from _regex.py against a single .tex file.
    """
    parser = argparse.ArgumentParser(description="Test a single texphage regex pattern.")
    parser.add_argument("pattern_name", help="The name of the regex pattern object in _regex.py (e.g., '_NEW_COMMAND_RE')")
    parser.add_argument("test_file", type=Path, help="Path to the .tex test file.")
    args = parser.parse_args()

    if not args.test_file.exists():
        print(f"Error: Test file not found at {args.test_file}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Ensure the LaTeX snippet is valid by compiling it
    print(f"INFO: Compiling {args.test_file} to verify it is valid LaTeX...")
    try:
        subprocess.run(
            ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', '-output-directory=' + str(args.test_file.parent), str(args.test_file)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        print("INFO: LaTeX compilation successful.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"Error: LaTeX compilation failed for {args.test_file}", file=sys.stderr)
        print("--- STDOUT ---
" + e.stdout.decode(errors='ignore'), file=sys.stderr)
        print("--- STDERR ---
" + e.stderr.decode(errors='ignore'), file=sys.stderr)
        sys.exit(1)


    # Step 2: Import the regex pattern
    try:
        regex_module = importlib.import_module("texphage._regex")
        pattern = getattr(regex_module, args.pattern_name)
    except (ImportError, AttributeError):
        print(f"Error: Could not import pattern '{args.pattern_name}' from texphage._regex", file=sys.stderr)
        sys.exit(1)

    # Step 3: Read and preprocess the file
    raw_content = args.test_file.read_text()
    preamble, _, _ = preprocessing(raw_content)

    # Step 4: Run the regex and report result
    print(f"INFO: Running pattern {args.pattern_name} against preprocessed content...")
    match = pattern.search(preamble)

    if match:
        print("
--- RESULT ---")
        print("MATCH")
        print("
--- CAPTURED GROUPS ---")
        for group, value in match.groupdict().items():
            if value is not None:
                print(f"  {group}: {value!r}")
    else:
        print("
--- RESULT ---")
        print("NO MATCH")

if __name__ == "__main__":
    main()
