# Agentic Workflow Analysis

This document analyzes the dual-agent (Gemini and Claude) workflow defined in the repository, including the transition from the deprecated `AGENTS.md` to the current modular framework.

## 1. Overall Collaboration Model

The project employs a clear separation of concerns between two primary AI agents:

-   **Gemini (The Architect/Researcher):** Acts as a domain expert (LaTeX) and system architect. Gemini's role is to perform high-level research, identify and define tasks, analyze limitations, and specify what should be done. Gemini does not write or debug Python code.
-   **Claude (The Engineer):** Acts as the hands-on software engineer. Claude's role is to implement the tasks defined by Gemini, write tests, debug code, and perform all direct modifications to the `src/` and `tests/` directories.

This model establishes a "what" vs. "how" dynamic. Gemini determines the direction and priorities, while Claude handles the technical execution. Communication is mediated through structured files like `BUGS.md`, `TODO.md`, and various agent/skill specification documents. A key feature is the `[observed]` vs. `[inferred]` comment system, which enforces an empirical validation loop: Gemini can propose limitations based on documentation, but only Claude can confirm them through testing.

## 2. Gemini's Workflow

-   **Role:** LaTeX expert, researcher, critic, and architect.
-   **Core Task Loop:** Research LaTeX standards, other tools, and arXiv usage patterns → Identify high-ROI improvements or bugs → Write detailed, actionable entries in `TODO.md` or `BUGS.md` for Claude.
-   **Write Permissions:** Strictly limited to documentation and planning files (`BUGS.md`, `TODO.md`, `.gemini/notes/`, `macros.md`, `inclusions.md`) and adding `[inferred]` limitation comments to `demacro.py` and `unfold.py`.
-   **Structured Agents:** Gemini has two main triggered agents:
    -   `InclusionCoverageAgent`: Audits `unfold.py` and generates `inclusions.md` to document file inclusion coverage.
    -   `MacroCoverageAgent`: Audits `demacro.py` and generates `macros.md` to document macro definition coverage.
    These agents produce high-level, human-readable documentation that summarizes the state of the implementation, which is a key part of Gemini's architectural oversight role.

## 3. Claude's Workflow

-   **Role:** Software and testing engineer.
-   **Core Task Loop:** Pick up a task from `BUGS.md` or `TODO.md` → Follow a strict, test-driven protocol to implement the fix or feature → Verify against the codebase standards and tests → Commit the changes.
-   **Structured Agents:** Claude's work is heavily structured into triggered agents:
    -   `coding-agent`: The primary implementation workflow for fixing bugs. It follows a mandatory TDD cycle, using the "playground" for ground truth.
    -   `testing-agent`: The engine for discovering new work. It automates downloading arXiv papers, running the pipeline, comparing outputs, and logging discrepancies to `BUGS.md`.
    -   `quarterly-audit`: A discovery agent for proactively finding new, unhandled macro patterns in the wild (CTAN).
-   **Skills (`.claude/skills/`):** This is the most significant architectural feature of Claude's workflow. Common, reusable protocols are factored out into "skills" that can be loaded by agents. This is a major improvement over monolithic specs.
    -   `failure-taxonomy`: Defines the crucial A/B/C bug classification system, providing a powerful diagnostic starting point.
    -   `playground-protocol`: Mandates that all test assertions be anchored to the actual output of the TeX compiler via a helper script, preventing agents from testing against incorrect assumptions.
    -   `regex-danger-zone`: Enforces strict safety protocols around modifying the complex and fragile regex patterns.
    -   `bug-management`: Standardizes bug reporting, commit messages, and the bug lifecycle.

## 4. `AGENTS.md` Migration Analysis

The `AGENTS.md` file is explicitly marked as deprecated and has been successfully superseded by the new, modular framework located in `.claude/` and `.gemini/`.

-   **Evolution:** The old system was a single, monolithic document. The new system is superior in its modularity, separation of concerns, and reusability.
    -   **Agent Specs:** Each agent now has its own specification file (e.g., `.claude/agents/coding-agent.md`).
    -   **Composable Skills:** The introduction of the `.claude/skills/` directory is the most important innovation. It allows for defining complex, reusable procedures once and composing them as needed, which reduces redundancy and enforces consistency.

-   **Translation of Concepts:** All critical ideas from `AGENTS.md` have been preserved and improved upon in the new framework.
    -   The core agent workflows (Testing, Coding, Audit) are now defined in their own spec files.
    -   The Failure Mode Taxonomy, Playground Templates, DANGER ZONE rules, and BUGS.md format are now encapsulated in their respective "skill" files.
    -   The locking protocol and directory structures remain part of the agent specs.
    -   The "Advanced Agent Capabilities (Future Vision)" section from `AGENTS.md` was aspirational and has not been formally translated, which is appropriate. These ideas could be captured in `TODO.md` or a `.gemini/notes/` file for future consideration.

## Conclusion

The agentic workflow is well-structured, robust, and clearly defines the collaborative model between the research/architect (Gemini) and engineering (Claude) roles. The migration from the monolithic `AGENTS.md` to a modular system of agent specs and composable skills is a significant architectural improvement, enhancing clarity, reducing duplication, and making the system more scalable. All important operational knowledge from the deprecated file has been successfully carried over into this superior structure.
