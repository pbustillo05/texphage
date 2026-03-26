from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import regex as re

from texphage._regex import (
    _ARG_REF_DOUBLE_RE,
    _ARG_REF_RE,
    _BLANK_LINE_RE,
    _BLOCK_COMMENT_RE,
    _COMMENT_RE,
    _CSNAME_DEF_RE,
    _DEF_PARAM_PIECE_RE,
    _DOCUMENT_SPLIT_RE,
    _FIND_ALL_RE,
    _OUTER_DELIMITERS_RE,
    _PAR_TOKENIZER_RE,
    _VERBATIM_ENVS_RE,
    _WHITESPACE_RE,
    _XARGS_POSITIONAL_RE,
    _XPARSE_PATTERN,
    com_name,
    embed_braces,
    embed_brackets,
    env_name,
    find_specific_com,
    token,
)

from .find_packages import find_used_packages

logger = logging.getLogger(__name__)

# Placeholder token for stashed verbatim blocks: long unique prefix, no TeX-special chars.
_VERBATIM_PLACEHOLDER = 'texphageVERBATIM{}ENDVERBATIM'


def _strip_par_in_groups(tex: str) -> str:
    r"""Remove \par tokens that appear inside groups where TeX forbids them.

    After whitespace collapse the flat string may contain \par tokens that
    arose from blank lines inside command arguments (e.g. \title{\par Text})
    or inside math display environments (e.g. \begin{gather}...\par...\end{gather}).
    TeX forbids \par in most command arguments and in all math environments,
    raising "Paragraph ended before \cmd was complete."

    This function tracks two kinds of nesting:
    - **brace depth**: incremented by ``{``, decremented by ``}``.
    - **math-env depth**: incremented by ``\begin{<math_env>}``, decremented
      by ``\end{<math_env>}``.  Only environments known to forbid \par are
      counted (see ``_PAR_FORBIDDEN_ENVS``).

    \par is stripped whenever *either* depth is > 0, and preserved at top
    level (between paragraphs in the document body) and inside non-math
    environments (itemize, enumerate, center, figure, etc.) where \par is legal.

    Called as step 4.5 in preprocessing(), after whitespace collapse.

    LIMITATIONS:
      [observed] Only a fixed set of math environments is tracked. \par inside
                 an unknown environment that also forbids it will survive. The
                 set covers all amsmath display environments, eqnarray, and
                 base LaTeX math/displaymath. Playground confirms \par is legal
                 inside itemize, enumerate, center, figure, tabular, minipage.
      [observed] \begin{document}/\end{document} ARE in the string at this
                 point (Step 6 splits on them later), but 'document' is not in
                 _PAR_FORBIDDEN_ENVS so it does not affect math-env depth.
    """
    # Environments where \par is illegal (all math display environments).
    # Starred variants (e.g. gather*) are matched by checking the base name.
    # Sources:
    #   - amsmath package: gather, align, alignat, flalign, multline, split
    #   - base LaTeX: equation, eqnarray, math, displaymath
    _PAR_FORBIDDEN_ENVS = frozenset({
        'gather', 'align', 'alignat', 'flalign', 'multline', 'split',
        'equation', 'eqnarray', 'math', 'displaymath',
    })

    out: list[str] = []
    brace_depth = 0
    math_env_depth = 0
    for m in _PAR_TOKENIZER_RE.finditer(tex):
        kind = m.lastgroup
        if kind == 'par':
            if brace_depth > 0 or math_env_depth > 0:
                continue  # strip \par and its trailing space
            out.append(m.group(0))
        elif kind == 'begin':
            out.append(m.group(0))
            base = m.group('begin_env').rstrip('*')
            if base in _PAR_FORBIDDEN_ENVS:
                math_env_depth += 1
        elif kind == 'end':
            out.append(m.group(0))
            base = m.group('end_env').rstrip('*')
            if base in _PAR_FORBIDDEN_ENVS and math_env_depth > 0:
                math_env_depth -= 1
        elif kind == 'open':
            brace_depth += 1
            out.append(m.group(0))
        elif kind == 'close':
            brace_depth = max(0, brace_depth - 1)
            out.append(m.group(0))
        else:  # ctrl or text
            out.append(m.group(0))
    return ''.join(out)


