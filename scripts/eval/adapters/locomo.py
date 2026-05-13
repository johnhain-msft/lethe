"""LoCoMo (and LoCoMo-Plus) adapter (WS4 stub).

Contract
--------
Loads LoCoMo and LoCoMo-Plus cases and maps them onto the common `Case`
schema. LoCoMo-Plus is the v1 proxy for non-factual memory evaluation
(preferences, goals) — see `docs/03-gaps/gap-09-non-factual-memory.md`.

Cross-refs
----------
- `docs/04-eval-plan.md` §3.2 — long-horizon dialogue; saturation caveat;
  LoCoMo-Plus as the only public benchmark exercising non-factual memory.
- `docs/02-synthesis.md` §2.9 — non-factual memory gap; LoCoMo-Plus raises
  it.
- `docs/04-eval-plan.md` §5.6 — per-class F1 over the seven-class taxonomy;
  LoCoMo-Plus contributes the `remember:preference` cases.

Public surface (planned)
------------------------
    load(variant: str = "locomo", snapshot_id: str | None = None)
        variant ∈ {"locomo", "locomo-plus"}; yields Case objects.
    metadata() -> dict
"""
from __future__ import annotations

import sys
from collections.abc import Iterable


def load(
    variant: str = "locomo", snapshot_id: str | None = None
) -> Iterable[object]:
    """Yield LoCoMo / LoCoMo-Plus cases. Wired but inert."""
    raise NotImplementedError(
        "adapters.locomo.load is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §3.2"
    )


def metadata() -> dict:
    """Return adapter metadata. Wired but inert."""
    raise NotImplementedError("adapters.locomo.metadata is a WS4 skeleton stub")


if __name__ == "__main__":
    print(
        "scripts.eval.adapters.locomo: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
