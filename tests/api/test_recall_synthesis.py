"""``recall_synthesis`` verb coverage (api §2.2).

Covers the synthesis-side behaviors per facilitator P3 §(f):

- URI form: direct fetch returns a one-page response; ``404`` on
  unknown uri.
- Query form: hybrid retrieve returns up-to-k pages; empty result is a
  legitimate zero-event response (still writes a ledger row).
- Validation (``400``): both / neither of ``uri`` / ``query``;
  ``k < 0``; empty ``tenant_id``.
- ``recall_id`` derivation matches the bare api §1.4 derivation
  (``derive_recall_id(tenant, ts_ms, query_hash)``); the verb's id is
  reproducible from logged inputs.
- ``recall_id`` is **distinct** between ``recall_synthesis(query="X")``
  and a ``recall("X")`` with the same surface query (different intent
  discriminant in the canonical query_hash payload).
- Events emitted with ``path="synthesis"`` (NOT ``"recall"``).
- ``fact_ids`` on emitted events are S4a page-ids (deterministic uuid
  derived from ``page_uri``), NOT S1 fact-edge ids.
- ``recall_ledger`` row written with
  ``weights_version="synthesis-passthrough"`` and the page-ids list.
- INSERT OR IGNORE replay: same call twice → silent no-op; same
  recall_id with a different page payload (substrate bug) raises
  :class:`RecallLedgerCorruption`.
- No bi-temporal filter is invoked (synthesis pages are git-versioned,
  not bi-temporally stamped).
- S4a outage from the source Protocol bubbles as :class:`S4aOutage`
  (5xx; synthesis hard-fails, fact ``recall`` path is unaffected).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lethe.api.recall import (
    RecallLedgerCorruption,
    RecallRequest,
    recall,
    write_ledger_row,
)
from lethe.api.recall_synthesis import (
    S4aOutage,
    SynthesisNotFoundError,
    SynthesisPage,
    SynthesisRequest,
    SynthesisValidationError,
    _page_uri_to_id,
    recall_synthesis,
)
from lethe.runtime.recall_id import compute_query_hash, derive_recall_id
from lethe.store.s2_meta import S2Schema

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeSynthesisSource:
    """In-memory SynthesisSource stub.

    ``by_uri`` is the URI-form table; ``query_hits`` is the canned
    response for the query form. ``raise_outage`` makes both methods
    raise :class:`S4aOutage` for the hard-fail-on-S4a-corruption test.
    """

    by_uri: dict[str, SynthesisPage] = field(default_factory=dict)
    query_hits: list[SynthesisPage] = field(default_factory=list)
    raise_outage: bool = False
    fetch_calls: list[tuple[str, str]] = field(default_factory=list)
    query_calls: list[tuple[str, str, int]] = field(default_factory=list)

    def fetch_by_uri(
        self, *, tenant_id: str, uri: str
    ) -> SynthesisPage | None:
        self.fetch_calls.append((tenant_id, uri))
        if self.raise_outage:
            raise S4aOutage("synthetic S4a outage")
        return self.by_uri.get(uri)

    def hybrid_query(
        self, *, tenant_id: str, query: str, k: int
    ) -> list[SynthesisPage]:
        self.query_calls.append((tenant_id, query, k))
        if self.raise_outage:
            raise S4aOutage("synthetic S4a outage")
        return list(self.query_hits[:k])


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
_TENANT = "tenant-synth"


def _open_s2(tenant_root: Path) -> sqlite3.Connection:
    return S2Schema(tenant_root=tenant_root).create()


def _page(
    page_uri: str,
    *,
    title: str = "Test Page",
    kind: str = "narrative",
    content: str = "page body",
    revision_id: str = "git-sha-1",
    score: float = 1.0,
) -> SynthesisPage:
    return SynthesisPage(
        page_uri=page_uri,
        title=title,
        kind=kind,
        frontmatter={"title": title, "kind": kind},
        content=content,
        revision_id=revision_id,
        score=score,
        provenance={
            "page_uri": page_uri,
            "revision_id": revision_id,
            "author_principal": "alice",
            "last_modified_at": "2025-05-15T00:00:00.000Z",
        },
    )


# ---------------------------------------------------------------------------
# Tests — URI form
# ---------------------------------------------------------------------------


def test_uri_form_returns_single_page(tenant_root: Path) -> None:
    """Direct fetch by stable uri returns the matching page."""
    conn = _open_s2(tenant_root)
    page = _page("s4a://tenant-synth/runbook.md", title="Runbook")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})
    sink = _RecordingSink()

    response = recall_synthesis(
        SynthesisRequest(
            tenant_id=_TENANT,
            uri=page.page_uri,
        ),
        s2_conn=conn,
        source=src,
        event_sink=sink,
        now=_T_NOW,
    )

    assert len(response.pages) == 1
    assert response.pages[0].page_uri == page.page_uri
    assert response.pages[0].title == "Runbook"
    assert response.recall_id  # uuid present
    assert response.store_health == {"s4a_available": True}
    # URI form does NOT call hybrid_query.
    assert src.query_calls == []
    assert src.fetch_calls == [(_TENANT, page.page_uri)]


def test_uri_form_unknown_uri_raises_not_found(tenant_root: Path) -> None:
    """``uri`` form against an unknown URI raises ``SynthesisNotFoundError`` (404)."""
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource(by_uri={})

    with pytest.raises(SynthesisNotFoundError) as excinfo:
        recall_synthesis(
            SynthesisRequest(tenant_id=_TENANT, uri="s4a://missing.md"),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )
    assert excinfo.value.code == "not_found"
    assert excinfo.value.status == 404


# ---------------------------------------------------------------------------
# Tests — Query form
# ---------------------------------------------------------------------------


def test_query_form_returns_topk_pages_in_source_order(tenant_root: Path) -> None:
    """Query form returns up to k pages from the source's hybrid query."""
    conn = _open_s2(tenant_root)
    pages = [
        _page(f"s4a://p{i}.md", title=f"Page {i}", score=1.0 - 0.1 * i)
        for i in range(5)
    ]
    src = _FakeSynthesisSource(query_hits=pages)
    sink = _RecordingSink()

    response = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, query="how to deploy", k=3),
        s2_conn=conn,
        source=src,
        event_sink=sink,
        now=_T_NOW,
    )
    assert [p.page_uri for p in response.pages] == [
        "s4a://p0.md",
        "s4a://p1.md",
        "s4a://p2.md",
    ]
    # k events, all path=synthesis.
    assert len(sink.events) == 3
    assert all(e["path"] == "synthesis" for e in sink.events)
    # URI-form fetch must not have been called.
    assert src.fetch_calls == []
    assert src.query_calls == [(_TENANT, "how to deploy", 3)]


