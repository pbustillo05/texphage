"""SemanTex structural parser and annotator for texphage.

Three public functions:

    parse(source, *, author="unknown") -> dict
        Extract nodes / edges / variables from a LaTeX string (or Path).

    annotate(tex_str, *, prefix_map=None) -> str
        Insert \\label{auto_id} into every unlabelled structure.

    process(source, *, author="unknown", prefix_map=None) -> (str, dict)
        annotate then parse in one call.

All pattern work uses compiled patterns from _regex.py (regex package).
No manual brace-counting loops; no import re (stdlib).
"""
from __future__ import annotations

import bisect
from pathlib import Path

import regex

import texphage._regex as _rx
from texphage._regex import (
    _DISPLAY_MATH_RE,
    _PGFKEYS_ITEM_SEP_RE,
    _PGFKEYS_PAIR_RE,
    _SECTION_CMD_RE,
    _SEMANTEX_MACRO_RE,
)

# ---------------------------------------------------------------------------
# Environment → node_type mapping
# ---------------------------------------------------------------------------

_ENV_TO_TYPE: dict[str, str] = {
    # result environments
    "theorem": "result",      "thm": "result",
    "lemma": "result",        "lem": "result",
    "corollary": "result",    "cor": "result",
    "proposition": "result",  "prop": "result",
    "remark": "result",       "rem": "result",
    # definition environments
    "definition": "definition", "defn": "definition",
    # proof environments
    "proof": "proof",
    # auxiliary environments
    "figure": "auxiliary",    "figure*": "auxiliary",
    "equation": "auxiliary",  "equation*": "auxiliary",
    "align": "auxiliary",     "align*": "auxiliary",
    "table": "auxiliary",     "table*": "auxiliary",
    "algorithm": "auxiliary",
}

# Section command names → subgraph
_SECTION_CMDS = frozenset({
    "chapter", "section", "subsection", "subsubsection",
    "paragraph", "subparagraph",
})

# Rank (lower = higher level) for section-stack management
_SECTION_RANK = {
    "chapter": 0, "section": 1, "subsection": 2,
    "subsubsection": 3, "paragraph": 4, "subparagraph": 5,
}

# ---------------------------------------------------------------------------
# Line-number helpers (pure Python — not regex, these operate on list indices)
# ---------------------------------------------------------------------------

def _offset_table(text: str) -> list[int]:
    """Build list of byte-offsets for the start of each line (0-indexed)."""
    offsets = [0]
    for i, c in enumerate(text):
        if c == "\n":
            offsets.append(i + 1)
    return offsets


def _offset_to_line(offsets: list[int], pos: int) -> int:
    """Return 1-indexed line number for byte offset *pos*."""
    idx = bisect.bisect_right(offsets, pos) - 1
    return idx + 1


# ---------------------------------------------------------------------------
# pgfkeys-lite option parser
# ---------------------------------------------------------------------------

def _parse_decl_options(opts_str: str) -> tuple[str | None, list[str]]:
    """Parse key=value pairs from a \\decl optional argument string.

    Uses _PGFKEYS_ITEM_SEP_RE to split on top-level commas, then
    _PGFKEYS_PAIR_RE to extract key/value pairs.  No character loops.

    Returns (type_ref, scope_list).
    """
    type_ref: str | None = None
    scope: list[str] = []

    for item_m in _PGFKEYS_ITEM_SEP_RE.finditer(opts_str):
        part = item_m.group(0).strip()
        pair_m = _PGFKEYS_PAIR_RE.match(part)
        if not pair_m:
            continue
        key = pair_m["pgfk"].strip()
        val = pair_m["pgfval"].strip()
        # Strip outer braces from brace-enclosed values
        if val.startswith("{") and val.endswith("}"):
            val = val[1:-1]
        if key == "type":
            type_ref = val
        elif key == "scope":
            scope = [s.strip() for s in val.split(",") if s.strip()]

    return type_ref, scope


