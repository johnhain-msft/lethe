"""Invalidate phase — write S1 ``valid_to`` + flag ``tier='invalidated'`` (P4 commit 6).

Per scoring §6 + §6.4 + §8.1 + IMPL §2.4 invariant I-11. Invalidate is
the heaviest of the three C6 phases: it writes S1 ``valid_to`` (same as
:mod:`.demote`) AND carries a per-fact ``decision`` (the gap-13 §3
invalidate-reason enum) AND a per-fact ``superseded_by`` pointer (the
scoring §8.1 supersession pointer; ``None`` for hard invalidate, a
fact_id string for soft / superseded invalidate). Per IMPLEMENT 6
amendment A3 the phase does NOT touch ``utility_events`` at C6 — see
"Utility-events freeze posture" below.

Utility-events freeze posture (per IMPLEMENT 6 amendment A3):

Per scoring §6.4: "events arriving AFTER ``valid_to`` do not increment
the live tally". Existing ``utility_events`` rows have
``ts_recorded ≤ now = valid_to`` at invalidate time — none of them are
"after valid_to". The ``frozen`` column on ``utility_events`` is a
WRITE-SIDE defense for FUTURE events whose ``ts_recorded > fact.
valid_to`` (set by the future utility-event writer when it observes
the invalidate stamp); it is NOT an invalidate-time backfill. Read-side
aggregation (``score.py`` at P5+) filters by
``ts_recorded < valid_to`` and/or ``frozen=0``. Old fact's utility
events stay as audit history for the OLD fact (do NOT transfer to
the NEW fact); soft invalidate (``superseded_by ≠ None``) does NOT
migrate utility to the new fact.

S1-first + reconciler ordering (per §k.6 + composition §5 row 7):

Same as :mod:`.demote` — the phase writes S1 ``valid_to`` BEFORE the
S2 + S5 transaction. If the S2 + S5 tx fails after S1 commit, S1 is
left with ``valid_to`` set but no covering ``promotion_flags`` row;
the next consolidate run's reconciler backfills.

Partial S1-write failure invariant (per IMPLEMENT 6 amendment A4):

Same as :mod:`.demote` — S1 writes happen in a per-fact loop BEFORE
``BEGIN IMMEDIATE``. On partial S1-write failure (success on prefix
``[a, b]``, failure on ``c``), no S2/S5/event writes occur. Facts
``a`` and ``b`` are S1 orphans, backfilled by the next reconciler
pass (``tier='backfilled'``). Composition §5 row 7 governs the ledger
reconciliation path.

Per A8: ``event_id`` is RANDOM uuidv7 (not deterministic). The
:func:`_generate_uuidv7` helper mirrors :func:`api.remember.
_generate_uuidv7` + :func:`api.recall._generate_uuidv7` verbatim.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from lethe.runtime.consolidate._reconciler import PhaseResult, reconcile_orphans
from lethe.runtime.events import SinkCallable, emit
from lethe.store.s1_graph.client import S1Client
from lethe.store.s5_log.writer import LogEntry, SqliteLogWriter
from lethe.store.shared_conn import shared_store_connection

# Sentinel for the ``superseded_by`` defensive check: ``None`` is a
# legitimate value (hard invalidate), so :func:`Mapping.get` with a
# None default cannot disambiguate "missing key" from "key present,
# value is None". A unique sentinel does. Mirrors the ``_MISSING``
# pattern in :mod:`lethe.runtime.events`.
_MISSING: Final[object] = object()

# Per IMPLEMENT 6 §k.4 + B-3: the verb-side enum that bounds the
# ``decision`` field on ``invalidate`` events (gap-13 §3 invalidate
# reason taxonomy). Phase code rejects any value not in this set
# BEFORE the S1 write (gate 16).
INVALIDATE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "contradiction_detected",
        "score_below_floor",
        "superseded",
        "manual_correction",
    }
)

# Per IMPLEMENT 6 §k.10 — pinned literals at P4; sha256 hashing wires P5+.
CONSOLIDATE_MODEL_VERSION: Final[str] = "v1.0.0"
CONSOLIDATE_WEIGHTS_VERSION: Final[str] = "p4-default-weights"


def _generate_uuidv7(*, now: datetime) -> str:
    """Random uuidv7 for the ``event_id`` field (per IMPLEMENT 6 A8).

    Mirrors :func:`api.remember._generate_uuidv7` + :func:`api.recall.
    _generate_uuidv7` verbatim. Future cleanup ticket extracts these
    three copies to :mod:`lethe.runtime.uuidv7` (currently per-module
    by precedent — adding a new shared util is outside C6 scope).
    """
    unix_ts_ms = int(now.astimezone(UTC).timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    msb = (unix_ts_ms << 16) | (0x7 << 12) | rand_a
    lsb = (0b10 << 62) | rand_b
    value = (msb << 64) | lsb
    return str(uuid.UUID(int=value))


def _format_iso(dt: datetime) -> str:
    """RFC 3339 with the ``Z`` suffix (per IMPLEMENT 6 A11)."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_invalidate_inputs(
    *,
    fact_ids: Sequence[str],
    decisions: Mapping[str, str],
    superseded_by: Mapping[str, str | None],
    run_id: str,
    valid_to: str,
) -> None:
    """Per IMPLEMENT 6 amendment A5 — preflight all pure validation.

    Raises :class:`ValueError` with a specific message naming the
    offending field or fact_id. Tests assert the exact messages.
    """
    if not run_id:
        raise ValueError("invalidate: run_id must be a non-empty string")
    if not valid_to:
        raise ValueError("invalidate: valid_to must be a non-empty RFC 3339 string")
    try:
        datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"invalidate: valid_to {valid_to!r} is not a parseable RFC 3339 timestamp"
        ) from exc
    for fid in fact_ids:
        if fid not in decisions:
            raise ValueError(f"invalidate: fact_id {fid!r} missing from decisions")
        decision = decisions[fid]
        if decision not in INVALIDATE_REASONS:
            raise ValueError(
                f"invalidate: decision {decision!r} for fact_id {fid!r} not in "
                f"INVALIDATE_REASONS={sorted(INVALIDATE_REASONS)}"
            )
        # superseded_by uses a sentinel-distinguished check: the KEY
        # MUST be present (per events.py:148 envelope contract); the
        # VALUE may be None (hard invalidate) or a non-empty fact_id str.
        sb_value = (
            superseded_by.get(fid, _MISSING) if isinstance(superseded_by, Mapping) else _MISSING
        )
        if sb_value is _MISSING:
            raise ValueError(
                f"invalidate: fact_id {fid!r} missing from superseded_by "
                f"(key required; value may be None)"
            )
        if sb_value is not None and (not isinstance(sb_value, str) or not sb_value):
            raise ValueError(f"invalidate: superseded_by[{fid!r}] must be None or non-empty str")


