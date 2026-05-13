"""PPR-wiring coverage for the ``recall`` verb (P4 C8).

Locks the IMPLEMENT 8 swap of the P3 ``rrf_score / rrf_max`` proxy at
:func:`lethe.api.recall._score_one` for the real
:func:`lethe.runtime.scoring.connectedness.connectedness` call against
the live S1 2-hop adjacency exposed by
:meth:`lethe.store.s1_graph.client.S1Client.adjacency_2hop`.

Test matrix (sub-plan §m.S2 + IMPLEMENT 8 amendments A1–A6):

- **T1** end-to-end recall() with seeded adjacency: connectedness
  derivation no longer matches the proxy formula (positive lock).
- **T2** end-to-end recall() with ``s1_client=None``:
  ``score_inputs["connectedness_value"] == 0.0`` for every fact
  (no-graph fallback per §m.O5).
- **T3** degenerate subgraph (< ``DEGREE_FALLBACK_THRESHOLD`` nodes →
  ``degree_percentile`` fallback): exact equality vs. independent
  ``degree_percentile`` call.
- **T4** isolated fact (no edges): ``connectedness_value == 0.0``.
- **T5** richer subgraph (≥ threshold nodes → real PPR path): exact
  equality vs. independent ``compute_connectedness`` call on the same
  adjacency, plus determinism across 3 reps (IMPLEMENT 8 A4).
- **T6** audit: proxy formula gone — file-text and
  ``inspect.getsource(_score_one)`` do not contain
  ``"rrf_score / rrf_max"``.
- **T7** S1Client.adjacency_2hop façade — pins ``group_id`` to
  ``tenant_id``; permissive read (``{}`` for unbootstrapped /
  empty / missing fact_id); BFS bounds the 2-hop slice; no
  cross-tenant leakage (IMPLEMENT 8 A2).
- **T8** legitimate replay with stable adjacency: second
  :func:`recall` call returns identical envelope; ledger silently
  no-ops; no :class:`RecallLedgerCorruption` (IMPLEMENT 8 A1).
- **T9** mutated adjacency between replays raises
  :class:`RecallLedgerCorruption`: locks the documented
  determinism narrowing (IMPLEMENT 8 A1).
- **T10** ``adjacency_2hop`` returned dict is independent of backend
  state — caller mutations never bleed back (IMPLEMENT 8 A5).
- Plus: tenant-mismatch between ``request.tenant_id`` and
  ``s1_client.tenant_id`` raises :class:`RecallValidationError`
  (IMPLEMENT 8 A3).
"""

from __future__ import annotations

import inspect
import sqlite3
from collections.abc import Mapping, Sequence
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
)
from lethe.runtime.preferences_prepend import PreferencePage
from lethe.runtime.retrievers import Hit, S3Outage
from lethe.runtime.scoring.connectedness import (
    DEGREE_FALLBACK_THRESHOLD,
    degree_percentile,
)
from lethe.runtime.scoring.connectedness import (
    connectedness as compute_connectedness,
)
from lethe.store.s1_graph.client import S1Client, _InMemoryGraphBackend
from lethe.store.s2_meta import S2Schema

# ---------------------------------------------------------------------------
# Test doubles (mirror tests/api/test_recall.py for substrate parity)
# ---------------------------------------------------------------------------


@dataclass
class _FakeFactStore:
    records: dict[str, FactRecord]

    def fetch_many(self, fact_ids: Sequence[str], *, t_now: datetime) -> list[FactRecord]:
        return [self.records[f] for f in fact_ids if f in self.records]


@dataclass
class _FakeLexical:
    hits: list[Hit]

    def search(self, *, query: str, k: int) -> list[Hit]:
        return list(self.hits[:k])


@dataclass
class _FakeSemantic:
    hits: list[Hit] = field(default_factory=list)
    raise_outage: bool = False

    def search(self, *, query_vec: Sequence[float], k: int) -> list[Hit]:
        if self.raise_outage:
            raise S3Outage("synthetic outage for test")
        return list(self.hits[:k])


@dataclass
class _FakeGraph:
    hits: list[Hit] = field(default_factory=list)

    def seed_topk(self, *, query: str, k: int) -> list[Hit]:
        return list(self.hits[:k])


@dataclass
class _FakePreferenceSource:
    pages: list[PreferencePage]

    def list_preferences(self, *, tenant_id: str) -> list[PreferencePage]:
        return list(self.pages)


