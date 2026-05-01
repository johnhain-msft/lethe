"""Shadow-retrieval harness — compute-don't-surface (WS4 stub).

Contract
--------
Dual-path runner: production answers continue from current system; shadow
path runs candidate system on same query in parallel; results emitted to
eval store, never to caller.

Compute-don't-surface invariants (§9):
    - Shadow path cannot mutate any store. Reads only.
    - Shadow path cannot raise exceptions visible to the caller. All shadow
      exceptions logged to S5 and counted as `shadow_error` metric.
    - Shadow path cannot exceed configurable wall-clock budget; over-budget
      results dropped and counted as `shadow_timeout`.

Implementation independence: this harness is a Lethe-internal facility; it
does not depend on, dual-write to, or read from any external system. The
dual-dispatch and agreement-scoring are both implemented here.

Cross-refs
----------
- `docs/04-eval-plan.md` §9.
- PLAN.md §WS4 ("compute but don't surface").

Public surface (planned)
------------------------
    dual_dispatch(query, prod_runner, shadow_runner, budget_ms) -> dict
        Runs both paths; returns the production result; logs comparison row.
    agreement_score(prod_result, shadow_result) -> float
        Lethe-owned scoring layer; 0.0 = total disagreement, 1.0 = identical.
    write_comparison_row(row: dict) -> None
"""
from __future__ import annotations

import sys


def dual_dispatch(
    query: object,
    prod_runner,
    shadow_runner,
    budget_ms: int,
) -> dict:
    """Run prod + shadow; return prod result; log comparison. Wired but inert."""
    raise NotImplementedError(
        "shadow.harness.dual_dispatch is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §9"
    )


def agreement_score(prod_result: object, shadow_result: object) -> float:
    """Compute agreement score in [0.0, 1.0]. Wired but inert."""
    raise NotImplementedError(
        "shadow.harness.agreement_score is a WS4 skeleton stub"
    )


def write_comparison_row(row: dict) -> None:
    """Persist a comparison row to the eval store. Wired but inert."""
    raise NotImplementedError(
        "shadow.harness.write_comparison_row is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.shadow.harness: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
