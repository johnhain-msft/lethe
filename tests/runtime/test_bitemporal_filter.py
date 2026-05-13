"""Tests for ``runtime.bitemporal_filter`` (scoring §4.1; invariant I-4).

Covers:

- Facts whose validity window does not contain ``t_now`` are excluded.
- Open-ended facts (``valid_to`` IS NULL) pass the upper-bound clause.
- The filter has no "small store" shortcut — it runs on every input
  size (invariant I-4).
- :data:`T_PURGE_DAYS` is exposed and unchanged.
- :func:`is_purge_eligible` honors the 90-day grace.
- :func:`pre_retriever_apply` invokes the filter **before** any
  retriever call (assertion via recording double).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from lethe.runtime.bitemporal_filter import (
    T_PURGE_DAYS,
    BitemporalFilterError,
    filter_facts,
    is_purge_eligible,
    pre_retriever_apply,
)

T0 = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _fact(
    fact_id: str,
    *,
    valid_from: datetime,
    valid_to: datetime | None = None,
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "valid_from": _iso(valid_from),
        "valid_to": _iso(valid_to) if valid_to is not None else None,
    }


def test_excludes_fact_with_valid_from_in_future() -> None:
    facts = [_fact("future", valid_from=T0 + timedelta(days=1))]
    assert filter_facts(facts, t_now=T0) == []


def test_excludes_fact_with_valid_to_at_or_before_now() -> None:
    # valid_to == t_now → invalid (strict ">", scoring §4.1).
    facts = [
        _fact("expired", valid_from=T0 - timedelta(days=10), valid_to=T0),
        _fact(
            "expired-yesterday",
            valid_from=T0 - timedelta(days=10),
            valid_to=T0 - timedelta(days=1),
        ),
    ]
    assert filter_facts(facts, t_now=T0) == []


def test_keeps_open_ended_fact() -> None:
    facts = [_fact("open", valid_from=T0 - timedelta(days=10), valid_to=None)]
    out = filter_facts(facts, t_now=T0)
    assert [f["fact_id"] for f in out] == ["open"]


def test_keeps_fact_currently_valid() -> None:
    facts = [
        _fact(
            "current",
            valid_from=T0 - timedelta(days=10),
            valid_to=T0 + timedelta(days=10),
        )
    ]
    out = filter_facts(facts, t_now=T0)
    assert [f["fact_id"] for f in out] == ["current"]


def test_filter_runs_on_small_store_no_shortcut() -> None:
    """Invariant I-4: no early-exit on tiny inputs.

    A single invalid-window fact must be dropped, not pass through
    because "the store is small".
    """
    facts = [_fact("future", valid_from=T0 + timedelta(seconds=1))]
    assert filter_facts(facts, t_now=T0) == []
    # And the empty input case still goes through the filter pipeline.
    assert filter_facts([], t_now=T0) == []


def test_filter_handles_mixed_validity() -> None:
    facts = [
        _fact("a-keep", valid_from=T0 - timedelta(days=1)),
        _fact("b-future", valid_from=T0 + timedelta(days=1)),
        _fact("c-keep-bounded", valid_from=T0 - timedelta(days=1), valid_to=T0 + timedelta(days=1)),
        _fact("d-expired", valid_from=T0 - timedelta(days=2), valid_to=T0 - timedelta(seconds=1)),
    ]
    out = filter_facts(facts, t_now=T0)
    assert [f["fact_id"] for f in out] == ["a-keep", "c-keep-bounded"]


def test_filter_raises_on_missing_valid_from() -> None:
    facts: list[dict[str, Any]] = [{"fact_id": "broken"}]
    with pytest.raises(BitemporalFilterError, match="valid_from"):
        filter_facts(facts, t_now=T0)


def test_t_purge_days_constant_is_90() -> None:
    assert T_PURGE_DAYS == 90


def test_is_purge_eligible_returns_false_within_grace() -> None:
    fact = _fact(
        "recent-invalidation",
        valid_from=T0 - timedelta(days=120),
        valid_to=T0 - timedelta(days=30),
    )
    assert is_purge_eligible(fact, t_now=T0) is False


def test_is_purge_eligible_returns_true_past_grace() -> None:
    fact = _fact(
        "old-invalidation",
        valid_from=T0 - timedelta(days=200),
        valid_to=T0 - timedelta(days=120),
    )
    assert is_purge_eligible(fact, t_now=T0) is True


def test_is_purge_eligible_open_ended_never_purged() -> None:
    fact = _fact("open", valid_from=T0 - timedelta(days=400), valid_to=None)
    assert is_purge_eligible(fact, t_now=T0) is False


def test_pre_retriever_apply_runs_filter_before_retriever() -> None:
    """Recording-double contract: the retriever is NOT invoked until the
    filter has fully returned. We capture call order via a monotonic
    counter shared between the (synchronous) filter and the retriever.
    """
    call_order: list[str] = []

    facts = [
        _fact("keep", valid_from=T0 - timedelta(days=1)),
        _fact("drop", valid_from=T0 + timedelta(days=1)),
    ]

    def recording_retriever(filtered: list[dict[str, Any]]) -> list[dict[str, Any]]:
        call_order.append("retriever")
        # The retriever sees ONLY the filtered candidates; the dropped
        # invalid-window fact never reaches it.
        assert [f["fact_id"] for f in filtered] == ["keep"]
        return filtered

    # Wrap the iterator to record exactly when the filter consumes it
    # — proves the filter has materialized its output before the
    # retriever runs.
    def recording_iter() -> Any:
        yield from facts
        call_order.append("filter-exhausted")

    out = pre_retriever_apply(
        facts=recording_iter(),
        retriever=recording_retriever,
        t_now=T0,
    )

    assert [f["fact_id"] for f in out] == ["keep"]
    # The filter must exhaust its source before the retriever is called.
    assert call_order == ["filter-exhausted", "retriever"]


def test_pre_retriever_apply_does_not_invoke_retriever_on_filter_failure() -> None:
    """If the filter raises, the retriever is never called."""
    invocations: list[str] = []

    def retriever(filtered: list[dict[str, Any]]) -> list[dict[str, Any]]:
        invocations.append("called")
        return filtered

    bad: list[dict[str, Any]] = [{"fact_id": "broken"}]  # missing valid_from
    with pytest.raises(BitemporalFilterError):
        pre_retriever_apply(facts=bad, retriever=retriever, t_now=T0)
    assert invocations == []
