"""Tests for ``runtime.retrievers`` — RRF combine + composition §3.1 fallback.

Covers:

- :func:`rrf_combine` correctness on a synthetic 3-list case (matches a
  hand-computed RRF score table).
- ``k_constant`` default is 60.
- Tie-breaking is deterministic by source-priority then ``fact_id``.
- ``top_k`` truncation.
- Empty input lists are tolerated.
- :func:`retrieve_all` falls back to lexical-only when the semantic
  backend raises :class:`S3Outage` (composition §3.1).
- :func:`retrieve_all` skips semantic when ``query_vec`` is None
  (Erratum E1: no write-side embedder at P3).
- Per-retriever ``k <= 0`` raises in each retriever entry point.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from lethe.runtime.retrievers import (
    Hit,
    S3Outage,
    graph_topk,
    lexical_topk,
    retrieve_all,
    rrf_combine,
    semantic_topk,
)


def _hits(source: str, ids: list[str]) -> list[Hit]:
    out: list[Hit] = []
    for i, fid in enumerate(ids):
        out.append(
            Hit(fact_id=fid, score=1.0 / (i + 1), source=source, rank=i + 1)  # type: ignore[arg-type]
        )
    return out


# ---------------------------------------------------------------------------
# rrf_combine
# ---------------------------------------------------------------------------


def test_rrf_combine_default_k_is_60() -> None:
    """A single-list, single-fact case yields exactly 1/(60+1)."""
    out = rrf_combine(ranked_lists=[_hits("semantic", ["a"])])
    assert len(out) == 1
    assert out[0].fact_id == "a"
    assert out[0].score == pytest.approx(1.0 / 61.0)


def test_rrf_combine_three_list_correctness() -> None:
    """Hand-computed RRF score table (k=60).

    semantic: [a, b, c]      → ranks a=1, b=2, c=3
    lexical:  [b, a, d]      → ranks b=1, a=2, d=3
    graph:    [c, e, a]      → ranks c=1, e=2, a=3

    RRF (k=60):
      a = 1/61 + 1/62 + 1/63   ≈ 0.04806
      b = 1/61 + 1/61          ≈ 0.03279
      c = 1/63 + 1/61          ≈ 0.03228
      d = 1/63                 ≈ 0.01587
      e = 1/62                 ≈ 0.01613

    Final order: a > b > c > e > d.
    """
    fused = rrf_combine(
        ranked_lists=[
            _hits("semantic", ["a", "b", "c"]),
            _hits("lexical", ["b", "a", "d"]),
            _hits("graph", ["c", "e", "a"]),
        ]
    )
    assert [h.fact_id for h in fused] == ["a", "b", "c", "e", "d"]
    assert [h.rank for h in fused] == [1, 2, 3, 4, 5]
    # Spot-check the analytic score for "a".
    a_hit = next(h for h in fused if h.fact_id == "a")
    assert a_hit.score == pytest.approx(1 / 61 + 1 / 62 + 1 / 63)
    # The first-source tie-break for "a" should be "semantic" (priority 0).
    assert a_hit.source == "semantic"


def test_rrf_combine_tie_breaks_by_source_priority_then_fact_id() -> None:
    """Two facts with identical RRF scores break ties deterministically.

    Both "x" and "y" appear once at rank 1 only:
      x in lexical (priority 1)
      y in graph (priority 2)
    Score is the same (1/61) → x wins on lower source priority.
    """
    fused = rrf_combine(
        ranked_lists=[
            [],
            [Hit(fact_id="x", score=1.0, source="lexical", rank=1)],
            [Hit(fact_id="y", score=1.0, source="graph", rank=1)],
        ]
    )
    assert [h.fact_id for h in fused] == ["x", "y"]


def test_rrf_combine_tie_breaks_by_fact_id_when_source_priority_equal() -> None:
    """Same source, same rank → lexicographic fact_id wins (ascending)."""
    fused = rrf_combine(
        ranked_lists=[
            [
                Hit(fact_id="zeta", score=1.0, source="lexical", rank=1),
                Hit(fact_id="alpha", score=1.0, source="lexical", rank=1),
            ]
        ]
    )
    # Both score 1/61; "alpha" < "zeta" lexicographically.
    assert [h.fact_id for h in fused] == ["alpha", "zeta"]


def test_rrf_combine_top_k_truncates() -> None:
    fused = rrf_combine(
        ranked_lists=[_hits("semantic", ["a", "b", "c", "d", "e"])],
        top_k=3,
    )
    assert [h.fact_id for h in fused] == ["a", "b", "c"]


def test_rrf_combine_handles_all_empty_lists() -> None:
    assert rrf_combine(ranked_lists=[[], [], []]) == []


def test_rrf_combine_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="k_constant"):
        rrf_combine(ranked_lists=[], k_constant=0)


def test_rrf_combine_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        rrf_combine(ranked_lists=[], top_k=0)


# ---------------------------------------------------------------------------
# Per-retriever entry points
# ---------------------------------------------------------------------------


class _FakeSemantic:
    def __init__(self, hits: list[Hit], *, raise_outage: bool = False) -> None:
        self._hits = hits
        self._raise_outage = raise_outage
        self.calls: list[tuple[Sequence[float], int]] = []

    def search(self, *, query_vec: Sequence[float], k: int) -> list[Hit]:
        if self._raise_outage:
            raise S3Outage("simulated sqlite-vec failure")
        self.calls.append((tuple(query_vec), k))
        return self._hits


class _FakeLexical:
    def __init__(self, hits: list[Hit]) -> None:
        self._hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, *, query: str, k: int) -> list[Hit]:
        self.calls.append((query, k))
        return self._hits


class _FakeGraph:
    def __init__(self, hits: list[Hit]) -> None:
        self._hits = hits
        self.calls: list[tuple[str, int]] = []

    def seed_topk(self, *, query: str, k: int) -> list[Hit]:
        self.calls.append((query, k))
        return self._hits


def test_semantic_topk_returns_empty_without_query_vec() -> None:
    backend = _FakeSemantic(_hits("semantic", ["a"]))
    assert semantic_topk(backend=backend, query_vec=None, k=5) == []
    assert backend.calls == []


def test_semantic_topk_returns_empty_without_backend() -> None:
    assert semantic_topk(backend=None, query_vec=[1.0, 0.0], k=5) == []


def test_semantic_topk_propagates_s3_outage() -> None:
    backend = _FakeSemantic([], raise_outage=True)
    with pytest.raises(S3Outage):
        semantic_topk(backend=backend, query_vec=[1.0, 0.0], k=5)


def test_lexical_topk_returns_empty_for_empty_query() -> None:
    backend = _FakeLexical(_hits("lexical", ["a"]))
    assert lexical_topk(backend=backend, query="", k=5) == []
    assert backend.calls == []


def test_graph_topk_returns_empty_for_empty_query() -> None:
    backend = _FakeGraph(_hits("graph", ["a"]))
    assert graph_topk(backend=backend, query="", k=5) == []


@pytest.mark.parametrize("entry", [semantic_topk, lexical_topk, graph_topk])
def test_each_retriever_rejects_non_positive_k(entry) -> None:  # type: ignore[no-untyped-def]
    """Every retriever entry point validates ``k > 0``."""
    if entry is semantic_topk:
        backend = _FakeSemantic([])
        with pytest.raises(ValueError, match="k must be positive"):
            entry(backend=backend, query_vec=[1.0], k=0)
    elif entry is lexical_topk:
        backend = _FakeLexical([])
        with pytest.raises(ValueError, match="k must be positive"):
            entry(backend=backend, query="q", k=0)
    else:  # graph_topk
        backend = _FakeGraph([])
        with pytest.raises(ValueError, match="k must be positive"):
            entry(backend=backend, query="q", k=0)


# ---------------------------------------------------------------------------
# retrieve_all orchestrator (composition §3.1 fallback)
# ---------------------------------------------------------------------------


def test_retrieve_all_falls_back_to_lexical_on_s3_outage() -> None:
    """When semantic raises S3Outage, lexical (and graph) still run."""
    semantic = _FakeSemantic([], raise_outage=True)
    lexical = _FakeLexical(_hits("lexical", ["lex-a", "lex-b"]))
    graph = _FakeGraph(_hits("graph", ["g-a"]))

    fused = retrieve_all(
        query="my query",
        query_vec=[1.0, 0.0, 0.0],
        semantic=semantic,
        lexical=lexical,
        graph=graph,
        k_per_retriever=10,
    )
    fused_ids = {h.fact_id for h in fused}
    # Semantic produced no candidates due to the outage; lexical + graph
    # contribute their full lists.
    assert fused_ids == {"lex-a", "lex-b", "g-a"}
    # Lexical and graph were both called; semantic was attempted (no
    # silent skip) but yielded nothing.
    assert lexical.calls == [("my query", 10)]
    assert graph.calls == [("my query", 10)]


def test_retrieve_all_skips_semantic_without_query_vec() -> None:
    """E1: no production embedder at P3 → query_vec=None is the norm."""
    semantic = _FakeSemantic(_hits("semantic", ["sem-a"]))
    lexical = _FakeLexical(_hits("lexical", ["lex-a"]))
    fused = retrieve_all(
        query="q",
        query_vec=None,
        semantic=semantic,
        lexical=lexical,
        graph=None,
    )
    assert {h.fact_id for h in fused} == {"lex-a"}
    assert semantic.calls == []  # never invoked


def test_retrieve_all_combines_all_three_when_all_configured() -> None:
    semantic = _FakeSemantic(_hits("semantic", ["a", "b"]))
    lexical = _FakeLexical(_hits("lexical", ["b", "c"]))
    graph = _FakeGraph(_hits("graph", ["c", "d"]))

    fused = retrieve_all(
        query="q",
        query_vec=[1.0],
        semantic=semantic,
        lexical=lexical,
        graph=graph,
        k_per_retriever=5,
    )
    # All four facts must appear.
    assert {h.fact_id for h in fused} == {"a", "b", "c", "d"}
    # b appears in semantic + lexical → highest score; a appears only
    # in semantic at rank 1; c appears in lexical@2 + graph@1.
    # b: 1/62 + 1/61; c: 1/62 + 1/61; tied → source priority breaks
    # (semantic < lexical < graph) → b wins (semantic priority 0,
    # lexical priority 1).
    assert fused[0].fact_id == "b"


def test_retrieve_all_top_k_combined_truncates() -> None:
    lexical = _FakeLexical(_hits("lexical", ["a", "b", "c", "d", "e"]))
    fused = retrieve_all(
        query="q",
        query_vec=None,
        semantic=None,
        lexical=lexical,
        graph=None,
        k_per_retriever=5,
        k_combined=2,
    )
    assert len(fused) == 2
    assert [h.fact_id for h in fused] == ["a", "b"]