def preprocessing(tex: str) -> tuple[str, str, list]:
    """Normalise a raw LaTeX string for the demacro regex engine.

    Steps performed in this exact order (order is significant):

    1. PROTECT verbatim environments: replace with opaque placeholders so
       steps 2–4 cannot touch their content.

    2. Strip comments: remove % to end-of-line. Preserves \\% (escaped percent).

    3. Preserve paragraph breaks: replace blank lines with \\par BEFORE
       collapsing whitespace. In LaTeX, blank line = \\par, NOT a space.

    4. Collapse whitespace: reduce all remaining whitespace to single spaces,
       producing the flat string that all downstream regex patterns require.

    4.5. Strip \\par inside brace groups: \\par inside command arguments is
       illegal in TeX ("Paragraph ended before \\cmd"). It arises when
       comment stripping (step 2) leaves blank lines inside ``{...}`` args.

    5. RESTORE verbatim environments: re-insert the protected blocks.

    6. Split on \\begin{document}/\\end{document}.

    Postcondition (the regex engine invariant): the result is a flat string
    with at most one space between tokens, verbatim content intact, and
    paragraph breaks represented as \\par tokens.

    Returns:
        (preamble, document_body, packages_list)
    """
    # Step 1: Protect verbatim-like environments.
    verbatim_store: dict[str, str] = {}

    def _stash(m: re.Match) -> str:
        key = _VERBATIM_PLACEHOLDER.format(len(verbatim_store))
        verbatim_store[key] = m.group(0)
        return key

    tex = _VERBATIM_ENVS_RE.sub(_stash, tex)

    # Step 2: Strip LaTeX comments.
    # (?<!\\) negative lookbehind: only % not preceded by backslash.
    # [^\n]* consumes rest of line, preserving the newline for Step 3.
    tex = _COMMENT_RE.sub('', tex)

    # Step 2b: Strip block comment environments (comment package).
    # \begin{comment}...\end{comment} produces no output; discard entirely.
    tex = _BLOCK_COMMENT_RE.sub('', tex)

    # Step 3: Preserve paragraph breaks BEFORE collapsing whitespace.
    # \n[ \t]*\n+ = one or more blank lines.
    # MUST run before Step 4, or blank lines collapse to spaces.
    tex = _BLANK_LINE_RE.sub(r' \\par ', tex)

    # Step 4: Collapse all remaining whitespace to exactly one space.
    tex = _WHITESPACE_RE.sub(' ', tex)

    # Step 4.5: Remove \par tokens inside brace groups.
    # Comment stripping can leave blank lines inside {arg} → \par in arg → TeX error.
    tex = _strip_par_in_groups(tex)

    # Step 5: Restore verbatim blocks.
    for key, value in verbatim_store.items():
        tex = tex.replace(key, value)

    # Step 6: Split preamble from body.
    parts = _DOCUMENT_SPLIT_RE.split(tex, maxsplit=2)
    if len(parts) < 3:
        return '', tex, find_used_packages(tex)
    preamble, document, _epilogue = parts
    return preamble, document, find_used_packages(preamble)

__all__ = ["demacro", "preprocessing", "build_dictionary", "expand"]


