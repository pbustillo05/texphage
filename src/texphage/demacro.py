## WAYS TO CREATE MACROS
### CLASSICAL WAYS:
# \def, \(re)newcommand, \let, \(re)newenvironment
## Variations: \edef, \gdef=\global\def and \xdef=\global\edef
# and the weird ones: \globaldefs, \futurelet => these looks crazy
#SHIT: how about \providecommand
## Prefixes:
#   -\long can be ignored
#   -\outer should NEVER be used: it creates macros which can't be used inside other macros.. can be ignored if used, it doesnt change meaning
#   -\global can be ignored (should be very rare)
#   -\expandafter is DANGER (absolutely crazy.. avoid it) => ONLY reasonnable use is to create commands with \csname ... \endcsname

###LATEX3
### XPARSE:
    # \NewDocumentCommand \RenewDocumentCommand \ProvideDocumentCommand \DeclareDocumentCommand
    # \NewDocumentEnvironment \RenewDocumentEnvironment \ProvideDocumentEnvironment \DeclareDocumentEnvironment
    # \NewExpandableDocumentCommand \RenewExpandableDocumentCommand \ProvideExpandableDocumentCommand \DeclareExpandableDocumentCommand
# \IfNoValue(TF) \IfValue(TF) \IfBoolean(TF)
## XARGS:
    # \newcommandx \renewcommandx \newenvironmentx \renewenvironmentx \providecommandx \DeclareRobustCommandx
    # these above work with a key list instead of default values
# XTEMPLATE

### KEYS
#expkv, keyval, xkeyval, ltxkeys, l3keys(2e), pgfkeys, kvsetkeys (used in keycommand), kvdefinekeys, options, simplekv, yax, kvoptions

### SPECIAL PACKAGES:
    # letltxmacro: \LetLtxMacro: same as \let except it works for macro with optional arguments and for robust macros
    # etoolbox: \(renew|new|provide)robustcmd(*) + many many weird stuff
    # twoopt: \(renew|new|provide)commandtwoopt with 2 optional arguments
# suffix: \withsuffix weird stuff
    # environ: \NewEnviron
        #\NewEnviron{⟨name⟩}[⟨N. args⟩][⟨opt. arg.⟩]{⟨macro code⟩}[⟨final code⟩] with \BODY of \environbodyname\.. and \environfinalcode{...}
    # newenviron: \newenviron (very similar)
        #\newenviron{⟨name⟩}[⟨N. args⟩][⟨opt. arg.⟩]{start code⟩}{(macro code)} with \envbody or \<envname>body
# ifthen (obsolete, now superseeded by etoolbox)
# cmdhook: Allows hooking into existing commands and modifying their behavior.
     #too crazy: adds after/before code to any command

### FONTS, COUNTERS and DIMS/BOXES:
# \letcharcode \chardef \charsubdef \charsubdefmax \mathchardef \newfont
# \countdef \newcounter
# \dimendef \muskipdef \skipdef \toksdef \newlength \newsavebox

## TO DO:
# - Find a way to deal with \expandafter especially in \csname ... \endcsname
# - Add support for the "expandable" commands from xparse
# - Add support for grouping
# - Add support for conditional statements (especially for starred environments)
# - Add support for tikzset
# - Add support for \makeatletter and \makeatother: could simply add them when expanding.. this works just fine
# - Add support for \mathpalette: could replace first argument by \currentmathstyle if the mathstyle package is present (this package seems to break xy though)

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import regex as re

from texphage._regex import (
    embed_braces,
    embed_brackets,
    find_com,
    find_env,
    num_args,
    token,
    xparse,
)

from .find_packages import find_used_packages

logger = logging.getLogger(__name__)

## ALL NECESSARY REGEX

# Naming a command
### IDEALLY: we use the following find_com to catch macros using a single symbol as a command. Unfortunately, this means a bit more work to adapt the regex..
# find_com = re.compile(r'\\([a-zA-Z]+|[^a-zA-Z])')
new_csname = lambda s : r'(?<%s>%s|\{ ?%s ?\})' %(s, find_com.pattern, find_com.pattern)
def com_name(csname: str) -> str:
    m = find_com.search(csname)
    assert m is not None
    return str(m[1])


