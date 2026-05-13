"""Tests for :mod:`lethe.runtime.consolidate.embedder_protocol`.

Coverage map (P4 commit 3 — Embedder Protocol contract only):

- :class:`NullEmbedder` is the production default; its ``__call__``
  raises :class:`NotImplementedError` with a P7 host-runtime citation.
- :class:`Embedder` is a structural Protocol — a deterministic test
  fake satisfying the call signature is assignable to an
  ``Embedder``-typed slot at static-check time.
- Batch contract: a fake embedder returns one vector per input text in
  input order; cardinality MUST equal ``len(texts)``.
- Determinism contract: same ``(tenant_id, texts)`` pair yields the
  same output (Protocol-level purity invariant).
- Empty-input edge case: ``texts=[]`` returns an empty result; the fake
  is not invoked with degenerate input by an arbitrary consumer
  contract, but the Protocol does not forbid the empty call.
- Re-export contract: :class:`Embedder` and :class:`NullEmbedder` are
  importable from :mod:`lethe.runtime.consolidate` (the public
  surface).
- §7.3 SDK-import audit: this module imports neither
  ``sentence_transformers`` nor ``openai`` directly or transitively
  (sanity check — the real audit is a repo-wide grep gate).

NOT in scope this commit (lands at C5 ``test_consolidate_extract_embedder.py``):

- ``embed.py`` orchestration.
- S3 vec0 + embedding_keys CHECK invariant (§B.5).
- Cross-store T2 atomicity for the embedder write path.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence

import pytest

from lethe.runtime.consolidate import Embedder, NullEmbedder
from lethe.runtime.consolidate import embedder_protocol as _embedder_protocol_mod


class _DeterministicStubEmbedder:
    """Deterministic fake embedder for Protocol-contract tests.

    Returns a ``dim``-length vector per input text whose entries are a
    pure function of (tenant_id, text). Mirrors the
    :class:`~lethe.runtime.classifier.intent_classifier.LLMClassifier`
    purity contract.
    """

    def __init__(self, *, dim: int = 8) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self._dim = dim
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        tenant_id: str,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        self.calls.append({"tenant_id": tenant_id, "texts": list(texts)})
        out: list[list[float]] = []
        for text in texts:
            seed = hash((tenant_id, text)) & 0xFFFFFFFF
            out.append([((seed >> (i % 32)) & 0xFF) / 255.0 for i in range(self._dim)])
        return out


# ---------------------------------------------------------------------------
# NullEmbedder default
# ---------------------------------------------------------------------------


def test_null_embedder_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        NullEmbedder()(tenant_id="t-test", texts=["hello"])


def test_null_embedder_error_message_cites_p7() -> None:
    with pytest.raises(NotImplementedError, match="P7"):
        NullEmbedder()(tenant_id="t-test", texts=["hello"])


def test_null_embedder_error_message_cites_composition_and_followups() -> None:
    """The error string MUST cite both the composition spec and the
    IMPL-followups erratum — this is the contract that lets a future
    P7 wiring author find the binding doc set without re-reading the
    plan."""
    with pytest.raises(NotImplementedError) as exc_info:
        NullEmbedder()(tenant_id="t-test", texts=["hello"])
    msg = str(exc_info.value)
    assert "composition §4.1" in msg
    assert "IMPL-followups erratum E1" in msg


def test_null_embedder_raises_even_on_empty_texts() -> None:
    """The default MUST NOT shortcut empty input — a host-not-wired
    state is the same regardless of payload size, and a silent
    ``return []`` would mask P7 wiring failures in downstream
    consumers."""
    with pytest.raises(NotImplementedError):
        NullEmbedder()(tenant_id="t-test", texts=[])


# ---------------------------------------------------------------------------
# Protocol structural compatibility
# ---------------------------------------------------------------------------


def test_null_embedder_satisfies_protocol_structurally() -> None:
    """Static-typing surrogate: assignment to an ``Embedder``-typed slot
    succeeds at runtime (Protocol structural matching is checked by
    mypy at the call site; here we exercise the assignment path so a
    breakage of either the Protocol shape or the NullEmbedder shape
    would surface in pytest as well)."""
    e: Embedder = NullEmbedder()
    assert callable(e)


def test_deterministic_stub_satisfies_protocol_structurally() -> None:
    e: Embedder = _DeterministicStubEmbedder(dim=8)
    assert callable(e)


# ---------------------------------------------------------------------------
# Batch contract — cardinality + ordering
# ---------------------------------------------------------------------------


def test_batch_cardinality_matches_input_length() -> None:
    stub = _DeterministicStubEmbedder(dim=8)
    out = stub(tenant_id="t-test", texts=["a", "b", "c", "d"])
    assert len(out) == 4
    for vec in out:
        assert len(vec) == 8


def test_batch_preserves_input_order() -> None:
    """The i-th output vector MUST correspond to ``texts[i]``."""
    stub = _DeterministicStubEmbedder(dim=8)
    out_one_then_two = stub(tenant_id="t-test", texts=["one", "two"])
    out_two_then_one = stub(tenant_id="t-test", texts=["two", "one"])
    # Same texts, different order → outputs swap to match.
    assert list(out_one_then_two[0]) == list(out_two_then_one[1])
    assert list(out_one_then_two[1]) == list(out_two_then_one[0])


def test_batch_handles_single_text_caller_pattern() -> None:
    """Single-text callers wrap as ``[text]`` and unpack ``[0]`` — this
    is the documented bridge from per-call to batch shape."""
    stub = _DeterministicStubEmbedder(dim=8)
    out = stub(tenant_id="t-test", texts=["solo"])
    assert len(out) == 1
    assert len(out[0]) == 8


def test_batch_handles_empty_texts_for_implementations_that_allow_it() -> None:
    """The Protocol does not forbid the empty call; an implementation
    MAY accept ``texts=[]`` and return ``[]`` (the C5 consumer wraps
    the call to skip the empty path entirely, but the Protocol shape
    itself is consumer-agnostic). Documented here so a future
    Protocol-tightening change has an explicit test to update."""
    stub = _DeterministicStubEmbedder(dim=8)
    out = stub(tenant_id="t-test", texts=[])
    assert list(out) == []


# ---------------------------------------------------------------------------
# Determinism contract
# ---------------------------------------------------------------------------


def test_stub_embedder_is_deterministic_across_calls() -> None:
    """Same ``(tenant_id, texts)`` pair → same output (the Protocol-
    level purity invariant)."""
    stub = _DeterministicStubEmbedder(dim=8)
    out_a = stub(tenant_id="t-test", texts=["alpha", "beta"])
    out_b = stub(tenant_id="t-test", texts=["alpha", "beta"])
    assert [list(v) for v in out_a] == [list(v) for v in out_b]


def test_stub_embedder_varies_by_tenant_id() -> None:
    """Tenant-scoped purity: different tenants on the same text are
    NOT required to produce the same vector — the Protocol carries
    ``tenant_id`` precisely so per-tenant embedders / caches are
    possible. The stub demonstrates this."""
    stub = _DeterministicStubEmbedder(dim=8)
    out_t1 = stub(tenant_id="t-one", texts=["hello"])
    out_t2 = stub(tenant_id="t-two", texts=["hello"])
    assert list(out_t1[0]) != list(out_t2[0])


# ---------------------------------------------------------------------------
# Re-export surface
# ---------------------------------------------------------------------------


def test_consolidate_package_reexports_embedder_and_null_embedder() -> None:
    """Both symbols MUST be importable from the package root (mirrors
    the ``runtime.classifier`` re-export pattern). Other consolidate
    symbols (run_consolidate, ConsolidatePhaseEvent, …) are NOT yet
    re-exported — they land in their own commits."""
    pkg = importlib.import_module("lethe.runtime.consolidate")
    assert pkg.Embedder is Embedder
    assert pkg.NullEmbedder is NullEmbedder


def test_consolidate_package_all_includes_embedder_seam() -> None:
    """The ``__all__`` list MUST include both embedder-seam symbols.
    Other consolidate symbols (score / gravity / contradiction adapters
    in C4; loop / phases / extract / embed / promote / demote /
    invalidate / scheduler in C5–C9) append as they land — this test
    pins the embedder-seam contract specifically and is invariant
    across C4–C9 additions."""
    pkg = importlib.import_module("lethe.runtime.consolidate")
    assert "Embedder" in pkg.__all__
    assert "NullEmbedder" in pkg.__all__


# ---------------------------------------------------------------------------
# §7.3 SDK-import audit (sanity surrogate)
# ---------------------------------------------------------------------------


def test_embedder_protocol_module_imports_no_third_party_sdk() -> None:
    """Sanity surrogate for the §7.3 repo-wide SDK-import audit gate.
    The Protocol module MUST be a pure-typing surface — no
    ``sentence_transformers``, no ``openai`` in its module globals.
    The repo-wide grep gate is the binding check; this test just
    fails fast in CI if a regression sneaks into this module's
    direct imports."""
    mod = _embedder_protocol_mod
    forbidden = {"sentence_transformers", "openai"}
    assert forbidden.isdisjoint(set(vars(mod).keys()))
