"""``remember`` verb implementation (api §3.1).

Composes the runtime primitives from commits 1-3:

- :mod:`lethe.runtime.idempotency` — uuidv7 + 24 h TTL + per-verb scope.
- :mod:`lethe.runtime.provenance` — envelope; ``source_uri`` mandatory.
- :mod:`lethe.runtime.classifier` — gap-12 §3 + §6 heuristic + LLM-residual.
- :mod:`lethe.runtime.events` — ``remember`` event emit point.

Plus the S1 + S2 stores:

- :class:`lethe.store.s1_graph.GraphBackend` — episode persistence.
- :class:`lethe.store.s2_meta.S2Schema` — sqlite per-tenant file
  (``idempotency_keys``, ``audit_log``, ``review_queue``).

The 8-step algorithm (api §3.1):

1. **Validate idempotency** — uuidv7 + replay → 200, conflict → 409.
2. **Validate provenance** — ``source_uri`` non-empty.
3. **Classifier dispatch** — heuristic + LLM-residual; ``force_skip_classifier``
   bypasses (audit row written; ``tenant_admin`` auth check stubbed for P7).
4. **Branch on class** — ``drop``/``reply_only`` → 200 dropped;
   ``peer_route`` → 400 hint; ``escalate`` → 422 staged; ``remember:*`` → continue.
5. **T1 transaction** — S1 ``add_episode`` + S2 ``idempotency_keys.record``.
6. **Commit T1** — sqlite commit.
7. **Emit `remember` event** (scoring §8.1).
8. **Return RememberResponse** with ``ack="synchronous_durable"``.

Error mapping (api §1.6):

- :class:`RememberValidationError` → 400 (missing/malformed idempotency key,
  missing provenance, ``force_skip_classifier`` without ``caller_tag``).
- :class:`RememberPeerRouteError` → 400 ``invalid_request`` with hint
  ``use_peer_message``.
- :class:`RememberAuthError` → 403 ``forbidden`` (``force_skip_classifier``
  by a non-tenant_admin principal; stub raises at P7 transport surface).
- :class:`RememberConflictError` → 409 ``idempotency_conflict``.

Escalate and drop/reply_only return :class:`RememberResponse` with the
appropriate ``http_status`` (422 / 200) — they have meaningful envelopes
(``staged_id`` / ``accepted=False``) that callers want.

Replay (idempotency hit, same body hash) returns the stored response
verbatim per api §3.1 step 1.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from lethe.runtime.classifier import (
    ClassificationRequest,
    ClassificationResult,
    IntentClass,
    LLMClassifier,
    SourceKind,
    classify,
)
from lethe.runtime.events import emit as emit_event
from lethe.runtime.idempotency import (
    IdempotencyConflict,
    IdempotencyKeyMalformed,
    IdempotencyKeyMissing,
    check_replay_or_conflict,
    validate_uuidv7,
)
from lethe.runtime.idempotency import (
    record as record_idempotency,
)
from lethe.runtime.provenance import ProvenanceRequired
from lethe.runtime.provenance import make as make_provenance
from lethe.store.s1_graph import GraphBackend

# Public so tests / callers don't accidentally drift from the schema columns.
_VERB_NAME: Final[str] = "remember"

# Review-queue retention (deployment §6.2 owns the canonical TTL — 7 days
# is the documented default; P7 may parameterise per-tenant).
_REVIEW_QUEUE_TTL_DAYS: Final[int] = 7

# Scoring envelope versions (api §1.7 + scoring §8.2). Until WS5 stamps
# the real release identifiers, the constants here are the agreed P2
# placeholders — they appear verbatim in `audit_log` rows and the
# `remember` event envelope so the contamination boundary is auditable.
_MODEL_VERSION_P2: Final[str] = "p2-classifier-v0"
_WEIGHTS_VERSION_P2: Final[str] = "p2-weights-v0"


class RememberError(Exception):
    """Base class for ``remember`` verb failures.

    Carries an api §1.6 ``code`` and HTTP ``status`` so the transport
    surface (P7) can map cleanly without re-classifying exceptions.
    """

    code: str = "internal_error"
    status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RememberValidationError(RememberError):
    """400 validation failure (idempotency / provenance / shape)."""

    status = 400

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class RememberPeerRouteError(RememberError):
    """400 — classifier returned ``peer_route``; caller should use ``peer_message``."""

    code = "invalid_request"
    status = 400
    hint = "use_peer_message"


class RememberAuthError(RememberError):
    """403 — ``force_skip_classifier=True`` by a non-``tenant_admin`` principal."""

    code = "forbidden"
    status = 403


class RememberConflictError(RememberError):
    """409 — same idempotency_key reused with a different body."""

    code = "idempotency_conflict"
    status = 409

    def __init__(
        self,
        message: str,
        *,
        original_hash: str,
        retried_hash: str,
    ) -> None:
        super().__init__(message)
        self.original_hash = original_hash
        self.retried_hash = retried_hash


@dataclass(frozen=True)
class RememberRequest:
    """Caller-facing input envelope for :func:`remember` (api §3.1)."""

    tenant_id: str
    principal: str
    content: str
    idempotency_key: str
    provenance: dict[str, Any]
    intent: IntentClass | None = None
    kind: str | None = None
    force_skip_classifier: bool = False
    source_kind: SourceKind = "utterance"
    source_subtype: str | None = None
    # Carrier for advanced callers; reserved for P5+ extraction phase.
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RememberResponse:
    """Response envelope (api §3.1 ``RememberResponse``)."""

    episode_id: str
    idempotency_key: str
    classified_intent: dict[str, Any]
    retention_class: str
    accepted: bool
    escalated: bool
    ack: str
    applied_at: str
    http_status: int = 200
    next_consolidate_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "episode_id": self.episode_id,
            "idempotency_key": self.idempotency_key,
            "classified_intent": self.classified_intent,
            "retention_class": self.retention_class,
            "accepted": self.accepted,
            "escalated": self.escalated,
            "ack": self.ack,
            "applied_at": self.applied_at,
            "http_status": self.http_status,
        }
        if self.next_consolidate_at is not None:
            out["next_consolidate_at"] = self.next_consolidate_at
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RememberResponse:
        return cls(
            episode_id=str(payload["episode_id"]),
            idempotency_key=str(payload["idempotency_key"]),
            classified_intent=dict(payload["classified_intent"]),
            retention_class=str(payload["retention_class"]),
            accepted=bool(payload["accepted"]),
            escalated=bool(payload["escalated"]),
            ack=str(payload["ack"]),
            applied_at=str(payload["applied_at"]),
            http_status=int(payload.get("http_status", 200)),
            next_consolidate_at=(
                str(payload["next_consolidate_at"])
                if payload.get("next_consolidate_at") is not None
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _generate_uuidv7(*, now: datetime | None = None) -> str:
    """Generate an RFC 9562 v7 uuid string.

    48-bit unix_ts_ms || 4-bit version (0111) || 12-bit rand_a || 2-bit
    variant (10) || 62-bit rand_b. Validated round-trip-clean by
    :func:`lethe.runtime.idempotency.validate_uuidv7`.
    """
    n = now or _now()
    unix_ts_ms = int(n.timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    # Top 48 bits: timestamp. Next 4: version. Next 12: rand_a. Next 2:
    # variant. Next 62: rand_b.
    msb = (unix_ts_ms << 16) | (0x7 << 12) | rand_a
    lsb = (0b10 << 62) | rand_b
    value = (msb << 64) | lsb
    return str(uuid.UUID(int=value))


def _hash_body(req: RememberRequest) -> str:
    """SHA-256 over the canonicalized request body (api §1.2)."""
    canonical = {
        "tenant_id": req.tenant_id,
        "content": req.content,
        "provenance": dict(sorted(req.provenance.items())),
        "intent": req.intent,
        "kind": req.kind,
        "source_kind": req.source_kind,
        "source_subtype": req.source_subtype,
        "force_skip_classifier": req.force_skip_classifier,
    }
    blob = json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _retention_class_for(intent: IntentClass, kind: str | None) -> str:
    """Map (class, kind) → gap-09 §3 retention shape (api §3.1 line 488).

    ``kind`` overrides the class-derived shape when supplied.
    """
    if kind:
        return kind
    mapping = {
        "remember:fact": "episodic_fact",
        "remember:preference": "preference",
        "remember:procedure": "procedure",
    }
    return mapping.get(intent, "narrative")


def _assert_force_skip_authorized(*, tenant_id: str, principal: str) -> None:
    """Stub auth check for ``force_skip_classifier=True`` (deployment §6.3).

    P2: no-op. The audit row written separately provides the forensic
    record. At P7 this is replaced by the real RBAC check that asserts
    ``principal`` has the ``tenant_admin`` role for ``tenant_id``; until
    then callers are trusted by contract.
    """
    _ = (tenant_id, principal)  # P7-bound; intentionally unused at P2.
    # TODO(P7): replace with real tenant_admin RBAC check (deployment §6.3).
    return None


def _write_force_skip_audit_row(
    conn: Any,
    *,
    tenant_id: str,
    principal: str,
    caller_tag: IntentClass,
    idempotency_key: str,
) -> None:
    """Insert the ``force_skip_classifier_invoked`` row (sub-plan §6)."""
    payload = json.dumps(
        {
            "caller_tag": caller_tag,
            "request_idempotency_key": idempotency_key,
        },
        sort_keys=True,
    )
    conn.execute(
        "INSERT INTO audit_log (tenant_id, verb, principal, action, payload_json)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            tenant_id,
            _VERB_NAME,
            principal,
            "force_skip_classifier_invoked",
            payload,
        ),
    )


def _stage_escalate_row(
    conn: Any,
    *,
    staged_id: str,
    tenant_id: str,
    principal: str,
    request_body: str,
    classifier_class: str,
    classifier_score: float,
) -> None:
    """Stage an escalate payload in ``review_queue`` (api §3.1 step 4)."""
    now = _now()
    expires_at = _format_iso(now + timedelta(days=_REVIEW_QUEUE_TTL_DAYS))
    staged_at = _format_iso(now)
    conn.execute(
        "INSERT INTO review_queue ("
        " staged_id, tenant_id, source_verb, source_principal, staged_at,"
        " payload_blob, classifier_class, classifier_score, status, expires_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            staged_id,
            tenant_id,
            _VERB_NAME,
            principal,
            staged_at,
            request_body.encode("utf-8"),
            classifier_class,
            float(classifier_score),
            "pending_review",
            expires_at,
        ),
    )


def _build_event(
    *,
    tenant_id: str,
    episode_id: str,
    classification: ClassificationResult,
    retention_class: str,
    provenance: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Build the scoring §8.1 ``remember`` envelope."""
    ts = _format_iso(now)
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "remember",
        "tenant_id": tenant_id,
        "ts_recorded": ts,
        "ts_valid": ts,
        "model_version": _MODEL_VERSION_P2,
        "weights_version": _WEIGHTS_VERSION_P2,
        "contamination_protected": True,
        "fact_ids": [episode_id],
        "decision": {
            "class": classification.intent,
            "confidence": classification.confidence,
            "path": classification.path,
            "retention_class": retention_class,
        },
        "provenance": dict(provenance),
    }


