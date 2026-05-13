"""Recency term — Cognitive Weave decay (scoring §3.1).

```
recency(f) = r_inf + (1 - r_inf) * exp( -max(0, t_now - t_access) / tau_r )
```

- `t_access` is **last access** (gap-03 §7 bet — preferences stay live as long
  as cited; cold storage decays faster). Caller is responsible for sourcing
  the right timestamp.
- `r_inf = 0.05` baseline prevents true zero (a single recall can revive).
- `tau_r = 30 d` for episodic facts; per-class overrides in scoring §5
  (procedure: 180 d; preference + narrative: not applied at all because
  ``beta = 0`` zeroes the term — see :mod:`.per_class`).
- Output range: ``[r_inf, 1.0]``; native normalizer.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Final

DEFAULT_R_INF: Final[float] = 0.05
DEFAULT_TAU_DAYS: Final[float] = 30.0

_SECONDS_PER_DAY: Final[float] = 86_400.0


def recency(
    *,
    t_now: datetime,
    t_access: datetime,
    tau_days: float = DEFAULT_TAU_DAYS,
    r_inf: float = DEFAULT_R_INF,
) -> float:
    """Compute the Cognitive Weave recency term.

    Both timestamps must be timezone-aware (UTC); naive datetimes raise.
    """
    if t_now.tzinfo is None or t_access.tzinfo is None:
        raise ValueError("recency: t_now and t_access must be timezone-aware")
    if tau_days <= 0:
        raise ValueError(f"recency: tau_days must be positive, got {tau_days!r}")
    if not 0.0 <= r_inf <= 1.0:
        raise ValueError(f"recency: r_inf must lie in [0, 1], got {r_inf!r}")

    delta_seconds = (t_now - t_access).total_seconds()
    delta_days = max(0.0, delta_seconds / _SECONDS_PER_DAY)
    decay = math.exp(-delta_days / tau_days)
    return r_inf + (1.0 - r_inf) * decay
