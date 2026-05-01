#!/usr/bin/env python3
"""Top-level harness entry point for the WS4 eval & benchmark harness.

Contract
--------
Orchestrates a single eval run. Dispatches to:

- public-benchmark adapters (`adapters.longmemeval`, `adapters.locomo`,
  `adapters.dmr`) — see `docs/04-eval-plan.md` §3.
- the Lethe-native eval-set loader (`lethe_native.loader`) — §4.
- the metrics emitter (`metrics.emitter`) — §5, §11.
- the shadow-retrieval harness (`shadow.harness`) — §9.
- the chaos / fault injector (`chaos.faults`) — §7.
- the contamination guard (`contamination.guard`) — §4.4.

Inputs (planned CLI):
    --benchmark {longmemeval, locomo, dmr, lethe_native, all}
    --epoch    {v1.0, v1.x}            (controls headline-tag rendering, §2)
    --stratum  {all-cases, strict, both}    (§5.9)
    --shadow   (flag; enables dual-path execution per §9)
    --chaos    {single, two-stores-down, all, none}    (§7)
    --snapshot <eval-set-snapshot-id>  (§4.5; reproducibility)
    --report-dir <path>                (default: scripts/eval/reports)

Outputs:
    Per-run report directory under `reports/<epoch>/<run-id>/` per §11.1:
    summary.json, per-phase/, per-stratum/, per-benchmark/, chaos.json,
    shadow.json, contamination.json, provenance.json.

Exit codes:
    0   run completed; no headline regression
    2   intentionally inert (WS4 stub)
    3   headline regression on strict stratum > 5% (CI gate, §11.4)
    4   contamination event detected in strict mode (§4.4)
    5   chaos run failed a P0 gate (§7.3)
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point. Will parse args and dispatch; today returns inert.

    Wired but inert. See module docstring for the contract this fulfills.
    """
    raise NotImplementedError(
        "run_eval.main is a WS4 skeleton stub; see docs/04-eval-plan.md §10"
    )


if __name__ == "__main__":
    print("scripts.eval.run_eval: not implemented (WS4 stub)", file=sys.stderr)
    sys.exit(2)
