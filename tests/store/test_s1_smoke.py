"""S1 smoke: schema creates cleanly from an empty tenant root.

Per plan.md §B8 row S1: bootstrap succeeds against the in-memory backend;
baseline entity types are registered; bi-temporal stamp helpers produce
monotonic ``recorded_at`` and reject inverted ``valid_from > valid_to``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lethe.store.s1_graph import (
    BASELINE_ENTITY_TYPES,
    BiTemporalStamp,
    S1Client,
    _InMemoryGraphBackend,
    now_recorded_at,
    stamp,
)


def test_s1_bootstrap_registers_baseline_types() -> None:
    backend = _InMemoryGraphBackend()
    client = S1Client(backend, tenant_id="smoke")
    assert not client.is_ready()

    client.bootstrap()

    assert client.is_ready()
    assert client.tenant_id == "smoke"
    registered = backend._registered_types_for("smoke")
    assert registered == frozenset(BASELINE_ENTITY_TYPES)


def test_s1_bootstrap_is_idempotent() -> None:
    backend = _InMemoryGraphBackend()
    client = S1Client(backend, tenant_id="smoke")
    client.bootstrap()
    client.bootstrap()  # second call must not raise
    assert backend._registered_types_for("smoke") == frozenset(BASELINE_ENTITY_TYPES)


def test_s1_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        S1Client(_InMemoryGraphBackend(), tenant_id="")


def test_bi_temporal_stamp_helpers() -> None:
    t0 = now_recorded_at()
    t1 = now_recorded_at()
    assert t1 >= t0  # monotonic non-decrease

    valid_from = datetime(2026, 1, 1, tzinfo=UTC)
    s = stamp(valid_from=valid_from)
    assert s.valid_from == valid_from
    assert s.valid_to is None
    assert s.recorded_at >= t1


def test_bi_temporal_stamp_rejects_inverted_validity() -> None:
    valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    valid_to = valid_from - timedelta(days=1)
    with pytest.raises(ValueError, match="precedes"):
        BiTemporalStamp(
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=now_recorded_at(),
        )
