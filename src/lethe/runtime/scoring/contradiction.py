"""Contradiction term — log-dampened ε (scoring §3.5; gap-13 §3.1).

```
contradiction(f)   = 1   if contradiction_count(f) > 0  else  0
eps_eff            = eps * (1 + log(1 + contradiction_count(f)))
```

The additive contribution to the §3 composed score is ``-eps_eff *
contradiction(f)``, i.e. ``-eps_eff`` when contradicted and ``0``
otherwise. Log-dampening prevents one highly-contradicted fact from
dominating the term while still raising the cost of repeat
contradictions. ``contradiction_count`` resets on revalidate (gap-13 §7).

Per-class ``eps`` cap is owned by :mod:`.per_class` (preference: 0.30;
all others: 0.50 — scoring §5.5).
"""

from __future__ import annotations

import math


def contradiction_indicator(contradiction_count: int) -> float:
    """1 if any contradictions are recorded, 0 otherwise (scoring §3.5)."""
    if contradiction_count < 0:
        raise ValueError(
            f"contradiction_indicator: count must be >= 0, got {contradiction_count!r}"
        )
    return 1.0 if contradiction_count > 0 else 0.0


def eps_effective(*, eps: float, contradiction_count: int) -> float:
    """Log-dampened effective epsilon (scoring §3.5; gap-13 §3.1)."""
    if eps < 0.0:
        raise ValueError(f"eps_effective: eps must be >= 0, got {eps!r}")
    if contradiction_count < 0:
        raise ValueError(
            f"eps_effective: count must be >= 0, got {contradiction_count!r}"
        )
    return eps * (1.0 + math.log1p(float(contradiction_count)))
