"""DMR (Dialogue Memory Recall) adapter (WS4 stub).

Contract
--------
Loads DMR cases and maps them onto the common `Case` schema. DMR is the
most-saturated of the three public benchmarks in scope; the harness uses
DMR primarily as a regression smoke test, not a discrimination signal.

Cross-refs
----------
- `docs/04-eval-plan.md` §3.3 — saturation caveat; smoke-test role.
- `docs/02-synthesis.md` §1.6 — memory benchmarks at known saturation
  levels.

Public surface (planned)
------------------------
    load(snapshot_id: str | None) -> Iterable[Case]
    metadata() -> dict
"""
from __future__ import annotations

import sys
from typing import Iterable


def load(snapshot_id: str | None = None) -> Iterable["object"]:
    """Yield DMR cases. Wired but inert."""
    raise NotImplementedError(
        "adapters.dmr.load is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §3.3"
    )


def metadata() -> dict:
    """Return adapter metadata. Wired but inert."""
    raise NotImplementedError("adapters.dmr.metadata is a WS4 skeleton stub")


if __name__ == "__main__":
    print(
        "scripts.eval.adapters.dmr: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
