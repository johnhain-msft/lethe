"""DMR sanity-replay exit gate (IMPL §2.3 P3).

This is the canonical test that exercises the production read path
(``lethe.api.recall.recall``) end-to-end against the deterministic
checked-in DMR corpus. It stands in for the IMPL §2.3 "DMR sanity replay"
exit gate — the gate the facilitator P3 plan §(f) names as #5.

Floor: ``recall@5 >= 0.6``. See ``tests/fixtures/dmr_corpus/README.md``
for the rationale (DMR is a smoke test per ``eval-plan §3.3``; the floor
is a regression detector, not a competitive benchmark).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.eval.adapters.dmr import (
    FLOOR,
    TOP_K,
    run_sanity_replay,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_DIR = _REPO_ROOT / "tests" / "fixtures" / "dmr_corpus"


def test_dmr_corpus_fixtures_present_and_parseable() -> None:
    """Both fixture files exist, are valid, and align (every fact has a vector)."""
    episodes = _CORPUS_DIR / "episodes.jsonl"
    embeddings = _CORPUS_DIR / "embeddings.json"
    readme = _CORPUS_DIR / "README.md"
    assert episodes.exists(), f"missing fixture: {episodes}"
    assert embeddings.exists(), f"missing fixture: {embeddings}"
    assert readme.exists(), f"missing fixture: {readme}"

    fact_ids: list[str] = []
    with episodes.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            assert {"fact_id", "kind", "content", "valid_from", "episode_id"} <= rec.keys()
            fact_ids.append(rec["fact_id"])
    assert len(fact_ids) == len(set(fact_ids)), "duplicate fact_id in corpus"

    payload = json.loads(embeddings.read_text(encoding="utf-8"))
    assert payload["scheme"] == "sha256-pseudo-v1"
    assert payload["dim"] == 32
    # Every fact has an embedding of the declared dim.
    for fid in fact_ids:
        vec = payload["facts"].get(fid)
        assert vec is not None, f"fact {fid} missing from embeddings.json"
        assert len(vec) == payload["dim"]
    # Every query has a vector + non-empty ground truth.
    for q in payload["queries"]:
        assert {"query_id", "query", "relevant_fact_ids", "vector"} <= q.keys()
        assert len(q["vector"]) == payload["dim"]
        assert q["relevant_fact_ids"], f"query {q['query_id']} has empty ground truth"
        for rid in q["relevant_fact_ids"]:
            assert rid in payload["facts"], f"ground-truth {rid} missing from corpus"


def test_dmr_sanity_replay_meets_floor() -> None:
    """The §2.3 exit gate: recall@5 >= 0.6 across the full DMR corpus.

    Drives the production ``recall`` verb against:

    - real ``sqlite-vec`` for semantic retrieval (vec0 cosine top-k);
    - real SQLite ``FTS5`` for lexical retrieval (BM25 top-k);
    - in-memory ``FactStore`` (production wiring is P4+, mirrors the unit
      tests' approach for the same Protocol).

    No embedder is instantiated anywhere on the path; embeddings come
    from the deterministic checked-in fixture (Erratum E1).
    """
    result = run_sanity_replay(tenant_id="dmr-pytest")
    assert result.queries == 25, f"expected 25 queries, got {result.queries}"
    assert result.top_k == TOP_K
    assert result.floor == FLOOR
    assert result.passed, (
        f"DMR sanity replay below floor: recall@{result.top_k}="
        f"{result.recall_at_k:.3f} < {result.floor:.2f} "
        f"({result.hits_at_k}/{result.queries} hits)"
    )


def test_run_eval_cli_exits_zero_on_dmr_pass() -> None:
    """``run_eval --adapter dmr`` returns exit 0 with a one-line summary.

    Invoked via the script *path* (not ``-m``) so the gate also covers the
    bare ``python scripts/eval/run_eval.py …`` invocation the kickoff
    references; this catches regressions in ``sys.path`` setup that the
    ``-m`` form would mask.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "eval" / "run_eval.py"),
            "--adapter",
            "dmr",
            "--tenant-id",
            "dmr-cli",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "PYTHONPATH": ""},
    )
    assert proc.returncode == 0, (
        f"harness exited {proc.returncode}\nstdout: {proc.stdout!r}\nstderr: {proc.stderr!r}"
    )
    assert "DMR sanity replay" in proc.stdout
    assert "PASS" in proc.stdout


def test_run_eval_cli_default_remains_inert() -> None:
    """No ``--adapter`` argument → WS4 stub behaviour preserved (exit 2).

    The rest of the harness (public-benchmark loaders, metrics emitter,
    shadow, chaos, contamination) hasn't landed yet; the default no-arg
    invocation must keep returning the inert WS4 exit code.
    """
    proc = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "scripts" / "eval" / "run_eval.py")],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        env={**__import__("os").environ, "PYTHONPATH": ""},
    )
    assert proc.returncode == 2, (
        f"expected WS4 inert exit 2, got {proc.returncode} "
        f"(stderr: {proc.stderr!r})"
    )


@pytest.mark.parametrize("missing", ["episodes.jsonl", "embeddings.json"])
def test_sanity_replay_raises_on_missing_fixture(missing: str, tmp_path: Path) -> None:
    """Helpful error if a fixture is missing (e.g. corpus partially deleted)."""
    # Build a stub corpus dir with only one of the two fixtures, so the
    # adapter raises FileNotFoundError pointing at the missing one.
    stub = tmp_path / "stub_corpus"
    stub.mkdir()
    if missing != "episodes.jsonl":
        (stub / "episodes.jsonl").write_text("", encoding="utf-8")
    if missing != "embeddings.json":
        (stub / "embeddings.json").write_text(
            json.dumps({"dim": 32, "facts": {}, "queries": []}),
            encoding="utf-8",
        )
    with pytest.raises(FileNotFoundError, match=missing):
        run_sanity_replay(tenant_id="dmr-stub", corpus_dir=stub)
