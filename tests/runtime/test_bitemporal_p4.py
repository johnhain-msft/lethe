"""QA-G1 §B.6 bi-temporal explicit-no-op assertions for P4 (C5 surfaces).

QA-G1 §B.6: "EVERY P4 call site that touches S2 / S3 / S5 / extraction_log
must explicitly NOT carry bi-temporal stamps unless the doc declares it
should." Bi-temporal stamping (``valid_from`` / ``valid_to`` per
composition §1 row 48) is a property of CANONICAL S1 facts and the S1
supersession edge — NOT of write-side derived state (extraction_log,
embeddings, embedding_keys, consolidation_state, promotion_flags,
utility_events, S5 consolidation log).

C5 surfaces that this file currently asserts:

- ``main.extraction_log`` schema (no ``valid_from`` / ``valid_to``).
- ``main.consolidation_state`` schema (no ``valid_from`` / ``valid_to``;
  cursor advance uses the native ``last_run_at`` + ``updated_at`` cols).
- ``s3.embeddings`` schema (no bi-temporal cols by construction —
  vec0 has no metadata cols).
- ``s3.embedding_keys`` schema (only the four key cols).

Will be APPENDED to at C6 (promote / demote / invalidate phases) +
C7 (loop). Don't rewrite — only add new test functions for new surfaces.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from lethe.runtime import bootstrap
from lethe.runtime.consolidate import run_extract
from lethe.store import shared_store_connection
from lethe.store.s1_graph.client import S1Client, _InMemoryGraphBackend
from lethe.store.s3_vec.client import S3Client

DIM = 768
BITEMPORAL_COLS = {"valid_from", "valid_to"}


class _Embedder:
    def __call__(self, *, tenant_id: str, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[0.0] * DIM for _ in texts]


def _bootstrap(lethe_home: Path) -> tuple[Path, S1Client, _InMemoryGraphBackend]:
    bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    backend = _InMemoryGraphBackend()
    s1 = S1Client(backend, tenant_id="smoke-tenant")
    s1.bootstrap()
    return lethe_home / "tenants" / "smoke-tenant", s1, backend


def _columns(conn: sqlite3.Connection, qualified_table: str) -> set[str]:
    """Return column-name set for an attached or main-schema table.

    SQLite syntax for schema-qualified ``PRAGMA table_info`` is
    ``PRAGMA <schema>.table_info(<table>)`` — NOT
    ``PRAGMA table_info(<schema>.<table>)``.
    """
    if "." in qualified_table:
        schema, table = qualified_table.split(".", 1)
        rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    else:
        rows = conn.execute(f"PRAGMA table_info({qualified_table})").fetchall()
    return {r[1] for r in rows}


# ---------- C5 surface: extraction_log ---------- #


def test_extraction_log_has_no_bitemporal_columns(lethe_home: Path) -> None:
    """``extraction_log`` is write-side derived state — bi-temporal stamps would
    misrepresent its semantics (the row records WHEN extraction happened, not
    a fact's lifetime)."""
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "main.extraction_log")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"extraction_log unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_extraction_log_row_carries_native_extracted_at_only(lethe_home: Path) -> None:
    """The C5 stub flow writes ``extracted_at`` (S2-state native) — never
    ``valid_from`` / ``valid_to``."""
    tenant_root, s1, backend = _bootstrap(lethe_home)
    backend.add_episode(
        group_id=s1.tenant_id,
        episode_id="ep-1",
        body="hi",
        source_uri="test://",
        ts_recorded="2026-01-01T00:00:00Z",
        intent="remember:general",
    )
    run_extract(
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=_Embedder(),
        s3_client=S3Client(tenant_root=tenant_root),
    )
    with shared_store_connection(tenant_root) as conn:
        # No SELECT on valid_from/valid_to should resolve — they don't exist.
        row = conn.execute("SELECT episode_id, extracted_at FROM main.extraction_log").fetchone()
        assert row[0] == "ep-1"
        assert row[1] is not None


# ---------- C5 surface: consolidation_state ---------- #


def test_consolidation_state_has_no_bitemporal_columns(lethe_home: Path) -> None:
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "main.consolidation_state")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"consolidation_state unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_consolidation_state_uses_native_timestamp_cols_only(lethe_home: Path) -> None:
    """Cursor advance uses ``last_run_at`` + ``updated_at`` — both S2-state
    native; never ``valid_to`` on a 'consumed' cursor."""
    tenant_root, s1, backend = _bootstrap(lethe_home)
    backend.add_episode(
        group_id=s1.tenant_id,
        episode_id="ep-1",
        body="x",
        source_uri="test://",
        ts_recorded="2026-01-01T00:00:00Z",
        intent="remember:general",
    )
    run_extract(
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=_Embedder(),
        s3_client=S3Client(tenant_root=tenant_root),
    )
    with shared_store_connection(tenant_root) as conn:
        row = conn.execute(
            "SELECT last_run_cursor, last_run_at, updated_at "
            "FROM main.consolidation_state WHERE tenant_id = 'smoke-tenant'"
        ).fetchone()
        assert all(v is not None for v in row)


