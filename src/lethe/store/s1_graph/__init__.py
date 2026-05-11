"""S1 — temporal/graph index (Graphiti-backed).

Per composition §2 row 1, S1 is the source of truth for everything ``recall``
returns: typed entity nodes, typed edges with ``(valid_from, valid_to,
recorded_at)``, episodes (raw observation payloads), and provenance edges
from fact → episode.

P1 scope:
- :mod:`lethe.store.s1_graph.schema` — entity-type registry, episode shape,
  bi-temporal stamp helpers (backend-agnostic).
- :mod:`lethe.store.s1_graph.client` — :class:`GraphBackend` Protocol +
  :class:`S1Client` wrapper. Real :class:`GraphitiBackend` is defined here;
  a private in-memory backend is used by the P1 smoke (Graphiti requires
  Neo4j or FalkorDB; standing one up is deferred to a later phase).
"""

from lethe.store.s1_graph.client import (
    GraphBackend,
    GraphitiBackend,
    S1Client,
    _InMemoryGraphBackend,
)
from lethe.store.s1_graph.schema import (
    BASELINE_ENTITY_TYPES,
    BiTemporalStamp,
    EpisodeShape,
    now_recorded_at,
    stamp,
)

__all__ = [
    "BASELINE_ENTITY_TYPES",
    "BiTemporalStamp",
    "EpisodeShape",
    "GraphBackend",
    "GraphitiBackend",
    "S1Client",
    "_InMemoryGraphBackend",
    "now_recorded_at",
    "stamp",
]
