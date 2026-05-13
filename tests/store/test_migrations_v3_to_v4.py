"""S2 P4 migration round-trip: ``consolidation_state`` + ``promotion_flags``
+ ``utility_events`` columns (schema v4).

Mirrors the layout of ``test_s2_p2_migrations.py`` and ``test_s2_p3_migrations.py``:

- A fresh ``S2Schema.create()`` lands at the latest schema version (v4) and
  the three newly-shaped tables expose the columns from facilitator P4 plan
  §(c) (kickoff §6 open item A — utility_events columnized at v4).
- A simulated v3-shaped database (stub ``(id, created_at)`` for the three
  newly-columned tables; ``schema_version='3'``) is ratcheted to v4 by
  :func:`apply_pending`, and re-running :func:`apply_pending` after that
  is a no-op.
- A fresh DB at v4 is also a no-op for :func:`apply_pending`.
- The three already-columned tables (``recall_ledger``, ``extraction_log``,
  ``audit_log``) hold real rows from P2/P3 — the v4 migration MUST NOT
  touch them. We bootstrap a v3 DB with one canonical row in each, run
  the migration, and assert byte-equality before vs. after.
- The schema produced by a fresh-v4 ``create()`` is byte-identical to the
  schema produced by ratcheting v1 → v2 → v3 → v4 (sanity-pin against
  divergence between the two paths).
- ``_STUB_TABLES`` is empty after v4 — every named table in
  :data:`S2_TABLE_NAMES` has a real shape.
- The CHECK constraints on the new tables are active (utility_events
  ``event_kind`` enum + ``frozen`` boolean) — we exercise each by
  attempting an invalid INSERT and asserting :class:`IntegrityError`.
- The composite index on ``utility_events`` is present after migrate.
- The S3 ``embedding_keys`` CHECK constraint (s3_vec/client.py:91-92) is
  unaffected by the v4 migration — we co-bootstrap S3 in the same tenant
  root, run the v4 migration on S2, and re-verify the S3 CHECK still
  rejects an all-NULL row. (Per kickoff "verify your migration test
  asserts it remains active after migrate.")
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
from lethe.store.s2_meta.schema import _STUB_TABLES, S2_TABLE_NAMES
from lethe.store.s3_vec import S3Client


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}


def _table_sql(conn: sqlite3.Connection, name: str) -> str | None:
    """Return the canonical CREATE statement SQLite recorded for ``name``."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return None if row is None else row[0]


# Facilitator P4 plan §(c): consolidation_state columns.
_EXPECTED_CONSOLIDATION_STATE_COLUMNS: frozenset[str] = frozenset(
    {
        "tenant_id",
        "lock_token",
        "lock_acquired_at",
        "lock_heartbeat_at",
        "last_run_cursor",
        "last_run_at",
        "cascade_cost_99pct",
        "created_at",
        "updated_at",
    }
)

# Facilitator P4 plan §(c): promotion_flags columns.
_EXPECTED_PROMOTION_FLAGS_COLUMNS: frozenset[str] = frozenset(
    {
        "tenant_id",
        "fact_id",
        "tier",
        "flag_set_at",
        "flag_set_by",
        "reason",
    }
)

# Facilitator P4 plan §(c): utility_events columns. ``event_kind`` enum
# matches scoring §3.3 per-event weight table exactly (citation,
# tool_success, correction, repeat_recall, no_op).
_EXPECTED_UTILITY_EVENTS_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "tenant_id",
        "fact_id",
        "event_kind",
        "event_weight",
        "ts_recorded",
        "frozen",
    }
)


# ---------------------------------------------------------------------------
# Sanity pins
# ---------------------------------------------------------------------------


def test_latest_schema_version_is_4() -> None:
    """Sanity-pin the v4 ratchet so a future bump fails this test loudly."""
    assert LATEST_SCHEMA_VERSION == 4


def test_stub_tables_is_empty_after_v4() -> None:
    """Commit-1 contract: every named S2 table now has a real shape."""
    assert not _STUB_TABLES, f"_STUB_TABLES should be empty at v4; got {_STUB_TABLES!r}"
    for name in S2_TABLE_NAMES:
        assert name not in _STUB_TABLES, f"{name!r} should not be a stub at v4"


# ---------------------------------------------------------------------------
# Fresh create at v4
# ---------------------------------------------------------------------------


