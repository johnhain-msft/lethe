"""S2 schema: 10 named tables (IMPL §2.1) + the S5 consolidation log table.

Column shapes are intentionally minimal at P1. The 10 table NAMES are pinned
by ``docs/IMPLEMENTATION.md`` §2.1; concrete column shapes evolve via
:mod:`lethe.store.s2_meta.migrations` as each table's owning verb lands
(P2 → ``recall_ledger`` / ``idempotency_keys``; P4 → ``consolidation_state``
/ ``scoring_weight_overrides``; P5 → ``promotion_flags``; P7 → ``review_queue``;
P8 → ``audit_log``; etc.).

Two tables ARE shaped at P1 because their shapes are pinned by canonical docs:

- ``review_queue`` per ``docs/08-deployment-design.md`` §6.2.
- ``idempotency_keys`` per api §1.2 + invariant I-5 (24 h TTL default; 7-day
  enforced ceiling) + gap-08 §5.

All other tables get a minimal ``(id, created_at)`` stub. A ``meta_version``
sentinel row tracks schema version so :mod:`.migrations` can ratchet forward.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Pinned by IMPL §2.1 — order is alphabetic except where the doc lists it.
S2_TABLE_NAMES: tuple[str, ...] = (
    "recall_ledger",
    "utility_events",
    "promotion_flags",
    "consolidation_state",
    "extraction_log",
    "tenant_config",
    "scoring_weight_overrides",
    "review_queue",
    "audit_log",
    "idempotency_keys",
)

# S5 lives inside the S2 file (facilitator §(g) lock) — single-DB T2 txn.
S5_LOG_TABLE_NAME = "s5_consolidation_log"

# Tables that get a minimal `(id, created_at)` stub at P1. See module docstring
# for why we don't speculate on real columns yet.
_STUB_TABLES: frozenset[str] = frozenset(
    {
        "recall_ledger",
        "utility_events",
        "promotion_flags",
        "consolidation_state",
        "extraction_log",
        "audit_log",
    }
)

# DDL fragments. Every table includes an `id` PK and a `created_at` timestamp;
# this is the minimum needed to satisfy "schemas create cleanly" without
# inventing speculative columns that P2+ migrations would have to undo.

_DDL_STUB = (
    "CREATE TABLE IF NOT EXISTS {name} ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
    ")"
)

# tenant_config: simple key-value (deployment doc references
# `tenant_config.X = Y` access pattern throughout — not a fixed-column table).
_DDL_TENANT_CONFIG = (
    "CREATE TABLE IF NOT EXISTS tenant_config ("
    " key TEXT PRIMARY KEY,"
    " value TEXT NOT NULL,"
    " updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
    ")"
)

# scoring_weight_overrides: per-tenant key-value override map for scoring §6
# weight tuples. Concrete tuple keys are scoring-doc owned; the table is
# key-value so weight changes don't require migrations.
_DDL_SCORING_OVERRIDES = (
    "CREATE TABLE IF NOT EXISTS scoring_weight_overrides ("
    " weight_key TEXT PRIMARY KEY,"
    " weight_value REAL NOT NULL,"
    " updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
    ")"
)

# review_queue: shape pinned by deployment §6.2.
_DDL_REVIEW_QUEUE = (
    "CREATE TABLE IF NOT EXISTS review_queue ("
    " staged_id TEXT PRIMARY KEY,"
    " tenant_id TEXT NOT NULL,"
    " source_verb TEXT NOT NULL"
    "   CHECK (source_verb IN ('remember','peer_message')),"
    " source_principal TEXT NOT NULL,"
    " staged_at TEXT NOT NULL,"
    " payload_blob BLOB NOT NULL,"
    " classifier_class TEXT NOT NULL,"
    " classifier_score REAL NOT NULL,"
    " status TEXT NOT NULL"
    "   CHECK (status IN ('pending_review','approved','rejected','expired')),"
    " reviewer_principal TEXT,"
    " reviewed_at TEXT,"
    " review_reason TEXT,"
    " expires_at TEXT NOT NULL"
    ")"
)

# idempotency_keys: pinned by api §1.2 + invariant I-5.
_DDL_IDEMPOTENCY_KEYS = (
    "CREATE TABLE IF NOT EXISTS idempotency_keys ("
    " key TEXT PRIMARY KEY,"
    " verb TEXT NOT NULL,"
    " response_blob BLOB,"
    " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
    " expires_at TEXT NOT NULL"
    ")"
)

# S5 consolidation log (lives inside S2 per facilitator §(g) lock).
_DDL_S5_LOG = (
    f"CREATE TABLE IF NOT EXISTS {S5_LOG_TABLE_NAME} ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " kind TEXT NOT NULL,"
    " payload_json TEXT NOT NULL,"
    " appended_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
    ")"
)

_DDL_META = (
    "CREATE TABLE IF NOT EXISTS _lethe_meta ("
    " key TEXT PRIMARY KEY,"
    " value TEXT NOT NULL"
    ")"
)


def open_connection(db_path: Path) -> sqlite3.Connection:
    """Open a per-tenant S2 SQLite connection with WAL + crash-safety pragmas.

    Pragmas chosen per composition §7 row "S2 SQLite down or locked" mitigation:
    ``journal_mode=WAL``, ``synchronous=NORMAL``, ``foreign_keys=ON``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@dataclass(frozen=True)
class S2Schema:
    """Per-tenant S2 file location + schema-creation entry point."""

    tenant_root: Path

    @property
    def db_path(self) -> Path:
        return self.tenant_root / "s2_meta.sqlite"

    def create(self) -> sqlite3.Connection:
        """Create the S2 schema (idempotent). Returns the open connection."""
        conn = open_connection(self.db_path)
        conn.execute(_DDL_META)
        for name in S2_TABLE_NAMES:
            if name in _STUB_TABLES:
                conn.execute(_DDL_STUB.format(name=name))
            elif name == "tenant_config":
                conn.execute(_DDL_TENANT_CONFIG)
            elif name == "scoring_weight_overrides":
                conn.execute(_DDL_SCORING_OVERRIDES)
            elif name == "review_queue":
                conn.execute(_DDL_REVIEW_QUEUE)
            elif name == "idempotency_keys":
                conn.execute(_DDL_IDEMPOTENCY_KEYS)
            else:
                # Defensive: if a name is added to S2_TABLE_NAMES without a
                # matching DDL branch, fail loudly rather than silently drop.
                raise RuntimeError(f"S2 table {name!r} has no DDL branch")
        conn.execute(_DDL_S5_LOG)
        conn.execute(
            "INSERT OR REPLACE INTO _lethe_meta(key, value) VALUES ('schema_version', '1')"
        )
        return conn
