"""Active-contradiction count adapter for consolidate-time scoring.

Pure count adapter over a caller-pre-filtered contradicting-edges
mapping. The graph traversal that materializes contradictions (gap-13
§3 — gap-13 §3 supersession check, revalidate-on-evidence path) lives
in ``runtime/consolidate/invalidate.py`` (P4 commit 6); this module is
the C4 pure-function surface that the score phase consumes.

Re-exports :func:`contradiction_indicator` and :func:`eps_effective`
from :mod:`lethe.runtime.scoring.contradiction` so consolidate-side
callers (C7 loop) don't have to dual-import. The log-dampened ε
formula (scoring §3.5; gap-13 §3.1) is NOT re-implemented here —
defining it twice is exactly what the audit gate at C4 close rejects.

Critical invariant (gap-13 §3.1; surfaced in module tests):
``eps_effective(eps=0.5, contradiction_count=0) == 0.5`` — NOT ``0``.
The penalty is the product ``eps_eff * contradiction_indicator``, and
``contradiction_indicator(0) == 0``; the indicator (not the dampener)
zeros the contradiction term.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from lethe.runtime.scoring.contradiction import contradiction_indicator, eps_effective

__all__ = [
    "contradiction_indicator",
    "count_active_contradictions",
    "eps_effective",
]


def count_active_contradictions(
    *,
    fact_id: str,
    contradicting_edges: Mapping[str, AbstractSet[str]],
) -> int:
    """Return the count of ACTIVE contradictions for ``fact_id``.

    ``contradicting_edges`` maps a fact id to the set of fact ids that
    are currently contradicting it. The caller (C6 invalidate.py) is
    responsible for pre-filtering to ACTIVE contradictions:

    - Superseded contradictions are removed (gap-13 §3.2).
    - Revalidate-on-evidence resets — the count drops to 0 when fresh
      evidence revalidates the fact (gap-13 §7).

    Missing keys / empty sets return ``0``.
    """
    return len(contradicting_edges.get(fact_id, frozenset()))