def env_name(csname: str) -> tuple[str, str]:
    name = find_env.search(csname)
    assert name is not None
    if name[2]:
        return (str(name[1]) + '_star', str(name[1]) + r' ?\*')
    else:
        return (str(name[1]), str(name[1]))


find_specific_com = lambda s : r'(?<%s>\\(?:%s)(?![a-zA-Z]))' %(s,s)


def find_specific_env(csname: str) -> str:
    if csname[0] == '{':
        truncated = csname[1:-1]
        if re.fullmatch(r'[a-zA-Z]+', truncated):
            # 5 placeholders: group-name, begin-csname, end-csname, cmd-name, end-cmd-name
            return r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z])|\\end%s(?![a-zA-Z]))' % (truncated, csname, csname, truncated, truncated)
        elif re.fullmatch(r'[^a-zA-Z]', truncated):
            # 4 placeholders: group-name, begin-csname, end-csname, cmd-name
            return r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z]))' % (truncated, csname, csname, truncated)
    elif csname[0] == '\\':
        pass #technically, if this token expands to characters, it can be used as a macro name
    else:
        return r'(?<%s>\\begin ?%s|\\end ?%s)' %(csname, csname, csname)
    return ''

# Commands

# MATCHES: \def\cmdname<pattern>{body}  or  \gdef\cmdname<pattern>{body}
# CAPTURES:
#   def_csname   → the command name token, e.g. \foo or {\foo}
#   def_pattern  → TeX parameter text between name and body, e.g. "#1 and #2"
#                  (may be empty for zero-argument commands)
#   def_content  → the replacement body: a single token or a {brace group}
# LIMITATIONS:
#   - \long\def and \outer\def prefixes not handled (they are ignored in practice)
#   - Single-symbol command names (\|, \!) not matched (find_com only handles [a-zA-Z]+)
#   - Delimited arguments (token patterns) are captured verbatim; build_dictionary
#     converts #N placeholders into named capture groups at expansion time
find_def = r'\\g?def ?%s(?<def_pattern>[^\{]*)%s' %(new_csname('def_csname'), token('def_content'))

# MATCHES: \edef\cmdname<pattern>{body}  or  \xdef\cmdname<pattern>{body}
# CAPTURES:
#   edef_csname   → the command name token
#   edef_pattern  → parameter text (same as def_pattern)
#   edef_content  → replacement body, expanded immediately using current macro_dict
# LIMITATIONS:
#   - Same single-symbol and prefix limitations as find_def
#   - \xdef is \global\edef; the \global scope is ignored (same semantics for expansion)
#   - Expansion is done by calling expand() on edef_content at parse time;
#     fully recursive \edef chains may not expand completely in one pass
find_edef = r'\\(e|x)def ?%s(?<edef_pattern>[^{]*)%s' %(new_csname('edef_csname'), token('edef_content'))

# MATCHES: \let\alias\original  or  \let\alias=\original  or  \let\alias<token>
#          Also \LetLtxMacro and \GlobalLetLtxMacro (letltxmacro package).
#          Docs: https://ctan.org/pkg/letltxmacro
# CAPTURES:
#   let_csname          → the new alias name
#   let_content         → the right-hand side: either a control sequence or a single char
#   let_called_csname   → if RHS is a control sequence, its name (without \)
# LIMITATIONS:
#   - If let_called_csname is already in macro_dict, the alias inherits the same
#     expansion pattern. If not, let_content is stored as a literal string replacement.
#   - \futurelet is not handled.
find_let = r'\\(?:let|LetLtxMacro|GlobalLetLtxMacro) ?%s ?=? ?(?<let_content>(?:\\(?<let_called_csname>[a-zA-Z]+))|.)' %new_csname('let_csname')

