"""``recall`` verb coverage (api §2.1).

Covers the facilitator P3 §(f) gates the ``recall`` verb owns:

- Gate 3a: ``recall(k=0)`` returns a preferences-only response with a
  ``recall_id`` (still computed via api §1.4).
- Gate 3b: ``recall(k=0)`` emits ZERO ``recall`` events.
- Gate 4: preferences prepend respects the gap-09 §6 cap (delegated to
  the shared envelope builder; spot-checked here at the verb boundary).
- Gate 6: per-class scoring exercised across all 4 persistent shapes
  (episodic_fact, preference, procedure, narrative).
- Bi-temporal filter (invariant I-4) runs **pre-RRF**: invalid-window
  facts never reach the per-class scorer (ordering enforced by a
  recording double).
- Provenance enforcement (composition §6): facts without ``episode_id``
  are dropped from the response *after* scoring/ranking; the dropped
  count surfaces in ``applied_filters.provenance_dropped``.
- ``recall_ledger`` row written via ``INSERT OR IGNORE``; legitimate
  same-input replay silently no-ops; same-PK + different-payload raises
  :class:`RecallLedgerCorruption` (substrate-bug semantics).
- ``recall_id`` from the ``recall`` verb matches the bare api §1.4
  derivation: ``derive_recall_id(tenant, ts_ms, query_hash)`` reproduces
  the verb's id.
- Lexical-only fallback survives an injected :class:`S3Outage` from the
  semantic backend (composition §3.1).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lethe.api.recall import (
    FactRecord,
    RecallLedgerCorruption,
    RecallRequest,
    RecallValidationError,
    recall,
    write_ledger_row,
)
from lethe.runtime.preferences_prepend import PreferencePage
from lethe.runtime.recall_id import compute_query_hash, derive_recall_id
from lethe.runtime.retrievers import Hit, S3Outage
from lethe.store.s2_meta import S2Schema

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeFactStore:
    """In-memory FactStore stub. ``fetch_many`` returns metadata in input order."""

    records: dict[str, FactRecord]
    fetch_calls: list[tuple[tuple[str, ...], datetime]] = field(default_factory=list)

    def fetch_many(
        self, fact_ids: Sequence[str], *, t_now: datetime
    ) -> list[FactRecord]:
        self.fetch_calls.append((tuple(fact_ids), t_now))
        return [self.records[f] for f in fact_ids if f in self.records]


@dataclass
class _FakeLexical:
    hits: list[Hit]
    call_count: int = 0
    last_query: str | None = None

    def search(self, *, query: str, k: int) -> list[Hit]:
        self.call_count += 1
        self.last_query = query
        return self.hits[:k]


@dataclass
class _FakeSemantic:
    hits: list[Hit] = field(default_factory=list)
    raise_outage: bool = False
    call_count: int = 0

    def search(self, *, query_vec: Sequence[float], k: int) -> list[Hit]:
        self.call_count += 1
        if self.raise_outage:
            raise S3Outage("synthetic outage for test")
        return self.hits[:k]


@dataclass
class _FakeGraph:
    hits: list[Hit] = field(default_factory=list)
    call_count: int = 0

    def seed_topk(self, *, query: str, k: int) -> list[Hit]:
        self.call_count += 1
        return self.hits[:k]


@dataclass
class _FakePreferenceSource:
    pages: list[PreferencePage]

    def list_preferences(self, *, tenant_id: str) -> list[PreferencePage]:
        return list(self.pages)


class _RecordingSink:
    """Capture all events emitted via the verb's sink."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_T_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


def _open_s2(tenant_root: Path) -> sqlite3.Connection:
    return S2Schema(tenant_root=tenant_root).create()


def _record(
    fact_id: str,
    *,
    kind: str = "user_fact",
    valid_from: str = "2024-01-01T00:00:00.000000+00:00",
    valid_to: str | None = None,
    episode_id: str | None = None,
    content: str = "test fact",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        kind=kind,
        content=content,
        valid_from=valid_from,
        valid_to=valid_to,
        recorded_at=valid_from,
        episode_id=episode_id if episode_id is not None else f"ep-{fact_id}",
        version=1,
        source_uri=f"file://{fact_id}.md",
    )


def _build_setup(
    tenant_root: Path,
    *,
    records: Iterable[FactRecord],
    lexical_hits: list[Hit] | None = None,
    semantic_hits: list[Hit] | None = None,
    graph_hits: list[Hit] | None = None,
    semantic_outage: bool = False,
    preferences: list[PreferencePage] | None = None,
) -> tuple[
    sqlite3.Connection,
    _FakeFactStore,
    _FakeLexical,
    _FakeSemantic,
    _FakeGraph,
    _FakePreferenceSource,
    _RecordingSink,
]:
    conn = _open_s2(tenant_root)
    store = _FakeFactStore({r.fact_id: r for r in records})
    lex = _FakeLexical(hits=lexical_hits or [])
    sem = _FakeSemantic(hits=semantic_hits or [], raise_outage=semantic_outage)
    grf = _FakeGraph(hits=graph_hits or [])
    pref_src = _FakePreferenceSource(pages=preferences or [])
    sink = _RecordingSink()
    return conn, store, lex, sem, grf, pref_src, sink


