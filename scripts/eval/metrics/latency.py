"""Latency metrics (p50 / p99) — stratified (WS4 stub).

Contract
--------
Compute p50 and p99 latency, **always stratified** per WS3-QA latency-
stratification nit. An aggregate p50/p99 across all paths is meaningless and
is not emitted by this module.

Strata (per `docs/04-eval-plan.md` §5.2):
    - path: recall | recall_synthesis | remember | consolidate | forget
    - cache state: cold | warm
    - tenancy: single | multi (placeholder at v1.0; gap-04 future)
    - shadow vs. live (§9 emits its own latency)

Cross-refs
----------
- `docs/04-eval-plan.md` §5.2.
- WS3-QA stratification nit (commit `558f830`).

Public surface (planned)
------------------------
    p50(samples_ms: list[float]) -> float
    p99(samples_ms: list[float]) -> float
    stratify(samples: list[dict], by: tuple[str, ...]) -> dict
        Returns nested dict of percentile rows keyed by stratum tuple.
"""
from __future__ import annotations

import sys


def p50(samples_ms: list) -> float:
    """50th percentile. Wired but inert."""
    raise NotImplementedError("metrics.latency.p50 is a WS4 skeleton stub")


def p99(samples_ms: list) -> float:
    """99th percentile. Wired but inert."""
    raise NotImplementedError("metrics.latency.p99 is a WS4 skeleton stub")


def stratify(samples: list, by: tuple) -> dict:
    """Stratify samples by the given strata tuple; emit per-stratum rows."""
    raise NotImplementedError(
        "metrics.latency.stratify is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §5.2"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.latency: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
