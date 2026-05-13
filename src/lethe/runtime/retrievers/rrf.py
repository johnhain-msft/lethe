"""Reciprocal Rank Fusion combine (scoring §4.2).

Cormack et al.'s RRF score for a candidate ``d`` across ``R`` ranked
lists::

    rrf(d) = Σ_{r ∈ R}  1 / (k_constant + rank_r(d))

with ``k_constant = 60`` per the qmd/Cormack default reaffirmed in
gap-03 §5. Candidates absent from a list contribute ``0`` from that
list. Final ordering is by descending RRF score; ties are broken
deterministically by:

1. Lower source-priority index (semantic < lexical < graph), using the
   *first* source the candidate appeared in (so a fact that ranked #3 in
   semantic and #5 in lexical breaks ties at the semantic index).
2. Lexicographically smaller ``fact_id``.

The combine is pure: it consumes the per-retriever ranks only, never
the retriever-native scores. The fused :class:`Hit` records the
candidate's *first* source (deterministic by ``_SOURCE_PRIORITY``) and
the RRF score in ``score``; ``rank`` is the 1-based position in the
fused output. The original per-source hits are not retained — the
``recall`` verb at commit 3 pairs the fused list against its own
fact-id → metadata map for downstream scoring.
"""

from __future__ import annotations

from collections.abc import Sequence

from lethe.runtime.retrievers import _SOURCE_PRIORITY, Hit


def rrf_combine(
    *,
    ranked_lists: Sequence[Sequence[Hit]],
    k_constant: int = 60,
    top_k: int | None = None,
) -> list[Hit]:
    """Fuse per-retriever ranked lists via RRF.

    Args:
        ranked_lists: One ranked list per retriever. Lists may be empty.
        k_constant: The RRF constant ``k`` (default 60).
        top_k: If provided, truncate the fused output to this many hits.

    Raises:
        ValueError: ``k_constant`` is not a positive integer or ``top_k``
            is non-positive when provided.
    """

    if k_constant <= 0:
        raise ValueError(f"rrf_combine: k_constant must be positive, got {k_constant}")
    if top_k is not None and top_k <= 0:
        raise ValueError(f"rrf_combine: top_k must be positive, got {top_k}")

    # Aggregate per-fact RRF score and remember the best (lowest priority
    # index) source the fact appeared in, for tie-breaking.
    scores: dict[str, float] = {}
    first_source: dict[str, str] = {}
    first_source_priority: dict[str, int] = {}

    for ranked in ranked_lists:
        for hit in ranked:
            scores[hit.fact_id] = scores.get(hit.fact_id, 0.0) + 1.0 / (
                k_constant + hit.rank
            )
            prio = _SOURCE_PRIORITY.get(hit.source, len(_SOURCE_PRIORITY))
            existing = first_source_priority.get(hit.fact_id)
            if existing is None or prio < existing:
                first_source_priority[hit.fact_id] = prio
                first_source[hit.fact_id] = hit.source

    # Sort: descending score, then ascending source priority, then
    # ascending fact_id (stable, deterministic across processes).
    ordered = sorted(
        scores.items(),
        key=lambda item: (
            -item[1],
            first_source_priority[item[0]],
            item[0],
        ),
    )
    if top_k is not None:
        ordered = ordered[:top_k]

    fused: list[Hit] = []
    for rank, (fact_id, score) in enumerate(ordered, start=1):
        fused.append(
            Hit(
                fact_id=fact_id,
                score=score,
                source=first_source[fact_id],  # type: ignore[arg-type]
                rank=rank,
            )
        )
    return fused


__all__ = ["rrf_combine"]
