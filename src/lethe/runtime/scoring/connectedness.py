"""Structural connectedness — HippoRAG personalized PageRank (scoring §3.2).

```
connectedness(f) = percentile_rank( PPR(f; d=0.85, seeds={f}) , N_2hop(f) )
```

with a degree-percentile fallback when the 2-hop subgraph is degenerate
(< ``DEGREE_FALLBACK_THRESHOLD`` nodes — gap-03 §4(a)).

This module is **pure** — it operates on adjacency dicts supplied by the
caller, never on the live S1 backend. The retriever package (P3 commit 2)
is responsible for materializing the right graph slice (fact-graph for
episodic facts and preferences, procedure-seq for procedures,
narrative-doc edges for narratives — scoring §5.5).

Adjacency shape: ``Mapping[NodeId, Mapping[NodeId, float]]`` where the
inner map's value is the (non-negative) edge weight; absence of an edge
means weight 0. Edges are treated as **undirected** for connectedness
(an edge ``a -> b`` with weight ``w`` is equivalent to ``b -> a`` with
weight ``w``); callers wanting directed graphs symmetrize first.

Locked decision D2 (facilitator P3 plan §(g)): full HippoRAG PPR, NOT
the simplified-only path. Without PPR the connectedness term is
meaningless (R6) and forces a re-do at P4.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from typing import Final

DEFAULT_DAMPING: Final[float] = 0.85  # standard PageRank value (scoring §3.2)
DEFAULT_MAX_ITER: Final[int] = 50
DEFAULT_TOL: Final[float] = 1e-6
DEFAULT_TWO_HOP_CAP: Final[int] = 500  # scoring §3.2 cost cap
DEGREE_FALLBACK_THRESHOLD: Final[int] = 10  # scoring §3.2 fallback trigger

NodeId = str
Adjacency = Mapping[NodeId, Mapping[NodeId, float]]


def two_hop_subgraph(
    adj: Adjacency,
    *,
    seed: NodeId,
    cap: int = DEFAULT_TWO_HOP_CAP,
) -> dict[NodeId, dict[NodeId, float]]:
    """Return the 2-hop subgraph around ``seed`` capped at ``cap`` nodes.

    BFS from ``seed`` to depth 2, collecting every node visited. The cap
    is enforced by truncating the BFS frontier — the resulting node set
    contains at most ``cap`` nodes (always including ``seed``). Edges in
    the returned subgraph are restricted to those whose endpoints are
    both inside the collected node set; weights are preserved.
    """
    if cap < 1:
        raise ValueError(f"two_hop_subgraph: cap must be >= 1, got {cap!r}")
    if seed not in adj:
        return {seed: {}}

    visited: set[NodeId] = {seed}
    queue: deque[tuple[NodeId, int]] = deque([(seed, 0)])
    while queue and len(visited) < cap:
        node, depth = queue.popleft()
        if depth >= 2:
            continue
        for nbr in adj.get(node, {}):
            if nbr in visited:
                continue
            visited.add(nbr)
            if len(visited) >= cap:
                break
            queue.append((nbr, depth + 1))

    sub: dict[NodeId, dict[NodeId, float]] = {}
    for node in visited:
        sub[node] = {
            nbr: float(w)
            for nbr, w in adj.get(node, {}).items()
            if nbr in visited and float(w) > 0.0
        }
    # Symmetrize: any edge present in one direction must be present in both
    # (connectedness treats the graph as undirected per module docstring).
    for node, nbrs in list(sub.items()):
        for nbr, w in nbrs.items():
            if node not in sub.get(nbr, {}):
                sub[nbr][node] = w
    return sub


def degree_percentile(
    adj: Adjacency,
    *,
    node: NodeId,
) -> float:
    """Fallback metric: ``degree(node) / max_degree(N_1hop(node))``.

    Used when :func:`two_hop_subgraph` returns fewer than
    :data:`DEGREE_FALLBACK_THRESHOLD` nodes (gap-03 §4(a)).

    Returns ``0.0`` for an isolated node; ``1.0`` if ``node`` has the
    largest degree in its 1-hop neighborhood (including itself).
    """
    own_degree = len(adj.get(node, {}))
    if own_degree == 0:
        return 0.0
    neighborhood_degrees = [own_degree]
    for nbr in adj.get(node, {}):
        neighborhood_degrees.append(len(adj.get(nbr, {})))
    max_deg = max(neighborhood_degrees)
    if max_deg == 0:
        return 0.0
    return own_degree / max_deg


def personalized_pagerank(
    adj: Adjacency,
    *,
    seed: NodeId,
    damping: float = DEFAULT_DAMPING,
    max_iter: int = DEFAULT_MAX_ITER,
    tol: float = DEFAULT_TOL,
) -> dict[NodeId, float]:
    """Power-iteration PPR with restart probability ``1 - damping`` to ``seed``.

    Returns a stationary probability distribution over the nodes of
    ``adj`` (sum approximately 1.0). For an empty adjacency or a seed
    not present in ``adj``, returns ``{seed: 1.0}``.

    Convergence: stops at ``max_iter`` iterations or when the L1 distance
    between successive distributions falls below ``tol``.
    """
    if not 0.0 < damping < 1.0:
        raise ValueError(f"personalized_pagerank: damping must lie in (0, 1), got {damping!r}")
    if max_iter < 1:
        raise ValueError(f"personalized_pagerank: max_iter must be >= 1, got {max_iter!r}")
    if tol <= 0.0:
        raise ValueError(f"personalized_pagerank: tol must be positive, got {tol!r}")

    nodes = list(adj.keys())
    if seed not in adj:
        return {seed: 1.0}
    n = len(nodes)
    if n == 0:
        return {seed: 1.0}

    # Pre-compute per-node weighted out-degree for normalization.
    out_weight: dict[NodeId, float] = {
        node: sum(float(w) for w in adj[node].values()) for node in nodes
    }

    # Initial mass entirely on the seed.
    rank: dict[NodeId, float] = dict.fromkeys(nodes, 0.0)
    rank[seed] = 1.0

    teleport = 1.0 - damping

    for _ in range(max_iter):
        new_rank: dict[NodeId, float] = dict.fromkeys(nodes, 0.0)
        # Mass distributed by edges.
        dangling_mass = 0.0
        for node in nodes:
            r = rank[node]
            if r == 0.0:
                continue
            ow = out_weight[node]
            if ow == 0.0:
                # Dangling node: its mass teleports back to the seed
                # (personalized variant — uniform teleport would dilute
                # the personalization vector).
                dangling_mass += r
                continue
            share = damping * r / ow
            for nbr, w in adj[node].items():
                wf = float(w)
                if wf <= 0.0:
                    continue
                new_rank[nbr] += share * wf
        # Restart probability + dangling-mass redirect, both to the seed
        # (the personalization vector concentrates 100 % on `seed`).
        new_rank[seed] += teleport + damping * dangling_mass

        # Convergence check.
        delta = sum(abs(new_rank[k] - rank[k]) for k in nodes)
        rank = new_rank
        if delta < tol:
            break

    return rank


def _percentile_rank(value: float, population: list[float]) -> float:
    """Fraction of ``population`` strictly less than ``value``.

    Returns ``0.0`` for an empty population. Used for the §3.2
    "report stationary probability of ``f`` itself relative to its
    2-hop neighborhood" semantic.
    """
    if not population:
        return 0.0
    less_than = sum(1 for v in population if v < value)
    return less_than / len(population)


def connectedness(
    adj: Adjacency,
    *,
    fact_id: NodeId,
    two_hop_cap: int = DEFAULT_TWO_HOP_CAP,
    fallback_threshold: int = DEGREE_FALLBACK_THRESHOLD,
    damping: float = DEFAULT_DAMPING,
    max_iter: int = DEFAULT_MAX_ITER,
    tol: float = DEFAULT_TOL,
) -> float:
    """Composed scoring §3.2 entry point.

    1. Materialize the 2-hop subgraph around ``fact_id`` (capped).
    2. If the subgraph has fewer than ``fallback_threshold`` nodes,
       return :func:`degree_percentile` over the full ``adj``.
    3. Otherwise run :func:`personalized_pagerank` over the subgraph,
       seeded on ``fact_id``, and return the percentile rank of
       ``fact_id``'s stationary probability against the rest of the
       subgraph.

    Output range: ``[0.0, 1.0]``.
    """
    sub = two_hop_subgraph(adj, seed=fact_id, cap=two_hop_cap)
    if len(sub) < fallback_threshold:
        return degree_percentile(adj, node=fact_id)

    pr = personalized_pagerank(
        sub, seed=fact_id, damping=damping, max_iter=max_iter, tol=tol
    )
    own_score = pr.get(fact_id, 0.0)
    population = [score for nid, score in pr.items() if nid != fact_id]
    return _percentile_rank(own_score, population)
