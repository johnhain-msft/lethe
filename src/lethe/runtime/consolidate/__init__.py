"""Consolidate loop + write-side embedder seam (P4 — IMPL §2.4).

This package lands the dream-daemon consolidate machinery (composition
§4.1 lines 4-8) over P4's nine-commit buildable order. At commit 5 the
extract→embed pipeline (C5) lands on top of the embedder seam (C3) and
the pure-function consolidate scoring lib (C4); the rest of the
package (``loop`` / ``phases`` / ``promote`` / ``demote`` /
``invalidate`` / ``scheduler``) lands in commits 6–9 and will append
to this re-export surface as it becomes consumer-visible.

Public re-exports (P4 commits 3–5):

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
- Extract → embed pipeline (C5 — :mod:`.extract` + :mod:`.embed`):
  :func:`run_extract`, :data:`EXTRACTOR_VERSION`, :func:`embed_episodes`,
  :func:`embed_nodes`, :func:`embed_edges`. The :class:`EpisodeRecord`
  type (sourced from :mod:`lethe.store.s1_graph.client`) is also
  re-exported as the consolidate-loop-facing episode shape.

The implementations live in
:mod:`lethe.runtime.consolidate.embedder_protocol`,
:mod:`lethe.runtime.consolidate.score`,
:mod:`lethe.runtime.consolidate.gravity`,
:mod:`lethe.runtime.consolidate.contradiction`,
:mod:`lethe.runtime.consolidate.embed`, and
:mod:`lethe.runtime.consolidate.extract`.
"""

from __future__ import annotations

from lethe.runtime.consolidate.contradiction import (
    contradiction_indicator,
    count_active_contradictions,
    eps_effective,
)
from lethe.runtime.consolidate.embed import (
    embed_edges,
    embed_episodes,
    embed_nodes,
)
from lethe.runtime.consolidate.embedder_protocol import (
    Embedder,
    NullEmbedder,
)
from lethe.runtime.consolidate.extract import (
    EXTRACTOR_VERSION,
    run_extract,
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
from lethe.store.s1_graph.client import EpisodeRecord

__all__ = [
    "DEFAULT_THETA_DEMOTE",
    "DEFAULT_WEIGHTS",
    "EXTRACTOR_VERSION",
    "ConsolidateScoreInput",
    "Embedder",
    "EpisodeRecord",
    "NullEmbedder",
    "WeightTuple",
    "cascade_cost",
    "cascade_cost_99pct",
    "contradiction_indicator",
    "count_active_contradictions",
    "embed_edges",
    "embed_episodes",
    "embed_nodes",
    "eps_effective",
    "gravity_mult",
    "normalize_gravity",
    "run_extract",
    "score_fact",
]
