"""S2 P2 migration round-trip: ``extraction_log`` + ``audit_log`` columns.

Covers:

- A fresh ``S2Schema.create()`` lands at the latest schema version (v2) and
  the two newly-shaped tables expose the columns from facilitator P2 sub-plan
  §6 + the gap-06 minimal scaffold (per facilitator §(c) closing line).
- A simulated v1-shaped database (stub ``(id, created_at)`` for both tables;
  ``schema_version='1'``) is ratcheted to v2 by :func:`apply_pending`, and
  re-running :func:`apply_pending` after that is a no-op.
- A fresh DB at v2 is also a no-op for :func:`apply_pending`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lethe.store.s2_meta import S2Schema
from lethe.store.s2_meta.migrations import (
    LATEST_SCHEMA_VERSION,
    apply_pending,
    current_version,
)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# Facilitator P2 sub-plan §6: extraction_log columns.
_EXPECTED_EXTRACTION_LOG_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "episode_id",
        "extracted_at",
        "extractor_version",
        "confidence",
        "payload_blob",
    }
)

# Facilitator P2 sub-plan §6: audit_log columns.
_EXPECTED_AUDIT_LOG_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "created_at",
        "tenant_id",
        "verb",
        "principal",
        "action",
        "payload_json",
    }
)


def test_fresh_schema_lands_at_latest_version(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION
    finally:
        conn.close()


def test_extraction_log_columns_pinned(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = _columns(conn, "extraction_log")
    finally:
        conn.close()
    assert _EXPECTED_EXTRACTION_LOG_COLUMNS.issubset(cols), (
        f"missing extraction_log columns: "
        f"{_EXPECTED_EXTRACTION_LOG_COLUMNS - cols}"
    )


def test_audit_log_columns_pinned(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = _columns(conn, "audit_log")
    finally:
        conn.close()
    assert _EXPECTED_AUDIT_LOG_COLUMNS.issubset(cols), (
        f"missing audit_log columns: {_EXPECTED_AUDIT_LOG_COLUMNS - cols}"
    )


def test_extraction_log_accepts_minimal_p2_row(tenant_root: Path) -> None:
    """The P2 column shape is the contract P3+ extraction wire-up consumes."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO extraction_log"
            " (episode_id, extractor_version, confidence, payload_blob)"
            " VALUES (?, ?, ?, ?)",
            ("ep-uuid-1", "v0.0.1", 0.87, b"{}"),
        )
        row = conn.execute(
            "SELECT episode_id, extractor_version, confidence, payload_blob"
            " FROM extraction_log"
        ).fetchone()
        assert row == ("ep-uuid-1", "v0.0.1", 0.87, b"{}")
    finally:
        conn.close()


def test_audit_log_accepts_force_skip_row(tenant_root: Path) -> None:
    """Audit row written by remember.py for force_skip_classifier=True."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO audit_log"
            " (tenant_id, verb, principal, action, payload_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "tenant-a",
                "remember",
                "principal-x",
                "force_skip_classifier_invoked",
                '{"caller_tag":"remember:fact","request_idempotency_key":"00000000-0000-7000-8000-000000000000"}',
            ),
        )
        row = conn.execute(
            "SELECT tenant_id, verb, action FROM audit_log"
        ).fetchone()
        assert row == ("tenant-a", "remember", "force_skip_classifier_invoked")
    finally:
        conn.close()


def _bootstrap_v1_database(tenant_root: Path) -> Path:
    """Create a v1-shaped S2 database (stub extraction_log + audit_log).

    Mirrors the literal P1 schema by hand so the migration test does not
    depend on git-historical schema.py behavior. Only the two tables that
    change at v2 are needed for round-trip coverage.
    """
    db_path = tenant_root / "s2_meta.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE _lethe_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO _lethe_meta(key, value) VALUES ('schema_version','1')"
    )
    # P1 stub shape for the two tables P2 columns.
    conn.execute(
        "CREATE TABLE extraction_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        ")"
    )
    conn.execute(
        "CREATE TABLE audit_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        ")"
    )
    conn.close()
    return db_path


def test_v1_database_ratchets_to_v2(tenant_root: Path) -> None:
    db_path = _bootstrap_v1_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        assert current_version(conn) == 1
        # P1 stub shape: only id + created_at columns.
        assert _columns(conn, "extraction_log") == {"id", "created_at"}
        assert _columns(conn, "audit_log") == {"id", "created_at"}

        new_version = apply_pending(conn)

        assert new_version == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_EXTRACTION_LOG_COLUMNS.issubset(
            _columns(conn, "extraction_log")
        )
        assert _EXPECTED_AUDIT_LOG_COLUMNS.issubset(
            _columns(conn, "audit_log")
        )
    finally:
        conn.close()


def test_apply_pending_is_idempotent_after_ratchet(tenant_root: Path) -> None:
    db_path = _bootstrap_v1_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pending(conn)
        # Re-running must be a no-op (returns LATEST, columns unchanged).
        again = apply_pending(conn)
        assert again == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_EXTRACTION_LOG_COLUMNS.issubset(
            _columns(conn, "extraction_log")
        )
        assert _EXPECTED_AUDIT_LOG_COLUMNS.issubset(
            _columns(conn, "audit_log")
        )
    finally:
        conn.close()


def test_apply_pending_on_fresh_v2_database_is_noop(tenant_root: Path) -> None:
    """A fresh S2Schema.create() is already at LATEST; apply_pending no-ops."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        cols_before_extraction = _columns(conn, "extraction_log")
        cols_before_audit = _columns(conn, "audit_log")
        result = apply_pending(conn)
        assert result == LATEST_SCHEMA_VERSION
        assert _columns(conn, "extraction_log") == cols_before_extraction
        assert _columns(conn, "audit_log") == cols_before_audit
    finally:
        conn.close()
