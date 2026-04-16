"""Shared PCRE regex primitives for the texphage package.

WARNING: Patterns in Sections 5 and 6 are interdependent.
Do not modify without reading the DANGER ZONE rules in CLAUDE.md.

Requires the `regex` package (not `re`): patterns use PCRE recursive groups
(?&name) and duplicate named groups in alternations — neither supported by `re`.

All macro-matching patterns (Sections 5–6) assume preprocessing has produced
a flat single-line string with at most one ASCII space between tokens
(see demacro.preprocessing).  Preprocessing patterns (Section 4) operate on
raw multi-line source and are exempt from that invariant.

Organisation
------------
Section 1  General TeX structural primitives   (building blocks for all below)
Section 2  Control-sequence & environment-name matchers
Section 3  Control-sequence helper functions
Section 4  Package-finding patterns             (find_packages.py)
Section 5  Preprocessing patterns               (demacro.preprocessing)
Section 6  Macro-definition patterns            (demacro.build_dictionary / expand)
Section 7  Preamble-building patterns           (pipeline.build_minimal_preamble)
Section 8  Attachment-finding patterns          (pipeline.find_attachments)

Naming conventions
------------------
compiled regex.compile() object : _UPPER_SNAKE_CASE_RE
raw regex pattern string        : _UPPER_SNAKE_CASE_PATTERN
pattern-builder lambda/function : snake_case
"""
from __future__ import annotations

import regex as re

# ============================================================================
# Section 1 — General TeX structural primitives
# ============================================================================
# Building blocks used across Sections 2–8.  Order matters: later definitions
# reference earlier ones.

# embed_brackets(s): matches a balanced {…} group, recursively.
# Named group `s` captures the entire {…} including outer braces.
# (?<!\\) prevents matching \{ (escaped brace).
# (?&s) recursion allows arbitrary nesting: {{inner} outer}.
# Used for: mandatory arguments — \cmd{arg}.
embed_brackets = lambda s: (
    r'(?<%s>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?&%s))*(?<!\\)\})' % (s, s)
)

# embed_braces(s): matches an optional […] argument, or nothing.
# Trailing ? makes the whole group optional.
# ASSUMPTION: [ inside an optional arg is only used for nested optional args,
#   not as a bare character (e.g. not in math mode).
# LIMITATION: bare [ in math inside optional args breaks this pattern.
# Used for: optional arguments — \cmd[opt]{arg}.
embed_braces = lambda s: (
    r'(?<%s>(?<!\\)\[(?:[^\[\]]++|(?<=\\)\[|(?<=\\)\]|(?&%s))*(?<!\\)\])?' % (s, s)
)

# _NOT_TOKEN_CHAR_PATTERN: any char that is not a TeX structural token (\, {, }).
_NOT_TOKEN_CHAR_PATTERN = r'[^\\\{\}]'

# token(s): matches exactly one TeX token:
#   - a single non-special character (e.g. 'a', '1', '+')
#   - a control sequence (e.g. \frac, \alpha)
#   - a balanced brace group {…}
# Used for: \def argument patterns and single-token arguments.
token = lambda s: r'(%s|(?:\\[a-zA-Z]+)|%s)' % (_NOT_TOKEN_CHAR_PATTERN, embed_brackets(s))

# num_args(s): matches optional [N] argument count.
# Used in: \newcommand{\cmd}[N]{body} — the [N] part.
num_args = lambda s: r'(?:\[ ?(?<%s>\d) ?\])?' % s


# ============================================================================
# Section 2 — Control-sequence and environment-name matchers
# ============================================================================

# _FIND_COMMAND_RE: matches a control sequence like \foobar.
# MATCHES: \ followed by one or more ASCII letters.
# CAPTURES: group 1 = command name without backslash, e.g. "foobar".
# LIMITATIONS:
#   [observed] Single-symbol names (\|, \!) are not handled.
_FIND_COMMAND_RE = re.compile(r'\\([a-zA-Z]+)')

# _FIND_ENV_RE: matches an environment name, optionally starred.
# MATCHES: one or more letters optionally followed by * (with optional space).
# CAPTURES: group 1 = env name; group 2 = '*' or None.
# LIMITATIONS:
#   [inferred] Names with digits or hyphens (e.g. "align-2") are not matched.
_FIND_ENV_RE = re.compile(r'([a-zA-Z]+) ?(\*)?')

# _XPARSE_PATTERN: raw string matching one xparse argument specifier.
# xparse (now in LaTeX kernel) describes arguments as a string like
# "m o O{default} s t\X":
#   m  → mandatory {…} or single token
#   o  → optional []; \NoValue if absent
#   O  → optional [] with explicit default value
#   s  → optional star; expands to \BooleanTrue or \BooleanFalse
#   t  → optional specific token; expands to \BooleanTrue or \BooleanFalse
# Docs: https://ctan.org/pkg/xparse
# LIMITATIONS:
#   [inferred] r, R, v, b, e, E, >, +o unsupported (rare xparse argument types).
_XPARSE_PATTERN = (
    r'(?<m>\+?m)|(?<o>o)|(?<O>O%s)|(?<s>s)|(?<t>t[^\\\{\}])' % embed_brackets('default')
)


# ============================================================================
# Section 3 — Control-sequence helper functions
# ============================================================================
# These build dynamic regex fragments or extract names from matched tokens.
# Convention: pattern-builder lambdas/functions use snake_case.

# new_csname(s): pattern matching a command token in either bare or braced form.
# Matches: \foobar  or  { \foobar }  (the two forms LaTeX uses for csnames).
# Used for: the command-name slot in \def, \newcommand, etc.
new_csname = lambda s: (
    r'(?<%s>%s|\{ ?%s ?\})' % (s, _FIND_COMMAND_RE.pattern, _FIND_COMMAND_RE.pattern)
)


def com_name(csname: str) -> str:
    """Extract the bare command name (no backslash) from a csname token.

    Handles both bare ``\\foobar`` and braced ``{ \\foobar }`` forms.
    """
    m = _FIND_COMMAND_RE.search(csname)
    assert m is not None
    return str(m[1])


def env_name(csname: str) -> tuple[str, str]:
    """Return ``(group_name, latex_pattern)`` for an environment csname token.

    For a plain name like ``{gather}`` returns ``('gather', 'gather')``.
    For a starred name like ``{gather*}`` returns
    ``('gather_star', r'gather ?\\\\*')``.
    The *group_name* is used as the macro_dict key; *latex_pattern* goes into
    ``\\\\begin{…}`` / ``\\\\end{…}`` match patterns.
    """
    name_m = _FIND_ENV_RE.search(csname)
    assert name_m is not None
    if name_m[2]:
        return (str(name_m[1]) + '_star', str(name_m[1]) + r' ?\*')
    else:
        return (str(name_m[1]), str(name_m[1]))


# find_specific_com(s): pattern matching exactly \s (word-boundary protected).
# MATCHES: \foobar not followed by another letter.
# CAPTURES: the full match into named group s.
# Used for: building the find_macro alternation in build_dictionary.
find_specific_com = lambda s: r'(?<%s>\\(?:%s)(?![a-zA-Z]))' % (s, s)

# _BRACE_LETTER_RE / _BRACE_SYMBOL_RE: helpers for find_specific_env.
_BRACE_LETTER_RE = re.compile(r'^\{([a-zA-Z]+)\}$')
_BRACE_SYMBOL_RE = re.compile(r'^\{([^a-zA-Z{}\s])\}$')
_CTRL_PREFIX_RE  = re.compile(r'^\\')


