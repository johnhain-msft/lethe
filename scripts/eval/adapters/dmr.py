"""DMR sanity-replay adapter (IMPL §2.3 P3 exit gate).

Exercises the production read path (``lethe.api.recall.recall``) end-to-end
against the deterministic checked-in DMR corpus under
``tests/fixtures/dmr_corpus/``. Concretely:

- Bootstraps a fresh per-tenant store under a temp ``LETHE_HOME`` (S1 + S2
  + **real sqlite-vec S3** + S4 + S5).
- Builds a real **SQLite FTS5** table over the corpus fact text (held in
  the same temp directory; not part of S2 because P3 doesn't ship a
  production lexical-index location yet — the FTS5 table is owned by the
  adapter and torn down with the temp dir).
- Loads the precomputed deterministic embeddings from
  ``embeddings.json`` and INSERTs them directly into the sqlite-vec
  ``embeddings`` virtual table (no embedder is instantiated — this is the
  point of Erratum E1: write-side embedder is reassigned to P4 and P3
  reads pre-seeded vectors).
- Invokes the **production** ``lethe.api.recall.recall`` verb for every
  query; computes recall@5 against the per-query ground truth.

Floor: ``recall@5 >= 0.6``. See README under the corpus dir for rationale.

This module exposes ``run_sanity_replay()`` (called by the harness CLI in
``scripts/eval/run_eval.py`` and by ``tests/eval/test_dmr_adapter.py``).
The legacy WS4 stubs ``load`` / ``metadata`` are not present anymore —
the adapter's contract is now the §2.3 sanity replay only.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import struct
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Repo-relative default for the corpus dir; overridable for tests.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CORPUS_DIR = _REPO_ROOT / "tests" / "fixtures" / "dmr_corpus"

#: ``recall@k`` is computed at this k. Pinned at 5 because the §2.3
#: sanity-replay floor is expressed as recall@5.
TOP_K = 5

#: Pass/fail floor — see ``tests/fixtures/dmr_corpus/README.md`` for
#: rationale. A regression below this means the read path actually broke.
FLOOR = 0.6


# ---------------------------------------------------------------------------
# Backends — REAL sqlite-vec semantic + REAL FTS5 lexical.
# ---------------------------------------------------------------------------


class _SqliteVecSemanticBackend:
    """Real ``SemanticBackend`` over a sqlite-vec ``vec0`` table.

    Thin wrapper around the same connection ``S3Client.bootstrap()``
    returned. Exposes the ``SemanticBackend`` Protocol shape consumed by
    ``lethe.runtime.retrievers.semantic_topk`` /
    ``lethe.api.recall.recall``.
    """

    def __init__(self, conn: sqlite3.Connection, dim: int) -> None:
        self._conn = conn
        self._dim = dim

    def search(
        self, *, query_vec: Sequence[float], k: int
    ) -> list[Hit]:  # noqa: F821
        from lethe.runtime.retrievers import Hit

        if len(query_vec) != self._dim:
            raise ValueError(
                f"query_vec dim {len(query_vec)} != backend dim {self._dim}"
            )
        # vec0 expects the query as its native serialized form. sqlite-vec
        # accepts a packed float32 BLOB.
        blob = struct.pack(f"{self._dim}f", *query_vec)
        cur = self._conn.execute(
            "SELECT k.node_id, e.distance "
            "FROM embeddings e "
            "JOIN embedding_keys k ON k.rowid = e.rowid "
            "WHERE e.embedding MATCH ? AND e.k = ? "
            "ORDER BY e.distance",
            (blob, k),
        )
        hits: list[Hit] = []
        for rank, (fact_id, distance) in enumerate(cur.fetchall(), start=1):
            # vec0 distance is L2 by default; convert to a similarity-like
            # score for the Hit envelope (the verb only consumes ranks).
            score = 1.0 / (1.0 + float(distance))
            hits.append(Hit(fact_id=fact_id, score=score, source="semantic", rank=rank))
        return hits


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _fts5_query(raw: str) -> str:
    """Sanitize a free-form query into FTS5 OR-syntax of bare tokens."""
    tokens = _TOKEN_RE.findall(raw.lower())
    if not tokens:
        return '""'
    # Quote each token defensively to keep FTS5 from interpreting reserved
    # chars; OR them so a paraphrased query still hits on token overlap.
    return " OR ".join(f'"{t}"' for t in tokens)


class _Fts5LexicalBackend:
    """Real ``LexicalBackend`` over a SQLite FTS5 virtual table.

    The FTS5 table is created and populated by ``_seed_substrate`` over
    the same corpus that goes into S3; ``search`` wraps the canonical
    BM25-ordered MATCH query.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search(self, *, query: str, k: int) -> list[Hit]:  # noqa: F821
        from lethe.runtime.retrievers import Hit

        sanitized = _fts5_query(query)
        cur = self._conn.execute(
            "SELECT fact_id, bm25(facts_fts) AS score "
            "FROM facts_fts "
            "WHERE facts_fts MATCH ? "
            "ORDER BY score "  # bm25() returns negative numbers; smaller = better
            "LIMIT ?",
            (sanitized, k),
        )
        hits: list[Hit] = []
        for rank, (fact_id, score) in enumerate(cur.fetchall(), start=1):
            # Convert "smaller-is-better" bm25 score to "larger-is-better"
            # for the Hit envelope; the verb doesn't consume this.
            hits.append(
                Hit(fact_id=fact_id, score=-float(score), source="lexical", rank=rank)
            )
        return hits


