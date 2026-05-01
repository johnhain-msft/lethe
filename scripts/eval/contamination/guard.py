"""Contamination CI-gate — §4.4 (WS4 stub).

Contract
--------
Detect and refuse system `remember` of `contamination_protected` eval-set
facts. Two modes:

    strict  → CI-gate; build fails on detection. Used in CI pipelines.
    shadow  → log only; used during development.

Detection layers (§4.4):
    1. Stable fact-id match against the `contamination_protected` flag.
    2. Content-level paraphrase detection (in case the runtime extracted a
       paraphrased version of an eval fact). Provenance enforcement (gap-05)
       provides the verification surface.

Emits `contamination_events` metric on every run (§11.1
`contamination.json`).

Cross-refs
----------
- `docs/04-eval-plan.md` §4.4.
- `docs/03-gaps/gap-14-eval-set-bias.md` §5(2).
- `docs/03-gaps/gap-05-provenance-enforcement.md` (verification surface).

Public surface (planned)
------------------------
    is_protected(fact_id: str) -> bool
    matches_protected_content(content: str) -> str | None
        Returns matching protected fact-id, or None.
    on_remember_attempt(fact, mode: str = "strict") -> None
        Called by the runtime's `remember` write path. In strict mode,
        raises ContaminationError on detection.
    summarize_events() -> dict
        For `contamination.json` report row.
"""
from __future__ import annotations

import sys


class ContaminationError(Exception):
    """Raised in strict mode when system `remember` would write a protected
    eval-set fact. Fails the CI build."""


def is_protected(fact_id: str) -> bool:
    """Check the `contamination_protected` flag. Wired but inert."""
    raise NotImplementedError(
        "contamination.guard.is_protected is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §4.4"
    )


def matches_protected_content(content: str):
    """Paraphrase-aware content match. Wired but inert."""
    raise NotImplementedError(
        "contamination.guard.matches_protected_content is a WS4 skeleton stub"
    )


def on_remember_attempt(fact: object, mode: str = "strict") -> None:
    """Hook for the runtime's remember write path. Wired but inert."""
    raise NotImplementedError(
        "contamination.guard.on_remember_attempt is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §4.4 and gap-14 §5(2)"
    )


def summarize_events() -> dict:
    """Summarize contamination events for the run report. Wired but inert."""
    raise NotImplementedError(
        "contamination.guard.summarize_events is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.contamination.guard: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
