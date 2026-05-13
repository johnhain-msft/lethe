"""Tests for the consolidate-loop extract → embed pipeline (P4 commit 5).

Covers the full sub-plan §j.9 T2 atomicity test plan + the §c
"all three embedding-key slots exercised" gate via direct unit tests
against :meth:`S3Client.add` (per substrate decision D in §j.11).

Coverage map:

- :class:`Embedder` Protocol contract — :class:`NullEmbedder` raises.
- :meth:`S3Client.add` invariant (§B.5 embedding-key) — exactly-one-of
  (node_id, edge_id, episode_id), all three slots exercised, dim
  mismatch raises before any SQL.
- :meth:`S1Client.episodes_since` façade + composite cursor semantics
  (A5) — same-ts_recorded boundary, strict > compare, ordering.
- :func:`embed_episodes` happy path + dim assertion + signature.
- :func:`embed_nodes` / :func:`embed_edges` — empty no-op + non-empty
  raise (A11).
- :func:`run_extract` end-to-end on a fresh tenant (A1).
- :func:`run_extract` cursor advance + idempotence on second-run.
- :func:`run_extract` T2 ROLLBACK on embedder failure (§j.9):
  extraction_log, s3.embeddings, s3.embedding_keys, last_run_cursor
  ALL revert; subsequent run with a working embedder processes ALL
  episodes (no skip / no double-process).
- :func:`run_extract` UPDATE rowcount=1 assertion (A1).
- :func:`shared_store_connection` itself — ATTACH alias works,
  ROLLBACK is atomic across attached vec0 (smoke gate §j.10 #9).
"""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Sequence
from pathlib import Path

import pytest
import sqlite_vec

from lethe.runtime import bootstrap
from lethe.runtime.consolidate import (
    EXTRACTOR_VERSION,
    Embedder,
    NullEmbedder,
    embed_edges,
    embed_episodes,
    embed_nodes,
    run_extract,
)
from lethe.store import shared_store_connection
from lethe.store.s1_graph.client import (
    EpisodeRecord,
    S1Client,
    _InMemoryGraphBackend,
)
from lethe.store.s3_vec.client import S3Client

DIM = 768  # matches S3Config default


# ---------- helpers ---------- #


def _bootstrap_tenant(lethe_home: Path, tenant_id: str = "smoke-tenant") -> Path:
    bootstrap(tenant_id=tenant_id, storage_root=lethe_home)
    return lethe_home / "tenants" / tenant_id


def _build_s1_client(tenant_id: str = "smoke-tenant") -> tuple[S1Client, _InMemoryGraphBackend]:
    backend = _InMemoryGraphBackend()
    client = S1Client(backend, tenant_id=tenant_id)
    client.bootstrap()
    return client, backend


def _add_episode(
    client: S1Client,
    backend: _InMemoryGraphBackend,
    *,
    episode_id: str,
    body: str,
    ts_recorded: str,
    intent: str = "remember:general",
    source_uri: str = "test://ep",
) -> None:
    backend.add_episode(
        group_id=client.tenant_id,
        episode_id=episode_id,
        body=body,
        source_uri=source_uri,
        ts_recorded=ts_recorded,
        intent=intent,
    )


