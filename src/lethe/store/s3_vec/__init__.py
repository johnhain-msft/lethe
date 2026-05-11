"""S3 — vector index (sqlite-vec, single-tenant default).

Per composition §2 row 3, S3 owns embeddings keyed by ``(node_id, edge_id,
episode_id)``. **Stale-tolerant; rebuildable.** S3 never holds the only copy
of anything (canonical text lives in S1).
"""

from lethe.store.s3_vec.client import S3Client, S3Config

__all__ = ["S3Client", "S3Config"]
