# Proposal: Replace Quarterly Audit with a Regex Audit Agent

## 1. Motivation

The current `quarterly-audit` agent is too generic for the specific challenges of `texphage`. Our primary source of bugs and regressions is not general code rot, but a subtle misalignment between three things:
1.  **Canonical LaTeX Syntax:** The full, often arcane, set of valid syntax that the TeX compiler accepts for a given command.
2.  **Regex Implementation:** The actual pattern in `_regex.py` that attempts to capture this syntax.
3.  **Documented Intent:** The comments in `demacro.py` that describe what the regex is *supposed* to do.

When these three drift apart, the pipeline fails silently. A generic audit is unlikely to catch this. We need a specialist.

## 2. The Proposal

I propose we deprecate the `quarterly-audit` agent and create a new, highly-focused **Regex Audit Agent**.

**Mandate:** To systematically verify every regex in `_regex.py` and achieve a 1:1:1 correspondence between documented intention, regex behavior, and canonical LaTeX syntax.

## 3. Workflow

This agent would operate on a per-regex basis, executing the following workflow:

1.  **Target Selection:** The agent selects a regex to analyze from `_regex.py` (e.g., the pattern for `
ewcommand`).
2.  **Intent Parsing:** It reads the corresponding documentation in `demacro.py` to understand the *claimed* behavior.
3.  **Test Case Generation (The Core Task):** Drawing on my embedded LaTeX knowledge (and potentially external resources like the TeXbook or CTAN documentation), the agent generates a comprehensive set of test snippets for the target command. This must include:
    *   **Standard cases:** The most common usage.
    *   **Edge cases:** Permutations of whitespace, optional arguments, `*`-variants, strange but valid brace patterns, etc.
    *   **Negative cases:** Malformed syntax that the regex should *not* match.
4.  **Regex Playground Execution:** The agent runs the targeted regex against each snippet in a sandboxed "regex playground." This provides a rapid, isolated confirmation of what the pattern *actually* matches, free from the noise of the full pipeline. This answers the question: "Does the pattern do what we think it does?"
5.  **LaTeX Playground Execution:** The agent then runs the same snippets through the full `latex_playground.py`. This provides semantic and visual ground truth from the `latexmk` compiler. This answers the question: "Does our interpretation of the syntax produce the correct output?"
6.  **Synthesize and Report:** The agent compares the results from all three sources: the documented intent, the regex match result, and the compiled LaTeX output.
    *   If all three align, the regex is certified.
    *   If a discrepancy is found, the agent automatically generates a `BUGS.md` or `TODO.md` entry. This entry will be highly actionable, containing the exact failing snippet, the expected outcome, and the observed outcome.

## 4. Benefits

This approach transforms our testing from a reactive, manual process into a proactive, automated one. It provides:

*   **Deep, Systematic Verification:** Ensures our regexes are robust against real-world LaTeX, not just the "happy path."
*   **Living Documentation:** Forces our comments and documentation to be rigorously tested and accurate.
*   **Focused ROI:** Directs agentic effort at the most complex and fragile part of the system.
*   **Scalable Expertise:** It allows my specialized knowledge of LaTeX syntax to be encoded into a repeatable, automated process that Claude can execute at any time.

This is a far more valuable use of agentic cycles than a generic quarterly review.
