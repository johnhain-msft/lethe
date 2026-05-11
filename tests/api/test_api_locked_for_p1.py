"""api lock: importing lethe.api raises NotImplementedError at P1.

Per docs/IMPLEMENTATION.md §2.1 exit gate. Verifies both:
1. ``import lethe.api`` raises (the gate).
2. ``import lethe`` does NOT pull in lethe.api (so package metadata
   consumers don't trip the gate accidentally).
"""

from __future__ import annotations

import importlib
import sys

import pytest


def test_lethe_api_import_raises() -> None:
    # Drop any cached failed-import sentinel to force re-evaluation.
    sys.modules.pop("lethe.api", None)
    with pytest.raises(NotImplementedError, match="P2"):
        importlib.import_module("lethe.api")


def test_top_level_lethe_does_not_import_api() -> None:
    # Snapshot current lethe.* modules; we restore them on exit so we don't
    # leave subsequent tests holding stale module references (the test file's
    # top-level imports of lethe.audit.* are cached and would otherwise point
    # to a different module instance than sys.modules['lethe.audit.integrity']
    # after this test finishes).
    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "lethe" or name.startswith("lethe.")
    }
    try:
        for mod in list(sys.modules):
            if mod == "lethe" or mod.startswith("lethe."):
                del sys.modules[mod]
        importlib.import_module("lethe")
        assert "lethe.api" not in sys.modules, (
            "Top-level `import lethe` must not pull in lethe.api; the api lock "
            "would otherwise fire on every consumer (see plan.md §B5)."
        )
    finally:
        for mod in list(sys.modules):
            if mod == "lethe" or mod.startswith("lethe."):
                del sys.modules[mod]
        sys.modules.update(saved)