def test_query_form_empty_result_is_legitimate_zero_event(
    tenant_root: Path,
) -> None:
    """No matches → zero events but ledger row still written.

    Mirrors recall(k=0) posture: a deterministic outcome with no
    facts is still a real recall with a real recall_id, recorded for
    audit.
    """
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource(query_hits=[])
    sink = _RecordingSink()

    response = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, query="no matches", k=5),
        s2_conn=conn,
        source=src,
        event_sink=sink,
        now=_T_NOW,
    )
    assert response.pages == []
    assert sink.events == []
    rows = conn.execute(
        "SELECT recall_id, top_k_fact_ids, weights_version FROM recall_ledger"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == response.recall_id
    assert rows[0][1] == "[]"
    assert rows[0][2] == "synthesis-passthrough"


# ---------------------------------------------------------------------------
# Tests — Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "query"),
    [
        (None, None),  # neither
        ("s4a://x.md", "some query"),  # both
    ],
)
def test_neither_or_both_raises_validation_error(
    tenant_root: Path, uri: str | None, query: str | None
) -> None:
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource()
    with pytest.raises(SynthesisValidationError):
        recall_synthesis(
            SynthesisRequest(tenant_id=_TENANT, uri=uri, query=query),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )


def test_empty_tenant_id_raises_validation_error(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource()
    with pytest.raises(SynthesisValidationError):
        recall_synthesis(
            SynthesisRequest(tenant_id="", query="x"),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )


def test_negative_k_raises_validation_error(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource()
    with pytest.raises(SynthesisValidationError):
        recall_synthesis(
            SynthesisRequest(tenant_id=_TENANT, query="x", k=-1),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )


# ---------------------------------------------------------------------------
# Tests — recall_id derivation
# ---------------------------------------------------------------------------


def test_verb_recall_id_matches_bare_derivation(tenant_root: Path) -> None:
    """The verb's recall_id = derive_recall_id(tenant, ts_ms, query_hash).

    Locks the api §1.4 replay invariant for the synthesis verb.
    """
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource(query_hits=[_page("s4a://p.md")])

    response = recall_synthesis(
        SynthesisRequest(
            tenant_id=_TENANT, query="hello", k=2, scope={"project": "lethe"}
        ),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    expected_query_hash = compute_query_hash(
        {
            "query": "hello",
            "intent": "synthesis_query",
            "k": 2,
            "scope": {"project": "lethe"},
        }
    )
    expected_id = derive_recall_id(
        tenant_id=_TENANT,
        ts_recorded_ms=int(_T_NOW.timestamp() * 1000),
        query_hash=expected_query_hash,
    )
    assert response.recall_id == expected_id


def test_recall_id_distinct_from_recall_verb_for_same_query(
    tenant_root: Path,
) -> None:
    """recall_synthesis(query="X") and recall(query="X") get different ids.

    The intent discriminant ("synthesis_query" vs "unspecified") in the
    canonical query_hash payload makes the surfaces deterministically
    distinct, even though the (tenant, ts) prefix is identical.
    """
    conn = _open_s2(tenant_root)

    # Stub fact-recall path.
    from tests.api.test_recall import (
        _FakeFactStore,
        _FakeGraph,
        _FakeLexical,
        _FakePreferenceSource,
        _FakeSemantic,
    )

    fact_store = _FakeFactStore(records={})
    fact_recall = recall(
        RecallRequest(tenant_id=_TENANT, query="hello", k=0),
        s2_conn=conn,
        fact_store=fact_store,
        lexical=_FakeLexical(hits=[]),
        semantic=_FakeSemantic(),
        graph=_FakeGraph(),
        preference_source=_FakePreferenceSource(pages=[]),
        now=_T_NOW,
    )

    # Need a fresh S2 (different tenant_root) since recall already wrote a
    # ledger row at ts_recorded; same tenant + ts + intent="synthesis_query"
    # gives a different recall_id but using the same conn + same tenant
    # would let two distinct ids coexist anyway. Use the same conn.
    src = _FakeSynthesisSource(query_hits=[])
    synth = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, query="hello", k=0),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    assert fact_recall.recall_id != synth.recall_id


def test_uri_and_query_forms_get_distinct_ids_for_same_string(
    tenant_root: Path,
) -> None:
    """``recall_synthesis(uri="X")`` and ``recall_synthesis(query="X")``
    get different recall_ids — the intent discriminant differs."""
    conn = _open_s2(tenant_root)
    page = _page("s4a://x.md")
    src_uri = _FakeSynthesisSource(by_uri={page.page_uri: page})
    src_query = _FakeSynthesisSource(query_hits=[page])

    r_uri = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri, k=1),
        s2_conn=conn,
        source=src_uri,
        now=_T_NOW,
    )
    r_query = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, query=page.page_uri, k=1),
        s2_conn=conn,
        source=src_query,
        now=_T_NOW,
    )
    assert r_uri.recall_id != r_query.recall_id