def _build_invalidate_event(
    *,
    tenant_id: str,
    fact_id: str,
    decision: str,
    superseded_by: str | None,
    run_id: str,
    valid_to: str,
    now: datetime,
) -> dict[str, Any]:
    """Build a scoring §8.2 invalidate envelope (per IMPLEMENT 6 §k.10)."""
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "invalidate",
        "tenant_id": tenant_id,
        "ts_recorded": _format_iso(now),
        "ts_valid": valid_to,
        "model_version": CONSOLIDATE_MODEL_VERSION,
        "weights_version": CONSOLIDATE_WEIGHTS_VERSION,
        "contamination_protected": True,
        "fact_ids": [fact_id],
        "decision": decision,
        "superseded_by": superseded_by,
        "consolidate_run_id": run_id,
    }


def invalidate(
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
    fact_ids: Sequence[str],
    decisions: Mapping[str, str],
    superseded_by: Mapping[str, str | None],
    run_id: str,
    valid_to: str,
    now: datetime | None = None,
    sink: SinkCallable | None = None,
) -> PhaseResult:
    """Set ``valid_to`` on a batch of S1 facts + flag ``tier='invalidated'``.

    Phase order (per §k.6 + A3 — utility_events untouched):

    1. Preflight (raises :class:`ValueError` on caller errors).
    2. Reconciler (own tx; backfills any prior S1 orphans).
    3. S1 writes per-fact in a loop (S1-first ordering).
    4. S2 (``promotion_flags``) + S5 writes in a single ``BEGIN
       IMMEDIATE`` / ``COMMIT`` tx. **Does NOT touch ``utility_events``
       at C6** (see module docstring "Utility-events freeze posture").
    5. Post-commit emit per envelope (sink failures collected, not
       raised — see :class:`PhaseResult`).
    """
    _validate_invalidate_inputs(
        fact_ids=fact_ids,
        decisions=decisions,
        superseded_by=superseded_by,
        run_id=run_id,
        valid_to=valid_to,
    )

    try:
        orphans = reconcile_orphans(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            s1_client=s1_client,
        )
    except BaseException as reconciler_err:
        raise RuntimeError("reconciliation failed; phase did not run") from reconciler_err

    # S1-first per-fact loop. Per A4: if this raises mid-loop, no S2/S5
    # writes occur (we have not yet entered BEGIN IMMEDIATE).
    for fid in fact_ids:
        s1_client.set_fact_valid_to(fact_id=fid, valid_to=valid_to)

    n = now or datetime.now(UTC)
    flag_set_at = _format_iso(n)
    envelopes: list[dict[str, Any]] = [
        _build_invalidate_event(
            tenant_id=tenant_id,
            fact_id=fid,
            decision=decisions[fid],
            superseded_by=superseded_by[fid],
            run_id=run_id,
            valid_to=valid_to,
            now=n,
        )
        for fid in fact_ids
    ]

    writer = SqliteLogWriter(tenant_root)
    with shared_store_connection(tenant_root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for fid in fact_ids:
                conn.execute(
                    "INSERT OR REPLACE INTO main.promotion_flags "
                    "(tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (tenant_id, fid, "invalidated", flag_set_at, run_id, decisions[fid]),
                )
            for envelope in envelopes:
                writer.append_with_conn(
                    LogEntry(
                        kind="invalidate",
                        payload=envelope,
                    ),
                    conn=conn,
                )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise

    sink_failures: list[tuple[str, Exception]] = []
    for envelope in envelopes:
        try:
            emit(envelope, sink=sink)
        except Exception as sink_err:
            sink_failures.append((str(envelope["event_id"]), sink_err))

    return PhaseResult(
        committed_fact_ids=tuple(fact_ids),
        sink_failures=tuple(sink_failures),
        orphans_backfilled=tuple(orphans),
    )
