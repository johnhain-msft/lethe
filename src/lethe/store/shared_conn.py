"""Cross-store T2 atomicity seam (P4 commit 5 — sub-plan §j.4).

Lands the :func:`shared_store_connection` context manager that opens
the per-tenant S2 SQLite file as the primary connection, loads the
``sqlite-vec`` extension on it, and ATTACHes the per-tenant S3 SQLite
file as the alias ``s3``. The result is a single
:class:`sqlite3.Connection` capable of writing to S2 tables
(``main.extraction_log``, ``main.consolidation_state``, …) AND the S3
``vec0`` virtual table (``s3.embeddings``) under one transaction.

The seam unblocks the P4 consolidate-loop embed phase
(:mod:`lethe.runtime.consolidate.extract` +
:mod:`lethe.runtime.consolidate.embed`), which writes one
``extraction_log`` row + one ``s3.embeddings`` row + one
``s3.embedding_keys`` row per episode. Without ATTACH-based atomicity
the three writes would risk leaving a cursor-advanced extraction with
no S3 vector — a divergence the recall-time path cannot detect cheaply.

**Spike result (sub-plan §j.4):** all three sub-tests passed —
ATTACH+vec extension+INSERT works, ROLLBACK is atomic across the
attached vec0 table (vec0 row count and S2 row count both return to
the pre-tx baseline), and either side can be primary. We pick S2 as
primary here because the migration ratchet, the per-tenant cursor, and
the extraction_log all live there; centring on S2 keeps the SQL
schema-qualified-as-``main`` for the "obvious" half of the writes.

**T2 atomicity caveat (A9):** this seam guarantees logical-transaction
atomicity (a successfully-rolled-back tx leaves both S2 and S3
unchanged — verified by spike Test B). Crash-atomicity across two
WAL-journaled SQLite files under ATTACH is NOT guaranteed by this seam
alone — process kill between the s3 WAL fsync and the s2 WAL fsync can
leave torn state. Full crash-recovery posture wires at P8 (deployment
§4.2 dream-daemon recovery); for P4 the next consolidate run's
``BEGIN IMMEDIATE`` + cursor read recovers via at-most-once retry.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import sqlite_vec

from lethe.store.s2_meta.schema import S2Schema
from lethe.store.s3_vec.client import S3Client


@contextmanager
def shared_store_connection(tenant_root: Path) -> Iterator[sqlite3.Connection]:
    """Open S2 as primary + ATTACH S3, yield the single shared connection.

    Pragmas on the S2 (main) connection mirror
    :func:`lethe.store.s2_meta.schema.open_connection`:
    ``isolation_level=None`` (autocommit, so caller owns BEGIN/COMMIT/
    ROLLBACK explicitly), ``journal_mode=WAL``, ``synchronous=NORMAL``,
    ``foreign_keys=ON``.

    Per A8, the same WAL+NORMAL pragma pair is also set on the
    attached ``s3`` schema after ATTACH so durability guarantees match
    on both sides; without this, the attached database inherits its
    own (possibly DELETE-mode) journal.

    Per A7, the ATTACH path is parameter-bound (not f-string'd) so
    paths containing single quotes don't break the seam.

    The CM does **not** auto-BEGIN/COMMIT — the caller owns transaction
    boundaries because (a) the consolidate extract loop wants explicit
    BEGIN IMMEDIATE for serialization (see A6) and (b) other callers
    may want savepoint-scoped sub-tx within a longer-lived seam. On
    exit, the CM detaches ``s3`` (best-effort) and closes the
    connection (idempotent).
    """
    s2_path = S2Schema(tenant_root=tenant_root).db_path
    s3_path = S3Client(tenant_root=tenant_root).db_path
    conn = sqlite3.connect(str(s2_path), isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # A12: hardened load — wrap enable_load_extension toggles so the
        # OFF call always runs even if sqlite_vec.load raises mid-flight.
        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)
        # A7: parameter-bound ATTACH (no f-string injection of s3_path).
        conn.execute("ATTACH DATABASE ? AS s3", (str(s3_path),))
        # A8: pragmas on the attached side — WAL + NORMAL match main.
        conn.execute("PRAGMA s3.journal_mode=WAL")
        conn.execute("PRAGMA s3.synchronous=NORMAL")
        yield conn
    finally:
        # Best-effort detach: a failed-tx state can refuse DETACH; the
        # subsequent close drops the lock anyway.
        with suppress(sqlite3.OperationalError):
            conn.execute("DETACH DATABASE s3")
        conn.close()
