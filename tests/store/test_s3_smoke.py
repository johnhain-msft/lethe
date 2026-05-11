"""S3 smoke: sqlite-vec extension loadable; vec0 + sidecar key table created."""

from __future__ import annotations

from pathlib import Path

import pytest

from lethe.store.s3_vec import S3Client, S3Config


def _table_names(conn) -> set[str]:  # type: ignore[no-untyped-def]
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def test_s3_bootstrap_creates_schema(tenant_root: Path) -> None:
    client = S3Client(tenant_root, config=S3Config(dim=128, ann_ef_search=32))
    conn = client.bootstrap()
    try:
        names = _table_names(conn)
        assert "embeddings" in names
        assert "embedding_keys" in names
        assert client.config.dim == 128
        assert client.config.ann_ef_search == 32
    finally:
        client.close()


def test_s3_default_config() -> None:
    cfg = S3Config()
    assert cfg.dim == 768
    assert cfg.ann_ef_search == 64


def test_s3_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match="dim"):
        S3Config(dim=0)
    with pytest.raises(ValueError, match="ef_search"):
        S3Config(dim=768, ann_ef_search=-1)


def test_s3_embedding_keys_check_constraint(tenant_root: Path) -> None:
    """Exactly one of (node_id, edge_id, episode_id) must be non-null."""
    import sqlite3

    client = S3Client(tenant_root)
    conn = client.bootstrap()
    try:
        # Two ids set -> CHECK violation.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO embedding_keys(rowid, node_id, edge_id, episode_id) "
                "VALUES (1, 'n', 'e', NULL)"
            )
        # All-null -> CHECK violation.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO embedding_keys(rowid, node_id, edge_id, episode_id) "
                "VALUES (2, NULL, NULL, NULL)"
            )
        # Exactly one set -> ok.
        conn.execute(
            "INSERT INTO embedding_keys(rowid, node_id, edge_id, episode_id) "
            "VALUES (3, 'n', NULL, NULL)"
        )
    finally:
        client.close()
