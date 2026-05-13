"""Lexical retriever — SQLite FTS5 / BM25 fallback (composition §3.1).

The lexical path is the **survival route** when the semantic store is
unreachable: composition §3.1 explicitly identifies it as the BM25
fallback that "survives S3 outage". For that reason the orchestrator
:func:`lethe.runtime.retrievers.retrieve_all` always runs lexical, even
when semantic is configured.

P3 ships the function shape; the concrete backend that wraps an FTS5
table over S1 episode bodies + S4 page text is constructed by the
``recall`` verb in commit 3.
"""

from __future__ import annotations

from lethe.runtime.retrievers import Hit, LexicalBackend


def lexical_topk(*, backend: LexicalBackend, query: str, k: int) -> list[Hit]:
    """Return the top-``k`` lexical candidates for ``query``.

    Empty queries are valid and yield ``[]`` (BM25 over the empty string
    is degenerate; backends should not be asked to handle it).

    Raises:
        ValueError: ``k`` is not a positive integer.
    """

    if k <= 0:
        raise ValueError(f"lexical_topk: k must be positive, got {k}")
    if not query:
        return []
    return list(backend.search(query=query, k=k))


__all__ = ["lexical_topk"]
