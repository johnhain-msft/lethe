"""Idempotency-key primitive coverage (api §1.2; gap-08 §3.1).

Covers:

- uuidv7 RFC 9562 layout validation (valid + several malformed forms).
- record → lookup round-trip returns the stored body_hash + response.
- lookup on a missing or expired row returns ``None``.
- ``record`` after the prior row has expired succeeds (TTL rollover).
- ``check_replay_or_conflict`` differentiates replay (matching body_hash)
  from conflict (differing body_hash).
- Per-tenant scope: tenant A's keys are invisible to tenant B.
- Per-verb scope: same uuid string under ``remember`` and ``forget``
  coexists (the storage-key namespacing fix; api §1.2 line 81 invariant).
- Versioned envelope round-trip + corrupt-blob detection.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lethe.runtime.idempotency import (
    DEFAULT_TTL_HOURS,
    IdempotencyConflict,
    IdempotencyHit,
    IdempotencyKeyMalformed,
    IdempotencyKeyMissing,
    IdempotencyStoreCorrupt,
    check_replay_or_conflict,
    lookup,
    record,
    validate_uuidv7,
)
from lethe.store.s2_meta import S2Schema

# A few RFC 9562 v7 strings (version nibble = 0x7; variant high bits = 0b10).
_VALID_KEY_A = "01890af0-0000-7000-8000-000000000001"
_VALID_KEY_B = "01890af0-0000-7abc-bdef-000000000002"
_VALID_KEY_C = "0190af00-1234-7fff-9000-abcdef012345"


@pytest.fixture
def s2_conn(tenant_root: Path) -> sqlite3.Connection:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# validate_uuidv7
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", [_VALID_KEY_A, _VALID_KEY_B, _VALID_KEY_C])
def test_uuidv7_shape_validation_accepts_valid(key: str) -> None:
    validate_uuidv7(key)  # no raise


def test_uuidv7_shape_validation_rejects_empty() -> None:
    with pytest.raises(IdempotencyKeyMissing):
        validate_uuidv7("")


@pytest.mark.parametrize(
    "bad_key",
    [
        "not-a-uuid",
        # Wrong version nibble (0x4 instead of 0x7):
        "01890af0-0000-4000-8000-000000000001",
        # Wrong variant bits (0xc instead of 0x8/9/a/b):
        "01890af0-0000-7000-c000-000000000001",
        # Too short:
        "01890af0-0000-7000-8000-0000000001",
        # Trailing junk:
        "01890af0-0000-7000-8000-000000000001-extra",
        # Non-hex chars:
        "0189zzzz-0000-7000-8000-000000000001",
    ],
)
def test_uuidv7_shape_validation_rejects_malformed(bad_key: str) -> None:
    with pytest.raises(IdempotencyKeyMalformed):
        validate_uuidv7(bad_key)


# ---------------------------------------------------------------------------
# record + lookup round-trip
# ---------------------------------------------------------------------------


def test_record_then_lookup_returns_hit(s2_conn: sqlite3.Connection) -> None:
    response = {"ack": "stored", "episode_id": "ep-1"}
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-a",
        response=response,
    )
    hit = lookup(s2_conn, key=_VALID_KEY_A, verb="remember")
    assert hit == IdempotencyHit(body_hash="hash-a", response=response)


def test_lookup_missing_returns_none(s2_conn: sqlite3.Connection) -> None:
    assert lookup(s2_conn, key=_VALID_KEY_A, verb="remember") is None


def test_lookup_after_ttl_returns_none(s2_conn: sqlite3.Connection) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-a",
        response={"ack": "stored"},
        ttl_hours=DEFAULT_TTL_HOURS,
        now=t0,
    )
    after_ttl = t0 + timedelta(hours=DEFAULT_TTL_HOURS, minutes=1)
    assert lookup(s2_conn, key=_VALID_KEY_A, verb="remember", now=after_ttl) is None


def test_record_after_expiry_allows_fresh_call(s2_conn: sqlite3.Connection) -> None:
    """The PK collision must not block a legitimate post-TTL re-record."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-old",
        response={"ack": "stale"},
        ttl_hours=DEFAULT_TTL_HOURS,
        now=t0,
    )
    after_ttl = t0 + timedelta(hours=DEFAULT_TTL_HOURS + 1)
    # Same key, fresh write past TTL — must succeed silently.
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-new",
        response={"ack": "fresh"},
        now=after_ttl,
    )
    hit = lookup(s2_conn, key=_VALID_KEY_A, verb="remember", now=after_ttl)
    assert hit is not None
    assert hit.body_hash == "hash-new"