def find_specific_env(csname: str) -> str:
    """Build a named-group pattern matching all uses of environment *csname*.

    Handles brace-delimited (``{envname}``), bare names, and single-symbol
    variants.  Returns empty string for control-sequence csnames (``\\foo``),
    which cannot be used as plain environment names.

    MATCHES (for letter-name ``{foo}``):
        \\begin{foo}, \\end{foo}, \\foo (word-boundary), \\endfoo.
    MATCHES (for single non-letter ``{+}``):
        \\begin{+}, \\end{+}, \\+.
    MATCHES (for bare word ``foo``):
        \\begin{foo}, \\end{foo}.
    """
    m_letter = _BRACE_LETTER_RE.match(csname)
    m_symbol = _BRACE_SYMBOL_RE.match(csname)
    if m_letter:
        truncated = m_letter.group(1)
        return (
            r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z])|\\end%s(?![a-zA-Z]))'
            % (truncated, csname, csname, truncated, truncated)
        )
    elif m_symbol:
        truncated = m_symbol.group(1)
        return (
            r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z]))'
            % (truncated, csname, csname, truncated)
        )
    elif _CTRL_PREFIX_RE.match(csname):
        pass  # \foo-style csname cannot be used as a plain env name
    else:
        return r'(?<%s>\\begin ?%s|\\end ?%s)' % (csname, csname, csname)
    return ''


# ============================================================================
# Section 4 — Package-finding patterns   (used by find_packages.py)
# ============================================================================

# _FIND_FILE_RE: individual package / library name token inside a comma list.
# MATCHES: one package/library name, e.g. "amsmath" or "defs_pp1".
# CAPTURES: the full match.
# LIMITATIONS:
#   [observed] CTAN packages do not use underscores, but arXiv bundled .sty
#              files routinely do (e.g. defs_pp1.sty). Underscore is required.
_FIND_FILE_RE = re.compile(r'[a-z0-9\+\-\._]+')

# _FIND_PKG_LIB_RE: matches \usepackage, \RequirePackage, \usetikzlibrary,
# \usepgflibrary calls in LaTeX source.
# MATCHES: \usepackage[opts]{pkg1,pkg2}  or  \usetikzlibrary{lib1,lib2}
# CAPTURES:
#   group 1   → "usepackage" or "RequirePackage"
#   options   → optional [...] argument (via embed_braces)
#   packages  → comma-separated package names
#   type      → "tikz" or "pgf" for library calls
#   libraries → comma-separated library names
# LIMITATIONS:
#   [observed] Underscore in package names needed for bundled .sty files (BUG-21).
#   [inferred] Does not match \usepackage with @ in name (rare).
_FIND_PKG_LIB_RE = re.compile(
    r'^[^%%\n]*(?:\\(usepackage|RequirePackage)\s*%s\s*\{(?<packages>(?:[a-z0-9\+\-\._]+| |,)+)\}'
    r'|\\use(?<type>tikz|pgf)library\s*\{(?<libraries>(?:[a-z0-9\+\-\._]+| |,)+)\})'
    % embed_braces('options'),
    flags=re.MULTILINE,
)

# _LETTERS_RE: checks if a string contains any ASCII letter.
# Used by find_command to classify csname types (letter-only vs symbol).
_LETTERS_RE = re.compile(r'[a-zA-Z]')

# _TIKZ_PREFIX_RE: checks if a filename begins with "tikz".
# Used by get_path to try a pgf-prefixed fallback for tikz libraries.
_TIKZ_PREFIX_RE = re.compile(r'^tikz')

# _COLON_RE: detects / strips colons from tikzlibrary names.
# Tikz library specifiers use "tikzlibrary:arrows" colon-separator syntax.
_COLON_RE = re.compile(r':')

# _CMD_DEF_KEYWORDS_PATTERN: raw alternation of ALL command-definition keywords.
# Shared sub-pattern reused in find_command (find_packages.py) and in
# _DEF_PATTERN / _NEW_COM_PATTERN etc. via the _FIND_ALL_RE union.
# Covers: \def family, \let, \newcommand family, \DeclareRobustCommand family,
#         xparse \NewDocumentCommand family.
_CMD_DEF_KEYWORDS_PATTERN = (
    r'(?:e|x|g)?def'
    r'|let'
    r'|LetLtxMacro'
    r'|GlobalLetLtxMacro'
    r'|(?:re|new|provide)(?:command(?:twoopt)?|robustcmd)x?'
    r'|(?:Declare|Check)RobustCommandx?'
    r'|DeclareRobustCommandx?'
    r'|(?:New|Renew|Provide|Declare)(?:Expandable)?DocumentCommand'
)

# _ENV_DEF_KEYWORDS_PATTERN: raw alternation of ALL environment-definition keywords.
# Shared sub-pattern reused in find_command.
_ENV_DEF_KEYWORDS_PATTERN = (
    r'(?:re)?newenvironmentx?'
    r'|(?:New|Renew|Provide|Declare)DocumentEnvironment'
    r'|NewEnviron'
    r'|newenviron'
)


# ============================================================================
# Section 5 — Preprocessing patterns   (used by demacro.preprocessing)
# ============================================================================

# _VERBATIM_ENVS_RE: verbatim-like environments whose content must not be
# whitespace-normalised.  Stashed in preprocessing Step 1.
# MATCHES: \begin{verbatim}…\end{verbatim} and all known verbatim variants.
# CAPTURES: group 1 = environment name (for back-reference in \end{…}).
# LIMITATIONS:
#   [inferred] Custom verbatim-like environments (e.g. via fancyvrb \DefineVerbatimEnvironment)
#              are not stashed; their content is whitespace-collapsed like normal text.
_VERBATIM_ENVS_RE = re.compile(
    r'\\begin\{(verbatim\*?|Verbatim\*?|lstlisting|minted|alltt|BVerbatim|LVerbatim)\}'
    r'.*?'
    r'\\end\{\1\}',
    re.DOTALL,
)

# _COMMENT_RE: LaTeX line comment — % to end of line (preprocessing Step 2).
# (?<!\\) ensures \% (escaped percent) is not stripped.
_COMMENT_RE = re.compile(r'(?<!\\)%[^\n]*')

# _BLOCK_COMMENT_RE: \begin{comment}…\end{comment} (comment package, Step 2b).
# Produces no output; discarded entirely.
_BLOCK_COMMENT_RE = re.compile(r'\\begin\{comment\}.*?\\end\{comment\}', re.DOTALL)

# _BLANK_LINE_RE: one or more blank lines → \par (preprocessing Step 3).
# Must run BEFORE whitespace collapse.
_BLANK_LINE_RE = re.compile(r'\n[ \t]*\n+')

# _WHITESPACE_RE: any run of whitespace → single space (preprocessing Step 4).
_WHITESPACE_RE = re.compile(r'[ \t\n]+')

# _DOCUMENT_SPLIT_RE: boundary markers for preamble/body split (preprocessing Step 6).
_DOCUMENT_SPLIT_RE = re.compile(r'\\begin ?\{ ?document ?\}|\\end ?\{ ?document ?\}')

# _BEGIN_DOCUMENT_RE: matches \begin{document} (strict, for preamble extraction).
# Used by build_minimal_preamble to locate the end of the preamble.
_BEGIN_DOCUMENT_RE = re.compile(r'\\begin\{document\}')

# _DOC_SPLIT_RE: captures preamble and body from a complete .tex document.
# Operates on raw (non-preprocessed) source with DOTALL so content may span lines.
# MATCHES: \documentclass…\begin{document}…\end{document} structure.
# CAPTURES:
#   preamble → everything before \begin{document} (incl. \documentclass line).
#   body     → everything between \begin{document} and \end{document}.
# LIMITATIONS:
#   [inferred] Does not handle nested \begin{document} (unusual/invalid LaTeX).
#   [inferred] If \begin{document} or \end{document} is absent, search() returns
#              None; callers must handle this case explicitly.
# USED BY: texphage.cli.main_convert
_DOC_SPLIT_RE = re.compile(
    r'(?P<preamble>.*?)\\begin\{document\}(?P<body>.*?)\\end\{document\}',
    re.DOTALL,
)

