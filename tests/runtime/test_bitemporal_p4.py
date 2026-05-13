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
