"""Per-class scoring dispatch (scoring §5).

Composed formula from scoring §3:

```
score(f) = gravity_mult(f) * [ alpha * type_priority(f)
                             + beta  * recency(f)
                             + gamma * connectedness(f)
                             + delta * utility(f)
                             - eps_eff * contradiction(f) ]
```

Per-class overrides (scoring §5.5):

| kind                                                        | tau_r | beta | eps cap |
|-------------------------------------------------------------|-------|------|---------|
| user_fact, project_fact, feedback, reference (episodic_fact)| 30 d  | 0.30 | 0.50    |
| preference, prohibition (preference)                         |  -    | 0.00 | 0.30    |
| procedure                                                    | 180 d | 0.30 | 0.50    |
| narrative                                                    |  -    | 0.00 | 0.50    |

Locked decision D1 (facilitator P3 plan §(g)): all four persistent
shapes implemented at P3 (no partial-coverage seam to P4).

**Non-persistent classes** (`reply_only`, `peer_route`, `drop`,
`escalate`) raise :class:`NonPersistentClass`. Per scoring §5 they
"never produce a stored fact and never reach a scoring surface" — if
:func:`score` is invoked on such a class, that's a caller bug.

Default weight tuple from gap-03 §5: alpha=0.2, beta=0.3, gamma=0.2,
delta=0.4, eps=0.5. Recall-time bonuses ``w_intent`` + ``w_utility``
(scoring §4) apply on top of this composed score in the recall verb;
they are NOT this module's concern.

The connectedness term is supplied **pre-computed** by the caller — the
per-class graph slice (fact-graph vs procedure-seq vs narrative-doc
edges per scoring §5.5) is the retriever's choice, not the scoring
lib's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from lethe.runtime.scoring.contradiction import contradiction_indicator, eps_effective
from lethe.runtime.scoring.gravity import gravity_mult
from lethe.runtime.scoring.recency import DEFAULT_R_INF, recency

# ---------------------------------------------------------------------------
# Class taxonomy + canonicalization (scoring §5; gap-09 §3)
# ---------------------------------------------------------------------------

# Frontmatter `kind` values that map to each persistent shape.
_EPISODIC_FACT_KINDS: Final[frozenset[str]] = frozenset(
    {"user_fact", "project_fact", "feedback", "reference"}
)
_PREFERENCE_KINDS: Final[frozenset[str]] = frozenset({"preference", "prohibition"})
_PROCEDURE_KINDS: Final[frozenset[str]] = frozenset({"procedure"})
_NARRATIVE_KINDS: Final[frozenset[str]] = frozenset({"narrative"})

# Non-persistent classifier outputs (gap-12 §3) — never reach scoring.
_NON_PERSISTENT_CLASSES: Final[frozenset[str]] = frozenset(
    {"reply_only", "peer_route", "drop", "escalate"}
)

PersistentShape = Literal["episodic_fact", "preference", "procedure", "narrative"]


# ---------------------------------------------------------------------------
# Type priority lookup (scoring §3.4)
# ---------------------------------------------------------------------------

TYPE_PRIORITY: Final[dict[str, float]] = {
    "prohibition": 1.00,
    "preference": 0.85,
    "user_fact": 0.70,
    "feedback": 0.55,
    # P4 C9 closure of residual-unknown #6 (scoring §A.1:553 + §10:495):
    # procedure adopts the feedback tier (0.55) — provisional in v1; gap-15
    # may re-tune at P5+ once operator-trace data is available.
    "procedure": 0.55,
    "narrative": 0.50,
    "project_fact": 0.40,
    "reference": 0.25,
}
DEFAULT_TYPE_PRIORITY: Final[float] = 0.30  # unclassified episodic


# ---------------------------------------------------------------------------
# Per-class parameter table (scoring §5.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassParams:
    """Per-class overrides applied on top of the §3 defaults.

    ``tau_r_days`` is ignored when ``beta == 0`` (recency term zeroed
    out anyway — preference + narrative).
    """

    shape: PersistentShape
    tau_r_days: float
    beta_override: float
    eps_cap: float


_PARAMS_BY_SHAPE: Final[dict[PersistentShape, ClassParams]] = {
    "episodic_fact": ClassParams(
        shape="episodic_fact", tau_r_days=30.0, beta_override=0.30, eps_cap=0.50
    ),
    "preference": ClassParams(
        shape="preference", tau_r_days=30.0, beta_override=0.00, eps_cap=0.30
    ),
    "procedure": ClassParams(shape="procedure", tau_r_days=180.0, beta_override=0.30, eps_cap=0.50),
    "narrative": ClassParams(shape="narrative", tau_r_days=30.0, beta_override=0.00, eps_cap=0.50),
}


# ---------------------------------------------------------------------------
# Default weight tuple (gap-03 §5 candidate (a))
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightTuple:
    """Additive-term weights from gap-03 §5 candidate (a) defaults.

    ``beta`` may be overridden by the per-class table (preference and
    narrative use ``beta = 0``); ``eps`` may be CAPPED by the per-class
    table (preference uses ``eps_cap = 0.30``).
    """

    alpha: float = 0.2  # type_priority
    beta: float = 0.3  # recency
    gamma: float = 0.2  # connectedness
    delta: float = 0.4  # utility
    eps: float = 0.5  # contradiction


DEFAULT_WEIGHTS: Final[WeightTuple] = WeightTuple()
DEFAULT_THETA_DEMOTE: Final[float] = 0.20  # demotion threshold (scoring §7)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ScoringError(Exception):
    """Base class for per-class scoring errors."""


class NonPersistentClass(ScoringError):
    """Raised when scoring is invoked on a non-persistent classifier output.

    Per scoring §5 + gap-12 §3: the four classes
    ``{reply_only, peer_route, drop, escalate}`` never produce a stored
    fact and never reach a scoring surface. If they do, the caller has
    routed wrong.
    """


class UnknownClass(ScoringError):
    """Raised when ``kind`` is neither a persistent shape nor a non-persistent class."""


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def shape_for_kind(kind: str) -> PersistentShape:
    """Map a frontmatter ``kind`` (or classifier intent) to its persistent shape.

    Raises :class:`NonPersistentClass` for non-persistent outputs;
    :class:`UnknownClass` for any other unknown string.
    """
    if kind in _EPISODIC_FACT_KINDS:
        return "episodic_fact"
    if kind in _PREFERENCE_KINDS:
        return "preference"
    if kind in _PROCEDURE_KINDS:
        return "procedure"
    if kind in _NARRATIVE_KINDS:
        return "narrative"
    if kind in _NON_PERSISTENT_CLASSES:
        raise NonPersistentClass(
            f"kind {kind!r} is non-persistent (gap-12 §3); never reaches scoring"
        )
    raise UnknownClass(f"kind {kind!r} is not in scoring §5 taxonomy")


def type_priority(kind: str) -> float:
    """Lookup type priority for ``kind`` (scoring §3.4).

    Unknown ``kind`` strings get :data:`DEFAULT_TYPE_PRIORITY` (the
    "unclassified episodic" row of the §3.4 table); callers that want
    strict validation should call :func:`shape_for_kind` first.
    """
    return TYPE_PRIORITY.get(kind, DEFAULT_TYPE_PRIORITY)


def score(
    *,
    kind: str,
    t_now: datetime,
    t_access: datetime,
    connectedness_value: float,
    utility_value: float,
    contradiction_count: int,
    gravity_value: float,
    weights: WeightTuple = DEFAULT_WEIGHTS,
    theta_demote: float = DEFAULT_THETA_DEMOTE,
    invalidated: bool = False,
    r_inf: float = DEFAULT_R_INF,
) -> float:
    """Compose the per-class score (scoring §5).

    ``connectedness_value`` and ``utility_value`` are precomputed by the
    caller (the retriever owns which graph slice + ledger window apply
    per scoring §5.5).

    Raises :class:`NonPersistentClass` / :class:`UnknownClass` via
    :func:`shape_for_kind` if ``kind`` is out of taxonomy.
    """
    shape = shape_for_kind(kind)
    params = _PARAMS_BY_SHAPE[shape]

    if not 0.0 <= connectedness_value <= 1.0:
        raise ValueError(
            f"score: connectedness_value must lie in [0, 1], got {connectedness_value!r}"
        )
    if not 0.0 <= utility_value <= 1.0:
        raise ValueError(f"score: utility_value must lie in [0, 1], got {utility_value!r}")

    tp = type_priority(kind)

    # Per-class beta override (preference + narrative use beta=0).
    beta_used = params.beta_override
    rec = (
        recency(t_now=t_now, t_access=t_access, tau_days=params.tau_r_days, r_inf=r_inf)
        if beta_used > 0.0
        else 0.0
    )

    # Per-class eps cap.
    eps_used = min(weights.eps, params.eps_cap)
    eps_eff = eps_effective(eps=eps_used, contradiction_count=contradiction_count)
    contr = contradiction_indicator(contradiction_count)

    additive = (
        weights.alpha * tp
        + beta_used * rec
        + weights.gamma * connectedness_value
        + weights.delta * utility_value
        - eps_eff * contr
    )

    mult = gravity_mult(
        score_pre_grav=additive,
        gravity_value=gravity_value,
        theta_demote=theta_demote,
        invalidated=invalidated,
    )
    return mult * additive