# _PAR_TOKENIZER_RE: tokenizer for _strip_par_in_groups (demacro.py).
# Splits the flat preprocessed string into the tokens that affect brace / math
# depth, or that are \par (the only token that may be stripped).
# MATCHES (named groups):
#   par       → \par token (optionally followed by its trailing space)
#   begin     → \begin{envname}; subgroup begin_env captures envname
#   end       → \end{envname};   subgroup end_env   captures envname
#   open      → { (open brace — increments brace depth)
#   close     → } (close brace — decrements brace depth)
#   ctrl      → any other control sequence (\foo or \X)
#   text      → run of non-special characters (letters, spaces, digits, …)
# LIMITATIONS:
#   [observed] \par detection uses (?![a-zA-Z]) (negative lookahead), matching
#              the TeXbook rule: \par is only a paragraph break when the control
#              sequence name is exactly 'par' with no following letter.
#   [observed] Tokenizer is gap-free: every character in the input is covered
#              by exactly one group; ''.join(m[0] for m) == original string.
_PAR_TOKENIZER_RE = re.compile(
    r'(?P<par>\\par(?![a-zA-Z]) ?)'
    r'|(?P<begin>\\begin\s*\{(?P<begin_env>[^}]*)\})'
    r'|(?P<end>\\end\s*\{(?P<end_env>[^}]*)\})'
    r'|(?P<open>\{)'
    r'|(?P<close>\})'
    r'|(?P<ctrl>\\(?:[a-zA-Z]+|.))'
    r'|(?P<text>[^\\{}]+)'
)

# _DEF_PARAM_PIECE_RE: tokenizer for _def_param_pattern (demacro.py).
# Parses one \def parameter-text token at a time.
# MATCHES (named groups):
#   hash  → digit N after a # sign (signals a parameter slot)
#   delim → literal delimiter text between this # and the next # (may be empty)
#   lit   → literal text that precedes any # (before the first parameter slot)
# LIMITATIONS:
#   [inferred] ## (doubled hash = literal # in replacement text) is not
#              explicitly handled; the leading # is skipped silently, matching
#              the behaviour of the original character-loop implementation.
_DEF_PARAM_PIECE_RE = re.compile(r'#(?P<hash>\d)(?P<delim>[^#]*)|(?P<lit>[^#]+)')

# _OUTER_DELIMITERS_RE: strip one layer of outer {} or [] from a captured token.
# MATCHES: {content}  or  [content]  (DOTALL so content may contain newlines).
# CAPTURES: group 1 (brace content) or group 2 (bracket content).
# LIMITATIONS:
#   [observed] Only strips the outermost delimiter layer; nested delimiters
#              inside are preserved (correct: called on already-captured tokens).
_OUTER_DELIMITERS_RE = re.compile(r'^\{(.*)\}$|^\[(.*)\]$', re.DOTALL)


# ============================================================================
# Section 6 — Macro-definition patterns   (used by demacro.build_dictionary)
# ============================================================================
# All patterns below assume the preprocessing invariant: flat single-line
# string with at most one space between tokens.
#
# Raw pattern strings : _UPPER_SNAKE_CASE_PATTERN
# Compiled objects    : _UPPER_SNAKE_CASE_RE
#
# The elif chain in build_dictionary() is order-sensitive; do not reorder
# the sub-patterns here or the _FIND_ALL_RE alternation below.

# MATCHES: \def\cmdname<pattern>{body}  or  \gdef\cmdname<pattern>{body}
# CAPTURES:
#   def_csname   → the command name token, e.g. \foo or {\foo}
#   def_pattern  → TeX parameter text between name and body, e.g. "#1 and #2"
#                  (may be empty for zero-argument commands)
#   def_content  → the replacement body: a single token or a {brace group}
# LIMITATIONS:
#   - \long\def and \outer\def prefixes not handled (ignored in practice)
#   - Single-symbol command names (\|, \!) not matched
#   - Delimited arguments captured verbatim; _def_param_pattern converts them
#   - [inferred] Doubled hashes (##) in parameter text not supported
_DEF_PATTERN = (
    r'\\g?def ?%s(?<def_pattern>[^\{]*)%s'
    % (new_csname('def_csname'), token('def_content'))
)

# MATCHES: \expandafter\def\csname<name>\endcsname{body}
#          and \expandafter\gdef\csname<name>\endcsname{body}
#          Standard TeX idiom for defining a command from a string.
#          Also matches the \long\expandafter variant.
# CAPTURES:
#   csname_def_name    → the literal name of the new command (without \)
#   csname_def_content → the replacement body
# LIMITATIONS:
#   [inferred] Name must be [a-zA-Z@]+ only; dynamic names not supported.
#   [inferred] \expandafter\edef\csname form not handled.
#   [observed] Direct and preamble-call-expanded forms both covered (BUG-19).
_CSNAME_DEF_PATTERN = (
    r'\\(?:long ?)?expandafter ?\\g?def ?\\csname ?'
    r'(?<csname_def_name>[a-zA-Z@]+) ?\\endcsname ?'
    + token('csname_def_content')
)

# _CSNAME_DEF_RE: compiled form of _CSNAME_DEF_PATTERN.
# Used separately in build_dictionary's preamble execution pass.
_CSNAME_DEF_RE = re.compile(_CSNAME_DEF_PATTERN)

# MATCHES: \edef\cmdname<pattern>{body}  or  \xdef\cmdname<pattern>{body}
# CAPTURES:
#   edef_csname   → the command name token
#   edef_pattern  → parameter text (same as def_pattern)
#   edef_content  → replacement body, expanded immediately at definition time
# LIMITATIONS:
#   - Same single-symbol and prefix limitations as _DEF_PATTERN
#   - Expansion done by calling expand() on edef_content at parse time;
#     fully recursive \edef chains may not expand completely in one pass
_EDEF_PATTERN = (
    r'\\(e|x)def ?%s(?<edef_pattern>[^{]*)%s'
    % (new_csname('edef_csname'), token('edef_content'))
)

# MATCHES: \let\alias\original  or  \let\alias=\original
#          Also \LetLtxMacro and \GlobalLetLtxMacro (letltxmacro package).
#          Docs: https://ctan.org/pkg/letltxmacro
# CAPTURES:
#   let_csname          → the new alias name
#   let_content         → the RHS: a control sequence or a single char
#   let_called_csname   → RHS command name (without \), if it is a control seq
# LIMITATIONS:
#   - If let_called_csname is in macro_dict, the alias inherits the expansion.
#   - \futurelet is not handled.
_LET_PATTERN = (
    r'\\(?:let|LetLtxMacro|GlobalLetLtxMacro) ?%s ?=? ?'
    r'(?<let_content>(?:\\(?<let_called_csname>[a-zA-Z]+))|.)'
    % new_csname('let_csname')
)

