"""Per-tenant lock + scheduler primitive tests for P4 commit 7.

Covers all scheduler.py surfaces (acquire / heartbeat / clear /
mark_success_and_release / force_clear / should_run) including all
IMPLEMENT 7 amendment-specific assertions:

- A1 split: clear_lock does NOT advance ``last_run_at``;
  mark_success_and_release does.
- A2: heartbeat captures fresh ``datetime.now(UTC)`` per call when
  ``now`` is not passed → ``lock_heartbeat_at`` strictly advances
  across successive calls.
- A5: SQLite ``OperationalError("database is locked")`` on
  ``BEGIN IMMEDIATE`` is normalized to
  :class:`LockAcquisitionFailed(reason="busy_timeout")`.
- A6: S5 ``kind='lock_acquired'`` audit row records ``prior_token``
  (None on first acquire; non-None on stale-lock takeover).
- A6: S5 ``kind='lock_force_cleared'`` audit row records
  ``prior_token`` (held lock) or None (free lock).

Standing reminders honored: LETHE_HOME isolation via the conftest
``lethe_home`` fixture, no new deps.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from lethe.runtime import bootstrap
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
from lethe.store import shared_store_connection
from lethe.store.s2_meta.schema import S5_LOG_TABLE_NAME

TENANT = "smoke-tenant"


def _bootstrap(lethe_home: Path) -> Path:
    bootstrap(tenant_id=TENANT, storage_root=lethe_home)
    return lethe_home / "tenants" / TENANT


def _consolidation_state_row(tenant_root: Path) -> dict[str, Any] | None:
    with shared_store_connection(tenant_root) as conn:
        cursor = conn.execute(
            "SELECT tenant_id, lock_token, lock_acquired_at, lock_heartbeat_at, "
            "       last_run_at, created_at, updated_at "
            "FROM main.consolidation_state WHERE tenant_id = ?",
            (TENANT,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "tenant_id": row[0],
        "lock_token": row[1],
        "lock_acquired_at": row[2],
        "lock_heartbeat_at": row[3],
        "last_run_at": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


def _s5_rows_of_kind(tenant_root: Path, kind: str) -> list[dict[str, Any]]:
    with shared_store_connection(tenant_root) as conn:
        cursor = conn.execute(
            f"SELECT kind, payload_json, appended_at "
            f"FROM main.{S5_LOG_TABLE_NAME} WHERE kind = ? ORDER BY seq ASC",
            (kind,),
        )
        rows = [
            {"kind": r[0], "payload": json.loads(r[1]), "appended_at": r[2]}
            for r in cursor.fetchall()
        ]
    return rows


# ---------- gate constants smoke ---------- #


def test_gate_constants_match_deployment_defaults() -> None:
    """deployment §4.1 + §4.2 + gap-01 §3.2 Q3."""
    assert GATE_INTERVAL_SECONDS == 15 * 60
    assert HEARTBEAT_INTERVAL_SECONDS == 30
    assert LOCK_BREAK_SECONDS == 60


# ---------- should_run gate ---------- #


def test_should_run_true_for_unbootstrapped_tenant_state(lethe_home: Path) -> None:
    """No row in consolidation_state → True (first run)."""
    tenant_root = _bootstrap(lethe_home)
    assert should_run(tenant_id=TENANT, tenant_root=tenant_root) is True


def test_should_run_false_before_gate_elapsed(lethe_home: Path) -> None:
    """last_run_at < gate ago → False."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    mark_success_and_release(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token=token,
        now=base_now,
    )
    one_minute_later = base_now + timedelta(seconds=60)
    assert should_run(tenant_id=TENANT, tenant_root=tenant_root, now=one_minute_later) is False


