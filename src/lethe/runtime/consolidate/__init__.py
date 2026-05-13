"""Consolidate loop + write-side embedder seam (P4 — IMPL §2.4).

This package lands the dream-daemon consolidate machinery (composition
§4.1 lines 4-8) over P4's nine-commit buildable order. At commit 3 only
the embedder seam is exposed; the rest of the package
(``loop`` / ``phases`` / ``extract`` / ``embed`` / ``score`` /
``promote`` / ``demote`` / ``invalidate`` / ``contradiction`` /
``gravity`` / ``scheduler``) lands in commits 4–9 and will append to
this re-export surface as it becomes consumer-visible.

Public re-exports (P4 commit 3):

- :class:`Embedder` — the dependency-injectable batch embedder Protocol
  consumed by the consolidate embed phase (composition §4.1 line 6;
  IMPL-followups erratum E1).
- :class:`NullEmbedder` — the production default; raises
  :class:`NotImplementedError` until the host-runtime transport
  surface wires a real implementation at P7 (mirrors
  :class:`~lethe.runtime.classifier.intent_classifier.NullLLMClassifier`).

The implementation lives in
:mod:`lethe.runtime.consolidate.embedder_protocol`.
"""

from __future__ import annotations

from lethe.runtime.consolidate.embedder_protocol import (
    Embedder,
    NullEmbedder,
)

__all__ = [
    "Embedder",
    "NullEmbedder",
]
