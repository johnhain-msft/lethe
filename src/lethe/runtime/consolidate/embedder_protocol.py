"""Write-side embedder seam (composition §4.1; IMPL-followups erratum E1).

Lands the dependency-injectable :class:`Embedder` Protocol that the
P4 consolidate loop's embed phase consumes (composition §4.1 line 6 —
"embed new nodes/edges into S3"; IMPL-followups §3 erratum E1 wires
the write-side embedding pipeline at P4 rather than P3).

Phase split:

- **P4 (this commit)**: Protocol definition + :class:`NullEmbedder`
  default. NO production embedder. NO consumer (commits 5–7 wire it
  via ``runtime/consolidate/embed.py`` and ``loop.py``); the seam sits
  unused in the import graph this commit so the Protocol shape is
  reviewable in isolation.
- **P7**: host-runtime transport surface supplies the production
  :class:`Embedder` implementation (mirrors the
  :class:`~lethe.runtime.classifier.intent_classifier.NullLLMClassifier`
  → host-LLM transition pattern).

Batch-friendly call shape (composition §4.1 lines 4-8): the dream-
daemon embed step processes new nodes / edges / episodes in batches per
phase boundary. The Protocol takes ``texts: Sequence[str]`` and returns
``Sequence[Sequence[float]]`` of equal cardinality (one vector per input
text in input order). Single-text callers wrap as ``[text]`` and unpack
``[0]``; this avoids an API churn cycle at C5 when ``embed.py`` wraps
the seam.

Vector dimensionality is NOT fixed by the Protocol — implementations
return whatever dim they support (BGE-class 768 is the
:class:`~lethe.store.s3_vec.client.S3Config` default at P1; switching
backbones costs an S3 ``dim`` reshape but no Protocol change). C5's
``embed.py`` is the validation seam that asserts returned-dim ==
``S3Config.dim`` before persistence.

The implementation MUST be pure with respect to the input — same
``(tenant_id, texts)`` pair yields the same output, so deterministic
test fakes are usable verbatim as production-shape callables. Mirrors
:class:`~lethe.runtime.classifier.intent_classifier.LLMClassifier`'s
purity contract.

CRITICAL audit invariant (gap-12 §(g) row 2 — "no embedded SDK"):
this module imports NO third-party embedder SDKs (no
``sentence_transformers``, no ``openai``). The Protocol is a pure-
typing surface; the production embedder reaches the host runtime via
P7 transport, never via an in-process SDK call.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Injectable batch embedder for the consolidate embed phase.

    Implementations MUST be pure: same ``(tenant_id, texts)`` pair
    yields the same output. Implementations MUST return a sequence of
    vectors with cardinality equal to ``len(texts)`` and in input order
    (the i-th output vector corresponds to ``texts[i]``).

    Vector dimensionality is implementation-defined; C5's ``embed.py``
    asserts the returned dim matches the per-tenant
    :class:`~lethe.store.s3_vec.client.S3Config.dim` before persistence.

    Implementations MUST NOT cross the tenant boundary —
    ``tenant_id`` is the privacy edge per scoring §8.5; cross-tenant
    embedding caches are forbidden.
    """

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]: ...


class NullEmbedder:
    """Default production embedder — raises until P7 wires the host transport.

    Mirrors :class:`~lethe.runtime.classifier.intent_classifier.NullLLMClassifier`:
    the production embedder is the host-runtime transport channel, wired
    in at P7. Until then this stub raises :class:`NotImplementedError`,
    which the C5 ``embed.py`` consumer surfaces to the consolidate loop's
    embed-phase failure handler (composition §4.1 — embed-step failures
    leave the consolidate run partially-applied; the next cycle retries).
    """

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        raise NotImplementedError(
            "Embedder not configured; host-runtime wiring lands at P7 "
            "transport surface (composition §4.1; IMPL-followups erratum E1)"
        )