# MATCHES: the parameter text of a \\def command (the text between the command
#          name and the opening { of the body), e.g. '#1and#2' or '#1' or ''.
# CAPTURES:
#   arg1, arg2, … argN  → the argument values at the call site
# LIMITATIONS:
#   [observed] Delimited params use lazy .*? which may over-match when the
#              delimiter string appears inside a brace group.  Playground
#              verified for simple alphanumeric delimiters (e.g. 'and').
#   [inferred] ## (doubled hash = literal #) is not handled.
#   [inferred] Spaces in delimiters interact with the whitespace-collapse
#              invariant; single-space delimiters (' ') work but multi-space
#              delimiters (' \t') do not (they collapse to one space anyway).
def _def_param_pattern(def_pattern: str) -> str:
    """Convert a TeX \\def parameter text to a call-site regex fragment.

    Delimited parameters (``#N`` followed by literal text) are matched lazily
    (``.*?``) so that the capture stops just before the delimiter.  Undelimited
    parameters (``#N`` with no following literal) are matched by ``token()``,
    which is exactly one TeX token or braced group — identical to TeX semantics.

    Uses _DEF_PARAM_PIECE_RE to tokenize the parameter text without a
    character-by-character loop.

    Example::

        '#1and#2'  →  r'(?<arg1>.*?)and(?<arg2><token>)'
        '#1'       →  r'(?<arg1><token>)'
        ''         →  r''  (zero-arg \\def)
    """
    result = ''
    for m in _DEF_PARAM_PIECE_RE.finditer(def_pattern):
        if m.group('hash') is not None:
            digit = m.group('hash')
            delimiter = m.group('delim')
            if delimiter:
                # Delimited: skip optional space, match lazily, then the delimiter.
                result += r' ?(?<%s>.*?)' % ('arg' + digit)
                result += re.escape(delimiter)
            else:
                # Undelimited: skip optional space, then exactly one TeX token.
                result += r' ?(?<%s>%s)' % ('arg' + digit, token('bracket_arg' + digit))
        else:
            # Literal text before the first parameter slot.
            result += re.escape(m.group('lit'))
    return result


###### DICTIONARY BUIDLING
def _strip_delimiters(s: str | None) -> str:
    """Strip a single layer of outer {} or [] delimiters from a captured token.

    Returns '' for None (unmatched optional group).
    Uses _OUTER_DELIMITERS_RE to avoid direct character-index access.
    """
    if s is None:
        return ''
    m = _OUTER_DELIMITERS_RE.match(s)
    if m:
        # group(1) is the brace-delimited content; group(2) is bracket-delimited.
        return m.group(1) if m.group(1) is not None else (m.group(2) or '')
    return s


def content_replacement(
    local_content: str, default_dict: dict = {}, boolean_list: list = []
) -> Callable:
    # Strip outer {} from content template (captured by token() with delimiters).
    local_content = _strip_delimiters(local_content)
    # Strip outer [] from default values (captured by embed_braces with delimiters).
    stripped_defaults = {k: _strip_delimiters(v) for k, v in default_dict.items()}

    def content(arg: Any) -> str:
        def arg_replacement(num: Any) -> str:
            if _ARG_REF_DOUBLE_RE.match(num[1]):
                return num[1]
            key = num[1][-1:]
            try:
                raw = arg.group('arg' + key)
            except IndexError:
                logger.debug('content_replacement: missing group arg%s, using default', key)
                return stripped_defaults.get(key, '')
            if raw is None:
                # Optional group absent — return BooleanFalse for boolean args, else default.
                if key in boolean_list:
                    return r'\BooleanFalse'
                return stripped_defaults.get(key, '')
            if key in boolean_list:
                return r'\BooleanTrue'
            return _strip_delimiters(raw)
        return _ARG_REF_RE.sub(arg_replacement, local_content)
    return content

