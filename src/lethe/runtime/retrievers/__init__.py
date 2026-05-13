"""Retriever package — semantic / lexical / graph + RRF combine (scoring §4.2).

P3 ships the retriever *protocols* and the RRF combine function. The
actual S1 / S3 / FTS5 wiring is performed by the ``recall`` verb in
commit 3, which constructs concrete backends bound to a per-tenant
connection and passes them into :func:`retrieve_all`.

Composition §3.1 fallback: if the semantic backend raises :class:`S3Outage`
the orchestrator absorbs it and proceeds with lexical + graph only — the
lexical path is the documented S3-outage survival route.

Determinism: retrievers are called in a fixed order (semantic, lexical,
graph) so tie-breaking in the RRF combine is reproducible across
processes. Parallel fan-out is a P-later optimization.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

RetrieverSource = Literal["semantic", "lexical", "graph"]

# Deterministic source priority for RRF tie-breaking (lower index wins).
_SOURCE_PRIORITY: Final[dict[str, int]] = {
    "semantic": 0,
    "lexical": 1,
    "graph": 2,
}


@dataclass(frozen=True, order=False)
class Hit:
    """A single retrieval candidate.

    ``rank`` is 1-based within the retriever's own ranked list (rank 1 =
    top result). ``score`` is the retriever-native score (cosine for
    semantic, BM25 for lexical, PPR-weighted for graph) — surfaced for
    debugging / event payloads but NOT used by the RRF combine, which
    only consumes ranks.
    """

    fact_id: str
    score: float
    source: RetrieverSource
    rank: int


class RetrieverError(Exception):
    """Base class for retriever-layer failures."""


class S3Outage(RetrieverError):
    """Raised when the semantic backend cannot be reached (composition §3.1).

    The :func:`retrieve_all` orchestrator absorbs this exception and
    proceeds with lexical + graph only; callers should not catch this
    themselves at the verb layer.
    """


class SemanticBackend(Protocol):
    def search(self, *, query_vec: Sequence[float], k: int) -> list[Hit]: ...


class LexicalBackend(Protocol):
    def search(self, *, query: str, k: int) -> list[Hit]: ...


class GraphBackend(Protocol):
    def seed_topk(self, *, query: str, k: int) -> list[Hit]: ...


from lethe.runtime.retrievers.graph import graph_topk  # noqa: E402
from lethe.runtime.retrievers.lexical import lexical_topk  # noqa: E402
from lethe.runtime.retrievers.rrf import rrf_combine  # noqa: E402
from lethe.runtime.retrievers.semantic import semantic_topk  # noqa: E402


def retrieve_all(
    *,
    query: str,
    query_vec: Sequence[float] | None,
    semantic: SemanticBackend | None,
    lexical: LexicalBackend,
    graph: GraphBackend | None,
    k_per_retriever: int = 50,
    k_combined: int | None = None,
    rrf_k: int = 60,
) -> list[Hit]:
    """Run all configured retrievers, fuse with RRF, return top results.

    ``query_vec`` is optional because P3 has no production write-side
    embedder (Erratum E1) — callers that lack a query embedding pass
    ``None`` and only lexical + graph contribute. Tests / the DMR adapter
    supply a query vector built from the same offline model that
    populated the corpus.

    A :class:`S3Outage` raised by the semantic backend is absorbed and
    treated as zero semantic results (composition §3.1 fallback path).
    """

    semantic_hits: list[Hit] = []
    if semantic is not None and query_vec is not None:
        try:
            semantic_hits = semantic_topk(
                backend=semantic, query_vec=query_vec, k=k_per_retriever
            )
        except S3Outage:
            semantic_hits = []

    lexical_hits = lexical_topk(backend=lexical, query=query, k=k_per_retriever)

    graph_hits: list[Hit] = []
    if graph is not None:
        graph_hits = graph_topk(backend=graph, query=query, k=k_per_retriever)

    # Order matters — the RRF tie-breaker uses _SOURCE_PRIORITY, which
    # mirrors this order. Keep them aligned.
    return rrf_combine(
        ranked_lists=[semantic_hits, lexical_hits, graph_hits],
        k_constant=rrf_k,
        top_k=k_combined,
    )


__all__ = [
    "GraphBackend",
    "Hit",
    "LexicalBackend",
    "RetrieverError",
    "RetrieverSource",
    "S3Outage",
    "SemanticBackend",
    "graph_topk",
    "lexical_topk",
    "retrieve_all",
    "rrf_combine",
    "semantic_topk",
]
