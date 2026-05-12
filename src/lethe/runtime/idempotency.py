"""Idempotency-key contract primitives (api §1.2; gap-08 §3.1).

P2 ships the primitives consumed by the ``remember`` verb at commit 4:

- RFC 9562 uuidv7 string validation (mandatory; missing → 400; malformed → 400).
- 24 h TTL by default (caller may override at record-time).
- Replay → returns the stored response payload; caller surfaces it with
  ``ack=idempotency_replay`` per api §1.6.
- Conflict (same key + different request body hash) →
  :class:`IdempotencyConflict`; caller maps to 409 ``idempotency_conflict``.
- Per-(tenant, verb) scope: tenant scope is the per-tenant S2 file (each
  tenant has its own ``s2_meta.sqlite``); verb scope is achieved by
  internally namespacing the storage key as ``"{verb}:{key}"`` so that a
  ``remember`` key and a ``forget`` key with the same uuid value coexist
  even though the P1 schema declares ``key`` as the table primary key.
  The ``verb`` column is still populated for audit.

Storage layout: the schema's ``response_blob`` column is opaque BLOB. We
pack a versioned JSON envelope::

    {"version": 1, "body_hash": "<sha256 hex>", "response": {...}}

so that the primitive can detect body-hash mismatch without a v3 column
migration. Corrupt blobs raise :class:`IdempotencyStoreCorrupt`.

Transactional discipline: callers MUST invoke :func:`record` inside the
same SQLite transaction as the underlying write (composition §5 T1). A
crash between the write and the record leaves the system in a state
where the next retry will re-execute the write — which is the same
correctness boundary gap-08 §3.1 already names.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

DEFAULT_TTL_HOURS: Final[int] = 24

# RFC 9562 v7: version nibble = 0x7; variant high bits = 0b10 (8/9/a/b).
_UUIDV7_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_PACK_VERSION: Final[int] = 1


class IdempotencyError(Exception):
    """Base class for all idempotency-primitive errors."""


class IdempotencyKeyMissing(IdempotencyError):
    """Raised when no idempotency_key is supplied (api §1.2 → 400)."""


class IdempotencyKeyMalformed(IdempotencyError):
    """Raised when the supplied key is not a valid RFC 9562 uuidv7 string."""


class IdempotencyConflict(IdempotencyError):
    """Raised when same key+verb is reused with a different body hash (→ 409).

    Carries both the original and the retried body hash so the caller can
    surface them in the api §1.6 error envelope.
    """

    def __init__(
        self,
        *,
        key: str,
        verb: str,
        original_hash: str,
        retried_hash: str,
    ) -> None:
        super().__init__(
            f"idempotency_conflict: key={key} verb={verb} "
            f"original={original_hash} retried={retried_hash}"
        )
        self.key = key
        self.verb = verb
        self.original_hash = original_hash
        self.retried_hash = retried_hash


class IdempotencyStoreCorrupt(IdempotencyError):
    """Raised when ``response_blob`` cannot be unpacked into the expected envelope."""


def validate_uuidv7(key: str) -> None:
    """Validate that ``key`` is a well-formed RFC 9562 uuidv7 string.

    Raises:
        IdempotencyKeyMissing: empty key (api §1.2 mandatory-key clause).
        IdempotencyKeyMalformed: non-empty key that fails the v7 layout.
    """
    if not key:
        raise IdempotencyKeyMissing("idempotency_key is mandatory (api §1.2)")
    if not _UUIDV7_RE.match(key):
        raise IdempotencyKeyMalformed(
            f"idempotency_key {key!r} is not a valid RFC 9562 uuidv7"
        )


@dataclass(frozen=True)
class IdempotencyHit:
    """Result of a successful lookup: stored response payload + body hash."""

    body_hash: str
    response: dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> datetime:
    # Python 3.11+ ``datetime.fromisoformat`` accepts the trailing ``Z``.
    return datetime.fromisoformat(s)


def _expires_at(ttl_hours: int, *, now: datetime | None = None) -> str:
    return _format_iso((now or _now()) + timedelta(hours=ttl_hours))


def _storage_key(key: str, verb: str) -> str:
    """Internal namespacing so per-verb scope holds without a schema change."""
    return f"{verb}:{key}"


def _pack(body_hash: str, response: dict[str, Any]) -> bytes:
    return json.dumps(
        {"version": _PACK_VERSION, "body_hash": body_hash, "response": response},
        sort_keys=True,
    ).encode("utf-8")


def _unpack(blob: bytes) -> IdempotencyHit:
    try:
        obj = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdempotencyStoreCorrupt(
            "response_blob is not a valid JSON envelope"
        ) from exc
    if not isinstance(obj, dict):
        raise IdempotencyStoreCorrupt("response_blob did not unpack to a dict")
    version = obj.get("version")
    body_hash = obj.get("body_hash")
    response = obj.get("response")
    if version != _PACK_VERSION:
        raise IdempotencyStoreCorrupt(
            f"response_blob version {version!r} != expected {_PACK_VERSION}"
        )
    if not isinstance(body_hash, str) or not isinstance(response, dict):
        raise IdempotencyStoreCorrupt(
            "response_blob missing body_hash:str / response:dict"
        )
    return IdempotencyHit(body_hash=body_hash, response=response)


def _delete_expired(
    conn: sqlite3.Connection, *, storage_key: str, now: datetime
) -> None:
    """Remove a row for ``storage_key`` whose ``expires_at`` is at/before ``now``.

    This is what lets a caller re-record a fresh response after the 24 h
    TTL has elapsed; without it the PK collision would block a legitimate
    fresh call (api §1.2 "regenerate keys past 24 h" wording).
    """
    cur = conn.execute(
        "SELECT expires_at FROM idempotency_keys WHERE key = ?",
        (storage_key,),
    )
    row = cur.fetchone()
    if row is None:
        return
    if _parse_iso(row[0]) <= now:
        conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (storage_key,))


def lookup(
    conn: sqlite3.Connection,
    *,
    key: str,
    verb: str,
    now: datetime | None = None,
) -> IdempotencyHit | None:
    """Look up a recorded key+verb. Pure read; returns None if missing or expired.

    Body-hash mismatch is *not* signalled here — callers that need
    replay-vs-conflict semantics use :func:`check_replay_or_conflict`.
    """
    validate_uuidv7(key)
    n = now or _now()
    cur = conn.execute(
        "SELECT response_blob, expires_at FROM idempotency_keys"
        " WHERE key = ? AND verb = ?",
        (_storage_key(key, verb), verb),
    )
    row = cur.fetchone()
    if row is None:
        return None
    response_blob, expires_at_iso = row
    if _parse_iso(expires_at_iso) <= n:
        return None
    if response_blob is None:
        return None
    return _unpack(response_blob)


def record(
    conn: sqlite3.Connection,
    *,
    key: str,
    verb: str,
    body_hash: str,
    response: dict[str, Any],
    ttl_hours: int = DEFAULT_TTL_HOURS,
    now: datetime | None = None,
) -> None:
    """Persist a fresh idempotency-key row.

    Caller must have lookup-missed first. If a row with the same storage
    key still exists but is past TTL, it is deleted before insert so the
    fresh call can claim the key. A live (non-expired) row triggers
    :class:`sqlite3.IntegrityError` from the PK constraint; callers
    upstream surface that as the api §1.6 ``idempotency_conflict`` (the
    pre-write :func:`check_replay_or_conflict` path is the canonical way
    to reach that signal — direct PK collisions here indicate a missed
    pre-check by the caller).
    """
    validate_uuidv7(key)
    n = now or _now()
    storage_key = _storage_key(key, verb)
    _delete_expired(conn, storage_key=storage_key, now=n)
    blob = _pack(body_hash, response)
    expires_iso = _expires_at(ttl_hours, now=n)
    conn.execute(
        "INSERT INTO idempotency_keys (key, verb, response_blob, expires_at)"
        " VALUES (?, ?, ?, ?)",
        (storage_key, verb, blob, expires_iso),
    )


def check_replay_or_conflict(
    conn: sqlite3.Connection,
    *,
    key: str,
    verb: str,
    body_hash: str,
    now: datetime | None = None,
) -> IdempotencyHit | None:
    """Pre-write idempotency check.

    Returns:
        None if no live row exists → caller proceeds with the fresh write
        and follow-up :func:`record` call inside the same transaction.
        :class:`IdempotencyHit` if a live row exists with a matching
        ``body_hash`` → caller returns the stored response with
        ``ack=idempotency_replay``.

    Raises:
        IdempotencyConflict: a live row exists with a different
            ``body_hash`` (api §1.2 → 409 ``idempotency_conflict``).
    """
    hit = lookup(conn, key=key, verb=verb, now=now)
    if hit is None:
        return None
    if hit.body_hash != body_hash:
        raise IdempotencyConflict(
            key=key,
            verb=verb,
            original_hash=hit.body_hash,
            retried_hash=body_hash,
        )
    return hit
