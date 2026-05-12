"""Tests for :mod:`lethe.api.remember` (api §3.1; dev sub-plan §7 gates).

Coverage map (sub-plan §7):

- Gate 1 (idempotency): missing key 400; replay returns stored response;
  conflict 409.
- Gate 2 (provenance): missing source_uri 400; round-trip on accepted writes.
- Gate 3 (classifier escape): escalate → 422 + ``staged_for_review`` +
  ``review_queue`` row.
- Gate 4 (replay invariant): same key + same body → identical response;
  no double S1 write.
- Gate 5 (force_skip): bypasses dispatch; audit row written; stubbed auth
  check exists.
- Gate 6 (events): event fires once per accepted write; no event on replay
  or 422; envelope carries scoring §8.2 fields.

All disk-touching writes go through the ``tenant_root`` fixture under
``LETHE_HOME``. No network; no live Graphiti — the production seam is
exercised via :class:`_InMemoryGraphBackend`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lethe.api import (
    RememberAuthError,
    RememberConflictError,
    RememberError,
    RememberPeerRouteError,
    RememberRequest,
    RememberResponse,
    RememberValidationError,
    remember,
)
from lethe.runtime.classifier import IntentClass, LLMClassification
from lethe.store.s1_graph import _InMemoryGraphBackend
from lethe.store.s2_meta import S2Schema

_VALID_KEY_A = "01890af0-0000-7000-8000-000000000001"
_VALID_KEY_B = "01890af0-0000-7000-8000-000000000002"
_VALID_KEY_C = "01890af0-0000-7000-8000-000000000003"
_TENANT = "smoke-tenant"
_PRINCIPAL = "agent:test"


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def s2_conn(tenant_root: Path) -> Iterator[sqlite3.Connection]:
    conn = S2Schema(tenant_root=tenant_root).create()
    yield conn
    conn.close()


@pytest.fixture
def graph() -> _InMemoryGraphBackend:
    backend = _InMemoryGraphBackend()
    backend.bootstrap_tenant(_TENANT)
    return backend


class _RecordingSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: Any) -> None:
        # Defensive copy so callers can mutate without affecting our log.
        self.events.append(dict(event))


class _ScriptedLLM:
    def __init__(self, verdict: LLMClassification) -> None:
        self.verdict = verdict
        self.calls = 0

    def __call__(
        self,
        *,
        tenant_id: str,
        payload: str,
        caller_tag: IntentClass | None,
    ) -> LLMClassification:
        self.calls += 1
        return self.verdict


def _req(
    *,
    content: str = "I prefer dark mode in my editor",
    idempotency_key: str = _VALID_KEY_A,
    intent: IntentClass | None = None,
    provenance: dict[str, Any] | None = None,
    force_skip_classifier: bool = False,
    source_kind: str = "utterance",
    source_subtype: str | None = None,
    kind: str | None = None,
) -> RememberRequest:
    return RememberRequest(
        tenant_id=_TENANT,
        principal=_PRINCIPAL,
        content=content,
        idempotency_key=idempotency_key,
        provenance=(
            provenance
            if provenance is not None
            else {"source_uri": "test://fixture"}
        ),
        intent=intent,
        kind=kind,
        force_skip_classifier=force_skip_classifier,
        source_kind=source_kind,  # type: ignore[arg-type]
        source_subtype=source_subtype,
    )


# Always-fact LLM so ambiguous utterances accept.
def _llm_fact() -> _ScriptedLLM:
    return _ScriptedLLM(
        {"intent": "remember:fact", "score": 0.9, "rationale": "accepted"}
    )


# ---------------------------------------------------------------------------
# Step 1 — idempotency (gate 1 + gate 4)
# ---------------------------------------------------------------------------


def test_missing_idempotency_key_returns_400(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    with pytest.raises(RememberValidationError) as exc_info:
        remember(
            _req(idempotency_key=""),
            graph=graph,
            s2_conn=s2_conn,
            llm_classifier=_llm_fact(),
        )
    assert exc_info.value.status == 400
    assert exc_info.value.code == "missing_idempotency_key"


def test_malformed_idempotency_key_returns_400(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    with pytest.raises(RememberValidationError) as exc_info:
        remember(
            _req(idempotency_key="not-a-uuid"),
            graph=graph,
            s2_conn=s2_conn,
        )
    assert exc_info.value.status == 400
    assert exc_info.value.code == "missing_idempotency_key"


def test_replay_within_ttl_returns_original_response(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    first = remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    second = remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    # Same envelope (replay returns stored verbatim).
    assert second.to_dict() == first.to_dict()
    # Gate 4: no double S1 write.
    assert len(graph._episodes_for(_TENANT)) == 1
    # Gate 6: no event on replay.
    assert len(sink.events) == 1


def test_same_key_different_body_returns_409_conflict(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    remember(
        _req(content="first body"),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
    )
    with pytest.raises(RememberConflictError) as exc_info:
        remember(
            _req(content="different body"),
            graph=graph,
            s2_conn=s2_conn,
            llm_classifier=_llm_fact(),
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "idempotency_conflict"
    assert exc_info.value.original_hash != exc_info.value.retried_hash


# ---------------------------------------------------------------------------
# Step 2 — provenance (gate 2)
# ---------------------------------------------------------------------------


def test_missing_source_uri_returns_400(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    with pytest.raises(RememberValidationError) as exc_info:
        remember(
            _req(provenance={"agent_id": "agent:x"}),
            graph=graph,
            s2_conn=s2_conn,
            llm_classifier=_llm_fact(),
        )
    assert exc_info.value.status == 400
    assert exc_info.value.code == "provenance_required"


def test_provenance_persisted_on_accepted_write(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    response = remember(
        _req(provenance={"source_uri": "doc://abc", "agent_id": "agent:x"}),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    assert response.accepted is True
    episodes = graph._episodes_for(_TENANT)
    assert len(episodes) == 1
    assert episodes[0]["source_uri"] == "doc://abc"
    # Event envelope provenance carries the same source_uri (gate 2 round-trip).
    assert sink.events[0]["provenance"]["source_uri"] == "doc://abc"


# ---------------------------------------------------------------------------
# Step 3 + step 4 — classifier dispatch + branching
# ---------------------------------------------------------------------------


def test_drop_returns_200_dropped_with_no_s1_write(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    # "ok thanks" is a short utterance → heuristic returns drop ≥0.8.
    response = remember(
        _req(content="ok thanks"),
        graph=graph,
        s2_conn=s2_conn,
        event_sink=sink,
    )
    assert response.http_status == 200
    assert response.accepted is False
    assert response.ack == "dropped"
    assert response.classified_intent["class"] == "drop"
    assert graph._episodes_for(_TENANT) == ()
    # Gate 6: no event on dropped writes.
    assert sink.events == []


def test_peer_route_class_raises_400_with_hint(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    peer_llm = _ScriptedLLM(
        {"intent": "peer_route", "score": 0.95, "rationale": "send to peer"}
    )
    with pytest.raises(RememberPeerRouteError) as exc_info:
        remember(
            _req(content="please tell Bob about the release notes"),
            graph=graph,
            s2_conn=s2_conn,
            llm_classifier=peer_llm,
        )
    assert exc_info.value.status == 400
    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.hint == "use_peer_message"
    assert graph._episodes_for(_TENANT) == ()


# ---------------------------------------------------------------------------
# Gate 3 — classifier escape (escalate → 422 + review_queue row)
# ---------------------------------------------------------------------------


def test_escalate_class_returns_422_and_stages_in_review_queue(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    response = remember(
        _req(content="my password is hunter2"),  # sensitive-regex hit
        graph=graph,
        s2_conn=s2_conn,
        event_sink=sink,
    )
    assert response.http_status == 422
    assert response.escalated is True
    assert response.ack == "staged_for_review"
    assert response.accepted is False
    assert response.classified_intent["class"] == "escalate"

    # review_queue row exists with the correct shape.
    row = s2_conn.execute(
        "SELECT staged_id, tenant_id, source_verb, source_principal,"
        " classifier_class, classifier_score, status FROM review_queue"
    ).fetchone()
    assert row is not None
    assert row[0] == response.episode_id
    assert row[1] == _TENANT
    assert row[2] == "remember"
    assert row[3] == _PRINCIPAL
    assert row[4] == "escalate"
    assert row[5] == 1.0
    assert row[6] == "pending_review"

    # Gate 6: no event on 422 path.
    assert sink.events == []
    # No S1 write on escalate.
    assert graph._episodes_for(_TENANT) == ()


# ---------------------------------------------------------------------------
# Gate 5 — force_skip
# ---------------------------------------------------------------------------


def test_force_skip_classifier_writes_audit_log_row(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    # Even though "ok thanks" would normally drop, force_skip honors the
    # caller tag.
    response = remember(
        _req(
            content="ok thanks",
            intent="remember:fact",
            force_skip_classifier=True,
        ),
        graph=graph,
        s2_conn=s2_conn,
        event_sink=sink,
    )
    assert response.accepted is True
    assert response.classified_intent["class"] == "remember:fact"
    assert response.classified_intent["path"] == "caller_tagged"

    row = s2_conn.execute(
        "SELECT tenant_id, verb, principal, action, payload_json"
        " FROM audit_log"
    ).fetchone()
    assert row is not None
    assert row[0] == _TENANT
    assert row[1] == "remember"
    assert row[2] == _PRINCIPAL
    assert row[3] == "force_skip_classifier_invoked"
    payload = json.loads(row[4])
    assert payload["caller_tag"] == "remember:fact"
    assert payload["request_idempotency_key"] == _VALID_KEY_A


def test_force_skip_classifier_auth_check_stub() -> None:
    # The stub is P7-bound; at P2 it must exist as a no-op so callers can
    # exercise the bypass without a real RBAC engine.
    from lethe.api.remember import _assert_force_skip_authorized

    assert (
        _assert_force_skip_authorized(tenant_id=_TENANT, principal=_PRINCIPAL)
        is None
    )


def test_force_skip_without_caller_tag_returns_400(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    with pytest.raises(RememberValidationError) as exc_info:
        remember(
            _req(
                content="anything",
                intent=None,
                force_skip_classifier=True,
            ),
            graph=graph,
            s2_conn=s2_conn,
        )
    assert exc_info.value.status == 400
    assert exc_info.value.code == "missing_caller_tag"


# ---------------------------------------------------------------------------
# Gate 6 — event emission
# ---------------------------------------------------------------------------


def test_remember_event_fires_once_per_accepted_write(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    response = remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    assert response.accepted is True
    assert len(sink.events) == 1

    event = sink.events[0]
    # scoring §8.2 envelope shape.
    for required in (
        "event_id",
        "event_type",
        "tenant_id",
        "ts_recorded",
        "ts_valid",
        "model_version",
        "weights_version",
        "contamination_protected",
    ):
        assert required in event, f"missing scoring §8.2 field: {required}"
    assert event["event_type"] == "remember"
    assert event["tenant_id"] == _TENANT
    assert event["contamination_protected"] is True
    # Per-type extras (remember).
    assert event["fact_ids"] == [response.episode_id]
    assert event["decision"]["class"] == "remember:fact"
    assert event["provenance"]["source_uri"] == "test://fixture"


def test_no_event_fires_on_replay(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    remember(
        _req(),  # same key + same body → replay
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
        event_sink=sink,
    )
    assert len(sink.events) == 1


def test_no_event_fires_on_422_escalate(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    sink = _RecordingSink()
    remember(
        _req(content="my password is hunter2"),
        graph=graph,
        s2_conn=s2_conn,
        event_sink=sink,
    )
    assert sink.events == []


# ---------------------------------------------------------------------------
# Retention class mapping (api §3.1 line 488)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intent", "expected_retention"),
    [
        ("remember:fact", "episodic_fact"),
        ("remember:preference", "preference"),
        ("remember:procedure", "procedure"),
    ],
)
def test_retention_class_derives_from_intent(
    s2_conn: sqlite3.Connection,
    graph: _InMemoryGraphBackend,
    intent: IntentClass,
    expected_retention: str,
) -> None:
    llm = _ScriptedLLM({"intent": intent, "score": 0.9, "rationale": "ok"})
    response = remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=llm,
    )
    assert response.retention_class == expected_retention


def test_explicit_kind_overrides_intent_derived_retention(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    response = remember(
        _req(kind="narrative"),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
    )
    assert response.retention_class == "narrative"


# ---------------------------------------------------------------------------
# Response envelope shape
# ---------------------------------------------------------------------------


def test_response_envelope_contains_api_3_1_fields(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    response = remember(
        _req(),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
    )
    assert isinstance(response, RememberResponse)
    assert response.episode_id  # uuidv7 string
    assert response.idempotency_key == _VALID_KEY_A
    assert set(response.classified_intent.keys()) == {
        "class",
        "confidence",
        "path",
    }
    assert response.classified_intent["path"] in {
        "heuristic",
        "llm",
        "caller_tagged",
    }
    assert response.ack == "synchronous_durable"
    assert response.applied_at.endswith("Z")
    assert response.http_status == 200


def test_different_tenants_isolated_via_idempotency_per_verb_scope(
    s2_conn: sqlite3.Connection, graph: _InMemoryGraphBackend
) -> None:
    # Two requests with different keys must both succeed; same key+verb
    # collision was already covered by the conflict / replay tests above.
    remember(
        _req(idempotency_key=_VALID_KEY_A, content="alpha is the codename"),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
    )
    remember(
        _req(idempotency_key=_VALID_KEY_B, content="beta is the codename"),
        graph=graph,
        s2_conn=s2_conn,
        llm_classifier=_llm_fact(),
    )
    assert len(graph._episodes_for(_TENANT)) == 2


# ---------------------------------------------------------------------------
# Error-class surface
# ---------------------------------------------------------------------------


def test_error_classes_carry_api_status_codes() -> None:
    # Smoke test on the error hierarchy: all RememberError subclasses
    # have well-defined HTTP status codes the P7 transport surface can
    # map.
    assert RememberValidationError("x", code="missing_idempotency_key").status == 400
    assert RememberPeerRouteError("x").status == 400
    assert RememberAuthError("x").status == 403
    assert (
        RememberConflictError(
            "x", original_hash="a", retried_hash="b"
        ).status
        == 409
    )
    assert issubclass(RememberValidationError, RememberError)
    assert issubclass(RememberPeerRouteError, RememberError)
    assert issubclass(RememberAuthError, RememberError)
    assert issubclass(RememberConflictError, RememberError)
