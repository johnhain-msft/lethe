"""Consolidate-loop embed phase — pure embedding orchestration (P4 C5).

Three functions in symmetric shape — :func:`embed_episodes`,
:func:`embed_nodes`, :func:`embed_edges` — that the consolidate-loop
extract phase calls per episode/node/edge batch. Each function takes
the :class:`~lethe.runtime.consolidate.embedder_protocol.Embedder` from
the loop's injection seam, the shared-store connection from
:func:`~lethe.store.shared_conn.shared_store_connection`, and a
sequence of ``(slot_id, text)`` tuples; returns the list of
``rowid``s assigned by ``s3.embeddings``.

P4 commit 5 contract (sub-plan §j.6 — option (i)):

- :func:`embed_episodes` is **fully implemented** at C5: writes
  ``s3.embeddings`` + ``s3.embedding_keys (episode_id=...)`` rows via
  :meth:`~lethe.store.s3_vec.client.S3Client.add` for each input pair.
- :func:`embed_nodes` and :func:`embed_edges` ship at C5 with the
  same signature so the public surface is stable across C7's loop
  dispatch — but they raise :class:`NotImplementedError` on non-empty
  input. Empty input returns ``[]`` without calling the embedder
  (no-op invocation pattern); the real bodies wire at P9 with gap-06
  fact-extraction.

Embedding-key invariant (composition §B.5): exactly one of ``node_id``
/ ``edge_id`` / ``episode_id`` is non-NULL per row. The slot is fixed
per function (``embed_episodes`` writes ``episode_id``, etc.) so the
caller never picks the slot. Validation lives in
:meth:`S3Client.add` — both at the Python layer (clearer error) and
the DB ``CHECK`` constraint (defence in depth).

All three functions are pure with respect to the (embedder, items)
input — same input → same writes (modulo SQL autoincrement rowids).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from lethe.runtime.consolidate.embedder_protocol import Embedder
from lethe.store.s3_vec.client import S3Client


def _embed_and_persist(
    *,
    tenant_id: str,
    embedder: Embedder,
    conn: sqlite3.Connection,
    items: Sequence[tuple[str, str]],
    s3_client: S3Client,
    slot: str,
) -> list[int]:
    """Shared body for the three slot-keyed embed_* functions.

    Calls the embedder once per input batch (one network/host hop;
    composition §4.1 batch-friendly contract) and persists each
    returned vector via :meth:`S3Client.add` keyed by the slot the
    caller fixed.

    Returns the list of ``rowid``s in input order. Vector dimension
    mismatches surface from inside :meth:`S3Client.add` as
    :class:`ValueError`.
    """
    if not items:
        return []
    texts = [body for (_slot_id, body) in items]
    vectors = embedder(tenant_id=tenant_id, texts=texts)
    if len(vectors) != len(items):
        raise ValueError(
            f"Embedder returned {len(vectors)} vectors for {len(items)} inputs "
            f"(tenant_id={tenant_id!r}); embedder must satisfy len(out)==len(in)"
        )
    rowids: list[int] = []
    for (slot_id, _body), vector in zip(items, vectors, strict=True):
        kwargs: dict[str, str | None] = {"node_id": None, "edge_id": None, "episode_id": None}
        kwargs[slot] = slot_id
        rowid = s3_client.add(
            conn=conn,
            vector=vector,
            schema="s3",
            **kwargs,
        )
        rowids.append(rowid)
    return rowids


def embed_episodes(
    *,
    tenant_id: str,
    embedder: Embedder,
    conn: sqlite3.Connection,
    items: Sequence[tuple[str, str]],
    s3_client: S3Client,
) -> list[int]:
    """Embed episode bodies and persist as ``episode_id``-keyed S3 rows.

    ``items`` is a sequence of ``(episode_id, body)`` tuples — typically
    one batch per consolidate-loop extract iteration. Returns the list
    of ``rowid``s assigned to the new ``s3.embeddings`` rows in input
    order. Empty input is a no-op that returns ``[]`` without invoking
    the embedder.

    The schema-qualified writes (``s3.embeddings`` + ``s3.embedding_keys``)
    are scoped to the cross-store T2 transaction owned by the caller —
    a ROLLBACK at the caller's level reverts both writes and the
    paired ``main.extraction_log`` row atomically (sub-plan §j.4 spike
    Test B).
    """
    return _embed_and_persist(
        tenant_id=tenant_id,
        embedder=embedder,
        conn=conn,
        items=items,
        s3_client=s3_client,
        slot="episode_id",
    )


def embed_nodes(
    *,
    tenant_id: str,
    embedder: Embedder,
    conn: sqlite3.Connection,
    items: Sequence[tuple[str, str]],
    s3_client: S3Client,
) -> list[int]:
    """Stub — wires at P9 with gap-06 fact-extraction.

    P4 C5 contract (sub-plan §j.6 + A11): empty input returns ``[]``
    WITHOUT invoking the embedder; non-empty input raises
    :class:`NotImplementedError` citing the P9 + gap-06 boundary.
    Symmetry with :func:`embed_episodes` keeps C7's dispatch table
    trivial; the real body replaces the raise without touching the
    signature.
    """
    if not items:
        return []
    raise NotImplementedError(
        "embed_nodes wires at P9 with gap-06 fact-extraction "
        "(P4 commit 5 ships the empty-no-op + signature only — sub-plan §j.6)"
    )


def embed_edges(
    *,
    tenant_id: str,
    embedder: Embedder,
    conn: sqlite3.Connection,
    items: Sequence[tuple[str, str]],
    s3_client: S3Client,
) -> list[int]:
    """Stub — wires at P9 with gap-06 fact-extraction.

    P4 C5 contract (sub-plan §j.6 + A11): empty input returns ``[]``
    WITHOUT invoking the embedder; non-empty input raises
    :class:`NotImplementedError` citing the P9 + gap-06 boundary.
    Symmetry with :func:`embed_episodes` keeps C7's dispatch table
    trivial; the real body replaces the raise without touching the
    signature.
    """
    if not items:
        return []
    raise NotImplementedError(
        "embed_edges wires at P9 with gap-06 fact-extraction "
        "(P4 commit 5 ships the empty-no-op + signature only — sub-plan §j.6)"
    )
