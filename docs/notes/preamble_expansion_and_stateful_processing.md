# The Illusion of Separation: Preamble vs. Body in TeX

The current `texphage` architecture, which strictly separates `build_dictionary` (preamble) and `expand` (body), is based on a convenient but flawed premise. This note explores why this separation is insufficient and proposes a more robust, unified model that better emulates TeX's actual behavior.

## The Core Problem: The Preamble is an Executable Script

The fundamental issue is that a LaTeX preamble is not merely a static list of definitions. It is an executable script. TeX processes tokens sequentially, defining and expanding macros as it encounters them. The distinction between "preamble" and "body" is largely a convention for the user; for the compiler, it's a continuous stream of processing.

When `texphage` only collects definitions from the preamble and only expands them in the body, it misses an entire class of operations: **macro expansion within the preamble itself.**

## Where Definitions and Uses Can Occur: The TeX Reality

TeX's flexibility allows macro definitions and uses to be intertwined throughout a document.

1.  **Define-then-Use in Preamble (Very Common):** A user defines a helper macro and immediately uses it inside a command like `\author`, `	itle`, or `\date`.
    ```latex
    % Preamble
    
ewcommand{\myaffiliation}{University of TeX}
    \author{A. User	hanks{\myaffiliation}}
    	itle{A Study of Macros}
    ```
    Under the current model, `\myaffiliation` is added to the dictionary, but it is never expanded within the `\author` command's argument because expansion is deferred until the body.

2.  **Chained Definitions in Preamble (Common):** Definitions themselves can rely on other macros that were just defined.
    ```latex
    % Preamble
    
ewcommand{\projectname}{Project X}
    
ewcommand{\statusreport}{Status Report for \projectname}
    	itle{\statusreport}
    ```

3.  **Definitions in Body (Less Common but Valid):** Users can define local helper macros within the `document` environment.
    ```latex
    \begin{document}
    
ewcommand{\localacronym}{LA}
    Here we use the \localacronym.
    ...
    The \localacronym is defined locally.
    \end{document}
    ```
    The current model would not discover or expand `\localacronym` at all.

## What is the "Document Body"?

The user's question, "what the body of the document really is," is key.

*   **From TeX's perspective:** The "body" is simply the token stream that follows the execution of the `\begin{document}` macro. Crucially, the state of the compiler (e.g., all defined macros) at the end of the preamble processing carries over directly into the body.
*   **From `texphage`'s current perspective:** The "body" is the literal string between the `\begin{document}` and `\end{document}` markers.

This mismatch in perspective is the source of the problem. `texphage` treats the preamble and body as separate, isolated strings, when in fact TeX creates a continuous, stateful processing environment.

## Proposed Solution: A Unified, Stateful Expansion Model

To achieve higher fidelity, `texphage` must evolve from a two-step, stateless process to a single-pass, stateful one that more closely resembles TeX's execution.

The core idea is to **merge the `build_dictionary` and `expand` steps** into a single, iterative loop that processes the entire document from start to finish.

### Conceptual Algorithm:

1.  **Initialize a stateful dictionary** for macros.
2.  **Process the full document source** as a single string or token stream, from top to bottom.
3.  **Iterate through the source:**
    *   If the next token is a **macro definition** (`
ewcommand`, `\def`, etc.):
        *   Parse the definition.
        *   Add the new macro to the stateful dictionary.
        *   Consume (remove) the definition from the source so it doesn't appear in the final output.
    *   If the next token is a **user-defined macro** (i.e., it exists in our dictionary):
        *   Expand it in-place.
        *   **Crucially, rescan from the beginning of the newly expanded text**, as the expansion itself may contain other macros that need to be expanded.
    *   If the next token is a **built-in or package macro** that we don't expand away (e.g., `\section`, `	itle`, `\emph`):
        *   Do not expand the command itself.
        *   **Recursively apply the expansion process to its arguments.** For example, in `	itle{Report on \projectname}`, the process would be called on the argument `Report on \projectname`, which would transform it into `Report on Project X`.
    *   If the next token is **plain text**, append it to the output and continue.

### Benefits of this Approach:

*   **Fidelity:** This model correctly handles define-then-use patterns in the preamble, chained definitions, and local definitions in the body.
*   **Simplicity of State:** It eliminates the artificial separation of preamble/body, resulting in a single, coherent processing model.
*   **Architectural Soundness:** It aligns the tool's architecture with the fundamental operating principles of its target language, TeX.

## Conclusion and Recommendation

The current separation of definition and expansion is a significant architectural limitation that prevents `texphage` from correctly processing a wide range of common and valid LaTeX documents.

**It is strongly recommended that the `build_dictionary` and `expand` steps be refactored into a single, stateful, iterative processing loop.** While this is a substantial change, it is a necessary one to move the tool towards a more robust and accurate implementation. This change would fix the entire class of issues related to macro expansion context and represent a major step forward in the project's maturity.