# ---------------------------------------------------------------------------
# _read_brace_arg — needed for sequential position tracking after a regex match
# ---------------------------------------------------------------------------
# The _SEMANTEX_MACRO_RE scan gives us the start position of each macro call.
# After the match we need to advance past `{arg}` and optionally `[opt]` in
# one sequential pass.  We use the embed_brackets pattern from _regex.py for
# this rather than a character loop.

_BRACE_ARG_RE = regex.compile(_rx.embed_brackets("_brace_arg"), regex.DOTALL)
_BRACKET_ARG_RE = regex.compile(_rx.embed_braces("_bracket_arg"), regex.DOTALL)


def _read_brace_arg(text: str, pos: int) -> tuple[str, int]:
    """Match a {…} argument at *pos* (skipping leading whitespace).

    Returns (content_without_outer_braces, next_pos).
    On mismatch returns ("", pos).
    """
    # Skip leading whitespace
    ws = regex.match(r"\s*", text[pos:])
    start = pos + (ws.end() if ws else 0)
    m = _BRACE_ARG_RE.match(text, start)
    if not m:
        return "", pos
    return m.group(0)[1:-1], m.end()


def _read_bracket_arg(text: str, pos: int) -> tuple[str, int]:
    """Match an optional […] argument at *pos* (skipping leading whitespace).

    Returns (content_without_outer_brackets, next_pos).
    Returns ("", pos) if no bracket argument follows.
    """
    ws = regex.match(r"\s*", text[pos:])
    start = pos + (ws.end() if ws else 0)
    m = _BRACKET_ARG_RE.match(text, start)
    if not m or not m.group(0):
        return "", pos
    return m.group(0)[1:-1], m.end()


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------

