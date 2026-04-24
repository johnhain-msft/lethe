# 02 — MAGMA: A Multi-Graph Agentic Memory Architecture

**URL:** https://arxiv.org/html/2601.03236v2  **Type:** paper  **Fetched:** 2026-04-23
**Authors:** Jiang, Li, Li (UT Dallas + U. Florida), arXiv:2601.03236v2.

## Problem framing
Existing MAG (Memory-Augmented Generation) systems rely on semantic similarity over monolithic memory stores. That entangles *temporal*, *causal*, and *entity* information — making it hard to align a query's intent with the right evidence. Structural limitation → reasoning accuracy cap.

## Architecture
Three layers:
1. **Query process** — Intent-Aware Router, Adaptive Topological Retrieval, Context Synthesizer.
2. **Data structure layer** — time-variant directed *multigraph* 𝒢ₜ=(𝒩ₜ,ℰₜ). Nodes are events with `⟨content, timestamp, embedding v∈ℝᵈ, attributes⟩`. **Edges are partitioned into four orthogonal subspaces**:
   - **Temporal graph** — strictly-ordered pairs (τᵢ < τⱼ). Immutable chronology.
   - **Causal graph** — directed edges where `S(nⱼ|nᵢ, q) > δ`, LLM-inferred during consolidation. Answers "why".
   - **Semantic graph** — undirected, `cos(vᵢ,vⱼ) > θ_sim`. Conceptual similarity.
   - **Entity graph** — events → abstract entity nodes. Solves object-permanence across disjoint timelines.
   - Plus a vector DB for semantic search alongside the graphs.
3. **Write/update process — dual-stream**:
   - **Synaptic Ingestion (fast path)** — latency-sensitive write.
   - **Asynchronous Consolidation (slow path)** — compute-intensive relational refinement.

## Scoring / retrieval math
Policy-guided graph traversal, not static lookup. Router decomposes query `q` into:
- **Intent classification** `T_q ∈ {Why, When, Entity}` — steers which edge subspace is prioritized.
- **Temporal parsing** — relative expressions → absolute timestamps → hard time window.
- **Representations** — dense embedding `q⃗` + sparse keywords `q_key`.

Anchor identification fuses semantic + lexical + temporal signals; adaptive traversal then navigates the selected graph views (e.g. "Why" → causal edges weighted up).

## API surface
Not exhaustively documented in the fetched v2 HTML. Open-source code: `github.com/FredJiang0324/MAGMA`. High-level interface is implicit: `ingest(event)`, `consolidate()` (async), `query(q)` returning a type-aligned context.

## Scale claims + evidence
- Benchmarks: **LoCoMo** (brief 19), **LongMemEval** (brief 18).
- "Consistently outperforms state-of-the-art agentic memory systems on long-context benchmarks."
- Reduced retrieval latency and token consumption vs prior systems. Numeric deltas not in the fetched section.

## Documented limits
- Intent classifier restricted to {Why, When, Entity}. Any query that doesn't route cleanly into one of those bins gets default treatment.
- Causal edges are LLM-inferred during async consolidation — the causal graph is only as good as the LLM's causal-reasoning call at refine-time.
- Vector DB sits alongside the four graphs — consistency between them at write time is not discussed in the fetched section.
- English / single-timeline assumption.

## Relation to Lethe
**Reference architecture.** Per PLAN.md scope call #5, Lethe = MAGMA-style on proven substrates. Two MAGMA primitives directly feed Lethe design:
1. **Dual-stream write path.** Fast synaptic ingest + async consolidation is exactly the split SCNS's dream-daemon implements. Consolidation-as-async is now a cross-paper consensus (MAGMA + LightMem + SleepGate, per brief 04).
2. **Intent-aware retrieval routing.** WS5/WS6 should adopt the intent classifier pattern; `{Why, When, Entity}` is a credible starting taxonomy but Lethe's agent-workflow audience may need extensions (`{How, What-tool, What-error}`).

The four-subspace edge partition is the *ideal v2* — v1 Lethe will almost certainly ship with fewer graphs (non-goal per `00-charter.md` §4.2).

## Gaps / hand-waves it introduces
- **No promotion/demotion criteria published.** Consolidation refines structure but the paper does not specify when an event is archived or downweighted.
- **Utility feedback absent.** Retrieval is policy-guided but there is no closed-loop signal that "this traversal helped" feeding back into the policy.
- **Multi-tenant / concurrency silent.** Single agent, single graph assumed.
- **"Dual-stream" is architecturally named but not quantitatively characterized.** How often does the slow path run? What are the gates? SCNS has a concrete answer (dream-gates); MAGMA does not.
- **Causal-graph ground truth.** The paper does not evaluate causal-graph quality independently of downstream retrieval accuracy — the edges could be wrong and the benchmark still pass.