# MATCHES: \newcommand{\cmdname}[N][default]{body}  and variants:
#          \renewcommand, \providecommand, \newrobustcmd, \renewrobustcmd,
#          \providerobustcmd (etoolbox), \DeclareRobustCommand,
#          \newcommandtwoopt, \renewcommandtwoopt (twoopt package),
#          all optionally with 'x' suffix (xargs variant).
#          Docs: https://ctan.org/pkg/xargs  https://ctan.org/pkg/etoolbox
#                https://ctan.org/pkg/twoopt
# CAPTURES:
#   new_com_csname    → the command name
#   new_com_xargs     → 'x' if xargs variant, else None
#   new_com_num_args  → the optional [N] argument count, e.g. "2"
#   new_com_default1  → first optional default value [default]
#   new_com_default2  → second optional default (twoopt only)
#   new_com_content   → the replacement body
# LIMITATIONS:
#   - \newcommand* (starred) treated identically to unstarred
#   - xargs positional key [i=default] syntax not fully supported
_NEW_COM_PATTERN = (
    r'\\(?:(?:renew|new|provide)(?:command(?:twoopt)?|robustcmd)|DeclareRobustCommand)'
    r'(?<new_com_xargs>x)? ?\*? ?'
    + new_csname('new_com_csname') + r' ?'
    + num_args('new_com_num_args') + r' ?'
    + embed_braces('new_com_default1') + r' ?'
    + embed_braces('new_com_default2') + r' ?'
    + token('new_com_content')
)

# MATCHES: \NewDocumentCommand{\cmdname}{arg-spec}{body}  and variants:
#          \RenewDocumentCommand, \ProvideDocumentCommand, \DeclareDocumentCommand,
#          \NewExpandableDocumentCommand (and Renew/Provide/Declare variants).
#          xparse is now part of the LaTeX kernel. Docs: https://ctan.org/pkg/xparse
# CAPTURES:
#   new_doc_com_csname  → the command name
#   new_doc_com_args    → the xparse argument specification string
#   new_doc_com_content → the replacement body
# LIMITATIONS:
#   - Argument types supported: m, o, O{default}, s, t<token>
#   - \IfNoValueTF / \IfBooleanTF conditionals inside body NOT evaluated
_NEW_DOC_COM_PATTERN = (
    r'\\(?:New|Renew|Provide|Declare)(?:Expandable)?DocumentCommand ?'
    + new_csname('new_doc_com_csname') + r' ?'
    + token('new_doc_com_args') + r' ?'
    + token('new_doc_com_content')
)

# MATCHES: \newenvironment{name}[N][default]{begin}{end}  and \renewenvironment,
#          optionally with 'x' suffix (xargs). Docs: https://ctan.org/pkg/xargs
# CAPTURES:
#   new_env_csname    → environment name token
#   new_env_xargs     → 'x' if xargs variant, else None
#   new_env_num_args  → optional [N] argument count
#   new_env_default   → optional [default] for first argument
#   new_env_begin     → begin-code
#   new_env_end       → end-code
# LIMITATIONS:
#   - xargs positional key syntax not supported
_NEW_ENV_PATTERN = (
    r'\\(?:re)?newenvironment(?<new_env_xargs>x)? ?\*? ?'
    + token('new_env_csname') + r' ?'
    + num_args('new_env_num_args') + r' ?'
    + embed_braces('new_env_default') + r' ?'
    + token('new_env_begin') + r' ?'
    + token('new_env_end')
)

# MATCHES: \NewDocumentEnvironment{name}{arg-spec}{begin}{end}  and variants.
#          Docs: https://ctan.org/pkg/xparse
# CAPTURES:
#   new_doc_env_csname  → environment name
#   new_doc_env_args    → xparse argument specification string
#   new_doc_env_begin   → begin-code
#   new_doc_env_end     → end-code
# LIMITATIONS:
#   - Same xparse argument type limitations as _NEW_DOC_COM_PATTERN
_NEW_DOC_ENV_PATTERN = (
    r'\\(?:New|Renew|Provide|Declare)DocumentEnvironment ?'
    + token('new_doc_env_csname') + r' ?'
    + token('new_doc_env_args') + r' ?'
    + token('new_doc_env_begin') + r' ?'
    + token('new_doc_env_end')
)

# MATCHES: \NewEnviron{name}[N][default]{body}[\finalcode]  and \RenewEnviron.
#          The environ package captures the body as \BODY.
#          Docs: https://ctan.org/pkg/environ
# CAPTURES:
#   New_Env_csname    → environment name
#   New_Env_num_args  → optional [N] argument count
#   New_Env_default   → optional [default]
#   New_Env_content   → the macro body (references \BODY for env content)
#   New_Env_end       → optional [final-code] appended after body expansion
# LIMITATIONS:
#   - \BODY substitution not performed (body treated as opaque text)
_NEW_ENVIRON_PATTERN = (
    r'\\(?:Ren|N)ewEnviron ?'
    + token('New_Env_csname') + r' ?'
    + num_args('New_Env_num_args') + r' ?'
    + embed_braces('New_Env_default') + r' ?'
    + token('New_Env_content') + r' ?'
    + embed_braces('New_Env_end')
)

# MATCHES: \newenviron{name}[N][default]{begin-code}{body}  and \renewenviron.
#          The newenviron package (older alternative to environ).
#          Docs: https://ctan.org/pkg/newenviron
# CAPTURES:
#   New_Env_csname    → environment name  (shares group names with _NEW_ENVIRON_PATTERN)
#   New_Env_num_args  → optional [N]
#   New_Env_default   → optional [default]
#   New_Env_begin     → begin-code
#   New_Env_content   → body macro (references \envbody or \<name>body)
# LIMITATIONS:
#   - \envbody substitution not performed (same as _NEW_ENVIRON_PATTERN)
_NEW_ENVIRON_PKG_PATTERN = (
    r'\\(?:re)?newenviron ?'
    + token('New_Env_csname') + r' ?'
    + num_args('New_Env_num_args') + r' ?'
    + embed_braces('New_Env_default') + r' ?'
    + token('New_Env_begin') + r' ?'
    + token('New_Env_content')
)

# MATCHES: \DeclareMathOperator{\cmdname}{symbol}  and starred form.
#          (amsmath). Defines \cmdname as \operatorname{symbol}.
#          Docs: https://ctan.org/pkg/amsmath (amsldoc.pdf §3.4)
# CAPTURES:
#   dmo_csname  → the command name token
#   dmo_star    → '*' if starred form (limits above/below), else None
#   dmo_content → the operator symbol, e.g. {Op} or {lim\,sup}
# LIMITATIONS:
#   - Starred vs non-starred changes limit placement; demacro expands both.
_DMO_PATTERN = (
    r'\\DeclareMathOperator ?(?<dmo_star>\*)? ?'
    + new_csname('dmo_csname') + r' ?'
    + token('dmo_content')
)

# MATCHES: special TeX directives that affect macro visibility.
# CAPTURES (alternation groups):
#   mathpalette  → \mathpalette
#   makeatother  → \makeatother
#   makeatletter → \makeatletter
_WEIRD_STUFF_PATTERN = (
    r'(?<mathpalette>\\mathpalette)'
    r'|(?<makeatother>\\makeatother)'
    r'|(?<makeatletter>\\makeatletter)'
)

# _FIND_ALL_RE: compiled union of all macro-definition patterns.
# MATCHES: any macro-definition command in the preamble.
# CAPTURES: top-level groups 'def', 'edef', 'let', 'new_com', 'new_env',
#           'new_doc_com', 'new_doc_env', 'dmo', 'csname_def' identify which
#           branch matched.  All sub-captures from the matched branch available.
# NOTE: _NEW_ENVIRON_PATTERN and _NEW_ENVIRON_PKG_PATTERN are NOT included
#       here; they are handled separately via the new_env xargs flag.
# NOTE: elif chain order in build_dictionary() is semantically significant:
#       \edef must expand immediately using the current dict state.
_FIND_ALL_RE = re.compile(
    r'(?<def>%s)'
    r'|(?<edef>%s)'
    r'|(?<let>%s)'
    r'|(?<new_com>%s)'
    r'|(?<new_env>%s)'
    r'|(?<new_doc_com>%s)'
    r'|(?<new_doc_env>%s)'
    r'|(?<dmo>%s)'
    r'|(?<csname_def>%s)' % (
        _DEF_PATTERN, _EDEF_PATTERN, _LET_PATTERN, _NEW_COM_PATTERN,
        _NEW_ENV_PATTERN, _NEW_DOC_COM_PATTERN, _NEW_DOC_ENV_PATTERN,
        _DMO_PATTERN, _CSNAME_DEF_PATTERN,
    )
)