def parse(source: str | Path, *, author: str = "unknown") -> dict:
    """Parse SemanTex structural annotations from a LaTeX string or file.

    Returns a plain dict with keys "nodes", "edges", "variables".
    """
    if isinstance(source, Path):
        file_str = str(source.resolve())
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        file_str = ""
        text = source

    offsets = _offset_table(text)

    nodes: list[dict] = []
    edges: list[dict] = []
    variables: list[dict] = []

    # --- Pass 1: display math blocks ---
    # Build a list of (start, end, env_start_line, env_end_line) for each
    # display math block. Used to classify \label found inside them.
    _display_spans: list[tuple[int, int, int, int]] = []
    for dm in _DISPLAY_MATH_RE.finditer(text):
        env_start_line = _offset_to_line(offsets, dm.start())
        env_end_line = _offset_to_line(offsets, dm.end() - 1)
        _display_spans.append((dm.start(), dm.end(), env_start_line, env_end_line))

    def _in_display_math(pos: int) -> tuple[int, int] | None:
        """Return (env_start_line, env_end_line) if pos is inside a display math block."""
        for ds, de, esl, eel in _display_spans:
            if ds < pos < de:
                return esl, eel
        return None

    # --- Pass 2: section commands ---
    # Build a list of (start, cmd_name, title, line_no) for each section cmd.
    _section_events: list[tuple[int, str, str, int]] = []
    for sm in _SECTION_CMD_RE.finditer(text):
        cmd = sm.group(1)
        title = sm["sarg"][1:-1]  # strip outer braces
        line_no = _offset_to_line(offsets, sm.start())
        _section_events.append((sm.start(), cmd, title, line_no))

    # --- Pass 3: main sequential scan via _SEMANTEX_MACRO_RE ---
    # env_stack entries: (kind, name, node_id_or_None, start_line)
    # kind is "env" or "section"
    env_stack: list[tuple[str, str, str | None, int]] = []

    # Pointer into _section_events: fire section pushes as we encounter them
    sec_idx = 0

    def _flush_sections_before(pos: int) -> None:
        """Push section entries from _section_events that precede pos."""
        nonlocal sec_idx
        while sec_idx < len(_section_events):
            spos, cmd, title, line_no = _section_events[sec_idx]
            if spos >= pos:
                break
            sec_idx += 1
            rank = _SECTION_RANK[cmd]
            # Pop sections of equal or lower rank (higher rank number = deeper level)
            # A new \section replaces an existing \section and all deeper levels
            while env_stack and env_stack[-1][0] == "section":
                top_rank = _SECTION_RANK.get(env_stack[-1][1], 99)
                if top_rank >= rank:
                    env_stack.pop()
                else:
                    break
            env_stack.append(("section", cmd, None, line_no))

    def _current_env() -> tuple[str, str, str | None, int] | None:
        """Return the innermost env_stack entry (env or section)."""
        if env_stack:
            return env_stack[-1]
        return None

    def _current_node_id() -> str | None:
        for entry in reversed(env_stack):
            if entry[2]:
                return entry[2]
        return None

    for m in _SEMANTEX_MACRO_RE.finditer(text):
        # Flush section events that come before this macro
        _flush_sections_before(m.start())

        cmd = m.group(1)
        pos = m.end()
        line_no = _offset_to_line(offsets, m.start())

        if cmd == "begin":
            env_name, _ = _read_brace_arg(text, pos)
            env_name = env_name.strip()
            env_stack.append(("env", env_name, None, line_no))

        elif cmd == "end":
            env_name, _ = _read_brace_arg(text, pos)
            env_clean = env_name.strip()
            for i in range(len(env_stack) - 1, -1, -1):
                if env_stack[i][0] == "env" and env_stack[i][1] == env_clean:
                    node_id_for_env = env_stack[i][2]
                    if node_id_for_env:
                        for node in nodes:
                            if node["id"] == node_id_for_env:
                                node["env_end"] = line_no
                                break
                    env_stack.pop(i)
                    break

        elif cmd in ("label", "label*"):
            node_id, _ = _read_brace_arg(text, pos)
            node_id = node_id.strip()
            if not node_id:
                continue

            # Check if inside a display math block
            dm_info = _in_display_math(m.start())
            if dm_info:
                env_start_line, env_end_line = dm_info
                nodes.append({
                    "id": node_id,
                    "kind": "label" if cmd == "label" else "label_star",
                    "node_type": "auxiliary",
                    "env_name": "display_math",
                    "file": file_str,
                    "label_line": line_no,
                    "env_start": env_start_line,
                    "env_end": env_end_line,
                    "author": author,
                })
                # Annotate current env_stack entry with this id
                if env_stack:
                    k, n, _, sl = env_stack[-1]
                    env_stack[-1] = (k, n, node_id, sl)
                continue

            # Find innermost recognised environment or section
            node_type = "unknown"
            env_name_out = ""
            env_start_line = 0

            for entry in reversed(env_stack):
                kind, name, _, start_line = entry
                if kind == "env" and name in _ENV_TO_TYPE:
                    node_type = _ENV_TO_TYPE[name]
                    env_name_out = name
                    env_start_line = start_line
                    break
                elif kind == "section" and name in _SECTION_CMDS:
                    node_type = "subgraph"
                    env_name_out = name
                    env_start_line = start_line
                    break

            nodes.append({
                "id": node_id,
                "kind": "label" if cmd == "label" else "label_star",
                "node_type": node_type,
                "env_name": env_name_out,
                "file": file_str,
                "label_line": line_no,
                "env_start": env_start_line,
                "env_end": 0,
                "author": author,
            })

            # Annotate the innermost env_stack entry with this node id
            if env_stack:
                k, n, _, sl = env_stack[-1]
                env_stack[-1] = (k, n, node_id, sl)

        elif cmd == "iref":
            ref_id, _ = _read_brace_arg(text, pos)
            ref_id = ref_id.strip()
            from_id = _current_node_id()
            if ref_id:
                edges.append({
                    "from_id": from_id or "",
                    "to_id": ref_id,
                    "kind": "iref",
                    "file": file_str,
                    "line": line_no,
                    "author": author,
                })

        elif cmd == "decl":
            symbol, pos2 = _read_brace_arg(text, pos)
            symbol = symbol.strip()
            opts_str, _ = _read_bracket_arg(text, pos2)
            if not symbol:
                continue
            type_ref, scope = _parse_decl_options(opts_str)
            if not scope:
                current = _current_node_id()
                scope = [current] if current else []
            variables.append({
                "symbol": symbol,
                "type_ref": type_ref,
                "scope": scope,
                "file": file_str,
                "line": line_no,
                "author": author,
            })

    # Flush any remaining section events (after last macro)
    _flush_sections_before(len(text) + 1)

    return {"nodes": nodes, "edges": edges, "variables": variables}


