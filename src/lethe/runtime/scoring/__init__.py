"""Scoring lib — per-class dispatch + 5 additive terms (scoring §3 + §5).

Public re-exports for the recall path (P3 commit 3+) and consolidate path
(P4+). Pure functions throughout — no S1 / S2 / S3 dependencies. Callers
materialize graph adjacency, ledger event lists, and gravity inputs.

See :mod:`.per_class` for the composed entry point :func:`score`.
"""

from __future__ import annotations

from lethe.runtime.scoring import (
    connectedness as connectedness_mod,
)
from lethe.runtime.scoring import (
    contradiction as contradiction_mod,
)
from lethe.runtime.scoring import (
    gravity as gravity_mod,
)
from lethe.runtime.scoring import (
    recency as recency_mod,
)
from lethe.runtime.scoring import (
    utility as utility_mod,
)
from lethe.runtime.scoring.per_class import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    TYPE_PRIORITY,
    ClassParams,
    NonPersistentClass,
    PersistentShape,
    ScoringError,
    UnknownClass,
    WeightTuple,
    score,
    shape_for_kind,
    type_priority,
)

__all__ = [
    # Composed entry
    "score",
    "shape_for_kind",
    "type_priority",
    # Types
    "ClassParams",
    "PersistentShape",
    "WeightTuple",
    # Defaults
    "DEFAULT_WEIGHTS",
    "DEFAULT_THETA_DEMOTE",
    "TYPE_PRIORITY",
    # Errors
    "ScoringError",
    "NonPersistentClass",
    "UnknownClass",
    # Submodules (callers may need lower-level access)
    "connectedness_mod",
    "contradiction_mod",
    "gravity_mod",
    "recency_mod",
    "utility_mod",
]