# MATCHES: \newcommand{\cmdname}[N][default]{body}  and variants:
#          \renewcommand, \providecommand, \newrobustcmd, \renewrobustcmd,
#          \providerobustcmd (etoolbox), \DeclareRobustCommand,
#          \newcommandtwoopt, \renewcommandtwoopt (twoopt package),
#          all optionally followed by 'x' (xargs variant).
#          Docs: https://ctan.org/pkg/xargs  https://ctan.org/pkg/etoolbox
#                https://ctan.org/pkg/twoopt
# CAPTURES:
#   new_com_csname    → the command name
#   new_com_xargs     → 'x' if this is an xargs variant, else None
#   new_com_num_args  → the optional [N] argument count, e.g. "2"
#   new_com_default1  → first optional default value [default]
#   new_com_default2  → second optional default (twoopt only)
#   new_com_content   → the replacement body
# LIMITATIONS:
#   - \newcommand* (starred form) is matched but treated identically to unstarred
#     (starred disallows \par in args; irrelevant for macro expansion)
#   - xargs positional key [i=default] syntax (e.g. [1=Hello]) is NOT supported;
#     see BUGS.md for the open issue
#   - robustcmd 'x' variants technically don't exist but are harmlessly matched
find_new_com = r'\\(?:(?:renew|new|provide)(?:command(?:twoopt)?|robustcmd)|DeclareRobustCommand)(?<new_com_xargs>x)? ?\*? ?%s ?%s ?%s ?%s ?%s' %(new_csname('new_com_csname'), num_args('new_com_num_args'), embed_braces('new_com_default1'), embed_braces('new_com_default2'), token('new_com_content')) #technically, the robustcmd "x" variants don't exist
#find_twoopt = r'\\(renew|new|provide)commandtwoopt ?\*? ?%s ?%s ?%s ?%s ?%s' %(new_csname('new_com_csname'), num_args('new_com_num_args'), embed_braces('new_com_default1'), embed_braces('new_com_default2'), token('new_com_content'))

# MATCHES: \NewDocumentCommand{\cmdname}{arg-spec}{body}  and variants:
#          \RenewDocumentCommand, \ProvideDocumentCommand, \DeclareDocumentCommand,
#          \NewExpandableDocumentCommand (and Renew/Provide/Declare variants).
#          xparse is now part of the LaTeX kernel. Docs: https://ctan.org/pkg/xparse
# CAPTURES:
#   new_doc_com_csname  → the command name
#   new_doc_com_args    → the xparse argument specification string, e.g. "m o O{default} s"
#   new_doc_com_content → the replacement body
# LIMITATIONS:
#   - Argument types supported: m, o, O{default}, s, t<token>
#   - Unsupported: r<tok1><tok2>, R, v, b, e, E, >, +m, +o, etc.
#   - \IfNoValueTF / \IfBooleanTF conditionals inside the body are NOT evaluated
find_new_doc_com = r'\\(?:New|Renew|Provide|Declare)(?:Expandable)?DocumentCommand ?%s ?%s ?%s' %(new_csname('new_doc_com_csname'), token('new_doc_com_args'), token('new_doc_com_content'))

# Environments

# MATCHES: \newenvironment{name}[N][default]{begin}{end}  and \renewenvironment variants,
#          optionally with 'x' suffix (xargs). Docs: https://ctan.org/pkg/xargs
# CAPTURES:
#   new_env_csname    → environment name token
#   new_env_xargs     → 'x' if xargs variant, else None
#   new_env_num_args  → optional [N] argument count
#   new_env_default   → optional [default] for first argument
#   new_env_begin     → begin-code token or {brace group}
#   new_env_end       → end-code token or {brace group}
# LIMITATIONS:
#   - xargs positional key syntax not supported (same as find_new_com)
#   - Starred environments (name*) are handled via env_name() returning (name_star, name ?\*)
find_new_env = r'\\(?:re)?newenvironment(?<new_env_xargs>x)? ?\*? ?%s ?%s ?%s ?%s ?%s' %(token('new_env_csname'), num_args('new_env_num_args'), embed_braces('new_env_default'), token('new_env_begin'), token('new_env_end'))

# MATCHES: \NewDocumentEnvironment{name}{arg-spec}{begin}{end}  and variants.
#          Docs: https://ctan.org/pkg/xparse
# CAPTURES:
#   new_doc_env_csname  → environment name
#   new_doc_env_args    → xparse argument specification string
#   new_doc_env_begin   → begin-code
#   new_doc_env_end     → end-code
# LIMITATIONS:
#   - Same xparse argument type limitations as find_new_doc_com
find_new_doc_env = r'\\(?:New|Renew|Provide|Declare)DocumentEnvironment ?%s ?%s ?%s ?%s' %(token('new_doc_env_csname'), token('new_doc_env_args'), token('new_doc_env_begin'), token('new_doc_env_end'))

