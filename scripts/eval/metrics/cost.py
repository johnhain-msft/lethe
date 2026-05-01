"""Cost metrics — fills synthesis §2.6 (WS4 stub).

Contract
--------
Public-benchmark accuracy without cost is not a WS4 output (eval plan §3.4).
This module emits the cost dimension that DMR/LongMemEval/LoCoMo all omit.

Measured (per `docs/04-eval-plan.md` §5.8):
    - tokens per `recall` (input + output, separately)
    - tokens per `remember` (extraction LLM call cost)
    - LLM calls per consolidation cycle (extraction + classifier residual +
      synthesis-page regeneration)
    - cost per benchmark question for each public benchmark

Cross-refs
----------
- `docs/04-eval-plan.md` §5.8.
- `docs/02-synthesis.md` §2.6 — "DMR, LongMemEval, LoCoMo all report
  accuracy. None reports tokens-per-query or p95 latency."

Public surface (planned)
------------------------
    tokens_per_recall(samples: list[dict]) -> dict
        Returns {input_p50, input_p99, output_p50, output_p99}.
    tokens_per_remember(samples: list[dict]) -> dict
    llm_calls_per_consolidation_cycle(samples: list[dict]) -> dict
    cost_per_benchmark_question(benchmark: str, samples: list[dict]) -> dict
"""
from __future__ import annotations

import sys


def tokens_per_recall(samples: list) -> dict:
    """Tokens per recall (input/output, percentiles). Wired but inert."""
    raise NotImplementedError(
        "metrics.cost.tokens_per_recall is a WS4 skeleton stub"
    )


def tokens_per_remember(samples: list) -> dict:
    """Tokens per remember (extraction cost). Wired but inert."""
    raise NotImplementedError(
        "metrics.cost.tokens_per_remember is a WS4 skeleton stub"
    )


def llm_calls_per_consolidation_cycle(samples: list) -> dict:
    """LLM calls per dream-daemon cycle. Wired but inert."""
    raise NotImplementedError(
        "metrics.cost.llm_calls_per_consolidation_cycle is a WS4 skeleton stub"
    )


def cost_per_benchmark_question(benchmark: str, samples: list) -> dict:
    """Cost per benchmark question. Wired but inert."""
    raise NotImplementedError(
        "metrics.cost.cost_per_benchmark_question is a WS4 skeleton stub"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.cost: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
