# 12 — Graphiti

**URL:** https://github.com/getzep/graphiti  **Type:** open-source repo (temporal context-graph engine)  **Fetched:** 2026-04-23
**License:** Apache-2.0 (Zep/getzep).
**Paper:** underpins Zep (brief 01, arXiv:2501.13956).

## Problem framing
Traditional RAG is batch-oriented and assumes static data. Graphiti is purpose-built for **dynamic, frequently-updated data** — agent interactions, business data, external streams — and for answering queries at any *point in time*, not just "what is true now."

## Architecture — a temporal **context graph**
Three primitive concepts (verbatim from the README):

| Component | What it stores |
|---|---|
| **Entities** (nodes) | People, products, policies, concepts — with summaries that evolve over time. |
| **Facts / Relationships** (edges) | Triplets `(Entity → Relationship → Entity)` with **temporal validity windows**. |
| **Episodes** (provenance) | Raw data as ingested — the ground-truth stream. Every derived fact traces back to an episode. |
| **Custom Types** (ontology) | Developer-defined entity + edge types via Pydantic models. |

Two-dimensional time model — **bi-temporal**:
- *Valid time* — when a fact was true in the world.
- *Ingestion / transaction time* — when the system learned about it.

## Scoring / retrieval math — hybrid retrieval
Combines three signals:
1. **Semantic** — embedding similarity.
2. **Keyword** — BM25.
3. **Graph traversal** — relationship walk (+ graph-distance re-ranking per quickstart example).

No single set of weights disclosed in the README; "hybrid" is the contract, tuning is the user's job. README explicitly mentions **"reranking search results using graph distance"** as one of six quickstart behaviors.

## API surface
- Python lib: `graphiti-core` (pip / uv). Python ≥ 3.10.
- Backends supported: **Neo4j 5.26**, **FalkorDB 1.1.2**, **Kuzu 0.11.2**, **Amazon Neptune** (+ OpenSearch Serverless for full-text).
- Graph drivers pluggable via `Graphiti(graph_driver=...)` (since v0.17.0).
- Quickstart demonstrates: connect → init indices → `add_episode` (text or JSON) → `search` (edges, hybrid) → graph-distance rerank → search recipes (nodes).
- **MCP server** under `mcp_server/` — episode management, entity management, semantic/hybrid search, group management, graph maintenance (see brief 13).
- **REST service** under `server/` (FastAPI).
- LLM extras: OpenAI (default), Anthropic, Groq, Google Gemini. **"Works best with LLM services that support Structured Output"** — smaller models fail ingestion.

### Concurrency
- `SEMAPHORE_LIMIT` env var defaults to **10** concurrent ops. Low default to avoid 429s from LLM providers. Tuneable up or down. Document in Lethe's ops guide.

## Scale claims + evidence
From the README + paper (brief 01):
- **Sub-200 ms retrieval** at scale *on the managed Zep platform* (not necessarily on self-hosted Graphiti).
- "Typically sub-second latency" for self-hosted Graphiti.
- Backend Neo4j is production-proven; FalkorDB/Kuzu/Neptune offer alternative scale profiles.
- DMR: 94.8 %. LongMemEval: +18.5 % over baseline. (Both from the paper, not the repo.)

Graphiti-vs-GraphRAG table asserts "High scalability, optimized for large datasets." No absolute node/edge counts in the README.

## Documented limits — explicit + implicit
- **Structured-output requirement.** Ingestion fails with models that don't support structured output cleanly.
- **Concurrency capped at SEMAPHORE_LIMIT** (LLM rate-limit protection).
- **Self-hosted requires operating the surrounding system** — no dashboard, no user/conversation management, no built-in SLAs. The README's "Zep vs Graphiti" table is explicit about this.
- **LLM-extraction-dependent** — graph fidelity inherits LLM correctness.
- **Graph DB dependency** is heavy — Neo4j / Neptune / etc. are not trivial ops burdens.

## Relation to Lethe
**The leading substrate candidate (per PLAN.md scope call #5).** Concrete Lethe decisions Graphiti informs:

1. **License alignment.** Apache-2.0 → Lethe's charter recommendation matches (`00-charter.md` §5.3). Clean licensing story.
2. **Bi-temporal invalidation is the right contradiction-resolution default.** Replaces SCNS's name-keyed LWW (`01b-dream-daemon-design-note.md` §2.6). Facts don't get deleted — they get `valid_to`-stamped. Preserves audit trail, supports "what did I know on X date" queries, handles contradiction density gracefully.
3. **Episodes = provenance.** Matches Lethe's provenance-enforcement requirement from `00-charter.md` §4.1. Every Lethe memory must trace to an episode. Graphiti already has the primitive.
4. **Hybrid retrieval (semantic + BM25 + graph) is Lethe's default retrieval shape.** SCNS already does semantic + BM25 (see audit §1, `memory/search.ts` at 0.7/0.3 weights). Graphiti adds graph traversal + graph-distance rerank as native operations.
5. **Structured-output LLM dependency** is an operational constraint Lethe inherits. Must document + enforce in deployment defaults.
6. **MCP server already exists** (brief 13). Lethe's MCP surface composes above this rather than duplicating it.

## Gaps / hand-waves it introduces (promotion/demotion — the WS3 anchor)
- **No promotion / demotion engine.** Graphiti ingests and retrieves; it does *not* decide when to prune, archive, or promote. This is exactly the gap Lethe owns. See brief 14 (issue #1300).
- **No utility-feedback loop.** Facts can get invalidated (bi-temporal) but not re-scored based on retrieval success.
- **No consolidation / synthesis.** Episodes → facts is the ingest path, but multi-episode synthesis (à la SCNS weekly/monthly rollup) is the caller's problem.
- **Hybrid weights are not tuned, not published.** The README says "hybrid"; the actual weighting of semantic/BM25/graph is user-chosen.
- **Scale ceiling not quantified** beyond "optimized for large datasets." No documented node-count or query-rate ceiling.
- **Graph-backend trade-offs not characterized.** Neo4j vs FalkorDB vs Kuzu vs Neptune — the README lists them but doesn't say when to prefer which.
- **Ontology evolution.** Custom types via Pydantic are defined at init. Migration of types when the agent domain shifts is not addressed.
- **Heavy ops burden** for self-hosted: Neo4j / Neptune + OpenSearch Serverless + LLM provider with structured-output support.
