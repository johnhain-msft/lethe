"""Gravity multiplier — MaM demotion-floor guard (scoring §3.6; Q1).

```
gravity(f)      = clip( cascade_cost(f) / cascade_cost_99pct , 0, 1 )
gravity_mult(f) = 1.0                                  if score_pre_grav >= theta_demote
                = max( 1.0, 1 + g_floor * gravity(f) ) if score_pre_grav <  theta_demote
```

Q1 resolution (scoring §3.6): gravity is a **demotion-floor multiplier**,
NOT a sixth additive term. This keeps the additive tuple
``(alpha, beta, gamma, delta, epsilon)`` closed (gap-03 stable) while
still expressing MaM intent (lit-review §04).

Invalidated facts: ``gravity_mult = 0`` per scoring §6.2 — they cannot
resist demotion regardless of cascade cost.

``g_floor = 0.5`` default — a fully-gravity-bound fact gets a 50 % lift
above the demote floor, sufficient to cross ``theta_demote`` from any
plausible pre-grav score in ``[0, 1]``.
"""

from __future__ import annotations

from typing import Final

DEFAULT_G_FLOOR: Final[float] = 0.5


def gravity(*, cascade_cost: float, cascade_cost_99pct: float) -> float:
    """Clip ``cascade_cost / cascade_cost_99pct`` into ``[0, 1]``.

    A non-positive ``cascade_cost_99pct`` (no per-tenant cascade data
    yet) collapses gravity to ``0`` — the MaM lift only applies when
    there is enough population to compute a 99th percentile against.
    """
    if cascade_cost < 0.0:
        raise ValueError(f"gravity: cascade_cost must be >= 0, got {cascade_cost!r}")
    if cascade_cost_99pct <= 0.0:
        return 0.0
    raw = cascade_cost / cascade_cost_99pct
    return max(0.0, min(1.0, raw))


def gravity_mult(
    *,
    score_pre_grav: float,
    gravity_value: float,
    theta_demote: float,
    g_floor: float = DEFAULT_G_FLOOR,
    invalidated: bool = False,
) -> float:
    """Compute the §3.6 demotion-floor multiplier.

    Applied to the additive composed sub-score in :mod:`.per_class`.
    """
    if not 0.0 <= gravity_value <= 1.0:
        raise ValueError(
            f"gravity_mult: gravity_value must lie in [0, 1], got {gravity_value!r}"
        )
    if g_floor < 0.0:
        raise ValueError(f"gravity_mult: g_floor must be >= 0, got {g_floor!r}")
    if invalidated:
        return 0.0
    if score_pre_grav >= theta_demote:
        return 1.0
    return max(1.0, 1.0 + g_floor * gravity_value)
