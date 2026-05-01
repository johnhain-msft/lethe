# `scripts/eval/` — WS4 harness skeleton

Runnable but inert stubs for the WS4 eval & benchmark harness. Every module is
wired (importable, callable, exit-clean) but raises `NotImplementedError` from
public functions. This skeleton exists so that downstream work (WS5 scoring,
WS6 API, WS7 migration, WS8 deployment) can plan against a stable contract
surface without waiting for the implementation.

**Spec:** `docs/04-eval-plan.md`. Read that first.

**Language:** Python 3 (stdlib only at v1; no third-party deps). Per
`docs/HANDOFF.md` §3.4, no `npm` / node tooling in scope.

## Layout

```
scripts/eval/
├── README.md
├── run_eval.py                     # top-level harness entry
├── adapters/                       # public benchmark adapters (§3)
│   ├── longmemeval.py
│   ├── locomo.py
│   └── dmr.py
├── lethe_native/                   # Lethe-native eval set (§4)
│   ├── loader.py
│   └── schema.py
├── metrics/                        # headline metrics (§5)
│   ├── retrieval.py
│   ├── latency.py
│   ├── budget.py
│   ├── classifier.py
│   ├── extraction.py
│   ├── cost.py
│   └── emitter.py
├── shadow/                         # shadow-retrieval harness (§9)
│   └── harness.py
├── chaos/                          # chaos / fault eval (§7)
│   └── faults.py
├── contamination/                  # CI-gate contamination guard (§4.4)
│   └── guard.py
└── reports/                        # per-epoch / per-run-id outputs land here
```

## Stub conventions

Every `.py` in this tree:

1. Has a module docstring naming the contract it fulfills, with cross-refs to
   `docs/04-eval-plan.md` §X and the gap brief that motivates it.
2. Declares public function signatures with `raise NotImplementedError` bodies
   (so import-time wiring is exercised).
3. Has an `if __name__ == "__main__":` block that prints
   `"<module>: not implemented (WS4 stub)"` to stderr and exits with code 2
   (conventional `EX_USAGE` / `EX_*` family for "intentionally inert").

## Running (today, intentionally inert)

```
$ python3 scripts/eval/run_eval.py --help
$ python3 scripts/eval/run_eval.py --benchmark longmemeval
scripts.eval.run_eval: not implemented (WS4 stub)
$ echo $?
2
```

## Self-collection note (no foreign-system dependency)

The Lethe-native operator-trace slice (§4.6 of the spec) is sourced from
Lethe's **own** opt-in audit-log capture once Lethe is deployed. There is no
foreign-system ingest at any epoch — no SCNS `session_store`, no other
memory-system's audit log, no data broker. The opt-in capture verb is a WS6
surface dependency; this harness consumes it but does not implement it.

## Next steps (post-skeleton)

The WS5 (scoring) author reads `docs/04-eval-plan.md` §6 (per-phase signals)
as input contract. The WS6 (API) author owns the opt-in audit-log capture
verb that powers v1.x operator-trace ingest. The WS8 (deployment) author
schedules the monthly held-set re-eval and the drift-detector alarm
(`docs/04-eval-plan.md` §8).