def test_fresh_create_is_at_v4(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION == 4
    finally:
        conn.close()


def test_consolidation_state_columns_pinned(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = _columns(conn, "consolidation_state")
    finally:
        conn.close()
    assert _EXPECTED_CONSOLIDATION_STATE_COLUMNS.issubset(cols), (
        f"missing consolidation_state columns: {_EXPECTED_CONSOLIDATION_STATE_COLUMNS - cols}"
    )


def test_promotion_flags_columns_pinned(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = _columns(conn, "promotion_flags")
    finally:
        conn.close()
    assert _EXPECTED_PROMOTION_FLAGS_COLUMNS.issubset(cols), (
        f"missing promotion_flags columns: {_EXPECTED_PROMOTION_FLAGS_COLUMNS - cols}"
    )


def test_utility_events_columns_pinned(tenant_root: Path) -> None:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        cols = _columns(conn, "utility_events")
    finally:
        conn.close()
    assert _EXPECTED_UTILITY_EVENTS_COLUMNS.issubset(cols), (
        f"missing utility_events columns: {_EXPECTED_UTILITY_EVENTS_COLUMNS - cols}"
    )


def test_utility_events_composite_index_present(tenant_root: Path) -> None:
    """The (tenant_id, fact_id, ts_recorded) index lands at v4."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        names = _index_names(conn, "utility_events")
        assert "ix_utility_events_tenant_fact_ts" in names, (
            f"missing index ix_utility_events_tenant_fact_ts; got {sorted(names)}"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Round-shape acceptance — canonical row inserts succeed
# ---------------------------------------------------------------------------


def test_consolidation_state_accepts_unlocked_row(tenant_root: Path) -> None:
    """Initial state row (no active lock, never run): all lock + last_run cols
    NULL is the expected initial shape."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO consolidation_state (tenant_id) VALUES (?)",
            ("tenant-a",),
        )
        row = conn.execute(
            "SELECT tenant_id, lock_token, last_run_cursor, last_run_at,"
            " cascade_cost_99pct FROM consolidation_state"
        ).fetchone()
        assert row == ("tenant-a", None, None, None, None)
    finally:
        conn.close()


def test_promotion_flags_accepts_consolidate_row(tenant_root: Path) -> None:
    """Row written by consolidate's promote phase."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO promotion_flags"
            " (tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "tenant-a",
                "fact-uuid-1",
                "promoted",
                "2025-12-01T12:00:00.000Z",
                "consolidate-run-uuid-1",
                "score above theta_promote",
            ),
        )
        row = conn.execute(
            "SELECT tenant_id, fact_id, tier, flag_set_by, reason FROM promotion_flags"
        ).fetchone()
        assert row == (
            "tenant-a",
            "fact-uuid-1",
            "promoted",
            "consolidate-run-uuid-1",
            "score above theta_promote",
        )
    finally:
        conn.close()


def test_utility_events_accepts_canonical_event(tenant_root: Path) -> None:
    """Row written by the (P9-future) recall_outcome ingest path."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        conn.execute(
            "INSERT INTO utility_events"
            " (tenant_id, fact_id, event_kind, event_weight, ts_recorded)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "tenant-a",
                "fact-uuid-1",
                "citation",
                0.4,
                "2025-12-01T12:00:00.000Z",
            ),
        )
        row = conn.execute(
            "SELECT tenant_id, fact_id, event_kind, event_weight, frozen FROM utility_events"
        ).fetchone()
        # frozen defaults to 0 (live tally); §6.4 freeze sets it to 1.
        assert row == (
            "tenant-a",
            "fact-uuid-1",
            "citation",
            0.4,
            0,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CHECK constraints active
# ---------------------------------------------------------------------------


def test_promotion_flags_pk_enforces_per_tenant_per_fact_uniqueness(
    tenant_root: Path,
) -> None:
    """(tenant_id, fact_id) PK forbids duplicate flags for the same pair."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        row = (
            "tenant-a",
            "fact-uuid-1",
            "promoted",
            "2025-12-01T12:00:00.000Z",
            "consolidate-run-uuid-1",
            None,
        )
        conn.execute(
            "INSERT INTO promotion_flags"
            " (tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            row,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO promotion_flags"
                " (tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                row,
            )
        # Different fact_id under the same tenant: ok.
        conn.execute(
            "INSERT INTO promotion_flags"
            " (tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "tenant-a",
                "fact-uuid-2",
                "demoted",
                "2025-12-01T12:00:00.000Z",
                "consolidate-run-uuid-1",
                None,
            ),
        )
    finally:
        conn.close()


def test_utility_events_event_kind_enum_active(tenant_root: Path) -> None:
    """event_kind CHECK rejects values outside the scoring §3.3 enum."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO utility_events"
                " (tenant_id, fact_id, event_kind, event_weight, ts_recorded)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    "tenant-a",
                    "fact-uuid-1",
                    "definitely-not-a-real-kind",
                    0.4,
                    "2025-12-01T12:00:00.000Z",
                ),
            )
        # All five canonical values from scoring §3.3 are accepted.
        for kind in (
            "citation",
            "tool_success",
            "correction",
            "repeat_recall",
            "no_op",
        ):
            conn.execute(
                "INSERT INTO utility_events"
                " (tenant_id, fact_id, event_kind, event_weight, ts_recorded)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    "tenant-a",
                    "fact-uuid-1",
                    kind,
                    0.0,
                    "2025-12-01T12:00:00.000Z",
                ),
            )
    finally:
        conn.close()


