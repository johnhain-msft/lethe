"""Tests for :mod:`lethe.runtime.consolidate.score`.

Coverage map (P4 commit 4 — adapter-only contract):

- Wrapper equality with :func:`lethe.runtime.scoring.per_class.score`
  for each persistent shape (episodic_fact, preference, procedure,
  narrative).
- Per-class ε cap applied exactly once (preference: ``eps_cap = 0.30``).
- ``invalidated=True`` collapses the result to ``0.0``
  (gravity_mult = 0 per scoring §6.2).
- Non-persistent kinds (e.g., ``reply_only``, ``escalate``) raise
  :class:`NonPersistentClass` via the shape-routing in
  :func:`per_class.score`.
- Unknown kinds raise :class:`UnknownClass`.
- Negative pre-gravity case (additive < 0) — gravity floor does NOT
  rescue the score; wrapper returns the same negative number as
  :func:`per_class.score`.
- Default ``weights`` and ``theta_demote`` flow through unchanged from
  :data:`DEFAULT_WEIGHTS` / :data:`DEFAULT_THETA_DEMOTE`.

NOT in scope this commit (lands at C7 / C9):

- consolidate-loop integration (loop.py).
- A/B weight sweep harness (P5).
- Appendix A worked-example integration test (residual #6 means
  ``TYPE_PRIORITY['procedure']`` doesn't yet land at 0.55; that is a
  C9 docs cleanup item, not a C4 wrapper concern).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from lethe.runtime.consolidate.score import (
    DEFAULT_THETA_DEMOTE,
    DEFAULT_WEIGHTS,
    ConsolidateScoreInput,
    WeightTuple,
    score_fact,
)
from lethe.runtime.scoring.per_class import (
    NonPersistentClass,
    UnknownClass,
)
from lethe.runtime.scoring.per_class import score as per_class_score

_T_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_T_RECENT = _T_NOW - timedelta(days=1)
_T_OLD = _T_NOW - timedelta(days=400)


def _input(
    *,
    kind: str,
    t_access: datetime = _T_RECENT,
    connectedness_value: float = 0.40,
    utility_value: float = 0.30,
    contradiction_count: int = 0,
    gravity_value: float = 0.20,
    invalidated: bool = False,
) -> ConsolidateScoreInput:
    return ConsolidateScoreInput(
        kind=kind,
        t_access=t_access,
        connectedness_value=connectedness_value,
        utility_value=utility_value,
        contradiction_count=contradiction_count,
        gravity_value=gravity_value,
        invalidated=invalidated,
    )


# ---------------------------------------------------------------------------
# Wrapper equality with per_class.score
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        "user_fact",
        "project_fact",
        "feedback",
        "reference",
        "preference",
        "prohibition",
        "procedure",
        "narrative",
    ],
)
def test_wrapper_equals_per_class_score_across_persistent_kinds(kind: str) -> None:
    inp = _input(kind=kind)
    assert score_fact(inp, t_now=_T_NOW) == per_class_score(
        kind=kind,
        t_now=_T_NOW,
        t_access=inp.t_access,
        connectedness_value=inp.connectedness_value,
        utility_value=inp.utility_value,
        contradiction_count=inp.contradiction_count,
        gravity_value=inp.gravity_value,
    )


def test_wrapper_threads_weights_and_theta_demote() -> None:
    """Custom weights + custom theta_demote MUST flow through unchanged."""
    custom_weights = WeightTuple(alpha=0.25, beta=0.20, gamma=0.35, delta=0.30, eps=0.40)
    custom_theta = 0.42
    inp = _input(kind="user_fact", contradiction_count=2)
    assert score_fact(
        inp, t_now=_T_NOW, weights=custom_weights, theta_demote=custom_theta
    ) == per_class_score(
        kind="user_fact",
        t_now=_T_NOW,
        t_access=inp.t_access,
        connectedness_value=inp.connectedness_value,
        utility_value=inp.utility_value,
        contradiction_count=inp.contradiction_count,
        gravity_value=inp.gravity_value,
        weights=custom_weights,
        theta_demote=custom_theta,
    )


def test_default_weights_and_theta_demote_match_per_class_defaults() -> None:
    """Re-exports MUST be the SAME object as the per_class.* defaults
    (no shadow-instantiation of a second WeightTuple)."""
    from lethe.runtime.scoring import per_class as scoring_per_class

    assert DEFAULT_WEIGHTS is scoring_per_class.DEFAULT_WEIGHTS
    assert DEFAULT_THETA_DEMOTE == scoring_per_class.DEFAULT_THETA_DEMOTE
    assert WeightTuple is scoring_per_class.WeightTuple


# ---------------------------------------------------------------------------
# Per-class ε cap (preference: 0.30)
# ---------------------------------------------------------------------------


def test_preference_eps_cap_applied_once_via_wrapper() -> None:
    """``preference`` caps ε at 0.30 (vs the gap-03 default 0.50). The
    wrapper MUST NOT double-cap or otherwise rescale the contradiction
    term — verified by equality with :func:`per_class.score`, which
    owns the cap."""
    inp = _input(kind="preference", contradiction_count=3)
    expected = per_class_score(
        kind=inp.kind,
        t_now=_T_NOW,
        t_access=inp.t_access,
        connectedness_value=inp.connectedness_value,
        utility_value=inp.utility_value,
        contradiction_count=inp.contradiction_count,
        gravity_value=inp.gravity_value,
    )
    assert score_fact(inp, t_now=_T_NOW) == expected


# ---------------------------------------------------------------------------
# Invalidated facts collapse to 0.0
# ---------------------------------------------------------------------------


def test_invalidated_fact_returns_zero() -> None:
    """``invalidated=True`` → ``gravity_mult = 0`` per scoring §6.2;
    the wrapper MUST surface a literal ``0.0``."""
    inp = _input(kind="user_fact", invalidated=True, gravity_value=0.95)
    assert score_fact(inp, t_now=_T_NOW) == 0.0


# ---------------------------------------------------------------------------
# Taxonomy errors propagate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["reply_only", "peer_route", "drop", "escalate"])
def test_non_persistent_kinds_raise(kind: str) -> None:
    inp = _input(kind=kind)
    with pytest.raises(NonPersistentClass):
        score_fact(inp, t_now=_T_NOW)


def test_unknown_kind_raises_unknown_class() -> None:
    inp = _input(kind="not_a_real_kind_xyz")
    with pytest.raises(UnknownClass):
        score_fact(inp, t_now=_T_NOW)


# ---------------------------------------------------------------------------
# Negative pre-gravity case — gravity floor does not rescue
# ---------------------------------------------------------------------------


def test_negative_additive_yields_negative_score() -> None:
    """When the additive sub-score is < 0 (heavy contradiction + low
    inputs), the gravity multiplier MAX-floor is still ``>= 1.0``, so
    the final score is ``mult * negative = even more negative``. The
    floor does NOT rescue. (Mirrors the Appendix A f_proc concept; the
    literal numbers depend on the impl ``TYPE_PRIORITY`` table, so we
    just assert sign + wrapper equality here, not the literal -0.566.)
    """
    inp = _input(
        kind="procedure",
        t_access=_T_OLD,
        connectedness_value=0.05,
        utility_value=0.01,
        contradiction_count=3,
        gravity_value=0.5,
    )
    result = score_fact(inp, t_now=_T_NOW)
    assert result < 0.0
    assert result == per_class_score(
        kind=inp.kind,
        t_now=_T_NOW,
        t_access=inp.t_access,
        connectedness_value=inp.connectedness_value,
        utility_value=inp.utility_value,
        contradiction_count=inp.contradiction_count,
        gravity_value=inp.gravity_value,
    )


# ---------------------------------------------------------------------------
# Dataclass shape pins
# ---------------------------------------------------------------------------


def test_input_dataclass_is_frozen() -> None:
    inp = _input(kind="user_fact")
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.kind = "preference"  # type: ignore[misc]


def test_input_invalidated_defaults_false() -> None:
    inp = _input(kind="user_fact")
    assert inp.invalidated is False
