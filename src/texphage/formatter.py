"""Pretty-printer for texphage canonical output.

Design:
  Pure Python, no external dependencies, fully deterministic.
  Two modes:
    - Default: isolate block environments and \\par; prose stays as-is.
    - --semantic-linebreaks: additionally split prose sentences onto separate lines.

Public API:
    pretty_print(tex, *, semantic_linebreaks=False, indent="  ") -> str
"""
from __future__ import annotations

import regex

from texphage._regex import _DOC_SPLIT_RE

# ---------------------------------------------------------------------------
# Inline environments: these are NOT isolated onto their own lines.
# ---------------------------------------------------------------------------

_INLINE_ENVS: frozenset[str] = frozenset({
    "minipage", "mbox", "makebox", "fbox", "parbox",
    "math", "displaymath",
})

# Build an alternation pattern for inline env names (exact match at end of name)
_INLINE_ENV_PAT: str = "|".join(
    regex.escape(e) for e in sorted(_INLINE_ENVS, key=len, reverse=True)
)

# ---------------------------------------------------------------------------
# Compiled patterns  (all use `regex`, never stdlib `re`)
# ---------------------------------------------------------------------------

# Block \begin{X} — X not in _INLINE_ENVS
_BLOCK_BEGIN_RE = regex.compile(
    r'\\begin\{(?P<env>(?!' + _INLINE_ENV_PAT + r'\b)[^}]+)\}'
)

# Block \end{X} — X not in _INLINE_ENVS
_BLOCK_END_RE = regex.compile(
    r'\\end\{(?P<env>(?!' + _INLINE_ENV_PAT + r'\b)[^}]+)\}'
)

# Display math delimiters \[ and \]
_DISP_OPEN_RE = regex.compile(r'\\\[')
_DISP_CLOSE_RE = regex.compile(r'\\\]')

# \par token (standalone, not \paragraph)
_PAR_RE = regex.compile(r'\\par\b[ \t]*')

# \item (any variant)
_ITEM_RE = regex.compile(r'(?<!\n)\\item\b')

# One or more newlines followed by optional spaces then \label or \caption:
# we want to REMOVE these newlines so \label stays on the same line as its anchor.
_LABEL_AFTER_NL_RE = regex.compile(r'\n+[ \t]*(?=\\label\{|\\caption\{)')

# Adjacent block env boundaries to merge (no newline between them):
#   \begin{A}  whitespace+newlines  \begin{B}  →  \begin{A}\begin{B}
#   \end{A}    whitespace+newlines  \end{B}    →  \end{A}\end{B}
#   \[         whitespace+newlines  \begin{B}  →  \[\begin{B}
#   \end{A}    whitespace+newlines  \]         →  \end{A}\]
_MERGE_OPEN_RE = regex.compile(
    r'(?P<left>\\begin\{[^}]+\}|\\\[)\s*\n\s*(?P<right>\\begin\{[^}]+\}|\\\[)'
)
_MERGE_CLOSE_RE = regex.compile(
    r'(?P<left>\\end\{[^}]+\}|\\\])\s*\n\s*(?P<right>\\end\{[^}]+\}|\\\])'
)

# "Pure env line": a line consisting only of \begin{}, \end{}, \[, \], \label{},
# \caption{} tokens and whitespace.
_PURE_ENV_LINE_RE = regex.compile(
    r'^(?:'
    r'\\begin\{[^}]+\}|\\end\{[^}]+\}|\\\[|\\\]'
    r'|\\label\{[^}]*\}|\\caption\{[^}]*\}'
    r'|\s'
    r')*$'
)

# Sentence boundary candidates for --semantic-linebreaks
_SENT_SPLIT_RE = regex.compile(
    r'(?<![A-Z])(?<!\b(?:Fig|Thm|Lem|Cor|Prop|Def|Rem|Sec|Ch|App|cf|vs|resp|wrt|iff|al)\b)'
    r'(?<!\b(?:i\.e|e\.g|et al|a\.s|w\.p|s\.t|w\.r\.t)\b)'
    r'(?<![A-Z])(?<!\b[A-Z])'     # single uppercase letter (initials)
    r'(?<!\b\d)'                  # digit before dot
    r'([.?!])[ \t]+(?=[A-Z\\])'
)

