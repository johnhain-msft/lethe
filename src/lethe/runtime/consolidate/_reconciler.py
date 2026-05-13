"""Reconciler helper + shared phase scaffolding (P4 commit 6).

Houses two related pieces of phase infrastructure that all three C6
modules (:mod:`promote`, :mod:`demote`, :mod:`invalidate`) consume:

1. :func:`reconcile_orphans` — the composition §5 row 7 backfill pass.
   Per IMPLEMENT 6 amendment A7, this opens its OWN
   :func:`~lethe.store.shared_conn.shared_store_connection` and runs in
   its OWN ``BEGIN IMMEDIATE`` / ``COMMIT`` transaction (so backfill
   rows are durable independently of the calling phase's main work).
   Per A2, an "orphan" is an S1 fact with ``valid_to ≠ NULL`` AND no
   covering ``promotion_flags`` row of tier ∈ {``demoted``,
   ``invalidated``, ``backfilled``}; the ``backfilled`` tier is part of
   the covered set so the reconciler is idempotent (running it twice
   does NOT produce duplicate backfill rows or duplicate S5 entries).
2. :class:`PhaseResult` — the frozen-dataclass return type for
   :func:`promote`, :func:`demote`, and :func:`invalidate`. Per A9, it
   carries ``committed_fact_ids`` (always the input ``fact_ids`` if the
   tx COMMITs), ``sink_failures`` (any post-commit ``emit()`` errors —
   state survives), and ``orphans_backfilled`` (the reconciler return,
   passed through for caller logging).

Co-located rather than split into a new ``_phase_result.py`` because the
§k.12 binding scope is exactly 9 paths; both pieces are infrastructure
shared by the three phase modules and naturally belong in the
"phase scaffolding" file. The leading-underscore module name flags
"phase-internal — not part of the public consolidate API".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from lethe.store.s1_graph.client import S1Client
from lethe.store.s5_log.writer import LogEntry, SqliteLogWriter
from lethe.store.shared_conn import shared_store_connection

# Per A2: tiers that "cover" an S1 valid_to set — the reconciler does
# NOT backfill if a promotion_flags row of any of these tiers exists.
# 'backfilled' is in the set so the reconciler is idempotent across
# runs (otherwise the second run would re-backfill every fact a first
# run already backfilled, blowing up S5 with duplicates).
_TIERS_COVERING_VALID_TO: Final[tuple[str, ...]] = (
    "demoted",
    "invalidated",
    "backfilled",
)


@dataclass(frozen=True)
class PhaseResult:
    """Return value of :func:`promote`, :func:`demote`, :func:`invalidate`.

    Per IMPLEMENT 6 amendment A9:

    - ``committed_fact_ids`` — the ``fact_ids`` whose S2 + S5 writes
      COMMITted (always the input fact_ids when the phase returns
      successfully; if the tx ROLLBACKed the phase raises and there is
      no PhaseResult).
    - ``sink_failures`` — list of ``(event_id, exception)`` pairs for
      events whose post-commit :func:`~lethe.runtime.events.emit`
      raised. Per gap-08 + composition §5 row 7, post-commit sink
      failure does NOT roll back the state; the sink is best-effort
      and a transient outage doesn't tear durable state. The C7 loop
      inspects this field to surface metrics-egress failures without
      retriggering the phase.
    - ``orphans_backfilled`` — the fact_ids the reconciler backfilled
      (composition §5 row 7) at the start of this phase. Empty in the
      common case; non-empty when a prior phase left S1 ahead of S2.
    """

    committed_fact_ids: tuple[str, ...]
    sink_failures: tuple[tuple[str, Exception], ...]
    orphans_backfilled: tuple[str, ...]


def _format_iso(dt: datetime) -> str:
    """RFC 3339 with the ``Z`` suffix (per IMPLEMENT 6 amendment A11)."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def reconcile_orphans(
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
) -> list[str]:
    """Backfill ``promotion_flags`` + S5 entries for S1 valid_to orphans.

    Reads the S1 fact set via
    :meth:`S1Client.iter_facts_with_valid_to`, then opens its own
    :func:`shared_store_connection` + ``BEGIN IMMEDIATE`` / ``COMMIT``
    block to query ``main.promotion_flags`` for covered fact_ids and
    backfill the rest. Returns the list of orphan fact_ids backfilled
    (sorted ASC for caller-side determinism); empty list when no
    orphans exist or when S1 has no facts with ``valid_to ≠ NULL``.

    Idempotency (per A2): the second run sees the first run's
    ``tier='backfilled'`` rows and skips them — orphan set is
    ``S1_with_valid_to \\\\ promotion_flags{demoted,invalidated,backfilled}``.

    Tx semantics (per A7): the reconciler owns its own connection +
    BEGIN IMMEDIATE. If it raises mid-way, ROLLBACK reverts any partial
    backfills; the caller catches and re-raises as a
    ``RuntimeError("reconciliation failed; phase did not run")`` so
    no S1/S2 phase writes occur after a reconciler failure.
    """
    s1_facts = list(s1_client.iter_facts_with_valid_to())
    if not s1_facts:
        return []

    s1_fact_ids = sorted({f.fact_id for f in s1_facts})

    writer = SqliteLogWriter(tenant_root)
    with shared_store_connection(tenant_root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            placeholders_fid = ",".join("?" * len(s1_fact_ids))
            placeholders_tier = ",".join("?" * len(_TIERS_COVERING_VALID_TO))
            cur = conn.execute(
                f"SELECT fact_id FROM main.promotion_flags "
                f"WHERE tenant_id = ? "
                f"AND fact_id IN ({placeholders_fid}) "
                f"AND tier IN ({placeholders_tier})",
                (tenant_id, *s1_fact_ids, *_TIERS_COVERING_VALID_TO),
            )
            covered = {row[0] for row in cur.fetchall()}
            orphans = [fid for fid in s1_fact_ids if fid not in covered]

            if not orphans:
                conn.execute("COMMIT")
                return []

            now_iso = _format_iso(datetime.now(UTC))
            for fid in orphans:
                conn.execute(
                    "INSERT OR REPLACE INTO main.promotion_flags "
                    "(tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (tenant_id, fid, "backfilled", now_iso, "reconciler", "s1_state_diff"),
                )
                writer.append_with_conn(
                    LogEntry(
                        kind="reconciler",
                        payload={
                            "tenant_id": tenant_id,
                            "fact_id": fid,
                            "tier": "backfilled",
                            "reason": "s1_state_diff",
                        },
                    ),
                    conn=conn,
                )
            conn.execute("COMMIT")
            return orphans
        except BaseException:
            conn.execute("ROLLBACK")
            raise