class _DeterministicEmbedder:
    """Returns a unit-vector-per-text whose first dim element encodes len(text)."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim
        self.calls = 0

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        self.calls += 1
        out: list[list[float]] = []
        for t in texts:
            v = [0.0] * self.dim
            v[0] = float(len(t))
            out.append(v)
        return out


class _EmbedderFailureForTest(RuntimeError):
    """Sentinel exception for the §j.9 T2 atomicity test."""


class _FailingEmbedder:
    """Returns valid vectors for the first call; raises on the second."""

    def __init__(self, dim: int = DIM, fail_after_calls: int = 1) -> None:
        self.dim = dim
        self.fail_after_calls = fail_after_calls
        self.calls = 0

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        self.calls += 1
        if self.calls > self.fail_after_calls:
            raise _EmbedderFailureForTest(
                f"_FailingEmbedder: deliberate failure on call {self.calls} "
                f"(tenant_id={tenant_id!r})"
            )
        return [[0.0] * self.dim for _ in texts]


class _DimMismatchEmbedder:
    """Returns vectors of the WRONG dim — exercises the dim assertion."""

    def __init__(self, returned_dim: int) -> None:
        self.returned_dim = returned_dim

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        return [[0.0] * self.returned_dim for _ in texts]


def _row_counts(conn: sqlite3.Connection) -> tuple[int, int, int]:
    el = conn.execute("SELECT COUNT(*) FROM main.extraction_log").fetchone()[0]
    em = conn.execute("SELECT COUNT(*) FROM s3.embeddings").fetchone()[0]
    ek = conn.execute("SELECT COUNT(*) FROM s3.embedding_keys").fetchone()[0]
    return el, em, ek


# ---------- (1) Embedder Protocol contract ---------- #


def test_null_embedder_raises_with_p7_pointer() -> None:
    embedder = NullEmbedder()
    with pytest.raises(NotImplementedError, match="P7"):
        embedder(tenant_id="t", texts=["x"])


def test_embedder_protocol_satisfied_by_callable_class() -> None:
    embedder: Embedder = _DeterministicEmbedder()
    out = embedder(tenant_id="t", texts=["hello", "world"])
    assert len(out) == 2
    assert all(len(v) == DIM for v in out)


# ---------- (2) S3Client.add invariants — all 3 slots (§7.9) ---------- #


def _open_attached_conn(tenant_root: Path) -> sqlite3.Connection:
    """Open S2 + ATTACH S3 + load sqlite-vec — small helper for direct add() tests."""
    s2_path = tenant_root / "s2_meta.sqlite"
    s3_path = tenant_root / "s3_vec.sqlite"
    conn = sqlite3.connect(str(s2_path), isolation_level=None)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("ATTACH DATABASE ? AS s3", (str(s3_path),))
    return conn


def test_s3client_add_episode_slot(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        rowid = s3.add(conn=conn, vector=[0.1] * DIM, episode_id="ep-1")
        assert rowid >= 1
        keys = conn.execute(
            "SELECT node_id, edge_id, episode_id FROM s3.embedding_keys WHERE rowid = ?",
            (rowid,),
        ).fetchone()
        assert keys == (None, None, "ep-1")
    finally:
        conn.close()


def test_s3client_add_node_slot(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        rowid = s3.add(conn=conn, vector=[0.0] * DIM, node_id="n-1")
        keys = conn.execute(
            "SELECT node_id, edge_id, episode_id FROM s3.embedding_keys WHERE rowid = ?",
            (rowid,),
        ).fetchone()
        assert keys == ("n-1", None, None)
    finally:
        conn.close()


def test_s3client_add_edge_slot(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        rowid = s3.add(conn=conn, vector=[0.0] * DIM, edge_id="e-1")
        keys = conn.execute(
            "SELECT node_id, edge_id, episode_id FROM s3.embedding_keys WHERE rowid = ?",
            (rowid,),
        ).fetchone()
        assert keys == (None, "e-1", None)
    finally:
        conn.close()


def test_s3client_add_rejects_no_slot(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        with pytest.raises(ValueError, match="exactly one"):
            s3.add(conn=conn, vector=[0.0] * DIM)
    finally:
        conn.close()


def test_s3client_add_rejects_two_slots(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        with pytest.raises(ValueError, match="exactly one"):
            s3.add(conn=conn, vector=[0.0] * DIM, node_id="n", episode_id="e")
    finally:
        conn.close()


def test_s3client_add_rejects_three_slots(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        with pytest.raises(ValueError, match="exactly one"):
            s3.add(
                conn=conn,
                vector=[0.0] * DIM,
                node_id="n",
                edge_id="e",
                episode_id="ep",
            )
    finally:
        conn.close()


def test_s3client_add_rejects_dim_mismatch(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = _open_attached_conn(tenant_root)
    try:
        with pytest.raises(ValueError, match="dim"):
            s3.add(conn=conn, vector=[0.0] * (DIM - 1), episode_id="ep")
    finally:
        conn.close()


def test_s3client_add_main_schema_for_standalone(lethe_home: Path) -> None:
    """Standalone S3 connection writes via schema='main'."""
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    conn = sqlite3.connect(str(s3.db_path), isolation_level=None)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    try:
        rowid = s3.add(conn=conn, vector=[0.0] * DIM, schema="main", episode_id="ep-2")
        assert rowid >= 1
        n = conn.execute("SELECT COUNT(*) FROM main.embeddings").fetchone()[0]
        assert n == 1
    finally:
        conn.close()


# ---------- (3) S1Client.episodes_since + composite cursor (A5/A10) ---------- #


def test_episodes_since_none_returns_all_sorted() -> None:
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="b", body="B", ts_recorded="2026-01-02T00:00:00Z")
    _add_episode(s1, backend, episode_id="a", body="A", ts_recorded="2026-01-01T00:00:00Z")
    out = list(s1.episodes_since(since_cursor=None))
    assert [e.episode_id for e in out] == ["a", "b"]


def test_episodes_since_strict_greater_than_cursor() -> None:
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="a", body="A", ts_recorded="2026-01-01T00:00:00Z")
    _add_episode(s1, backend, episode_id="b", body="B", ts_recorded="2026-01-02T00:00:00Z")
    cursor = "2026-01-01T00:00:00Z\ta"
    out = list(s1.episodes_since(since_cursor=cursor))
    assert [e.episode_id for e in out] == ["b"]


def test_episodes_since_same_ts_recorded_disambiguates_by_episode_id() -> None:
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-z", body="Z", ts_recorded="2026-01-01T00:00:00Z")
    _add_episode(s1, backend, episode_id="ep-a", body="A", ts_recorded="2026-01-01T00:00:00Z")
    out = list(s1.episodes_since(since_cursor=None))
    assert [e.episode_id for e in out] == ["ep-a", "ep-z"]
    cursor_after_first = "2026-01-01T00:00:00Z\tep-a"
    out2 = list(s1.episodes_since(since_cursor=cursor_after_first))
    assert [e.episode_id for e in out2] == ["ep-z"]


def test_episodes_since_returns_episode_record_dataclass() -> None:
    s1, backend = _build_s1_client()
    _add_episode(
        s1,
        backend,
        episode_id="e1",
        body="hello",
        ts_recorded="2026-01-01T00:00:00Z",
        intent="remember:general",
    )
    out = list(s1.episodes_since(since_cursor=None))
    assert len(out) == 1
    assert isinstance(out[0], EpisodeRecord)
    assert out[0].body == "hello"
    assert out[0].intent == "remember:general"


# ---------- (4) embed_episodes / embed_nodes / embed_edges ---------- #


def test_embed_episodes_writes_episode_keyed_rows(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with shared_store_connection(tenant_root) as conn:
        conn.execute("BEGIN")
        rowids = embed_episodes(
            tenant_id="smoke-tenant",
            embedder=embedder,
            conn=conn,
            items=[("ep-1", "hello"), ("ep-2", "world!")],
            s3_client=s3,
        )
        conn.execute("COMMIT")
        assert len(rowids) == 2
        assert embedder.calls == 1  # one batch call, not per-item
        keys = conn.execute("SELECT episode_id FROM s3.embedding_keys ORDER BY rowid").fetchall()
        assert keys == [("ep-1",), ("ep-2",)]


def test_embed_episodes_empty_input_skips_embedder(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with shared_store_connection(tenant_root) as conn:
        out = embed_episodes(
            tenant_id="smoke-tenant",
            embedder=embedder,
            conn=conn,
            items=[],
            s3_client=s3,
        )
        assert out == []
        assert embedder.calls == 0


def test_embed_episodes_dim_mismatch_raises_before_sql(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    bad = _DimMismatchEmbedder(returned_dim=DIM - 1)
    with shared_store_connection(tenant_root) as conn:
        conn.execute("BEGIN")
        with pytest.raises(ValueError, match="dim"):
            embed_episodes(
                tenant_id="smoke-tenant",
                embedder=bad,
                conn=conn,
                items=[("ep-x", "body")],
                s3_client=s3,
            )
        conn.execute("ROLLBACK")
        n = conn.execute("SELECT COUNT(*) FROM s3.embeddings").fetchone()[0]
        assert n == 0


def test_embed_nodes_empty_input_returns_no_op(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with shared_store_connection(tenant_root) as conn:
        out = embed_nodes(tenant_id="t", embedder=embedder, conn=conn, items=[], s3_client=s3)
        assert out == []
        assert embedder.calls == 0


def test_embed_nodes_non_empty_raises_p9_pointer(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with (
        shared_store_connection(tenant_root) as conn,
        pytest.raises(NotImplementedError, match="P9"),
    ):
        embed_nodes(
            tenant_id="t", embedder=embedder, conn=conn, items=[("n1", "body")], s3_client=s3
        )


def test_embed_edges_empty_input_returns_no_op(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with shared_store_connection(tenant_root) as conn:
        out = embed_edges(tenant_id="t", embedder=embedder, conn=conn, items=[], s3_client=s3)
        assert out == []


def test_embed_edges_non_empty_raises_p9_pointer(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    with (
        shared_store_connection(tenant_root) as conn,
        pytest.raises(NotImplementedError, match="P9"),
    ):
        embed_edges(
            tenant_id="t", embedder=embedder, conn=conn, items=[("e1", "body")], s3_client=s3
        )


# ---------- (5) shared_store_connection seam ---------- #


def test_shared_store_connection_attaches_s3_alias(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    with shared_store_connection(tenant_root) as conn:
        # Both schemas resolvable: main.consolidation_state from S2,
        # s3.embeddings from S3.
        n_state = conn.execute("SELECT COUNT(*) FROM main.consolidation_state").fetchone()[0]
        assert n_state == 0
        n_emb = conn.execute("SELECT COUNT(*) FROM s3.embeddings").fetchone()[0]
        assert n_emb == 0


def test_shared_store_connection_rollback_atomic_across_attach(lethe_home: Path) -> None:
    """Spike Test B replicated as a real test (gate §j.10 #9)."""
    tenant_root = _bootstrap_tenant(lethe_home)
    with shared_store_connection(tenant_root) as conn:
        before = _row_counts(conn)
        conn.execute("BEGIN")
        blob = struct.pack(f"{DIM}f", *([0.5] * DIM))
        cur = conn.execute("INSERT INTO s3.embeddings (embedding) VALUES (?)", (blob,))
        rowid = cur.lastrowid
        conn.execute(
            "INSERT INTO s3.embedding_keys (rowid, episode_id) VALUES (?, ?)",
            (rowid, "ep-rb"),
        )
        conn.execute(
            "INSERT INTO main.extraction_log "
            "(episode_id, extracted_at, extractor_version, confidence, payload_blob) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ep-rb", "2026-01-01T00:00:00Z", "test", 1.0, b""),
        )
        conn.execute("ROLLBACK")
        after = _row_counts(conn)
        assert after == before


