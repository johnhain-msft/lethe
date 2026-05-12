"""api package import behavior.

P1 had a hard lock (``import lethe.api`` raised ``NotImplementedError``).
P2 lifts that lock when commit 4 lands the ``remember`` verb. Two
remaining invariants:

1. ``import lethe.api`` succeeds and exposes :func:`remember`.
2. ``import lethe`` does NOT eagerly pull in ``lethe.api`` — the api
   surface imports heavyweight deps (graphiti-core) and metadata
   consumers should not have to pay for them.
"""

from __future__ import annotations

import importlib
import sys


def test_lethe_api_import_succeeds_and_exposes_remember() -> None:
    sys.modules.pop("lethe.api", None)
    api = importlib.import_module("lethe.api")
    assert hasattr(api, "remember")
    assert callable(api.remember)


def test_top_level_lethe_does_not_import_api() -> None:
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
            "Top-level `import lethe` must not pull in lethe.api; the api "
            "surface drags graphiti-core eagerly (see plan.md §B5)."
        )
    finally:
        for mod in list(sys.modules):
            if mod == "lethe" or mod.startswith("lethe."):
                del sys.modules[mod]
        sys.modules.update(saved)

