"""Tests for the XY-to-tikzcd converter.

Phase 0 tests (TestImport … TestXymatrixStar): bug fixes in scripts/xy_to_tikz.
Phase 2 tests (TestModuleAPI … TestLimitations): convert_xy_body/preamble API.

Bug reference (plan Phase 0):
  #1  import re → import regex as re  (module raises re.error on import without fix)
  #2  module-level print(ar)           (stdout pollution on every import)
  #3  match.grouo(...)  ×5            (AttributeError in label position branches)
  #4  print('ERROR:...') + silent     (stdout pollution + silent wrong output)
      return on unknown XY operator
  #5  [:1] == '^-' dead branch        (off-by-one: should be [:2])
"""
from __future__ import annotations

import importlib
import sys


# ---------------------------------------------------------------------------
# Bug #1 + #2: module can be imported; import does not print to stdout
# ---------------------------------------------------------------------------

class TestImport:
    def test_module_imports_without_error(self):
        """Bug #1: with stdlib re, re.compile(ar) raises re.error at import time.
        After the fix (import regex as re), import must succeed silently."""
        # If the module is already cached, force a reload to re-run module-level code.
        if 'scripts.xy_to_tikz' in sys.modules:
            importlib.reload(sys.modules['scripts.xy_to_tikz'])
        else:
            import scripts.xy_to_tikz  # noqa: F401

    def test_import_does_not_print(self, capsys):
        """Bug #2: module-level print(ar) dumps the arrow regex to stdout."""
        if 'scripts.xy_to_tikz' in sys.modules:
            importlib.reload(sys.modules['scripts.xy_to_tikz'])
        else:
            import scripts.xy_to_tikz  # noqa: F401
        captured = capsys.readouterr()
        assert captured.out == '', (
            f"Import produced stdout output (should be empty):\n{captured.out[:200]}"
        )


# ---------------------------------------------------------------------------
# Core conversion smoke tests
# ---------------------------------------------------------------------------

class TestSimpleConversions:
    def setup_method(self):
        from scripts.xy_to_tikz import xy_to_tikzcd
        self.convert = xy_to_tikzcd

    def test_simple_arrow(self):
        """A→B with label should produce a tikzcd environment."""
        src = r'\xymatrix{ A \ar[r]^{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result
        assert r'\end{tikzcd}' in result
        assert 'A' in result
        assert 'B' in result

    def test_nested_braces_not_truncated(self):
        """Bug #1 regression: (?&bracket0) requires regex module; nested braces
        must be matched fully."""
        src = r'\xymatrix{ \mathrm{Hom}(A,B) \ar[r] & C }'
        result = self.convert(src)
        assert r'\mathrm{Hom}(A,B)' in result

    def test_commutative_square(self):
        """Multi-row matrix with explicit \\\\ row separator."""
        src = (
            r'\xymatrix{'
            r'  A \ar[r]^f \ar[d]_g & B \ar[d]^{h} \\'
            r'  C \ar[r]_k & D'
            r'}'
        )
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result
        # All node labels preserved
        for label in ('A', 'B', 'C', 'D'):
            assert label in result

    def test_passthrough_when_no_xymatrix(self):
        """Source without \\xymatrix is returned unchanged."""
        src = r'\begin{tikzcd} A \arrow[r] & B \end{tikzcd}'
        assert self.convert(src) == src


# ---------------------------------------------------------------------------
# Bug #3: match.grouo() typos — label position branches
# ---------------------------------------------------------------------------

