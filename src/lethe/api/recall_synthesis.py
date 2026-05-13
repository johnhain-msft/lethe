"""``recall_synthesis`` verb implementation (api §2.2).

The S4a-targeted markdown synthesis path. Composition §3.2.

**Distinct from** :func:`lethe.api.recall.recall` — synthesis pages are
S4a-canonical (authored prose, not facts), and conflating them with the
fact path corrupts both surfaces. They share a transport (the ``recall``
event) but the discriminator ``path="synthesis"`` lets the v2 emit
pipeline split or unify by its own preference (scoring §5).

Algorithm (api §2.2):

1. Validate: exactly one of ``uri`` / ``query`` is required.
2. **Compute recall_id** — deterministic uuidv7 per api §1.4. Inputs
   are funnelled through the canonical ``compute_query_hash`` shape
   ``{query, intent, k, scope}`` with ``intent`` carrying the synthesis
   discriminant (``"synthesis_uri"`` or ``"synthesis_query"``). This
   makes ``recall_synthesis("X")`` and ``recall("X")`` deterministically
   distinct (which they ARE — different verbs, different surfaces).
3. **Fetch** —
   - ``uri`` form: direct fetch by S4a stable uri; bypass index. 404 if
     unknown.
   - ``query`` form: qmd-class hybrid retrieve over S4a (gap-07).
4. **No bi-temporal filter** — synthesis pages are authored, not
   bi-temporally stamped (composition §3 row S4a). Revision history is
   git-based. The verb intentionally does NOT call
   :mod:`lethe.runtime.bitemporal_filter`.
5. **Write recall_ledger row** — INSERT OR IGNORE on the deterministic
   PK; ``weights_version="synthesis-passthrough"`` (no scoring weights
   apply to direct page lookup or qmd-class rerank).
6. **Emit one ``recall`` event per returned page** — events share the
   shared ``recall_id`` and carry ``path="synthesis"``. ``fact_ids`` is
   set to the S4a page-ids (deterministic uuid derived from the stable
   page_uri) NOT S1 fact-edge ids.
7. **Return**.

S4a outage policy (composition §7): ``recall_synthesis`` is the **only**
read path that goes hard-fail on S4a outage. The fact ``recall`` path
is unaffected; it absorbs S3 outage into ``store_health.degraded``.

Code reuse: this module imports
:func:`lethe.api.recall.write_ledger_row` and
:func:`lethe.api.recall.emit_recall_events` directly — the same writer
and emit-pipeline run for both verbs (per sub-plan §(g); commit-3
exposed them at module level for exactly this purpose).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Protocol

from lethe.api.recall import (
    _canonical_intent as _canonical_intent_helper,
)
from lethe.api.recall import (
    _format_iso as _format_iso_helper,
)
from lethe.api.recall import (
    _ts_recorded_ms as _ts_recorded_ms_helper,
)
from lethe.api.recall import (
    _utc_now as _utc_now_helper,
)
from lethe.api.recall import (
    emit_recall_events,
    write_ledger_row,
)
from lethe.runtime.recall_id import compute_query_hash, derive_recall_id

_VERB_NAME: Final[str] = "recall_synthesis"

#: Per kickoff: synthesis is a passthrough — no recall-time weight tuple
#: applies (URI form is direct fetch; query form is qmd-class hybrid
#: rerank, not the recall-side per-class formula). The literal is
#: persisted in the recall_ledger row and surfaces in the v2 §8.4
#: emit-pipeline so trainers can split synthesis vs. recall by it.
_WEIGHTS_VERSION_SYNTHESIS: Final[str] = "synthesis-passthrough"

#: Canonical intent discriminants for the api §1.4 query_hash. The
#: canonical key set ``{query, intent, k, scope}`` is enforced by
#: :func:`compute_query_hash`; ``intent`` is repurposed here to keep
#: synthesis recall_ids distinct from fact-recall ids that happen to
#: share the same query string.
_INTENT_URI: Final[str] = "synthesis_uri"
_INTENT_QUERY: Final[str] = "synthesis_query"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SynthesisError(Exception):
    """Base class for ``recall_synthesis`` verb errors."""

    code: str = "internal_error"
    status: int = 500


class SynthesisValidationError(SynthesisError):
    """Caller violated the verb's input contract (api §2.2 ``400``)."""

    code = "invalid_request"
    status = 400


class SynthesisNotFoundError(SynthesisError):
    """``uri`` form against an unknown S4a stable uri (api §2.2 ``404``)."""

    code = "not_found"
    status = 404


