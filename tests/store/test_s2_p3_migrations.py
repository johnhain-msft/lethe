"""S2 P3 migration round-trip: ``recall_ledger`` columns (schema v3).

Mirrors the layout of ``test_s2_p2_migrations.py``:

- A fresh ``S2Schema.create()`` lands at the latest schema version (v3) and
  the ``recall_ledger`` table exposes the column shape from facilitator P3
  plan §(d).
- A simulated v2-shaped database (stub ``(id, created_at)`` for
  ``recall_ledger``; ``schema_version='2'``) is ratcheted to v3 by
  :func:`apply_pending`, and re-running :func:`apply_pending` after that
  is a no-op.
- A fresh DB at v3 is also a no-op for :func:`apply_pending`.
- ``recall_ledger`` accepts the canonical row shape the recall verb writes
  (8 caller-supplied columns + auto ``created_at``).
- ``recall_id`` is the PRIMARY KEY: a duplicate insert without
  ``OR IGNORE`` raises an integrity error.
- ``_STUB_TABLES`` no longer includes ``recall_ledger`` (commit-3 contract).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lethe.store.s2_meta import S2Schema
from lethe.store.s2_meta.migrations import (
    LATEST_SCHEMA_VERSION,
    apply_pending,
    current_version,
)
from lethe.store.s2_meta.schema import _STUB_TABLES


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# Facilitator P3 plan §(d): recall_ledger columns.
_EXPECTED_RECALL_LEDGER_COLUMNS: frozenset[str] = frozenset(
    {
        "recall_id",
        "tenant_id",
        "query_hash",
        "ts_recorded",
        "classified_intent",
        "weights_version",
        "top_k_fact_ids",
        "response_envelope_blob",
        "created_at",
    }
)


def test_latest_schema_version_is_at_least_3() -> None:
    """P3 sanity-pin: the recall_ledger v3 ratchet has shipped (commit-3
    contract). The exact LATEST may have moved past 3 as later phases
    column more tables (P4+); the contract this test guards is that v3 is
    now baked in. ``test_migrations_v3_to_v4`` (and any future
    ``test_migrations_vN_to_vN+1``) owns the exact-LATEST tripwire.
    """
    assert LATEST_SCHEMA_VERSION >= 3


def test_stub_tables_no_longer_include_recall_ledger() -> None:
    """Commit-3 contract: recall_ledger leaves the stub set."""
    assert "recall_ledger" not in _STUB_TABLES


def test_fresh_create_carries_recall_ledger_columns(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 3
        cols = _columns(conn, "recall_ledger")
        assert _EXPECTED_RECALL_LEDGER_COLUMNS.issubset(cols), (
            f"missing: {_EXPECTED_RECALL_LEDGER_COLUMNS - cols}"
        )
    finally:
        conn.close()


def test_recall_ledger_accepts_verb_row_shape(tenant_root: Path) -> None:
    """Insert one row mirroring the recall verb's INSERT signature."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO recall_ledger("
            " recall_id, tenant_id, query_hash, ts_recorded, classified_intent,"
            " weights_version, top_k_fact_ids, response_envelope_blob"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "01234567-89ab-7def-8123-456789abcdef",
                "tenant-a",
                "0123456789abcdef",
                "2025-06-01T12:34:56.789Z",
                "lookup",
                "p3-gap03-5a-v0",
                '["ep-1","ep-2"]',
                b'{"recall_id":"...","facts":[]}',
            ),
        )
        row = conn.execute(
            "SELECT recall_id, tenant_id, classified_intent, weights_version FROM recall_ledger"
        ).fetchone()
        assert row == (
            "01234567-89ab-7def-8123-456789abcdef",
            "tenant-a",
            "lookup",
            "p3-gap03-5a-v0",
        )
    finally:
        conn.close()


def test_recall_ledger_pk_collision_raises_without_ignore(tenant_root: Path) -> None:
    """``recall_id`` is PRIMARY KEY: raw duplicate insert raises."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        row = (
            "01234567-89ab-7def-8123-456789abcdef",
            "tenant-a",
            "0123456789abcdef",
            "2025-06-01T12:34:56.789Z",
            "lookup",
            "p3-gap03-5a-v0",
            "[]",
            b"{}",
        )
        conn.execute(
            "INSERT INTO recall_ledger("
            " recall_id, tenant_id, query_hash, ts_recorded, classified_intent,"
            " weights_version, top_k_fact_ids, response_envelope_blob"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO recall_ledger("
                " recall_id, tenant_id, query_hash, ts_recorded, classified_intent,"
                " weights_version, top_k_fact_ids, response_envelope_blob"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    finally:
        conn.close()


def _bootstrap_v2_database(tenant_root: Path) -> Path:
    """Create a v2-shaped S2 database: ``recall_ledger`` is a stub.

    Mirrors the literal P2 schema by hand so this migration test does
    not depend on git-historical schema.py behavior. Only the table that
    changes at v3 needs to match the v2 shape exactly; other tables can
    be omitted.
    """
    db_path = tenant_root / "s2_meta.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE _lethe_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO _lethe_meta(key, value) VALUES ('schema_version','2')")
    # P1/P2 stub shape for recall_ledger (id + created_at only).
    conn.execute(
        "CREATE TABLE recall_ledger ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        ")"
    )
    conn.close()
    return db_path


def test_v2_database_ratchets_to_v3(tenant_root: Path) -> None:
    db_path = _bootstrap_v2_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        assert current_version(conn) == 2
        assert _columns(conn, "recall_ledger") == {"id", "created_at"}

        new_version = apply_pending(conn)

        assert new_version == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_RECALL_LEDGER_COLUMNS.issubset(_columns(conn, "recall_ledger"))
    finally:
        conn.close()


def test_apply_pending_is_idempotent_after_v3_ratchet(tenant_root: Path) -> None:
    db_path = _bootstrap_v2_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pending(conn)
        again = apply_pending(conn)
        assert again == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_RECALL_LEDGER_COLUMNS.issubset(_columns(conn, "recall_ledger"))
    finally:
        conn.close()


def test_apply_pending_on_fresh_v3_database_is_noop(tenant_root: Path) -> None:
    """A fresh S2Schema.create() is already at LATEST; apply_pending no-ops."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        cols_before = _columns(conn, "recall_ledger")
        result = apply_pending(conn)
        assert result == LATEST_SCHEMA_VERSION
        assert _columns(conn, "recall_ledger") == cols_before
    finally:
        conn.close()
