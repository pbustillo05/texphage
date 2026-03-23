# Prompt for Claude: Build an Evaluation Harness for xy_to_tikz.py

The goal is to rigorously evaluate the visual fidelity of the `xy_to_tikz.py` script. You will create a new script in the `scripts/` directory to orchestrate this evaluation. The script will take a source `.tex` file, run the conversion, compile both versions, and compare the resulting PDFs.

Here are the detailed steps:

### 1. Create the Evaluation Script

Create a new file: `scripts/evaluate_xy_conversion.py`.

This script should:
a. Accept a single command-line argument: the path to a `.tex` file containing an `xymatrix` environment.
b. Create a temporary directory in `tests/runs/` to store the output files (e.g., `original.pdf`, `converted.tex`, `converted.pdf`, diff images).

### 2. Implement the Conversion and Compilation Logic

a. **Copy `xy_to_tikz.py`**: The logic from `xy_to_tikz.py` should be imported and used by your new script. You can either import it directly or copy the necessary functions. Ensure you change `import re` to `import regex as re` to align with project standards and prevent silent failures on complex patterns.
b. **Compile the Original**: Use `latexmk` to compile the original input `.tex` file into a PDF (`original.pdf`).
c. **Perform the Conversion**:
    i. Read the content of the input `.tex` file.
    ii. Run the `xy_to_tikzcd()` function on the content.
    iii. In the resulting string, you must also modify the preamble:
        - Remove any instance of `\usepackage{xy}` or `\usepackage[all]{xy}`.
        - Add `\usepackage{tikz-cd}` if it's not already there.
    iv. Save this new content to `converted.tex`.
d. **Compile the Converted**: Use `latexmk` to compile `converted.tex` into a PDF (`converted.pdf`).

### 3. Compare the PDFs

a. Use the `pdf2image` library to convert both `original.pdf` and `converted.pdf` into a series of PNG images (one per page).
b. For each pair of corresponding pages, use `scikit-image`'s `structural_similarity` function (SSIM) to compute their similarity. Also, calculate the Mean Squared Error (MSE).
c. If the images are not identical, generate a visual diff image showing the differences.
d. The script should print a summary report to the console:
    - For each page: SSIM score, MSE, and the path to the diff image if one was created.
    - A final verdict: "SUCCESS: PDFs are visually identical." or "FAILURE: PDFs are visually different."

### 4. Create a Test Case

To test your script, create a new fixture file: `tests/fixtures/xymatrix_simple/main.tex`. Use the following content:

```latex
\documentclass{article}
\usepackage[all]{xy}
\usepackage{tikz-cd} % Include for baseline comparison

\begin{document}

A simple diagram:
\xymatrix{
  A \ar[r]^f \ar[d]_g & B \ar[d]^{h} 
  C \ar[r]_k & D
}

A diagram with different spacing:
\xymatrix@C=4cm@R=1pc{
    A \ar[r,"f"] \ar[d,swap,"g"] & B \ar[d,"h"] 
    C \ar[r,"k"] & D
}

\end{document}
```

### 5. Final Instructions

Your script should be robust and clean. Use `subprocess` to call `latexmk`. Ensure all temporary files are handled cleanly within the designated run directory. Your final output should clearly state whether the conversion was successful from a visual fidelity perspective.