# ---------- (6) run_extract end-to-end (T2 atomicity §j.9) ---------- #


def test_run_extract_first_run_fresh_tenant_creates_state_row(lethe_home: Path) -> None:
    """A1: INSERT OR IGNORE so a fresh tenant works."""
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-1", body="hi", ts_recorded="2026-01-01T00:00:00Z")
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    n = run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3)
    assert n == 1
    with shared_store_connection(tenant_root) as conn:
        row = conn.execute(
            "SELECT last_run_cursor, last_run_at FROM main.consolidation_state WHERE tenant_id = ?",
            ("smoke-tenant",),
        ).fetchone()
        assert row is not None
        assert row[0] == "2026-01-01T00:00:00Z\tep-1"
        assert row[1] is not None  # last_run_at was stamped
        n_log = conn.execute("SELECT COUNT(*) FROM main.extraction_log").fetchone()[0]
        assert n_log == 1
        n_emb = conn.execute("SELECT COUNT(*) FROM s3.embeddings").fetchone()[0]
        assert n_emb == 1


def test_run_extract_empty_tenant_creates_state_row_then_no_op(lethe_home: Path) -> None:
    """First-run with no episodes: state row created, cursor stays NULL, returns 0."""
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, _ = _build_s1_client()
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    n = run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3)
    assert n == 0
    with shared_store_connection(tenant_root) as conn:
        row = conn.execute(
            "SELECT last_run_cursor FROM main.consolidation_state WHERE tenant_id = ?",
            ("smoke-tenant",),
        ).fetchone()
        assert row == (None,)