def test_utility_events_frozen_check_active(tenant_root: Path) -> None:
    """frozen CHECK rejects values outside {0, 1}."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO utility_events"
                " (tenant_id, fact_id, event_kind, event_weight, ts_recorded,"
                " frozen) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "tenant-a",
                    "fact-uuid-1",
                    "citation",
                    0.4,
                    "2025-12-01T12:00:00.000Z",
                    2,
                ),
            )
        # Both legal values accepted.
        for f in (0, 1):
            conn.execute(
                "INSERT INTO utility_events"
                " (tenant_id, fact_id, event_kind, event_weight, ts_recorded,"
                " frozen) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "tenant-a",
                    "fact-uuid-1",
                    "citation",
                    0.4,
                    "2025-12-01T12:00:00.000Z",
                    f,
                ),
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# v3 → v4 ratchet round-trip + non-regression of v3 columned tables
# ---------------------------------------------------------------------------


def _bootstrap_v3_database(tenant_root: Path) -> Path:
    """Create a v3-shaped S2 database.

    The three tables that change at v4 (consolidation_state, promotion_flags,
    utility_events) are stubs (id, created_at). The three already-columned
    tables (recall_ledger, extraction_log, audit_log) get their v3 column
    shape AND one canonical row each, so the v3 → v4 ratchet test can
    assert byte-equality before vs. after migrate.

    Mirrors the literal P3 schema by hand so the migration test does not
    depend on git-historical schema.py behavior.
    """
    db_path = tenant_root / "s2_meta.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE _lethe_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO _lethe_meta(key, value) VALUES ('schema_version','3')")
    # v3 stub shape for the three tables P4 columns.
    for name in ("consolidation_state", "promotion_flags", "utility_events"):
        conn.execute(
            f"CREATE TABLE {name} ("
            f" id INTEGER PRIMARY KEY AUTOINCREMENT,"
            f" created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
            f")"
        )
    # v3 columned shape for the three tables P4 must NOT touch. Each gets
    # one canonical row so byte-equality assertions are meaningful.
    conn.execute(
        "CREATE TABLE recall_ledger ("
        " recall_id TEXT PRIMARY KEY,"
        " tenant_id TEXT NOT NULL,"
        " query_hash TEXT NOT NULL,"
        " ts_recorded TEXT NOT NULL,"
        " classified_intent TEXT NOT NULL,"
        " weights_version TEXT NOT NULL,"
        " top_k_fact_ids TEXT NOT NULL,"
        " response_envelope_blob BLOB NOT NULL,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        ")"
    )
    conn.execute(
        "INSERT INTO recall_ledger"
        " (recall_id, tenant_id, query_hash, ts_recorded, classified_intent,"
        "  weights_version, top_k_fact_ids, response_envelope_blob, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "01234567-89ab-7def-8123-456789abcdef",
            "tenant-a",
            "0123456789abcdef",
            "2025-06-01T12:34:56.789Z",
            "lookup",
            "p3-gap03-5a-v0",
            '["ep-1","ep-2"]',
            b'{"recall_id":"...","facts":[]}',
            "2025-06-01T12:34:56.789Z",
        ),
    )
    conn.execute(
        "CREATE TABLE extraction_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " episode_id TEXT NOT NULL,"
        " extracted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
        " extractor_version TEXT NOT NULL,"
        " confidence REAL NOT NULL,"
        " payload_blob BLOB NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO extraction_log"
        " (episode_id, extracted_at, extractor_version, confidence, payload_blob)"
        " VALUES (?, ?, ?, ?, ?)",
        ("ep-uuid-1", "2025-06-01T12:34:56.789Z", "v0.0.1", 0.87, b"{}"),
    )
    conn.execute(
        "CREATE TABLE audit_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
        " tenant_id TEXT NOT NULL,"
        " verb TEXT NOT NULL,"
        " principal TEXT NOT NULL,"
        " action TEXT NOT NULL,"
        " payload_json TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO audit_log"
        " (created_at, tenant_id, verb, principal, action, payload_json)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            "2025-06-01T12:34:56.789Z",
            "tenant-a",
            "remember",
            "principal-x",
            "force_skip_classifier_invoked",
            '{"caller_tag":"remember:fact"}',
        ),
    )
    conn.close()
    return db_path


def _snapshot_columned_table_rows(
    conn: sqlite3.Connection,
) -> dict[str, list[tuple[object, ...]]]:
    """Snapshot every row from the three already-columned tables for byte-equality."""
    return {
        "recall_ledger": list(
            conn.execute(
                "SELECT recall_id, tenant_id, query_hash, ts_recorded,"
                " classified_intent, weights_version, top_k_fact_ids,"
                " response_envelope_blob, created_at FROM recall_ledger"
                " ORDER BY recall_id"
            )
        ),
        "extraction_log": list(
            conn.execute(
                "SELECT id, episode_id, extracted_at, extractor_version,"
                " confidence, payload_blob FROM extraction_log ORDER BY id"
            )
        ),
        "audit_log": list(
            conn.execute(
                "SELECT id, created_at, tenant_id, verb, principal, action,"
                " payload_json FROM audit_log ORDER BY id"
            )
        ),
    }


def test_v3_database_ratchets_to_v4(tenant_root: Path) -> None:
    db_path = _bootstrap_v3_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        assert current_version(conn) == 3
        for name in ("consolidation_state", "promotion_flags", "utility_events"):
            assert _columns(conn, name) == {"id", "created_at"}, (
                f"v3 stub shape mismatch for {name}: {_columns(conn, name)}"
            )

        new_version = apply_pending(conn)

        assert new_version == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_CONSOLIDATION_STATE_COLUMNS.issubset(_columns(conn, "consolidation_state"))
        assert _EXPECTED_PROMOTION_FLAGS_COLUMNS.issubset(_columns(conn, "promotion_flags"))
        assert _EXPECTED_UTILITY_EVENTS_COLUMNS.issubset(_columns(conn, "utility_events"))
        # The composite index lands as part of the v4 step.
        assert "ix_utility_events_tenant_fact_ts" in _index_names(conn, "utility_events")
    finally:
        conn.close()


def test_v3_to_v4_does_not_touch_already_columned_tables(
    tenant_root: Path,
) -> None:
    """recall_ledger / extraction_log / audit_log are byte-unchanged across migrate.

    Standing rule from the migrations module docstring: tables that may
    hold rows MUST NOT be drop-recreated. This is the regression guard.
    """
    db_path = _bootstrap_v3_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        before_rows = _snapshot_columned_table_rows(conn)
        before_sql = {
            name: _table_sql(conn, name)
            for name in ("recall_ledger", "extraction_log", "audit_log")
        }

        apply_pending(conn)

        after_rows = _snapshot_columned_table_rows(conn)
        after_sql = {
            name: _table_sql(conn, name)
            for name in ("recall_ledger", "extraction_log", "audit_log")
        }
        assert before_rows == after_rows, (
            "v4 migration mutated rows in already-columned tables; this "
            "violates the ALTER-discipline standing rule"
        )
        assert before_sql == after_sql, (
            "v4 migration mutated CREATE TABLE statement of already-columned "
            "tables; this violates the ALTER-discipline standing rule"
        )
    finally:
        conn.close()


def test_apply_pending_is_idempotent_after_v4_ratchet(tenant_root: Path) -> None:
    db_path = _bootstrap_v3_database(tenant_root)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pending(conn)
        again = apply_pending(conn)
        assert again == LATEST_SCHEMA_VERSION
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        assert _EXPECTED_CONSOLIDATION_STATE_COLUMNS.issubset(_columns(conn, "consolidation_state"))
        assert _EXPECTED_PROMOTION_FLAGS_COLUMNS.issubset(_columns(conn, "promotion_flags"))
        assert _EXPECTED_UTILITY_EVENTS_COLUMNS.issubset(_columns(conn, "utility_events"))
    finally:
        conn.close()


def test_apply_pending_on_fresh_v4_database_is_noop(tenant_root: Path) -> None:
    """A fresh S2Schema.create() is already at LATEST; apply_pending no-ops."""
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    try:
        assert current_version(conn) == LATEST_SCHEMA_VERSION
        cols_before = {
            name: _columns(conn, name)
            for name in (
                "consolidation_state",
                "promotion_flags",
                "utility_events",
            )
        }
        result = apply_pending(conn)
        assert result == LATEST_SCHEMA_VERSION
        cols_after = {
            name: _columns(conn, name)
            for name in (
                "consolidation_state",
                "promotion_flags",
                "utility_events",
            )
        }
        assert cols_before == cols_after
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fresh-v4 vs ratcheted-v4 schema identity (sanity-pin the two paths)
# ---------------------------------------------------------------------------


def test_fresh_v4_and_ratcheted_v4_produce_identical_schema(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The two construction paths converge on byte-identical CREATE statements.

    Catches drift between the bootstrap-at-LATEST path
    (:meth:`S2Schema.create`) and the ratchet path (v3 db + apply_pending).
    Either path adopting a different shape than the other would surface
    here.
    """
    fresh_root = tmp_path_factory.mktemp("fresh-v4-tenant")
    ratcheted_root = tmp_path_factory.mktemp("ratcheted-v4-tenant")

    fresh_conn = S2Schema(tenant_root=fresh_root).create()
    try:
        # All P4-columned tables + the three v3-untouched columned tables +
        # the three index-bearing surfaces. The S5 log table is part of the
        # bootstrap surface too.
        names = [
            "recall_ledger",
            "extraction_log",
            "audit_log",
            "consolidation_state",
            "promotion_flags",
            "utility_events",
            "tenant_config",
            "scoring_weight_overrides",
            "review_queue",
            "idempotency_keys",
            "s5_consolidation_log",
        ]
        fresh_sql = {name: _table_sql(fresh_conn, name) for name in names}
        # Indexes are in sqlite_master too.
        fresh_index_sql = {
            row[0]: row[1]
            for row in fresh_conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"
            )
        }
    finally:
        fresh_conn.close()

    ratcheted_db = _bootstrap_v3_database(ratcheted_root / "tenants" / "smoke-tenant")
    ratcheted_conn = sqlite3.connect(str(ratcheted_db), isolation_level=None)
    try:
        apply_pending(ratcheted_conn)
        # Compare only the three P4-touched tables + their indexes; the
        # v3-untouched tables in the ratcheted DB use the by-hand bootstrap
        # SQL from _bootstrap_v3_database (which intentionally mirrors the
        # production shape but isn't byte-identical to schema.py's CREATE
        # IF NOT EXISTS form).
        for name in (
            "consolidation_state",
            "promotion_flags",
            "utility_events",
        ):
            assert fresh_sql[name] == _table_sql(ratcheted_conn, name), (
                f"fresh-v4 vs ratcheted-v4 CREATE TABLE divergence for {name}"
            )
        # Index also lands identically.
        ratcheted_index_sql = {
            row[0]: row[1]
            for row in ratcheted_conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"
            )
        }
        assert (
            fresh_index_sql["ix_utility_events_tenant_fact_ts"]
            == ratcheted_index_sql["ix_utility_events_tenant_fact_ts"]
        )
    finally:
        ratcheted_conn.close()