# ---------------------------------------------------------------------------
# FactStore — small in-memory dict over the parsed corpus.
# ---------------------------------------------------------------------------
#
# Production wiring of FactStore is P4+ (see ``recall.FactStore`` docstring).
# At P3 there is no production FactStore; the existing ``recall`` unit tests
# also use an in-memory dict double. The kickoff "real backends" mandate
# applies to the *retriever* surfaces (semantic + lexical), where a
# production-realistic substrate is what proves the read path works
# end-to-end. FactStore stays a small dict here for the same reason it
# does in test_recall.py: it's purely a metadata-fetch Protocol, with no
# scoring or ranking semantics of its own.


@dataclass
class _DictFactStore:
    records: dict[str, FactRecord]  # noqa: F821

    def fetch_many(
        self, fact_ids: Sequence[str], *, t_now: datetime
    ) -> list[FactRecord]:  # noqa: F821
        return [self.records[f] for f in fact_ids if f in self.records]


# ---------------------------------------------------------------------------
# Substrate seeding.
# ---------------------------------------------------------------------------


def _read_corpus(corpus_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes_path = corpus_dir / "episodes.jsonl"
    embeddings_path = corpus_dir / "embeddings.json"
    if not episodes_path.exists():
        raise FileNotFoundError(f"missing fixture: {episodes_path}")
    if not embeddings_path.exists():
        raise FileNotFoundError(
            f"missing fixture: {embeddings_path} "
            f"(regenerate via scripts/eval/fixtures/build_dmr_embeddings.py)"
        )
    facts: list[dict[str, Any]] = []
    with episodes_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            facts.append(json.loads(line))
    embeddings = json.loads(embeddings_path.read_text(encoding="utf-8"))
    if embeddings.get("dim") is None:
        raise ValueError("embeddings.json missing 'dim'")
    return facts, embeddings


def _seed_substrate(
    *,
    tenant_id: str,
    storage_root: Path,
    facts: list[dict[str, Any]],
    embeddings: dict[str, Any],
) -> tuple[
    sqlite3.Connection,  # s2_conn (recall_ledger lives here)
    sqlite3.Connection,  # s3_conn (sqlite-vec)
    sqlite3.Connection,  # fts_conn (lexical)
    _DictFactStore,
]:
    """Bootstrap the per-tenant tree and load the corpus into real backends."""
    # Lazy imports keep the adapter cheap when only `metadata`-style
    # discovery is needed (run_eval imports this module to dispatch).
    from lethe.api.recall import FactRecord
    from lethe.runtime.tenant_init import bootstrap as tenant_bootstrap
    from lethe.store.s2_meta import S2Schema
    from lethe.store.s3_vec import S3Client, S3Config

    bootstrap_result = tenant_bootstrap(tenant_id, storage_root)
    if not bootstrap_result.all_ready:
        raise RuntimeError(f"tenant_init failed: {bootstrap_result}")

    tenant_root = storage_root / "tenants" / tenant_id

    # S2: open a fresh handle for the verb (ledger writes go here).
    s2_conn = S2Schema(tenant_root=tenant_root).create()

    # S3: re-open at the fixture's dim. We must drop+recreate the vec0
    # table because tenant_init bootstraps S3 at the default dim (768),
    # which doesn't match the 32-dim hash-pseudo embeddings.
    dim = int(embeddings["dim"])
    s3_client = S3Client(tenant_root=tenant_root, config=S3Config(dim=dim))
    # bootstrap() above created vec0 at dim=768. Recreate at our dim.
    s3_conn = sqlite3.connect(str(s3_client.db_path))
    s3_conn.enable_load_extension(True)
    import sqlite_vec

    sqlite_vec.load(s3_conn)
    s3_conn.enable_load_extension(False)
    s3_conn.execute("DROP TABLE IF EXISTS embeddings")
    s3_conn.execute("DELETE FROM embedding_keys")
    s3_conn.execute(
        f"CREATE VIRTUAL TABLE embeddings USING vec0(embedding float[{dim}])"
    )

    # Insert one row per fact into both vec0 and the sidecar key table.
    fact_vectors: dict[str, list[float]] = embeddings["facts"]
    for rowid, fact in enumerate(facts, start=1):
        fid = fact["fact_id"]
        vec = fact_vectors.get(fid)
        if vec is None:
            raise ValueError(f"fact_id {fid} missing from embeddings.json")
        if len(vec) != dim:
            raise ValueError(
                f"fact {fid} vector dim {len(vec)} != embeddings.dim {dim}"
            )
        blob = struct.pack(f"{dim}f", *vec)
        s3_conn.execute(
            "INSERT INTO embeddings(rowid, embedding) VALUES (?, ?)", (rowid, blob)
        )
        s3_conn.execute(
            "INSERT INTO embedding_keys(rowid, node_id, edge_id, episode_id) "
            "VALUES (?, ?, NULL, NULL)",
            (rowid, fid),
        )
    s3_conn.commit()

    # FTS5: own SQLite file under the tenant root for the lexical index.
    # P3 has no production lexical-index location yet (that's P4+); the
    # adapter owns this DB and tears it down with the temp dir.
    fts_path = tenant_root / "dmr_lexical_fts5.sqlite"
    fts_conn = sqlite3.connect(str(fts_path))
    fts_conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts "
        "USING fts5(fact_id UNINDEXED, content)"
    )
    for fact in facts:
        fts_conn.execute(
            "INSERT INTO facts_fts(fact_id, content) VALUES (?, ?)",
            (fact["fact_id"], fact["content"]),
        )
    fts_conn.commit()

    # FactStore: small dict mirror of the corpus metadata.
    records: dict[str, FactRecord] = {}
    for fact in facts:
        records[fact["fact_id"]] = FactRecord(
            fact_id=fact["fact_id"],
            kind=fact["kind"],
            content=fact["content"],
            valid_from=fact["valid_from"],
            valid_to=None,
            recorded_at=fact["valid_from"],
            episode_id=fact.get("episode_id"),
            version=1,
            source_uri=f"dmr://{fact['fact_id']}",
        )
    fact_store = _DictFactStore(records=records)

    return s2_conn, s3_conn, fts_conn, fact_store


