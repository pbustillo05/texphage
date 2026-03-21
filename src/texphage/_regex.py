"""Shared PCRE regex primitives for the texphage package.

WARNING: These lambdas are interdependent. Do not modify without reading
the DANGER ZONE rules in CLAUDE_INSTRUCTIONS.md.

Requires the `regex` package (not `re`): patterns use PCRE recursive groups
(?&name) and duplicate named groups in alternations — neither supported by `re`.

All patterns assume preprocessing has produced a flat single-line string with
at most one ASCII space between tokens (see demacro.preprocessing).
"""
import regex as re

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

# not_tokenizer_char: any char that is not a TeX structural token (\, {, }).
not_tokenizer_char = r'[^\\\{\}]'

# token(s): matches exactly one TeX token:
#   - a single non-special character (e.g. 'a', '1', '+')
#   - a control sequence (e.g. \frac, \alpha)
#   - a balanced brace group {…}
# Used for: \def argument patterns and single-token arguments.
token = lambda s: r'(%s|(?:\\[a-zA-Z]+)|%s)' % (not_tokenizer_char, embed_brackets(s))

# num_args(s): matches optional [N] argument count.
# Used in: \newcommand{\cmd}[N]{body} — the [N] part.
num_args = lambda s: r'(?:\[ ?(?<%s>\d) ?\])?' % s

# find_com: matches a control sequence like \foobar. Captures name without \.
# Only handles letter-only names; single-symbol names (\|, \!) are not handled.
find_com = re.compile(r'\\([a-zA-Z]+)')

# find_env: matches an env name, optionally starred. Group 1: name; group 2: *.
find_env = re.compile(r'([a-zA-Z]+) ?(\*)?')

# xparse: matches one xparse argument specifier.
# xparse (now in LaTeX kernel) describes arguments as a string like "m o O{default} s t\X":
#   m  → mandatory {…} or single token
#   o  → optional []; \NoValue if absent
#   O  → optional [] with explicit default value
#   s  → optional star; expands to \BooleanTrue or \BooleanFalse
#   t  → optional specific token; expands to \BooleanTrue or \BooleanFalse
# Docs: https://ctan.org/pkg/xparse
xparse = (
    r'(?<m>\+?m)|(?<o>o)|(?<O>O%s)|(?<s>s)|(?<t>t[^\\\{\}])' % embed_brackets('default')
)
