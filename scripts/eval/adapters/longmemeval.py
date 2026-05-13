"""LongMemEval adapter (WS4 stub).

Contract
--------
Loads LongMemEval cases and maps them onto the common `Case` schema
(`scripts.eval.lethe_native.schema.Case`) so the harness can route them
through `recall(query, intent, scope)` uniformly.

Cross-refs
----------
- `docs/04-eval-plan.md` §3.1 — what we use LongMemEval for; conversational-
  vs-agent-workflow caveat.
- `docs/03-gaps/gap-01-retention-engine.md` §6 residual ("two-stream Q1
  outcome — until WS4 measures the temporal-vs-semantic split on
  LongMemEval, we don't know whether one-stream is sufficient"). LongMemEval
  is the substrate for that measurement.
- `docs/02-synthesis.md` §1.6 (memory benchmarks) and §2.6 (cost/latency
  framing — public-benchmark accuracy without cost is not a WS4 output).

Public surface (planned)
------------------------
    load(snapshot_id: str | None) -> Iterable[Case]
        Yield LongMemEval cases mapped onto the common Case schema. If
        snapshot_id is None, use the bundled default snapshot.
    metadata() -> dict
        Return adapter metadata (benchmark name, version, citation, license).
"""
from __future__ import annotations

import sys
from collections.abc import Iterable


def load(snapshot_id: str | None = None) -> Iterable[object]:
    """Yield LongMemEval cases mapped to the common Case schema.

    Wired but inert. See module docstring.
    """
    raise NotImplementedError(
        "adapters.longmemeval.load is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §3.1"
    )


def metadata() -> dict:
    """Return adapter metadata. Wired but inert."""
    raise NotImplementedError(
        "adapters.longmemeval.metadata is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.adapters.longmemeval: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