# ---------------------------------------------------------------------------
# check_replay_or_conflict
# ---------------------------------------------------------------------------


def test_check_replay_returns_none_when_missing(s2_conn: sqlite3.Connection) -> None:
    result = check_replay_or_conflict(
        s2_conn, key=_VALID_KEY_A, verb="remember", body_hash="hash-a"
    )
    assert result is None


def test_check_replay_returns_hit_for_matching_body(
    s2_conn: sqlite3.Connection,
) -> None:
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-a",
        response={"ack": "stored"},
    )
    hit = check_replay_or_conflict(
        s2_conn, key=_VALID_KEY_A, verb="remember", body_hash="hash-a"
    )
    assert hit is not None
    assert hit.response == {"ack": "stored"}


def test_check_replay_raises_conflict_for_differing_body(
    s2_conn: sqlite3.Connection,
) -> None:
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-original",
        response={"ack": "stored"},
    )
    with pytest.raises(IdempotencyConflict) as excinfo:
        check_replay_or_conflict(
            s2_conn,
            key=_VALID_KEY_A,
            verb="remember",
            body_hash="hash-different",
        )
    err = excinfo.value
    assert err.key == _VALID_KEY_A
    assert err.verb == "remember"
    assert err.original_hash == "hash-original"
    assert err.retried_hash == "hash-different"


# ---------------------------------------------------------------------------
# Scope: per-tenant + per-verb
# ---------------------------------------------------------------------------


def test_per_tenant_scope_isolation(lethe_home: Path) -> None:
    """Tenant A's keys must not appear in tenant B's idempotency table."""
    root_a = lethe_home / "tenants" / "tenant-a"
    root_b = lethe_home / "tenants" / "tenant-b"
    conn_a = S2Schema(tenant_root=root_a).create()
    conn_b = S2Schema(tenant_root=root_b).create()
    try:
        record(
            conn_a,
            key=_VALID_KEY_A,
            verb="remember",
            body_hash="hash-a",
            response={"ack": "tenant-a"},
        )
        assert lookup(conn_a, key=_VALID_KEY_A, verb="remember") is not None
        assert lookup(conn_b, key=_VALID_KEY_A, verb="remember") is None
    finally:
        conn_a.close()
        conn_b.close()


def test_per_verb_scope_same_uuid_coexists(s2_conn: sqlite3.Connection) -> None:
    """api §1.2: a `remember` key and a `forget` key with the same uuid value
    do not collide. Internal storage-key namespacing makes this hold even
    though the schema declares ``key`` as the PK alone."""
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-r",
        response={"ack": "remember"},
    )
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="forget",
        body_hash="hash-f",
        response={"ack": "forget"},
    )
    hit_r = lookup(s2_conn, key=_VALID_KEY_A, verb="remember")
    hit_f = lookup(s2_conn, key=_VALID_KEY_A, verb="forget")
    assert hit_r is not None and hit_r.response == {"ack": "remember"}
    assert hit_f is not None and hit_f.response == {"ack": "forget"}


def test_lookup_filters_by_verb(s2_conn: sqlite3.Connection) -> None:
    """A row recorded under one verb must not be returned to a lookup
    against a different verb."""
    record(
        s2_conn,
        key=_VALID_KEY_A,
        verb="remember",
        body_hash="hash-r",
        response={"ack": "remember"},
    )
    assert lookup(s2_conn, key=_VALID_KEY_A, verb="forget") is None


# ---------------------------------------------------------------------------
# Versioned envelope + corruption
# ---------------------------------------------------------------------------


def test_corrupt_blob_raises_store_corrupt(s2_conn: sqlite3.Connection) -> None:
    """A row whose response_blob is not a valid v1 envelope surfaces clearly."""
    s2_conn.execute(
        "INSERT INTO idempotency_keys (key, verb, response_blob, expires_at)"
        " VALUES (?, ?, ?, ?)",
        (
            f"remember:{_VALID_KEY_A}",
            "remember",
            b"this is not json",
            (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace(
                "+00:00", "Z"
            ),
        ),
    )
    with pytest.raises(IdempotencyStoreCorrupt):
        lookup(s2_conn, key=_VALID_KEY_A, verb="remember")


def test_lookup_validates_key_shape(s2_conn: sqlite3.Connection) -> None:
    with pytest.raises(IdempotencyKeyMalformed):
        lookup(s2_conn, key="not-a-uuid", verb="remember")


def test_record_validates_key_shape(s2_conn: sqlite3.Connection) -> None:
    with pytest.raises(IdempotencyKeyMalformed):
        record(
            s2_conn,
            key="not-a-uuid",
            verb="remember",
            body_hash="x",
            response={},
        )