class _RecordingSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_T_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_TENANT = "tenant-ppr"


def _open_s2(tenant_root: Path) -> sqlite3.Connection:
    return S2Schema(tenant_root=tenant_root).create()


def _record(
    fact_id: str,
    *,
    kind: str = "user_fact",
    valid_from: str = "2024-01-01T00:00:00.000000+00:00",
    content: str = "ppr fact",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        kind=kind,
        content=content,
        valid_from=valid_from,
        valid_to=None,
        recorded_at=valid_from,
        episode_id=f"ep-{fact_id}",
        version=1,
        source_uri=f"file://{fact_id}.md",
    )


def _make_s1_client_with_dense_graph(
    *,
    tenant_id: str = _TENANT,
    n_hub_neighbors: int = 14,
    chain_extra: int = 0,
) -> tuple[S1Client, _InMemoryGraphBackend, list[str]]:
    """Build an :class:`S1Client` over a backend seeded with a dense graph.

    Returns ``(client, backend, fact_ids)`` where ``fact_ids[0]`` is
    the hub. The hub is bidirectionally connected to ``n_hub_neighbors``
    leaves, optionally plus a chain of ``chain_extra`` further nodes
    extending from the last leaf (for cap / depth tests).
    """
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(tenant_id)
    fact_ids = [f"f{i}" for i in range(1 + n_hub_neighbors + chain_extra)]
    hub = fact_ids[0]
    for leaf in fact_ids[1 : 1 + n_hub_neighbors]:
        backend._seed_adjacency_edge(group_id=tenant_id, src=hub, dst=leaf, weight=1.0)
        backend._seed_adjacency_edge(group_id=tenant_id, src=leaf, dst=hub, weight=1.0)
    chain = fact_ids[1 + n_hub_neighbors :]
    if chain:
        prev = fact_ids[n_hub_neighbors]  # last leaf
        for nxt in chain:
            backend._seed_adjacency_edge(group_id=tenant_id, src=prev, dst=nxt, weight=1.0)
            backend._seed_adjacency_edge(group_id=tenant_id, src=nxt, dst=prev, weight=1.0)
            prev = nxt
    client = S1Client(backend, tenant_id=tenant_id)
    client.bootstrap()
    return client, backend, fact_ids


def _build_recall_inputs(
    tenant_root: Path,
    fact_ids: Sequence[str],
    *,
    lex_score_step: float = 0.1,
) -> tuple[sqlite3.Connection, _FakeFactStore, _FakeLexical, _RecordingSink]:
    """Build the verb's substrate inputs for a recall over ``fact_ids``.

    Lexical hits descend in score (rank 1 = highest score) so the RRF
    fusion has a meaningful ``rrf_max``. The fact_store mirrors the
    fact_ids set 1:1.
    """
    records = [_record(fid) for fid in fact_ids]
    conn = _open_s2(tenant_root)
    store = _FakeFactStore({r.fact_id: r for r in records})
    lex = _FakeLexical(
        hits=[
            Hit(
                fact_id=fid,
                score=1.0 - i * lex_score_step,
                source="lexical",
                rank=i + 1,
            )
            for i, fid in enumerate(fact_ids)
        ]
    )
    sink = _RecordingSink()
    return conn, store, lex, sink


# ---------------------------------------------------------------------------
# T1 — end-to-end recall() with PPR connectedness
# ---------------------------------------------------------------------------


