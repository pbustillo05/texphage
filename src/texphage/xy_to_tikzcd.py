"""
Pure string-manipulation XY-to-tikzcd converter.
No I/O, no side effects, no compilation.
Operates on raw source (regex.DOTALL for multi-line matching).

MATCHES: \\xymatrix environments with \\ar arrows, basic tip/conn styles,
         curve/shift options, label positioning.
LIMITATIONS:
  [observed] \\xymatrix inside \\vcenter is not converted; tikzcd cannot be
             used inside \\vcenter.
  [observed] Crossing paths |!{[dl];[rr]}\\hole require global arrow analysis;
             not supported — block left unchanged.
  [inferred] Harpoon variants (^|, _|) produce incorrect output.
  [observed] Unsupported tip types (\\(, \\), \\+, \\/) leave arrow without tips.
  [observed] \\xymatrix inside user macros is invisible: macro content is not
             yet expanded at conversion time.
  [inferred] Comments inside \\xymatrix{...} (e.g. % this arrow) confuse the
             converter — block left unchanged with log.warning.
  [observed] \\xymatrix*{...} is not valid XY-pic syntax (playground-confirmed);
             the * is captured into options and silently ignored.
  [observed] The conversion changes pixel-level rendering (XY uses MetaPost,
             tikzcd uses PGF). SSIM < 1.0 is expected and documented.
USED BY: texphage-convert CLI (Phase 3); scripts/xy_to_tikz.py (thin wrapper)
"""
from __future__ import annotations

import logging

import regex as re

from texphage._regex import (
    _XY_AR_RE,
    _XY_CONN_DIR_RE,
    _XY_DIMEN_PARSE_RE,
    _XY_ENDPTS_RE,
    _XY_OPTIONS_RE,
    _XY_POS_LABEL_PAREN_RE,
    _XY_POS_NEAR_END_RE,
    _XY_POS_NEAR_START_RE,
    _XY_TIP_DIR_RE,
    _XY_USEPACKAGE_TIKZCD_RE,
    _XY_USEPACKAGE_XY_RE,
    _XY_XYMATRIX_RE,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lookup tables (data, not patterns — live here, not in _regex.py)
# ---------------------------------------------------------------------------

# tip_dict[tip_specifier][nfold_index] → tikzcd tip name.
# Index: 0=start(nfold>=1), 1=start(nfold>=2), 2=end(nfold=1), 3=end(nfold>=2).
tip_dict: dict[str, list[str]] = {
    '<':  ['tail reversed', 'ntail reversed', 'head reversed', 'nhead reversed'],
    '>':  ['tail', 'ntail', '', 'nhead'],
    '|':  ['maps to', 'maps to', 'maps from', 'maps from'],
    "'":  ['hook', '', 'hook head', ''],
    '`':  ["hook'", '', "hook' head", ''],
    '<<': [
        'two tails reversed', 'two ntails reversed',
        'two heads reversed', 'two nheads reversed',
    ],
    '>>': ['two tails', 'two ntails', 'two heads', 'two nheads'],
    '||': ['two maps to', 'two maps to', 'two maps from', 'two maps from'],
    '(':  ['', '', '', ''],
    ')':  ['', '', '', ''],
    '+':  ['', '', '', ''],
    '/':  ['', '', '', ''],
}

# conn_dict[conn_specifier] → tikzcd connector option string.
conn_dict: dict[str, str] = {
    '-':  '',
    '=':  '',
    '.':  'dotted',
    ':':  'dotted',
    '~':  'squiggly',
    '--': 'dashed',
    '==': 'dashed',
    '~~': '',
}

# dimen_dict[unit] → em conversion factor (default: cm at 12pt font).
dimen_dict: dict[str, float] = {
    'em': 1.0,
    'pt': 0.1,
    'mm': 0.28,
    'cm': 2.8,
    'ex': 0.43,
    'bp': 0.1,
    'dd': 0.1,
    'pc': 1.2,
    'in': 7.2,
    'sp': 1.5e-6,
    'cc': 1.2,
    'px': 0.1,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unit_to_em(dimension: str) -> float:
    """Convert a TeX dimension string (e.g. '10pt') to em units."""
    unit = _XY_DIMEN_PARSE_RE.search(dimension)
    assert unit is not None, f'unit_to_em: no dimension found in {dimension!r}'
    return float(unit.group(1).replace(' ', '')) * dimen_dict[unit.group(2)]


def _resolve_position(pos: str | None, argument: list[str]) -> None:
    """Append a tikzcd position option to *argument* based on *pos* string."""
    if pos is None:
        return
    m = _XY_POS_LABEL_PAREN_RE.search(pos)
    if m:
        argument.append('pos=' + m.group(0))
    elif _XY_POS_NEAR_START_RE.search(pos):
        argument.append('near start')
    elif _XY_POS_NEAR_END_RE.search(pos):
        argument.append('near end')


# ---------------------------------------------------------------------------
# Arrow replacement
# ---------------------------------------------------------------------------

def replace_ar(match: re.Match) -> str:  # type: ignore[type-arg]
    """Convert one \\ar match to a tikzcd \\arrow[...] command."""
    arrow: list[str] = []

    # End points
    if match.group('dir'):
        arrow.append(match.group('dir'))
    elif match.group('endpts'):
        ep = _XY_ENDPTS_RE.search(match.group('endpts'))
        if ep:
            arrow.append('from=' + ep.group('start'))
            arrow.append('to=' + ep.group('end'))

    # Labels
    if match.group('uplabel'):
        label = '"{' + match.group('uplabel') + '}"'
        argument: list[str] = []
        _resolve_position(match.group('uppos'), argument)
        if match.group('upalias'):
            argument.append('name=' + match.group('upalias'))
        if argument:
            label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)

    if match.group('downlabel'):
        label = '"{' + match.group('downlabel') + '}"\''
        argument = []
        _resolve_position(match.group('downpos'), argument)
        if match.group('downalias'):
            argument.append('name=' + match.group('downalias'))
        if argument:
            label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)

    if match.group('midlabel'):
        label = '"{' + match.group('midlabel') + '}"'
        argument = ['description', 'inner sep=0.05pt']
        _resolve_position(match.group('midpos'), argument)
        if match.group('midalias'):
            argument.append('name=' + match.group('midalias'))
        label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)

    # Bend / curve
    if match.group('curve'):
        cv = match.group('curve')
        if cv == '^':
            arrow.append('bend left')
        elif cv == '_':
            arrow.append('bend right')
        elif cv[0] == '_':
            arrow.append('curve={height=' + cv[1:] + '}')
        elif cv[:2] == '^-':
            arrow.append('curve={height=' + cv[2:] + '}')
        else:
            arrow.append('curve={height=-' + cv[1:] + '}')

    # Shift
    if match.group('shift'):
        arrow.append('shift left=' + match.group('shift'))

    # Arrow style (@{...} block)
    if match.group('style'):
        start_s = match.group('start') or ''
        conn_s  = match.group('conn') or ''
        end_s   = match.group('end') or ''
        start_triv = not start_s or '{}' in start_s or '{ }' in start_s
        conn_triv  = not conn_s  or '{}' in conn_s  or '{ }' in conn_s
        end_triv   = not end_s   or '{}' in end_s   or '{ }' in end_s

        conn_str    = match.group('conn')    or ''
        variant_str = match.group('variant') or ''
        if '3' in conn_str or '3' in variant_str:
            nfold = 3
        elif '2' in conn_str or '=' in conn_str or '2' in variant_str:
            nfold = 2
        elif start_triv and conn_triv and end_triv:
            nfold = 0
        else:
            nfold = 1

        if not start_triv:
            m_tip = _XY_TIP_DIR_RE.search(match.group('start'))
            if m_tip:
                arrow.append(tip_dict[m_tip[0]][min(nfold, 2) - 1])
        if not conn_triv:
            m_conn = _XY_CONN_DIR_RE.search(match.group('conn'))
            if m_conn:
                arrow.append(conn_dict[m_conn[0]])
        if not end_triv:
            m_tip = _XY_TIP_DIR_RE.search(match.group('end'))
            if m_tip:
                arrow.append(tip_dict[m_tip[0]][1 + min(nfold, 2)])
        if nfold == 0:
            arrow.append('phantom')
        elif nfold > 1:
            arrow.append('scaling nfold=' + str(nfold))

    # Strip empty strings from tip lookups on unsupported types
    arrow = [a for a in arrow if a != '']

    return r'\arrow[' + ' , '.join(arrow) + r']'