# _ARG_REF_RE: matches argument references in a macro body template.
# Matches #N or ##N (where ##N means a literal # followed by arg N).
# Used in content_replacement to substitute #N placeholders.
_ARG_REF_RE = re.compile(r'#(#*\d)')

# _ARG_REF_DOUBLE_RE: detects a doubled-hash prefix in an arg reference group.
# If _ARG_REF_RE captures "##N", the captured group starts with '#' → literal.
_ARG_REF_DOUBLE_RE = re.compile(r'^#')

# _XARGS_POSITIONAL_RE: matches xargs positional key prefix "N=" in [N=default].
# Used in build_dictionary to strip the position index from xargs defaults.
_XARGS_POSITIONAL_RE = re.compile(r'^\d+=')

## pgfkeys patterns (not yet fully supported — reserved for future use)
key = lambda s: (
    r' ?(?<%s>(?:\/(?!\.))?(?:[^=,\/]+?(?:\/(?!\.)))*)'
    r'(?<%s>[^=,\/]+?)(?<%s>\/.[^=,\/]+?)? ?'
    % (s + '_path', s + '_name', s + '_handler')
)
value = lambda s: r'(?<%s>(?:%s|[^,\{\}])*)' % (s, embed_brackets('brackted_' + s))
key_value = r'(?!\s)%s(?:=%s)?(?=,|\})' % (key('key'), value('value'))


# ============================================================================
# Section 10 — SemanTex structural patterns   (used by semantex.py)
# ============================================================================
# These patterns operate on raw multi-line LaTeX source (NOT on preprocessed
# flat strings). They are DOTALL-aware where noted and do NOT assume the §5/§6
# preprocessing invariant (no whitespace collapse, no \par substitution).

# _SEMANTEX_MACRO_RE: matches SemanTex annotation macros and structural delimiters.
# MATCHES: \label, \label*, \iref, \decl, \begin, \end — each followed by {
#          Skips whitespace between the command name and the opening brace.
# CAPTURES:
#   group 1 → the command name without backslash: "label", "label*",
#             "iref", "decl", "begin", or "end"
# LIMITATIONS:
#   [inferred] \label inside verbatim environments is matched; callers must
#              handle this via surrounding context (not filtered here).
#   [inferred] \label inside comments (already stripped by preprocessing) is
#              matched when operating on raw source; parse() receives raw source.
# USED BY:   semantex.parse()
_SEMANTEX_MACRO_RE = re.compile(r'\\(label\*?|iref|decl|begin|end)\s*(?=\{)')

# _SECTION_CMD_RE: matches LaTeX sectioning commands with their title argument.
# MATCHES: \chapter, \section, \subsection, \subsubsection, \paragraph,
#          \subparagraph — optionally starred — followed by {title}.
# CAPTURES:
#   group 1 → the command name without backslash, e.g. "section"
#   sarg    → the entire {title} argument including outer braces (balanced)
# LIMITATIONS:
#   [inferred] Does not match \part (unusual in math papers; add if needed).
#   [inferred] Short-title optional argument [\short] before {title} not captured.
#   [observed] Starred form (\section*) matched; star is not captured separately.
# USED BY:   semantex.parse()
_SECTION_CMD_RE = re.compile(
    r'\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)'
    r'\*?\s*'
    + embed_brackets('sarg'),
    re.DOTALL,
)

# _DISPLAY_MATH_RE: matches display math blocks \[…\] and $$…$$.
# MATCHES:
#   \[content\]   — LaTeX display math (does not nest)
#   $$content$$   — TeX display math (does not nest)
# CAPTURES:
#   dm_bracket → content inside \[…\] (may span multiple lines)
#   dm_dollar  → content inside $$…$$ (may span multiple lines)
# LIMITATIONS:
#   [inferred] Does not match \begin{equation}…\end{equation} or similar;
#              those are handled via \begin/\end by _SEMANTEX_MACRO_RE.
#   [inferred] Nested display math (invalid LaTeX) produces undefined behaviour.
#   [inferred] $$ inside a \label{} argument is not a display math delimiter.
#   [observed] Does not match \(…\) (inline math) — alternation ends at \] / $$.
# USED BY:   semantex.parse()
_DISPLAY_MATH_RE = re.compile(
    r'\\\[(?P<dm_bracket>.*?)\\\]'
    r'|(?<!\$)\$\$(?P<dm_dollar>.*?)\$\$(?!\$)',
    re.DOTALL,
)

# _AUTO_LABEL_ID_RE: matches texphage-generated (machine-authored) label ids.
# MATCHES: any string of the form  prefix:_N  where N is one or more digits.
# Examples: thm:_1, sec:_2, eq:_12, prf:thm:_1 (prefix may contain colons)
# CAPTURES: full match (no groups needed — used as a boolean test).
# LIMITATIONS:
#   [inferred] User-written ids that accidentally match this form would be
#              treated as machine-generated by BourbakIA's enrichment pass.
#              The underscore prefix makes this extremely unlikely in practice.
# USED BY:   BourbakIA enrichment pass (to identify labels to replace with
#            LLM-chosen ids). Also used by semantex.annotate() to skip
#            existing auto-generated labels.
_AUTO_LABEL_ID_RE = re.compile(r'^[^:]+:_\d+$')


# ============================================================================
# Section 11 — pgfkeys-lite key=value patterns   (used by semantex.py)
# ============================================================================
# Minimal key=value parser for \decl[type=X, scope={a,b}] option strings.
# Foundation for the full pgfkeys plan (docs/notes/pgfkeys_implementation_plan.md).
# These patterns operate on the already-extracted option string (no backslash
# or environment structure), so the preprocessing invariant does not apply.

# _PGFKEYS_BRACE_VAL_PATTERN: raw sub-pattern for a balanced {…} value.
# This is a building block (raw string), not a compiled RE.
# Named group 'pgfv' enables recursive brace matching.
# USED BY:   _PGFKEYS_PAIR_RE (below)
_PGFKEYS_BRACE_VAL_PATTERN = embed_brackets('pgfv')

# _PGFKEYS_PAIR_RE: matches one key=value pair from an option string.
# MATCHES: key=value  or  key={brace-enclosed value}
#          Optional whitespace around the = sign is consumed.
# CAPTURES:
#   pgfk   → the key string (no spaces, no = { } ,)
#   pgfval → the value: either a balanced {…} group (with outer braces)
#            or a bare sequence of non-comma, non-brace characters
# LIMITATIONS:
#   [inferred] Keys with / (pgfkeys path syntax) not supported in this lite version.
#   [inferred] Valueless keys (bare key without =) are not matched; callers
#              must handle them separately if needed.
# USED BY:   semantex._parse_decl_options()
_PGFKEYS_PAIR_RE = re.compile(
    r'(?P<pgfk>[^={},\s]+)\s*=\s*(?P<pgfval>%s|[^,{}]*)' % _PGFKEYS_BRACE_VAL_PATTERN
)

