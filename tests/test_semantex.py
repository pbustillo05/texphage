"""Tests for texphage.semantex (parse, annotate, process).

All test inputs are minimal hand-crafted snippets; assertions are grounded
in the semantex.py contract (not playground-compiled PDF output, since these
are pure structural annotations on .tex strings, not macro-expansion).
"""
from __future__ import annotations

import pytest

from texphage.semantex import annotate, parse, process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nodes_by_id(graph: dict) -> dict:
    return {n["id"]: n for n in graph["nodes"]}


# ===========================================================================
# parse() — basic node extraction
# ===========================================================================

def test_parse_label_inside_theorem():
    src = r"""
\begin{theorem}
\label{thm:foo}
Some statement.
\end{theorem}
"""
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert "thm:foo" in nodes
    n = nodes["thm:foo"]
    assert n["node_type"] == "result"
    assert n["env_name"] == "theorem"
    assert n["kind"] == "label"
    assert n["env_start"] > 0
    assert n["env_end"] > n["env_start"]


def test_parse_label_star_sets_kind():
    src = r"""
\begin{definition}
\label*{def:bar}
A definition.
\end{definition}
"""
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert "def:bar" in nodes
    assert nodes["def:bar"]["kind"] == "label_star"
    assert nodes["def:bar"]["node_type"] == "definition"


def test_parse_iref_produces_edge():
    src = r"""
\begin{proof}
\label{prf:foo}
By \iref{thm:foo}.
\end{proof}
"""
    g = parse(src)
    edges = g["edges"]
    assert any(e["from_id"] == "prf:foo" and e["to_id"] == "thm:foo" and e["kind"] == "iref"
               for e in edges)


def test_parse_cross_project_iref_passes_through():
    src = r"""
\begin{theorem}
\label{thm:main}
Follows from \iref{otherproject:thm:base}.
\end{theorem}
"""
    g = parse(src)
    edges = g["edges"]
    assert any(e["to_id"] == "otherproject:thm:base" for e in edges)


def test_parse_section_produces_subgraph():
    src = r"""
\section{Introduction}
\label{sec:intro}
Some text.
"""
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert "sec:intro" in nodes
    n = nodes["sec:intro"]
    assert n["node_type"] == "subgraph"
    assert n["env_name"] == "section"
    assert n["env_end"] == 0


def test_parse_display_math_bracket_with_label():
    src = r"""
\[
\label{eq:energy}
E = mc^2
\]
"""
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert "eq:energy" in nodes
    n = nodes["eq:energy"]
    assert n["node_type"] == "auxiliary"
    assert n["env_name"] == "display_math"
    assert n["env_end"] > 0


def test_parse_label_outside_env_is_unknown_not_dropped():
    src = r"\label{bare:label} Some text."
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert "bare:label" in nodes
    assert nodes["bare:label"]["node_type"] == "unknown"


def test_parse_decl_produces_variable():
    src = r"""
\begin{definition}
\label{def:cont}
Let \decl{f}[type=def:cont, scope={sec:intro}] be continuous.
\end{definition}
"""
    g = parse(src)
    variables = g["variables"]
    assert any(v["symbol"] == "f" for v in variables)
    v = next(v for v in variables if v["symbol"] == "f")
    assert v["type_ref"] == "def:cont"
    assert "sec:intro" in v["scope"]


def test_parse_author_field_propagates():
    src = r"""
\begin{lemma}
\label{lem:x}
Statement.
\end{lemma}
"""
    g = parse(src, author="alice")
    nodes = _nodes_by_id(g)
    assert nodes["lem:x"]["author"] == "alice"


def test_parse_file_field_empty_for_string_input():
    src = r"""
\begin{theorem}
\label{thm:t}
\end{theorem}
"""
    g = parse(src)
    assert g["nodes"][0]["file"] == ""


def test_parse_multiple_envs_correct_types():
    src = r"""
\begin{lemma}
\label{lem:a}
\end{lemma}
\begin{proof}
\label{prf:a}
\end{proof}
\begin{definition}
\label{def:a}
\end{definition}
\begin{figure}
\label{fig:a}
\end{figure}
"""
    g = parse(src)
    nodes = _nodes_by_id(g)
    assert nodes["lem:a"]["node_type"] == "result"
    assert nodes["prf:a"]["node_type"] == "proof"
    assert nodes["def:a"]["node_type"] == "definition"
    assert nodes["fig:a"]["node_type"] == "auxiliary"


# ===========================================================================
# annotate() — label insertion
# ===========================================================================

def test_annotate_adds_label_to_theorem():
    src = r"""\begin{theorem}
Some statement.
\end{theorem}
"""
    out = annotate(src)
    assert r"\label{thm:_1}" in out


def test_annotate_does_not_touch_existing_label():
    src = r"""\begin{theorem}
\label{thm:existing}
Some statement.
\end{theorem}
"""
    out = annotate(src)
    assert r"\label{thm:existing}" in out
    assert "thm:_" not in out


def test_annotate_does_not_touch_existing_label_star():
    src = r"""\begin{theorem}
\label*{thm:existing}
Some statement.
\end{theorem}
"""
    out = annotate(src)
    assert r"\label*{thm:existing}" in out
    assert "thm:_" not in out


def test_annotate_proof_after_labeled_result_gets_deterministic_id():
    src = r"""\begin{theorem}
\label{thm:foo}
Statement.
\end{theorem}
\begin{proof}
Proof text.
\end{proof}
"""
    out = annotate(src)
    assert r"\label{prf:thm:foo}" in out
    # No auto-numbered proof label
    assert "prf:_" not in out


def test_annotate_section_gets_label():
    src = r"""\section{Introduction}
Some text.
"""
    out = annotate(src)
    assert r"\label{sec:_1}" in out


def test_annotate_display_math_bracket_gets_label_without_env_conversion():
    src = r"""\[
E = mc^2
\]
"""
    out = annotate(src)
    assert r"\label{eq:_1}" in out
    # Must NOT convert \[...\] to \begin{equation}
    assert r"\begin{equation}" not in out


def test_annotate_shared_counter_never_reuses_number():
    src = r"""\begin{theorem}
Statement.
\end{theorem}
\section{Next}
\begin{definition}
A definition.
\end{definition}
"""
    out = annotate(src)
    assert r"\label{thm:_1}" in out
    assert r"\label{sec:_2}" in out
    assert r"\label{def:_3}" in out


# ===========================================================================
# process()
# ===========================================================================

def test_process_graph_matches_parse_of_annotated():
    src = r"""\begin{theorem}
Statement.
\end{theorem}
"""
    annotated, graph = process(src)
    graph2 = parse(annotated)
    # Both graphs should contain the same node ids
    ids1 = {n["id"] for n in graph["nodes"]}
    ids2 = {n["id"] for n in graph2["nodes"]}
    assert ids1 == ids2
