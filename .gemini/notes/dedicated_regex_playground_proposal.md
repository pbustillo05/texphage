# A Dedicated Regex Playground: From Diagnostics to Development

## The Core Insight

The current "Regex Playground" is a diagnostic procedure, not a development environment. It is designed to answer the question, "Which part of our existing `demacro` pipeline failed?" It does not provide a sandbox to answer the more fundamental question, "Does this new regex pattern I am writing work as expected?"

A regular expression, especially the complex, multi-level patterns used in `texphage`, is a miniature program. To treat it as something that can only be tested once fully integrated into the main application is like asking a developer to write a complex function without ever being able to run it in isolation. A dedicated playground is needed to fill this gap.

## Current State vs. Proposed Vision

*   **Current (Implicit Procedure):** The "Pattern Probe" from the `failure-taxonomy` skill is a *diagnostic* tool. It uses the pre-built, monolithic `find_all` regex to see which major branch of the system is failing. It is not designed for testing a new, isolated pattern.

*   **Proposed (Explicit Tool):** We should create a new, standalone script, `scripts/regex_playground.py`. This tool's purpose is to test **any arbitrary regex pattern against any arbitrary text in isolation**. This shifts its function from diagnostics to **iterative development and validation**.

## Why This is a Necessary Evolution

1.  **True Isolation:** It allows a pattern to be developed and perfected without the confounding variables of the entire `demacro` pipeline. When a pattern fails inside the massive `find_all` alternation, it can be difficult to know why. Testing it in isolation makes debugging trivial.

2.  **Empowering Development:** To extend `texphage` with support for a new command, Claude needs a sandbox to build the required regex. The workflow should be:
    *   Try a pattern.
    *   Inspect the captured groups.
    *   Refine the pattern.
    *   Try again.
    This iterative loop is fundamental to regex development and is not supported by the current diagnostic procedure.

3.  **Clarity and Precision:** The output of this tool would be focused entirely on the regex engine's view of the world: a precise, named list of all captured groups. This is far more direct and useful for pattern development than inspecting the `macro_dict` produced by `build_dictionary`, which is an abstraction layer above the raw regex match.

## Proposed Tool: `scripts/regex_playground.py`

This would be a command-line tool with the following features:

*   **Interface:**
    ```bash
    python scripts/regex_playground.py --text "LaTeX string" --pattern "Regex pattern"
    ```
    or to test a complex pattern already in the codebase:
    ```bash
    python scripts/regex_playground.py --file "test.tex" --pattern-from "src.texphage.demacro:find_new_com"
    ```

*   **Functionality:**
    1.  Takes a text source (string or file) and a regex pattern (string or imported from a module).
    2.  Executes `regex.finditer()` to find all non-overlapping matches.
    3.  For each match, it would print a clear report showing the full match and, most importantly, a key-value list of all **named capture groups**.

*   **Example Output:**
    ```
    Match 1/1:
    Full match: "
ewcommand{\foo}[1][default]{body}"
    Named Groups:
      - new_com_csname:   "\foo"
      - new_com_num_args: "1"
      - new_com_default1: "[default]"
      - new_com_content:  "{body}"
    ```

## The New Agentic Workflow for Extending Coverage

This tool enables a much more robust and logical workflow for Claude:

1.  **Hypothesis:** A new command, `\bar`, needs to be supported.
2.  **Pattern Development (Regex Playground):** Claude uses the new `regex_playground.py` to iteratively craft a pattern for `\bar`, testing it against various examples until the named capture groups are reliably correct.
3.  **Integration:** Claude adds the now-validated pattern into `_regex.py` and the `find_all` alternation in `demacro.py`.
4.  **End-to-End Validation (LaTeX Playground):** Claude uses the existing `latex_playground.py` (ideally the vision-based version) to confirm that the integrated pattern works correctly within the full pipeline and produces the desired final output.

By creating this tool, we are giving Claude the proper sandbox required for the "tiny programs" that our regexes are. It closes a critical gap in the agentic workflow, elevating Claude from a debugger of the existing system to a true developer capable of extending it.