# _PGFKEYS_ITEM_SEP_RE: matches one top-level item in a comma-separated option string.
# An item is a maximal non-empty sequence of: non-comma/non-brace chars, or
# balanced {…} groups. Top-level commas (separators) are NOT matched.
# MATCHES: the full text of one key=value pair including any {…} values.
# CAPTURES:
#   pgfsep → balanced brace group (named for recursion only; use group(0) for item)
# USAGE:    regex.finditer(_PGFKEYS_ITEM_SEP_RE, opts_str) → individual pair strings.
# LIMITATIONS:
#   [inferred] Empty items (adjacent commas: "key=a,,key=b") produce no match
#              for the empty slot — this is correct behaviour.
#   [inferred] Leading/trailing whitespace in items is preserved; callers strip().
# USED BY:   semantex._parse_decl_options()
_PGFKEYS_ITEM_SEP_RE = re.compile(
    r'(?:[^,{}]|' + embed_brackets('pgfsep') + r')+'
)


# ============================================================================
# Section 7 — Preamble-building patterns   (used by pipeline.build_minimal_preamble)
# ============================================================================

# _DOCCLASS_RE: matches the \documentclass declaration.
_DOCCLASS_RE = re.compile(r'\\documentclass\s*(?:\[[^\]]*\])?\s*\{[^}]*\}')

# _FRONT_MATTER_RE: front-matter commands that must survive preamble stripping.
# amsart/amsbook put \title, \author, \address, \email, \keywords, \subjclass,
# \dedicatory in the preamble; without them \maketitle raises "No \title given."
# MATCHES: \title{…}, \author{…}, etc. with balanced-brace mandatory argument.
# CAPTURES: named group 'arg' = the argument (balanced braces, supports nesting).
_FRONT_MATTER_RE = re.compile(
    r'\\(?:title|author|date|address|email|keywords|subjclass|dedicatory|thanks)'
    r'(?:\[[^\]]*\])?'          # optional [short] argument
    r'\s*'
    r'(?P<arg>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?P&arg))*(?<!\\)\})',
    re.DOTALL,
)

# _NEWTHEOREM_RE: \newtheorem and related declarations that must survive.
# Docs: https://texdoc.org/pkg/amsthm
# MATCHES: \newtheorem{envname}{Print Name}[numbered-within] and variants.
# CAPTURES:
#   nt_env     → the environment name, e.g. "remark"
#   nt_counter → the optional shared counter name from [counter] before title
#   nt_title   → the print name (balanced braces)
# LIMITATIONS:
#   [observed] Does not handle \theoremstyle{} (separate command).
#   [observed] BUG-20: \newtheoremrm (tac.cls) covered via \w*.
#   [observed] BUG-22: \newtheoremstyle excluded via negative lookahead.
#   [observed] BUG-23: print-name may contain nested braces; balanced-brace used.
#   [observed] BUG-31: shared counter [counter] captured for \newcounter dependency.
_NEWTHEOREM_RE = re.compile(
    r'\\newtheorem(?!style)\w*\*?'
    r'\s*\{(?P<nt_env>[^}]*)\}'         # {environment-name} — captured for dedup
    r'\s*(?:\[(?P<nt_counter>[^\]]*)\])?'  # optional [shared-counter] before title (BUG-31)
    # {print-name} — balanced braces for nested \ref{…} etc. (BUG-23)
    r'\s*(?P<nt_title>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?P&nt_title))*(?<!\\)\})'
    r'\s*(?:\[[^\]]*\])?',              # optional [numbered-within] after title
    re.DOTALL,
)

# _NEWCOUNTER_RE: \newcounter{name} declarations in the preamble.
# BUG-31: when \newtheorem uses [counter] syntax, the \newcounter{counter}
# declaration must survive in the minimal preamble.
# Docs: https://texdoc.org/serve/texbytopic/0 (Ch.21 — \newcounter)
# MATCHES: \newcounter{name} with optional [within] arg.
# CAPTURES:
#   nc_name → the counter name, e.g. "other"
# LIMITATIONS:
#   [observed] Only captures \newcounter; \setcounter, \addtocounter etc. are
#              not needed for the dependency chain.
# USED BY: pipeline.py — build_minimal_preamble()
_NEWCOUNTER_RE = re.compile(
    r'\\newcounter'
    r'\s*\{(?P<nc_name>[^}]*)\}'        # {counter-name}
    r'(?:\s*\[[^\]]*\])?',             # optional [within]
    re.DOTALL,
)

# _THE_COUNTER_RE: \renewcommand{\thefoo}{...} counter-formatting declarations.
# BUG-31: when \newcounter{foo} is preserved, any \renewcommand{\thefoo}{...}
# that sets the counter's display format must also be preserved.
# MATCHES: \renewcommand{\thefoo}{balanced-brace body}
# CAPTURES:
#   tc_name → the counter name (without "the" prefix), e.g. "other"
#   tc_body → the replacement body (balanced braces)
# LIMITATIONS:
#   [observed] Only matches \renewcommand; \def\thefoo would need a separate branch.
# USED BY: pipeline.py — build_minimal_preamble()
_THE_COUNTER_RE = re.compile(
    r'\\renewcommand\s*\{\\the(?P<tc_name>[a-zA-Z@]+)\}'
    r'\s*(?P<tc_body>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?P&tc_body))*(?<!\\)\})',
    re.DOTALL,
)

# _VERSION_ENV_RE: \excludeversion / \includeversion / \excludecomment / \includecomment.
# These define LaTeX environments in the preamble; stripping them causes
# "Environment name undefined" in the body.
# Docs: https://ctan.org/pkg/version, https://ctan.org/pkg/comment
# LIMITATIONS:
#   [observed] \excludeversion optional arg [text] captured correctly.
#   [inferred] Nested braces in optional arg not supported (unlikely).
_VERSION_ENV_RE = re.compile(
    r'\\(?:exclude|include)(?:version|comment)'
    r'\s*(?:\[[^\]]*\])?'   # optional [replacement text]
    r'\s*\{[^}]*\}',
    re.DOTALL,
)

# _DEFINECOLOR_RE: xcolor color definition commands that must survive preamble stripping.
# Defines named colors; stripping them causes "Undefined color 'name'".
# Docs: https://ctan.org/pkg/xcolor (xcolor.pdf §2.1)
# MATCHES: \definecolor{name}{model}{spec}  \colorlet{name}{expr}  etc.
# LIMITATIONS:
#   [observed] \definecolor, \colorlet, \DefineNamedColor tested via playground.
#   [inferred] \providecolor, \preparecolor have same syntax; not separately tested.
_DEFINECOLOR_RE = re.compile(
    r'\\(?:definecolor|DefineNamedColor|colorlet|providecolor|preparecolor)'
    r'\s*(?:\[[^\]]*\])?'        # optional [type] argument
    r'(?:\s*\{[^}]*\}){2,4}',   # 2–4 brace-delimited arguments
    re.DOTALL,
)

# _DECLARE_NEW_FOOTNOTE_RE: \DeclareNewFootnote from the manyfoot package.
# Defines new footnote series (\footnoteX, \FootnoteX, etc.); stripping it
# causes "Undefined control sequence" for all \footnoteX calls in the body.
# Docs: https://ctan.org/pkg/manyfoot
# MATCHES: \DeclareNewFootnote[ctr-type]{suffix}[numbering-style]
# CAPTURES: no named groups — only the full match is needed for preservation.
# LIMITATIONS:
#   [observed] BUG-30: {suffix} and optional [arabic] tested via playground.
#   [inferred] Optional [ctr-type] before {suffix} (e.g. [para]) not separately tested.
# USED BY: pipeline.build_minimal_preamble
_DECLARE_NEW_FOOTNOTE_RE = re.compile(
    r'\\DeclareNewFootnote'
    r'\s*(?:\[[^\]]*\])?'   # optional [counter-type] (e.g. [para])
    r'\s*\{[^}]*\}'         # {suffix} — e.g. {A}
    r'(?:\s*\[[^\]]*\])?',  # optional [numbering-style] (e.g. [arabic])
    re.DOTALL,
)


