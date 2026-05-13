"""S3 client — sqlite-vec adapter.

P1 scope: schema only. ``S3Client.bootstrap()`` loads the ``sqlite-vec``
loadable extension into a per-tenant SQLite file and creates two tables:

- ``embeddings`` — a ``vec0`` virtual table keyed by ``rowid`` with a
  ``embedding float[<dim>]`` column. Vector ANN happens here (P3+).
- ``embedding_keys`` — sidecar table mapping ``rowid`` → composite key
  ``(node_id, edge_id, episode_id)`` per composition §2 row 3.

P4 commit 5 scope: typed write helper :meth:`S3Client.add` lands so the
consolidate-loop embed phase persists vectors via a method that
enforces the §B.5 embedding-key invariant (exactly-one-of-three).
The helper takes a ``conn`` (so the cross-store T2 seam can inject the
ATTACH-shared connection) and a ``schema`` selector (default ``"s3"``
for the ATTACH seam; ``"main"`` for standalone unit tests against an
S3-only connection — see A4 in plan §j).

Embedding generation, ANN config tuning, and rebuild-on-divergence land
in P3 (read path).
"""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Sequence
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
            raise ValueError(f"S3Config.ann_ef_search must be positive, got {self.ann_ef_search}")


class S3Client:
    """Per-tenant S3 vector-index client.

    P1 contract: ``bootstrap()`` is idempotent and creates the schema.
    P4 commit 5 contract: ``add()`` lands as a typed write helper for
    the consolidate-loop embed phase. ``query()`` lands in P3 (read path).
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

    def add(
        self,
        *,
        conn: sqlite3.Connection,
        vector: Sequence[float],
        schema: str = "s3",
        node_id: str | None = None,
        edge_id: str | None = None,
        episode_id: str | None = None,
    ) -> int:
        """Insert one vector + sidecar key row; return assigned ``rowid``.

        Writes to ``{schema}.embeddings`` + ``{schema}.embedding_keys``
        (always schema-qualified per A4 in plan §j). ``schema="s3"`` is
        the default — matches the
        :func:`lethe.store.shared_conn.shared_store_connection` ATTACH
        alias. Pass ``schema="main"`` when the caller has opened the S3
        SQLite file directly (e.g. unit tests against ``S3Client.add``
        without the cross-store T2 seam).

        Validations:

        - ``len(vector) == self._config.dim`` — the per-tenant
          ``S3Config.dim`` invariant. Mismatch raises :class:`ValueError`
          BEFORE any SQL runs (clearer than ``vec0`` blob-size errors).
        - **Exactly one** of ``node_id`` / ``edge_id`` / ``episode_id``
          must be non-None. Validated at the Python layer so the failure
          mode is a typed :class:`ValueError`, not a generic SQLite
          ``CHECK constraint failed``. The DB-level CHECK on
          ``embedding_keys`` is the redundant second line of defence.

        The ``conn`` parameter is **required** (no default) — every C5
        embedding write flows through the cross-store T2 seam, which
        owns the connection lifecycle. Audit gate §j.10 #10 enforces
        this surface ("``INSERT INTO (s3.|main.)?(embeddings|embedding_keys)``
        outside this module = 0 hits").
        """
        if len(vector) != self._config.dim:
            raise ValueError(
                f"S3Client.add: vector dim {len(vector)} != S3Config.dim {self._config.dim}"
            )
        present = sum(x is not None for x in (node_id, edge_id, episode_id))
        if present != 1:
            raise ValueError(
                "S3Client.add: exactly one of (node_id, edge_id, episode_id) "
                f"must be non-None, got {present} non-None values"
            )
        # vec0 expects a length-prefixed float32 blob. sqlite_vec.serialize_float32
        # is the conventional helper but raw struct.pack matches the spike.
        blob = struct.pack(f"{self._config.dim}f", *vector)
        cur = conn.execute(
            f"INSERT INTO {schema}.embeddings (embedding) VALUES (?)",
            (blob,),
        )
        rowid = cur.lastrowid
        if rowid is None:  # pragma: no cover - SQLite always assigns
            raise RuntimeError("S3Client.add: vec0 INSERT returned no rowid")
        conn.execute(
            f"INSERT INTO {schema}.embedding_keys "
            "(rowid, node_id, edge_id, episode_id) VALUES (?, ?, ?, ?)",
            (rowid, node_id, edge_id, episode_id),
        )
        return rowid
