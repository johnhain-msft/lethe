"""Per-class scoring tests (scoring §5 dispatch — D1 covers all four shapes).

Verifies:

- Each of the four persistent shapes (episodic_fact, preference,
  procedure, narrative) uses its declared §5 formula.
- Type-priority lookup matches the §3.4 table.
- Per-class beta override: preference + narrative zero out the recency
  term; episodic_fact + procedure use the default beta.
- Per-class eps cap: preference uses 0.30; the rest use 0.50; the cap
  applies regardless of the supplied weights.eps.
- Per-class tau_r: episodic_fact = 30 d, procedure = 180 d (asserted via
  decay-rate comparison since recency is composed inside score()).
- Non-persistent classes raise NonPersistentClass.
- Unknown kinds raise UnknownClass.
- Gravity demotion-floor lift: a low pre-grav score below theta_demote
  is multiplied by ``max(1, 1 + g_floor*g)``; an invalidated fact
  collapses to 0.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from lethe.runtime.scoring.contradiction import eps_effective
from lethe.runtime.scoring.per_class import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    TYPE_PRIORITY,
    NonPersistentClass,
    UnknownClass,
    WeightTuple,
    score,
    shape_for_kind,
    type_priority,
)
from lethe.runtime.scoring.recency import recency

NOW = datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# shape_for_kind taxonomy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("user_fact", "episodic_fact"),
        ("project_fact", "episodic_fact"),
        ("feedback", "episodic_fact"),
        ("reference", "episodic_fact"),
        ("preference", "preference"),
        ("prohibition", "preference"),
        ("procedure", "procedure"),
        ("narrative", "narrative"),
    ],
)
def test_shape_for_kind_persistent(kind: str, expected: str) -> None:
    assert shape_for_kind(kind) == expected


@pytest.mark.parametrize("kind", ["reply_only", "peer_route", "drop", "escalate"])
def test_shape_for_kind_non_persistent_raises(kind: str) -> None:
    with pytest.raises(NonPersistentClass):
        shape_for_kind(kind)


def test_shape_for_kind_unknown_raises() -> None:
    with pytest.raises(UnknownClass):
        shape_for_kind("not_a_real_kind")


# ---------------------------------------------------------------------------
# Type priority (§3.4 table)
# ---------------------------------------------------------------------------


def test_type_priority_table_matches_spec() -> None:
    assert TYPE_PRIORITY == {
        "prohibition": 1.00,
        "preference": 0.85,
        "user_fact": 0.70,
        "feedback": 0.55,
        # P4 C9 closure of residual-unknown #6 (scoring §A.1:553 + §10:495):
        # procedure adopts the feedback tier in v1.
        "procedure": 0.55,
        "narrative": 0.50,
        "project_fact": 0.40,
        "reference": 0.25,
    }


def test_type_priority_unknown_kind_falls_back_to_default() -> None:
    # Default is 0.30 — the "unclassified episodic" row of the §3.4 table.
    assert type_priority("never_heard_of_it") == 0.30


# ---------------------------------------------------------------------------
# Episodic fact: full §3 formula, beta=0.30, eps cap 0.50, tau_r=30 d
# ---------------------------------------------------------------------------


def test_episodic_fact_uses_full_additive_tuple() -> None:
    t_access = NOW - timedelta(days=10)
    s = score(
        kind="user_fact",
        t_now=NOW,
        t_access=t_access,
        connectedness_value=0.5,
        utility_value=0.4,
        contradiction_count=0,
        gravity_value=0.0,
    )
    # Hand-compute: alpha*0.70 + 0.30*recency + 0.20*0.5 + 0.40*0.4 - 0
    # recency uses tau=30: r_inf=0.05, decay = exp(-10/30)
    rec = 0.05 + 0.95 * math.exp(-10 / 30)
    expected_pre_grav = 0.2 * 0.70 + 0.30 * rec + 0.20 * 0.5 + 0.40 * 0.4
    # No demotion lift (gravity_value=0 → mult = max(1, 1) = 1 below theta).
    assert s == pytest.approx(expected_pre_grav, rel=1e-9)


def test_episodic_fact_eps_cap_is_050() -> None:
    # Force a contradiction so eps participates; verify eps_used = min(weights.eps, 0.50)
    # by passing a weights.eps above the cap and below.
    t_access = NOW - timedelta(days=1)

    # weights.eps = 0.9 → effective eps capped to 0.50
    high_eps = WeightTuple(eps=0.9)
    s_capped = score(
        kind="user_fact",
        t_now=NOW,
        t_access=t_access,
        connectedness_value=0.0,
        utility_value=0.0,
        contradiction_count=2,
        gravity_value=0.0,
        weights=high_eps,
    )
    rec = 0.05 + 0.95 * math.exp(-1 / 30)
    expected_eps_eff = eps_effective(eps=0.50, contradiction_count=2)
    expected = 0.2 * 0.70 + 0.30 * rec + 0.20 * 0.0 + 0.40 * 0.0 - expected_eps_eff * 1.0
    assert s_capped == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Preference: beta=0 (recency dropped), eps cap 0.30
# ---------------------------------------------------------------------------


def test_preference_zeroes_recency_term() -> None:
    t_recent = NOW - timedelta(days=1)
    t_ancient = NOW - timedelta(days=10_000)
    # Both should give the same score because recency is multiplied by beta=0.
    s_recent = score(
        kind="preference",
        t_now=NOW,
        t_access=t_recent,
        connectedness_value=0.3,
        utility_value=0.2,
        contradiction_count=0,
        gravity_value=0.0,
    )
    s_ancient = score(
        kind="preference",
        t_now=NOW,
        t_access=t_ancient,
        connectedness_value=0.3,
        utility_value=0.2,
        contradiction_count=0,
        gravity_value=0.0,
    )
    assert s_recent == pytest.approx(s_ancient, rel=1e-12)
    # And the value should be alpha*0.85 + 0 + gamma*0.3 + delta*0.2
    expected = 0.2 * 0.85 + 0.20 * 0.3 + 0.40 * 0.2
    assert s_recent == pytest.approx(expected, rel=1e-9)


def test_preference_eps_cap_is_030() -> None:
    # weights.eps = 0.9 → effective eps capped to 0.30
    high_eps = WeightTuple(eps=0.9)
    s = score(
        kind="preference",
        t_now=NOW,
        t_access=NOW,
        connectedness_value=0.0,
        utility_value=0.0,
        contradiction_count=1,
        gravity_value=0.0,
        weights=high_eps,
    )
    expected_eps_eff = eps_effective(eps=0.30, contradiction_count=1)
    expected = 0.2 * 0.85 + 0 + 0 + 0 - expected_eps_eff * 1.0
    assert s == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Procedure: tau_r=180 d (slower decay than episodic)
# ---------------------------------------------------------------------------


def test_procedure_uses_180_day_tau_r() -> None:
    t_access = NOW - timedelta(days=60)

    # Procedure recency at delta=60d, tau=180d
    proc_rec = recency(t_now=NOW, t_access=t_access, tau_days=180.0)
    # Episodic recency at delta=60d, tau=30d would be much smaller
    epi_rec = recency(t_now=NOW, t_access=t_access, tau_days=30.0)
    assert proc_rec > epi_rec  # slower decay

    # P4 C9: type_priority for "procedure" is the feedback tier (0.55).
    # Closes residual-unknown #6 (scoring §A.1:553 + §10:495); gap-15 may
    # re-tune at P5+. Note: previously fell back to DEFAULT_TYPE_PRIORITY
    # (0.30) — the +0.05 lift flows through alpha=0.2 here.
    s = score(
        kind="procedure",
        t_now=NOW,
        t_access=t_access,
        connectedness_value=0.0,
        utility_value=0.0,
        contradiction_count=0,
        gravity_value=0.0,
    )
    expected = 0.2 * 0.55 + 0.30 * proc_rec
    assert s == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Narrative: beta=0, type_priority 0.50
# ---------------------------------------------------------------------------


def test_narrative_zeroes_recency_and_uses_priority_050() -> None:
    s = score(
        kind="narrative",
        t_now=NOW,
        t_access=NOW - timedelta(days=999),  # ignored since beta=0
        connectedness_value=0.4,
        utility_value=0.1,
        contradiction_count=0,
        gravity_value=0.0,
    )
    expected = 0.2 * 0.50 + 0 + 0.20 * 0.4 + 0.40 * 0.1
    assert s == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Gravity multiplier (§3.6 demotion-floor lift)
# ---------------------------------------------------------------------------


def test_gravity_lift_applies_below_theta_demote() -> None:
    # Construct a scenario whose pre-grav score is below DEFAULT_THETA_DEMOTE
    # but whose gravity_value=1.0 lifts it via mult = max(1, 1 + 0.5*1.0) = 1.5.
    t_access = NOW - timedelta(days=365)  # ancient → low recency
    s_ungrav = score(
        kind="user_fact",
        t_now=NOW,
        t_access=t_access,
        connectedness_value=0.0,
        utility_value=0.0,
        contradiction_count=0,
        gravity_value=0.0,
    )
    s_grav = score(
        kind="user_fact",
        t_now=NOW,
        t_access=t_access,
        connectedness_value=0.0,
        utility_value=0.0,
        contradiction_count=0,
        gravity_value=1.0,
    )
    # Sanity: pre-grav below threshold so the lift does fire.
    assert s_ungrav < DEFAULT_THETA_DEMOTE
    assert s_grav == pytest.approx(1.5 * s_ungrav, rel=1e-9)


def test_invalidated_fact_collapses_to_zero() -> None:
    s = score(
        kind="user_fact",
        t_now=NOW,
        t_access=NOW,
        connectedness_value=0.5,
        utility_value=0.5,
        contradiction_count=0,
        gravity_value=1.0,
        invalidated=True,
    )
    assert s == 0.0


# ---------------------------------------------------------------------------
# Score input-validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_score_rejects_out_of_range_connectedness(bad: float) -> None:
    with pytest.raises(ValueError, match="connectedness_value"):
        score(
            kind="user_fact",
            t_now=NOW,
            t_access=NOW,
            connectedness_value=bad,
            utility_value=0.0,
            contradiction_count=0,
            gravity_value=0.0,
        )


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_score_rejects_out_of_range_utility(bad: float) -> None:
    with pytest.raises(ValueError, match="utility_value"):
        score(
            kind="user_fact",
            t_now=NOW,
            t_access=NOW,
            connectedness_value=0.0,
            utility_value=bad,
            contradiction_count=0,
            gravity_value=0.0,
        )


def test_score_rejects_non_persistent_kind() -> None:
    with pytest.raises(NonPersistentClass):
        score(
            kind="reply_only",
            t_now=NOW,
            t_access=NOW,
            connectedness_value=0.0,
            utility_value=0.0,
            contradiction_count=0,
            gravity_value=0.0,
        )


# ---------------------------------------------------------------------------
# Default weight tuple matches gap-03 §5 candidate (a)
# ---------------------------------------------------------------------------


def test_default_weights_match_gap03_candidate_a() -> None:
    assert WeightTuple(alpha=0.2, beta=0.3, gamma=0.2, delta=0.4, eps=0.5) == DEFAULT_WEIGHTS
