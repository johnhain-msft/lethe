"""S2 schema: 10 named tables (IMPL §2.1) + the S5 consolidation log table.

Column shapes evolve via :mod:`lethe.store.s2_meta.migrations` as each
table's owning verb lands. Schema version history:

- v1 (P1): ``review_queue`` + ``idempotency_keys`` shaped; six other named
  tables (``recall_ledger``, ``utility_events``, ``promotion_flags``,
  ``consolidation_state``, ``extraction_log``, ``audit_log``) ship as
  ``(id, created_at)`` stubs; ``tenant_config`` + ``scoring_weight_overrides``
  are key-value.
- v2 (P2): ``extraction_log`` columned per gap-06 minimal scaffold;
  ``audit_log`` columned for the ``force_skip_classifier_invoked`` row
  (deployment §6.3 + facilitator P2 sub-plan §6).
- v3 (P3): ``recall_ledger`` columned per facilitator P3 plan §(d) —
  one row per ``recall`` invocation, keyed by the deterministic api
  §1.4 ``recall_id``.

Future: P4 → ``consolidation_state``; P5 → ``promotion_flags`` +
``recall_ledger`` extensions; P7 → review_queue indexes; etc.

A ``meta_version`` sentinel row tracks schema version so :mod:`.migrations`
can ratchet existing databases forward without dropping data on already-shaped
tables.
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

# Tables that still get a minimal `(id, created_at)` stub. See module docstring
# for why we don't speculate on real columns yet.
#
# P2 columns ``extraction_log`` (per gap-06; minimal scaffold so P3+ doesn't
# need a re-migration) and ``audit_log`` (per deployment §6.3 + api §3.1
# ``force_skip_classifier=true`` audit row), so both are dropped from this set.
# P3 columns ``recall_ledger`` (per facilitator P3 plan §(d)); shrinks again.
_STUB_TABLES: frozenset[str] = frozenset(
    {
        "utility_events",
        "promotion_flags",
        "consolidation_state",
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

# extraction_log: P2 minimal scaffold per facilitator plan §(c) closing line.
# gap-06 owns extraction-confidence semantics; this shape is the seam P3+
# extraction wire-up consumes without needing a re-migration.
_DDL_EXTRACTION_LOG = (
    "CREATE TABLE IF NOT EXISTS extraction_log ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " episode_id TEXT NOT NULL,"
    " extracted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
    " extractor_version TEXT NOT NULL,"
    " confidence REAL NOT NULL,"
    " payload_blob BLOB NOT NULL"
    ")"
)

# audit_log: P2 minimal columns per facilitator plan §6 (sub-plan).
# Records the `force_skip_classifier_invoked` row at P2; deployment §6.3's
# `review_approved{...}` row has its own column shape and lands at P7.
_DDL_AUDIT_LOG = (
    "CREATE TABLE IF NOT EXISTS audit_log ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
    " tenant_id TEXT NOT NULL,"
    " verb TEXT NOT NULL,"
    " principal TEXT NOT NULL,"
    " action TEXT NOT NULL,"
    " payload_json TEXT NOT NULL"
    ")"
)

# recall_ledger: P3 fold per facilitator P3 plan §(d). One row per
# `recall` invocation, keyed by the deterministic api §1.4 recall_id.
# The verb does INSERT OR IGNORE on the PK so a legitimate replay (same
# inputs → same recall_id → same payload) is a no-op; same-PK +
# different-payload is treated as a substrate bug at the verb layer.
# `top_k_fact_ids` is a JSON-encoded list[str]; an index lands at P9
# alongside the recall_outcome ingest path.
_DDL_RECALL_LEDGER = (
    "CREATE TABLE IF NOT EXISTS recall_ledger ("
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
            elif name == "extraction_log":
                conn.execute(_DDL_EXTRACTION_LOG)
            elif name == "audit_log":
                conn.execute(_DDL_AUDIT_LOG)
            elif name == "recall_ledger":
                conn.execute(_DDL_RECALL_LEDGER)
            else:
                # Defensive: if a name is added to S2_TABLE_NAMES without a
                # matching DDL branch, fail loudly rather than silently drop.
                raise RuntimeError(f"S2 table {name!r} has no DDL branch")
        conn.execute(_DDL_S5_LOG)
        conn.execute(
            "INSERT OR REPLACE INTO _lethe_meta(key, value) VALUES ('schema_version', '3')"
        )
        return conn