class S4aOutage(SynthesisError):
    """S4a corruption / unavailable (composition §7).

    ``recall_synthesis`` is the only read path that hard-fails on this;
    the fact ``recall`` path is unaffected. Surfaces as 5xx so callers
    fail-loud instead of silently degrading the synthesis surface.
    """

    code = "internal_error"
    status = 500


# ---------------------------------------------------------------------------
# Protocols + data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthesisPage:
    """A single S4a page in the synthesis response (api §2.2)."""

    page_uri: str
    title: str
    kind: str  # gap-09 §3: "preference" | "procedure" | "narrative"
    frontmatter: Mapping[str, Any]
    content: str
    revision_id: str  # git sha
    score: float
    provenance: Mapping[str, Any]


class SynthesisSource(Protocol):
    """Per-tenant S4a-backed page source.

    Production wiring (P4+) backs this with the on-disk S4a layout +
    qmd-class hybrid index (gap-07). At P3 there is no live qmd index,
    so the verb consumes this Protocol and tests inject in-memory
    stubs. The two methods correspond to the api §2.2 algorithm's two
    branches.

    Implementations MUST raise :class:`S4aOutage` on substrate
    corruption rather than returning an empty list — synthesis is
    hard-fail on S4a outage by design (composition §7).
    """

    def fetch_by_uri(
        self, *, tenant_id: str, uri: str
    ) -> SynthesisPage | None:
        """URI form: direct fetch. ``None`` → 404 not_found."""

    def hybrid_query(
        self, *, tenant_id: str, query: str, k: int
    ) -> list[SynthesisPage]:
        """Query form: qmd-class hybrid retrieve. May return ``[]``."""


