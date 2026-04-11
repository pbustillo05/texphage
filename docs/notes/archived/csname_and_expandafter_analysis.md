# Analysis: Parsing `\csname` and `\expandafter`

**Preamble:** This note provides architectural guidance for implementing support for `\csname` and `\expandafter`, identified as the #1 priority in the triage of 2026-03-23. This is a fundamental TeX feature, and supporting it is critical for improving `texphage`'s coverage.

## The Core Problem

The current parsing model in `demacro.py` (`find_all` regex) is based on finding literal, static command names in definitions. For example, `\def\foo...` is easy to find because `\foo` is a literal string.

`\csname` breaks this model. In a construct like `\expandafter\def\csname my@cmd\endcsname{...}`, the name of the command being defined (`\my@cmd`) does not exist as a literal string. It must be *constructed* by the TeX engine.

The challenge is that the content between `\csname` and `\endcsname` is itself subject to expansion. For example:
```latex
\def\prefix{my@}
\def
ame{cmd}
\expandafter\def\csname\prefix
ame\endcsname{...} % Defines \my@cmd
```
To find the real command name, the parser must expand `\prefix` and `
ame` *before* it can know what command is being defined.

## Architectural Proposal

A simple regex pre-pass to replace `\csname` is not feasible due to the nested expansion rules. The logic must be integrated into the main `build_dictionary` function in `src/texphage/demacro.py`.

The `find_all` regex should be modified to also capture `\expandafter` as a token. Then, the `build_dictionary` loop needs to be stateful.

**Proposed Logic:**

1.  **Modify `find_all`**: Add a new branch to the main regex to capture `\expandafter`.
    ```regex
    find_all = re.compile(r'(?<expandafter>\expandafter)|(?<def>...)|...')
    ```

2.  **Stateful `build_dictionary` Loop**: The loop that iterates over matches from `find_all` needs to handle what comes *after* an `\expandafter`.

    ```python
    # Inside build_dictionary(tex)
    expandafter_stack = 0
    macros = list(re.finditer(find_all, tex))
    i = 0
    while i < len(macros):
        macro = macros[i]
        if macro.group('expandafter'):
            expandafter_stack += 1
            i += 1
            continue # Don't reset the stack, just look at the next token

        # If we have expandafters on the stack and see a definition command...
        if expandafter_stack > 0 and macro.group('def'):
             # ... and the next token is \csname ...
             next_macro = macros[i+1] # Simplified, needs bounds checks
             if next_macro.group('csname'): # Assuming \csname is also in find_all
                 # TRIGGER THE SPECIAL HANDLER
                 # 1. Get the content inside \csname ... \endcsname
                 csname_content = ...

                 # 2. Expand it using the *current* macro_dict
                 # This is the recursive part.
                 expanded_name, _ = expand(csname_content, macro_dict, find_macro)

                 # 3. Use the result to build the definition
                 csname = expanded_name
                 # ... proceed with the rest of the 'def' logic from the original loop ...

                 # 4. Decrement stack and advance 'i' past the used tokens
                 expandafter_stack -= 1
                 i += 2 # Advance past \def and \csname
             else:
                 # expandafter not followed by def/csname, handle other cases or ignore
                 expandafter_stack = 0 # Reset on non-match
                 # ... regular 'def' logic ...
                 i += 1
        else:
            # Original logic for 'def', 'let', 'new_com' etc.
            # Reset stack if we hit a definition without a preceding expandafter
            expandafter_stack = 0
            # ...
            i += 1

    ```
    **Note:** The Python above is pseudo-code to illustrate the state machine logic, not a literal implementation. The key is to consume `\expandafter` tokens, look ahead to see if they are followed by a `def`/`let`/etc. and then a `\csname`, and if so, trigger a recursive expansion of the `\csname` content.

A less complex, but potentially less robust, alternative would be a dedicated regex for the `\expandafter\def\csname...` pattern, but this would not handle multiple `\expandafter`s, which are common.

## Test Cases for Claude

These snippets should be used to create unit tests to validate the implementation. They progress from simple to complex.

### Test Case 1: Simple `\expandafter\def\csname`

```latex
\documentclass{article}
\makeatletter
\expandafter\def\csname my@cmd\endcsname{Hello}
\makeatother
\begin{document}
\my@cmd
\end{document}
```
**Expected pipeline body:** `Hello`

### Test Case 2: `\csname` with one level of macro expansion

```latex
\documentclass{article}
\def\myname{world}
\expandafter\def\csname greet@\myname\endcsname{Hello world}
\makeatletter
\begin{document}
\greet@world
\end{document}
```
**Expected pipeline body:** `Hello world`

### Test Case 3: `\csname` with a counter

```latex
\documentclass{article}

ewcounter{mycounter}
\setcounter{mycounter}{42}
\expandafter\def\csname cmdoman{mycounter}\endcsname{The answer is 42.}
% This defines \cmdxlii
\begin{document}
\cmdxlii
\end{document}
```
**Note:** This test requires that `oman` and `
ewcounter` are handled correctly. `oman` is a TeX primitive, but `
ewcounter` itself defines other macros (like `\c@mycounter`). For this specific test, we can assume a simplified context where `oman{mycounter}` expands to `xlii`.
**Expected pipeline body:** `The answer is 42.`

### Test Case 4: Multiple `\expandafter`s

This is the advanced case. `\expandafter` expands the second token *after* it. A chain of them peels back layers of expansion.
```latex
\documentclass{article}
\def\a{\b}
\def\b{\c}
\def\c{realname}
\expandafter\expandafter\expandafter\def\csname\a\endcsname{Success}
\begin{document}
ealname
\end{document}
```
**Explanation:**
1. The first `\expandafter` skips `\expandafter`.
2. The second `\expandafter` skips `\def`.
3. The third `\expandafter` skips `\csname`.
4. `\a` is expanded to `\b`.
5. Now we have `\expandafter\expandafter\def\csname\b\endcsname...`
6. This process repeats until `\c` is expanded to `realname`, which is then used by `\csname`. The result is the definition of `ealname`.

**Expected pipeline body:** `Success`