# ---------------------------------------------------------------------------
# Public surface.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SanityReplayResult:
    """One-shot summary of a DMR sanity replay."""

    queries: int
    hits_at_k: int
    recall_at_k: float
    floor: float
    top_k: int
    passed: bool

    def summary_line(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        return (
            f"DMR sanity replay: recall@{self.top_k}={self.recall_at_k:.3f} "
            f"[floor={self.floor:.2f}] {verdict} "
            f"({self.hits_at_k}/{self.queries} queries)"
        )


def run_sanity_replay(
    *,
    tenant_id: str = "dmr-smoke",
    corpus_dir: Path | None = None,
    floor: float = FLOOR,
    top_k: int = TOP_K,
) -> SanityReplayResult:
    """Run the §2.3 DMR sanity replay end-to-end and return the result.

    Uses ``LETHE_HOME=$(mktemp -d)`` isolation per the project test
    convention; the temp directory is removed on exit.
    """
    from lethe.api.recall import RecallRequest, recall

    corpus_dir = corpus_dir or _DEFAULT_CORPUS_DIR
    facts, embeddings = _read_corpus(corpus_dir)
    queries: list[dict[str, Any]] = embeddings["queries"]

    with tempfile.TemporaryDirectory(prefix="lethe-dmr.") as tmp:
        storage_root = Path(tmp)
        prior_lethe_home = os.environ.get("LETHE_HOME")
        os.environ["LETHE_HOME"] = str(storage_root)
        try:
            s2_conn, s3_conn, fts_conn, fact_store = _seed_substrate(
                tenant_id=tenant_id,
                storage_root=storage_root,
                facts=facts,
                embeddings=embeddings,
            )
            try:
                semantic = _SqliteVecSemanticBackend(
                    s3_conn, dim=int(embeddings["dim"])
                )
                lexical = _Fts5LexicalBackend(fts_conn)

                hits_at_k = 0
                # Pin a single ``now`` so recall_id derivation is stable
                # across the loop (only ts_recorded_ms varies the prefix
                # bits anyway, but pinning makes debugging easier).
                now = datetime.now(UTC)
                for q in queries:
                    request = RecallRequest(
                        tenant_id=tenant_id,
                        query=str(q["query"]),
                        k=top_k,
                        intent="dmr-sanity-replay",
                        scope={"adapter": "dmr"},
                        query_vec=list(q["vector"]),
                    )
                    response = recall(
                        request,
                        s2_conn=s2_conn,
                        fact_store=fact_store,
                        lexical=lexical,
                        semantic=semantic,
                        graph=None,
                        now=now,
                    )
                    returned_ids = [f.fact_id for f in response.facts[:top_k]]
                    relevant: list[str] = list(q["relevant_fact_ids"])
                    if any(r in returned_ids for r in relevant):
                        hits_at_k += 1
            finally:
                fts_conn.close()
                s3_conn.close()
                s2_conn.close()
        finally:
            if prior_lethe_home is None:
                os.environ.pop("LETHE_HOME", None)
            else:
                os.environ["LETHE_HOME"] = prior_lethe_home

    n = len(queries)
    recall_at_k = hits_at_k / n if n else 0.0
    return SanityReplayResult(
        queries=n,
        hits_at_k=hits_at_k,
        recall_at_k=recall_at_k,
        floor=floor,
        top_k=top_k,
        passed=recall_at_k >= floor,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m scripts.eval.adapters.dmr [--tenant-id X]``."""
    import argparse

    parser = argparse.ArgumentParser(prog="adapters.dmr")
    parser.add_argument("--tenant-id", default="dmr-smoke")
    args = parser.parse_args(argv)

    result = run_sanity_replay(tenant_id=args.tenant_id)
    print(result.summary_line())
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
