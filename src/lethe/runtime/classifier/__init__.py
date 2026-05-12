"""Intent classifier (gap-12) — public surface.

Lands the heuristic + LLM-residual hybrid named in gap-12 §5 as the v1
recommendation. The 7-class taxonomy (§3) and the decision-boundary
table (§6) are the contract; this module is the implementation seam.

Public re-exports:

- :data:`IntentClass` — the seven valid intent labels (§3).
- :data:`VALID_INTENT_CLASSES` — runtime-checkable set form of the same.
- :class:`LLMClassification` / :class:`LLMClassifier` — the dependency-
  injectable LLM seam (locked decision #2 in the facilitator P2 plan).
- :class:`NullLLMClassifier` — the production default; raises
  :class:`NotImplementedError` until the host transport surface lands at
  P7. The dispatch layer treats that the same as a timeout (fall back to
  the heuristic verdict).
- :class:`ClassificationRequest` / :class:`ClassificationResult` — the
  function-level input/output contract for :func:`classify`.
- :func:`classify` — the entry point that ``remember.py`` (commit 4)
  composes.

The implementation lives in :mod:`lethe.runtime.classifier.intent_classifier`.
"""

from __future__ import annotations

from lethe.runtime.classifier.intent_classifier import (
    VALID_INTENT_CLASSES,
    ClassificationPath,
    ClassificationRequest,
    ClassificationResult,
    IntentClass,
    LLMClassification,
    LLMClassifier,
    NullLLMClassifier,
    SourceKind,
    classify,
)

__all__ = [
    "VALID_INTENT_CLASSES",
    "ClassificationPath",
    "ClassificationRequest",
    "ClassificationResult",
    "IntentClass",
    "LLMClassification",
    "LLMClassifier",
    "NullLLMClassifier",
    "SourceKind",
    "classify",
]
