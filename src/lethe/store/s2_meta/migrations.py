"""S2 schema migrations registry.

Each migration brings a database from ``version - 1`` to ``version``. Fresh
databases created via :meth:`S2Schema.create` always land at the latest
``schema_version`` directly; migrations exist for databases that were
bootstrapped at an earlier version and need to be ratcheted forward.

Schema version history:

- v1 (P1): baseline (six stub tables; ``review_queue`` + ``idempotency_keys``
  shaped; ``tenant_config`` + ``scoring_weight_overrides`` key-value).
- v2 (P2): ``extraction_log`` + ``audit_log`` columned per facilitator
  sub-plan §6. The two tables are empty stubs at v1 (no production data
  exists yet anywhere in the system at P1), so the v2 migration drops and
  recreates each — no data preservation required.
- v3 (P3): ``recall_ledger`` columned per facilitator P3 plan §(d). Same
  drop-and-recreate semantics as v2 (table is an empty stub at v2 — no
  verb writes to it before P3).
- v4 (P4): ``consolidation_state`` + ``promotion_flags`` + ``utility_events``
  columned per facilitator P4 plan §(c) (kickoff §6 open item A). All
  three are stubs at v3 — no verb writes to them before P4 — so
  drop-and-recreate is safe. The already-columned tables (``recall_ledger``,
  ``extraction_log``, ``audit_log``) are NOT touched by this migration:
  they hold real production rows from P2/P3, and the standing rule below
  binds.

Future migrations (P5+) for tables that may already hold rows MUST use
``ALTER TABLE`` rather than drop-and-recreate. After v4 every named table
in :data:`lethe.store.s2_meta.schema.S2_TABLE_NAMES` has a non-stub shape,
so this rule applies to every subsequent migration.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from lethe.store.s2_meta.schema import (
    _DDL_AUDIT_LOG,
    _DDL_CONSOLIDATION_STATE,
    _DDL_EXTRACTION_LOG,
    _DDL_PROMOTION_FLAGS,
    _DDL_RECALL_LEDGER,
    _DDL_UTILITY_EVENTS,
    _DDL_UTILITY_EVENTS_INDEX,
)

LATEST_SCHEMA_VERSION = 4


def _m2_extraction_and_audit_columns(conn: sqlite3.Connection) -> None:
    """v1 → v2: column ``extraction_log`` + ``audit_log``.

    Both tables are P1 stubs ``(id, created_at)`` and contain no rows in any
    valid v1 deployment (no verb writes to them at P1), so drop-and-recreate
    is safe. P4+ migrations on tables with real data must use ``ALTER TABLE``.
    """
    conn.execute("DROP TABLE IF EXISTS extraction_log")
    conn.execute(_DDL_EXTRACTION_LOG)
    conn.execute("DROP TABLE IF EXISTS audit_log")
    conn.execute(_DDL_AUDIT_LOG)


def _m3_recall_ledger_columns(conn: sqlite3.Connection) -> None:
    """v2 → v3: column ``recall_ledger`` per facilitator P3 plan §(d).

    The v2 ``recall_ledger`` is an ``(id, created_at)`` stub; no verb has
    ever written to it (the ``recall`` verb lands at P3 with this exact
    column shape), so drop-and-recreate is safe. P5+ recall_ledger
    extensions (e.g. join indexes for ``recall_outcome`` ingest) MUST use
    ``ALTER TABLE`` because P3+ deployments will hold real ledger rows.
    """
    conn.execute("DROP TABLE IF EXISTS recall_ledger")
    conn.execute(_DDL_RECALL_LEDGER)


def _m4_consolidate_v4(conn: sqlite3.Connection) -> None:
    """v3 → v4: column ``consolidation_state`` + ``promotion_flags`` + ``utility_events``.

    All three tables are P3 stubs ``(id, created_at)`` and contain no rows
    in any valid v3 deployment (no verb writes to them before P4), so
    drop-and-recreate is safe (kickoff §D8 + QA-G1 §B.5). The already-
    columned tables (``recall_ledger``, ``extraction_log``, ``audit_log``)
    are intentionally NOT touched here — they hold real production rows
    from P2/P3, and the module docstring's ALTER discipline binds. P5+
    extensions to those tables MUST use ``ALTER TABLE``.

    The ``utility_events`` composite index ``(tenant_id, fact_id, ts_recorded)``
    is created alongside the table in this same step so the consolidate
    δ-term aggregation hot path is indexed from day one (per facilitator
    plan §(c) + §(i) open item A).
    """
    conn.execute("DROP TABLE IF EXISTS consolidation_state")
    conn.execute(_DDL_CONSOLIDATION_STATE)
    conn.execute("DROP TABLE IF EXISTS promotion_flags")
    conn.execute(_DDL_PROMOTION_FLAGS)
    conn.execute("DROP TABLE IF EXISTS utility_events")
    conn.execute(_DDL_UTILITY_EVENTS)
    conn.execute(_DDL_UTILITY_EVENTS_INDEX)


# Each migration is `(version, callable)` where callable mutates the DB to
# bring it from `version - 1` to `version`.
MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (2, _m2_extraction_and_audit_columns),
    (3, _m3_recall_ledger_columns),
    (4, _m4_consolidate_v4),
)


def current_version(conn: sqlite3.Connection) -> int:
    """Return the schema version recorded in ``_lethe_meta``.

    Returns ``0`` if the meta row is absent (pre-bootstrap database).
    """
    cur = conn.execute("SELECT value FROM _lethe_meta WHERE key = 'schema_version'")
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def apply_pending(conn: sqlite3.Connection) -> int:
    """Run every migration whose target version is above ``current_version``.

    Idempotent: re-applying after the schema is already at
    :data:`LATEST_SCHEMA_VERSION` is a no-op. Returns the version after
    migration. Each migration runs in its own transaction so a partial
    failure leaves the schema-version sentinel pointing at the last
    successfully-applied migration.
    """
    version = current_version(conn)
    for target, migrate in MIGRATIONS:
        if target <= version:
            continue
        conn.execute("BEGIN")
        try:
            migrate(conn)
            conn.execute(
                "INSERT OR REPLACE INTO _lethe_meta(key, value) VALUES ('schema_version', ?)",
                (str(target),),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        version = target
    return version
