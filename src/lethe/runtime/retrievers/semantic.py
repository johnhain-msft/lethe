"""Semantic retriever — sqlite-vec cosine top-k (composition §3.1; scoring §4.2).

P3 surface: a thin function that delegates to a :class:`SemanticBackend`
Protocol. The concrete backend that wraps :class:`lethe.store.s3_vec.client.S3Client`
is constructed in commit 3 (the ``recall`` verb owns the per-tenant
connection lifecycle); the function itself is backend-agnostic so unit
tests can supply an in-memory recording double.

Erratum E1: there is no write-side embedder at P3, so production callers
will typically pass ``query_vec=None`` and the semantic retriever
returns ``[]``. The DMR adapter (commit 5) supplies a query vector built
from the same offline-pinned model that populated the corpus fixtures.
"""

from __future__ import annotations

from collections.abc import Sequence

from lethe.runtime.retrievers import Hit, S3Outage, SemanticBackend


def semantic_topk(
    *,
    backend: SemanticBackend | None,
    query_vec: Sequence[float] | None,
    k: int,
) -> list[Hit]:
    """Return the top-``k`` semantic candidates, or ``[]`` if no embedding.

    Raises:
        S3Outage: the backend was unable to reach the sqlite-vec store.
            The :func:`retrieve_all` orchestrator catches this; direct
            callers must decide whether to surface or absorb.
        ValueError: ``k`` is not a positive integer.
    """

    if k <= 0:
        raise ValueError(f"semantic_topk: k must be positive, got {k}")
    if backend is None or query_vec is None:
        return []
    return list(backend.search(query_vec=query_vec, k=k))


__all__ = ["S3Outage", "semantic_topk"]