def test_run_extract_advances_cursor_idempotent_on_second_run(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-1", body="A", ts_recorded="2026-01-01T00:00:00Z")
    _add_episode(s1, backend, episode_id="ep-2", body="B", ts_recorded="2026-01-02T00:00:00Z")
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    assert run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3) == 2
    # second run: nothing new
    assert run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3) == 0
    # add one more, third run picks it up
    _add_episode(s1, backend, episode_id="ep-3", body="C", ts_recorded="2026-01-03T00:00:00Z")
    assert run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3) == 1
    with shared_store_connection(tenant_root) as conn:
        n = conn.execute("SELECT COUNT(*) FROM main.extraction_log").fetchone()[0]
        assert n == 3
        n_emb = conn.execute("SELECT COUNT(*) FROM s3.embeddings").fetchone()[0]
        assert n_emb == 3


def test_run_extract_same_ts_boundary_no_skip_no_double_process(lethe_home: Path) -> None:
    """A5: composite cursor — two episodes share ts; both get processed exactly once."""
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-a", body="A", ts_recorded="2026-01-01T00:00:00Z")
    _add_episode(s1, backend, episode_id="ep-b", body="B", ts_recorded="2026-01-01T00:00:00Z")
    s3 = S3Client(tenant_root=tenant_root)
    embedder = _DeterministicEmbedder()
    assert run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3) == 2
    # second run: NOTHING (composite cursor disambiguated correctly)
    assert run_extract(tenant_root=tenant_root, s1_client=s1, embedder=embedder, s3_client=s3) == 0
    with shared_store_connection(tenant_root) as conn:
        ids = conn.execute("SELECT episode_id FROM main.extraction_log ORDER BY id").fetchall()
        assert ids == [("ep-a",), ("ep-b",)]


