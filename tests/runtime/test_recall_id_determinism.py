"""Tests for ``runtime.recall_id`` — api §1.4 binding spec.

Covers:

- Same ``(tenant_id, ts_recorded_ms, query_hash)`` → same ``recall_id``.
- Same ``(tenant_id, query_hash)`` with different ``ts_recorded_ms`` →
  ids differ ONLY in the 48-bit timestamp prefix (74 deterministic bits
  are byte-identical because they hash only ``(tenant_id, query_hash)``).
- Different ``tenant_id`` with otherwise-identical inputs → different
  ``recall_id`` (api §1.4 third bullet).
- ``compute_query_hash`` returns 16 lowercase hex; key order in the
  payload doesn't change the hash; changing any of ``query / intent /
  k / scope`` changes the hash.
- RFC 9562 layout invariants: version nibble = ``7``; variant high bits
  ∈ ``{8,9,a,b}``; 48-bit ts prefix decodes to the input ms.
- Anti-regression: the 74 deterministic bits are derived from
  ``sha256(tenant_id ‖ query_hash)`` ONLY — guards against future drift
  back to a ``"rec"`` discriminant or ``ts_recorded`` folding.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from lethe.runtime.recall_id import (
    RecallIdError,
    compute_query_hash,
    derive_recall_id,
    recall_id,
)

# A fixed canonical payload used across multiple tests.
_PAYLOAD = {
    "query": "what's my preferred editor?",
    "intent": "state_fact",
    "k": 5,
    "scope": {"project": "lethe"},
}

_TENANT = "tenant-a"
_TS_MS = 1_715_500_000_123  # arbitrary ms timestamp inside the 48-bit window


def test_same_inputs_yield_same_recall_id() -> None:
    qh = compute_query_hash(_PAYLOAD)
    a = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    b = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    assert a == b


def test_different_ts_changes_only_48_bit_prefix() -> None:
    """ts_recorded_ms must NOT influence the 74 deterministic bits."""
    qh = compute_query_hash(_PAYLOAD)
    a = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    b = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS + 12345, query_hash=qh)
    assert a != b
    a_int = uuid.UUID(a).int
    b_int = uuid.UUID(b).int
    # 80 LSBs = 4-bit ver | 12-bit rand_a | 2-bit var | 62-bit rand_b → must be identical.
    mask80 = (1 << 80) - 1
    assert (a_int & mask80) == (b_int & mask80)
    # The 48-bit MSBs (the ts prefix) must differ by exactly the ms delta.
    assert (a_int >> 80) == _TS_MS
    assert (b_int >> 80) == _TS_MS + 12345


def test_different_tenant_yields_different_id() -> None:
    qh = compute_query_hash(_PAYLOAD)
    a = derive_recall_id(tenant_id="tenant-a", ts_recorded_ms=_TS_MS, query_hash=qh)
    b = derive_recall_id(tenant_id="tenant-b", ts_recorded_ms=_TS_MS, query_hash=qh)
    assert a != b
    # ts prefix is identical; the difference must be in the 80 LSBs
    # (specifically inside rand_a/rand_b — the version & variant nibbles
    # are fixed, so the difference is concentrated in the deterministic
    # bits).
    a_int = uuid.UUID(a).int
    b_int = uuid.UUID(b).int
    assert (a_int >> 80) == (b_int >> 80) == _TS_MS


def test_query_hash_canonical_shape() -> None:
    qh = compute_query_hash(_PAYLOAD)
    assert len(qh) == 16
    assert all(c in "0123456789abcdef" for c in qh)
    # Key order in the payload dict must not change the hash (canonical
    # JSON sorts keys).
    reordered = {
        "scope": _PAYLOAD["scope"],
        "k": _PAYLOAD["k"],
        "intent": _PAYLOAD["intent"],
        "query": _PAYLOAD["query"],
    }
    assert compute_query_hash(reordered) == qh


@pytest.mark.parametrize(
    "mutation",
    [
        {"query": "different question"},
        {"intent": "narrative_recall"},
        {"k": 6},
        {"scope": {"project": "other"}},
    ],
)
def test_query_hash_changes_when_any_field_changes(mutation: dict[str, object]) -> None:
    base = compute_query_hash(_PAYLOAD)
    mutated_payload = dict(_PAYLOAD)
    mutated_payload.update(mutation)
    assert compute_query_hash(mutated_payload) != base


def test_query_hash_rejects_extra_or_missing_keys() -> None:
    with pytest.raises(RecallIdError, match="extra"):
        compute_query_hash({**_PAYLOAD, "uninvited": "guest"})
    with pytest.raises(RecallIdError, match="missing"):
        compute_query_hash({"query": "q", "intent": "i", "k": 1})


def test_uuidv7_rfc9562_layout() -> None:
    qh = compute_query_hash(_PAYLOAD)
    rid = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    # Canonical 8-4-4-4-12 form.
    assert len(rid) == 36
    parsed = uuid.UUID(rid)
    # Version nibble = 7.
    assert parsed.hex[12] == "7"
    # Variant high bits 0b10 → first hex char of the variant nibble ∈ {8,9,a,b}.
    assert parsed.hex[16] in "89ab"
    # 48-bit ts prefix decodes to the exact input ms.
    assert (parsed.int >> 80) == _TS_MS


def test_no_ts_recorded_in_deterministic_bits() -> None:
    """Anti-regression: the 74 deterministic bits hash ONLY (tenant_id, query_hash).

    No ``"rec"`` discriminant. No ``ts_recorded`` folded into the hash
    input. We recompute the expected 74 bits independently and assert
    they match the recall_id's tail bits, then assert they are
    timestamp-invariant.
    """
    qh = compute_query_hash(_PAYLOAD)
    digest = hashlib.sha256(_TENANT.encode("utf-8") + qh.encode("utf-8")).digest()
    digest_int = int.from_bytes(digest, "big")
    expected_rand_bits = digest_int >> (256 - 74)
    expected_rand_a = (expected_rand_bits >> 62) & 0xFFF
    expected_rand_b = expected_rand_bits & ((1 << 62) - 1)

    rid = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    rid_int = uuid.UUID(rid).int
    actual_rand_a = (rid_int >> 64) & 0xFFF
    actual_rand_b = rid_int & ((1 << 62) - 1)
    assert actual_rand_a == expected_rand_a
    assert actual_rand_b == expected_rand_b

    # Second derivation with a wildly different ts must reproduce the
    # same rand_a + rand_b — that is the property the §8.4 emit-pipeline
    # depends on for replay (it does not need the ts to recompute the
    # 74 deterministic bits).
    rid2 = derive_recall_id(
        tenant_id=_TENANT, ts_recorded_ms=_TS_MS + 999_999, query_hash=qh
    )
    rid2_int = uuid.UUID(rid2).int
    assert ((rid2_int >> 64) & 0xFFF) == expected_rand_a
    assert (rid2_int & ((1 << 62) - 1)) == expected_rand_b


def test_recall_id_convenience_matches_two_step_derivation() -> None:
    one_shot = recall_id(
        tenant_id=_TENANT,
        ts_recorded_ms=_TS_MS,
        query=_PAYLOAD["query"],
        intent=_PAYLOAD["intent"],
        k=_PAYLOAD["k"],
        scope=_PAYLOAD["scope"],
    )
    qh = compute_query_hash(_PAYLOAD)
    two_step = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    assert one_shot == two_step


@pytest.mark.parametrize(
    "ts_ms",
    [-1, (1 << 48)],
)
def test_derive_rejects_out_of_range_ts(ts_ms: int) -> None:
    qh = compute_query_hash(_PAYLOAD)
    with pytest.raises(RecallIdError):
        derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=ts_ms, query_hash=qh)


def test_derive_rejects_empty_tenant() -> None:
    qh = compute_query_hash(_PAYLOAD)
    with pytest.raises(RecallIdError, match="tenant_id"):
        derive_recall_id(tenant_id="", ts_recorded_ms=_TS_MS, query_hash=qh)


@pytest.mark.parametrize(
    "bad_qh",
    ["", "tooshort", "ABCDEF0123456789", "012345678901234g", "0" * 17],
)
def test_derive_rejects_malformed_query_hash(bad_qh: str) -> None:
    with pytest.raises(RecallIdError, match="query_hash"):
        derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=bad_qh)


def test_derive_rejects_bool_ts() -> None:
    """``True``/``False`` are ints in Python; reject explicitly."""
    qh = compute_query_hash(_PAYLOAD)
    with pytest.raises(RecallIdError):
        derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=True, query_hash=qh)  # type: ignore[arg-type]


def test_derive_validates_uuidv7_regex() -> None:
    """The output must satisfy the same regex idempotency.py uses."""
    from lethe.runtime.idempotency import validate_uuidv7

    qh = compute_query_hash(_PAYLOAD)
    rid = derive_recall_id(tenant_id=_TENANT, ts_recorded_ms=_TS_MS, query_hash=qh)
    validate_uuidv7(rid)  # must not raise