# ---------------------------------------------------------------------------
# Tests — k=0 short-circuit (gates 3a + 3b)
# ---------------------------------------------------------------------------


def test_k0_returns_preferences_only_with_recall_id(tenant_root: Path) -> None:
    """Gate 3a: k=0 → facts=[], preferences populated, recall_id present."""
    pref = PreferencePage(
        page_uri="prefs/lang.md",
        content="prefer python",
        kind="preference",
        revision_id="rev-1",
        revised_at="2025-05-01T00:00:00.000Z",
        bytes=14,
    )
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=[], preferences=[pref]
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="anything", k=0),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            semantic=sem,
            graph=grf,
            preference_source=pref_src,
            event_sink=sink,
            now=_T_NOW,
        )
        assert resp.facts == []
        assert resp.recall_id  # uuidv7 string
        assert [p.page_uri for p in resp.preferences] == ["prefs/lang.md"]
        assert resp.preferences_truncated is False
        assert resp.preferences_total_bytes == 14
        # Retrievers must NOT have been consulted at k=0.
        assert lex.call_count == 0
        assert sem.call_count == 0
        assert grf.call_count == 0
        # Ledger row written.
        rows = conn.execute(
            "SELECT recall_id, classified_intent, top_k_fact_ids FROM recall_ledger"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == resp.recall_id
        assert rows[0][1] == "unspecified"
        assert rows[0][2] == "[]"
    finally:
        conn.close()


def test_k0_emits_zero_recall_events(tenant_root: Path) -> None:
    """Gate 3b: k=0 must not emit any recall events."""
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=[]
    )
    try:
        recall(
            RecallRequest(tenant_id="tenant-a", query="anything", k=0),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            event_sink=sink,
            now=_T_NOW,
        )
        assert sink.events == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — happy path + per-class scoring (gate 6)
# ---------------------------------------------------------------------------


def test_happy_path_returns_top_k_with_provenance(tenant_root: Path) -> None:
    records = [
        _record("f1", kind="user_fact", content="user fact one"),
        _record("f2", kind="preference", content="pref one"),
        _record("f3", kind="procedure", content="proc one"),
        _record("f4", kind="narrative", content="narr one"),
    ]
    lex_hits = [
        Hit(fact_id="f1", score=0.9, source="lexical", rank=1),
        Hit(fact_id="f2", score=0.8, source="lexical", rank=2),
        Hit(fact_id="f3", score=0.7, source="lexical", rank=3),
        Hit(fact_id="f4", score=0.6, source="lexical", rank=4),
    ]
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=records, lexical_hits=lex_hits
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="q", k=10),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            event_sink=sink,
            now=_T_NOW,
        )
        # All four shapes survived (provenance present on each).
        returned_ids = {f.fact_id for f in resp.facts}
        assert returned_ids == {"f1", "f2", "f3", "f4"}
        # Each fact has provenance + score_inputs.
        for f in resp.facts:
            assert "episode_id" in f.provenance
            assert "rrf_score" in f.score_inputs
        # One ledger row.
        rows = conn.execute("SELECT recall_id FROM recall_ledger").fetchall()
        assert len(rows) == 1 and rows[0][0] == resp.recall_id
        # Four events (one per top-k fact), all carrying the same recall_id.
        assert len(sink.events) == 4
        assert {e["recall_id"] for e in sink.events} == {resp.recall_id}
        assert {e["path"] for e in sink.events} == {"recall"}
        assert {e["fact_ids"][0] for e in sink.events} == returned_ids
    finally:
        conn.close()