# ---------- C5 surface: s3.embeddings + s3.embedding_keys ---------- #


def test_s3_embeddings_has_no_bitemporal_columns(lethe_home: Path) -> None:
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "s3.embeddings")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"s3.embeddings unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_s3_embedding_keys_has_no_bitemporal_columns(lethe_home: Path) -> None:
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "s3.embedding_keys")
        # Embedding keys carry only the four shape cols (rowid + 3 slots).
        assert cols == {"rowid", "node_id", "edge_id", "episode_id"}, (
            f"s3.embedding_keys columns drifted: {cols}"
        )
        assert BITEMPORAL_COLS.isdisjoint(cols)


# ---------- C6 surfaces: phase impls (promote / demote / invalidate) ---------- #
#
# Per QA-G1 §B.6 + §k.11: bi-temporal stamping at C6 is a property of S1
# (the canonical ``valid_to`` write at demote / invalidate); ``promotion_flags``
# + ``utility_events`` + ``s5_consolidation_log`` use S2-state native
# timestamps (``flag_set_at`` / ``ts_recorded`` / ``appended_at``) and
# explicitly DO NOT carry bi-temporal columns.


def _seeded_s1(
    lethe_home: Path, fact_ids: list[str]
) -> tuple[Path, S1Client, _InMemoryGraphBackend]:
    """Bootstrap a tenant + seed N S1 facts (no ``valid_to`` at start)."""
    tenant_root, s1, backend = _bootstrap(lethe_home)
    for fid in fact_ids:
        backend._seed_fact(
            group_id=s1.tenant_id,
            fact_id=fid,
            valid_from="2026-01-01T00:00:00Z",
        )
    return tenant_root, s1, backend


def test_promotion_flags_has_no_bitemporal_columns(lethe_home: Path) -> None:
    """``promotion_flags`` records a verb decision; bi-temporal stamps would
    misrepresent its semantics (the row records WHEN a tier was set on a
    fact, not the fact's lifetime — that's S1)."""
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "main.promotion_flags")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"promotion_flags unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_utility_events_has_no_bitemporal_columns(lethe_home: Path) -> None:
    """``utility_events`` rows record event arrivals; bi-temporal stamps would
    misrepresent its semantics (per scoring §3.3 the read-side aggregator
    uses ``ts_recorded`` + ``frozen``, never ``valid_from``/``valid_to``)."""
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "main.utility_events")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"utility_events unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_s5_consolidation_log_has_no_bitemporal_columns(lethe_home: Path) -> None:
    """The S5 consolidation log records appends; ``appended_at`` is the
    S2-state native timestamp — never bi-temporal."""
    _bootstrap(lethe_home)
    with shared_store_connection(lethe_home / "tenants" / "smoke-tenant") as conn:
        cols = _columns(conn, "main.s5_consolidation_log")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"s5_consolidation_log unexpectedly has bi-temporal columns: {cols & BITEMPORAL_COLS}"
        )


def test_demote_writes_s1_valid_to(lethe_home: Path) -> None:
    """Positive bi-temporal assertion — demote.py DOES stamp ``valid_to`` on
    S1 (composition §1 row 48 + scoring §6); the canonical bi-temporal
    surface lives on S1, NOT on S2 (promotion_flags does not get a
    ``valid_to`` column even though demote ran)."""
    from lethe.runtime.consolidate import demote

    tenant_root, s1, backend = _seeded_s1(lethe_home, ["fact-1"])
    valid_to = "2026-06-01T00:00:00Z"
    demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.05},
        decisions={"fact-1": "score_below_theta_demote"},
        run_id="consolidate-run-test-001",
        valid_to=valid_to,
    )
    rec = backend._facts[s1.tenant_id]["fact-1"]
    assert rec.valid_to == valid_to


def test_invalidate_writes_s1_valid_to_only(lethe_home: Path) -> None:
    """Per IMPLEMENT 6 amendment A3: invalidate stamps S1 ``valid_to`` and
    writes ``promotion_flags(tier='invalidated')`` + S5 entry. It does
    NOT touch ``utility_events`` (the ``frozen`` column is a write-side
    defense for FUTURE events whose ``ts_recorded > fact.valid_to``;
    it lives at the future utility-event writer, not at invalidate-time).
    """
    from lethe.runtime.consolidate import invalidate

    tenant_root, s1, backend = _seeded_s1(lethe_home, ["fact-1"])
    valid_to = "2026-06-01T00:00:00Z"
    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        decisions={"fact-1": "contradiction_detected"},
        superseded_by={"fact-1": None},
        run_id="consolidate-run-test-001",
        valid_to=valid_to,
    )
    # S1 stamped.
    rec = backend._facts[s1.tenant_id]["fact-1"]
    assert rec.valid_to == valid_to
    # S2 promotion_flags row written.
    with shared_store_connection(tenant_root) as conn:
        flag = conn.execute(
            "SELECT tier FROM main.promotion_flags WHERE fact_id = 'fact-1'"
        ).fetchone()
        assert flag is not None and flag[0] == "invalidated"
        # S5 entry written.
        log_count = conn.execute(
            "SELECT COUNT(*) FROM main.s5_consolidation_log WHERE kind = 'invalidate'"
        ).fetchone()[0]
        assert log_count == 1


