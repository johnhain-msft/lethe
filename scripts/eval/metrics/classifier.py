"""Intent-classifier F1 metrics — gap-12 headline (WS4 stub).

Contract
--------
Compute per-class precision, recall, F1 over the seven intent classes from
`docs/03-gaps/gap-12-intent-classifier.md` §3:
    remember:fact | remember:preference | remember:procedure |
    reply_only | peer_route | drop | escalate

Headline number is **macro-F1** (unweighted average) — prevents a high-
prevalence class from dominating. Per-class F1 is the diagnostic.

Baseline target per gap-12 §7 residual: 85% macro-F1 on the held-out
symmetric set. Below 85%, classifier itself is degrading recall.

Cross-refs
----------
- `docs/04-eval-plan.md` §5.6 (headline metric for gap-12).
- `docs/03-gaps/gap-12-intent-classifier.md` §3 (taxonomy), §7 (baseline).
- `docs/03-gaps/gap-14-eval-set-bias.md` §5(5) (symmetric pos/neg cases).

Public surface (planned)
------------------------
    per_class_f1(predictions, ground_truth) -> dict[str, float]
    macro_f1(predictions, ground_truth) -> float
"""
from __future__ import annotations

import sys


def per_class_f1(predictions: list, ground_truth: list) -> dict:
    """Per-class F1 over the seven intent classes. Wired but inert."""
    raise NotImplementedError(
        "metrics.classifier.per_class_f1 is a WS4 skeleton stub; "
        "see gap-12 §3"
    )


def macro_f1(predictions: list, ground_truth: list) -> float:
    """Macro-F1 (headline metric per gap-12). Wired but inert."""
    raise NotImplementedError(
        "metrics.classifier.macro_f1 is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §5.6"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.classifier: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
