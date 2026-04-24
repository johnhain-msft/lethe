# 01 — Zep: A Temporal Knowledge Graph Architecture for Agent Memory

**URL:** https://arxiv.org/abs/2501.13956  **Type:** paper  **Fetched:** 2026-04-23
**Authors:** Rasmussen et al. (Zep AI Research). 12 pages, arXiv:2501.13956v1, Jan 2025.

## Problem framing
RAG treats every query as fresh retrieval over static documents. Enterprise agent use requires *dynamic* knowledge integration from ongoing conversations + business data while preserving historical relationships. The paper explicitly positions existing RAG as insufficient for long-running, stateful agents.

## Architecture
Zep is a memory-layer *service*; its core engine is **Graphiti**, a temporally-aware knowledge graph. Three conceptual components:
1. **Ingestion** — accepts unstructured conversational data and structured business data; synthesizes both into graph form.
2. **Graphiti engine** — temporal knowledge graph maintaining entity + relationship nodes with bi-temporal validity (valid-time + transaction-time) so historical state is preserved rather than overwritten.
3. **Retrieval** — graph traversal + semantic search producing context for LLM calls.

## Scoring / retrieval math
Paper asserts latency and accuracy wins but the published abstract does not give the retrieval math directly. From the Graphiti repo (brief 12): bi-temporal validity drives an **invalidate-don't-delete** policy — contradicted facts get `valid_to` stamped, not removed. Relevance at retrieval time combines semantic similarity with graph-distance + temporal filter. Exact weights are not disclosed in the abstract; see brief 12 for repo-level specifics.

## API surface
Not enumerated in the abstract. Zep ships as a service with an SDK; the reference implementation in brief 12 (`getzep/graphiti`) is the canonical public surface.

## Scale claims + evidence
- **DMR benchmark:** 94.8 % vs MemGPT 93.4 %.
- **LongMemEval:** accuracy improvements "up to 18.5 %" over baseline.
- **Latency:** "90 % reduction" vs baseline implementation (baseline unspecified in abstract).
- 12-page paper, 3 tables. Benchmark detail lives in the full PDF, not the abstract fetched here.

## Documented limits
Not enumerated in the abstract. The paper evidently concedes MemGPT is the prior SOTA for DMR only (margin is small: +1.4 pts).

## Relation to Lethe
**Leading substrate candidate.** Per PLAN.md scope call #5, Graphiti is the leading substrate dependency. Zep is the packaging; Graphiti is the engine Lethe would depend on. Zep's bi-temporal invalidation pattern is the recommended replacement for SCNS's name-keyed last-write-wins contradiction handling (see `01b-dream-daemon-design-note.md` §2.6, §4).

## Gaps / hand-waves it introduces
- **Promotion / demotion silent.** Zep ingests and retrieves; the paper says little about what gets *pruned*, *promoted*, or *forgotten*. This maps directly to Graphiti issue #1300 (brief 14) — the engine is a substrate, not a runtime.
- **Scoring weights.** Paper claims "weighting matters more than individual signals" (PDF §gap) but doesn't publish the weights it used.
- **Enterprise-only framing.** "Conversations + business data" is a narrower audience than agent-workflow memory. The benchmark lift on LongMemEval is impressive but LongMemEval is conversational; see brief 18 for the applicability gap.
- **Latency baseline is vague.** "90 %" vs *what* baseline implementation is the obvious question.