# ============================================================================
# Section 8 — Attachment-finding patterns   (used by pipeline.find_attachments)
# ============================================================================

# _INCLUDEGRAPHICS_RE: \includegraphics[opts]{path}
# CAPTURES: group 1 = file reference (no extension for LaTeX-resolved images).
_INCLUDEGRAPHICS_RE = re.compile(
    r'\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}'
)

# _BIBLIOGRAPHY_RE: \bibliography{file1,file2,…} (BibTeX)
# CAPTURES: group 1 = comma-separated bib file names.
_BIBLIOGRAPHY_RE = re.compile(r'\\bibliography\s*\{([^}]+)\}')

# _ADDBIBRESOURCE_RE: \addbibresource{file.bib} (BibLaTeX)
# CAPTURES: group 1 = the bib file path.
_ADDBIBRESOURCE_RE = re.compile(r'\\addbibresource\s*\{([^}]+)\}')

# _BIB_EXT_RE: detects whether a bibliography filename already has .bib extension.
_BIB_EXT_RE = re.compile(r'\.bib$')

# _BIB_FILE_NAME_RE: matches individual bibliography filenames in a comma list.
# MATCHES: a run of non-whitespace, non-comma characters (any case, path chars).
# Used to split \bibliography{refs, other} without str.split(',').
_BIB_FILE_NAME_RE = re.compile(r'[^\s,]+')


# ============================================================================
# Section 9 — XY-to-tikzcd converter patterns   (used by xy_to_tikzcd.py)
# ============================================================================
# These patterns operate on raw multi-line source (DOTALL where noted).
# They do NOT assume the preprocessing invariant from Sections 5–6.

# _XY_NOT_SPECIAL_CHAR_PATTERN: non-structural XY character fragment.
# Used as a building block in xy_token().
# Excludes _, ^, |, @, $, & which are XY structural/math characters.
_XY_NOT_SPECIAL_CHAR_PATTERN = r'[^\\\{\}_\^\|@$&]'

# _XY_NUM_COEFF_PATTERN: decimal coefficient in [0, 1).
# MATCHES: 0.5, .25, 0.0, 0  (but not negative values)
# USED BY: _XY_POS_LABEL_PATTERN, _XY_POS_LABEL_PAREN_RE
_XY_NUM_COEFF_PATTERN = r'0?(?:\.\d+)?'

# _XY_NUMBER_PATTERN: any real number, optionally negative.
# MATCHES: 10, -2.5, .75, -10pt prefix (numeric part only)
# USED BY: _XY_DIMEN_PATTERN, _XY_DIMEN_PARSE_RE
_XY_NUMBER_PATTERN = r'-? ?(?:\d+)?(?:\.\d+)?'

# _XY_UNITS_PATTERN: TeX dimension units accepted by XY-pic.
# USED BY: _XY_DIMEN_PATTERN, _XY_DIMEN_PARSE_RE
_XY_UNITS_PATTERN = r'pt|pc|in|bp|cm|mm|dd|cc|sp|ex|em|px'

# _XY_DIMEN_PATTERN: a TeX dimension (number + unit), e.g. 10pt, -2.5cm.
# USED BY: _XY_CURVE_PATTERN, _XY_SHIFT_PATTERN, _XY_OPTIONS_RE
_XY_DIMEN_PATTERN = r'%s ?(?:%s)' % (_XY_NUMBER_PATTERN, _XY_UNITS_PATTERN)

# _XY_VARIANT_PATTERN: XY arrow variant modifier (^, _, 2, 3).
# ^/_ flip the arrow; 2/3 scale to double/triple stroke.
# USED BY: _XY_TIP_PATTERN, _XY_AR_PATTERN
_XY_VARIANT_PATTERN = r'\^|_|2|3'

# _XY_CONN_VARIANT_PATTERN: connector scaling variant (2 or 3 only).
# USED BY: _XY_CONN_PATTERN
_XY_CONN_VARIANT_PATTERN = r'2|3'

# _XY_TIP_DIR_PATTERN: alternation of all XY tip specifiers.
# Longer forms (<<, >>, \|\|) must appear before shorter ones (<, >, \|)
# to prevent premature match.
# MATCHES: <, >, \|, ', `, <<, >>, \|\|, \(, \), \+, \/
# (last four are unsupported — produce empty tikzcd output with log.warning)
# USED BY: _XY_TIP_PATTERN, _XY_TIP_DIR_RE
_XY_TIP_DIR_PATTERN = r"<<|>>|\|\||<|>|\||'|`|\(|\)|\+|\/"

# _XY_CONN_DIR_PATTERN: alternation of all XY connector styles.
# Longer forms (--, ==) before shorter ones (-, =) to prevent premature match.
# MATCHES: -, =, ., :, ~, --, ==, ~~
# USED BY: _XY_CONN_PATTERN, _XY_CONN_DIR_RE
_XY_CONN_DIR_PATTERN = r'--|==|-|=|\.|:|~|~~'

# xy_token(s): one XY structural token — control sequence, non-special char,
# or balanced {…} group named s.  Different from the §1 token() lambda:
# XY excludes _, ^, |, @, $, & from its non-special character set.
# USED BY: _XY_AR_PATTERN (uplabel/downlabel/midlabel capture groups)
xy_token = lambda s: r'(?:\\[a-zA-Z]+)|%s|%s' % (
    _XY_NOT_SPECIAL_CHAR_PATTERN, embed_brackets(s)
)

# _XY_TIP_DIR_RE: compiled form for searching within a captured tip string.
# MATCHES: any XY tip type specifier.
# USED BY: replace_ar() in xy_to_tikzcd.py (tip_dict lookup)
_XY_TIP_DIR_RE = re.compile(_XY_TIP_DIR_PATTERN)

# _XY_CONN_DIR_RE: compiled form for searching within a captured conn string.
# MATCHES: any XY connector style specifier.
# USED BY: replace_ar() in xy_to_tikzcd.py (conn_dict lookup)
_XY_CONN_DIR_RE = re.compile(_XY_CONN_DIR_PATTERN)

# _XY_DIMEN_PARSE_RE: extract the numeric part and unit from a dimension string.
# MATCHES: a TeX dimension like "10pt" or "-2.5cm".
# CAPTURES: group 1 = numeric part, group 2 = unit string.
# LIMITATIONS:
#   [inferred] Spaces between number and unit ("-2 .5cm") are matched loosely.
# USED BY: unit_to_em() in xy_to_tikzcd.py
_XY_DIMEN_PARSE_RE = re.compile(
    r'(%s)(%s)' % (_XY_NUMBER_PATTERN, _XY_UNITS_PATTERN)
)

# _XY_POS_LABEL_PAREN_RE: parenthesised position coefficient in a label spec.
# MATCHES: (0.5), (.25), (0)
# CAPTURES: group 1 = the coefficient string.
# USED BY: replace_ar() position branches in xy_to_tikzcd.py
_XY_POS_LABEL_PAREN_RE = re.compile(r'\((%s)\)' % _XY_NUM_COEFF_PATTERN)

# _XY_POS_NEAR_START_RE / _XY_POS_NEAR_END_RE: detect < / > in position spec.
# USED BY: replace_ar() near-start / near-end branches in xy_to_tikzcd.py
_XY_POS_NEAR_START_RE = re.compile(r'<')
_XY_POS_NEAR_END_RE   = re.compile(r'>')