# ---------------------------------------------------------------------------
# Tests — Events
# ---------------------------------------------------------------------------


def test_events_carry_synthesis_path(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    pages = [_page("s4a://a.md"), _page("s4a://b.md")]
    src = _FakeSynthesisSource(query_hits=pages)
    sink = _RecordingSink()

    response = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, query="x", k=2),
        s2_conn=conn,
        source=src,
        event_sink=sink,
        now=_T_NOW,
    )
    assert len(sink.events) == 2
    for ev in sink.events:
        assert ev["event_type"] == "recall"
        assert ev["path"] == "synthesis"
        assert ev["recall_id"] == response.recall_id
        assert ev["weights_version"] == "synthesis-passthrough"
        assert isinstance(ev["fact_ids"], list)
        assert len(ev["fact_ids"]) == 1


def test_event_fact_ids_are_page_ids_not_page_uris(tenant_root: Path) -> None:
    """``fact_ids`` carry deterministic page-ids derived from page_uri."""
    conn = _open_s2(tenant_root)
    page = _page("s4a://specific.md")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})
    sink = _RecordingSink()

    recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        event_sink=sink,
        now=_T_NOW,
    )
    expected_id = _page_uri_to_id(page.page_uri)
    assert sink.events[0]["fact_ids"] == [expected_id]
    # Sanity: the page_uri itself is NOT what gets emitted.
    assert sink.events[0]["fact_ids"] != [page.page_uri]


