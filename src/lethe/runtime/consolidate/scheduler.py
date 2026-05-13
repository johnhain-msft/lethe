"""Per-tenant consolidate scheduler primitives — gate + lock surface (P4 C7).

Per IMPLEMENT 7 sub-plan §L.1 + amendments A1, A2, A5, A6: scheduler
exposes the four lock primitives + the gate-elapsed predicate that the
consolidate loop (:mod:`lethe.runtime.consolidate.loop`) composes into
one cycle. The 30 s heartbeat / 60 s break / 15 min gate constants are
module-level :class:`Final` literals (deployment §4.1 + §4.2 + gap-01
§3.2 Q3); operator override via ``tenant_config`` lands at P5+.

Surface (per A1's clear/mark_success split):

- :func:`should_run` — cheap pre-acquire hint; returns True when the
  gate has elapsed since ``last_run_at`` (or the row does not exist).
- :func:`acquire_lock` — atomic INSERT-OR-IGNORE + conditional UPDATE
  WHERE; raises :class:`LockAcquisitionFailed` on contention. Writes
  S5 ``kind='lock_acquired'`` audit row inside the same tx (per A6).
- :func:`heartbeat` — UPDATE ``lock_heartbeat_at`` to **fresh**
  ``datetime.now(UTC)`` (per A2); returns ``False`` when our token has
  been broken (rowcount==0). Fail-soft, NOT raise.
- :func:`clear_lock` — release without advancing ``last_run_at``; for
  the failure paths (``phase_failed`` + ``lock_lost``) per A1.
- :func:`mark_success_and_release` — release AND advance
  ``last_run_at``; for the happy-path full 6-phase completion only.
- :func:`force_clear_lock` — admin recovery surface
  (``lethe-admin lock break`` at P5+); writes S5
  ``kind='lock_force_cleared'`` and returns the cleared token.

Per A5: SQLite ``OperationalError("database is locked")`` raised by
``BEGIN IMMEDIATE`` on busy-timeout exhaustion is normalized to
:class:`LockAcquisitionFailed(reason="busy_timeout")` so the loop's
contention path sees one error type, not two.

Per A9 (carry-forward note): in-phase heartbeat is OUT OF SCOPE at C7
— phases at P4 run sub-second. P9 (gap-06 fact extraction) introduces
phases that may exceed :data:`LOCK_BREAK_SECONDS`; those phases MUST
accept a heartbeat callback or run under a daemon-side timer (P7+
deployment scheduler). Carry-forward: B-3 expansion at P7+/P9.
"""

from __future__ import annotations

import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from lethe.store.s5_log.writer import LogEntry, SqliteLogWriter
from lethe.store.shared_conn import shared_store_connection

# Gate cadence + lock-break thresholds (deployment §4.1 + §4.2;
# gap-01 §3.2 Q3). Operator override via ``tenant_config`` is P5+.
GATE_INTERVAL_SECONDS: Final[int] = 15 * 60
HEARTBEAT_INTERVAL_SECONDS: Final[int] = 30
LOCK_BREAK_SECONDS: Final[int] = 60

# Per A5: busy-timeout for ``BEGIN IMMEDIATE`` on the per-tenant S2
# connection. 5000ms matches Python sqlite3's default; setting it
# explicitly here makes the contract visible at the lock seam (the
# shared_store_connection helper does NOT set busy_timeout).
_BUSY_TIMEOUT_MS: Final[int] = 5000


class LockAcquisitionFailed(Exception):
    """Raised by :func:`acquire_lock` when the per-tenant lock cannot be taken.

    ``reason`` distinguishes:

    - ``"lock_held_and_fresh"`` — another holder owns the lock and its
      ``lock_heartbeat_at`` is within the last :data:`LOCK_BREAK_SECONDS`.
      Loop retries on the next gate cycle.
    - ``"busy_timeout"`` — SQLite ``BEGIN IMMEDIATE`` waited up to
      :data:`_BUSY_TIMEOUT_MS` then surfaced ``OperationalError``.
      Per A5 normalization. Loop treats identically to the held case.
    """

    def __init__(self, tenant_id: str, *, reason: str = "lock_held_and_fresh") -> None:
        self.tenant_id = tenant_id
        self.reason = reason
        super().__init__(f"failed to acquire consolidate lock for tenant {tenant_id!r}: {reason}")


