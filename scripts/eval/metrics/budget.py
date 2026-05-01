"""Context-budget adherence metrics (WS4 stub).

Contract
--------
Measure whether `recall` responses fit a caller-declared token budget;
report over-budget tail distribution.

Cross-refs
----------
- `docs/04-eval-plan.md` §5.3.

Public surface (planned)
------------------------
    fit_rate(samples: list[dict]) -> float
        Fraction of recalls that fit the declared budget.
    over_budget_tail(samples: list[dict]) -> dict
        p95 and p99 over-budget excess (in tokens).
"""
from __future__ import annotations

import sys


def fit_rate(samples: list) -> float:
    """Fraction of recalls fitting their declared budget. Wired but inert."""
    raise NotImplementedError("metrics.budget.fit_rate is a WS4 skeleton stub")


def over_budget_tail(samples: list) -> dict:
    """Over-budget tail (p95, p99 excess). Wired but inert."""
    raise NotImplementedError(
        "metrics.budget.over_budget_tail is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.budget: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
