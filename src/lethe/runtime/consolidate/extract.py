"""Consolidate-loop extract phase — minimal real flow at P4 C5.

Per sub-plan §j.5 (option (a)): ``extract.py`` runs the
extract→embed→cursor-advance pipeline end-to-end with a stub extractor
(``extractor_version="p4-c5-stub-v0"``, ``confidence=1.0``,
``payload_blob=b""``). The stub body is a no-op; the seam is the
deliverable — full fact + entity extraction (gap-06) lands at P9 by
swapping the stub body inside this same orchestrator.

Cross-store T2 atomicity (sub-plan §j.4 spike Test B):

The whole pipeline runs inside one
:func:`~lethe.store.shared_conn.shared_store_connection` context with
a single ``BEGIN IMMEDIATE`` / ``COMMIT`` boundary. The S3 vec0 INSERT
+ S2 ``extraction_log`` INSERT + S2 ``consolidation_state`` UPDATE
either ALL commit or — on any in-loop exception (e.g. embedder raise,
dim mismatch, dropped backend connection) — ALL roll back via a single
``ROLLBACK``. The cursor is advanced inside the same tx so a rolled-
back run leaves ``last_run_cursor`` unchanged and the next run reads
the same baseline (at-most-once retry).

Per A1 + A6:

- ``BEGIN IMMEDIATE`` is the FIRST statement inside the seam. This
  serializes per-tenant S2 state against any concurrent extract run
  — sufficient for C5 (the C7 scheduler will add proper lock
  semantics on top).
- ``INSERT OR IGNORE INTO main.consolidation_state(tenant_id) VALUES (?)``
  before the first SELECT, so a fresh tenant (no row yet) gets a row
  created idempotently. The subsequent UPDATE asserts ``rowcount == 1``
  to prove the cursor write actually landed.

Per A5:

- ``last_run_cursor`` stores a **composite cursor** of the form
  ``f"{ts_recorded}\\t{episode_id}"`` (tab-separated) so episodes
  sharing a ``ts_recorded`` value are not permanently skipped on the
  second run. The cursor is computed from the LAST element of the
  episodes list (which is sorted ASC by ``(ts_recorded, episode_id)``
  per the :meth:`GraphBackend.episodes_since` contract — A10).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from lethe.runtime.consolidate.embed import embed_episodes
from lethe.runtime.consolidate.embedder_protocol import Embedder
from lethe.store.s1_graph.client import S1Client
from lethe.store.s3_vec.client import S3Client
from lethe.store.shared_conn import shared_store_connection

EXTRACTOR_VERSION = "p4-c5-stub-v0"


def _build_cursor(ts_recorded: str, episode_id: str) -> str:
    """Compose the per-(ts, eid) cursor stored in ``last_run_cursor`` (A5).

    The tab separator (0x09) is less than every printable RFC 3339
    character so lexicographic compare degrades correctly to ts-first
    when ts values differ; ties on ts fall through to episode_id.
    """
    return f"{ts_recorded}\t{episode_id}"


def run_extract(
    *,
    tenant_root: Path,
    s1_client: S1Client,
    embedder: Embedder,
    s3_client: S3Client,
) -> int:
    """Run one extract pass for ``s1_client.tenant_id``; return episodes processed.

    On embedder failure (or any exception inside the BEGIN IMMEDIATE /
    COMMIT block), the entire transaction is rolled back — extraction_log
    rows, S3 embeddings, S3 embedding_keys, AND the cursor advance are
    ALL reverted. The exception then re-raises to the caller.

    Empty-tenant case (no new episodes since cursor): the function still
    runs the BEGIN IMMEDIATE / INSERT OR IGNORE / SELECT cursor sequence
    (so the consolidation_state row exists after the first run), but
    skips the embed loop and the cursor UPDATE. Returns ``0``.
    """
    tenant_id = s1_client.tenant_id
    with shared_store_connection(tenant_root) as conn:
        # A6: BEGIN IMMEDIATE first — serializes per-tenant S2 state
        # against any concurrent extract run. SQLITE_BUSY surfaces here
        # for the loser if two runs race; C7 scheduler adds the proper
        # consolidation_state lock on top.
        conn.execute("BEGIN IMMEDIATE")
        try:
            # A1: ensure the per-tenant consolidation_state row exists
            # (idempotent on subsequent runs). DEFAULT CLAUSEs supply
            # created_at / updated_at; lock and last_run_* stay NULL
            # until something writes them.
            conn.execute(
                "INSERT OR IGNORE INTO main.consolidation_state (tenant_id) VALUES (?)",
                (tenant_id,),
            )
            cur = conn.execute(
                "SELECT last_run_cursor FROM main.consolidation_state WHERE tenant_id = ?",
                (tenant_id,),
            )
            row = cur.fetchone()
            since_cursor: str | None = row[0] if row is not None else None

            # episodes_since returns sorted ASC by (ts_recorded, episode_id)
            # per A10; we materialize as a list so the LAST element is
            # the highest cursor candidate.
            episodes = list(s1_client.episodes_since(since_cursor=since_cursor))

            if not episodes:
                conn.execute("COMMIT")
                return 0

            # P4 C5 stub flow (sub-plan §j.5 — option (a)): one embed
            # call per episode batch + one extraction_log row per
            # episode. The "real" extractor body replaces the stub
            # block at P9.
            items = [(ep.episode_id, ep.body) for ep in episodes]
            embed_episodes(
                tenant_id=tenant_id,
                embedder=embedder,
                conn=conn,
                items=items,
                s3_client=s3_client,
            )

            extracted_at = datetime.now(UTC).isoformat()
            for ep in episodes:
                conn.execute(
                    "INSERT INTO main.extraction_log "
                    "(episode_id, extracted_at, extractor_version, "
                    " confidence, payload_blob) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        ep.episode_id,
                        extracted_at,
                        EXTRACTOR_VERSION,
                        1.0,
                        b"",
                    ),
                )

            # Cursor + last_run_at advance from the LAST sorted episode
            # (per A10 ordering contract) — NOT max() over the list.
            last = episodes[-1]
            new_cursor = _build_cursor(last.ts_recorded, last.episode_id)
            update = conn.execute(
                "UPDATE main.consolidation_state "
                "SET last_run_cursor = ?, last_run_at = ?, "
                "    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE tenant_id = ?",
                (new_cursor, extracted_at, tenant_id),
            )
            # A1: assert the cursor write actually landed (otherwise
            # we'd silently fail to advance and reprocess on next run).
            if update.rowcount != 1:
                raise RuntimeError(
                    "extract: consolidation_state UPDATE affected "
                    f"{update.rowcount} rows, expected exactly 1 "
                    f"(tenant_id={tenant_id!r})"
                )

            conn.execute("COMMIT")
            return len(episodes)
        except BaseException:
            # ROLLBACK reverts main.extraction_log, s3.embeddings,
            # s3.embedding_keys, AND the consolidation_state UPDATE
            # (and even the INSERT OR IGNORE on first run). Re-raise
            # so the caller (C7 loop) sees the failure.
            conn.execute("ROLLBACK")
            raise