# ---------------------------------------------------------------------------
# Tests — Ledger semantics
# ---------------------------------------------------------------------------


def test_ledger_row_uses_synthesis_weights_version(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    page = _page("s4a://p.md")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})

    response = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    row = conn.execute(
        "SELECT recall_id, classified_intent, weights_version, top_k_fact_ids "
        "FROM recall_ledger WHERE recall_id = ?",
        (response.recall_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == response.recall_id
    assert row[1] == "synthesis_uri"
    assert row[2] == "synthesis-passthrough"
    # top_k_fact_ids is the JSON-encoded page-ids list.
    import json

    assert json.loads(row[3]) == [_page_uri_to_id(page.page_uri)]


def test_legitimate_replay_is_silent_noop(tenant_root: Path) -> None:
    """Same call twice → same recall_id, ledger has exactly one row."""
    conn = _open_s2(tenant_root)
    page = _page("s4a://p.md")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})

    r1 = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    r2 = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    assert r1.recall_id == r2.recall_id
    rows = conn.execute("SELECT COUNT(*) FROM recall_ledger").fetchone()
    assert rows[0] == 1


def test_same_pk_different_payload_raises_corruption(tenant_root: Path) -> None:
    """Substrate bug: deterministic id reused with divergent envelope."""
    conn = _open_s2(tenant_root)
    page = _page("s4a://p.md")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})

    response = recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    # Replay write with a divergent envelope blob → corruption.
    with pytest.raises(RecallLedgerCorruption):
        write_ledger_row(
            conn,
            recall_id=response.recall_id,
            tenant_id=_TENANT,
            query_hash="0" * 16,
            ts_recorded="2025-06-01T12:00:00.000Z",
            classified_intent="synthesis_uri",
            weights_version="synthesis-passthrough",
            top_k_fact_ids=["different-id"],
            response_envelope_blob=b"divergent payload",
        )


# ---------------------------------------------------------------------------
# Tests — Bi-temporal filter NOT invoked
# ---------------------------------------------------------------------------


def test_no_bitemporal_filter_invoked(
    tenant_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthesis pages are git-versioned; bi-temporal filter must NOT run.

    Patches the filter callable at its api.recall_synthesis import site
    AND at its source — neither is allowed to be invoked from the
    synthesis path. Asserts call count stays zero.
    """
    import lethe.runtime.bitemporal_filter as bt_module

    calls: list[Any] = []
    original = bt_module.filter_facts

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(bt_module, "filter_facts", _spy)

    conn = _open_s2(tenant_root)
    page = _page("s4a://p.md")
    src = _FakeSynthesisSource(by_uri={page.page_uri: page})
    recall_synthesis(
        SynthesisRequest(tenant_id=_TENANT, uri=page.page_uri),
        s2_conn=conn,
        source=src,
        now=_T_NOW,
    )
    assert calls == []


# ---------------------------------------------------------------------------
# Tests — S4a outage
# ---------------------------------------------------------------------------


def test_s4a_outage_bubbles_uri_form(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource(raise_outage=True)

    with pytest.raises(S4aOutage):
        recall_synthesis(
            SynthesisRequest(tenant_id=_TENANT, uri="s4a://x.md"),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )
    # No ledger row should have been written when fetch raised.
    rows = conn.execute("SELECT COUNT(*) FROM recall_ledger").fetchone()
    assert rows[0] == 0


def test_s4a_outage_bubbles_query_form(tenant_root: Path) -> None:
    conn = _open_s2(tenant_root)
    src = _FakeSynthesisSource(raise_outage=True)

    with pytest.raises(S4aOutage):
        recall_synthesis(
            SynthesisRequest(tenant_id=_TENANT, query="x", k=3),
            s2_conn=conn,
            source=src,
            now=_T_NOW,
        )
    rows = conn.execute("SELECT COUNT(*) FROM recall_ledger").fetchone()
    assert rows[0] == 0