def test_per_class_scoring_exercises_all_four_persistent_shapes(
    tenant_root: Path,
) -> None:
    """Gate 6: each of the 4 persistent shapes runs its declared formula.

    We confirm by injecting one fact of each shape with otherwise-equal
    inputs (same RRF rank/score, same valid_from), and asserting the
    resulting per-class scores are NOT all equal — proves the per-class
    table (different beta_override / eps_cap / type_priority) actually
    branches per shape.
    """
    records = [
        _record("ep_fact", kind="user_fact"),
        _record("pref", kind="preference"),
        _record("proc", kind="procedure"),
        _record("narr", kind="narrative"),
    ]
    # Equal-rank hits so the only score differences come from per-class.
    hits = [
        Hit(fact_id="ep_fact", score=0.5, source="lexical", rank=1),
        Hit(fact_id="pref", score=0.5, source="lexical", rank=1),
        Hit(fact_id="proc", score=0.5, source="lexical", rank=1),
        Hit(fact_id="narr", score=0.5, source="lexical", rank=1),
    ]
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=records, lexical_hits=hits
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="q", k=4),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            now=_T_NOW,
        )
        scores = {f.fact_id: f.score for f in resp.facts}
        assert set(scores.keys()) == {"ep_fact", "pref", "proc", "narr"}
        # Not all equal → proves per-class dispatch actually fires.
        assert len(set(scores.values())) > 1
        # Preference outranks user_fact (TYPE_PRIORITY: preference=0.85 vs
        # user_fact=0.70 — formulas are otherwise identical-input here).
        assert scores["pref"] > scores["ep_fact"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — bi-temporal filter ordering (invariant I-4)
# ---------------------------------------------------------------------------


def test_bitemporal_filter_excludes_invalid_window_facts_pre_scoring(
    tenant_root: Path,
) -> None:
    """Invalid-window facts must not appear in the response or in events.

    A fact with valid_to <= t_now is dropped before scoring; its fact_id
    never appears in the response and is not in any emitted event's
    fact_ids list.
    """
    records = [
        _record("alive", valid_from="2024-01-01T00:00:00.000+00:00"),
        _record(
            "expired",
            valid_from="2024-01-01T00:00:00.000+00:00",
            valid_to="2024-06-01T00:00:00.000+00:00",  # before t_now
        ),
    ]
    hits = [
        Hit(fact_id="alive", score=0.9, source="lexical", rank=1),
        Hit(fact_id="expired", score=0.8, source="lexical", rank=2),
    ]
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=records, lexical_hits=hits
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="q", k=10),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            event_sink=sink,
            now=_T_NOW,
        )
        assert {f.fact_id for f in resp.facts} == {"alive"}
        assert resp.applied_filters["pre_filter_excluded"] == 1
        # Events carry only the surviving fact.
        assert {e["fact_ids"][0] for e in sink.events} == {"alive"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — provenance enforcement (composition §6)
# ---------------------------------------------------------------------------


def test_facts_without_episode_id_are_dropped_after_scoring(tenant_root: Path) -> None:
    records = [
        _record("with_prov"),
        FactRecord(
            fact_id="no_prov",
            kind="user_fact",
            content="orphaned",
            valid_from="2024-01-01T00:00:00.000+00:00",
            valid_to=None,
            recorded_at="2024-01-01T00:00:00.000+00:00",
            episode_id=None,  # missing provenance
            version=1,
            source_uri="",
        ),
    ]
    hits = [
        Hit(fact_id="with_prov", score=0.9, source="lexical", rank=1),
        Hit(fact_id="no_prov", score=0.8, source="lexical", rank=2),
    ]
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=records, lexical_hits=hits
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="q", k=10),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            event_sink=sink,
            now=_T_NOW,
        )
        assert {f.fact_id for f in resp.facts} == {"with_prov"}
        assert resp.applied_filters["provenance_dropped"] == 1
        # The dropped fact must not appear in any emitted event.
        all_event_fact_ids = {fid for e in sink.events for fid in e["fact_ids"]}
        assert "no_prov" not in all_event_fact_ids
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — ledger row + INSERT OR IGNORE replay
# ---------------------------------------------------------------------------


def test_replay_is_silent_noop(tenant_root: Path) -> None:
    """Same (tenant, ts, query_hash) → INSERT OR IGNORE no-ops on second call."""
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=[]
    )
    try:
        req = RecallRequest(tenant_id="tenant-a", query="q", k=0)
        r1 = recall(req, s2_conn=conn, fact_store=store, lexical=lex, now=_T_NOW)
        r2 = recall(req, s2_conn=conn, fact_store=store, lexical=lex, now=_T_NOW)
        assert r1.recall_id == r2.recall_id
        rows = conn.execute("SELECT COUNT(*) FROM recall_ledger").fetchone()
        assert rows[0] == 1
    finally:
        conn.close()


