"""Lethe-native eval-set loader (WS4 stub).

Contract
--------
Loads Lethe-native cases by source class and snapshot version; enforces the
composition floors and caps in `docs/04-eval-plan.md` §4.1; refuses to emit a
"headline-eligible" case set if any floor or cap is violated; supports
opt-in audit-log capture (§4.6) as the v1.x operator-trace ingest path.

Cross-refs
----------
- `docs/04-eval-plan.md` §4 (composition, sourcing, contamination, versioning)
  and §4.6 (Lethe self-collection pipeline).
- `docs/03-gaps/gap-14-eval-set-bias.md` §5(1)–(5) — the constraints the
  loader's invariants enforce.
- `docs/03-gaps/gap-11-forgetting-as-safety.md` §3.3 — sensitivity-class
  taxonomy used by the §4.6 scrub step.

Composition floors / caps (loader-enforced)
-------------------------------------------
v1.0 (epoch=v1.0):
    operator        : 0%   (foreign-system ingest is forbidden; §4.6)
    adversarial     : ≥35% floor
    ablation        : ≥25% floor
    synthetic       : ≤25% (with 10% spot-check sample; §4.2)
    author-curated  : ≤15% cap

v1.x (epoch=v1.x):
    operator        : ≥20% gate-to-leave-v1.0 / 30% target
    adversarial     : 25% target
    ablation        : 20% target
    synthetic       : 15% target (with 5% spot-check sample)
    author-curated  : ≤10% cap

Headline-eligible iff all floors/caps satisfied AND symmetry ratio in
[0.7, 1.3] per §4.3.

Public surface (planned)
------------------------
    load(snapshot_id: str, epoch: str = "v1.0") -> Iterable[Case]
    composition_stats(cases: Iterable[Case]) -> dict
    is_headline_eligible(stats: dict, epoch: str) -> tuple[bool, list[str]]
        Returns (eligible, list_of_violations).
    capture_opt_in_trace(tenant_id, opt_in_record, trace) -> None
        v1.x audit-log ingest entry point. Stubbed at v1.0 (no operator
        traces exist yet); contract is set so WS6 can wire the verb.
"""
from __future__ import annotations

import sys
from typing import Iterable


def load(snapshot_id: str, epoch: str = "v1.0") -> Iterable["object"]:
    """Yield Lethe-native Case objects for the snapshot. Wired but inert."""
    raise NotImplementedError(
        "lethe_native.loader.load is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §4"
    )


def composition_stats(cases: Iterable["object"]) -> dict:
    """Return per-source-class case counts and ratios. Wired but inert."""
    raise NotImplementedError(
        "lethe_native.loader.composition_stats is a WS4 skeleton stub"
    )


def is_headline_eligible(stats: dict, epoch: str) -> tuple[bool, list[str]]:
    """Enforce §4.1 floors/caps and §4.3 symmetry. Wired but inert."""
    raise NotImplementedError(
        "lethe_native.loader.is_headline_eligible is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §4.1 and gap-14 §5(1)"
    )


def capture_opt_in_trace(
    tenant_id: str, opt_in_record: dict, trace: object
) -> None:
    """v1.x audit-log capture entry point (§4.6).

    At v1.0 this raises. The contract is set here so WS6 (which owns the
    opt-in verb) can wire against a stable signature.
    """
    raise NotImplementedError(
        "lethe_native.loader.capture_opt_in_trace is a v1.x facility; "
        "see docs/04-eval-plan.md §4.6"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.lethe_native.loader: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
