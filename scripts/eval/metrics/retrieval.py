"""Retrieval-quality metrics (WS4 stub).

Contract
--------
Compute precision@k, recall@k, nDCG@k for `recall(query, intent, scope)`
results against the Case ground truth. Stratified per intent class
(gap-12 §3), per source class (eval plan §4.1), per epoch (§2).

Cross-refs
----------
- `docs/04-eval-plan.md` §5.1 (precision/recall/nDCG @ k ∈ {1, 5, 10}).
- `docs/04-eval-plan.md` §5.9 (two-strata reporting).

Public surface (planned)
------------------------
    precision_at_k(retrieved, relevant, k) -> float
    recall_at_k(retrieved, relevant, k) -> float
    ndcg_at_k(retrieved, relevances, k) -> float
"""
from __future__ import annotations

import sys


def precision_at_k(retrieved: list, relevant: set, k: int) -> float:
    """precision@k. Wired but inert."""
    raise NotImplementedError(
        "metrics.retrieval.precision_at_k is a WS4 skeleton stub"
    )


def recall_at_k(retrieved: list, relevant: set, k: int) -> float:
    """recall@k. Wired but inert."""
    raise NotImplementedError(
        "metrics.retrieval.recall_at_k is a WS4 skeleton stub"
    )


def ndcg_at_k(retrieved: list, relevances: dict, k: int) -> float:
    """nDCG@k. Wired but inert."""
    raise NotImplementedError(
        "metrics.retrieval.ndcg_at_k is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.retrieval: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