class TestLabelPositionBranches:
    """Bug #3: five occurrences of match.grouo() raise AttributeError.
    These are all in the uppos/downpos/midpos branches of replace_ar().
    After the fix, they must not raise and must produce valid output."""

    def setup_method(self):
        from scripts.xy_to_tikz import xy_to_tikzcd
        self.convert = xy_to_tikzcd

    def test_uplabel_with_position_near_start(self):
        """uppos '<' branch — match.grouo('uppos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]^<{f} & B }'
        # Must not raise AttributeError
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result

    def test_uplabel_with_position_near_end(self):
        """uppos '>' branch — match.grouo('uppos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]^>{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result

    def test_downlabel_with_position_near_start(self):
        """downpos '<' branch — match.grouo('downpos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]_<{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result

    def test_downlabel_with_position_near_end(self):
        """downpos '>' branch — match.grouo('downpos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]_>{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result

    def test_midlabel_with_position_near_start(self):
        """midpos '<' branch — match.grouo('midpos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]|<{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result

    def test_midlabel_with_position_near_end(self):
        """midpos '>' branch — match.grouo('midpos') raised AttributeError."""
        src = r'\xymatrix{ A \ar[r]|>{f} & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result


# ---------------------------------------------------------------------------
# Bug #4: print('ERROR:...') + silent return on unknown XY operator
# ---------------------------------------------------------------------------

class TestUnknownOperator:
    """Bug #4: on unknown options operator the function prints to stdout and
    returns a partial conversion (silently wrong). After the fix it must
    log a warning and return the original \\xymatrix block unchanged."""

    def setup_method(self):
        from scripts.xy_to_tikz import xy_to_tikzcd
        self.convert = xy_to_tikzcd

    def test_unknown_operator_does_not_print(self, capsys):
        """Bug #4: 'ERROR:...' should not go to stdout."""
        # Use an unsupported addop character to trigger the else branch.
        # The current code triggers it when settings.group('addop') is not
        # in {'+', '-', '='}. We can trigger via the 'fixed' branch (no addop).
        # Actually, the 'fixed' group (!R, !C, !) triggers the else on 'addop'
        # being None — which hits the second else branch at line 263.
        src = r'\xymatrix!R{ A \ar[r] & B }'
        self.convert(src)
        captured = capsys.readouterr()
        assert 'ERROR' not in captured.out, (
            f"Unexpected stdout: {captured.out[:200]}"
        )

    def test_unknown_operator_returns_original_block(self):
        """Bug #4: unknown operator → original \\xymatrix block returned unchanged."""
        src = r'\xymatrix!R{ A \ar[r] & B }'
        result = self.convert(src)
        # After fix: original block preserved (conversion not applied)
        assert r'\xymatrix' in result


# ---------------------------------------------------------------------------
# Bug #5: [:1] == '^-' dead branch in curve handling
# ---------------------------------------------------------------------------

class TestCurveHandling:
    """Bug #5: match.group('curve')[:1] == '^-' is dead code ([:1] gives 1
    char; '^-' needs 2). After fix ([:2]), negative-height ^ curves map to
    curve={height=...} correctly."""

    def setup_method(self):
        from scripts.xy_to_tikz import xy_to_tikzcd
        self.convert = xy_to_tikzcd

    def test_positive_bend_left(self):
        r"""Arrow with @/^/ (bend up) should produce 'bend left'."""
        src = r'\xymatrix{ A \ar@/^/[r] & B }'
        result = self.convert(src)
        assert 'bend left' in result

    def test_negative_bend_right(self):
        r"""Arrow with @/_/ (bend down) should produce 'bend right'."""
        src = r'\xymatrix{ A \ar@/_/[r] & B }'
        result = self.convert(src)
        assert 'bend right' in result

    def test_negative_height_curve(self):
        r"""Arrow with @/^-10pt/ — the '^-' prefix triggers Bug #5.
        After fix [:2], match.group('curve')[:2] == '^-' is True and the
        branch produces curve={height=10pt} (positive, because negative
        means going the other direction in tikzcd)."""
        src = r'\xymatrix{ A \ar@/^-10pt/[r] & B }'
        result = self.convert(src)
        assert r'\begin{tikzcd}' in result
        # After fix: height should be positive (the '^-' branch strips the '-')
        assert 'height=10pt' in result


# ---------------------------------------------------------------------------
# \xymatrix* — observed: not valid XY-pic syntax
# ---------------------------------------------------------------------------

class TestXymatrixStar:
    r"""[observed] \xymatrix*{...} is not valid XY-pic syntax. Any paper using
    it would fail to compile. The converter must not crash and should either
    pass the block through or document the limitation."""

    def setup_method(self):
        from scripts.xy_to_tikz import xy_to_tikzcd
        self.convert = xy_to_tikzcd

    def test_starred_form_does_not_crash(self):
        """The * is captured into options by find_xymatrix. The converter
        must not raise an exception regardless."""
        src = r'\xymatrix*{ A \ar[r] & B }'
        # Must not raise
        result = self.convert(src)
        assert isinstance(result, str)


# ===========================================================================
# Phase 2: convert_xy_body() and convert_xy_preamble() module API
# ===========================================================================


class TestModuleAPI:
    """convert_xy_body() and convert_xy_preamble() from texphage.xy_to_tikzcd."""

    def setup_method(self):
        from texphage.xy_to_tikzcd import convert_xy_body, convert_xy_preamble
        self.body = convert_xy_body
        self.preamble = convert_xy_preamble

    # --- convert_xy_body ---

    def test_body_simple_arrow(self):
        """convert_xy_body produces a tikzcd environment from a simple \\ar."""
        src = r'\xymatrix{ A \ar[r]^{f} & B }'
        result = self.body(src)
        assert r'\begin{tikzcd}' in result
        assert r'\end{tikzcd}' in result
        assert r'\xymatrix' not in result

    def test_body_commutative_square(self):
        """Multi-row matrix survives convert_xy_body with all node labels."""
        src = (
            r'\xymatrix{'
            r'  A \ar[r]^f \ar[d]_g & B \ar[d]^{h} \\'
            r'  C \ar[r]_k & D'
            r'}'
        )
        result = self.body(src)
        assert r'\begin{tikzcd}' in result
        for label in ('A', 'B', 'C', 'D'):
            assert label in result

    def test_body_passthrough_no_xymatrix(self):
        """Source without \\xymatrix is returned unchanged by convert_xy_body."""
        src = r'\begin{tikzcd} A \arrow[r] & B \end{tikzcd}'
        assert self.body(src) == src

    def test_body_multiline_raw_source(self):
        """convert_xy_body handles real multi-line source (DOTALL)."""
        src = (
            r'\xymatrix{' + '\n'
            r'  A \ar[r]^f & B \\' + '\n'
            r'  C \ar[r]_k & D' + '\n'
            r'}'
        )
        result = self.body(src)
        assert r'\begin{tikzcd}' in result
        assert r'\end{tikzcd}' in result

    def test_body_multiple_xymatrix_blocks(self):
        """All \\xymatrix blocks in the source are converted."""
        src = (
            r'First: \xymatrix{ A \ar[r] & B } '
            r'and second: \xymatrix{ C \ar[r] & D }'
        )
        result = self.body(src)
        assert result.count(r'\begin{tikzcd}') == 2
        assert r'\xymatrix' not in result

    def test_body_nested_braces(self):
        """Nested braces in node labels are preserved by convert_xy_body."""
        src = r'\xymatrix{ \mathrm{Hom}(A,B) \ar[r] & C }'
        result = self.body(src)
        assert r'\mathrm{Hom}(A,B)' in result

    # --- convert_xy_preamble ---

    def test_preamble_removes_usepackage_xy(self):
        r"""convert_xy_preamble removes \usepackage{xy}."""
        preamble = r'\usepackage{xy}'
        result = self.preamble(preamble)
        assert r'\usepackage{xy}' not in result

    def test_preamble_removes_usepackage_xy_with_options(self):
        r"""convert_xy_preamble removes \usepackage[all]{xy}."""
        preamble = r'\usepackage[all]{xy}'
        result = self.preamble(preamble)
        assert r'\usepackage[all]{xy}' not in result

    def test_preamble_adds_tikzcd(self):
        r"""convert_xy_preamble adds \usepackage{tikz-cd} when absent."""
        preamble = r'\usepackage[all]{xy}'
        result = self.preamble(preamble)
        assert r'\usepackage{tikz-cd}' in result

    def test_preamble_no_double_tikzcd(self):
        r"""convert_xy_preamble does not add \usepackage{tikz-cd} if already present."""
        preamble = r'\usepackage[all]{xy}' + '\n' + r'\usepackage{tikz-cd}'
        result = self.preamble(preamble)
        assert result.count(r'\usepackage{tikz-cd}') == 1

    def test_preamble_preserves_other_packages(self):
        r"""convert_xy_preamble leaves unrelated \usepackage calls intact."""
        preamble = (
            r'\usepackage{amsmath}' + '\n'
            r'\usepackage[all]{xy}' + '\n'
            r'\usepackage{hyperref}'
        )
        result = self.preamble(preamble)
        assert r'\usepackage{amsmath}' in result
        assert r'\usepackage{hyperref}' in result

    # --- wrapper compatibility ---

    def test_script_wrapper_delegates_to_module(self):
        """scripts/xy_to_tikz.xy_to_tikzcd is an alias for convert_xy_body."""
        from scripts.xy_to_tikz import xy_to_tikzcd
        src = r'\xymatrix{ A \ar[r] & B }'
        assert xy_to_tikzcd(src) == self.body(src)


class TestLimitations:
    """Boundary tests: unsupported constructs must be left unchanged."""

    def setup_method(self):
        from texphage.xy_to_tikzcd import convert_xy_body
        self.body = convert_xy_body

    def test_fixed_option_block_unchanged(self):
        r"""[observed] !R (fixed option) → \\xymatrix block returned unchanged."""
        src = r'\xymatrix!R{ A \ar[r] & B }'
        result = self.body(src)
        assert r'\xymatrix' in result
        assert r'\begin{tikzcd}' not in result

    def test_fixed_option_logs_warning(self, caplog):
        r"""[observed] !R triggers log.warning, not an exception."""
        import logging
        src = r'\xymatrix!R{ A \ar[r] & B }'
        with caplog.at_level(logging.WARNING, logger='texphage.xy_to_tikzcd'):
            self.body(src)
        assert caplog.records, 'Expected a warning to be logged'

    def test_unsupported_tip_produces_empty_tip(self):
        r"""[observed] Unsupported tip types (\(, \), \+, \/) produce no tikzcd tip."""
        # \ar@{\\(->}[r] — open-bracket start tip is unsupported
        src = r'\xymatrix{ A \ar@{\(->}[r] & B }'
        result = self.body(src)
        # Must not crash; arrow should still be present
        assert isinstance(result, str)
        assert r'\begin{tikzcd}' in result


# ===========================================================================
# Phase 3: texphage-convert CLI  (main_convert)
# ===========================================================================


class TestCLI:
    """Tests for texphage-convert xy  (cli.main_convert)."""

    FIXTURE = 'tests/fixtures/xymatrix_simple/main.tex'

    def _invoke(self, argv: list[str], capsys=None):
        """Run main_convert with patched sys.argv; return (stdout, stderr, exit_code)."""
        import sys
        from texphage.cli import main_convert
        sys.argv = ['texphage-convert'] + argv
        try:
            main_convert()
            code = 0
        except SystemExit as exc:
            code = int(exc.code) if exc.code is not None else 0
        out, err = capsys.readouterr() if capsys else ('', '')
        return out, err, code

    def test_xy_to_stdout(self, capsys):
        """Basic invocation: xy fixture file → tikzcd on stdout, no \\xymatrix."""
        out, _, code = self._invoke(['xy', self.FIXTURE], capsys)
        assert code == 0, f'Expected exit 0, got {code}'
        assert r'\begin{tikzcd}' in out
        assert r'\end{tikzcd}' in out
        assert r'\xymatrix' not in out

    def test_xy_preamble_converted(self, capsys):
        r"""usepackage{xy} is removed; usepackage{tikz-cd} is present in output."""
        out, _, code = self._invoke(['xy', self.FIXTURE], capsys)
        assert code == 0
        assert r'\usepackage{tikz-cd}' in out
        assert r'\usepackage[all]{xy}' not in out

    def test_xy_out_flag(self, tmp_path):
        """Output file written when -o is given."""
        import sys
        from texphage.cli import main_convert
        out_file = str(tmp_path / 'out.tex')
        sys.argv = ['texphage-convert', 'xy', self.FIXTURE, '-o', out_file]
        try:
            main_convert()
        except SystemExit:
            pass
        content = (tmp_path / 'out.tex').read_text(encoding='utf-8')
        assert r'\begin{tikzcd}' in content
        assert r'\xymatrix' not in content

    def test_strict_passes_when_all_converted(self, capsys):
        """--strict succeeds (exit 0) when every \\xymatrix block converts."""
        _, _, code = self._invoke(['xy', self.FIXTURE, '--strict'], capsys)
        assert code == 0

    def test_strict_fails_on_unconvertible_block(self, tmp_path, capsys):
        """--strict exits non-zero when a block cannot be converted."""
        # !R is an unsupported fixed option → replace_xymatrix returns original
        bad_tex = (
            r'\documentclass{article}' + '\n'
            r'\usepackage[all]{xy}' + '\n'
            r'\begin{document}' + '\n'
            r'\xymatrix!R{ A \ar[r] & B }' + '\n'
            r'\end{document}' + '\n'
        )
        bad_file = tmp_path / 'bad.tex'
        bad_file.write_text(bad_tex, encoding='utf-8')
        _, _, code = self._invoke(['xy', str(bad_file), '--strict'], capsys)
        assert code != 0

    def test_missing_file_exits_nonzero(self, capsys):
        """Non-existent input file → non-zero exit."""
        _, _, code = self._invoke(['xy', 'does_not_exist.tex'], capsys)
        assert code != 0