# ---------------------------------------------------------------------------
# Verb
# ---------------------------------------------------------------------------


def remember(
    request: RememberRequest,
    *,
    graph: GraphBackend,
    s2_conn: Any,
    llm_classifier: LLMClassifier | None = None,
    event_sink: Any = None,
    now: datetime | None = None,
) -> RememberResponse:
    """Synchronous portion of ``remember`` (api §3.1; composition §4.1).

    Arguments:
        request: caller-supplied envelope.
        graph: S1 backend (production: :class:`GraphitiBackend`; tests
            inject :class:`_InMemoryGraphBackend`).
        s2_conn: open per-tenant sqlite connection (S2 file). The caller
            owns connection lifecycle; this function performs its T1
            commit inside an explicit transaction.
        llm_classifier: optional injectable LLM (plan §4). When ``None``
            the classifier falls back to the heuristic-only path.
        event_sink: optional override for the ``remember`` event sink
            (tests use a recording sink). When ``None`` the default
            ``scripts.eval.metrics.emitter.emit_score_event`` is used.
        now: optional clock override (tests can pin time).

    Returns:
        :class:`RememberResponse` for 200 (accepted / dropped) and 422
        (escalate). Non-2xx with no episode raises a :class:`RememberError`
        subclass.

    Raises:
        RememberValidationError: 400 — missing key, missing provenance,
            ``force_skip_classifier=True`` without ``caller_tag``.
        RememberPeerRouteError: 400 — classifier said ``peer_route``.
        RememberAuthError: 403 — ``force_skip_classifier=True`` from a
            non-``tenant_admin`` (P7-enforced; stub at P2).
        RememberConflictError: 409 — same key + different body.
    """
    n = now or _now()

    # Step 1: validate idempotency key.
    try:
        validate_uuidv7(request.idempotency_key)
    except IdempotencyKeyMissing as exc:
        raise RememberValidationError(
            str(exc), code="missing_idempotency_key"
        ) from exc
    except IdempotencyKeyMalformed as exc:
        raise RememberValidationError(
            str(exc), code="missing_idempotency_key"
        ) from exc

    body_hash = _hash_body(request)

    # Replay vs conflict pre-check.
    try:
        hit = check_replay_or_conflict(
            s2_conn,
            key=request.idempotency_key,
            verb=_VERB_NAME,
            body_hash=body_hash,
            now=n,
        )
    except IdempotencyConflict as exc:
        raise RememberConflictError(
            str(exc),
            original_hash=exc.original_hash,
            retried_hash=exc.retried_hash,
        ) from exc

    if hit is not None:
        # Replay — return stored response verbatim (api §3.1 step 1). No
        # event re-emit (gate 6: "no event on replay or 422").
        return RememberResponse.from_dict(hit.response)

    # Step 2: validate provenance.
    try:
        provenance_obj = make_provenance(
            episode_id="placeholder",  # bound below once episode_id is generated
            source_uri=str(request.provenance.get("source_uri", "")),
            agent_id=str(
                request.provenance.get("agent_id") or request.principal
            ),
            recorded_at=_format_iso(n),
            derived_from=(
                str(request.provenance["derived_from"])
                if request.provenance.get("derived_from") is not None
                else None
            ),
        )
    except ProvenanceRequired as exc:
        raise RememberValidationError(
            str(exc), code="provenance_required"
        ) from exc

    # Step 3: classify (or honor force_skip).
    if request.force_skip_classifier:
        if request.intent is None:
            raise RememberValidationError(
                "force_skip_classifier=true requires a caller-supplied intent "
                "(api §3.1 + deployment §6.3)",
                code="missing_caller_tag",
            )
        _assert_force_skip_authorized(
            tenant_id=request.tenant_id, principal=request.principal
        )

    classification = classify(
        ClassificationRequest(
            tenant_id=request.tenant_id,
            payload=request.content,
            caller_tag=request.intent,
            source_kind=request.source_kind,
            source_subtype=request.source_subtype,
            force_skip_classifier=request.force_skip_classifier,
        ),
        llm=llm_classifier,
    )

    # Step 4: branch on class.
    if classification.intent == "peer_route":
        raise RememberPeerRouteError(
            "classifier returned peer_route; use peer_message verb instead"
        )

    episode_id = _generate_uuidv7(now=n)
    applied_at = _format_iso(n)

    if classification.intent in ("drop", "reply_only"):
        response = RememberResponse(
            episode_id=episode_id,
            idempotency_key=request.idempotency_key,
            classified_intent={
                "class": classification.intent,
                "confidence": classification.confidence,
                "path": classification.path,
            },
            retention_class=_retention_class_for(
                classification.intent, request.kind
            ),
            accepted=False,
            escalated=False,
            ack="dropped",
            applied_at=applied_at,
            http_status=200,
        )
        # Record idempotency-key for stable retries (api §3.1 step 4 bullet).
        # No S1 write; no event emission.
        record_idempotency(
            s2_conn,
            key=request.idempotency_key,
            verb=_VERB_NAME,
            body_hash=body_hash,
            response=response.to_dict(),
            now=n,
        )
        s2_conn.commit()
        return response

    if classification.intent == "escalate":
        staged_id = episode_id  # reuse the generated uuidv7 as staged_id.
        _stage_escalate_row(
            s2_conn,
            staged_id=staged_id,
            tenant_id=request.tenant_id,
            principal=request.principal,
            request_body=json.dumps(
                {
                    "content": request.content,
                    "provenance": request.provenance,
                    "intent": request.intent,
                    "kind": request.kind,
                },
                sort_keys=True,
                default=str,
            ),
            classifier_class=classification.intent,
            classifier_score=classification.confidence,
        )
        response = RememberResponse(
            episode_id=staged_id,
            idempotency_key=request.idempotency_key,
            classified_intent={
                "class": classification.intent,
                "confidence": classification.confidence,
                "path": classification.path,
            },
            retention_class=_retention_class_for(
                "remember:fact", request.kind
            ),
            accepted=False,
            escalated=True,
            ack="staged_for_review",
            applied_at=applied_at,
            http_status=422,
        )
        record_idempotency(
            s2_conn,
            key=request.idempotency_key,
            verb=_VERB_NAME,
            body_hash=body_hash,
            response=response.to_dict(),
            now=n,
        )
        s2_conn.commit()
        return response

    # Step 5+6: T1 — happy path (remember:fact / preference / procedure).
    if request.force_skip_classifier and request.intent is not None:
        # Audit row only on bypass; written inside the same T1.
        _write_force_skip_audit_row(
            s2_conn,
            tenant_id=request.tenant_id,
            principal=request.principal,
            caller_tag=request.intent,
            idempotency_key=request.idempotency_key,
        )

    # Rebuild provenance with the real episode_id.
    provenance_obj = make_provenance(
        episode_id=episode_id,
        source_uri=provenance_obj.source_uri,
        agent_id=provenance_obj.agent_id,
        recorded_at=provenance_obj.recorded_at,
        derived_from=provenance_obj.derived_from,
    )

    # S1 write (graphiti or in-memory).
    graph.add_episode(
        group_id=request.tenant_id,
        episode_id=episode_id,
        body=request.content,
        source_uri=provenance_obj.source_uri,
        ts_recorded=provenance_obj.recorded_at,
        intent=classification.intent,
    )

    retention_class = _retention_class_for(classification.intent, request.kind)
    response = RememberResponse(
        episode_id=episode_id,
        idempotency_key=request.idempotency_key,
        classified_intent={
            "class": classification.intent,
            "confidence": classification.confidence,
            "path": classification.path,
        },
        retention_class=retention_class,
        accepted=True,
        escalated=False,
        ack="synchronous_durable",
        applied_at=applied_at,
        http_status=200,
    )

    # Record idempotency key in the same transaction as the audit row +
    # any other S2 writes; then commit.
    record_idempotency(
        s2_conn,
        key=request.idempotency_key,
        verb=_VERB_NAME,
        body_hash=body_hash,
        response=response.to_dict(),
        now=n,
    )
    s2_conn.commit()

    # Step 7: emit `remember` event (scoring §8.1).
    event = _build_event(
        tenant_id=request.tenant_id,
        episode_id=episode_id,
        classification=classification,
        retention_class=retention_class,
        provenance=provenance_obj.to_dict(),
        now=n,
    )
    emit_event(event, sink=event_sink)

    # Step 8: return.
    return response