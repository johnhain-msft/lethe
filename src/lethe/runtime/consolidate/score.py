"""Consolidate-time scoring adapter (scoring §3 + §5; IMPL §2.4).

Thin typed wrapper around :func:`lethe.runtime.scoring.per_class.score`
for the consolidate loop's score phase (composition §4.1). The P3
``runtime.scoring`` lib owns the §3 composed formula and the §5.5
per-class parameter table — this module deliberately defines NO new
math. It only:

1. Bundles the per-fact score inputs into a frozen
   :class:`ConsolidateScoreInput` dataclass so the C7 loop can pass a
   single payload across the score / promote / demote phase boundary
   without keyword churn.
2. Re-exports :class:`WeightTuple`, :data:`DEFAULT_WEIGHTS`, and
   :data:`DEFAULT_THETA_DEMOTE` from
   :mod:`lethe.runtime.scoring.per_class` so consolidate-side callers
   (C6/C7) don't have to dual-import.

Q1 invariant (scoring §3.6): gravity remains a multiplier, not a sixth
additive — :func:`score_fact` calls into ``per_class.score`` whose
implementation already enforces this. Re-implementing the formula
here would risk drifting from that invariant, so this module is
intentionally adapter-only (audit gate §8 rejects formula
duplication).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from lethe.runtime.scoring.per_class import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    WeightTuple,
)
from lethe.runtime.scoring.per_class import score as per_class_score

__all__ = [
    "DEFAULT_THETA_DEMOTE",
    "DEFAULT_WEIGHTS",
    "ConsolidateScoreInput",
    "WeightTuple",
    "score_fact",
]


@dataclass(frozen=True)
class ConsolidateScoreInput:
    """Per-fact inputs for the consolidate-time score (scoring §3 + §5).

    All members are pre-computed by the caller (the C7 consolidate loop):

    - ``kind`` — frontmatter ``kind`` from the fact's S2 row; routed
      through :func:`lethe.runtime.scoring.per_class.shape_for_kind` for
      per-class params (§5.5). Non-persistent kinds raise
      :class:`~lethe.runtime.scoring.per_class.NonPersistentClass`.
    - ``t_access`` — last-access timestamp from the recall ledger /
      utility tally (scoring §5).
    - ``connectedness_value`` — already-normalized PPR percentile in the
      caller-selected graph slice (scoring §3.3); MUST be in ``[0, 1]``.
    - ``utility_value`` — already-normalized utility tally (scoring §3.2);
      MUST be in ``[0, 1]``.
    - ``contradiction_count`` — count of ACTIVE contradictions (gap-13;
      caller filters out superseded / revalidated edges).
    - ``gravity_value`` — already-clipped per-fact gravity (scoring §3.6);
      MUST be in ``[0, 1]``. Use
      :func:`lethe.runtime.consolidate.gravity.normalize_gravity` to
      normalize a raw cascade cost / 99th-percentile pair.
    - ``invalidated`` — gap-13 §3 invalidation flag; when ``True`` the
      gravity multiplier collapses to ``0`` per scoring §6.2.
    """

    kind: str
    t_access: datetime
    connectedness_value: float
    utility_value: float
    contradiction_count: int
    gravity_value: float
    invalidated: bool = False


def score_fact(
    input_: ConsolidateScoreInput,
    *,
    t_now: datetime,
    weights: WeightTuple = DEFAULT_WEIGHTS,
    theta_demote: float = DEFAULT_THETA_DEMOTE,
) -> float:
    """Compose the per-fact consolidate-time score (scoring §3).

    Pure delegation to :func:`lethe.runtime.scoring.per_class.score` —
    no math is added, no defaults are duplicated. ``weights`` and
    ``theta_demote`` flow through unchanged so consolidate-time A/B
    sweeps (P5) can override the gap-03 §5 candidate (a) defaults.
    """
    return per_class_score(
        kind=input_.kind,
        t_now=t_now,
        t_access=input_.t_access,
        connectedness_value=input_.connectedness_value,
        utility_value=input_.utility_value,
        contradiction_count=input_.contradiction_count,
        gravity_value=input_.gravity_value,
        weights=weights,
        theta_demote=theta_demote,
        invalidated=input_.invalidated,
    )
