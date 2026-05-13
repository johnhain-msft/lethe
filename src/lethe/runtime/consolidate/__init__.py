"""Consolidate loop + write-side embedder seam (P4 — IMPL §2.4).

This package lands the dream-daemon consolidate machinery (composition
§4.1 lines 4-8) over P4's nine-commit buildable order. At commit 6 the
three phase impls (:mod:`.promote`, :mod:`.demote`, :mod:`.invalidate`)
land on top of the cross-store T2 seam (C5), the pure-function
consolidate scoring lib (C4), and the embedder seam (C3); the
remaining loop/scheduler/PPR-wiring/Appendix-A-smoke ship in commits
7–9 and will append to this re-export surface as they become
consumer-visible.

Public re-exports (P4 commits 3–6):

- Embedder seam (C3):
  :class:`Embedder`, :class:`NullEmbedder`.
- Consolidate-time scoring adapter (C4 — :mod:`.score`):
  :class:`ConsolidateScoreInput`, :func:`score_fact`, plus
  re-exported :class:`WeightTuple`, :data:`DEFAULT_WEIGHTS`,
  :data:`DEFAULT_THETA_DEMOTE` from
  :mod:`lethe.runtime.scoring.per_class`.
- Cascade-cost math (C4 — :mod:`.gravity`):
  :func:`cascade_cost`, :func:`cascade_cost_99pct`, plus re-exported
  :func:`normalize_gravity` and :func:`gravity_mult` from
  :mod:`lethe.runtime.scoring.gravity`.
- Active-contradiction count adapter (C4 — :mod:`.contradiction`):
  :func:`count_active_contradictions`, plus re-exported
  :func:`contradiction_indicator` and :func:`eps_effective` from
  :mod:`lethe.runtime.scoring.contradiction`.
- Extract → embed pipeline (C5 — :mod:`.extract` + :mod:`.embed`):
  :func:`run_extract`, :data:`EXTRACTOR_VERSION`, :func:`embed_episodes`,
  :func:`embed_nodes`, :func:`embed_edges`. The :class:`EpisodeRecord`
  type (sourced from :mod:`lethe.store.s1_graph.client`) is also
  re-exported as the consolidate-loop-facing episode shape.
- Phase impls (C6 — :mod:`.promote` + :mod:`.demote` + :mod:`.invalidate`):
  :func:`promote`, :func:`demote`, :func:`invalidate`, the verb-side
  decision/reason enums (:data:`PROMOTE_DECISIONS`,
  :data:`DEMOTE_DECISIONS`, :data:`INVALIDATE_REASONS`), the shared
  ``promotion_flags`` tier enum (:data:`PROMOTION_FLAG_TIERS`), the
  versioning literals stamped on emitted events
  (:data:`CONSOLIDATE_MODEL_VERSION`,
  :data:`CONSOLIDATE_WEIGHTS_VERSION`), and :class:`FactRecord` (sourced
  from :mod:`lethe.store.s1_graph.client`) re-exported as the
  consolidate-loop-facing fact shape. :class:`PhaseResult` is the frozen
  return type of every phase function.
- Loop orchestration (C7 — :mod:`.loop` + :mod:`.scheduler` +
  :mod:`.phases`): :func:`run_one_consolidate` is THE public entry
  point; :class:`ConsolidateRunResult` + :class:`LoopPhaseResult` are
  the loop's frozen return shape; :class:`ConsolidateRun` is the per-
  cycle context dataclass; :data:`PHASE_DISPATCH` is the canonical
  I-11 6-phase order tuple. Scheduler primitives (:func:`acquire_lock`,
  :func:`heartbeat`, :func:`clear_lock`,
  :func:`mark_success_and_release`, :func:`force_clear_lock`,
  :func:`should_run`) and the gate constants
  (:data:`GATE_INTERVAL_SECONDS`, :data:`HEARTBEAT_INTERVAL_SECONDS`,
  :data:`LOCK_BREAK_SECONDS`) are re-exported for direct test access.
  :class:`LockAcquisitionFailed` is the contention error.

The implementations live in
:mod:`lethe.runtime.consolidate.embedder_protocol`,
:mod:`lethe.runtime.consolidate.score`,
:mod:`lethe.runtime.consolidate.gravity`,
:mod:`lethe.runtime.consolidate.contradiction`,
:mod:`lethe.runtime.consolidate.embed`,
:mod:`lethe.runtime.consolidate.extract`,
:mod:`lethe.runtime.consolidate.promote`,
:mod:`lethe.runtime.consolidate.demote`,
:mod:`lethe.runtime.consolidate.invalidate`,
:mod:`lethe.runtime.consolidate._reconciler`,
:mod:`lethe.runtime.consolidate.scheduler`,
:mod:`lethe.runtime.consolidate.phases`, and
:mod:`lethe.runtime.consolidate.loop`.
"""

