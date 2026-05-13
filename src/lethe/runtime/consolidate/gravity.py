"""Cascade-cost math for consolidate-time gravity (scoring §3.6; Q1).

Pure summation over an already-weighted, undirected adjacency map. The
edge-class weight table (scoring §3.6 footnote — citation /
co-occurrence / supersession edge weights) is OWNED by the C6/C8 graph-
backend layer; this module does NOT define one. Callers materialize the
2-hop neighborhood with weights pre-applied, then call
:func:`cascade_cost`.

Re-exports :func:`gravity` (aliased :func:`normalize_gravity`) and
:func:`gravity_mult` from :mod:`lethe.runtime.scoring.gravity` so
consolidate-side callers (C7 loop) don't have to dual-import. The
local alias avoids the symbol-shadow that ``from lethe.runtime.scoring
import gravity`` would create against this module's name.

Q1 invariant (scoring §3.6 — gravity is a multiplier, NOT a sixth
additive term) is preserved by re-exporting :func:`gravity_mult` rather
than re-implementing it; the audit gate at C4 close rejects any second
definition of the multiplier formula.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from lethe.runtime.scoring.gravity import gravity as normalize_gravity
from lethe.runtime.scoring.gravity import gravity_mult

NodeId = str
AdjacencyMap = Mapping[NodeId, Mapping[NodeId, float]]

__all__ = [
    "AdjacencyMap",
    "NodeId",
    "cascade_cost",
    "cascade_cost_99pct",
    "gravity_mult",
    "normalize_gravity",
]


def cascade_cost(
    *,
    fact_id: NodeId,
    adjacency_2hop: AdjacencyMap,
) -> float:
    """Sum the weights of edges incident on ``fact_id``.

    ``adjacency_2hop`` is a caller-materialized 2-hop neighborhood with
    edge weights already applied (the C6/C8 graph-backend layer owns
    the edge-class weight table; this surface is taxonomy-agnostic).

    Semantics (binding):

    - Adjacency is treated as **undirected**. If both
      ``adjacency_2hop[a][b]`` and ``adjacency_2hop[b][a]`` are present
      they MUST agree exactly; disagreement raises :class:`ValueError`.
    - Each undirected edge is counted **once**, even when present in
      both directions.
    - Self-loops (``adjacency_2hop[a][a]``) are ignored.
    - Negative weights raise :class:`ValueError` (cost cannot subtract).
    - Missing or isolated ``fact_id`` returns ``0.0``.
    """
    edges: dict[NodeId, float] = {}

    forward = adjacency_2hop.get(fact_id, {})
    for neighbor, weight in forward.items():
        if neighbor == fact_id:
            continue
        if weight < 0.0:
            raise ValueError(
                f"cascade_cost: edge weight must be >= 0, got {weight!r} "
                f"on edge ({fact_id!r}, {neighbor!r})"
            )
        edges[neighbor] = weight

    for src, neighbors in adjacency_2hop.items():
        if src == fact_id:
            continue
        if fact_id not in neighbors:
            continue
        rev_weight = neighbors[fact_id]
        if rev_weight < 0.0:
            raise ValueError(
                f"cascade_cost: edge weight must be >= 0, got {rev_weight!r} "
                f"on edge ({src!r}, {fact_id!r})"
            )
        if src in edges:
            if edges[src] != rev_weight:
                raise ValueError(
                    f"cascade_cost: undirected adjacency disagreement on edge "
                    f"({fact_id!r}, {src!r}): forward={edges[src]!r}, "
                    f"reverse={rev_weight!r}"
                )
        else:
            edges[src] = rev_weight

    return sum(edges.values())


def cascade_cost_99pct(costs: Sequence[float]) -> float:
    """Deterministic 99th-percentile of cascade costs (no numpy).

    Sort-ascending + index ``min(len-1, max(0, ceil(0.99 * n) - 1))``
    (lower-bound discontinuous form — equivalent to numpy's
    ``method='lower'``). Empty input returns ``0.0``; negative cost
    raises :class:`ValueError`.

    Examples:

    - ``cascade_cost_99pct([])`` → ``0.0``
    - ``cascade_cost_99pct([42.0])`` → ``42.0``
    - ``cascade_cost_99pct(list(range(100)))`` → ``98.0``
      (n=100, ceil(99) - 1 = 98)
    """
    n = len(costs)
    if n == 0:
        return 0.0
    for cost in costs:
        if cost < 0.0:
            raise ValueError(f"cascade_cost_99pct: cost must be >= 0, got {cost!r}")
    sorted_costs = sorted(costs)
    idx = min(n - 1, max(0, math.ceil(0.99 * n) - 1))
    return sorted_costs[idx]
