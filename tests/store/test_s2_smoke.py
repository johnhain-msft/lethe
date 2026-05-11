"""S2 smoke: 10 named tables + S5 log table present; WAL pragmas honored."""

from __future__ import annotations

from pathlib import Path

from lethe.store.s2_meta import S2_TABLE_NAMES, S5_LOG_TABLE_NAME, S2Schema


def _table_names(conn) -> set[str]:  # type: ignore[no-untyped-def]
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def test_s2_schema_creates_all_tables(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        present = _table_names(conn)
        for name in S2_TABLE_NAMES:
            assert name in present, f"S2 table {name!r} missing"
        assert S5_LOG_TABLE_NAME in present, "S5 log table must live inside S2 file"
    finally:
        conn.close()


def test_s2_schema_pragmas_set(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert journal_mode.lower() == "wal"
        # synchronous=NORMAL maps to integer 1.
        assert synchronous == 1
        assert foreign_keys == 1
    finally:
        conn.close()


def test_s2_schema_is_idempotent(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn1 = schema.create()
    conn1.close()
    conn2 = schema.create()
    try:
        present = _table_names(conn2)
        for name in S2_TABLE_NAMES:
            assert name in present
    finally:
        conn2.close()


def test_review_queue_shape_pinned(tenant_root: Path) -> None:
    """review_queue columns track docs/08-deployment-design.md §6.2."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(review_queue)")}
    finally:
        conn.close()
    expected = {
        "staged_id",
        "tenant_id",
        "source_verb",
        "source_principal",
        "staged_at",
        "payload_blob",
        "classifier_class",
        "classifier_score",
        "status",
        "reviewer_principal",
        "reviewed_at",
        "review_reason",
        "expires_at",
    }
    assert expected.issubset(cols)
