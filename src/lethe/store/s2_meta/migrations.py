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

Future migrations (P4+) for tables that may already hold rows MUST use
``ALTER TABLE`` rather than drop-and-recreate.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from lethe.store.s2_meta.schema import (
    _DDL_AUDIT_LOG,
    _DDL_EXTRACTION_LOG,
    _DDL_RECALL_LEDGER,
)

LATEST_SCHEMA_VERSION = 3


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


# Each migration is `(version, callable)` where callable mutates the DB to
# bring it from `version - 1` to `version`.
MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (2, _m2_extraction_and_audit_columns),
    (3, _m3_recall_ledger_columns),
)


def current_version(conn: sqlite3.Connection) -> int:
    """Return the schema version recorded in ``_lethe_meta``.

    Returns ``0`` if the meta row is absent (pre-bootstrap database).
    """
    cur = conn.execute(
        "SELECT value FROM _lethe_meta WHERE key = 'schema_version'"
    )
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
                "INSERT OR REPLACE INTO _lethe_meta(key, value)"
                " VALUES ('schema_version', ?)",
                (str(target),),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        version = target
    return version

