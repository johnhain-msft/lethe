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
- v4 (P4): ``consolidation_state`` + ``promotion_flags`` + ``utility_events``
  columned per facilitator P4 plan §(c) (kickoff §6 open item A — the
  utility-tally freeze surface from scoring §6.4 needs a real write
  surface, not a stub). All three are stubs at v3; drop-and-recreate is
  safe (no verb writes to them before P4). The P5 ``promote`` verb
  consumes ``promotion_flags`` (IMPL §2.5); column shape is shared.

Future: P5 → ``promotion_flags`` writes from the ``promote`` verb +
``recall_ledger`` extensions (ALTER discipline; rows exist); P7 →
``review_queue`` indexes; etc.

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
# P4 columns ``consolidation_state`` + ``promotion_flags`` + ``utility_events``
# (per facilitator P4 plan §(c) + kickoff §6 open item A); the set is now
# empty — every named table in :data:`S2_TABLE_NAMES` has a real shape.
_STUB_TABLES: frozenset[str] = frozenset()

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

# consolidation_state: per-tenant lock state + last-run cursor (P4; gap-01
# §3.2 + gap-08 §3.4 → deployment §4.2). PK is ``tenant_id`` so each
# tenant has at most one row; the row is created lazily on first acquire
# attempt (or by the loop's first run). Lock columns are NULL when the
# lock is free; ``last_run_*`` columns are NULL until the first consolidate
# completes; ``cascade_cost_99pct`` is NULL until the first run accumulates
# enough population to compute it (gravity.py uses 0 as the multiplier
# floor when the percentile is unknown — see scoring §3.6).
#
# Acquire / extend / break semantics live in ``runtime/consolidate/scheduler.py``
# via ``BEGIN IMMEDIATE`` + a single conditional UPDATE (composition §5;
# kickoff §D4). All timestamp columns are S2-state native (``created_at`` /
# ``updated_at`` style) — NOT bi-temporal (QA-G1 §B.6).
_DDL_CONSOLIDATION_STATE = (
    "CREATE TABLE IF NOT EXISTS consolidation_state ("
    " tenant_id TEXT PRIMARY KEY,"
    " lock_token TEXT,"
    " lock_acquired_at TEXT,"
    " lock_heartbeat_at TEXT,"
    " last_run_cursor TEXT,"
    " last_run_at TEXT,"
    " cascade_cost_99pct REAL,"
    " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
    " updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
    ")"
)

# promotion_flags: per-(tenant, fact) flag consumed at the next consolidate
# run (IMPL §2.4 + §2.5). Columned at P4 so consolidate's promote /
# demote / invalidate phases can write outcomes; the P5 ``promote`` verb
# also writes via this same shape (kickoff §D8 sequencing). ``tier``
# values are open at v4 (consolidate writes 'promoted' / 'demoted' /
# 'invalidated'; promote verb writes 'promoted'); locking the enum is
# deferred to P5 when the verb-side semantics land. ``flag_set_by`` is
# the consolidate run-id or a verb-tag string (e.g. ``user:promote``).
# All timestamps are S2-state native (QA-G1 §B.6).
_DDL_PROMOTION_FLAGS = (
    "CREATE TABLE IF NOT EXISTS promotion_flags ("
    " tenant_id TEXT NOT NULL,"
    " fact_id TEXT NOT NULL,"
    " tier TEXT NOT NULL,"
    " flag_set_at TEXT NOT NULL,"
    " flag_set_by TEXT NOT NULL,"
    " reason TEXT,"
    " PRIMARY KEY (tenant_id, fact_id)"
    ")"
)

# utility_events: per-fact downstream-feedback events (gap-02 §3 + scoring
# §3.3 + §6.4). Columned at P4 because the δ-term in the consolidate-time
# additive score (scoring §3) requires a real read surface, and the
# §6.4 utility-tally freeze on invalidate requires a per-row mutability
# surface (the ``frozen`` flag). The ``event_kind`` enum is locked here
# at exactly the five values from scoring §3.3 (per-event weight table);
# ``event_weight`` is the resolved per-event weight (caller may override
# the §3.3 default when needed).  Timestamps are S2-state native — not
# bi-temporal (QA-G1 §B.6); ``ts_recorded`` is the event time used by the
# §3.3 exponential-decay aggregation ``Σ_e w_event · exp(-(t_now-e.t)/τ_u)``.
_DDL_UTILITY_EVENTS = (
    "CREATE TABLE IF NOT EXISTS utility_events ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " tenant_id TEXT NOT NULL,"
    " fact_id TEXT NOT NULL,"
    " event_kind TEXT NOT NULL"
    "   CHECK (event_kind IN"
    "     ('citation','tool_success','correction','repeat_recall','no_op')),"
    " event_weight REAL NOT NULL,"
    " ts_recorded TEXT NOT NULL,"
    " frozen INTEGER NOT NULL DEFAULT 0"
    "   CHECK (frozen IN (0,1))"
    ")"
)

# Composite index for the consolidate-time aggregation read pattern
# ``SELECT … FROM utility_events WHERE tenant_id=? AND fact_id=? AND
# ts_recorded >= ?``. Created alongside the table at v4 so the consolidate
# δ-term hot path is indexed from day one; adding it later would require a
# P5+ ALTER (per migrations.py docstring discipline).
_DDL_UTILITY_EVENTS_INDEX = (
    "CREATE INDEX IF NOT EXISTS ix_utility_events_tenant_fact_ts"
    " ON utility_events (tenant_id, fact_id, ts_recorded)"
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

_DDL_META = "CREATE TABLE IF NOT EXISTS _lethe_meta ( key TEXT PRIMARY KEY, value TEXT NOT NULL)"


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
            elif name == "consolidation_state":
                conn.execute(_DDL_CONSOLIDATION_STATE)
            elif name == "promotion_flags":
                conn.execute(_DDL_PROMOTION_FLAGS)
            elif name == "utility_events":
                conn.execute(_DDL_UTILITY_EVENTS)
                conn.execute(_DDL_UTILITY_EVENTS_INDEX)
            else:
                # Defensive: if a name is added to S2_TABLE_NAMES without a
                # matching DDL branch, fail loudly rather than silently drop.
                raise RuntimeError(f"S2 table {name!r} has no DDL branch")
        conn.execute(_DDL_S5_LOG)
        conn.execute(
            "INSERT OR REPLACE INTO _lethe_meta(key, value) VALUES ('schema_version', '4')"
        )
        return conn
