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

import argparse
import sys
from pathlib import Path

# Path-style invocation (`python scripts/eval/run_eval.py …`) puts only
# this script's directory on ``sys.path``, so ``from scripts.eval...``
# imports break. Inject the repo root explicitly so the harness behaves
# the same whether invoked as a path, ``-m scripts.eval.run_eval``, or
# from a parent test that already has the repo on ``sys.path``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_dmr(tenant_id: str) -> int:
    """Dispatch to the DMR sanity-replay adapter (P3 §2.3 exit gate)."""
    # Local import: keeps the WS4 inert default cheap and avoids dragging
    # sqlite-vec / FTS5 into a no-args invocation.
    from scripts.eval.adapters.dmr import run_sanity_replay

    result = run_sanity_replay(tenant_id=tenant_id)
    print(result.summary_line())
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    """Entry point. Dispatch on ``--adapter``; defaults to the WS4 inert path.

    P3 wires only ``--adapter dmr`` (sanity-replay). The rest of the WS4
    surface remains inert (exit 2) until those workstreams land.
    """
    parser = argparse.ArgumentParser(prog="scripts.eval.run_eval", add_help=True)
    parser.add_argument(
        "--adapter",
        choices=["dmr"],
        default=None,
        help="P3: only 'dmr' is wired; selects the §2.3 sanity-replay adapter.",
    )
    parser.add_argument(
        "--tenant-id",
        default="dmr-smoke",
        help="Tenant id used for the adapter's per-run temp store.",
    )
    args, _unknown = parser.parse_known_args(argv)

    if args.adapter == "dmr":
        return _run_dmr(args.tenant_id)

    # No adapter selected → preserve the WS4 inert behaviour (the rest of
    # the harness — public-benchmark loaders, metrics emitter, shadow,
    # chaos, contamination — has not landed yet).
    print("scripts.eval.run_eval: not implemented (WS4 stub)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