def build_dictionary(tex: str) -> tuple[dict, str]:
    """Parse the preamble and build a macro expansion dictionary.

    Iterates over _FIND_ALL_RE matches in order. For each definition found,
    adds an entry to macro_dict: {csname: [match_pattern, replacement_fn]}.
    Also builds find_macro — a regex alternation string used by expand() to
    find uses of defined macros in the document body.

    The elif chain order is semantically significant: \\edef must expand its
    content immediately using the *current* macro_dict state (unlike \\def).
    Do not reorder. See DANGER ZONE rules in CLAUDE_INSTRUCTIONS.md.

    Returns:
        (macro_dict, find_macro)  where find_macro is a compiled-ready string
        (leading | stripped).
    """
    macro_dict, find_macro = {}, ''
    for macro in _FIND_ALL_RE.finditer(tex):
        # csname = macro.group(macro.lastgroup + '_csname')
        # try:
        #     if re.search(to_expand, macro.group(macro.lastgroup + '_content')):
        #         to_expand += r'|(?<%s>\\%s(?![a-zA-Z]))' %(csname, csname)
        # except IndexError:
        #     if re.search(to_expand, macro.group(macro.lastgroup + '_begin')) or re.search(to_expand, macro.group(macro.lastgroup + '_end')):
        #         to_expand += r'|\\(?<%s>begin ?\{ ?%s ?\}|(?<%s>end ?\{ ?%s ?\})|(?<%s>%s(?![a-zA-Z]))|(?<%s>end%s(?![a-zA-Z]))' %(csname, csname)
        # COMMANDS
        if macro.group('def'):
            csname = com_name(macro.group('def_csname'))
            # .strip(): TeX ignores whitespace between command name and { of body;
            # def_pattern captures that trailing space — strip it so zero-arg macros
            # don't require a literal space in the call-site pattern. (BUG-10)
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + _def_param_pattern(macro.group('def_pattern').strip())
            content = content_replacement(macro.group('def_content'))
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('edef'):
            csname = com_name(macro.group('edef_csname'))
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + _def_param_pattern(macro.group('edef_pattern').strip())
            #Content needs to be extended first:
            expanded_content, _ = expand(macro.group('edef_content'), macro_dict, find_macro)
            content = content_replacement(expanded_content)
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('let'):
            csname = com_name(macro.group('let_csname'))
            if macro.group('let_called_csname') in macro_dict:
                called = macro_dict[macro.group('let_called_csname')]
                pattern = re.sub(r'\\' + macro.group('let_called_csname'), (r'\\%s(?![a-zA-Z])' %csname), called[0], 1)
                macro_dict[csname] = [pattern, called[1]]
            else:
                macro_dict[csname] = [(r'\\%s(?![a-zA-Z])' %csname), macro.group('let_content')]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('new_com'):
            csname = com_name(macro.group('new_com_csname'))
            pattern = r'\\%s(?![a-zA-Z])' %csname
            if macro.group('new_com_num_args'):
                num_args = int(macro.group('new_com_num_args'))
                i = 0
                default_dict = {}
                if macro.group('new_com_default1'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg1')
                    raw1 = macro.group('new_com_default1')
                    if macro.group('new_com_xargs') and raw1:
                        # xargs [i=val] syntax: strip leading "i=" position prefix
                        inner = raw1[1:-1]
                        m2 = _XARGS_POSITIONAL_RE.match(inner)
                        if m2:
                            raw1 = '[' + inner[m2.end():] + ']'
                    default_dict['1'] = raw1
                if macro.group('new_com_default2'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg2')
                    raw2 = macro.group('new_com_default2')
                    if macro.group('new_com_xargs') and raw2:
                        inner = raw2[1:-1]
                        m2 = _XARGS_POSITIONAL_RE.match(inner)
                        if m2:
                            raw2 = '[' + inner[m2.end():] + ']'
                    default_dict['2'] = raw2
                while i < num_args:
                    i+=1
                    pattern += r' ?(?<%s>%s)' %('arg' + str(i), token('bracket_arg' + str(i)))
                content = content_replacement(macro.group('new_com_content'), default_dict)
            else:   #else used here because otherwise the re.sub seemed to fail.. can it be removed?
                # Lambda used here because (for some reason) it makes macro.group('new_com_content') be seen as raw
                content = lambda arg, local_content = _strip_delimiters(macro.group('new_com_content')) : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('new_doc_com'):
            csname = com_name(macro.group('new_doc_com_csname'))
            pattern = r'\\%s(?![a-zA-Z])' %csname
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(_XPARSE_PATTERN, macro.group('new_doc_com_args')):
                arg_num += 1
                if args.lastgroup == 'm':
                    pattern += ' ?' + embed_brackets('arg' + str(arg_num))
                elif args.lastgroup == 'o':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                elif args.lastgroup == 'O':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                    default_dict[str(arg_num)] = args.group('default')
                elif args.lastgroup == 's':
                    pattern += r' ?(?<arg%s>\*)? ?' %str(arg_num)
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
                elif args.lastgroup == 't':
                    pattern += r' ?(?<arg%s>\%s)? ?' %(str(arg_num), args.group('t')[1:])
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
            if arg_num != 0:
                content = content_replacement(macro.group('new_doc_com_content'), default_dict)
            else:   #else used here because otherwise the re.sub seemed to fail.. can it be removed?
                # Lambda used here because (for some reason) it makes macro.group('new_doc_com_content') be seen as raw
                content = lambda arg, local_content = _strip_delimiters(macro.group('new_doc_com_content')) : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder

        # ENVIRONMENTS
        elif macro.group('new_env'):
            csname_group, csname_latex = env_name(macro.group('new_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
            default_dict = {}
            if macro.group('new_env_num_args'):
                num_args = int(macro.group('new_env_num_args'))
                i = 0
                if macro.group('new_env_default'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg1')
                    default_dict = {'1':macro.group('new_env_default')}
                while i < num_args:
                    i+=1
                    pattern += r' ?(?<%s>%s)' %('arg' + str(i), token('bracket_arg' + str(i)))
            pattern += r'(?<between>.*)\\end ?\{ ?%s ?\}' %csname_latex
            begin = content_replacement(macro.group('new_env_begin'), default_dict)
            end = content_replacement(macro.group('new_env_end'), default_dict)
            content = lambda arg, b=begin, e=end: b(arg) + arg.group('between') + e(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        elif macro.group('new_doc_env'):
            csname_group, csname_latex = env_name(macro.group('new_doc_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(_XPARSE_PATTERN, macro.group('new_doc_env_args')):
                arg_num += 1
                if args.lastgroup == 'm':
                    pattern += ' ?' + embed_brackets('arg' + str(arg_num))
                elif args.lastgroup == 'o':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                elif args.lastgroup == 'O':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                    default_dict[str(arg_num)] = args.group('default')
                elif args.lastgroup == 's':
                    pattern += r' ?(?<arg%s>\*)? ?' %str(arg_num)
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
                elif args.lastgroup == 't':
                    pattern += r' ?(?<arg%s>\%s)? ?' %(str(arg_num), args.group('t')[1:])
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
            arg_num += 1
            pattern += r'(?<arg%s>.*)\\end ?\{ ?%s ?\}' %(str(arg_num), csname_latex)
            begin = content_replacement(macro.group('new_doc_env_begin'), default_dict)
            end = content_replacement(macro.group('new_doc_env_end'), default_dict)
            between = 'arg%s' %str(arg_num)
            content = lambda arg, b=begin, e=end, bw=between: b(arg) + arg.group(bw) + e(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        elif macro.group('dmo'):
            # \DeclareMathOperator{\myOp}{Op}  →  expand \myOp as \operatorname{Op}
            # \DeclareMathOperator*{\myOp}{Op} →  expand \myOp as \operatorname*{Op}
            csname = com_name(macro.group('dmo_csname'))
            star = '*' if macro.group('dmo_star') else ''
            symbol = _strip_delimiters(macro.group('dmo_content'))
            expansion = r'\operatorname%s{%s}' % (star, symbol)
            content = lambda arg, r=expansion: r
            pattern = r'\\%s(?![a-zA-Z])' % csname
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('csname_def'):
            # Direct \expandafter\def\csname<name>\endcsname{body} in the preamble.
            name = macro.group('csname_def_name').strip()
            if name:
                content = content_replacement(macro.group('csname_def_content'))
                macro_dict[name] = [r'\\%s(?![a-zA-Z])' % name, content]
                find_macro += '|' + find_specific_com(name)
        else: #tikzset
            pass

    # Preamble execution pass: some macros use \expandafter\def\csname...\endcsname
    # inside their body to define new commands at call time.  After the initial scan
    # we expand any such macro calls found in the preamble and re-register the commands
    # they produce.  We only process macros whose raw call-site pattern matches in the
    # preamble text AND whose expansion contains the csname-def idiom.
    # Collect (pattern, content_fn) for all command macros (environments are excluded
    # because their call syntax includes \begin{...} which would not appear outside
    # the document body in a definition-generating call).
    _cmd_entries = [(pat, fn) for pat, fn in macro_dict.values() if callable(fn)]
    for call_pattern, content_fn in _cmd_entries:
        try:
            for call_match in re.finditer(call_pattern, tex):
                expanded_call = content_fn(call_match)
                for def_m in _CSNAME_DEF_RE.finditer(expanded_call):
                    new_name = def_m.group('csname_def_name').strip()
                    if new_name and new_name not in macro_dict:
                        new_content = content_replacement(def_m.group('csname_def_content'))
                        macro_dict[new_name] = [r'\\%s(?![a-zA-Z])' % new_name, new_content]
                        find_macro += '|' + find_specific_com(new_name)
        except Exception:
            continue

    return macro_dict, find_macro[1:]

###### EXPANDING
def expand(
    tex: str,
    macro_dict: dict,
    find_macro: str,
    log_level: int = logging.WARNING,
) -> tuple[str, list]:
    """Expand macro uses left-to-right. If expansion produces no change
    (self-referential macro), log and advance past the match to prevent
    an infinite loop."""
    if not find_macro:
        return tex, []
    macro = re.search(find_macro, tex)
    pos = 0
    problematic_macros = []
    while macro:
        pos += macro.start()
        macro_def = macro_dict[macro.lastgroup]
        if re.search(macro_def[0], tex[pos:]):
            # If the replacement is a plain string (e.g. \let alias to unknown macro),
            # wrap it in a lambda so regex.sub does not interpret \c, \j etc. as
            # backreference escapes and raise "bad escape" errors.
            repl = macro_def[1]
            if not callable(repl):
                repl = lambda m, r=repl: r
            new_tex = tex[:pos] + re.sub(macro_def[0], repl, tex[pos:], count=1)
            if new_tex == tex:
                logging.log(log_level,
                    'Macro %s at pos %i is self-referential — skipping',
                    macro.lastgroup, pos)
                problematic_macros.append((macro.lastgroup, pos, 'no_progress'))
                pos += 1
            else:
                tex = new_tex
        else:
            logging.log(log_level,
                'Macro %s at pos %i: definition pattern did not match context',
                macro.lastgroup, pos)
            problematic_macros.append((macro.lastgroup, pos, 'pattern_mismatch'))
            pos += 1
        macro = re.search(find_macro, tex[pos:])
    return tex, problematic_macros

###### MAIN
def demacro(tex: str) -> tuple[str, list, list]:
    """Parse a flat LaTeX string, expand preamble-defined macros in the body.

    Args:
        tex: A flat (preprocessed or raw) LaTeX string, typically produced
             by unfold(). Should contain \\begin{document}...\\end{document}.

    Returns:
        (expanded_tex, packages_list, problematic_macros) where:
        - expanded_tex: the document body with all resolvable macros expanded.
        - packages_list: list of package names found in the preamble.
        - problematic_macros: list of (csname, pos, reason) tuples for macros
          that could not be expanded (pattern_mismatch or no_progress).
    """
    preamble, document, list_packages = preprocessing(tex)
    macro_dict, find_macro = build_dictionary(preamble)
    expanded_tex, problematic_macros = expand(document, macro_dict, find_macro)
    return expanded_tex, list_packages, problematic_macros