# ---------------------------------------------------------------------------
# annotate()
# ---------------------------------------------------------------------------

# Default prefix map: env/section name → id prefix
_DEFAULT_PREFIX_MAP: dict[str, str] = {
    # result environments
    "theorem": "thm", "thm": "thm",
    "lemma": "lem", "lem": "lem",
    "proposition": "prop", "prop": "prop",
    "corollary": "cor", "cor": "cor",
    "remark": "rem",
    # definition environments
    "definition": "def", "defn": "def",
    # proof environments
    "proof": "prf",
    # section commands
    "chapter": "chap",
    "section": "sec", "subsection": "sec",
    "subsubsection": "sec", "paragraph": "sec",
    # auxiliary environments
    "figure": "fig", "figure*": "fig",
    "equation": "eq", "equation*": "eq",
    "align": "eq", "align*": "eq",
    "table": "tab", "table*": "tab",
    "algorithm": "alg",
    # display math shorthand
    "display_math": "eq",
}

# Compiled patterns used exclusively by annotate()
# Match \begin{envname} possibly with a newline before the body
_ANNOTATE_BEGIN_RE = regex.compile(
    r'\\begin\{(?P<env>[^}]*)\}',
    regex.DOTALL,
)
# Match \label{...} or \label*{...} inside an environment body
_ANNOTATE_LABEL_RE = regex.compile(
    r'\\label\*?\s*\{[^}]*\}',
)
# Match \section (and variants) with optional star and {title}
_ANNOTATE_SECTION_RE = regex.compile(
    r'(\\(?:chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?'
    r'\s*\{[^}]*\})',
    regex.DOTALL,
)
# Match display math \[...\] and $$...$$
_ANNOTATE_DISPLAY_RE = regex.compile(
    r'(\\\[.*?\\\]|\$\$.*?\$\$)',
    regex.DOTALL,
)