def _generate_uuidv7(*, now: datetime) -> str:
    """Random uuidv7 for ``lock_token`` (mirror api/recall.py + promote.py).

    Per IMPLEMENT 6 amendment A8: random uuidv7 (not deterministic).
    Lock tokens MUST be unique across acquires so a stale-broken-lock
    holder's heartbeat / clear_lock cannot accidentally hit the new
    holder's row (the WHERE clause is ``lock_token=?``).
    """
    unix_ts_ms = int(now.astimezone(UTC).timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    msb = (unix_ts_ms << 16) | (0x7 << 12) | rand_a
    lsb = (0b10 << 62) | rand_b
    value = (msb << 64) | lsb
    return str(uuid.UUID(int=value))


def _format_iso(dt: datetime) -> str:
    """RFC 3339 with Z suffix (per IMPLEMENT 6 amendment A11)."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 timestamp accepting both ``Z`` suffix and ``+00:00``.

    The schema's DEFAULT (``strftime('%Y-%m-%dT%H:%M:%fZ','now')``) writes
    Z-suffix; our explicit writes (lock + last_run timestamps) also emit
    Z. ``fromisoformat`` accepted the Z suffix only since Python 3.11 —
    we are on 3.11.14 (toolchain locked at P1) so the call is safe.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def should_run(*, tenant_id: str, tenant_root: Path, now: datetime | None = None) -> bool:
    """Return True iff the gate has elapsed since ``last_run_at`` (or no row).

    Per A2 + §L.2: this is a CHEAP HINT. The conditional UPDATE WHERE in
    :func:`acquire_lock` is the AUTHORITATIVE atomic gate; should_run is
    purely an optimization to avoid even attempting acquire when the
    gate hasn't elapsed.
    """
    n = now if now is not None else datetime.now(UTC)
    with shared_store_connection(tenant_root) as conn:
        cursor = conn.execute(
            "SELECT last_run_at FROM main.consolidation_state WHERE tenant_id = ?",
            (tenant_id,),
        )
        row = cursor.fetchone()
    if row is None or row[0] is None:
        return True
    last_run_at = _parse_iso(row[0])
    return (n - last_run_at).total_seconds() >= GATE_INTERVAL_SECONDS


def acquire_lock(
    *,
    tenant_id: str,
    tenant_root: Path,
    now: datetime | None = None,
) -> str:
    """Acquire the per-tenant consolidate lock; return the new lock_token.

    Per A6: pre-UPDATE SELECT captures ``prior_token`` (None if free,
    non-None if stale-broken) for the S5 audit row. Per A5: SQLite
    ``OperationalError("database is locked")`` is normalized to
    :class:`LockAcquisitionFailed(reason="busy_timeout")`.

    The whole flow runs inside one ``BEGIN IMMEDIATE`` / ``COMMIT``:

    1. ``INSERT OR IGNORE`` row for the tenant (idempotent — extract.py
       at C5 may have already created it).
    2. ``SELECT lock_token`` to capture ``prior_token``.
    3. ``UPDATE ... WHERE (lock_token IS NULL OR lock_heartbeat_at < ?)``
       — atomic compare-and-swap. ``rowcount == 0`` means the lock is
       held + fresh (raise).
    4. ``writer.append_with_conn(LogEntry(kind='lock_acquired', ...))``
       inside the same tx so the S5 audit row commits with the lock
       state.
    5. ``COMMIT``.
    """
    n = now if now is not None else datetime.now(UTC)
    new_token = _generate_uuidv7(now=n)
    now_str = _format_iso(n)
    stale_threshold_str = _format_iso(n - timedelta(seconds=LOCK_BREAK_SECONDS))
    writer = SqliteLogWriter(tenant_root)

    with shared_store_connection(tenant_root) as conn:
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as begin_err:
            if "locked" in str(begin_err).lower():
                raise LockAcquisitionFailed(tenant_id, reason="busy_timeout") from begin_err
            raise
        try:
            conn.execute(
                "INSERT OR IGNORE INTO main.consolidation_state(tenant_id) VALUES (?)",
                (tenant_id,),
            )
            prior_row = conn.execute(
                "SELECT lock_token FROM main.consolidation_state WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            prior_token: str | None = prior_row[0] if prior_row is not None else None

            cursor = conn.execute(
                "UPDATE main.consolidation_state "
                "SET lock_token = ?, lock_acquired_at = ?, lock_heartbeat_at = ?, "
                "    updated_at = ? "
                "WHERE tenant_id = ? "
                "  AND (lock_token IS NULL OR lock_heartbeat_at < ?)",
                (new_token, now_str, now_str, now_str, tenant_id, stale_threshold_str),
            )
            if cursor.rowcount == 0:
                conn.execute("ROLLBACK")
                raise LockAcquisitionFailed(tenant_id, reason="lock_held_and_fresh")

            writer.append_with_conn(
                LogEntry(
                    kind="lock_acquired",
                    payload={
                        "tenant_id": tenant_id,
                        "lock_token": new_token,
                        "prior_token": prior_token,
                        "now": now_str,
                    },
                ),
                conn=conn,
            )
            conn.execute("COMMIT")
        except LockAcquisitionFailed:
            raise
        except BaseException:
            conn.execute("ROLLBACK")
            raise

    return new_token


def heartbeat(
    *,
    tenant_id: str,
    tenant_root: Path,
    lock_token: str,
    now: datetime | None = None,
) -> bool:
    """Extend our hold on the lock; return False if our token was broken.

    Per A2: when ``now`` is None (default), capture
    ``datetime.now(UTC)`` INSIDE this function so each call advances
    ``lock_heartbeat_at`` to a fresh time. Tests inject explicit ``now``
    for deterministic advancement assertions.

    Per A5: ``False`` (NOT raise) on rowcount==0 so the loop can
    compose ``if not heartbeat(): break`` cleanly. Mirrors C6 A9 sink-
    failure pattern (collect failures, don't raise on best-effort
    surfaces).
    """
    n = now if now is not None else datetime.now(UTC)
    now_str = _format_iso(n)
    with shared_store_connection(tenant_root) as conn:
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE main.consolidation_state "
                "SET lock_heartbeat_at = ?, updated_at = ? "
                "WHERE tenant_id = ? AND lock_token = ?",
                (now_str, now_str, tenant_id, lock_token),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return cursor.rowcount == 1


def clear_lock(
    *,
    tenant_id: str,
    tenant_root: Path,
    lock_token: str,
    now: datetime | None = None,
) -> bool:
    """Release the lock without advancing ``last_run_at`` (per A1).

    For the failure paths: ``phase_failed`` + ``lock_lost``. The next
    consolidate cycle's ``should_run`` check sees the unchanged
    ``last_run_at`` and the gate elapses on the original cadence — so a
    failed cycle does NOT suppress retries for 15 minutes (which would
    mask the ``consolidation_stalled`` alarm at deployment §5.5).

    Idempotent: ``rowcount == 0`` (token mismatch — e.g., another
    process has already broken the lock) is fail-soft (returns False).
    """
    n = now if now is not None else datetime.now(UTC)
    now_str = _format_iso(n)
    with shared_store_connection(tenant_root) as conn:
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE main.consolidation_state "
                "SET lock_token = NULL, lock_acquired_at = NULL, "
                "    lock_heartbeat_at = NULL, updated_at = ? "
                "WHERE tenant_id = ? AND lock_token = ?",
                (now_str, tenant_id, lock_token),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return cursor.rowcount == 1


def mark_success_and_release(
    *,
    tenant_id: str,
    tenant_root: Path,
    lock_token: str,
    now: datetime | None = None,
) -> bool:
    """Release the lock AND advance ``last_run_at`` (per A1).

    For the happy-path full 6-phase completion only. Setting
    ``last_run_at`` here makes the next ``should_run`` check see the
    fresh value and skip until ``GATE_INTERVAL_SECONDS`` elapses.
    """
    n = now if now is not None else datetime.now(UTC)
    now_str = _format_iso(n)
    with shared_store_connection(tenant_root) as conn:
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE main.consolidation_state "
                "SET lock_token = NULL, lock_acquired_at = NULL, "
                "    lock_heartbeat_at = NULL, "
                "    last_run_at = ?, updated_at = ? "
                "WHERE tenant_id = ? AND lock_token = ?",
                (now_str, now_str, tenant_id, lock_token),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return cursor.rowcount == 1


def force_clear_lock(
    *,
    tenant_id: str,
    tenant_root: Path,
    now: datetime | None = None,
) -> str | None:
    """Admin-side lock recovery: NULL the lock without acquiring; return prior token.

    Surface for ``lethe-admin lock break --reason=...`` (deployment
    §8.3); the CLI surface lands at P5+. At C7 the function is
    callable from Python (tests + future CLI). Always writes S5
    ``kind='lock_force_cleared'`` (with ``prior_token`` field
    populated, ``null`` if the lock was already free) so the audit
    trail is complete.
    """
    n = now if now is not None else datetime.now(UTC)
    now_str = _format_iso(n)
    writer = SqliteLogWriter(tenant_root)

    with shared_store_connection(tenant_root) as conn:
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO main.consolidation_state(tenant_id) VALUES (?)",
                (tenant_id,),
            )
            prior_row = conn.execute(
                "SELECT lock_token FROM main.consolidation_state WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            prior_token: str | None = prior_row[0] if prior_row is not None else None

            conn.execute(
                "UPDATE main.consolidation_state "
                "SET lock_token = NULL, lock_acquired_at = NULL, "
                "    lock_heartbeat_at = NULL, updated_at = ? "
                "WHERE tenant_id = ?",
                (now_str, tenant_id),
            )
            writer.append_with_conn(
                LogEntry(
                    kind="lock_force_cleared",
                    payload={
                        "tenant_id": tenant_id,
                        "prior_token": prior_token,
                        "now": now_str,
                    },
                ),
                conn=conn,
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return prior_token
