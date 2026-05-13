"""Tests for :mod:`lethe.runtime.consolidate.gravity`.

Coverage map (P4 commit 4 — pure cascade-cost math + re-export pins):

- :func:`cascade_cost` shape / ordering / disagreement / negative-weight
  / self-loop / missing-fact behavior.
- :func:`cascade_cost_99pct` lower-bound discontinuous form: empty,
  singleton, ordinary populations (n=10, n=100, n=1000), outlier
  clipping, negative cost.
- Re-export identity: :func:`normalize_gravity` IS
  :func:`lethe.runtime.scoring.gravity.gravity` and :func:`gravity_mult`
  IS :func:`lethe.runtime.scoring.gravity.gravity_mult` (same callable
  object — no shadow definition).
- Q1 invariant (scoring §3.6): :func:`score_fact` equals
  ``gravity_mult * sum_of_additives`` on a hand-constructed input where
  the additive sum is computed independently.
- Invalidated facts: ``gravity_mult = 0`` re-asserted at the consolidate
  layer.
- f_proc-style edge case: ``score_pre_grav = -0.453``, ``gravity = 0.5``,
  ``gravity_mult = 1.25``, final ≈ ``-0.566`` (floor does not rescue).

NOT in scope this commit (lands at C6/C8):

- Edge-class weight table (citation / co-occurrence / supersession).
- 2-hop neighborhood materialization from the live graph backend.
- Cascade-cost feedback into the consolidation_state ledger.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

import lethe.runtime.scoring.gravity as scoring_gravity
from lethe.runtime.consolidate.gravity import (
    cascade_cost,
    cascade_cost_99pct,
    gravity_mult,
    normalize_gravity,
)
from lethe.runtime.consolidate.score import (
    ConsolidateScoreInput,
    score_fact,
)

# ---------------------------------------------------------------------------
# Re-export identity
# ---------------------------------------------------------------------------


def test_normalize_gravity_is_scoring_gravity() -> None:
    assert normalize_gravity is scoring_gravity.gravity


def test_gravity_mult_is_scoring_gravity_mult() -> None:
    assert gravity_mult is scoring_gravity.gravity_mult


# ---------------------------------------------------------------------------
# cascade_cost — basic shape
# ---------------------------------------------------------------------------


def test_cascade_cost_empty_adjacency_returns_zero() -> None:
    assert cascade_cost(fact_id="f1", adjacency_2hop={}) == 0.0


def test_cascade_cost_missing_fact_returns_zero() -> None:
    adj = {"f2": {"f3": 0.5}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == 0.0


def test_cascade_cost_isolated_fact_returns_zero() -> None:
    adj: dict[str, dict[str, float]] = {"f1": {}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == 0.0


def test_cascade_cost_single_edge_returns_weight() -> None:
    adj = {"f1": {"f2": 0.7}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == 0.7


def test_cascade_cost_multiple_edges_sum() -> None:
    adj = {"f1": {"f2": 0.5, "f3": 0.25, "f4": 1.0}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == pytest.approx(1.75)


# ---------------------------------------------------------------------------
# cascade_cost — undirected semantics
# ---------------------------------------------------------------------------


def test_cascade_cost_symmetric_adjacency_no_double_count() -> None:
    """``adj[a][b] == adj[b][a]`` MUST count the edge once, not twice."""
    adj = {
        "f1": {"f2": 0.5, "f3": 0.25},
        "f2": {"f1": 0.5},
        "f3": {"f1": 0.25},
    }
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == pytest.approx(0.75)


def test_cascade_cost_reverse_only_edge_is_counted() -> None:
    """An edge present ONLY as ``adj[neighbor][fact_id]`` (no forward
    entry under fact_id) MUST still contribute — undirected
    semantics."""
    adj = {
        "f2": {"f1": 0.4},
        "f3": {"f1": 0.6},
    }
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == pytest.approx(1.0)


def test_cascade_cost_disagreement_raises() -> None:
    adj = {
        "f1": {"f2": 0.5},
        "f2": {"f1": 0.7},
    }
    with pytest.raises(ValueError, match="disagreement"):
        cascade_cost(fact_id="f1", adjacency_2hop=adj)


def test_cascade_cost_self_loop_ignored() -> None:
    adj = {"f1": {"f1": 0.9, "f2": 0.3}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == pytest.approx(0.3)


def test_cascade_cost_negative_weight_raises_forward() -> None:
    adj = {"f1": {"f2": -0.1}}
    with pytest.raises(ValueError, match=">= 0"):
        cascade_cost(fact_id="f1", adjacency_2hop=adj)


def test_cascade_cost_negative_weight_raises_reverse() -> None:
    adj = {"f2": {"f1": -0.2}}
    with pytest.raises(ValueError, match=">= 0"):
        cascade_cost(fact_id="f1", adjacency_2hop=adj)


def test_cascade_cost_zero_weight_allowed() -> None:
    adj = {"f1": {"f2": 0.0, "f3": 0.5}}
    assert cascade_cost(fact_id="f1", adjacency_2hop=adj) == 0.5


# ---------------------------------------------------------------------------
# cascade_cost_99pct — quantile semantics
# ---------------------------------------------------------------------------


def test_cascade_cost_99pct_empty_returns_zero() -> None:
    assert cascade_cost_99pct([]) == 0.0


def test_cascade_cost_99pct_singleton_returns_value() -> None:
    assert cascade_cost_99pct([42.0]) == 42.0


def test_cascade_cost_99pct_n_100_lower_bound_form() -> None:
    """n=100, ceil(0.99*100)=99, idx=99-1=98, sorted[98]=98."""
    assert cascade_cost_99pct([float(i) for i in range(100)]) == 98.0


def test_cascade_cost_99pct_n_10_lower_bound_form() -> None:
    """n=10, ceil(0.99*10)=ceil(9.9)=10, idx=10-1=9, sorted[9]=9."""
    assert cascade_cost_99pct([float(i) for i in range(10)]) == 9.0


def test_cascade_cost_99pct_n_1000_lower_bound_form() -> None:
    """n=1000, ceil(990)=990, idx=989, sorted[989]=989."""
    assert cascade_cost_99pct([float(i) for i in range(1000)]) == 989.0


def test_cascade_cost_99pct_unsorted_input_handled() -> None:
    """The function MUST sort internally — caller does not have to."""
    costs = [99.0, 1.0, 50.0, 25.0, 75.0, 10.0, 60.0, 30.0, 5.0, 80.0]
    assert cascade_cost_99pct(costs) == 99.0


def test_cascade_cost_99pct_outlier_clipping_via_lower_bound() -> None:
    """A single 1e6 outlier in 100 items: sorted has 1e6 at idx 99, but
    p99 picks idx 98, so the outlier does NOT pollute the cap."""
    costs = [float(i) for i in range(99)] + [1_000_000.0]
    assert cascade_cost_99pct(costs) == 98.0


def test_cascade_cost_99pct_negative_raises() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        cascade_cost_99pct([1.0, -0.5, 2.0])


def test_cascade_cost_99pct_zero_population_allowed() -> None:
    assert cascade_cost_99pct([0.0, 0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# Q1 invariant — multiplier, not 6th additive
# ---------------------------------------------------------------------------


def test_q1_invariant_score_is_multiplier_times_additive_sum() -> None:
    """A hand-constructed positive-additive case where the additive sum
    is reproducible:

    - kind = preference (β=0, ε cap 0.30) — recency term zeroed.
    - tp = 0.85 (preference)
    - connectedness = 0.40, utility = 0.30, contradiction = 0
    - additive = 0.20*0.85 + 0 + 0.20*0.40 + 0.40*0.30 - 0
              = 0.17 + 0 + 0.08 + 0.12 - 0
              = 0.37
    - score_pre_grav = 0.37 ≥ θ_demote (0.20) → gravity_mult = 1.0
    - final = 0.37
    """
    t_now = datetime(2026, 1, 1, tzinfo=UTC)
    inp = ConsolidateScoreInput(
        kind="preference",
        t_access=t_now,
        connectedness_value=0.40,
        utility_value=0.30,
        contradiction_count=0,
        gravity_value=0.60,  # gravity isn't applied (mult=1) since pre-grav >= theta
    )
    expected_additive = 0.20 * 0.85 + 0.20 * 0.40 + 0.40 * 0.30
    expected_mult = 1.0  # pre-grav >= theta_demote
    expected_final = expected_mult * expected_additive
    assert score_fact(inp, t_now=t_now) == pytest.approx(expected_final, abs=1e-9)


def test_invalidated_collapses_via_gravity_mult() -> None:
    """``gravity_mult(invalidated=True)`` returns 0 — re-asserted at
    the consolidate layer to lock the contract (scoring §6.2)."""
    assert (
        gravity_mult(
            score_pre_grav=0.95,
            gravity_value=0.95,
            theta_demote=0.20,
            invalidated=True,
        )
        == 0.0
    )


# ---------------------------------------------------------------------------
# f_proc-style edge case — gravity floor does not rescue negative additive
# ---------------------------------------------------------------------------


def test_gravity_mult_floor_on_negative_pre_grav_does_not_rescue() -> None:
    """f_proc datapoint (scoring Appendix A §A.1):
    score_pre_grav = -0.453, gravity = 0.5
        → gravity_mult = max(1.0, 1 + 0.5*0.5) = 1.25
        → final = 1.25 * -0.453 ≈ -0.566 (within ±1e-3)

    The floor lifts the multiplier to 1.25 but cannot flip the sign;
    the additive's strong-contradiction negative still wins."""
    score_pre_grav = -0.453
    mult = gravity_mult(
        score_pre_grav=score_pre_grav,
        gravity_value=0.5,
        theta_demote=0.20,
    )
    assert mult == pytest.approx(1.25, abs=1e-9)
    final = mult * score_pre_grav
    assert final == pytest.approx(-0.566, abs=1e-3)
    assert final < 0.0


def test_normalize_gravity_clip_to_unit_interval() -> None:
    """Re-export smoke (math owned by P3 lib): cascade_cost / 99pct
    clipped to ``[0, 1]``."""
    assert normalize_gravity(cascade_cost=0.0, cascade_cost_99pct=10.0) == 0.0
    assert normalize_gravity(cascade_cost=5.0, cascade_cost_99pct=10.0) == 0.5
    assert normalize_gravity(cascade_cost=15.0, cascade_cost_99pct=10.0) == 1.0
    # Zero-population safety: no 99pct yet → 0.
    assert normalize_gravity(cascade_cost=5.0, cascade_cost_99pct=0.0) == 0.0