@dataclass(frozen=True)
class SynthesisRequest:
    """Caller envelope for ``recall_synthesis`` (api §2.2).

    Exactly one of ``uri`` or ``query`` is required (validated in the
    verb). ``scope`` participates in the recall_id query_hash so two
    callers with different scope masks get distinct ledger rows even
    when the surface query is identical.
    """

    tenant_id: str
    uri: str | None = None
    query: str | None = None
    k: int = 5
    scope: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisResponse:
    """The api §2.2 synthesis envelope."""

    recall_id: str
    pages: list[SynthesisPage]
    store_health: Mapping[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _page_uri_to_id(uri: str) -> str:
    """Deterministic page-id derived from a stable S4a uri.

    Per api §2.2 emit-points contract: ``fact_ids`` carries S4a page-ids
    (stable URIs hashed to uuid). The events module accepts arbitrary
    non-empty ``str`` values for ``fact_ids`` entries; we use a uuid
    string built from the leading 16 bytes of the URI's sha256 so the
    page-id is stable across runs and joinable across emit-pipeline
    sessions.
    """
    digest = hashlib.sha256(uri.encode("utf-8")).digest()[:16]
    return str(uuid.UUID(bytes=digest))


def _serialize_response(response: SynthesisResponse) -> bytes:
    """Pack a :class:`SynthesisResponse` for the ``response_envelope_blob``.

    JSON; same posture as :func:`lethe.api.recall._serialize_response`
    (BLOB column accepts any encoding; JSON is the P3 choice for audit
    replay readability and bandwidth).
    """
    payload: dict[str, Any] = {
        "recall_id": response.recall_id,
        "pages": [
            {
                "page_uri": p.page_uri,
                "title": p.title,
                "kind": p.kind,
                "frontmatter": dict(p.frontmatter),
                "content": p.content,
                "revision_id": p.revision_id,
                "score": p.score,
                "provenance": dict(p.provenance),
            }
            for p in response.pages
        ],
        "store_health": dict(response.store_health),
    }
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# The verb
# ---------------------------------------------------------------------------


def recall_synthesis(
    request: SynthesisRequest,
    *,
    s2_conn: sqlite3.Connection,
    source: SynthesisSource,
    event_sink: Callable[[Mapping[str, Any]], None] | None = None,
    now: datetime | None = None,
) -> SynthesisResponse:
    """Synchronous portion of ``recall_synthesis`` (api §2.2).

    Arguments:
        request: caller envelope; exactly one of ``uri`` / ``query``.
        s2_conn: per-tenant S2 connection (caller owns the T1
            transaction; the verb writes one ledger row inside it).
        source: per-tenant S4a-backed page source Protocol.
        event_sink: deterministic recording sink for tests; ``None``
            uses the WS5 forward-spec sink (see
            :mod:`lethe.runtime.events`).
        now: explicit clock for tests; defaults to ``datetime.now(UTC)``.

    Returns:
        :class:`SynthesisResponse` with up to ``request.k`` pages plus
        the store-health snapshot.

    Raises:
        SynthesisValidationError: missing tenant_id, both/neither of
            ``uri`` / ``query``, or ``k < 0``.
        SynthesisNotFoundError: ``uri`` form against an unknown URI.
        S4aOutage: S4a substrate corruption (composition §7); bubbles
            up from the source Protocol.
    """
    n = now or _utc_now_helper()

    # ---- Step 1: validate ----------------------------------------------
    if not request.tenant_id:
        raise SynthesisValidationError(
            "recall_synthesis: tenant_id must be non-empty"
        )
    if request.k < 0:
        raise SynthesisValidationError(
            f"recall_synthesis: k must be >= 0, got {request.k}"
        )
    has_uri = request.uri is not None
    has_query = request.query is not None
    if has_uri == has_query:
        # Both or neither — both code paths land in the same 400.
        raise SynthesisValidationError(
            "recall_synthesis: exactly one of `uri` or `query` is required"
        )

    # ---- Step 2: recall_id (deterministic; api §1.4) -------------------
    # The synthesis discriminant goes in `intent` so synthesis ids are
    # never confused with fact-recall ids that happen to share the same
    # query string.
    if has_uri:
        assert request.uri is not None  # narrowing for mypy
        canonical_intent = _INTENT_URI
        hash_payload = {
            "query": request.uri,
            "intent": canonical_intent,
            "k": request.k,
            "scope": dict(request.scope),
        }
    else:
        assert request.query is not None  # narrowing for mypy
        canonical_intent = _INTENT_QUERY
        hash_payload = {
            "query": request.query,
            "intent": canonical_intent,
            "k": request.k,
            "scope": dict(request.scope),
        }

    query_hash = compute_query_hash(hash_payload)
    ts_recorded_ms = _ts_recorded_ms_helper(n)
    rid = derive_recall_id(
        tenant_id=request.tenant_id,
        ts_recorded_ms=ts_recorded_ms,
        query_hash=query_hash,
    )
    ts_recorded_iso = _format_iso_helper(n)

    # ---- Step 3: fetch -------------------------------------------------
    # NOTE: NO bi-temporal filter is applied here (api §2.2 step 3).
    # Synthesis pages are authored prose, not bi-temporally stamped
    # facts; the composition §3 row S4a row uses git revision history
    # for time-travel, not (valid_from, valid_to). Skipping the filter
    # is intentional, not an oversight.
    pages: list[SynthesisPage]
    if has_uri:
        assert request.uri is not None
        page = source.fetch_by_uri(tenant_id=request.tenant_id, uri=request.uri)
        if page is None:
            raise SynthesisNotFoundError(
                f"recall_synthesis: no S4a page at uri {request.uri!r}"
            )
        pages = [page]
    else:
        assert request.query is not None
        # Empty-result query is legitimate (no matches in the qmd corpus);
        # NOT an error. The verb still writes a ledger row and emits
        # zero events — same posture as recall(k=0).
        pages = list(
            source.hybrid_query(
                tenant_id=request.tenant_id,
                query=request.query,
                k=request.k,
            )
        )
        # Truncate defensively in case the source overshoots.
        pages = pages[: request.k]

    response = SynthesisResponse(
        recall_id=rid,
        pages=pages,
        store_health={"s4a_available": True},
    )

    # ---- Step 5: write recall_ledger row -------------------------------
    page_ids: list[str] = [_page_uri_to_id(p.page_uri) for p in pages]
    write_ledger_row(
        s2_conn,
        recall_id=rid,
        tenant_id=request.tenant_id,
        query_hash=query_hash,
        ts_recorded=ts_recorded_iso,
        classified_intent=canonical_intent,
        weights_version=_WEIGHTS_VERSION_SYNTHESIS,
        top_k_fact_ids=page_ids,
        response_envelope_blob=_serialize_response(response),
    )

    # ---- Step 6: emit one recall event per returned page ---------------
    # Empty pages → ZERO events (emit_recall_events handles this).
    emit_recall_events(
        tenant_id=request.tenant_id,
        recall_id=rid,
        fact_ids=page_ids,
        path="synthesis",
        now=n,
        sink=event_sink,
        weights_version=_WEIGHTS_VERSION_SYNTHESIS,
    )

    return response


# Re-export the helper names recall.py exposes here too, for symmetry
# with downstream consumers that import from this module.
__all__ = [
    "S4aOutage",
    "SynthesisError",
    "SynthesisNotFoundError",
    "SynthesisPage",
    "SynthesisRequest",
    "SynthesisResponse",
    "SynthesisSource",
    "SynthesisValidationError",
    "recall_synthesis",
]
# Quiet ruff F401 on the canonical-intent helper import (kept available
# for future synthesis-side intent-classifier wiring; not removed to
# preserve the 1:1 helper-import roster with recall.py).
_ = _canonical_intent_helper