# ---------------------------------------------------------------------------
# S3 embedding-key invariant unaffected by the v4 migration
# ---------------------------------------------------------------------------


def test_s3_embedding_key_check_remains_active_after_v4_migrate(
    tenant_root: Path,
) -> None:
    """The s3_vec/client.py:91-92 CHECK still rejects an all-NULL row after
    running the v3 → v4 S2 migration.

    Per facilitator reminder: the v4 migration does not touch S3, but we
    explicitly verify the embedding-key invariant remains active so a
    future migration that accidentally co-mutates S3 would surface here.
    """
    s3 = S3Client(tenant_root)
    s3_conn = s3.bootstrap()
    try:
        # Ratchet S2 from v3 to v4 in the same tenant root.
        s2_db_path = _bootstrap_v3_database(tenant_root)
        s2_conn = sqlite3.connect(str(s2_db_path), isolation_level=None)
        try:
            apply_pending(s2_conn)
        finally:
            s2_conn.close()

        # All-null insert must still raise (the CHECK is unchanged).
        with pytest.raises(sqlite3.IntegrityError):
            s3_conn.execute(
                "INSERT INTO embedding_keys"
                " (rowid, node_id, edge_id, episode_id)"
                " VALUES (?, NULL, NULL, NULL)",
                (1,),
            )
        # Two-of-three set: still rejected.
        with pytest.raises(sqlite3.IntegrityError):
            s3_conn.execute(
                "INSERT INTO embedding_keys"
                " (rowid, node_id, edge_id, episode_id)"
                " VALUES (?, ?, ?, NULL)",
                (2, "node-1", "edge-1"),
            )
        # Exactly one of three set: still accepted.
        s3_conn.execute(
            "INSERT INTO embedding_keys"
            " (rowid, node_id, edge_id, episode_id)"
            " VALUES (?, ?, NULL, NULL)",
            (3, "node-1"),
        )
    finally:
        s3.close()