def test_run_extract_t2_rollback_on_embedder_failure(lethe_home: Path) -> None:
    """§j.9 — the central T2 atomicity test.

    Embedder raises mid-run → entire transaction rolls back → all four
    invariants hold simultaneously: no extraction_log rows, no
    s3.embeddings rows, no s3.embedding_keys rows, last_run_cursor IS NULL.
    """
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    for i in range(4):
        _add_episode(
            s1,
            backend,
            episode_id=f"ep-{i}",
            body=f"body-{i}",
            ts_recorded=f"2026-01-0{i + 1}T00:00:00Z",
        )
    s3 = S3Client(tenant_root=tenant_root)
    failing = _FailingEmbedder(fail_after_calls=0)  # raise on the FIRST call
    with pytest.raises(_EmbedderFailureForTest):
        run_extract(tenant_root=tenant_root, s1_client=s1, embedder=failing, s3_client=s3)
    with shared_store_connection(tenant_root) as conn:
        el, em, ek = _row_counts(conn)
        assert el == 0
        assert em == 0
        assert ek == 0
        # state row exists (INSERT OR IGNORE before failure point) but
        # cursor stayed NULL — the row's INSERT OR IGNORE was rolled
        # back too; the row may or may not exist depending on tx
        # boundary. The invariant we care about: cursor IS NULL.
        row = conn.execute(
            "SELECT last_run_cursor FROM main.consolidation_state WHERE tenant_id = ?",
            ("smoke-tenant",),
        ).fetchone()
        assert row is None or row[0] is None


def test_run_extract_after_rollback_re_processes_all_episodes(lethe_home: Path) -> None:
    """Companion to the rollback test: a successful re-run processes ALL episodes,
    no skip from the rolled-back attempt and no double-process."""
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    for i in range(4):
        _add_episode(
            s1,
            backend,
            episode_id=f"ep-{i}",
            body=f"body-{i}",
            ts_recorded=f"2026-01-0{i + 1}T00:00:00Z",
        )
    s3 = S3Client(tenant_root=tenant_root)
    failing = _FailingEmbedder(fail_after_calls=0)
    with pytest.raises(_EmbedderFailureForTest):
        run_extract(tenant_root=tenant_root, s1_client=s1, embedder=failing, s3_client=s3)
    # Now re-run with a working embedder
    good = _DeterministicEmbedder()
    n = run_extract(tenant_root=tenant_root, s1_client=s1, embedder=good, s3_client=s3)
    assert n == 4
    with shared_store_connection(tenant_root) as conn:
        ids = conn.execute("SELECT episode_id FROM main.extraction_log ORDER BY id").fetchall()
        assert ids == [("ep-0",), ("ep-1",), ("ep-2",), ("ep-3",)]


def test_run_extract_writes_stub_extractor_version(lethe_home: Path) -> None:
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-1", body="x", ts_recorded="2026-01-01T00:00:00Z")
    s3 = S3Client(tenant_root=tenant_root)
    run_extract(
        tenant_root=tenant_root, s1_client=s1, embedder=_DeterministicEmbedder(), s3_client=s3
    )
    with shared_store_connection(tenant_root) as conn:
        row = conn.execute(
            "SELECT extractor_version, confidence, payload_blob FROM main.extraction_log"
        ).fetchone()
        assert row[0] == EXTRACTOR_VERSION
        assert row[1] == 1.0
        assert row[2] == b""


def test_run_extract_concurrent_serialized_via_begin_immediate(lethe_home: Path) -> None:
    """A6: BEGIN IMMEDIATE — second concurrent run gets SQLITE_BUSY.

    Hold a tx open on a side connection that already executed
    BEGIN IMMEDIATE; concurrent run_extract should fail to acquire.
    """
    tenant_root = _bootstrap_tenant(lethe_home)
    s1, backend = _build_s1_client()
    _add_episode(s1, backend, episode_id="ep-1", body="x", ts_recorded="2026-01-01T00:00:00Z")
    s3 = S3Client(tenant_root=tenant_root)
    blocker = sqlite3.connect(
        str(tenant_root / "s2_meta.sqlite"), isolation_level=None, timeout=0.1
    )
    try:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked|busy"):
            run_extract(
                tenant_root=tenant_root,
                s1_client=s1,
                embedder=_DeterministicEmbedder(),
                s3_client=s3,
            )
        blocker.execute("ROLLBACK")
    finally:
        blocker.close()
