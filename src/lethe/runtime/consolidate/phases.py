"""Phase dispatch table + per-phase adapter functions (P4 C7).

Per IMPLEMENT 7 sub-plan §L.3 + §L.6 + §L.13 (B-1..B-10): the
canonical 6-phase order from IMPL §2.4 invariant I-11 lives as a
:class:`Final` tuple here; the loop (:mod:`.loop`) iterates it. Each
``_xxx_phase`` is a thin adapter that takes a :class:`ConsolidateRun`
context dataclass and returns a :class:`PhaseResult` (the C6 frozen
return type, re-used so phase code shares one shape).

The 6 phase names match :data:`lethe.runtime.events._VALID_CONSOLIDATE_PHASES`
verbatim (a frozenset on the events.py side; the canonical I-11 ORDER
lives only here in the :data:`PHASE_DISPATCH` tuple — events.py owns
membership, this module owns ordering, the canonical-order test asserts
both).

P4 posture (per §L.8):

- ``_extract_phase`` is a thin adapter that calls
  :func:`lethe.runtime.consolidate.extract.run_extract` (C5 — its own
  ``BEGIN IMMEDIATE`` lifecycle). The episode count is dropped at the
  adapter boundary because :class:`PhaseResult` does not have a metric
  field at C6; a future P9 expansion adds metrics-by-fact via the
  ``LoopPhaseResult`` wrapper in :mod:`.loop` (per A8 + B-1).
- ``_score_phase`` is a NO-OP at P4 — :func:`.score.score_fact` is
  per-fact, not per-batch; gap-06 P9 owns the real batch scorer
  (B-7).
- ``_promote_phase`` / ``_demote_phase`` / ``_invalidate_phase`` are
  NO-OP adapters at P4 — the C6 :func:`.promote` / :func:`.demote` /
  :func:`.invalidate` need ``fact_ids``, but the loop has none until
  gap-06 P9 wires the real fact source (B-8).
- ``_consolidate_phase`` is genuinely no-op at P4 + C7 — the
  merge/derive step lands at P9 (gap-06) by REPLACING this adapter
  body. The canonical 6-phase cadence ships first so I-11 + the
  ``consolidate_phase`` event cadence are stable from C7 onward
  (B-10).

In-phase heartbeat carry-forward (per A9): in-phase heartbeat is OUT
OF SCOPE at C7 — phase impls run sub-second at P4. P9 (gap-06 fact
extraction) introduces phases that may exceed
:data:`.scheduler.LOCK_BREAK_SECONDS` (60 s); those phases MUST accept
a heartbeat callback or run under a daemon-side timer (P7+ deployment
scheduler). Carry-forward: B-3 expansion at P7+/P9.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from lethe.runtime.consolidate._reconciler import PhaseResult
from lethe.runtime.consolidate.embedder_protocol import Embedder
from lethe.runtime.consolidate.extract import run_extract
from lethe.runtime.events import SinkCallable
from lethe.store.s1_graph.client import S1Client
from lethe.store.s3_vec.client import S3Client


@dataclass(frozen=True)
class ConsolidateRun:
    """Frozen context dataclass passed into each phase adapter (per §L.6).

    Carries every piece of substrate a phase might need; phases that
    don't need a field simply ignore it. Frozen so adapters cannot
    mutate the context (any mutation would leak across phases via
    aliasing).
    """

    tenant_id: str
    tenant_root: Path
    s1_client: S1Client
    embedder: Embedder
    s3_client: S3Client
    run_id: str
    sink: SinkCallable | None
    now: datetime


PhaseImpl = Callable[[ConsolidateRun], PhaseResult]


def _empty_result() -> PhaseResult:
    """No-op :class:`PhaseResult` shared by the 5 P4-no-op adapters."""
    return PhaseResult(
        committed_fact_ids=(),
        sink_failures=(),
        orphans_backfilled=(),
    )


def _extract_phase(ctx: ConsolidateRun) -> PhaseResult:
    """Adapter for :func:`.extract.run_extract` (C5) — episode count dropped.

    Per B-1: ``run_extract`` opens its own ``BEGIN IMMEDIATE`` /
    ``COMMIT`` lifecycle and returns the episode count. The adapter
    drops the count at this boundary because :class:`PhaseResult` has
    no metric field at C6 (avoiding a 9th-path edit to ``_reconciler.py``
    per §L.15 deviation 1). The episode count surfaces in the S5
    audit trail via ``extraction_log`` rows that ``run_extract`` writes
    inside its own tx.

    TODO(P9): wire ``ctx.run_id`` into ``run_extract`` for cross-store
    audit traceability (currently ``run_extract`` uses its own per-call
    cursor advance without the consolidate ``run_id``; gap-06 fact
    extraction will surface this when extract emits fact events).
    """
    run_extract(
        tenant_root=ctx.tenant_root,
        s1_client=ctx.s1_client,
        embedder=ctx.embedder,
        s3_client=ctx.s3_client,
    )
    return _empty_result()


def _score_phase(ctx: ConsolidateRun) -> PhaseResult:
    """No-op at P4 (per B-7).

    :func:`.score.score_fact` is per-fact — no batch scorer exists at
    P4. gap-06 P9 owns the real batch scorer (scan candidates → score
    each → return outputs). The C7 adapter ships the empty body so the
    canonical 6-phase cadence is correct from day one; replacing this
    body at P9 is a one-function swap.
    """
    return _empty_result()


def _promote_phase(ctx: ConsolidateRun) -> PhaseResult:
    """No-op at P4 (per B-8).

    The C6 :func:`.promote` function needs ``fact_ids`` + ``score_outputs``
    + ``decisions``; the C7 loop has none of these until gap-06 P9
    wires the real fact source. The ``if fact_ids:`` guard inside this
    adapter body (when P9 lands) calls C6 :func:`.promote` with the
    derived inputs; for now the body is empty.
    """
    return _empty_result()


def _demote_phase(ctx: ConsolidateRun) -> PhaseResult:
    """No-op at P4 (per B-8).

    Same posture as :func:`_promote_phase` — C6 :func:`.demote` needs
    ``fact_ids`` + ``score_outputs`` + ``decisions`` + ``valid_to``.
    P9 wires; C7 ships empty.
    """
    return _empty_result()


def _consolidate_phase(ctx: ConsolidateRun) -> PhaseResult:
    """Genuine no-op at P4 + P9-incomplete (per B-10).

    The "consolidate" phase between demote and invalidate is the
    merge/derive step (gap-06 + IMPL §2.4). At P4 the merge logic
    doesn't exist; at P9 (gap-06) it lands as a real impl by REPLACING
    this adapter body. C7 ships the empty adapter so the canonical 6-
    phase cadence is correct from day one — I-11 + the
    ``consolidate_phase`` event cadence are stable from C7 onward.
    """
    return _empty_result()


def _invalidate_phase(ctx: ConsolidateRun) -> PhaseResult:
    """No-op at P4 (per B-8).

    Same posture as :func:`_promote_phase` — C6 :func:`.invalidate`
    needs ``fact_ids`` + ``decisions`` + ``superseded_by`` + ``valid_to``.
    P9 wires; C7 ships empty.
    """
    return _empty_result()


# Per IMPLEMENT 7 §L.3 + amendment A4: PHASE_DISPATCH owns the canonical
# I-11 ORDER (events.py:_VALID_CONSOLIDATE_PHASES is a frozenset and so
# does NOT carry order). The canonical-order test in
# tests/runtime/test_consolidate_phases.py asserts (a) tuple equality
# against the literal I-11 sequence + (b) frozenset membership
# equality against events.py — without referencing a non-existent
# events.py-side ordered constant.
PHASE_DISPATCH: Final[tuple[tuple[str, PhaseImpl], ...]] = (
    ("extract", _extract_phase),
    ("score", _score_phase),
    ("promote", _promote_phase),
    ("demote", _demote_phase),
    ("consolidate", _consolidate_phase),
    ("invalidate", _invalidate_phase),
)