# MATCHES: \NewEnviron{name}[N][default]{body}[\finalcode]  and \RenewEnviron.
#          The environ package captures the body as \BODY. Docs: https://ctan.org/pkg/environ
# CAPTURES:
#   New_Env_csname    → environment name
#   New_Env_num_args  → optional [N] argument count
#   New_Env_default   → optional [default]
#   New_Env_content   → the macro body (references \BODY for the environment content)
#   New_Env_end       → optional [final-code] appended after body expansion
# LIMITATIONS:
#   - \BODY substitution is not performed during expansion (body is treated as opaque text)
#   - \environbodyname customisation not handled
find_New_Environ = r'\\(?:Ren|N)ewEnviron ?%s ?%s ?%s ?%s ?%s' %(token('New_Env_csname'), num_args('New_Env_num_args'), embed_braces('New_Env_default'), token('New_Env_content'), embed_braces('New_Env_end'))

# MATCHES: \newenviron{name}[N][default]{begin-code}{body}  and \renewenviron.
#          The newenviron package (older alternative to environ). Docs: https://ctan.org/pkg/newenviron
# CAPTURES:
#   New_Env_csname    → environment name  (shares group names with find_New_Environ)
#   New_Env_num_args  → optional [N]
#   New_Env_default   → optional [default]
#   New_Env_begin     → begin-code
#   New_Env_content   → body macro (references \envbody or \<name>body)
# LIMITATIONS:
#   - \envbody substitution not performed (same limitation as find_New_Environ)
find_new_environ = r'\\(?:re)?newenviron ?%s ?%s ?%s ?%s ?%s' %(token('New_Env_csname'), num_args('New_Env_num_args'), embed_braces('New_Env_default'), token('New_Env_begin'), token('New_Env_content'))

# Weird stuff
find_weird_stuff = r'(?<mathpalette>\\mathpalette)|(?<makeatother>\\makeatother)|(?<makeatletter>\\makeatletter)'

## KEYS: pgfkeys
key = lambda s : r' ?(?<%s>(?:\/(?!\.))?(?:[^=,\/]+?(?:\/(?!\.)))*)(?<%s>[^=,\/]+?)(?<%s>\/.[^=,\/]+?)? ?' %(s + '_path', s + '_name', s + '_handler')
value = lambda s : r'(?<%s>(?:%s|[^,\{\}])*)' %(s, embed_brackets('brackted_' + s))
key_value = r'(?!\s)%s(?:=%s)?(?=,|\})' %(key('key'), value('value'))

# MATCHES: any macro-definition command in the preamble — the union of all patterns above.
# CAPTURES: top-level groups 'def', 'edef', 'let', 'new_com', 'new_env',
#           'new_doc_com', 'new_doc_env' identify which branch matched.
#           All sub-captures from the matched branch are also available.
# NOTE: find_New_Environ and find_new_environ are NOT included here; they are
#       handled by find_new_env's branch in build_dictionary via the xargs flag.
# LIMITATIONS:
#   - find_weird_stuff (mathpalette, makeatletter) is not included; those are
#     detected in build_dictionary but not acted upon in the current implementation.
#   - The elif chain order in build_dictionary() is load-order-sensitive:
#     \edef must expand immediately using the current dict state; do not reorder.
find_all = re.compile(r'(?<def>%s)|(?<edef>%s)|(?<let>%s)|(?<new_com>%s)|(?<new_env>%s)|(?<new_doc_com>%s)|(?<new_doc_env>%s)' %(find_def, find_edef, find_let, find_new_com, find_new_env, find_new_doc_com, find_new_doc_env))

## PREPROCESSING: verbatim protection, whitespace normalisation, package list