def test_should_run_true_after_gate_elapsed(lethe_home: Path) -> None:
    """last_run_at + gate elapsed → True."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    mark_success_and_release(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token=token,
        now=base_now,
    )
    after_gate = base_now + timedelta(seconds=GATE_INTERVAL_SECONDS + 1)
    assert should_run(tenant_id=TENANT, tenant_root=tenant_root, now=after_gate) is True


# ---------- acquire happy path + audit ---------- #


def test_acquire_returns_random_uuidv7_token(lethe_home: Path) -> None:
    """Token is a uuidv7 string (version nibble at index 14 == '7')."""
    tenant_root = _bootstrap(lethe_home)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root)
    assert isinstance(token, str)
    assert len(token) == 36
    assert token[14] == "7"


def test_acquire_writes_lock_columns_with_z_suffix(lethe_home: Path) -> None:
    """Lock acquire populates lock_token + lock_acquired_at + lock_heartbeat_at; ts use Z."""
    tenant_root = _bootstrap(lethe_home)
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=fixed_now)
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] == token
    assert row["lock_acquired_at"] == "2026-06-01T12:00:00Z"
    assert row["lock_heartbeat_at"] == "2026-06-01T12:00:00Z"
    assert row["last_run_at"] is None  # acquire does NOT advance last_run_at


def test_acquire_audit_records_null_prior_token_on_first_acquire(
    lethe_home: Path,
) -> None:
    """A6: first acquire writes S5 'lock_acquired' with prior_token=None."""
    tenant_root = _bootstrap(lethe_home)
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=fixed_now)
    rows = _s5_rows_of_kind(tenant_root, "lock_acquired")
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["tenant_id"] == TENANT
    assert payload["lock_token"] == token
    assert payload["prior_token"] is None
    assert payload["now"] == "2026-06-01T12:00:00Z"


def test_acquire_audit_records_prior_token_when_stale_broken(lethe_home: Path) -> None:
    """A6: stale-lock takeover writes S5 'lock_acquired' with prior_token populated."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    first_token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    # Second acquire from a "different process" after stale threshold elapses
    # — heartbeat_at < (now - LOCK_BREAK_SECONDS) lets the WHERE clause match.
    after_stale = base_now + timedelta(seconds=LOCK_BREAK_SECONDS + 1)
    second_token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=after_stale)
    assert second_token != first_token

    rows = _s5_rows_of_kind(tenant_root, "lock_acquired")
    assert len(rows) == 2
    assert rows[0]["payload"]["prior_token"] is None
    assert rows[1]["payload"]["prior_token"] == first_token


# ---------- acquire contention ---------- #


def test_acquire_raises_lock_acquisition_failed_when_held_and_fresh(
    lethe_home: Path,
) -> None:
    """Two acquires in quick succession: second raises LockAcquisitionFailed."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    with pytest.raises(LockAcquisitionFailed) as excinfo:
        acquire_lock(
            tenant_id=TENANT,
            tenant_root=tenant_root,
            now=base_now + timedelta(seconds=10),
        )
    assert excinfo.value.tenant_id == TENANT
    assert excinfo.value.reason == "lock_held_and_fresh"


def test_concurrent_acquire_only_one_succeeds(lethe_home: Path) -> None:
    """Sequential acquire calls: first succeeds; second raises LockAcquisitionFailed."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token_a = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    with pytest.raises(LockAcquisitionFailed):
        acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    # First holder still owns the lock
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] == token_a


def test_acquire_breaks_stale_heartbeat(lethe_home: Path) -> None:
    """Lock with heartbeat_at older than LOCK_BREAK_SECONDS → next acquire succeeds."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    first_token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    # Sanity: a fresh second acquire fails
    with pytest.raises(LockAcquisitionFailed):
        acquire_lock(
            tenant_id=TENANT,
            tenant_root=tenant_root,
            now=base_now + timedelta(seconds=10),
        )
    # After stale threshold the second acquire succeeds
    after_stale = base_now + timedelta(seconds=LOCK_BREAK_SECONDS + 1)
    second_token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=after_stale)
    assert second_token != first_token
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] == second_token


def test_acquire_normalizes_sqlite_busy_to_lock_acquisition_failed(
    lethe_home: Path,
) -> None:
    """A5: ``OperationalError("database is locked")`` → LockAcquisitionFailed(busy_timeout)."""
    tenant_root = _bootstrap(lethe_home)

    # sqlite3.Connection.execute is read-only on the C object; build a
    # proxy that delegates everything to the real connection but raises
    # OperationalError on ``BEGIN IMMEDIATE``.
    class _RaisingProxy:
        def __init__(self, real: sqlite3.Connection) -> None:
            self._real = real

        def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
            if sql.strip().upper().startswith("BEGIN IMMEDIATE"):
                raise sqlite3.OperationalError("database is locked")
            return self._real.execute(sql, *args)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._real, name)

    @contextmanager
    def _failing_shared_conn(_tenant_root: Path) -> Iterator[object]:
        with shared_store_connection(_tenant_root) as real_conn:
            yield _RaisingProxy(real_conn)

    with (
        mock.patch(
            "lethe.runtime.consolidate.scheduler.shared_store_connection",
            _failing_shared_conn,
        ),
        pytest.raises(LockAcquisitionFailed) as excinfo,
    ):
        acquire_lock(tenant_id=TENANT, tenant_root=tenant_root)
    assert excinfo.value.reason == "busy_timeout"


# ---------- heartbeat ---------- #


def test_heartbeat_returns_true_when_we_hold_the_lock(lethe_home: Path) -> None:
    """heartbeat advances lock_heartbeat_at + returns True when our token matches."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    later = base_now + timedelta(seconds=15)
    ok = heartbeat(tenant_id=TENANT, tenant_root=tenant_root, lock_token=token, now=later)
    assert ok is True
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_heartbeat_at"] == "2026-06-01T12:00:15Z"


