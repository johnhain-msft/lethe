"""Tests for :mod:`lethe.runtime.consolidate.contradiction`.

Coverage map (P4 commit 4 — pure adapter + re-export pins):

- :func:`eps_effective` log-dampened invariants:
  - ``count=0`` → ``eps`` (NOT 0); the dampener returns the cap, the
    indicator zeros the term.
  - ``count=1`` → ``eps * (1 + log 2) ≈ 0.847`` for ``eps=0.5`` —
    matches the scoring Appendix A f_proc datapoint.
  - ``count=10`` → ``eps * (1 + log 11)``.
  - Monotonic non-decreasing in ``count``.
  - Log-bounded — ``count = 1e6`` is finite and well below ``1e3``.
  - Negative ``eps`` / ``contradiction_count`` raise.
- :func:`contradiction_indicator`:
  - ``0 → 0.0``; ``> 0 → 1.0``; ``< 0`` raises.
  - Combined penalty ``eps_eff * indicator`` is ``0`` when ``count == 0``.
- :func:`count_active_contradictions`:
  - empty mapping → ``0``; missing key → ``0``; single → ``1``;
    multi-element set → ``len``.
  - Caller is responsible for pre-filtering to ACTIVE contradictions
    (gap-13 §3 supersession + revalidate paths) — documented in test
    docstring.
- Per-class ε cap NOT double-capped via the wrapper: a contradiction
  count threaded through :func:`per_class.score` for a preference kind
  produces the same value as a hand-computation that applies the
  0.30 cap exactly once.
- Re-export identity: :func:`eps_effective` and
  :func:`contradiction_indicator` ARE the same callables as in
  :mod:`lethe.runtime.scoring.contradiction`.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

import lethe.runtime.scoring.contradiction as scoring_contradiction
from lethe.runtime.consolidate.contradiction import (
    contradiction_indicator,
    count_active_contradictions,
    eps_effective,
)
from lethe.runtime.scoring.per_class import DEFAULT_WEIGHTS
from lethe.runtime.scoring.per_class import score as per_class_score

_T_NOW = datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Re-export identity
# ---------------------------------------------------------------------------


def test_eps_effective_is_scoring_eps_effective() -> None:
    assert eps_effective is scoring_contradiction.eps_effective


def test_contradiction_indicator_is_scoring_contradiction_indicator() -> None:
    assert contradiction_indicator is scoring_contradiction.contradiction_indicator


# ---------------------------------------------------------------------------
# eps_effective — log-dampened invariants
# ---------------------------------------------------------------------------


def test_eps_effective_count_zero_returns_eps() -> None:
    """At ``count=0`` the dampener is ``1 + log1p(0) = 1``, so
    ``eps_effective == eps`` — NOT 0. The indicator zeros the term;
    the dampener does not."""
    assert eps_effective(eps=0.5, contradiction_count=0) == 0.5


def test_eps_effective_count_one_matches_appendix_a_datapoint() -> None:
    """``eps_effective(eps=0.5, count=1) = 0.5 * (1 + log 2) ≈ 0.847``
    — matches scoring Appendix A f_proc."""
    expected = 0.5 * (1.0 + math.log(2.0))
    assert eps_effective(eps=0.5, contradiction_count=1) == pytest.approx(expected, abs=1e-9)
    assert eps_effective(eps=0.5, contradiction_count=1) == pytest.approx(0.847, abs=1e-3)


def test_eps_effective_count_ten_matches_log_form() -> None:
    expected = 0.5 * (1.0 + math.log(11.0))
    assert eps_effective(eps=0.5, contradiction_count=10) == pytest.approx(expected, abs=1e-9)


def test_eps_effective_monotonic_non_decreasing_in_count() -> None:
    prev = -math.inf
    for count in (0, 1, 2, 5, 10, 100, 1_000):
        cur = eps_effective(eps=0.5, contradiction_count=count)
        assert cur >= prev
        prev = cur


def test_eps_effective_log_bounded_at_million() -> None:
    """No divergence: ``count = 1e6`` is finite and well below 1e3."""
    val = eps_effective(eps=0.5, contradiction_count=1_000_000)
    assert math.isfinite(val)
    assert val < 1e3


def test_eps_effective_negative_eps_raises() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        eps_effective(eps=-0.1, contradiction_count=0)


def test_eps_effective_negative_count_raises() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        eps_effective(eps=0.5, contradiction_count=-1)


# ---------------------------------------------------------------------------
# contradiction_indicator — gating semantics
# ---------------------------------------------------------------------------


def test_contradiction_indicator_zero_count_returns_zero() -> None:
    assert contradiction_indicator(0) == 0.0


@pytest.mark.parametrize("count", [1, 2, 10, 100])
def test_contradiction_indicator_positive_count_returns_one(count: int) -> None:
    assert contradiction_indicator(count) == 1.0


def test_contradiction_indicator_negative_count_raises() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        contradiction_indicator(-1)


def test_combined_penalty_at_count_zero_is_zero() -> None:
    """The §3.5 contribution is ``eps_eff * indicator``; at ``count=0``
    the indicator is 0 → penalty is 0 regardless of eps_eff."""
    eps_eff = eps_effective(eps=0.5, contradiction_count=0)
    indicator = contradiction_indicator(0)
    assert eps_eff * indicator == 0.0


# ---------------------------------------------------------------------------
# count_active_contradictions — pure adapter
# ---------------------------------------------------------------------------


def test_count_empty_mapping_returns_zero() -> None:
    assert count_active_contradictions(fact_id="f1", contradicting_edges={}) == 0


def test_count_missing_fact_returns_zero() -> None:
    edges: dict[str, frozenset[str]] = {"f2": frozenset({"f3"})}
    assert count_active_contradictions(fact_id="f1", contradicting_edges=edges) == 0


def test_count_single_contradicting_edge_returns_one() -> None:
    edges = {"f1": frozenset({"f2"})}
    assert count_active_contradictions(fact_id="f1", contradicting_edges=edges) == 1


def test_count_multi_element_set_returns_len() -> None:
    edges = {"f1": frozenset({"f2", "f3", "f4"})}
    assert count_active_contradictions(fact_id="f1", contradicting_edges=edges) == 3


def test_count_caller_is_responsible_for_active_filter() -> None:
    """This adapter does NOT filter superseded / revalidated edges
    (gap-13 §3 + §7) — the caller pre-filters. Documented here so a
    future graph-traversal change has an explicit test asserting the
    pure-adapter contract is unchanged."""
    edges = {
        "f1": frozenset({"f2", "f3"}),  # caller has already removed superseded
    }
    assert count_active_contradictions(fact_id="f1", contradicting_edges=edges) == 2


def test_count_accepts_set_subclasses() -> None:
    """``Set`` (the abstract type from ``collections.abc``) covers
    ``set``, ``frozenset``, and any user-defined Set ABC subclass."""
    edges_set: dict[str, set[str]] = {"f1": {"f2", "f3"}}
    assert count_active_contradictions(fact_id="f1", contradicting_edges=edges_set) == 2


# ---------------------------------------------------------------------------
# Per-class ε cap NOT double-capped via the wrapper
# ---------------------------------------------------------------------------


def test_preference_eps_cap_applied_once_under_contradiction() -> None:
    """Threading a contradiction count through :func:`per_class.score`
    for a ``preference`` kind MUST cap ε at 0.30 exactly once; the
    consolidate wrapper does not re-cap. Hand-computed expected:

    - kind = preference (β=0)
    - tp = 0.85
    - eps_used = min(weights.eps=0.5, eps_cap=0.30) = 0.30
    - eps_eff(0.30, count=2) = 0.30 * (1 + log 3)
    - additive = 0.20*0.85 + 0 + 0.20*0.40 + 0.40*0.30 - eps_eff*1
    - score_pre_grav < theta? (depends on additive)
    """
    weights = DEFAULT_WEIGHTS
    eps_eff = 0.30 * (1.0 + math.log(3.0))
    additive = (
        0.20 * 0.85  # alpha * tp(preference)
        + 0.0  # beta=0 for preference
        + 0.20 * 0.40  # gamma * connectedness
        + 0.40 * 0.30  # delta * utility
        - eps_eff * 1.0  # contradiction term (capped 0.30)
    )
    theta_demote = 0.20
    expected_mult = 1.0 if additive >= theta_demote else max(1.0, 1.0 + 0.5 * 0.50)
    expected_final = expected_mult * additive

    actual = per_class_score(
        kind="preference",
        t_now=_T_NOW,
        t_access=_T_NOW,
        connectedness_value=0.40,
        utility_value=0.30,
        contradiction_count=2,
        gravity_value=0.50,
        weights=weights,
        theta_demote=theta_demote,
    )
    assert actual == pytest.approx(expected_final, abs=1e-9)
