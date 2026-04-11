# Prompt for Claude: Implement a LaTeX "Pretty-Printer" for Compacted Output

## 1. Goal: Human-Readable Output

The primary `texphage` pipeline produces a highly compacted, single-line `.tex` string. This is efficient for machines but difficult for humans to inspect. Your task is to build a "pretty-printer" that reformats this compacted code into a structured, human-readable layout.

This feature must be available in two ways:
1.  As an optional final step in the `texphage()` pipeline.
2.  As a standalone command-line tool `texphage-format`.

**Guiding Principle:** 
- The formatting must *never* alter the compiled PDF output. This means we will only add newlines where LaTeX treats them as whitespace, primarily by replacing existing single spaces.
- All instances of `\par` must be replaced by newlines (unless impossible).
- Every English sentence should have its own line.
- In mathematical environments, code should be indented and newlines should be created (with the appropriate `%`) for optimal readability.

## 2. Your Task: Build the Formatter and Standalone Tool

### Step 2.1: Create the Core Formatting Function

Create a new file `src/texphage/formatters.py`. In this file, define a public function:
`def pretty_print_latex(compacted_latex: str) -> str:`

This function will contain the core formatting logic. Here is the required implementation strategy:

1.  **Split Document**: First, split the input string into three parts: the content before `\begin{document}`, the `\begin{document}` command itself, and the content after it.
2.  **Format the Preamble**:
    *   Take the preamble part.
    *   Use `regex.sub()` to insert a newline before `\documentclass` and each `\usepackage`. The pattern should look something like `r'\s*(\documentclass|\usepackage)'` and the replacement `r'

\1'`.
3.  **Format the Body**:
    *   Take the body part (everything between `\begin{document}` and `\end{document}`).
    *   **Restore Paragraphs**: Replace all instances of ` \par ` with `

\par

`. This is the most important step for readability.
    *   **Isolate Environments**: To further improve structure, insert newlines around major block-level environments. Use a regex to find `\begin{...}` and `\end{...}` for a list of common environments and add newlines before and after them.
        *   **Target environments**: `equation`, `align`, `gather`, `itemize`, `enumerate`, `description`, `figure`, `table`, `theorem`, `lemma`, `proof`, and their starred variants (`equation*`, etc.).
        *   The pattern should look like `r'\s*(\begin\{(' + env_list + r')\*?\})'` and `r'\s*(\end\{(' + env_list + r')\*?\})'`, where `env_list` is a `|`-separated string of the environment names. Insert a newline before `\begin` and after `\end`.
4.  **Assemble the Final String**: Combine the formatted preamble, `\begin{document}`, the formatted body, and `\end{document}`, ensuring they are separated by appropriate newlines.

### Step 2.2: Create the Standalone CLI Tool

1.  In `src/texphage/cli.py`, create a new `main` function for the formatter tool (e.g., `main_format`).
2.  Use `argparse` to handle command-line arguments:
    -   `input_file`: The compacted `.tex` file to read.
    -   `--output` or `-o`: An optional output file path. If not provided, the formatted code should be printed to standard output.
3.  The function will read the input file, call `formatters.pretty_print_latex()`, and either print the result or write it to the specified output file.
4.  Register the new tool in `pyproject.toml`:
    ```toml
    [project.scripts]
    texphage-convert-xy = "texphage.cli:main_convert_xy"
    texphage-format = "texphage.cli:main_format"
    ```

## 3. Your Second Task: Integrate into the `texphage` Pipeline

### Step 3.1: Modify the `texphage()` API

In `src/texphage/pipeline.py`, add a new boolean argument to the `texphage()` function:

```python
def texphage(
    # ... existing arguments
    pretty_print: bool = False,
) -> str:
    # ...
```

### Step 3.2: Add the Final Formatting Step

At the very end of the `texphage()` function, just before the final `return`, add the conditional formatting step:

```python
    # ... final_compacted_string is ready
    if pretty_print:
        return pretty_print_latex(final_compacted_string)
    else:
        return final_compacted_string
```
Make sure to import `pretty_print_latex` from `texphage.formatters`.
