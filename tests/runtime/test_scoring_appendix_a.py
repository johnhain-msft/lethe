"""Replay docs/05-scoring-design.md Appendix A worked example.

Numerical targets per plan §c.94 (tolerance ±1e-3):
    - score(f_pref)  =  0.522   (consolidate-time)
    - score(f_fact)  =  0.397
    - score(f_proc)  = -0.566   (gravity-floor edge — plan §i.227)
    - ε_eff(count=1) =  0.847
    - rrf  =  0.0489 / 0.0479 / 0.0454
    - rerank =  0.0556 / 0.0498 / 0.0454

Closes residual-unknown #6 (scoring §A.1:553) — procedure adopts the
feedback tier (type_priority=0.55). See per_class.py:TYPE_PRIORITY for
the table entry. gap-15 may re-tune at P5+.

A.2 rerank assertions are a forward spec: w_intent / intent_match /
classifier_conf / w_utility are NOT wired into recall() at P4 per plan
§g.192 (QA-P3 §F.3 carry-forward → P5+). The inline private helper
``_appendix_a_rerank()`` documents the closed-form formula for QA-P4
inspection; recall() today sorts by the consolidate-time composed score.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lethe.runtime.consolidate.score import (
    ConsolidateScoreInput,
    score_fact,
)
from lethe.runtime.retrievers import Hit
from lethe.runtime.retrievers.rrf import rrf_combine
from lethe.runtime.scoring.contradiction import eps_effective
from lethe.runtime.scoring.per_class import TYPE_PRIORITY, type_priority

# ---------------------------------------------------------------------------
# Appendix A setup (docs/05-scoring-design.md §A:522-528)
# ---------------------------------------------------------------------------

# Doc states t_now = 2025-12-01T12:00Z. Doc-cited deltas (11d / 26d / 61d)
# are integer-day. We align t_access to t_now's time-of-day so the
# elapsed-days math matches the doc exactly (per_class.score → recency()
# converts (t_now - t_access) seconds → days).
T_NOW = datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC)
T_ACCESS_PREF = datetime(2025, 11, 20, 12, 0, 0, tzinfo=UTC)  # 11d
T_ACCESS_FACT = datetime(2025, 11, 5, 12, 0, 0, tzinfo=UTC)  # 26d
T_ACCESS_PROC = datetime(2025, 10, 1, 12, 0, 0, tzinfo=UTC)  # 61d

# Per-fact pre-computed inputs (doc §A.1).
_PREF_INPUT = ConsolidateScoreInput(
    kind="preference",
    t_access=T_ACCESS_PREF,
    connectedness_value=0.40,
    utility_value=0.68,
    contradiction_count=0,
    gravity_value=0.6,
)
_FACT_INPUT = ConsolidateScoreInput(
    kind="user_fact",
    t_access=T_ACCESS_FACT,
    connectedness_value=0.35,
    utility_value=0.13,
    contradiction_count=0,
    gravity_value=0.2,
)
_PROC_INPUT = ConsolidateScoreInput(
    kind="procedure",
    t_access=T_ACCESS_PROC,
    connectedness_value=0.30,
    utility_value=0.013,
    contradiction_count=1,
    gravity_value=0.5,
)

# RRF ranks per doc §A.2:568-572 (one row per fact across sem/lex/graph).
_RANKS_SEM: dict[str, int] = {"f_pref": 1, "f_fact": 3, "f_proc": 5}
_RANKS_LEX: dict[str, int] = {"f_pref": 1, "f_fact": 4, "f_proc": 8}
_RANKS_GRAPH: dict[str, int] = {"f_pref": 2, "f_fact": 1, "f_proc": 5}

# Doc §A.2:528,574 — intent = update_preference, classifier_conf = 0.92.
# intent_match row from scoring §4.3:206 (update_preference column).
_INTENT_MATCH: dict[str, float] = {"f_pref": 1.0, "f_fact": 0.3, "f_proc": 0.0}
_CLASSIFIER_CONF = 0.92
_W_INTENT = 0.15  # gap-03 §5 / scoring §4.3
_W_UTILITY = 0.0  # doc §A.2:581 — N_ledger=0 for v1.0 strict stratum


def _appendix_a_rerank(
    *,
    rrf: float,
    intent_match: float,
    classifier_conf: float,
    w_intent: float = _W_INTENT,
    w_utility: float = _W_UTILITY,
    utility_prior: float = 0.0,
) -> float:
    """Closed-form rerank score from docs/05-scoring-design.md §4 + §A.2.

    Forward-spec helper — w_intent / intent_match / classifier_conf /
    w_utility are NOT wired into :func:`lethe.api.recall.recall` at P4
    per plan §g.192 (deferred to P5+). Lives here as a test-local
    reference so QA-P4 can inspect the closed-form formula. When recall
    wires the bonus in (P5+), this helper should be deleted in favor of
    the production path and T6 / T6b reattached there.

        rerank = rrf · (1 + w_intent · intent_match · classifier_conf)
                     + w_utility · utility_prior
    """
    bonus = 1.0 + w_intent * intent_match * classifier_conf
    return rrf * bonus + w_utility * utility_prior


def _build_ranked_lists() -> list[list[Hit]]:
    """Construct per-retriever ranked Hit lists matching doc §A.2:568-572."""

    # Order each list by ascending rank (so list index lines up with rank).
    def _ranked(source: str, ranks: dict[str, int]) -> list[Hit]:
        return [
            Hit(fact_id=fid, score=0.0, source=source, rank=rk)  # type: ignore[arg-type]
            for fid, rk in sorted(ranks.items(), key=lambda kv: kv[1])
        ]

    return [
        _ranked("semantic", _RANKS_SEM),
        _ranked("lexical", _RANKS_LEX),
        _ranked("graph", _RANKS_GRAPH),
    ]


# ---------------------------------------------------------------------------
# T1 — score(f_pref) = 0.522 (consolidate-time, β=0, gravity_mult=1.0)
# ---------------------------------------------------------------------------


def test_appendix_a_score_f_pref_matches_doc() -> None:
    """f_pref: preference shape, β=0, pre_grav ≥ θ_demote → gravity_mult=1.0.

    Pre-grav = 0.2·0.85 + 0 + 0.2·0.40 + 0.4·0.68 - 0 = 0.522 (exact).
    Doc target: 0.522 (docs/05-scoring-design.md §A.1:538-540).
    """
    s = score_fact(_PREF_INPUT, t_now=T_NOW)
    assert s == pytest.approx(0.522, abs=1e-3)


# ---------------------------------------------------------------------------
# T2 — score(f_fact) = 0.397 (consolidate-time, episodic, gravity_mult=1.0)
# ---------------------------------------------------------------------------


def test_appendix_a_score_f_fact_matches_doc() -> None:
    """f_fact: episodic shape, β=0.3 active, pre_grav ≥ θ_demote → mult=1.0.

    Doc target: 0.397 (docs/05-scoring-design.md §A.1:548-550).
    Drift from doc rounding (rec≈0.45) is ~2e-4 — well inside ±1e-3.
    """
    s = score_fact(_FACT_INPUT, t_now=T_NOW)
    assert s == pytest.approx(0.397, abs=1e-3)


# ---------------------------------------------------------------------------
# T3 — score(f_proc) = -0.566 (gravity-floor edge case, plan §i.227)
# ---------------------------------------------------------------------------


def test_appendix_a_score_f_proc_matches_doc_with_gravity_lift() -> None:
    """f_proc: procedure shape (P4 C9 type_priority=0.55), strong contradiction.

    Pre-grav goes negative (-0.453). gravity_mult = max(1.0, 1+0.5·0.5) =
    1.25 (lift, since pre_grav < θ_demote). Final score = 1.25·-0.453 =
    -0.566 (docs/05-scoring-design.md §A.1:558-560).

    This is the §i.227 gravity-floor edge case: the floor is a MULTIPLIER,
    so when the additive sub-score is negative the lift drives the score
    MORE negative (not less). The fact still demotes; gap-13
    contradiction-resolution then dominates.

    Sub-asserts isolate the multiplier vs the additive so a regression
    in either narrows quickly.
    """
    s = score_fact(_PROC_INPUT, t_now=T_NOW)
    assert s == pytest.approx(-0.566, abs=1e-3)

    # Sub-assert (multiplier is the lift, not 1.0): re-score with
    # gravity_value=0.0 to defeat the floor → pre_grav unchanged but
    # mult collapses to max(1.0, 1+0)=1.0. The ratio s / s_no_grav must
    # then equal the analytic 1.25 lift.
    no_grav = ConsolidateScoreInput(
        kind=_PROC_INPUT.kind,
        t_access=_PROC_INPUT.t_access,
        connectedness_value=_PROC_INPUT.connectedness_value,
        utility_value=_PROC_INPUT.utility_value,
        contradiction_count=_PROC_INPUT.contradiction_count,
        gravity_value=0.0,
    )
    s_no_grav = score_fact(no_grav, t_now=T_NOW)
    assert s_no_grav == pytest.approx(-0.453, abs=1e-3)
    assert s / s_no_grav == pytest.approx(1.25, abs=1e-6)


# ---------------------------------------------------------------------------
# T4 — ε_eff(count=1) = 0.847 (mid-formula sanity)
# ---------------------------------------------------------------------------


def test_appendix_a_eps_effective_count_1_matches_doc() -> None:
    """eps_eff(count=1) = 0.50 · (1 + ln 2) = 0.847.

    Doc target: 0.847 (docs/05-scoring-design.md §A.1:557).
    Isolates the contradiction-dampening intermediate.
    """
    eff = eps_effective(eps=0.50, contradiction_count=1)
    assert eff == pytest.approx(0.847, abs=1e-3)


# ---------------------------------------------------------------------------
# T5 — RRF values match doc §A.2 table
# ---------------------------------------------------------------------------


def test_appendix_a_rrf_matches_doc() -> None:
    """RRF combine over sem/lex/graph with k=60.

    Doc targets (docs/05-scoring-design.md §A.2:568-572):
      f_pref = 0.0489, f_fact = 0.0479, f_proc = 0.0454.

    Uses production :func:`rrf_combine` (not a re-implementation) so
    the assertion locks the live formula, not a duplicate.
    """
    fused = rrf_combine(ranked_lists=_build_ranked_lists())
    scores = {hit.fact_id: hit.score for hit in fused}
    assert scores["f_pref"] == pytest.approx(0.0489, abs=1e-3)
    assert scores["f_fact"] == pytest.approx(0.0479, abs=1e-3)
    assert scores["f_proc"] == pytest.approx(0.0454, abs=1e-3)


# ---------------------------------------------------------------------------
# T6 — rerank values match doc §A.2:584-586 (forward spec via test helper)
# ---------------------------------------------------------------------------


def test_appendix_a_rerank_matches_doc() -> None:
    """Final rerank = rrf · (1 + w_intent·intent_match·classifier_conf).

    Doc targets (docs/05-scoring-design.md §A.2:584-586):
      f_pref = 0.0556, f_fact = 0.0498, f_proc = 0.0454.

    Forward-spec: this multiplicative bonus is NOT wired into recall()
    at P4 (plan §g.192); helper :func:`_appendix_a_rerank` documents
    the closed form for QA-P4 inspection.
    """
    fused = rrf_combine(ranked_lists=_build_ranked_lists())
    rerank = {
        hit.fact_id: _appendix_a_rerank(
            rrf=hit.score,
            intent_match=_INTENT_MATCH[hit.fact_id],
            classifier_conf=_CLASSIFIER_CONF,
        )
        for hit in fused
    }
    assert rerank["f_pref"] == pytest.approx(0.0556, abs=1e-3)
    assert rerank["f_fact"] == pytest.approx(0.0498, abs=1e-3)
    assert rerank["f_proc"] == pytest.approx(0.0454, abs=1e-3)


# ---------------------------------------------------------------------------
# T6b — rerank multiplicative bonus factor (A2 sub-assertions)
# ---------------------------------------------------------------------------


def test_appendix_a_rerank_bonus_factor_matches_doc() -> None:
    """Lock the multiplicative bonus formula `1 + w_intent · im · cc`.

    Doc targets (docs/05-scoring-design.md §A.2:576-579):
      f_pref bonus = 1.138, f_fact bonus = 1.041, f_proc bonus = 1.000.

    Defends against drift if P5+ refactors the bonus expression — by
    passing rrf=1.0 the helper output equals the bonus alone, so this
    test isolates the bonus from the RRF multiplication tested in T6.
    """
    assert _appendix_a_rerank(
        rrf=1.0, intent_match=1.0, classifier_conf=_CLASSIFIER_CONF
    ) == pytest.approx(1.138, abs=1e-3)
    assert _appendix_a_rerank(
        rrf=1.0, intent_match=0.3, classifier_conf=_CLASSIFIER_CONF
    ) == pytest.approx(1.041, abs=1e-3)
    assert _appendix_a_rerank(
        rrf=1.0, intent_match=0.0, classifier_conf=_CLASSIFIER_CONF
    ) == pytest.approx(1.000, abs=1e-3)


# ---------------------------------------------------------------------------
# T7 — Top-1 ordering: f_pref wins despite f_fact's graph-rank-1 hit
# ---------------------------------------------------------------------------


def test_appendix_a_top_1_is_f_pref_after_rerank() -> None:
    """The MAGMA intent-bonus lifts f_pref above f_fact.

    Doc §A.2:589: "Top-1 is `f_pref`. The intent multiplicative bonus
    correctly lifts the preference above the user_fact despite the
    user_fact having a graph-rank-1 hit."
    """
    fused = rrf_combine(ranked_lists=_build_ranked_lists())
    ordered = sorted(
        fused,
        key=lambda h: _appendix_a_rerank(
            rrf=h.score,
            intent_match=_INTENT_MATCH[h.fact_id],
            classifier_conf=_CLASSIFIER_CONF,
        ),
        reverse=True,
    )
    assert [h.fact_id for h in ordered] == ["f_pref", "f_fact", "f_proc"]


# ---------------------------------------------------------------------------
# T8 — type_priority("procedure") == 0.55 (res-unknown #6 closure)
# ---------------------------------------------------------------------------


def test_appendix_a_procedure_type_priority_is_feedback_tier() -> None:
    """Closes residual-unknown #6 (scoring §A.1:553 + §10:495).

    Companion to T3: T3 verifies the composed score lands at -0.566;
    T8 isolates the table-entry change that makes that target reachable.
    Without ``"procedure": 0.55`` in TYPE_PRIORITY, type_priority() would
    fall back to DEFAULT_TYPE_PRIORITY (0.30) and f_proc would compute
    ≈-0.629 — outside the ±1e-3 budget.
    """
    assert TYPE_PRIORITY["procedure"] == 0.55
    assert type_priority("procedure") == 0.55
