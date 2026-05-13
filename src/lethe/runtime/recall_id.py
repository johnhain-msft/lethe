"""Deterministic ``recall_id`` derivation per api §1.4 (binding).

Authoritative spec (api §1.4):

- ``recall_id = uuidv7(tenant_id, ts_recorded, query_hash)``.
- ``query_hash = sha256(canonical_json({query, intent, k, scope}))[:16]``
  (16 lowercase hex characters of the sha256 hexdigest).
- ``ts_recorded`` is request-arrival timestamp at **millisecond**
  resolution.
- 48-bit timestamp prefix = ``ts_recorded`` in milliseconds (RFC 9562).
- 4-bit version = ``0111``; 2-bit variant = ``10`` (RFC 9562 fixed).
- The remaining 74 bits (``rand_a ‖ rand_b``) are the **leading 74 bits
  of** ``sha256(tenant_id ‖ query_hash)``. There is **NO** discriminant
  string folded into the hash, and ``ts_recorded`` is **NOT** part of
  the hash input — only ``(tenant_id, query_hash)`` are.

The replay invariant (scoring §8.3) requires the §8.4 emit-pipeline to
reproduce ``recall_id`` from logged inputs without the live runtime;
this only works if the deterministic 74 bits depend on
``(tenant_id, query_hash)`` exactly per api §1.4, with the timestamp
contributing only the 48-bit prefix. The earlier kickoff prose that
folded a ``"rec"`` discriminant and ``ts_recorded`` into the hash was a
slip inherited from the predecessor handoff; it is superseded by this
module's implementation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any, Final

#: Maximum representable ``ts_recorded_ms`` (48 bits unsigned).
_MAX_TS_MS: Final[int] = (1 << 48) - 1

#: Canonical query-hash payload key set (api §1.4).
_QUERY_HASH_KEYS: Final[frozenset[str]] = frozenset({"query", "intent", "k", "scope"})


class RecallIdError(Exception):
    """Raised on malformed inputs to :func:`derive_recall_id` / :func:`compute_query_hash`."""


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    """Stable JSON encoding with sorted keys and tight separators."""
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_query_hash(payload: Mapping[str, Any]) -> str:
    """Compute the api §1.4 query hash for a recall request.

    ``payload`` MUST contain exactly the keys ``{"query", "intent", "k",
    "scope"}``. Returns 16 lowercase hex characters of the sha256 hex
    digest.

    Raises:
        RecallIdError: ``payload`` is missing required keys or contains
            unexpected keys (canonical shape is strict — extra keys
            would change the hash silently if accepted).
    """
    keys = frozenset(payload.keys())
    if keys != _QUERY_HASH_KEYS:
        missing = sorted(_QUERY_HASH_KEYS - keys)
        extra = sorted(keys - _QUERY_HASH_KEYS)
        raise RecallIdError(
            "compute_query_hash: payload keys must be exactly "
            f"{sorted(_QUERY_HASH_KEYS)} (missing={missing}, extra={extra})"
        )
    return hashlib.sha256(_canonical_json(payload)).hexdigest()[:16]


def derive_recall_id(
    *,
    tenant_id: str,
    ts_recorded_ms: int,
    query_hash: str,
) -> str:
    """Pack a deterministic uuidv7 from the api §1.4 inputs.

    The 48-bit timestamp prefix carries ``ts_recorded_ms``. The 74
    deterministic bits in ``rand_a ‖ rand_b`` are taken as the leading
    74 bits of ``sha256(tenant_id_bytes ‖ query_hash_bytes)``; both
    inputs are UTF-8 encoded.

    Raises:
        RecallIdError: invalid tenant_id, ts_recorded_ms, or query_hash.
    """
    if not tenant_id:
        raise RecallIdError("derive_recall_id: tenant_id must be non-empty")
    if not isinstance(ts_recorded_ms, int) or isinstance(ts_recorded_ms, bool):
        raise RecallIdError(
            f"derive_recall_id: ts_recorded_ms must be an int, got {type(ts_recorded_ms)!r}"
        )
    if ts_recorded_ms < 0 or ts_recorded_ms > _MAX_TS_MS:
        raise RecallIdError(
            f"derive_recall_id: ts_recorded_ms {ts_recorded_ms} not in [0, {_MAX_TS_MS}]"
        )
    if (
        len(query_hash) != 16
        or not all(c in "0123456789abcdef" for c in query_hash)
    ):
        raise RecallIdError(
            f"derive_recall_id: query_hash must be 16 lowercase hex chars, got {query_hash!r}"
        )

    digest = hashlib.sha256(
        tenant_id.encode("utf-8") + query_hash.encode("utf-8")
    ).digest()
    digest_int = int.from_bytes(digest, "big")
    # Leading 74 bits of the 256-bit digest (right-shift by the remaining 182).
    rand_bits = digest_int >> (256 - 74)
    rand_a = (rand_bits >> 62) & 0xFFF  # top 12 bits of the 74
    rand_b = rand_bits & ((1 << 62) - 1)  # bottom 62 bits

    # RFC 9562 layout (MSB → LSB):
    #   48 ts | 4 ver=0x7 | 12 rand_a | 2 var=0b10 | 62 rand_b
    uuid_int = (
        ((ts_recorded_ms & _MAX_TS_MS) << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0x2 << 62)
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))


def recall_id(
    *,
    tenant_id: str,
    ts_recorded_ms: int,
    query: str,
    intent: str,
    k: int,
    scope: Mapping[str, Any],
) -> str:
    """Convenience wrapper: compute ``query_hash`` then derive the ``recall_id``."""
    query_hash = compute_query_hash(
        {"query": query, "intent": intent, "k": k, "scope": dict(scope)}
    )
    return derive_recall_id(
        tenant_id=tenant_id,
        ts_recorded_ms=ts_recorded_ms,
        query_hash=query_hash,
    )


__all__ = [
    "RecallIdError",
    "compute_query_hash",
    "derive_recall_id",
    "recall_id",
]