from __future__ import annotations

from typing import Final

from lethe.runtime.consolidate._reconciler import PhaseResult
from lethe.runtime.consolidate.contradiction import (
    contradiction_indicator,
    count_active_contradictions,
    eps_effective,
)
from lethe.runtime.consolidate.demote import (
    DEMOTE_DECISIONS,
    demote,
)
from lethe.runtime.consolidate.embed import (
    embed_edges,
    embed_episodes,
    embed_nodes,
)
from lethe.runtime.consolidate.embedder_protocol import (
    Embedder,
    NullEmbedder,
)
from lethe.runtime.consolidate.extract import (
    EXTRACTOR_VERSION,
    run_extract,
)
from lethe.runtime.consolidate.gravity import (
    cascade_cost,
    cascade_cost_99pct,
    gravity_mult,
    normalize_gravity,
)
from lethe.runtime.consolidate.invalidate import (
    INVALIDATE_REASONS,
    invalidate,
)
from lethe.runtime.consolidate.loop import (
    ConsolidateRunResult,
    LoopPhaseResult,
    run_one_consolidate,
)
from lethe.runtime.consolidate.phases import (
    PHASE_DISPATCH,
    ConsolidateRun,
)
from lethe.runtime.consolidate.promote import (
    CONSOLIDATE_MODEL_VERSION,
    CONSOLIDATE_WEIGHTS_VERSION,
    PROMOTE_DECISIONS,
    promote,
)
from lethe.runtime.consolidate.scheduler import (
    GATE_INTERVAL_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    LOCK_BREAK_SECONDS,
    LockAcquisitionFailed,
    acquire_lock,
    clear_lock,
    force_clear_lock,
    heartbeat,
    mark_success_and_release,
    should_run,
)
from lethe.runtime.consolidate.score import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    ConsolidateScoreInput,
    WeightTuple,
    score_fact,
)
from lethe.store.s1_graph.client import EpisodeRecord, FactRecord

# Per IMPLEMENT 6 §k.8: the verb-side enum that bounds the ``tier``
# column on every ``promotion_flags`` row. Phase code (and the
# reconciler) asserts ``tier ∈ PROMOTION_FLAG_TIERS`` BEFORE INSERT
# OR REPLACE — gives a clearer error than waiting for a downstream
# read to choke. Lives in __init__.py because it is shared across
# all three phase modules + the reconciler (avoids a circular import).
PROMOTION_FLAG_TIERS: Final[frozenset[str]] = frozenset(
    {
        "promoted",
        "demoted",
        "invalidated",
        "backfilled",
    }
)

__all__ = [
    "CONSOLIDATE_MODEL_VERSION",
    "CONSOLIDATE_WEIGHTS_VERSION",
    "DEFAULT_THETA_DEMOTE",
    "DEFAULT_WEIGHTS",
    "DEMOTE_DECISIONS",
    "EXTRACTOR_VERSION",
    "GATE_INTERVAL_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
    "INVALIDATE_REASONS",
    "LOCK_BREAK_SECONDS",
    "PHASE_DISPATCH",
    "PROMOTE_DECISIONS",
    "PROMOTION_FLAG_TIERS",
    "ConsolidateRun",
    "ConsolidateRunResult",
    "ConsolidateScoreInput",
    "Embedder",
    "EpisodeRecord",
    "FactRecord",
    "LockAcquisitionFailed",
    "LoopPhaseResult",
    "NullEmbedder",
    "PhaseResult",
    "WeightTuple",
    "acquire_lock",
    "cascade_cost",
    "cascade_cost_99pct",
    "clear_lock",
    "contradiction_indicator",
    "count_active_contradictions",
    "demote",
    "embed_edges",
    "embed_episodes",
    "embed_nodes",
    "eps_effective",
    "force_clear_lock",
    "gravity_mult",
    "heartbeat",
    "invalidate",
    "mark_success_and_release",
    "normalize_gravity",
    "promote",
    "run_extract",
    "run_one_consolidate",
    "score_fact",
    "should_run",
]