def test_heartbeat_advances_lock_heartbeat_at_on_each_call(lethe_home: Path) -> None:
    """A2: each heartbeat advances ``lock_heartbeat_at`` (fresh time per call)."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    timestamps: list[str] = []
    for offset in (5, 10, 20):
        heartbeat(
            tenant_id=TENANT,
            tenant_root=tenant_root,
            lock_token=token,
            now=base_now + timedelta(seconds=offset),
        )
        row = _consolidation_state_row(tenant_root)
        assert row is not None
        timestamps.append(str(row["lock_heartbeat_at"]))
    # Strictly increasing → fresh time captured per call
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == 3


def test_heartbeat_returns_false_after_force_clear(lethe_home: Path) -> None:
    """heartbeat returns False (NOT raise) when our token has been broken."""
    tenant_root = _bootstrap(lethe_home)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root)
    force_clear_lock(tenant_id=TENANT, tenant_root=tenant_root)
    ok = heartbeat(tenant_id=TENANT, tenant_root=tenant_root, lock_token=token)
    assert ok is False


def test_heartbeat_returns_false_when_token_does_not_match(lethe_home: Path) -> None:
    """heartbeat with a foreign token returns False."""
    tenant_root = _bootstrap(lethe_home)
    acquire_lock(tenant_id=TENANT, tenant_root=tenant_root)
    ok = heartbeat(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token="01000000-0000-7000-8000-000000000000",
    )
    assert ok is False


# ---------- clear_lock (A1: NO last_run_at advance) ---------- #


def test_clear_lock_releases_lock_without_advancing_last_run_at(
    lethe_home: Path,
) -> None:
    """A1: clear_lock NULLs lock columns; last_run_at remains NULL/unchanged."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    pre_row = _consolidation_state_row(tenant_root)
    assert pre_row is not None
    pre_last_run_at = pre_row["last_run_at"]

    ok = clear_lock(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token=token,
        now=base_now + timedelta(seconds=5),
    )
    assert ok is True
    post_row = _consolidation_state_row(tenant_root)
    assert post_row is not None
    assert post_row["lock_token"] is None
    assert post_row["lock_acquired_at"] is None
    assert post_row["lock_heartbeat_at"] is None
    # CRITICAL: last_run_at unchanged so the next gate cycle elapses normally
    assert post_row["last_run_at"] == pre_last_run_at


def test_clear_lock_idempotent_when_token_does_not_match(lethe_home: Path) -> None:
    """Stale token → False (NOT raise); table state unchanged."""
    tenant_root = _bootstrap(lethe_home)
    acquire_lock(tenant_id=TENANT, tenant_root=tenant_root)
    ok = clear_lock(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token="01000000-0000-7000-8000-000000000000",
    )
    assert ok is False


# ---------- mark_success_and_release (A1: advances last_run_at) ---------- #


def test_mark_success_and_release_advances_last_run_at(lethe_home: Path) -> None:
    """A1: mark_success_and_release sets last_run_at + clears lock."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    later = base_now + timedelta(seconds=30)
    ok = mark_success_and_release(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        lock_token=token,
        now=later,
    )
    assert ok is True
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] is None
    assert row["last_run_at"] == "2026-06-01T12:00:30Z"


# ---------- force_clear_lock + S5 audit ---------- #


def test_force_clear_lock_returns_prior_token_when_held(lethe_home: Path) -> None:
    """force_clear on a held lock returns the prior token + writes S5."""
    tenant_root = _bootstrap(lethe_home)
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    held_token = acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=fixed_now)
    cleared = force_clear_lock(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        now=fixed_now + timedelta(seconds=5),
    )
    assert cleared == held_token

    rows = _s5_rows_of_kind(tenant_root, "lock_force_cleared")
    assert len(rows) == 1
    assert rows[0]["payload"]["prior_token"] == held_token
    assert rows[0]["payload"]["now"] == "2026-06-01T12:00:05Z"


def test_force_clear_lock_returns_none_when_already_free(lethe_home: Path) -> None:
    """force_clear on a free lock returns None + still writes S5 audit."""
    tenant_root = _bootstrap(lethe_home)
    cleared = force_clear_lock(tenant_id=TENANT, tenant_root=tenant_root)
    assert cleared is None
    rows = _s5_rows_of_kind(tenant_root, "lock_force_cleared")
    assert len(rows) == 1
    assert rows[0]["payload"]["prior_token"] is None


def test_force_cleared_lock_immediately_reacquirable(lethe_home: Path) -> None:
    """After force_clear, a fresh acquire succeeds."""
    tenant_root = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=base_now)
    force_clear_lock(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        now=base_now + timedelta(seconds=2),
    )
    new_token = acquire_lock(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        now=base_now + timedelta(seconds=3),
    )
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] == new_token