# Environments whose content must not be whitespace-normalised.
# They produce literal verbatim output; collapsing their whitespace corrupts the PDF.
_VERBATIM_ENVS = re.compile(
    r'\\begin\{(verbatim\*?|Verbatim\*?|lstlisting|minted|alltt|BVerbatim|LVerbatim)\}'
    r'.*?'
    r'\\end\{\1\}',
    re.DOTALL,
)
# Placeholder: long unique prefix, no TeX-special characters.
_VERBATIM_PLACEHOLDER = 'texphageVERBATIM{}ENDVERBATIM'


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

    tex = _VERBATIM_ENVS.sub(_stash, tex)

    # Step 2: Strip LaTeX comments.
    # (?<!\\) negative lookbehind: only % not preceded by backslash.
    # [^\n]* consumes rest of line, preserving the newline for Step 3.
    tex = re.sub(r'(?<!\\)%[^\n]*', '', tex)

    # Step 3: Preserve paragraph breaks BEFORE collapsing whitespace.
    # \n[ \t]*\n+ = one or more blank lines.
    # MUST run before Step 4, or blank lines collapse to spaces.
    tex = re.sub(r'\n[ \t]*\n+', r' \\par ', tex)

    # Step 4: Collapse all remaining whitespace to exactly one space.
    tex = re.sub(r'[ \t\n]+', ' ', tex)

    # Step 5: Restore verbatim blocks.
    for key, value in verbatim_store.items():
        tex = tex.replace(key, value)

    # Step 6: Split preamble from body.
    parts = re.split(
        r'\\begin ?\{ ?document ?\}|\\end ?\{ ?document ?\}', tex, maxsplit=2
    )
    if len(parts) < 3:
        return '', tex, find_used_packages(tex)
    preamble, document, _epilogue = parts
    return preamble, document, find_used_packages(preamble)

__all__ = ["demacro", "preprocessing", "build_dictionary", "expand"]

###### DICTIONARY BUIDLING
def content_replacement(
    local_content: str, default_dict: dict = {}, boolean_list: list = []
) -> Callable:
    def content(arg: Any) -> str:
        def arg_replacement(num: Any) -> str:
            if re.search(r'#', num[1]):
                return num[1]
            else:
                try:
                    input = arg.group('arg' + num[1][-1:])
                    if num[1][-1:] not in boolean_list:
                        return input
                    else:
                        return r'\BooleanTrue'
                except IndexError:
                    logger.debug('content_replacement: missing group arg%s, using default', num[1][-1:])
                    return default_dict[num[1][-1:]]
        return re.sub(r'#(#*\d)', arg_replacement, local_content)
    return content

def build_dictionary(tex: str) -> tuple[dict, str]:
    """Parse the preamble and build a macro expansion dictionary.

    Iterates over find_all matches in order. For each definition found,
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
    # to_expand = r'(?<_pattern_>%s)' %pattern.pattern
    for macro in re.finditer(find_all, tex):
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
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + re.sub(r'#(\d)', lambda num : r'(?<%s>%s)' %('arg' + num[1], token('bracket_arg'+ num[1])), macro.group('def_pattern'))
            content = content_replacement(macro.group('def_content'))
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('edef'):
            csname = com_name(macro.group('edef_csname'))
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + re.sub(r'#(\d)', lambda num : r'(?<%s>%s)' %('arg' + num[1], token('bracket_arg'+ num[1])), macro.group('edef_pattern'))
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
                    default_dict['1'] = macro.group('new_com_default1')
                if macro.group('new_com_default2'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg2')
                    default_dict['2'] = macro.group('new_com_default2')
                while i < num_args:
                    i+=1
                    pattern += r' ?(?<%s>%s)' %('arg' + str(i), token('bracket_arg' + str(i)))
                content = content_replacement(macro.group('new_com_content'), default_dict)
            else:   #else used here because otherwise the re.sub seemed to fail.. can it be removed?
                # Lambda used here because (for some reason) it makes macro.group('new_com_content') be seen as raw
                content = lambda arg, local_content = macro.group('new_com_content') : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('new_doc_com'):
            csname = com_name(macro.group('new_doc_com_csname'))
            pattern = r'\\%s(?![a-zA-Z])' %csname
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(xparse, macro.group('new_doc_com_args')):
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
                content = lambda arg, local_content = macro.group('new_doc_com_content') : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder

        # ENVIRONMENTS
        elif macro.group('new_env'):
            csname_group, csname_latex = env_name(macro.group('new_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
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
            content = lambda arg : begin(arg) + arg.group('between') + end(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        elif macro.group('new_doc_env'):
            csname_group, csname_latex = env_name(macro.group('new_doc_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(xparse, macro.group('new_doc_env_args')):
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
            content = lambda arg : begin(arg) + arg.group(between) + end(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        else: #tikzset
            pass
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
    macro = re.search(find_macro, tex)
    pos = 0
    problematic_macros = []
    while macro:
        pos += macro.start()
        macro_def = macro_dict[macro.lastgroup]
        if re.search(macro_def[0], tex[pos:]):
            new_tex = tex[:pos] + re.sub(macro_def[0], macro_def[1], tex[pos:], count=1)
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