def test_invalidate_does_not_modify_utility_events_at_c6(lethe_home: Path) -> None:
    """Per IMPLEMENT 6 amendment A3: invalidate at C6 does NOT touch
    ``utility_events`` — neither INSERTs new rows nor UPDATEs existing
    ones. Seed N rows for a fact, call invalidate, assert the row count
    AND the column values are byte-identical pre- and post-invalidate.

    Per scoring §6.4 the ``frozen`` write-side defense for FUTURE events
    lives at the utility-event writer (which observes the invalidate
    stamp and sets ``frozen=1`` on incoming rows whose
    ``ts_recorded > fact.valid_to``), not at invalidate-time.
    """
    from lethe.runtime.consolidate import invalidate

    tenant_root, s1, backend = _seeded_s1(lethe_home, ["fact-1", "fact-2"])
    # Seed 3 utility_events rows (2 for fact-1, 1 for fact-2) BEFORE invalidate.
    with shared_store_connection(tenant_root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT INTO main.utility_events "
            "(tenant_id, fact_id, event_kind, event_weight, ts_recorded, frozen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (s1.tenant_id, "fact-1", "citation", 1.0, "2026-02-01T00:00:00Z", 0),
                (s1.tenant_id, "fact-1", "tool_success", 0.5, "2026-03-01T00:00:00Z", 0),
                (s1.tenant_id, "fact-2", "citation", 1.0, "2026-02-15T00:00:00Z", 0),
            ],
        )
        conn.execute("COMMIT")
        before = conn.execute(
            "SELECT id, tenant_id, fact_id, event_kind, event_weight, ts_recorded, frozen "
            "FROM main.utility_events ORDER BY id"
        ).fetchall()

    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        decisions={"fact-1": "score_below_floor"},
        superseded_by={"fact-1": None},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
    )

    with shared_store_connection(tenant_root) as conn:
        after = conn.execute(
            "SELECT id, tenant_id, fact_id, event_kind, event_weight, ts_recorded, frozen "
            "FROM main.utility_events ORDER BY id"
        ).fetchall()
    assert before == after, (
        "utility_events rows changed during invalidate at C6 (must be byte-identical "
        "per IMPLEMENT 6 amendment A3)"
    )


def test_promote_does_not_touch_s1_valid_to(lethe_home: Path) -> None:
    """Negative bi-temporal assertion — promote.py is an S2-only event.
    Promotion does NOT retire a fact (S1 ``valid_to`` stays NULL); only
    demote / invalidate stamp ``valid_to`` on S1."""
    from lethe.runtime.consolidate import promote

    tenant_root, s1, backend = _seeded_s1(lethe_home, ["fact-1"])
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
    )
    rec = backend._facts[s1.tenant_id]["fact-1"]
    assert rec.valid_to is None, (
        f"promote unexpectedly stamped S1 valid_to={rec.valid_to!r}; "
        f"promote is an S2-only event (composition §1 row 48 + §c)"
    )


# ---------- C7 APPEND per IMPLEMENT 7 — gate 25 + A1 lock-columns native ---------- #


def test_consolidation_state_lock_columns_after_acquire_are_native(
    lethe_home: Path,
) -> None:
    """Gate 25: after :func:`acquire_lock`, the lock columns
    (``lock_token``, ``lock_acquired_at``, ``lock_heartbeat_at``) are
    native ISO strings — NOT bi-temporal ``valid_from`` / ``valid_to``.
    Per A1 the ``last_run_at`` column stays NULL on a bare acquire (no
    successful run yet); only ``mark_success_and_release`` advances it.
    """
    from datetime import UTC, datetime

    from lethe.runtime.consolidate import acquire_lock

    _bootstrap(lethe_home)
    tenant_root = lethe_home / "tenants" / "smoke-tenant"
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    token = acquire_lock(tenant_id="smoke-tenant", tenant_root=tenant_root, now=fixed_now)

    with shared_store_connection(tenant_root) as conn:
        cols = _columns(conn, "main.consolidation_state")
        assert BITEMPORAL_COLS.isdisjoint(cols), (
            f"consolidation_state unexpectedly has bi-temporal cols after acquire: "
            f"{cols & BITEMPORAL_COLS}"
        )
        row = conn.execute(
            "SELECT lock_token, lock_acquired_at, lock_heartbeat_at, last_run_at "
            "FROM main.consolidation_state WHERE tenant_id = 'smoke-tenant'"
        ).fetchone()
    assert row is not None
    lock_token, lock_acquired_at, lock_heartbeat_at, last_run_at = row
    assert lock_token == token
    assert isinstance(lock_acquired_at, str) and lock_acquired_at.endswith("Z")
    assert isinstance(lock_heartbeat_at, str) and lock_heartbeat_at.endswith("Z")
    # Per A1: bare acquire does NOT advance last_run_at
    assert last_run_at is None