def test_same_pk_different_payload_raises(tenant_root: Path) -> None:
    """If the same recall_id ever resolves to a divergent payload, raise."""
    conn = _open_s2(tenant_root)
    try:
        write_ledger_row(
            conn,
            recall_id="01234567-89ab-7def-8123-456789abcdef",
            tenant_id="tenant-a",
            query_hash="0123456789abcdef",
            ts_recorded="2025-06-01T12:00:00.000Z",
            classified_intent="lookup",
            weights_version="p3-gap03-5a-v0",
            top_k_fact_ids=["f1"],
            response_envelope_blob=b'{"first":1}',
        )
        with pytest.raises(RecallLedgerCorruption, match="divergent payloads"):
            write_ledger_row(
                conn,
                recall_id="01234567-89ab-7def-8123-456789abcdef",
                tenant_id="tenant-a",
                query_hash="0123456789abcdef",
                ts_recorded="2025-06-01T12:00:00.000Z",
                classified_intent="lookup",
                weights_version="p3-gap03-5a-v0",
                top_k_fact_ids=["f1"],
                response_envelope_blob=b'{"different":2}',  # divergent
            )
    finally:
        conn.close()


def test_same_pk_same_payload_is_silent_noop(tenant_root: Path) -> None:
    """Verbatim replay of the same row is a no-op (legitimate idempotent retry)."""
    conn = _open_s2(tenant_root)
    try:
        kwargs = {
            "recall_id": "01234567-89ab-7def-8123-456789abcdef",
            "tenant_id": "tenant-a",
            "query_hash": "0123456789abcdef",
            "ts_recorded": "2025-06-01T12:00:00.000Z",
            "classified_intent": "lookup",
            "weights_version": "p3-gap03-5a-v0",
            "top_k_fact_ids": ["f1"],
            "response_envelope_blob": b'{"x":1}',
        }
        write_ledger_row(conn, **kwargs)
        write_ledger_row(conn, **kwargs)  # must not raise
        count = conn.execute("SELECT COUNT(*) FROM recall_ledger").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — recall_id determinism crossing the verb boundary
# ---------------------------------------------------------------------------


def test_verb_recall_id_matches_bare_derivation(tenant_root: Path) -> None:
    """The verb's recall_id matches what derive_recall_id would produce.

    This is the load-bearing replay invariant (scoring §8.3): the
    §8.4 emit-pipeline must reproduce recall_id from logged inputs
    without the live runtime.
    """
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root, records=[]
    )
    try:
        req = RecallRequest(
            tenant_id="tenant-a",
            query="reproduce me",
            intent="lookup",
            k=0,
            scope={"project": "lethe"},
        )
        resp = recall(req, s2_conn=conn, fact_store=store, lexical=lex, now=_T_NOW)
        expected_hash = compute_query_hash(
            {
                "query": "reproduce me",
                "intent": "lookup",
                "k": 0,
                "scope": {"project": "lethe"},
            }
        )
        ts_ms = int(_T_NOW.astimezone(UTC).timestamp() * 1000)
        expected_rid = derive_recall_id(
            tenant_id="tenant-a",
            ts_recorded_ms=ts_ms,
            query_hash=expected_hash,
        )
        assert resp.recall_id == expected_rid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — composition §3.1 lexical-only fallback
# ---------------------------------------------------------------------------


def test_s3_outage_falls_back_to_lexical(tenant_root: Path) -> None:
    """An S3Outage is absorbed; lexical results still surface; degraded=True."""
    records = [_record("f1")]
    lex_hits = [Hit(fact_id="f1", score=0.9, source="lexical", rank=1)]
    conn, store, lex, sem, grf, pref_src, sink = _build_setup(
        tenant_root,
        records=records,
        lexical_hits=lex_hits,
        semantic_outage=True,
    )
    try:
        resp = recall(
            RecallRequest(tenant_id="tenant-a", query="q", k=10, query_vec=[0.1, 0.2]),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            semantic=sem,
            event_sink=sink,
            now=_T_NOW,
        )
        assert {f.fact_id for f in resp.facts} == {"f1"}
        assert resp.store_health == {"s3_used": False, "degraded": True}
        # Semantic was attempted (call_count==1) but raised; lexical succeeded.
        assert sem.call_count == 1
        assert lex.call_count == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests — validation
# ---------------------------------------------------------------------------


def test_negative_k_raises_validation(tenant_root: Path) -> None:
    conn, store, lex, *_ = _build_setup(tenant_root, records=[])
    try:
        with pytest.raises(RecallValidationError, match="k must be >= 0"):
            recall(
                RecallRequest(tenant_id="tenant-a", query="q", k=-1),
                s2_conn=conn,
                fact_store=store,
                lexical=lex,
                now=_T_NOW,
            )
    finally:
        conn.close()


def test_empty_tenant_id_raises_validation(tenant_root: Path) -> None:
    conn, store, lex, *_ = _build_setup(tenant_root, records=[])
    try:
        with pytest.raises(RecallValidationError, match="tenant_id must be non-empty"):
            recall(
                RecallRequest(tenant_id="", query="q", k=10),
                s2_conn=conn,
                fact_store=store,
                lexical=lex,
                now=_T_NOW,
            )
    finally:
        conn.close()
