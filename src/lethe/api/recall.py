"""``recall`` verb implementation (api §2.1).

Composes the P3 runtime substrate landed in commits 1-2:

- :mod:`lethe.runtime.bitemporal_filter` — invariant I-4 (filter pre-RRF).
- :mod:`lethe.runtime.recall_id` — deterministic uuidv7 per api §1.4.
- :mod:`lethe.runtime.retrievers` — semantic / lexical / graph + RRF.
- :mod:`lethe.runtime.scoring.per_class` — per-class scoring dispatch.
- :mod:`lethe.runtime.preferences_prepend` — gap-09 §6 always-load.
- :mod:`lethe.runtime.events` — ``recall`` event emit point.

Plus the S2 ``recall_ledger`` table (schema v3 — column shape folded in
this commit) and the per-tenant fact-store + preference-source Protocols
that abstract S1 / S3 / S4a from the verb.

The 11-step api §2.1 algorithm:

1. **Compute recall_id** — deterministic uuidv7 from
   ``(tenant_id, ts_recorded_ms, query_hash)`` per api §1.4. Computed
   first so every code path (including the k=0 short-circuit in §2.1.1)
   shares one identifier.
2. **k=0 short-circuit** — skip retrievers/RRF/rerank entirely; still
   write the ledger row, still prepend preferences, emit ZERO ``recall``
   events. Returns a ``facts=[]`` envelope (api §2.1.1; gates 3a + 3b).
3. **Intent classify** — at P3 the verb accepts a caller-supplied
   ``intent``; the live classifier dispatch wires in at P4 (the P2
   classifier is remember-side and not directly applicable to read-side
   intent — keeping the seam minimal at P3 honors D5).
4. **Parallel retrieve** — ``retrieve_all`` fans out semantic + lexical
   + graph (sequential at P3; parallel optimization is P-later).
5. **Bi-temporal filter (pre-RRF)** — drop hits whose validity window
   does not contain ``t_now``. Applied to each retriever's ranked list
   *before* RRF combine so RRF rank statistics never see invalid-window
   facts (invariant I-4).
6. **RRF combine** — fuse the three filtered ranked lists (rrf_k=60).
7. **Per-class score** — dispatch each fused candidate through
   ``per_class.score`` using its declared formula (D1; all 4 persistent
   shapes). RRF rank feeds the connectedness term as a normalized
   proxy at P3; full PPR-derived connectedness wires when the live
   graph backend lands (P4+).
8. **Truncate to top-k** — sort by per-class score descending, take
   the first ``k``.
9. **Provenance enforcement** — drop facts whose metadata lacks an
   ``episode_id`` (composition §6 invariant). Counted in
   ``applied_filters.provenance_dropped``.
10. **Write recall_ledger row** — INSERT OR IGNORE on the deterministic
    PK; replays of the same (tenant, ts, query_hash) silently no-op.
    Same-PK + different-payload raises :class:`RecallLedgerCorruption`.
11. **Prepend preferences** — gap-09 §6 unconditional include up to
    10 KB; ``preferences_truncated`` exposed when capped.
12. **Emit one ``recall`` event per top-k fact** — events share the
    same ``recall_id`` and carry ``path="recall"``. Validation by
    :mod:`lethe.runtime.events`.

Order is binding (api §2.1 §0.3 #2). The two helpers
:func:`write_ledger_row` and :func:`emit_recall_events` are exported at
module level so :mod:`lethe.api.recall_synthesis` (commit 4) reuses
them without duplication.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Literal, Protocol

from lethe.runtime.bitemporal_filter import filter_facts
from lethe.runtime.events import emit as emit_event
from lethe.runtime.preferences_prepend import (
    EMPTY_PREFERENCE_SOURCE,
    PreferencePage,
    PreferencesEnvelope,
    PreferenceSource,
)
from lethe.runtime.preferences_prepend import (
    build_envelope as build_preferences_envelope,
)
from lethe.runtime.recall_id import compute_query_hash, derive_recall_id
from lethe.runtime.retrievers import (
    GraphBackend,
    Hit,
    LexicalBackend,
    S3Outage,
    SemanticBackend,
)
from lethe.runtime.retrievers import (
    graph_topk as _graph_topk,
)
from lethe.runtime.retrievers import (
    lexical_topk as _lexical_topk,
)
from lethe.runtime.retrievers import (
    semantic_topk as _semantic_topk,
)
from lethe.runtime.retrievers.rrf import rrf_combine
from lethe.runtime.scoring.per_class import DEFAULT_WEIGHTS
from lethe.runtime.scoring.per_class import score as per_class_score

_VERB_NAME: Final[str] = "recall"

# Scoring envelope versions (api §1.7 + scoring §8.2). Mirror the P2
# pattern in remember.py — until WS5 stamps real release identifiers,
# these constants are the agreed P3 placeholders. ``weights_version``
# identifies the gap-03 §5 candidate-(a) weight tuple.
_MODEL_VERSION_P3: Final[str] = "p3-recall-v0"
_WEIGHTS_VERSION_P3: Final[str] = "p3-gap03-5a-v0"

#: RRF combine constant (scoring §4.2; gap-03 §5).
_RRF_K: Final[int] = 60

#: Per-retriever fan-out cap before RRF combine.
_K_PER_RETRIEVER: Final[int] = 50

RecallPath = Literal["recall", "synthesis"]


# ---------------------------------------------------------------------------
# Errors (api §1.6)
# ---------------------------------------------------------------------------


class RecallError(Exception):
    """Base class for ``recall`` verb failures.

    Carries the api §1.6 ``code`` and HTTP ``status`` so the transport
    surface (P7) can map without re-classifying exceptions.
    """

    code: str = "internal_error"
    status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RecallValidationError(RecallError):
    code = "invalid_request"
    status = 400


class RecallLedgerCorruption(RecallError):
    """Raised when an INSERT OR IGNORE collision reveals a payload divergence.

    Same recall_id with a different ``response_envelope_blob`` means a
    deterministic input produced two different outputs — a substrate
    bug, not a caller error. Surfaces as 500 so monitoring picks it up.
    """

    code = "internal_error"
    status = 500


# ---------------------------------------------------------------------------
# Protocols (substrate the verb consumes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FactRecord:
    """Metadata for a single recall candidate.

    The verb fetches these via the :class:`FactStore` Protocol after
    retrievers return rank-only :class:`Hit` objects. ``valid_to`` may
    be ``None`` (open-ended fact). ``episode_id`` may be ``None`` to
    indicate a missing-provenance fact (which gets dropped in step 9).
    """

    fact_id: str
    kind: str
    content: str
    valid_from: str
    valid_to: str | None
    recorded_at: str
    episode_id: str | None
    version: int = 1
    source_uri: str = ""


class FactStore(Protocol):
    """Per-tenant metadata-fetch Protocol.

    Production wiring (P4+) backs this with S1 + S3 joined views; tests
    inject in-memory stubs. ``t_now`` is supplied so backends MAY apply
    bi-temporal pushdown at the SQL layer (defense-in-depth alongside
    the verb's own :func:`filter_facts` call).
    """

    def fetch_many(
        self, fact_ids: Sequence[str], *, t_now: datetime
    ) -> list[FactRecord]: ...


# ---------------------------------------------------------------------------
# Request / Response dataclasses (api §2.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecallRequest:
    """Caller envelope for the ``recall`` verb (api §2.1).

    ``intent`` is optional; if omitted the verb uses ``"unspecified"``
    as the canonical query-hash and ledger value (the P4 read-side
    classifier wires in later). ``scope`` is a free-form mapping
    forwarded to retrievers (e.g. project-id / source-kind narrowing).

    There is no ``idempotency_key`` field: ``recall_id`` is itself the
    deterministic replay key (api §1.4), so a separate idempotency key
    would be redundant. Identical inputs produce the identical
    response_envelope, persisted under the same recall_id.
    """

    tenant_id: str
    query: str
    k: int = 10
    intent: str | None = None
    scope: Mapping[str, Any] = field(default_factory=dict)
    query_vec: Sequence[float] | None = None


@dataclass(frozen=True)
class ScoredFact:
    """A single top-k candidate in the recall response."""

    fact_id: str
    version: int
    kind: str
    content: str
    score: float
    score_inputs: Mapping[str, float]
    valid_from: str
    valid_to: str | None
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class RecallResponse:
    """The composition §3.5 / api §2.1 recall envelope."""

    recall_id: str
    facts: list[ScoredFact]
    preferences: list[PreferencePage]
    preferences_truncated: bool
    preferences_total_bytes: int
    classified_intent: str
    applied_filters: Mapping[str, Any]
    store_health: Mapping[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_iso(dt: datetime) -> str:
    """Millisecond-resolution ISO-8601 with ``Z`` suffix (api §1.4).

    ``ts_recorded`` is documented at millisecond resolution; we surface
    that everywhere the timestamp leaves the verb so the wire shape is
    consistent.
    """
    s = dt.astimezone(UTC).isoformat(timespec="milliseconds")
    return s.replace("+00:00", "Z")


def _ts_recorded_ms(dt: datetime) -> int:
    """Convert a datetime to milliseconds-since-epoch for the recall_id prefix."""
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _generate_uuidv7(*, now: datetime) -> str:
    """Random uuidv7 for non-deterministic IDs (event_id, etc.).

    Distinct from :func:`derive_recall_id` which builds a *deterministic*
    uuidv7 from request inputs.
    """
    import secrets

    unix_ts_ms = int(now.astimezone(UTC).timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    msb = (unix_ts_ms << 16) | (0x7 << 12) | rand_a
    lsb = (0b10 << 62) | rand_b
    value = (msb << 64) | lsb
    return str(uuid.UUID(int=value))


def _canonical_intent(intent: str | None) -> str:
    """Canonicalize an absent intent into ``"unspecified"`` for hashing + ledger."""
    return intent if intent else "unspecified"


def _hash_response_envelope(envelope: Mapping[str, Any]) -> bytes:
    """Stable hash of the response envelope for ledger payload comparison.

    Used in :func:`write_ledger_row` to detect same-PK + different-payload
    collisions (substrate bug → :class:`RecallLedgerCorruption`).
    """
    blob = json.dumps(envelope, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).digest()


def _serialize_response(response: RecallResponse) -> bytes:
    """Pack a ``RecallResponse`` for the ``response_envelope_blob`` column.

    JSON is sufficient at P3 (bandwidth + audit replay are the
    requirements; future binary format is forward-compatible because
    the column is a BLOB).
    """
    payload: dict[str, Any] = {
        "recall_id": response.recall_id,
        "facts": [
            {
                "fact_id": f.fact_id,
                "version": f.version,
                "kind": f.kind,
                "content": f.content,
                "score": f.score,
                "score_inputs": dict(f.score_inputs),
                "valid_from": f.valid_from,
                "valid_to": f.valid_to,
                "provenance": dict(f.provenance),
            }
            for f in response.facts
        ],
        "preferences": [
            {
                "page_uri": p.page_uri,
                "content": p.content,
                "kind": p.kind,
                "revision_id": p.revision_id,
                "revised_at": p.revised_at,
                "bytes": p.bytes,
            }
            for p in response.preferences
        ],
        "preferences_truncated": response.preferences_truncated,
        "preferences_total_bytes": response.preferences_total_bytes,
        "classified_intent": response.classified_intent,
        "applied_filters": dict(response.applied_filters),
        "store_health": dict(response.store_health),
    }
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# Module-level helpers shared with recall_synthesis (commit 4)
# ---------------------------------------------------------------------------


def write_ledger_row(
    conn: sqlite3.Connection,
    *,
    recall_id: str,
    tenant_id: str,
    query_hash: str,
    ts_recorded: str,
    classified_intent: str,
    weights_version: str,
    top_k_fact_ids: Sequence[str],
    response_envelope_blob: bytes,
) -> None:
    """Insert one ``recall_ledger`` row (commit 3 schema v3 shape).

    Uses ``INSERT OR IGNORE``: a legitimate replay (same deterministic
    ``recall_id`` + same payload) is a silent no-op. A same-PK +
    different-payload collision raises :class:`RecallLedgerCorruption`.
    Both ``recall`` and ``recall_synthesis`` (commit 4) call this; the
    helper is intentionally module-level so the verbs share one writer.
    """
    fact_ids_blob = json.dumps(list(top_k_fact_ids))
    cur = conn.execute(
        "INSERT OR IGNORE INTO recall_ledger("
        " recall_id, tenant_id, query_hash, ts_recorded, classified_intent,"
        " weights_version, top_k_fact_ids, response_envelope_blob"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            recall_id,
            tenant_id,
            query_hash,
            ts_recorded,
            classified_intent,
            weights_version,
            fact_ids_blob,
            response_envelope_blob,
        ),
    )
    if cur.rowcount == 1:
        return

    # IGNORE fired — verify the existing row matches (replay) vs.
    # diverges (substrate bug).
    existing = conn.execute(
        "SELECT response_envelope_blob FROM recall_ledger WHERE recall_id = ?",
        (recall_id,),
    ).fetchone()
    if existing is None:
        # Race that should never occur in single-writer P3 — surface
        # loudly rather than silently swallow.
        raise RecallLedgerCorruption(
            f"recall_ledger INSERT OR IGNORE on {recall_id!r} affected zero rows but"
            " no row exists on read-back"
        )
    existing_blob = existing[0]
    if bytes(existing_blob) != response_envelope_blob:
        raise RecallLedgerCorruption(
            f"recall_ledger PK collision on {recall_id!r}: same deterministic id "
            "produced divergent payloads (substrate invariant violation)"
        )


def build_recall_event(
    *,
    tenant_id: str,
    recall_id: str,
    fact_id: str,
    path: RecallPath,
    now: datetime,
    weights_version: str = _WEIGHTS_VERSION_P3,
    model_version: str = _MODEL_VERSION_P3,
) -> dict[str, Any]:
    """Build one scoring §8.1 ``recall`` event envelope.

    One event per top-k fact (api §2.1 step 11); each event carries the
    shared ``recall_id`` and a single-element ``fact_ids`` list. The
    ``path`` field discriminates ``recall`` (api §2.1) vs ``synthesis``
    (api §2.2).
    """
    ts = _format_iso(now)
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "recall",
        "tenant_id": tenant_id,
        "ts_recorded": ts,
        "ts_valid": ts,
        "model_version": model_version,
        "weights_version": weights_version,
        "contamination_protected": True,
        "recall_id": recall_id,
        "fact_ids": [fact_id],
        "path": path,
    }


def emit_recall_events(
    *,
    tenant_id: str,
    recall_id: str,
    fact_ids: Sequence[str],
    path: RecallPath,
    now: datetime,
    sink: Callable[[Mapping[str, Any]], None] | None = None,
    weights_version: str = _WEIGHTS_VERSION_P3,
    model_version: str = _MODEL_VERSION_P3,
) -> int:
    """Emit one ``recall`` event per ``fact_ids`` entry. Returns the count.

    On an empty ``fact_ids`` (k=0 / synthesis-no-hits), emits ZERO
    events and returns 0 — the caller should not see this as an error.
    Each emission flows through :func:`emit_event`, which validates
    against the §8.2 envelope contract and the recall-specific
    per-type extras.
    """
    count = 0
    for fact_id in fact_ids:
        event = build_recall_event(
            tenant_id=tenant_id,
            recall_id=recall_id,
            fact_id=fact_id,
            path=path,
            now=now,
            weights_version=weights_version,
            model_version=model_version,
        )
        emit_event(event, sink=sink)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Internal pipeline steps
# ---------------------------------------------------------------------------


def _filter_hits_by_kept_ids(
    hits: Sequence[Hit], *, kept_ids: frozenset[str]
) -> list[Hit]:
    """Drop hits whose fact_id is not in ``kept_ids`` and renumber rank.

    Rank renumbering is contiguous (1, 2, 3, ...) so the RRF combine
    sees the post-filter ranked list as if the dropped items had never
    been retrieved. Order is preserved.
    """
    out: list[Hit] = []
    rank = 1
    for hit in hits:
        if hit.fact_id not in kept_ids:
            continue
        out.append(Hit(fact_id=hit.fact_id, score=hit.score, source=hit.source, rank=rank))
        rank += 1
    return out


def _retrieve_per_source(
    *,
    query: str,
    query_vec: Sequence[float] | None,
    semantic: SemanticBackend | None,
    lexical: LexicalBackend,
    graph: GraphBackend | None,
    k_per_retriever: int,
) -> tuple[list[Hit], list[Hit], list[Hit], dict[str, Any]]:
    """Run each retriever individually so the verb can filter pre-RRF.

    Returns ``(semantic_hits, lexical_hits, graph_hits, store_health)``.
    Semantic-only failures (S3Outage) are absorbed and surfaced via
    ``store_health`` so the response can advertise ``s3_used=False``
    (composition §3.1 fallback path).
    """
    store_health: dict[str, Any] = {"s3_used": False, "degraded": False}
    semantic_hits: list[Hit] = []
    if semantic is not None and query_vec is not None:
        try:
            semantic_hits = _semantic_topk(
                backend=semantic, query_vec=query_vec, k=k_per_retriever
            )
            store_health["s3_used"] = True
        except S3Outage:
            store_health["degraded"] = True

    lexical_hits = _lexical_topk(backend=lexical, query=query, k=k_per_retriever)

    graph_hits: list[Hit] = []
    if graph is not None:
        graph_hits = _graph_topk(backend=graph, query=query, k=k_per_retriever)

    return semantic_hits, lexical_hits, graph_hits, store_health


def _score_one(
    *,
    record: FactRecord,
    rrf_score: float,
    rrf_max: float,
    t_now: datetime,
) -> tuple[float, dict[str, float]]:
    """Run one fused candidate through the per-class scorer.

    The connectedness term consumes a normalized RRF rank-score proxy
    at P3 (RRF score / max RRF score), keeping the term in [0, 1] as
    per_class.score requires. Live PPR-derived connectedness lands at
    P4+ when the production graph backend wires in. utility / gravity
    inputs default to 0.0 because P3 has no utility-event ledger or
    gravity store yet (D5).

    ``t_access`` is wired to ``valid_from`` as the recency seed (the
    fact's first appearance in the system); ``recorded_at`` would be
    equivalent for facts that never get re-recorded. For preference +
    narrative shapes the recency term is zeroed out by the per-class
    table anyway.

    Returns ``(score, score_inputs)`` where ``score_inputs`` records
    the term values for forward-compat with the §8.4 emit-pipeline.
    """
    connectedness_value = (rrf_score / rrf_max) if rrf_max > 0 else 0.0
    # Belt-and-braces clamp; numerical drift in (rrf_score / rrf_max)
    # cannot push the term out of [0, 1], but the assertion is documented
    # in per_class.score so we keep the values explicitly bounded here.
    connectedness_value = max(0.0, min(1.0, connectedness_value))
    utility_value = 0.0
    contradiction_count = 0
    gravity_value = 0.0
    t_access = datetime.fromisoformat(record.valid_from)
    composed = per_class_score(
        kind=record.kind,
        t_now=t_now,
        t_access=t_access,
        connectedness_value=connectedness_value,
        utility_value=utility_value,
        contradiction_count=contradiction_count,
        gravity_value=gravity_value,
        weights=DEFAULT_WEIGHTS,
    )
    score_inputs: dict[str, float] = {
        "rrf_score": float(rrf_score),
        "connectedness_value": connectedness_value,
        "utility_value": utility_value,
        "contradiction_count": float(contradiction_count),
        "gravity_value": gravity_value,
    }
    return composed, score_inputs


# ---------------------------------------------------------------------------
# Verb
# ---------------------------------------------------------------------------


def recall(
    request: RecallRequest,
    *,
    s2_conn: sqlite3.Connection,
    fact_store: FactStore,
    lexical: LexicalBackend,
    semantic: SemanticBackend | None = None,
    graph: GraphBackend | None = None,
    preference_source: PreferenceSource = EMPTY_PREFERENCE_SOURCE,
    event_sink: Callable[[Mapping[str, Any]], None] | None = None,
    now: datetime | None = None,
) -> RecallResponse:
    """Synchronous portion of ``recall`` (api §2.1).

    Arguments:
        request: caller envelope.
        s2_conn: per-tenant S2 connection (caller owns the T1 transaction;
            the verb writes one ledger row inside that transaction).
        fact_store: per-tenant metadata-fetch Protocol (S1 + S3 joined
            view in production; in-memory stubs in tests).
        lexical: SQLite FTS5 backend (composition §3.1 mandatory path).
        semantic: optional sqlite-vec backend; ``None`` triggers the
            lexical-only fallback. ``S3Outage`` raised by the backend
            is absorbed and surfaces in ``store_health.degraded=True``.
        graph: optional graph backend; ``None`` skips the graph retriever.
        preference_source: S4a Protocol; defaults to the empty source so
            tenants without S4a get a zero-page envelope.
        event_sink: deterministic recording sink for tests; ``None``
            uses the WS5 forward-spec sink (see :mod:`lethe.runtime.events`).
        now: explicit clock for tests; defaults to ``datetime.now(UTC)``.

    Returns:
        :class:`RecallResponse` with up to ``request.k`` facts plus the
        preferences envelope, classified intent, applied-filter accounting,
        and store-health snapshot.

    Raises:
        RecallValidationError: ``k < 0`` or empty ``tenant_id`` / ``query``.
        RecallLedgerCorruption: same recall_id with divergent payload
            (substrate bug, not a caller error).
    """
    n = now or _utc_now()
    if not request.tenant_id:
        raise RecallValidationError("recall: tenant_id must be non-empty")
    if request.k < 0:
        raise RecallValidationError(f"recall: k must be >= 0, got {request.k}")
    if request.query is None:
        # Empty string is allowed (lexical search will return nothing);
        # None is a contract violation.
        raise RecallValidationError("recall: query must be a string (not None)")

    # ---- Step 1: recall_id (deterministic) ------------------------------
    canonical_intent = _canonical_intent(request.intent)
    query_hash = compute_query_hash(
        {
            "query": request.query,
            "intent": canonical_intent,
            "k": request.k,
            "scope": dict(request.scope),
        }
    )
    ts_recorded_ms = _ts_recorded_ms(n)
    rid = derive_recall_id(
        tenant_id=request.tenant_id,
        ts_recorded_ms=ts_recorded_ms,
        query_hash=query_hash,
    )
    ts_recorded_iso = _format_iso(n)

    preferences_envelope = build_preferences_envelope(
        preference_source.list_preferences(tenant_id=request.tenant_id)
    )

    # ---- Step 2: k=0 short-circuit (api §2.1.1) -------------------------
    if request.k == 0:
        response = RecallResponse(
            recall_id=rid,
            facts=[],
            preferences=preferences_envelope.pages,
            preferences_truncated=preferences_envelope.truncated,
            preferences_total_bytes=preferences_envelope.total_bytes,
            classified_intent=canonical_intent,
            applied_filters={
                "bi_temporal_at": ts_recorded_iso,
                "pre_filter_excluded": 0,
                "provenance_dropped": 0,
                "k_zero_short_circuit": True,
            },
            store_health={"s3_used": False, "degraded": False},
        )
        write_ledger_row(
            s2_conn,
            recall_id=rid,
            tenant_id=request.tenant_id,
            query_hash=query_hash,
            ts_recorded=ts_recorded_iso,
            classified_intent=canonical_intent,
            weights_version=_WEIGHTS_VERSION_P3,
            top_k_fact_ids=(),
            response_envelope_blob=_serialize_response(response),
        )
        # Step 11 (k=0): emit ZERO recall events (gate 3b).
        return response

    # ---- Step 4: parallel retrieve --------------------------------------
    semantic_hits, lexical_hits, graph_hits, store_health = _retrieve_per_source(
        query=request.query,
        query_vec=request.query_vec,
        semantic=semantic,
        lexical=lexical,
        graph=graph,
        k_per_retriever=_K_PER_RETRIEVER,
    )

    # Union of fact_ids across all retrievers — fetch metadata once.
    union_ids: list[str] = []
    seen: set[str] = set()
    for ranked in (semantic_hits, lexical_hits, graph_hits):
        for hit in ranked:
            if hit.fact_id not in seen:
                seen.add(hit.fact_id)
                union_ids.append(hit.fact_id)

    records = fact_store.fetch_many(union_ids, t_now=n)
    by_id: dict[str, FactRecord] = {r.fact_id: r for r in records}

    # ---- Step 5: bi-temporal filter (pre-RRF; invariant I-4) ------------
    # Apply on the metadata-enriched union, then map kept fact_ids back
    # onto each retriever's ranked list. Rank reassignment preserves
    # within-list order so RRF math is correct.
    record_dicts = [
        {
            "fact_id": r.fact_id,
            "valid_from": r.valid_from,
            "valid_to": r.valid_to,
        }
        for r in records
    ]
    kept_dicts = filter_facts(record_dicts, t_now=n)
    kept_ids = frozenset(str(d["fact_id"]) for d in kept_dicts)
    pre_filter_excluded = len(union_ids) - len(kept_ids)

    semantic_kept = _filter_hits_by_kept_ids(semantic_hits, kept_ids=kept_ids)
    lexical_kept = _filter_hits_by_kept_ids(lexical_hits, kept_ids=kept_ids)
    graph_kept = _filter_hits_by_kept_ids(graph_hits, kept_ids=kept_ids)

    # ---- Step 6: RRF combine --------------------------------------------
    fused = rrf_combine(
        ranked_lists=[semantic_kept, lexical_kept, graph_kept],
        k_constant=_RRF_K,
    )

    # ---- Step 7: per-class score ----------------------------------------
    rrf_max = max((h.score for h in fused), default=0.0)
    scored: list[tuple[Hit, FactRecord, float, dict[str, float]]] = []
    for fused_hit in fused:
        record = by_id.get(fused_hit.fact_id)
        if record is None:
            # Retriever returned a fact_id with no metadata — should not
            # happen with a well-behaved fact_store, but skip rather than
            # crash so a backend bug doesn't break recall.
            continue
        composed, inputs = _score_one(
            record=record, rrf_score=fused_hit.score, rrf_max=rrf_max, t_now=n
        )
        scored.append((fused_hit, record, composed, inputs))

    # Sort by per-class score descending; secondary by fact_id for
    # deterministic tie-breaking.
    scored.sort(key=lambda t: (-t[2], t[1].fact_id))

    # ---- Step 8: truncate to top-k --------------------------------------
    truncated = scored[: request.k]

    # ---- Step 9: provenance enforcement (composition §6) ----------------
    facts: list[ScoredFact] = []
    provenance_dropped = 0
    for _hit, record, composed_score, inputs in truncated:
        if not record.episode_id:
            provenance_dropped += 1
            continue
        facts.append(
            ScoredFact(
                fact_id=record.fact_id,
                version=record.version,
                kind=record.kind,
                content=record.content,
                score=composed_score,
                score_inputs=inputs,
                valid_from=record.valid_from,
                valid_to=record.valid_to,
                provenance={
                    "episode_id": record.episode_id,
                    "source_uri": record.source_uri,
                    "recorded_at": record.recorded_at,
                },
            )
        )

    response = RecallResponse(
        recall_id=rid,
        facts=facts,
        preferences=preferences_envelope.pages,
        preferences_truncated=preferences_envelope.truncated,
        preferences_total_bytes=preferences_envelope.total_bytes,
        classified_intent=canonical_intent,
        applied_filters={
            "bi_temporal_at": ts_recorded_iso,
            "pre_filter_excluded": pre_filter_excluded,
            "provenance_dropped": provenance_dropped,
            "k_zero_short_circuit": False,
        },
        store_health=store_health,
    )

    # ---- Step 10: write recall_ledger row -------------------------------
    top_k_ids = [f.fact_id for f in facts]
    write_ledger_row(
        s2_conn,
        recall_id=rid,
        tenant_id=request.tenant_id,
        query_hash=query_hash,
        ts_recorded=ts_recorded_iso,
        classified_intent=canonical_intent,
        weights_version=_WEIGHTS_VERSION_P3,
        top_k_fact_ids=top_k_ids,
        response_envelope_blob=_serialize_response(response),
    )

    # ---- Step 11: emit one recall event per top-k fact ------------------
    emit_recall_events(
        tenant_id=request.tenant_id,
        recall_id=rid,
        fact_ids=top_k_ids,
        path="recall",
        now=n,
        sink=event_sink,
    )

    return response


__all__ = [
    "EMPTY_PREFERENCE_SOURCE",
    "FactRecord",
    "FactStore",
    "PreferencePage",
    "PreferencesEnvelope",
    "RecallError",
    "RecallLedgerCorruption",
    "RecallPath",
    "RecallRequest",
    "RecallResponse",
    "RecallValidationError",
    "ScoredFact",
    "build_recall_event",
    "emit_recall_events",
    "recall",
    "write_ledger_row",
]
