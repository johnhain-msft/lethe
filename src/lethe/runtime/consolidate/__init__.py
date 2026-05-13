"""Consolidate loop + write-side embedder seam (P4 — IMPL §2.4).

This package lands the dream-daemon consolidate machinery (composition
§4.1 lines 4-8) over P4's nine-commit buildable order. At commit 4 the
embedder seam (C3) and the pure-function consolidate scoring lib (C4)
are exposed; the rest of the package (``loop`` / ``phases`` /
``extract`` / ``embed`` / ``promote`` / ``demote`` / ``invalidate`` /
``scheduler``) lands in commits 5–9 and will append to this re-export
surface as it becomes consumer-visible.

Public re-exports (P4 commits 3–4):

- Embedder seam (C3):
  :class:`Embedder`, :class:`NullEmbedder`.
- Consolidate-time scoring adapter (C4 — :mod:`.score`):
  :class:`ConsolidateScoreInput`, :func:`score_fact`, plus
  re-exported :class:`WeightTuple`, :data:`DEFAULT_WEIGHTS`,
  :data:`DEFAULT_THETA_DEMOTE` from
  :mod:`lethe.runtime.scoring.per_class`.
- Cascade-cost math (C4 — :mod:`.gravity`):
  :func:`cascade_cost`, :func:`cascade_cost_99pct`, plus re-exported
  :func:`normalize_gravity` and :func:`gravity_mult` from
  :mod:`lethe.runtime.scoring.gravity`.
- Active-contradiction count adapter (C4 — :mod:`.contradiction`):
  :func:`count_active_contradictions`, plus re-exported
  :func:`contradiction_indicator` and :func:`eps_effective` from
  :mod:`lethe.runtime.scoring.contradiction`.

The implementations live in
:mod:`lethe.runtime.consolidate.embedder_protocol`,
:mod:`lethe.runtime.consolidate.score`,
:mod:`lethe.runtime.consolidate.gravity`, and
:mod:`lethe.runtime.consolidate.contradiction`.
"""

from __future__ import annotations

from lethe.runtime.consolidate.contradiction import (
    contradiction_indicator,
    count_active_contradictions,
    eps_effective,
)
from lethe.runtime.consolidate.embedder_protocol import (
    Embedder,
    NullEmbedder,
)
from lethe.runtime.consolidate.gravity import (
    cascade_cost,
    cascade_cost_99pct,
    gravity_mult,
    normalize_gravity,
)
from lethe.runtime.consolidate.score import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    ConsolidateScoreInput,
    WeightTuple,
    score_fact,
)

__all__ = [
    "DEFAULT_THETA_DEMOTE",
    "DEFAULT_WEIGHTS",
    "ConsolidateScoreInput",
    "Embedder",
    "NullEmbedder",
    "WeightTuple",
    "cascade_cost",
    "cascade_cost_99pct",
    "contradiction_indicator",
    "count_active_contradictions",
    "eps_effective",
    "gravity_mult",
    "normalize_gravity",
    "score_fact",
]