def test_recall_with_s1_client_uses_ppr_connectedness(tenant_root: Path) -> None:
    """T1: with seeded adjacency + s1_client, connectedness derivation
    is the real PPR/degree-percentile, not the old ``rrf_score / rrf_max``
    proxy. Locks the swap (sub-plan §m.S2 — proxy-removal lock #1)."""
    s1_client, _backend, fact_ids = _make_s1_client_with_dense_graph()
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        resp = recall(
            RecallRequest(tenant_id=_TENANT, query="q", k=len(fact_ids)),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        assert len(resp.facts) == len(fact_ids)
        # rrf_max from the verb is max(rrf score) across the fused list.
        # We can't reach into the verb's local; instead, demonstrate the
        # POSITIVE lock: at least one returned fact's connectedness_value
        # does NOT equal its (rrf_score / rrf_max) proxy.
        rrf_scores = [f.score_inputs["rrf_score"] for f in resp.facts]
        rrf_max = max(rrf_scores)
        assert rrf_max > 0.0  # sanity: the proxy formula was non-trivial
        proxy_values = [(f.score_inputs["rrf_score"] / rrf_max) for f in resp.facts]
        connectedness_values = [f.score_inputs["connectedness_value"] for f in resp.facts]
        # At least one fact must diverge from the proxy — the swap is
        # observable at the score_inputs surface.
        diverged = any(
            abs(c - p) > 1e-9 for c, p in zip(connectedness_values, proxy_values, strict=True)
        )
        assert diverged, (
            "All connectedness values match the legacy proxy "
            f"(rrf_score / rrf_max); expected at least one to diverge. "
            f"connectedness={connectedness_values} proxy={proxy_values}"
        )
        # All values still in [0, 1].
        for v in connectedness_values:
            assert 0.0 <= v <= 1.0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T2 — recall() without s1_client → P3 RRF-rank proxy fallback (A7)
# ---------------------------------------------------------------------------


def test_recall_without_s1_client_uses_proxy_fallback(
    tenant_root: Path,
) -> None:
    """T2 (A7-rewritten): ``s1_client=None`` (default) → connectedness
    degrades to the P3 RRF-rank proxy ``(rrf_score / rrf_max)`` clamped
    into ``[0, 1]`` so DMR sanity replay and other no-graph callers
    retain meaningful per-class ordering. Verifies the math AND that
    connectedness_value is NOT 0.0 (A1's premise was wrong; A7
    canonicalises the proxy fallback)."""
    fact_ids = [f"f{i}" for i in range(5)]
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        resp = recall(
            RecallRequest(tenant_id=_TENANT, query="q", k=len(fact_ids)),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            event_sink=sink,
            now=_T_NOW,
        )
        assert len(resp.facts) == len(fact_ids)
        rrf_max = max(f.score_inputs["rrf_score"] for f in resp.facts)
        assert rrf_max > 0.0, "fixture should produce non-zero RRF scores"
        for f in resp.facts:
            assert "connectedness_value" in f.score_inputs
            assert "rrf_score" in f.score_inputs
            expected = max(0.0, min(1.0, f.score_inputs["rrf_score"] / rrf_max))
            assert f.score_inputs["connectedness_value"] == pytest.approx(expected, abs=1e-12), (
                f"fact {f.fact_id}: expected proxy {expected!r}, "
                f"got {f.score_inputs['connectedness_value']!r}"
            )
        # Lock the spirit of A7: at least one fact has a non-zero
        # connectedness contribution under the proxy fallback.
        assert any(f.score_inputs["connectedness_value"] > 0.0 for f in resp.facts), (
            "proxy fallback must produce non-zero values for at least one fact"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T3 — degenerate subgraph → degree_percentile fallback
# ---------------------------------------------------------------------------


def test_degenerate_subgraph_falls_back_to_degree_percentile(
    tenant_root: Path,
) -> None:
    """T3: a 2-hop slice with fewer than ``DEGREE_FALLBACK_THRESHOLD``
    nodes triggers the ``degree_percentile`` fallback inside
    ``connectedness()``. We verify by computing the expected value
    independently against the same adjacency the backend returns."""
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(_TENANT)
    # 3-node chain: f1—f2—f3 (well below DEGREE_FALLBACK_THRESHOLD=10).
    backend._seed_adjacency_edge(group_id=_TENANT, src="f1", dst="f2", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="f2", dst="f1", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="f2", dst="f3", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="f3", dst="f2", weight=1.0)
    s1_client = S1Client(backend, tenant_id=_TENANT)
    s1_client.bootstrap()
    fact_ids = ["f1", "f2", "f3"]
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        resp = recall(
            RecallRequest(tenant_id=_TENANT, query="q", k=len(fact_ids)),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        # Sanity: subgraph size is BELOW the fallback threshold.
        adj_for_seed_f2 = s1_client.adjacency_2hop(fact_id="f2")
        assert len(adj_for_seed_f2) < DEGREE_FALLBACK_THRESHOLD
        # Compute expected fallback values directly. ``connectedness()``
        # computes ``degree_percentile(adj, node=fact_id)`` where ``adj``
        # is the 2-hop slice for that fact_id (NOT the full tenant adj).
        by_id = {f.fact_id: f for f in resp.facts}
        for fid in fact_ids:
            adj = s1_client.adjacency_2hop(fact_id=fid)
            expected = degree_percentile(adj, node=fid)
            assert by_id[fid].score_inputs["connectedness_value"] == pytest.approx(
                expected, abs=1e-12
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T4 — isolated fact → 0.0 connectedness
# ---------------------------------------------------------------------------


def test_isolated_fact_returns_zero_connectedness(tenant_root: Path) -> None:
    """T4: a fact with NO edges in the tenant adjacency yields
    ``connectedness_value == 0.0`` (sub-plan §m.O8 case 3 + scoring §3.2
    isolated-node case)."""
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(_TENANT)
    # Seed edges among other facts; the seed fact (f0) is NOT in any edge.
    backend._seed_adjacency_edge(group_id=_TENANT, src="f1", dst="f2", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="f2", dst="f1", weight=1.0)
    s1_client = S1Client(backend, tenant_id=_TENANT)
    s1_client.bootstrap()
    fact_ids = ["f0"]
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        resp = recall(
            RecallRequest(tenant_id=_TENANT, query="q", k=1),
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        assert len(resp.facts) == 1
        assert resp.facts[0].fact_id == "f0"
        assert resp.facts[0].score_inputs["connectedness_value"] == 0.0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T5 — richer subgraph: real PPR equals independent compute_connectedness
# ---------------------------------------------------------------------------


def test_richer_subgraph_returns_value_matching_compute_connectedness(
    tenant_root: Path,
) -> None:
    """T5 (IMPLEMENT 8 A4): on a 15-node graph (above
    ``DEGREE_FALLBACK_THRESHOLD``), ``connectedness_value`` matches an
    independent ``compute_connectedness(adj, fact_id=hub)`` call to
    floating-point precision; deterministic across 3 reps."""
    s1_client, _backend, fact_ids = _make_s1_client_with_dense_graph(n_hub_neighbors=14)
    hub = fact_ids[0]
    # Verify the slice is large enough that the real PPR path runs.
    adj_hub = s1_client.adjacency_2hop(fact_id=hub)
    assert len(adj_hub) >= DEGREE_FALLBACK_THRESHOLD
    expected = compute_connectedness(adj_hub, fact_id=hub)
    assert 0.0 < expected <= 1.0  # hub gets non-trivial PPR mass

    observed: list[float] = []
    for _ in range(3):
        # Fresh S2 conn per replay (different recall_id via different
        # tenant_id → no ledger collision; we only care about the score
        # value here, not the ledger semantics — that's T8/T9).
        sub_root = tenant_root / f"rep-{len(observed)}"
        sub_root.mkdir(parents=True, exist_ok=True)
        conn, store, lex, sink = _build_recall_inputs(sub_root, [hub])
        try:
            resp = recall(
                RecallRequest(tenant_id=_TENANT, query="q", k=1),
                s2_conn=conn,
                fact_store=store,
                lexical=lex,
                s1_client=s1_client,
                event_sink=sink,
                now=_T_NOW,
            )
            assert len(resp.facts) == 1
            observed.append(resp.facts[0].score_inputs["connectedness_value"])
        finally:
            conn.close()
    # All three reps return EXACTLY the same value (PPR is deterministic
    # for fixed adj+seed+damping+max_iter+tol).
    assert observed == [observed[0], observed[0], observed[0]], (
        f"PPR not deterministic across reps: {observed}"
    )
    assert observed[0] == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# T6 — _score_one dispatches PPR vs proxy on s1_client (A7-repurposed)
# ---------------------------------------------------------------------------


def test_score_one_dispatches_proxy_vs_ppr_per_s1_client() -> None:
    """T6 (A7-rewritten — supersedes the original 'proxy formula
    removed' lock): _score_one's source MUST contain BOTH the PPR call
    site (when ``s1_client`` is supplied) AND the proxy formula (the
    no-graph fallback that preserves DMR sanity replay). Both branches
    MUST be conditional on ``s1_client``. (Source-text checks only;
    no bytecode inspection — see IMPLEMENT 8 A6.)"""
    import sys

    # ``lethe.api/__init__.py`` re-exports ``recall`` (the function),
    # which shadows the ``recall`` submodule on ``lethe.api`` —
    # ``import lethe.api.recall as recall_mod`` therefore resolves to
    # the function, not the module. Round-trip via ``sys.modules``,
    # which holds the module under its dotted import path.
    recall_mod = sys.modules["lethe.api.recall"]
    score_one_src = inspect.getsource(recall_mod._score_one)

    # PPR branch — wires real connectedness against live S1 adjacency.
    assert "compute_connectedness(" in score_one_src, (
        "_score_one source must call compute_connectedness() in the "
        "s1_client-supplied branch (P4 C8 PPR wire-in)"
    )
    # Proxy branch — preserved as the no-graph fallback (A7).
    assert "rrf_score / rrf_max" in score_one_src, (
        "_score_one source must retain the 'rrf_score / rrf_max' proxy "
        "formula in the no-graph fallback branch (A7); cleanup tracked "
        "to P9+ alongside real fact-extraction"
    )
    # Dispatch shape — both branches gate on ``s1_client``.
    assert "if s1_client is not None" in score_one_src, (
        "_score_one source must dispatch on 'if s1_client is not None' "
        "to gate the PPR branch vs the proxy fallback"
    )
    # Spatial check — the PPR call is INSIDE the s1_client conditional
    # block (the conditional appears strictly before the PPR call site).
    # Search for the proxy formula AFTER the conditional so we don't
    # match the docstring's reference to it (the docstring lives above
    # the function body and mentions the formula by name).
    cond_idx = score_one_src.find("if s1_client is not None")
    ppr_idx = score_one_src.find("compute_connectedness(", cond_idx)
    proxy_idx = score_one_src.find("rrf_score / rrf_max", cond_idx)
    assert cond_idx >= 0 and ppr_idx > cond_idx, (
        "PPR call must appear after (i.e. inside) the s1_client "
        "conditional block in _score_one source"
    )
    assert proxy_idx > cond_idx, (
        "Proxy fallback must appear after (i.e. inside the else of) "
        "the s1_client conditional block in _score_one source"
    )


# ---------------------------------------------------------------------------
# T7 — S1Client.adjacency_2hop façade contract
# ---------------------------------------------------------------------------


def test_s1_client_adjacency_2hop_facade_pins_tenant_and_is_permissive() -> None:
    """T7 (sub-plan §m.O7/O8 + IMPLEMENT 8 A2): façade pins ``group_id``
    to ``self._tenant_id``; permissive read posture; BFS bounds the
    2-hop slice; cross-tenant edges do not leak."""
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant("tenant-x")
    s1_client = S1Client(backend, tenant_id="tenant-x")
    s1_client.bootstrap()
    # (a) Bootstrapped-but-no-edges → {}
    assert s1_client.adjacency_2hop(fact_id="anything") == {}
    # (b) Unbootstrapped tenant → {} (façade pins to "tenant-x"; we
    #     can't directly call adjacency_2hop on a different tenant
    #     via the façade, but we can verify the backend-level
    #     permissive read).
    assert backend.adjacency_2hop(group_id="never-bootstrapped", fact_id="x") == {}
    # (c) 2-hop slice prunes nodes deeper than depth 2.
    # Seed bidirectionally — the in-memory backend stores edges in
    # their native (directed) direction (sub-plan §m.O3); for the
    # symmetric assertions below we seed both directions so the
    # restricted slice has the expected adjacency-list shape.
    backend._seed_adjacency_edge(group_id="tenant-x", src="f1", dst="f2", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f2", dst="f1", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f2", dst="f3", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f3", dst="f2", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f3", dst="f4", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f4", dst="f3", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f4", dst="f5", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-x", src="f5", dst="f4", weight=1.0)
    adj = s1_client.adjacency_2hop(fact_id="f1")
    assert sorted(adj.keys()) == ["f1", "f2", "f3"], (
        f"BFS should bound to depth 2; got {sorted(adj.keys())}"
    )
    # f1's edges restricted to {f2}, f2's to {f1, f3}, f3's to {f2}
    # (f4 dropped because it's outside the visited set).
    assert sorted(adj["f1"].keys()) == ["f2"]
    assert sorted(adj["f2"].keys()) == ["f1", "f3"]
    assert sorted(adj["f3"].keys()) == ["f2"]
    # (d) Cross-fact isolation: another tenant's edges don't leak.
    backend.bootstrap_tenant("tenant-y")
    backend._seed_adjacency_edge(group_id="tenant-y", src="g1", dst="g2", weight=1.0)
    backend._seed_adjacency_edge(group_id="tenant-y", src="g2", dst="g1", weight=1.0)
    adj_x_again = s1_client.adjacency_2hop(fact_id="f1")
    assert "g1" not in adj_x_again
    assert "g2" not in adj_x_again
    # And tenant-x has no nodes from tenant-y appearing in any value.
    for nbrs in adj_x_again.values():
        assert "g1" not in nbrs
        assert "g2" not in nbrs
    # (e) fact_id absent from edges → {}
    assert s1_client.adjacency_2hop(fact_id="not-a-node") == {}


# ---------------------------------------------------------------------------
# T8 — legitimate replay with stable adjacency (silent ledger no-op)
# ---------------------------------------------------------------------------


def test_ledger_replay_silent_noop_when_adjacency_unchanged(
    tenant_root: Path,
) -> None:
    """T8 (IMPLEMENT 8 A1): two replays of the same recall_id with
    UNCHANGED graph state are silent ledger no-ops; the second call
    returns the identical envelope; no :class:`RecallLedgerCorruption`."""
    s1_client, _backend, fact_ids = _make_s1_client_with_dense_graph(n_hub_neighbors=14)
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        request = RecallRequest(tenant_id=_TENANT, query="q", k=len(fact_ids))
        resp1 = recall(
            request,
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        # Replay (no graph mutation between calls).
        resp2 = recall(
            request,
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        assert resp1.recall_id == resp2.recall_id
        assert [f.fact_id for f in resp1.facts] == [f.fact_id for f in resp2.facts]
        for a, b in zip(resp1.facts, resp2.facts, strict=True):
            assert a.score == b.score
            assert dict(a.score_inputs) == dict(b.score_inputs)
        # Ledger has exactly one row (INSERT OR IGNORE swallowed the dup).
        rows = conn.execute("SELECT recall_id FROM recall_ledger").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == resp1.recall_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T9 — mutated adjacency between replays raises RecallLedgerCorruption
# ---------------------------------------------------------------------------


def test_ledger_replay_raises_corruption_when_adjacency_mutates(
    tenant_root: Path,
) -> None:
    """T9 (IMPLEMENT 8 A1): mutating the S1 adjacency between two
    replays of the same recall_id surfaces as
    :class:`RecallLedgerCorruption`. Locks the documented determinism
    narrowing — if a future commit adds snapshot/replay it must update
    this test."""
    # Start with a 3-node chain so the seed is NOT a hub —
    # ``degree_percentile`` fires (3 nodes < DEGREE_FALLBACK_THRESHOLD
    # = 10) and the seed gets a non-1.0 fallback value:
    #   adj_2hop(seed) = {seed, n1, n2}; seed's neighborhood degrees
    #   = [own=1, n1=2], max=2 → degree_percentile(seed) = 1/2 = 0.5
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(_TENANT)
    backend._seed_adjacency_edge(group_id=_TENANT, src="seed", dst="n1", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="n1", dst="seed", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="n1", dst="n2", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="n2", dst="n1", weight=1.0)
    s1_client = S1Client(backend, tenant_id=_TENANT)
    s1_client.bootstrap()

    # Compute expected BEFORE-mutation connectedness directly.
    before_adj = s1_client.adjacency_2hop(fact_id="seed")
    before_value = compute_connectedness(before_adj, fact_id="seed")

    fact_ids = ["seed"]
    conn, store, lex, sink = _build_recall_inputs(tenant_root, fact_ids)
    try:
        request = RecallRequest(tenant_id=_TENANT, query="q", k=1)
        resp1 = recall(
            request,
            s2_conn=conn,
            fact_store=store,
            lexical=lex,
            s1_client=s1_client,
            event_sink=sink,
            now=_T_NOW,
        )
        assert resp1.facts[0].score_inputs["connectedness_value"] == pytest.approx(
            before_value, abs=1e-12
        )

        # Mutate adjacency — add many new neighbors so the seed now has
        # a 2-hop slice ≥ DEGREE_FALLBACK_THRESHOLD nodes (switches
        # connectedness path from degree_percentile to real PPR, which
        # produces a different value).
        for i in range(20):
            backend._seed_adjacency_edge(group_id=_TENANT, src="seed", dst=f"new-{i}", weight=1.0)
            backend._seed_adjacency_edge(group_id=_TENANT, src=f"new-{i}", dst="seed", weight=1.0)

        after_adj = s1_client.adjacency_2hop(fact_id="seed")
        after_value = compute_connectedness(after_adj, fact_id="seed")
        # Sanity: the mutation actually changed the connectedness value.
        assert before_value != pytest.approx(after_value, abs=1e-9), (
            "Test setup bug: mutation did not change connectedness; "
            "T9 cannot lock the determinism narrowing."
        )

        with pytest.raises(RecallLedgerCorruption):
            recall(
                request,
                s2_conn=conn,
                fact_store=store,
                lexical=lex,
                s1_client=s1_client,
                event_sink=sink,
                now=_T_NOW,
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T10 — adjacency_2hop returned dict is independent of backend state
# ---------------------------------------------------------------------------


def test_adjacency_2hop_returned_dict_is_independent_of_backend_state() -> None:
    """T10 (IMPLEMENT 8 A5): mutating the returned ``Adjacency`` must
    not bleed back into backend state — caller-driven mutation is
    isolated thanks to the deep-copy in
    :meth:`_InMemoryGraphBackend.adjacency_2hop`."""
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(_TENANT)
    backend._seed_adjacency_edge(group_id=_TENANT, src="a", dst="b", weight=1.0)
    backend._seed_adjacency_edge(group_id=_TENANT, src="b", dst="a", weight=1.0)
    first = backend.adjacency_2hop(group_id=_TENANT, fact_id="a")
    # Mutate the returned inner neighbor map (cast away Mapping
    # invariance for the destructive write).
    first_inner = first["a"]
    assert isinstance(first_inner, dict), (
        "Test invariant: in-memory backend returns mutable dict slices"
    )
    first_inner["b"] = 999.0
    first_inner["evil-injected-node"] = 42.0
    # A second lookup must observe the original (un-mutated) state.
    second = backend.adjacency_2hop(group_id=_TENANT, fact_id="a")
    assert second["a"]["b"] == 1.0
    assert "evil-injected-node" not in second["a"]
    # And the backend's internal _edges dict matches.
    raw = backend._edges_for(_TENANT)
    assert raw["a"]["b"] == 1.0
    assert "evil-injected-node" not in raw["a"]


# ---------------------------------------------------------------------------
# Tenant-mismatch validation (IMPLEMENT 8 A3)
# ---------------------------------------------------------------------------


def test_tenant_mismatch_between_request_and_s1_client_raises(
    tenant_root: Path,
) -> None:
    """IMPLEMENT 8 A3: passing an :class:`S1Client` scoped to one
    tenant alongside a :class:`RecallRequest` for a different tenant
    raises :class:`RecallValidationError`. Validation runs before any
    retriever / fact_store / s2 lookup."""
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant("tenant-a")
    backend.bootstrap_tenant("tenant-b")
    s1_client_a = S1Client(backend, tenant_id="tenant-a")
    s1_client_a.bootstrap()

    # Track that the verb does NOT consult substrate before raising.
    @dataclass
    class _LoudFactStore:
        called: bool = False

        def fetch_many(self, fact_ids: Sequence[str], *, t_now: datetime) -> list[FactRecord]:
            self.called = True
            raise AssertionError("fetch_many must NOT be called on tenant mismatch")

    @dataclass
    class _LoudLexical:
        called: bool = False

        def search(self, *, query: str, k: int) -> list[Hit]:
            self.called = True
            raise AssertionError("lexical.search must NOT be called on tenant mismatch")

    store = _LoudFactStore()
    lex = _LoudLexical()
    conn = _open_s2(tenant_root)
    try:
        with pytest.raises(RecallValidationError) as excinfo:
            recall(
                RecallRequest(tenant_id="tenant-b", query="q", k=5),
                s2_conn=conn,
                fact_store=store,
                lexical=lex,
                s1_client=s1_client_a,
                now=_T_NOW,
            )
        msg = str(excinfo.value)
        assert "tenant-a" in msg
        assert "tenant-b" in msg
        assert store.called is False
        assert lex.called is False
        # Ledger row NOT written on validation failure.
        rows = conn.execute("SELECT recall_id FROM recall_ledger").fetchall()
        assert rows == []
    finally:
        conn.close()
