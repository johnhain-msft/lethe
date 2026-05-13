"""Utility term — gap-02 §3 weighted aggregate over the recall ledger.

```
utility(f) = Sum_e   w_event(e.kind) * exp( -(t_now - e.t) / tau_u )
                          for e in ledger(f) ∩ [t_now - tau_u, t_now]
```

with per-event weights from gap-02 §3 (see :data:`EVENT_WEIGHTS`).

Output is **clipped + min-max normalized to [0, 1]** at the per-tenant
95th percentile of the ledger window (scoring §3.3). Callers compute the
p95 normalizer once per (tenant, scoring pass) and pass it in; pre-norm
output is also returned for diagnostics.

Frozen on invalidate per scoring §6.4 — the caller is responsible for
not invoking utility() on an invalidated fact (or for passing an empty
ledger window when it does).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

# gap-02 §3 per-event weights.
EventKind = Literal[
    "citation",
    "tool_success",
    "correction",
    "repeat_recall",
    "no_op",
]

EVENT_WEIGHTS: Final[Mapping[EventKind, float]] = {
    "citation": 0.4,
    "tool_success": 0.7,
    "correction": 1.0,
    "repeat_recall": 0.1,
    "no_op": -0.2,
}

DEFAULT_TAU_DAYS: Final[float] = 30.0  # scoring §3.3
_SECONDS_PER_DAY: Final[float] = 86_400.0


@dataclass(frozen=True)
class LedgerEvent:
    """One row of the gap-02 §3 utility ledger."""

    kind: EventKind
    t: datetime


def utility_raw(
    *,
    t_now: datetime,
    ledger_events: Iterable[LedgerEvent],
    tau_days: float = DEFAULT_TAU_DAYS,
) -> float:
    """Compute the un-normalized utility sum (scoring §3.3).

    Events outside ``[t_now - tau_days, t_now]`` contribute zero
    (exponential decay drives them effectively to 0 anyway, but we
    excise them explicitly so the per-tenant p95 normalizer isn't
    dominated by ancient noise).
    """
    if t_now.tzinfo is None:
        raise ValueError("utility_raw: t_now must be timezone-aware")
    if tau_days <= 0:
        raise ValueError(f"utility_raw: tau_days must be positive, got {tau_days!r}")

    window_seconds = tau_days * _SECONDS_PER_DAY
    total = 0.0
    for event in ledger_events:
        if event.t.tzinfo is None:
            raise ValueError("utility_raw: ledger event timestamps must be timezone-aware")
        delta_seconds = (t_now - event.t).total_seconds()
        if delta_seconds < 0.0 or delta_seconds > window_seconds:
            continue
        delta_days = delta_seconds / _SECONDS_PER_DAY
        weight = EVENT_WEIGHTS.get(event.kind)
        if weight is None:
            raise ValueError(
                f"utility_raw: unknown event kind {event.kind!r}; expected one of "
                f"{sorted(EVENT_WEIGHTS)}"
            )
        total += weight * math.exp(-delta_days / tau_days)
    return total


def utility(
    *,
    t_now: datetime,
    ledger_events: Iterable[LedgerEvent],
    p95_normalizer: float,
    tau_days: float = DEFAULT_TAU_DAYS,
) -> float:
    """Composed entry: clip + min-max normalize the §3.3 raw sum to ``[0, 1]``.

    ``p95_normalizer`` is the per-tenant 95th-percentile of the ledger
    window (scoring §3.3). A non-positive normalizer collapses the term
    to ``0`` (no per-tenant data to scale against → can't claim utility
    signal). Pre-norm negatives (caused by a window dominated by
    ``no_op`` events) clip to ``0``.
    """
    raw = utility_raw(t_now=t_now, ledger_events=ledger_events, tau_days=tau_days)
    if p95_normalizer <= 0.0:
        return 0.0
    clipped = max(0.0, raw)
    normalized = clipped / p95_normalizer
    return min(1.0, normalized)
