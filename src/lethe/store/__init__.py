"""Five-store substrate root (S1 graph / S2 meta / S3 vec / S4 markdown / S5 log).

Per ``docs/03-composition-design.md`` §2, exactly one store is canonical for any
given fact; the rest derive. P1 lands schema scaffolding only — verbs land in P2+.

P4 commit 5 lands :func:`shared_store_connection` — the cross-store T2
atomicity seam used by the consolidate-loop embed phase to write
``main.extraction_log`` + ``s3.embeddings`` + ``s3.embedding_keys``
under a single transaction.
"""

from lethe.store.shared_conn import shared_store_connection

__all__ = ["shared_store_connection"]
