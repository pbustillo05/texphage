# Prompt for Claude: Architecting an Optional and Standalone XY-to-TikZ Pipeline

## 1. Project Vision: A "Near-Perfect" Canonicalization Module

We are evolving `texphage` to support a new class of experimental, "near-perfect" canonicalization features. The XY-to-TikZ conversion is the pilot for this initiative. This functionality will have two entry points: an optional step in the main `texphage` pipeline and a standalone converter tool.

**The Core Philosophy:**
- **Dual-Use**: The core conversion logic will be shared between the internal pipeline and a new, user-facing standalone tool.
- **Opt-In Complexity**: When used within the main pipeline, this feature will be disabled by default.
- **Measurable Fidelity**: We will not aim for pixel-perfection. Instead, we define an acceptable "distance" (tolerance) between the original and converted PDFs, measured by default with a Structural Similarity Index (SSIM) of 0.99.
- **Fail-Safe Operation**: If a conversion's visual difference exceeds the tolerance, the operation MUST fail gracefully. The internal pipeline will revert to the original source, and the standalone tool will report an error.
- **Dedicated Ownership**: The core logic will be the responsibility of a new, specialized agent (`xy_tikz_fidelity_agent`) whose long-term mission is to improve its coverage and fidelity.

## 2. Your Task: Build the Core Logic and a Standalone Tool

Your first task is to build the core conversion and fidelity-checking logic and expose it through a standalone command-line tool.

### Step 2.1: Refactor Conversion Logic

Create a new file: `src/texphage/_xy_converter.py`.
- This file will contain the pure string-manipulation logic adapted from `xy_to_tikz.py`. Ensure it uses `import regex as re`.
- It should have no side effects (no printing, no file I/O).
- It should provide two main functions:
    - `convert_xy_body(tex_body: str) -> str`: Runs the `\xymatrix` to `tikzcd` replacement.
    - `convert_xy_preamble(tex_preamble: str) -> str`: Removes `\usepackage{xy}` and adds `\usepackage{tikz-cd}`.

### Step 2.2: Build the Orchestration and Fidelity-Check Function

Create a new file: `src/texphage/converters.py`. This will house the public-facing API.
- Create a function `convert_xy(latex_string: str, tolerance: float = 0.99) -> str`.
- This function orchestrates the entire "compile-check-revert" process for a given string:
    1.  **Isolate**: Create a temporary directory for `latexmk` runs.
    2.  **Compile Original**: Compile the `latex_string`. If it fails, raise an exception.
    3.  **Convert**: Use the functions from `_xy_converter.py` to get the `converted_latex_string`.
    4.  **Compile Converted**: Compile the new string. If it fails, raise an exception detailing that the conversion produced invalid LaTeX.
    5.  **Fidelity Check**: Compare the two PDFs using SSIM.
    6.  **Return or Fail**: If the SSIM score for all pages is `>= tolerance`, return the `converted_latex_string`. Otherwise, raise a `FidelityError` (a custom exception you should define) with a message detailing the failed SSIM score.

### Step 2.3: Create the Standalone CLI Tool

1.  Create a new file `src/texphage/cli.py`.
2.  Using `argparse`, create a main function for the CLI tool. It should accept the following arguments:
    - `input_file`: Path to the `.tex` file to convert.
    - `output_file`: Path to write the converted `.tex` file.
    - `--tolerance`: An optional float to override the default SSIM tolerance of 0.99.
    - `--force`: An optional flag to write the output file even if the fidelity check fails.
3.  The CLI's main function will:
    - Read the `input_file`.
    - Call `converters.convert_xy()`.
    - Handle any exceptions (e.g., `FidelityError`), print informative messages to the user.
    - Write the result to the `output_file`. If `--force` is used, the file is written even after a `FidelityError`.
4.  Add the CLI entry point to `pyproject.toml`:
    ```toml
    [project.scripts]
    texphage-convert-xy = "texphage.cli:main_convert_xy"
    ```

## 3. Your Second Task: Integrate into the `texphage` Pipeline

Once the standalone tool and core `convert_xy` function are complete, integrate it into the main pipeline.

### Step 3.1: Modify the Public API

In `src/texphage/pipeline.py`, update the `texphage()` signature:
```python
def texphage(
    # ... existing arguments
    convert_xy_to_tikz: bool = False,
    xy_tikz_tolerance: float = 0.99,
) -> str:
    # ...
```

### Step 3.2: Implement the Pipeline Logic

Inside `texphage()`, after `unfold`, add the logic to call your new converter.
```python
tex_string = unfold_result.flat_latex

if convert_xy_to_tikz and r'\xymatrix' in tex_string:
    print("INFO: \\xymatrix detected. Attempting XY-to-TikZ conversion with fidelity check...")
    try:
        converted_string = convert_xy(
            latex_string=tex_string,
            tolerance=xy_tikz_tolerance,
        )
        print("INFO: XY-to-TikZ conversion successful and within tolerance.")
        tex_string = converted_string
    except Exception as e: # Catch FidelityError and others
        print(f"WARNING: XY-to-TikZ conversion failed or exceeded tolerance ({e}). Proceeding with original XY.")
```
This reuses the robust, exception-based logic from the `converters` module.

## 4. The `xy_tikz_fidelity_agent` (Context)

This is the definition of the specialist agent that will improve the core logic in `_xy_converter.py` over time. Your current task is to build the architecture in which this future agent will operate.
- **Mission**: Systematically improve the XY-to-TikZ converter.
- **Core Tasks**:
    1.  Find real-world `xymatrix` examples from arXiv that cause exceptions or have low fidelity scores.
    2.  Iteratively enhance the conversion regex and logic.
    3.  Tune dimension approximations to minimize visual differences and improve SSIM scores.
