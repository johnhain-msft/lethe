"""Graph retriever — seeds for HippoRAG PPR (scoring §3.2; D2).

The retriever's job is to surface a *seed set* of candidate fact-ids
from the S1 graph backend; the actual PPR scoring happens in
:mod:`lethe.runtime.scoring.connectedness` (committed in commit 1) and
is invoked by the ``recall`` verb's post-rerank pass in commit 3.

P3 ships the function shape; the concrete backend that wraps
:class:`lethe.store.s1_graph.client.S1Client` is constructed by the
``recall`` verb in commit 3. Tests use an in-memory double.
"""

from __future__ import annotations

from lethe.runtime.retrievers import GraphBackend, Hit


def graph_topk(*, backend: GraphBackend, query: str, k: int) -> list[Hit]:
    """Return the top-``k`` graph-seed candidates for ``query``.

    Raises:
        ValueError: ``k`` is not a positive integer.
    """

    if k <= 0:
        raise ValueError(f"graph_topk: k must be positive, got {k}")
    if not query:
        return []
    return list(backend.seed_topk(query=query, k=k))


__all__ = ["graph_topk"]
