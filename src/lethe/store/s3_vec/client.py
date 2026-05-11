"""S3 client — sqlite-vec adapter.

P1 scope: schema only. ``S3Client.bootstrap()`` loads the ``sqlite-vec``
loadable extension into a per-tenant SQLite file and creates two tables:

- ``embeddings`` — a ``vec0`` virtual table keyed by ``rowid`` with a
  ``embedding float[<dim>]`` column. Vector ANN happens here (P3+).
- ``embedding_keys`` — sidecar table mapping ``rowid`` → composite key
  ``(node_id, edge_id, episode_id)`` per composition §2 row 3.

Embedding generation, ANN config tuning, and rebuild-on-divergence land
in P3 (read path).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec


@dataclass(frozen=True)
class S3Config:
    """Per-tenant S3 configuration knobs.

    ``dim`` is the embedding dimensionality (e.g. 768 for many BGE-class
    models, 1536 for OpenAI ada-002). It is fixed at bootstrap time because
    sqlite-vec ``vec0`` declares the column shape in DDL; switching ``dim``
    requires rebuilding the index (composition §5 "S3 is rebuildable").

    ``ann_ef_search`` is a placeholder ANN-tuning knob. sqlite-vec's brute-
    force scoring path doesn't use it today; the field exists so the P3
    rebuild path has a stable knob to surface to operators.
    """

    dim: int = 768
    ann_ef_search: int = 64

    def __post_init__(self) -> None:
        if self.dim <= 0:
            raise ValueError(f"S3Config.dim must be positive, got {self.dim}")
        if self.ann_ef_search <= 0:
            raise ValueError(
                f"S3Config.ann_ef_search must be positive, got {self.ann_ef_search}"
            )


class S3Client:
    """Per-tenant S3 vector-index client.

    P1 contract: ``bootstrap()`` is idempotent and creates the schema.
    ``add()`` / ``query()`` land in P3.
    """

    def __init__(self, tenant_root: Path, config: S3Config | None = None) -> None:
        self._tenant_root = tenant_root
        self._config = config if config is not None else S3Config()
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self._tenant_root / "s3_vec.sqlite"

    @property
    def config(self) -> S3Config:
        return self._config

    def bootstrap(self) -> sqlite3.Connection:
        """Open the S3 SQLite file, load ``sqlite-vec``, and create the schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS embeddings "
            f"USING vec0(embedding float[{self._config.dim}])"
        )
        # Sidecar key table mirrors `rowid` → composite key per composition §2.
        # Exactly one of (node_id, edge_id, episode_id) must be non-null; the
        # check enforces "embedding-key shape" at write time.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embedding_keys ("
            " rowid INTEGER PRIMARY KEY,"
            " node_id TEXT,"
            " edge_id TEXT,"
            " episode_id TEXT,"
            " CHECK ("
            "   (node_id IS NOT NULL) + (edge_id IS NOT NULL) + (episode_id IS NOT NULL) = 1"
            " )"
            ")"
        )
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
