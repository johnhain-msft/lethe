"""Promote phase — flag scored facts as promoted (P4 commit 6).

Per scoring §8.1 + IMPL §2.4 invariant I-11. Promote is an S2-only event
(NO S1 ``valid_to`` write — promotion does not retire a fact, it merely
flags it as having cleared ``θ_promote``). Promotion is the lightest of
the three C6 phases; the heavier "this fact is no longer valid" semantics
live in :mod:`.demote` (S1 ``valid_to`` set + ``tier='demoted'`` flag) and
:mod:`.invalidate` (same plus reason enum + supersession pointer).

Phase function structure (per IMPLEMENT 6 amendment A5 — preflight all
pure validation BEFORE any I/O so a caller error never creates an S1
orphan; promote does not write S1 so the orphan risk is moot here, but
the pattern is uniform across the three phase modules):

1. PREFLIGHT (:func:`_validate_promote_inputs`) — pure validation, raises
   :class:`ValueError` on any caller error (missing ``score_outputs`` key,
   unknown ``decision``, empty ``run_id``).
2. RECONCILER (:func:`._reconciler.reconcile_orphans`) — own tx; backfills
   any S1 valid_to facts that lack a covering ``promotion_flags`` row.
3. (No S1 writes — see module docstring.)
4. S2 + S5 writes via the shared-conn seam under ``BEGIN IMMEDIATE`` /
   ``COMMIT`` (single transaction).
5. POST-COMMIT event emit (per A9 — sink failures collected into
   :attr:`PhaseResult.sink_failures`, never roll back state).

Per IMPLEMENT 6 amendment A8: ``event_id`` is a RANDOM uuidv7 (not
deterministic). The :func:`_generate_uuidv7` helper mirrors
``api.remember._generate_uuidv7`` + ``api.recall._generate_uuidv7``
verbatim; a future cleanup ticket extracts to
:mod:`lethe.runtime.uuidv7`.
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

# Per IMPLEMENT 6 §k.4 + B-3: the verb-side enum that bounds the
# ``decision`` field on ``promote`` events. Phase code rejects any
# ``decision`` not in this set BEFORE the S2 write (gate 16) — gives a
# clearer error than waiting for a downstream consumer to choke.
PROMOTE_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "score_above_theta_promote",
    }
)

# Per IMPLEMENT 6 §k.10: the model + weights versions stamped on the
# emitted event envelope. Pinned to literal constants at P4; sha256
# hashing wires at P5+ when the live versioning surface lands.
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


def _validate_promote_inputs(
    *,
    fact_ids: Sequence[str],
    score_outputs: Mapping[str, float],
    decisions: Mapping[str, str],
    run_id: str,
) -> None:
    """Per IMPLEMENT 6 amendment A5 — preflight all pure validation.

    Raises :class:`ValueError` with a specific message naming the
    offending field or fact_id. Tests assert the exact messages.
    """
    if not run_id:
        raise ValueError("promote: run_id must be a non-empty string")
    for fid in fact_ids:
        if fid not in score_outputs:
            raise ValueError(f"promote: fact_id {fid!r} missing from score_outputs")
        if fid not in decisions:
            raise ValueError(f"promote: fact_id {fid!r} missing from decisions")
        decision = decisions[fid]
        if decision not in PROMOTE_DECISIONS:
            raise ValueError(
                f"promote: decision {decision!r} for fact_id {fid!r} not in "
                f"PROMOTE_DECISIONS={sorted(PROMOTE_DECISIONS)}"
            )


def _build_promote_event(
    *,
    tenant_id: str,
    fact_id: str,
    decision: str,
    score_output: float,
    run_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Build a scoring §8.2 promote envelope (per IMPLEMENT 6 §k.10)."""
    ts = _format_iso(now)
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "promote",
        "tenant_id": tenant_id,
        "ts_recorded": ts,
        "ts_valid": ts,
        "model_version": CONSOLIDATE_MODEL_VERSION,
        "weights_version": CONSOLIDATE_WEIGHTS_VERSION,
        "contamination_protected": True,
        "fact_ids": [fact_id],
        "decision": decision,
        "score_output": score_output,
        "consolidate_run_id": run_id,
    }


def promote(
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
    fact_ids: Sequence[str],
    score_outputs: Mapping[str, float],
    decisions: Mapping[str, str],
    run_id: str,
    now: datetime | None = None,
    sink: SinkCallable | None = None,
) -> PhaseResult:
    """Flag a batch of facts as ``tier='promoted'`` (S2 + S5).

    Promote does NOT write S1 (§c — it's an S2-only event). The
    cross-store T2 transaction wraps the ``promotion_flags`` INSERT OR
    REPLACE plus the S5 ``s5_consolidation_log`` append; both COMMIT or
    both ROLLBACK. Events are emitted POST-COMMIT (per A9 — sink failures
    do NOT roll back state).
    """
    _validate_promote_inputs(
        fact_ids=fact_ids,
        score_outputs=score_outputs,
        decisions=decisions,
        run_id=run_id,
    )

    try:
        orphans = reconcile_orphans(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            s1_client=s1_client,
        )
    except BaseException as reconciler_err:
        raise RuntimeError("reconciliation failed; phase did not run") from reconciler_err

    n = now or datetime.now(UTC)
    flag_set_at = _format_iso(n)
    envelopes: list[dict[str, Any]] = [
        _build_promote_event(
            tenant_id=tenant_id,
            fact_id=fid,
            decision=decisions[fid],
            score_output=score_outputs[fid],
            run_id=run_id,
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
                    (tenant_id, fid, "promoted", flag_set_at, run_id, decisions[fid]),
                )
            for envelope in envelopes:
                writer.append_with_conn(
                    LogEntry(
                        kind="promote",
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
