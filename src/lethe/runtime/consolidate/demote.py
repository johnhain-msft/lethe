"""Demote phase — write S1 ``valid_to`` + flag ``tier='demoted'`` (P4 commit 6).

Per scoring §3.6 + §6 + §8.1 + IMPL §2.4 invariant I-11. Demote is the
first of the two C6 phases that writes S1 (``valid_to`` end-of-validity
stamp; the bi-temporal supersession lives on S1 per composition §1
row 48 + QA-G1 §B.6). The S2-side flag (``tier='demoted'``) + the S5
audit entry pin the verb-side semantics (which run + which decision
drove the demotion) so the read-side aggregator can replay history.

S1-FIRST + RECONCILER ORDERING (per §k.6 + composition §5 row 7):

The phase writes S1 BEFORE the S2 + S5 transaction. If the S2 + S5 tx
succeeds after S1 commit, both sides agree. If the S2 + S5 tx fails
after S1 commit, S1 is left with ``valid_to`` set but no covering
``promotion_flags`` row — the next consolidate run's reconciler
(:func:`._reconciler.reconcile_orphans`) detects the orphan via
:meth:`S1Client.iter_facts_with_valid_to` and writes a
``tier='backfilled', flag_set_by='reconciler'`` row + S5 entry. This
inverted ordering (S1 before S2) is deliberate: an unrecorded S1
change is recoverable by reconciliation; an S2 + S5 record without a
matching S1 change is corruption.

PARTIAL S1-WRITE FAILURE INVARIANT (per IMPLEMENT 6 amendment A4):

The S1 writes happen in a per-fact loop BEFORE ``BEGIN IMMEDIATE``.
On partial S1-write failure (success on prefix ``[a, b]``, failure on
``c``), no S2/S5/event writes occur — the function raises before
``BEGIN IMMEDIATE``. Facts ``a`` and ``b`` are left as S1 orphans
(``valid_to`` set, no ``promotion_flags`` row). The next reconciler
pass backfills ``tier='backfilled'`` rows for ``a`` and ``b``.
Composition §5 row 7 governs the ledger reconciliation path.

PER A8: ``event_id`` is RANDOM uuidv7 (not deterministic). The
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

# Per IMPLEMENT 6 §k.4: the verb-side enum that bounds the ``decision``
# field on ``demote`` events. Phase code rejects any value not in this
# set BEFORE the S1 write (gate 16) — gives a clearer error than waiting
# for a downstream consumer to choke. See §k.4 / B-3 for derivation
# (scoring §3.6 floor + §6.3 purge-after-grace).
DEMOTE_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "score_below_theta_demote",
        "score_below_theta_purge",
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


def _validate_demote_inputs(
    *,
    fact_ids: Sequence[str],
    score_outputs: Mapping[str, float],
    decisions: Mapping[str, str],
    run_id: str,
    valid_to: str,
) -> None:
    """Per IMPLEMENT 6 amendment A5 — preflight all pure validation.

    Raises :class:`ValueError` with a specific message naming the
    offending field or fact_id. Tests assert the exact messages.
    """
    if not run_id:
        raise ValueError("demote: run_id must be a non-empty string")
    if not valid_to:
        raise ValueError("demote: valid_to must be a non-empty RFC 3339 string")
    try:
        datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"demote: valid_to {valid_to!r} is not a parseable RFC 3339 timestamp"
        ) from exc
    for fid in fact_ids:
        if fid not in score_outputs:
            raise ValueError(f"demote: fact_id {fid!r} missing from score_outputs")
        if fid not in decisions:
            raise ValueError(f"demote: fact_id {fid!r} missing from decisions")
        decision = decisions[fid]
        if decision not in DEMOTE_DECISIONS:
            raise ValueError(
                f"demote: decision {decision!r} for fact_id {fid!r} not in "
                f"DEMOTE_DECISIONS={sorted(DEMOTE_DECISIONS)}"
            )


def _build_demote_event(
    *,
    tenant_id: str,
    fact_id: str,
    decision: str,
    score_output: float,
    run_id: str,
    valid_to: str,
    now: datetime,
) -> dict[str, Any]:
    """Build a scoring §8.2 demote envelope (per IMPLEMENT 6 §k.10)."""
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "demote",
        "tenant_id": tenant_id,
        "ts_recorded": _format_iso(now),
        "ts_valid": valid_to,
        "model_version": CONSOLIDATE_MODEL_VERSION,
        "weights_version": CONSOLIDATE_WEIGHTS_VERSION,
        "contamination_protected": True,
        "fact_ids": [fact_id],
        "decision": decision,
        "score_output": score_output,
        "consolidate_run_id": run_id,
    }


def demote(
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
    fact_ids: Sequence[str],
    score_outputs: Mapping[str, float],
    decisions: Mapping[str, str],
    run_id: str,
    valid_to: str,
    now: datetime | None = None,
    sink: SinkCallable | None = None,
) -> PhaseResult:
    """Set ``valid_to`` on a batch of S1 facts + flag ``tier='demoted'``.

    Phase order (per §k.6):

    1. Preflight (raises :class:`ValueError` on caller errors).
    2. Reconciler (own tx; backfills any prior S1 orphans).
    3. S1 writes per-fact in a loop (S1-first ordering).
    4. S2 + S5 writes in a single ``BEGIN IMMEDIATE`` / ``COMMIT`` tx.
    5. Post-commit emit per envelope (sink failures collected, not
       raised — see :class:`PhaseResult`).
    """
    _validate_demote_inputs(
        fact_ids=fact_ids,
        score_outputs=score_outputs,
        decisions=decisions,
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
        _build_demote_event(
            tenant_id=tenant_id,
            fact_id=fid,
            decision=decisions[fid],
            score_output=score_outputs[fid],
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
                    (tenant_id, fid, "demoted", flag_set_at, run_id, decisions[fid]),
                )
            for envelope in envelopes:
                writer.append_with_conn(
                    LogEntry(
                        kind="demote",
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
