#!/usr/bin/env python3
"""Generate the deterministic hash-pseudo embedding fixture for the DMR corpus.

Why hash-pseudo instead of a real embedding model
-------------------------------------------------
The §2.3 DMR sanity-replay exit gate exercises the **read-path algorithm**
end-to-end (bi-temporal filter → real sqlite-vec semantic + real FTS5
lexical retrievers → RRF fuse → per-class score → ledger write → events).
What it does *not* test is "does a real embedding model rank paraphrased
queries well" — that's a P-later concern once a production embedder lands
(Erratum E1 reassigns the write-side embedder to P4).

A real model (e.g. ``sentence-transformers/all-MiniLM-L6-v2``) would force
``sentence-transformers`` + ``torch`` + ``transformers`` into the project's
``pyproject.toml`` (or a brittle off-CI install dance), and contributes
*nothing* the read-path gate is asking us to prove. So we use a
content-addressable **sha256-derived 32-dim float vector**:

    digest = sha256(text.encode("utf-8")).digest()  # 32 bytes
    vec[i] = (digest[i] - 127.5) / 127.5            # in [-1, +1]
    vec   = vec / ||vec||_2                         # L2-normalize

Properties:

- **Deterministic** byte-for-byte across machines and Python versions
  (sha256 is stable; float32 round-trip via JSON preserves enough bits
  for cosine ranking to be reproducible).
- **Content-addressable**: queries that share substrings or tokens with
  facts produce vectors whose cosine similarity is a *little* above
  noise (each shared byte nudges that dimension the same direction).
  Pure noise vectors would give the test no semantic signal at all.
- **Zero external deps** — only stdlib + the project-pinned ``numpy`` are
  needed (numpy is for the L2 normalize; falling back to pure Python is
  trivial if needed). This script intentionally imports nothing the
  project doesn't already declare.

This script is invoked manually when you want to regenerate the fixture
(e.g. you added/removed an episode). CI does **not** invoke it; CI consumes
the checked-in ``embeddings.json`` only.

Usage
-----
    uv run python scripts/eval/fixtures/build_dmr_embeddings.py

Reads:  ``tests/fixtures/dmr_corpus/episodes.jsonl``
Writes: ``tests/fixtures/dmr_corpus/embeddings.json``
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

# Embedding dimensionality. 32 = exactly one sha256 digest, no padding.
EMBED_DIM = 32

# Pinned for documentation/reproducibility-audit purposes only; the hash
# function ignores the seed (it's a pure function of input text). The
# constant is exported so the README and the test docstring agree.
SEED = 42

SCHEME = "sha256-pseudo-v1"

# Paraphrased DMR-style queries with single-fact ground truth. Designed
# to deliberately *avoid* trivial substring matches against the fact
# content where possible (e.g. "reside" vs "lives", "vehicle" vs "car"),
# so lexical alone won't trivially ace the recall@5 floor.
QUERIES: list[dict[str, object]] = [
    {"query_id": "q-001", "query": "What language does Alice prefer for coding?", "relevant_fact_ids": ["f-001"]},  # noqa: E501
    {"query_id": "q-002", "query": "Where does Bob reside?", "relevant_fact_ids": ["f-002"]},
    {"query_id": "q-003", "query": "What is Carol's job title?", "relevant_fact_ids": ["f-003"]},
    {"query_id": "q-004", "query": "When was David born?", "relevant_fact_ids": ["f-004"]},
    {"query_id": "q-005", "query": "What pet does Eve have?", "relevant_fact_ids": ["f-005"]},
    {"query_id": "q-006", "query": "What is Frank's email address?", "relevant_fact_ids": ["f-006"]},  # noqa: E501
    {"query_id": "q-007", "query": "Which beverage does Grace prefer in the morning?", "relevant_fact_ids": ["f-007"]},  # noqa: E501
    {"query_id": "q-008", "query": "What kind of vehicle does Henry drive?", "relevant_fact_ids": ["f-008"]},  # noqa: E501
    {"query_id": "q-009", "query": "Does Iris have any food allergies?", "relevant_fact_ids": ["f-009"]},  # noqa: E501
    {"query_id": "q-010", "query": "Which university did Jack attend?", "relevant_fact_ids": ["f-010"]},  # noqa: E501
    {"query_id": "q-011", "query": "What is Kate's spouse's name?", "relevant_fact_ids": ["f-011"]},  # noqa: E501
    {"query_id": "q-012", "query": "What instrument does Liam play?", "relevant_fact_ids": ["f-012"]},  # noqa: E501
    {"query_id": "q-013", "query": "Where did Mia grow up?", "relevant_fact_ids": ["f-013"]},
    {"query_id": "q-014", "query": "How many children does Noah have?", "relevant_fact_ids": ["f-014"]},  # noqa: E501
    {"query_id": "q-015", "query": "What sport does Olivia play on weekends?", "relevant_fact_ids": ["f-015"]},  # noqa: E501
    {"query_id": "q-016", "query": "Which company employs Peter?", "relevant_fact_ids": ["f-016"]},
    {"query_id": "q-017", "query": "What is Quinn's preferred operating system?", "relevant_fact_ids": ["f-017"]},  # noqa: E501
    {"query_id": "q-018", "query": "What is Rachel's middle name?", "relevant_fact_ids": ["f-018"]},  # noqa: E501
    {"query_id": "q-019", "query": "What time zone does Sam work in?", "relevant_fact_ids": ["f-019"]},  # noqa: E501
    {"query_id": "q-020", "query": "Which nationality does Tina hold?", "relevant_fact_ids": ["f-020"]},  # noqa: E501
    {"query_id": "q-021", "query": "What is Uma's favorite cuisine?", "relevant_fact_ids": ["f-021"]},  # noqa: E501
    {"query_id": "q-022", "query": "What hobby does Victor pursue?", "relevant_fact_ids": ["f-022"]},  # noqa: E501
    {"query_id": "q-023", "query": "Which book is Wendy currently reading?", "relevant_fact_ids": ["f-023"]},  # noqa: E501
    {"query_id": "q-024", "query": "What is Xander's daily commute like?", "relevant_fact_ids": ["f-024"]},  # noqa: E501
    {"query_id": "q-025", "query": "Which charity does Yara donate to?", "relevant_fact_ids": ["f-025"]},  # noqa: E501
]


def hash_embed(text: str) -> list[float]:
    """Compute the deterministic ``EMBED_DIM`` pseudo-embedding for ``text``.

    Pure-Python (no numpy dep). Round-trip through JSON preserves enough
    precision for cosine ranking to be reproducible.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    if len(digest) != EMBED_DIM:
        raise AssertionError(f"sha256 digest size != EMBED_DIM ({EMBED_DIM})")
    raw = [(b - 127.5) / 127.5 for b in digest]
    norm = math.sqrt(sum(x * x for x in raw))
    if norm == 0.0:
        return raw
    return [round(x / norm, 8) for x in raw]


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_dir = repo_root / "tests" / "fixtures" / "dmr_corpus"
    episodes_path = fixture_dir / "episodes.jsonl"
    out_path = fixture_dir / "embeddings.json"

    if not episodes_path.exists():
        print(f"missing corpus: {episodes_path}", file=sys.stderr)
        return 1

    facts: dict[str, list[float]] = {}
    fact_count = 0
    with episodes_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            facts[rec["fact_id"]] = hash_embed(rec["content"])
            fact_count += 1

    queries_out: list[dict[str, object]] = []
    for q in QUERIES:
        queries_out.append(
            {
                "query_id": q["query_id"],
                "query": q["query"],
                "relevant_fact_ids": q["relevant_fact_ids"],
                "vector": hash_embed(q["query"]),  # type: ignore[arg-type]
            }
        )

    payload = {
        "scheme": SCHEME,
        "seed": SEED,  # documented; hash function ignores it (pure of text).
        "dim": EMBED_DIM,
        "facts": facts,
        "queries": queries_out,
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {out_path} (scheme={SCHEME}, dim={EMBED_DIM}, "
        f"facts={fact_count}, queries={len(queries_out)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