def annotate(
    tex_str: str,
    *,
    prefix_map: dict[str, str] | None = None,
) -> str:
    """Insert \\label{auto_id} into every unlabelled structure.

    Never modifies structures that already have a \\label or \\label* inside.
    Returns the modified string.

    Auto-ids: ``{prefix}:_{N}`` where N is a shared counter (no padding,
    starts at 1, incremented globally across the document in document order).
    Special case: a proof immediately following a labelled result gets
    ``prf:{result_id}`` (deterministic, not ``prf:_N``).
    """
    if prefix_map is None:
        prefix_map = _DEFAULT_PREFIX_MAP

    def _has_label(body: str) -> bool:
        return bool(regex.search(r'\\label\*?\s*\{', body))

    text = tex_str

    # Collect all candidate structures as (doc_pos, kind, data) tuples,
    # then sort by doc_pos so the shared counter is assigned in document order.
    # kind: "env"     → data = (begin_match_end, env_name, end_match_end, body)
    #       "section" → data = (cmd_end, cmd_name)
    #       "display" → data = (block_start, block_len, is_bracket)

    candidates: list[tuple[int, str, tuple]] = []

    # ----- Env blocks -----
    for bm in _ANNOTATE_BEGIN_RE.finditer(text):
        env = bm.group("env").strip()
        if env not in prefix_map:
            continue

        end_pattern = regex.compile(
            r'\\end\s*\{' + regex.escape(env) + r'\}', regex.DOTALL,
        )
        begin_pattern = regex.compile(
            r'\\begin\s*\{' + regex.escape(env) + r'\}', regex.DOTALL,
        )
        depth = 1
        search_pos = bm.end()
        end_match = None
        while depth > 0:
            next_begin = begin_pattern.search(text, search_pos)
            next_end = end_pattern.search(text, search_pos)
            if next_end is None:
                break
            if next_begin and next_begin.start() < next_end.start():
                depth += 1
                search_pos = next_begin.end()
            else:
                depth -= 1
                if depth == 0:
                    end_match = next_end
                else:
                    search_pos = next_end.end()

        if end_match is None:
            continue

        body = text[bm.end():end_match.start()]
        candidates.append((
            bm.start(), "env",
            (bm.end(), env, end_match.end(), body),
        ))

    # ----- Section commands -----
    for sm in _ANNOTATE_SECTION_RE.finditer(text):
        cmd_block = sm.group(1)
        cmd_end = sm.end()
        lookahead = text[cmd_end:cmd_end + 200]
        if regex.match(r'\s*\\label\*?\s*\{', lookahead):
            continue
        cmd_m = regex.match(
            r'\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)',
            cmd_block,
        )
        if not cmd_m:
            continue
        cmd_name = cmd_m.group(1)
        if cmd_name not in prefix_map:
            continue
        candidates.append((sm.start(), "section", (cmd_end, cmd_name)))

    # ----- Display math blocks -----
    for dm in _ANNOTATE_DISPLAY_RE.finditer(text):
        block = dm.group(0)
        if _has_label(block):
            continue
        is_bracket = block.startswith(r'\[')
        candidates.append((dm.start(), "display", (dm.start(), len(block), is_bracket)))

    # Sort by document position so counter assignment is in document order
    candidates.sort(key=lambda c: c[0])

    # Assign IDs and build insertion list
    counter = 0
    insertions: list[tuple[int, str]] = []
    last_result_id: str | None = None
    last_result_end: int = -1

    for _pos, kind, data in candidates:
        if kind == "env":
            bm_end, env, end_m_end, body = data
            prefix = prefix_map[env]

            if _has_label(body):
                # Already labelled — track result for proof-linking
                node_type = _ENV_TO_TYPE.get(env, "")
                if node_type == "result":
                    lm = regex.search(r'\\label\*?\s*\{([^}]*)\}', body)
                    if lm:
                        last_result_id = lm.group(1).strip()
                        last_result_end = end_m_end
                continue

            if prefix == "prf" and last_result_id:
                between = text[last_result_end:_pos]
                if not regex.search(r'\S', between):
                    label_id = f"prf:{last_result_id}"
                else:
                    counter += 1
                    label_id = f"{prefix}:_{counter}"
            else:
                counter += 1
                label_id = f"{prefix}:_{counter}"

            insertions.append((bm_end, f"\n\\label{{{label_id}}}"))

            node_type = _ENV_TO_TYPE.get(env, "")
            if node_type == "result":
                last_result_id = label_id
                last_result_end = end_m_end

        elif kind == "section":
            cmd_end, cmd_name = data
            counter += 1
            label_id = f"{prefix_map[cmd_name]}:_{counter}"
            insertions.append((cmd_end, f"\n\\label{{{label_id}}}"))

        elif kind == "display":
            block_start, block_len, is_bracket = data
            prefix = prefix_map.get("display_math", "eq")
            counter += 1
            label_id = f"{prefix}:_{counter}"
            if is_bracket:
                insert_at = block_start + len(r'\[')
            else:
                insert_at = block_start + 2  # after $$
            insertions.append((insert_at, f"\n\\label{{{label_id}}}"))

    # Apply insertions from last to first to preserve offsets
    insertions.sort(key=lambda x: x[0], reverse=True)
    result = text
    for offset, ins_text in insertions:
        result = result[:offset] + ins_text + result[offset:]

    return result


# ---------------------------------------------------------------------------
# process()
# ---------------------------------------------------------------------------

def process(
    source: str | Path,
    *,
    author: str = "unknown",
    prefix_map: dict[str, str] | None = None,
) -> tuple[str, dict]:
    """Annotate unlabelled structures then parse the result.

    If source is a Path, reads file content first.
    Returns (annotated_tex_str, graph_dict).
    Note: graph_dict["nodes"][*]["file"] will be "" (parse receives a string,
    not the original Path). Call parse(Path(...)) separately for file attribution.
    """
    tex = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    annotated = annotate(tex, prefix_map=prefix_map)
    graph = parse(annotated, author=author)
    return annotated, graph
