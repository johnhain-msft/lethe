"""Lethe — bi-temporal memory substrate (v1).

This package marker is intentionally minimal. In particular it does NOT
import :mod:`lethe.api`, which is locked at P1 and raises
``NotImplementedError`` on import (per ``docs/IMPLEMENTATION.md`` §2.1
exit gates).
"""

from __future__ import annotations

__version__ = "0.0.1"