# _XY_ENDPTS_RE: parse "start";"end" explicit endpoint notation in XY arrows.
# MATCHES: "nodename";"nodename" — the \ar"A";"B" form.
# CAPTURES: start → start node alias, end → end node alias.
# USED BY: replace_ar() endpts branch in xy_to_tikzcd.py
_XY_ENDPTS_RE = re.compile(r'"(?P<start>.+)";"(?P<end>.+)"')

# Intermediate fragments — not exported but used to build _XY_AR_PATTERN below.
_XY_TIP_PATTERN = (
    r'(?:%s)? ?(?:\{(?:%s| |)\}|%s)' % (
        _XY_VARIANT_PATTERN, _XY_TIP_DIR_PATTERN, _XY_TIP_DIR_PATTERN
    )
)
_XY_CONN_PATTERN = (
    r'(?:%s)? ?(?:\{(?:%s| |)\}|%s)' % (
        _XY_CONN_VARIANT_PATTERN, _XY_CONN_DIR_PATTERN, _XY_CONN_DIR_PATTERN
    )
)
_XY_CURVE_PATTERN  = r'(?:\^|_) ?(?:%s)?' % _XY_DIMEN_PATTERN
_XY_SHIFT_PATTERN  = r'(?:%s)?' % _XY_DIMEN_PATTERN
_XY_POS_LABEL_PATTERN = r'(?:[<>]+)|(?:\( ?%s ?\))' % _XY_NUM_COEFF_PATTERN

# _XY_AR_RE: compiled pattern matching a complete \ar command.
# MATCHES: \ar[@style][@curve][@shift][dir]^label_label|label
# CAPTURES (named groups):
#   dir        → direction string, e.g. "rr", "dl"
#   endpts     → explicit "A";"B" endpoint string
#   style      → full @{...} style block
#   variant    → ^/_/2/3 modifier inside @{...}
#   start      → start-tip specifier inside @{...}
#   conn       → connector style inside @{...}
#   end        → end-tip specifier inside @{...}
#   curve      → @/.../ curve spec
#   shift      → @<...> shift spec
#   uppos      → position modifier before ^ label
#   uplabel    → ^ label content (bracket0 for brace groups)
#   upalias    → ="name" alias for ^ label
#   downpos    → position modifier before _ label
#   downlabel  → _ label content (bracket1 for brace groups)
#   downalias  → ="name" alias for _ label
#   midpos     → position modifier before | label
#   midlabel   → | label content (bracket2 for brace groups)
#   midalias   → ="name" alias for | label
# LIMITATIONS:
#   [observed] \ar requires at least one direction or endpoint group.
#   [inferred] \ar with no arguments (phantom arrow) may not match.
#   [observed] Inline % comments inside \xymatrix{...} confuse the converter.
# USED BY: convert_xy_body() via replace_ar() in xy_to_tikzcd.py
_XY_AR_PATTERN = (
    r'\\ar ?'
    r'(?:'
    r'(?<style>@ ?(?<variant>%(v)s)? ?\{ ?(?<start>%(t)s)?? ?(?<conn>%(c)s)? ?(?<end>%(t)s)? ?\} ?)'
    r'|(?:@ ?\/ ?(?<curve>%(cu)s) ?\/ ?)'
    r'|(?:@ ?\< ?(?<shift>%(sh)s) ?\> ?)'
    r')*'
    r'(?:'
    r'(?:\[ ?(?<dir>[udlr]+) ?\] ?)'
    r'|(?<endpts>" ?.+ ?" ?; ?" ?.+ ?" ?)'
    r'|(?:\^ ?(?<uppos>%(p)s)? ?(?<uplabel>%(t0)s) ?(?:= ?" ?(?<upalias>.+) ?" ?)? ?)'
    r'|(?:_ ?(?<downpos>%(p)s)? ?(?<downlabel>%(t1)s) ?(?:= ?" ?(?<downalias>.+) ?" ?)? ?)'
    r'|(?:\| ?(?<midpos>%(p)s)? ?(?<midlabel>%(t2)s) ?(?:= ?" ?(?<midalias>.+) ?" ?)? ?)'
    r')+'
) % dict(
    v=_XY_VARIANT_PATTERN,
    t=_XY_TIP_PATTERN,
    c=_XY_CONN_PATTERN,
    cu=_XY_CURVE_PATTERN,
    sh=_XY_SHIFT_PATTERN,
    p=_XY_POS_LABEL_PATTERN,
    t0=xy_token('bracket0'),
    t1=xy_token('bracket1'),
    t2=xy_token('bracket2'),
)
_XY_AR_RE = re.compile(_XY_AR_PATTERN)

# _XY_ADD_OP_PATTERN: operator in xymatrix spacing options.
# USED BY: _XY_OPTIONS_RE
_XY_ADD_OP_PATTERN = r'\+|-|=|\+=|-='

# _XY_OPTIONS_RE: parse xymatrix option string (e.g. "R+2cm", "C-5pt", "!").
# MATCHES: axis-based spacing (R/C/both +/-/= dimen) or fixed overrides (!R, !C, !).
# CAPTURES:
#   axis   → 'R', 'C', or '' (both axes)
#   addop  → the operator (+, -, =, +=, -=)
#   dimen  → the dimension argument or 'R'/'C' alias
#   fixed  → !R, !C, or ! (unsupported — block returned unchanged)
# LIMITATIONS:
#   [inferred] += and -= operators are structurally captured but not converted.
#   [observed] ! (fixed) triggers log.warning + original block returned.
# USED BY: replace_xymatrix() in xy_to_tikzcd.py
_XY_OPTIONS_RE = re.compile(
    r'(?<axis>R|C|)(?<addop>%s)(?<dimen>%s|R|C)|(?<fixed>!R|!C|!)' % (
        _XY_ADD_OP_PATTERN, _XY_DIMEN_PATTERN
    )
)

# _XY_XYMATRIX_RE: matches a complete \xymatrix<options>{body} call.
# MATCHES: \xymatrix followed by optional non-brace options then a {…} body.
# CAPTURES:
#   options  → the option string between \xymatrix and the opening brace
#   bracket0 → the brace-balanced body, including outer braces
# LIMITATIONS:
#   [observed] \xymatrix* is not valid XY-pic; * is silently captured into options.
#   [observed] \xymatrix inside \vcenter cannot be converted; block unchanged.
#   [observed] Inline % comments inside body confuse the converter.
#   [observed] \xymatrix inside user macros is invisible at conversion time.
# USED BY: convert_xy_body() in xy_to_tikzcd.py
_XY_XYMATRIX_RE = re.compile(
    r'\\xymatrix ?(?<options>[^\{\}]*)' + embed_brackets('bracket0'),
    re.DOTALL,
)

# _XY_USEPACKAGE_XY_RE: matches \usepackage / \RequirePackage calls loading xy.
# MATCHES: \usepackage[all]{xy}, \usepackage{xy}, \RequirePackage[...]{xy}, etc.
# LIMITATIONS:
#   [inferred] \usepackage{xy,other} removes the whole call including other package.
# USED BY: convert_xy_preamble() in xy_to_tikzcd.py
_XY_USEPACKAGE_XY_RE = re.compile(
    r'\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{[^}]*\bxy\b[^}]*\}',
    re.DOTALL,
)

# _XY_USEPACKAGE_TIKZCD_RE: detects an existing \usepackage{tikz-cd} call.
# USED BY: convert_xy_preamble() to avoid double-inserting the tikz-cd package.
_XY_USEPACKAGE_TIKZCD_RE = re.compile(
    r'\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{[^}]*\btikz-cd\b[^}]*\}',
    re.DOTALL,
)
