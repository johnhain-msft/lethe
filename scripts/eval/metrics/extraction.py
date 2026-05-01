"""Extraction-quality metrics — gap-06 (WS4 stub).

Contract
--------
Three dimensions, all reported (gap-06 §3):
    1. Recall — of facts present in source episode, how many extracted?
    2. Precision — of facts extracted, how many truthful + relevant?
    3. Disambiguation accuracy — entity binding to correct existing node.

Plus a per-domain calibration table (gap-06 §3 names per-domain calibration
explicitly): F1 per domain class as it emerges in the eval set.

Threshold targets (gap-06 §6):
    - quarantine rate target 5%; alarm at sustained > 15%
    - disambiguation F1 alarm at < 0.85

Cross-refs
----------
- `docs/04-eval-plan.md` §5.7.
- `docs/03-gaps/gap-06-extraction-quality.md` §3 (dimensions), §6 (thresholds).

Public surface (planned)
------------------------
    extraction_recall(extracted, expected) -> float
    extraction_precision(extracted, expected) -> float
    disambiguation_accuracy(bindings, expected_bindings) -> float
    per_domain_calibration(samples: list[dict]) -> dict[str, dict]
        Returns {domain: {recall, precision, disambiguation, f1}}.
"""
from __future__ import annotations

import sys


def extraction_recall(extracted: set, expected: set) -> float:
    """Extraction recall. Wired but inert."""
    raise NotImplementedError(
        "metrics.extraction.extraction_recall is a WS4 skeleton stub"
    )


def extraction_precision(extracted: set, expected: set) -> float:
    """Extraction precision. Wired but inert."""
    raise NotImplementedError(
        "metrics.extraction.extraction_precision is a WS4 skeleton stub"
    )


def disambiguation_accuracy(
    bindings: dict, expected_bindings: dict
) -> float:
    """Entity disambiguation accuracy. Wired but inert."""
    raise NotImplementedError(
        "metrics.extraction.disambiguation_accuracy is a WS4 skeleton stub"
    )


def per_domain_calibration(samples: list) -> dict:
    """Per-domain calibration table (gap-06 §3). Wired but inert."""
    raise NotImplementedError(
        "metrics.extraction.per_domain_calibration is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.extraction: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