# Known abbreviation lookbehind — reused in the sentence splitter
_ABBREV_PAT = regex.compile(
    r'\b(?:Fig|Thm|Lem|Cor|Prop|Def|Rem|Sec|Ch|App|cf|vs|resp|wrt|iff)\.'
    r'|(?:i\.e|e\.g|et al|a\.s|w\.p|s\.t|w\.r\.t)\.'
    r'|[A-Z]\.'         # single uppercase initial
    r'|\d\.'            # digit
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pretty_print(
    tex: str,
    *,
    semantic_linebreaks: bool = False,
    indent: str = "  ",
) -> str:
    """Format a LaTeX string for human readability.

    Args:
        tex:                 The .tex string to format (canonical or raw).
        semantic_linebreaks: If True, split prose into one sentence per line.
        indent:              Indentation string inside block environments.

    Returns:
        Formatted .tex string. PDF output is identical to input.
    """
    m = _DOC_SPLIT_RE.search(tex)
    if not m:
        # No \\begin{document} — treat whole string as body
        return _format_body(tex, indent=indent, semantic_linebreaks=semantic_linebreaks)

    preamble: str = m.group("preamble")
    body: str = m.group("body")

    formatted = _format_body(body, indent=indent, semantic_linebreaks=semantic_linebreaks)

    return preamble + r"\begin{document}" + "\n" + formatted + r"\end{document}" + "\n"


# ---------------------------------------------------------------------------
# Body formatting
# ---------------------------------------------------------------------------

def _format_body(body: str, indent: str, semantic_linebreaks: bool) -> str:
    # 1. \par → blank line
    body = _PAR_RE.sub("\n\n", body)

    # 2. Isolate block environments and display math delimiters
    body = _isolate_block_envs(body)

    # 3. \item on its own line
    body = _ITEM_RE.sub(r"\n\\item", body)

    # 4. \label / \caption: remove any newlines that appeared before them
    body = _LABEL_AFTER_NL_RE.sub("", body)

    # 5. Collapse runs of 3+ newlines → 2 (paragraph boundary)
    body = regex.sub(r"\n{3,}", "\n\n", body)

    # 6. Indentation
    body = _indent_body(body, indent)

    # 7. Optional semantic linebreaks (applied AFTER indentation so prose
    #    runs are identifiable as single lines)
    if semantic_linebreaks:
        body = _apply_semantic_linebreaks(body)

    # 8. Final blank-line collapse (sentence splitting may add newlines)
    body = regex.sub(r"\n{3,}", "\n\n", body)

    return body.strip() + "\n"


def _isolate_block_envs(body: str) -> str:
    """Surround every block \\begin{}/\\end{} and \\[/\\] with newlines,
    then merge adjacent env boundaries onto the same line.

    Uses lookbehind/lookahead guards so the pass is idempotent:
    a \\begin already at the start of a line is not prefixed again.
    """
    # Insert \\n before block \\begin{X} — only if not already preceded by \\n
    body = regex.sub(
        r'(?<!\n)(' + _BLOCK_BEGIN_RE.pattern + r')',
        r'\n\1', body,
    )
    # Insert \\n after block \\begin{X} — only if not already followed by \\n
    body = regex.sub(
        r'(' + _BLOCK_BEGIN_RE.pattern + r')(?!\n)',
        r'\1\n', body,
    )
    # Insert \\n before block \\end{X} — only if not already preceded by \\n
    body = regex.sub(
        r'(?<!\n)(' + _BLOCK_END_RE.pattern + r')',
        r'\n\1', body,
    )
    # (No \\n after \\end{X}: prose after it stays on the same line.)

    # Insert \\n before \\[ — only if not already preceded by \\n
    body = regex.sub(r'(?<!\n)(\\\[)', r'\n\1', body)
    # Insert \\n after \\[ — only if not already followed by \\n
    body = regex.sub(r'(\\\[)(?!\n)', r'\1\n', body)
    # Insert \\n before \\] — only if not already preceded by \\n
    body = regex.sub(r'(?<!\n)(\\\])', r'\n\1', body)

    # Merge adjacent opens: \\begin{A}...\\n...\\begin{B} → \\begin{A}\\begin{B}
    # Apply repeatedly until stable (handles triple nesting)
    prev = None
    while prev != body:
        prev = body
        body = _MERGE_OPEN_RE.sub(lambda m: m.group("left") + m.group("right"), body)

    # Merge adjacent closes: \\end{A}...\\n...\\end{B} → \\end{A}\\end{B}
    prev = None
    while prev != body:
        prev = body
        body = _MERGE_CLOSE_RE.sub(lambda m: m.group("left") + m.group("right"), body)

    return body


def _is_pure_env_line(line: str) -> bool:
    """True if the line contains only env markers, \\[/\\], \\label, \\caption."""
    return bool(_PURE_ENV_LINE_RE.match(line))


def _count_block_begins(line: str) -> int:
    return len(_BLOCK_BEGIN_RE.findall(line)) + len(_DISP_OPEN_RE.findall(line))


def _count_block_ends(line: str) -> int:
    return len(_BLOCK_END_RE.findall(line)) + len(_DISP_CLOSE_RE.findall(line))


def _indent_body(body: str, indent: str) -> str:
    """Walk lines and apply depth-based indentation.

    Rules:
    - Pure-open line (only \\begin{}/\\[ tokens): render at current depth, then depth+1.
    - Pure-close line (only \\end{}/\\] tokens): depth-1, then render.
    - Pure-mixed line (both opens and closes): depth-1 for the closes, then net+1 for opens.
    - Prose line with embedded env markers: adjust depth by net change.
    """
    lines = body.split("\n")
    result: list[str] = []
    depth = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        begins = _count_block_begins(stripped)
        ends = _count_block_ends(stripped)
        is_pure = _is_pure_env_line(stripped)

        if is_pure and ends > 0 and begins == 0:
            # Pure close: render at depth-1
            depth = max(0, depth - 1)
            result.append(indent * depth + stripped)
        elif is_pure and begins > 0 and ends == 0:
            # Pure open: render at current depth, then go one level deeper
            result.append(indent * depth + stripped)
            depth += 1
        elif is_pure and begins > 0 and ends > 0:
            # Pure mixed (e.g. \\end{A}\\begin{B}): treat as -1 then +1 (net 0)
            depth = max(0, depth - 1)
            result.append(indent * depth + stripped)
            depth += 1
        else:
            # Prose line (may contain env markers — e.g. "\\end{align} follows.")
            net = begins - ends
            if net < 0:
                depth = max(0, depth + net)
                result.append(indent * depth + stripped)
            elif net > 0:
                result.append(indent * depth + stripped)
                depth += net
            else:
                result.append(indent * depth + stripped)

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Semantic linebreaks (opt-in)
# ---------------------------------------------------------------------------

def _apply_semantic_linebreaks(body: str) -> str:
    """Split prose runs at sentence boundaries.

    Only applies to lines that are NOT inside a math environment or env marker.
    Uses a deterministic rule-based approach (no LLM).
    """
    lines = body.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or _is_pure_env_line(stripped) or stripped.startswith("%"):
            result.append(line)
            continue
        # Apply sentence splitting to this line
        split = _split_sentences(line)
        result.extend(split)
    return "\n".join(result)


def _split_sentences(line: str) -> list[str]:
    """Split a single prose line at sentence boundaries.

    Respects:
    - Known abbreviations (Thm., Fig., etc.)
    - Single uppercase initials
    - Digits before dots
    - Math mode ($...$, \\(...\\), \\[...\\])
    """
    # Protect math regions: replace with placeholders
    placeholder_map: dict[str, str] = {}

    def _protect(m: regex.Match) -> str:  # type: ignore[type-arg]
        key = f"\x00MATH{len(placeholder_map)}\x00"
        placeholder_map[key] = m.group(0)
        return key

    # Protect $...$ (non-greedy, single $)
    line_p = regex.sub(r'\$[^$]+?\$', _protect, line)
    # Protect \(...\)
    line_p = regex.sub(r'\\\(.*?\\\)', _protect, line_p)
    # Protect \cite{...}, \ref{...}, \eqref{...}
    line_p = regex.sub(r'\\(?:cite|ref|eqref)\{[^}]*\}', _protect, line_p)

    # Find candidate sentence-end positions
    segments: list[str] = []
    pos = 0
    for m in regex.finditer(r'([.?!])[ \t]+(?=[A-Z\\])', line_p):
        punct_end = m.start() + 1  # position after the punctuation
        before_dot = line_p[:punct_end]

        # Check if preceded by an abbreviation — if so, skip this split
        if _ABBREV_PAT.search(before_dot) and before_dot.rstrip(". ").endswith(
            tuple(
                a.rstrip(".")
                for a in [
                    "Fig", "Thm", "Lem", "Cor", "Prop", "Def", "Rem",
                    "Sec", "Ch", "App", "cf", "vs", "resp", "wrt", "iff",
                    "i.e", "e.g", "et al", "a.s", "w.p", "s.t", "w.r.t",
                ]
            )
        ):
            continue

        segments.append(line_p[pos : m.start() + 1])
        pos = m.end() - len(m.group(0)) + len(m.group(1)) + 1  # skip the space

    segments.append(line_p[pos:])

    # Restore placeholders and return segments
    restored: list[str] = []
    indent_str = line[: len(line) - len(line.lstrip())]
    for i, seg in enumerate(segments):
        for key, val in placeholder_map.items():
            seg = seg.replace(key, val)
        seg = seg.strip()
        if seg:
            restored.append(indent_str + seg if i > 0 else seg)

    return restored if restored else [line]