# ---------------------------------------------------------------------------
# xymatrix replacement
# ---------------------------------------------------------------------------

def replace_xymatrix(match: re.Match) -> str:  # type: ignore[type-arg]
    """Convert one \\xymatrix match to a tikzcd environment."""
    options = ['nodes in empty cells']
    # XY default row/col sep is 2pc ≈ 1.8em; tikzcd default is also 1.8em.
    for settings in _XY_OPTIONS_RE.finditer(match.group('options')):
        if settings.group('addop'):
            addop = settings.group('addop')
            axis  = settings.group('axis')
            dimen_val = unit_to_em(settings.group('dimen'))
            if addop == '+':
                base = 1.8 + dimen_val
            elif addop == '-':
                base = 1.8 - dimen_val
            elif addop == '=':
                base = dimen_val
            else:
                log.warning(
                    'xy_to_tikzcd: unsupported addop %r in \\xymatrix options; '
                    'leaving block unchanged', addop,
                )
                return str(match.group(0))
            sep_val = f'{base}em'
            if axis in ('R', ''):
                options.append('row sep=' + sep_val)
            if axis in ('C', ''):
                options.append('column sep=' + sep_val)
        else:
            log.warning(
                'xy_to_tikzcd: unsupported fixed option %r in \\xymatrix options; '
                'leaving block unchanged', settings.group('fixed'),
            )
            return str(match.group(0))

    body = str(match.group('bracket0'))[1:-1]  # strip outer braces
    converted_body = str(_XY_AR_RE.sub(replace_ar, body))
    return r'\begin{tikzcd}[' + ' , '.join(options) + ']' + converted_body + r'\end{tikzcd}'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_xy_body(tex: str) -> str:
    """Replace all \\xymatrix environments with tikzcd equivalents.

    Operates on raw source text (regex.DOTALL for multi-line matching).
    Unsupported \\xymatrix blocks are left unchanged with log.warning.
    """
    return str(_XY_XYMATRIX_RE.sub(replace_xymatrix, tex))


def convert_xy_preamble(preamble: str) -> str:
    """Remove \\usepackage{xy} variants; add \\usepackage{tikz-cd} if absent."""
    result = str(_XY_USEPACKAGE_XY_RE.sub('', preamble))
    if not _XY_USEPACKAGE_TIKZCD_RE.search(result):
        result = result + '\n\\usepackage{tikz-cd}'
    return result
