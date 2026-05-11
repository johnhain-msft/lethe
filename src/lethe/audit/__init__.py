"""Lethe audit/lint surface.

P1 ships :mod:`.integrity` — the ``lethe-audit lint --integrity`` command
plus an empty :class:`LintRegistry` that P2/P5/P8 register concrete lints
against (gap-08 §3.5: startup integrity check).
"""

from lethe.audit.integrity import LintRegistry, LintResult, lint_integrity, main

__all__ = ["LintRegistry", "LintResult", "lint_integrity", "main"]
