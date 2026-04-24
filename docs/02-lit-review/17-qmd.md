# 17 — QMD (Query Markup Documents)

**URL:** https://github.com/tobi/qmd  **Type:** open-source CLI + MCP server (on-device search engine)  **Fetched:** 2026-04-23
**Author:** Tobi Lütke (`tobi`) — Shopify CEO; personal tool, pattern-reference quality.
**Install:** `npm install -g @tobilu/qmd` (Node or Bun).
**Runtime:** node-llama-cpp + local GGUF models. Fully on-device.

## Problem framing
> "An on-device search engine for everything you need to remember. Index your markdown notes, meeting transcripts, documentation, and knowledge bases. Search with keywords or natural language. Ideal for your agentic flows."

The framing is notable for what it does *not* claim: no memory lifecycle, no consolidation, no learning. QMD owns the **retrieval** problem and punts everything else to the filesystem. The interesting design move is **collections + contexts-as-a-tree** for LLM-friendly ranking.

## Architecture
Four components:
1. **Collections** — named source trees of markdown files (`qmd collection add ~/notes --name notes`).
2. **Context tree** — human-authored descriptive strings attached to paths (`qmd://notes`, `qmd://meetings`). Returned alongside matching sub-documents so the LLM gets hierarchical context. **This is QMD's distinctive contribution.**
3. **Index** — SQLite (`my-index.sqlite`) holding BM25 + embeddings (generated via `qmd embed`).
4. **Query pipeline** — three modes:
   - `search` — BM25 full-text (fast keyword).
   - `vsearch` — vector semantic search.
   - `query` — hybrid: typed sub-queries (lex / vec / HyDE) combined via **Reciprocal Rank Fusion (RRF)** + LLM **re-ranking**. Marketed as "best quality."

All three use the same local llama-cpp inference path. No external services. No cloud.

## Scoring / retrieval math
- **Lexical:** BM25 (SQLite FTS5-class).
- **Vector:** cosine over GGUF-model embeddings.
- **HyDE:** Hypothetical Document Embeddings — LLM expands the query into a plausible answer doc, embeds that, retrieves.
- **Fusion:** Reciprocal Rank Fusion over the sub-query results.
- **Re-rank:** LLM pass scoring candidate docs against the query (the "--min-score 0.3" threshold is on this pass).
- **Context injection:** matching documents are returned *with their ancestor context strings* — the LLM sees "this came from `qmd://meetings` which is *Meeting transcripts and notes*" alongside each hit.

Exact RRF constant and LLM-reranker model are repo-readable but not surfaced in the README. Practical shape matches the now-standard hybrid-retrieval stack (Graphiti, SCNS, Zep all converge here).

## API surface
**CLI** (primary):
```
qmd collection add <path> --name <name>
qmd context add <qmd-uri> <description>
qmd embed
qmd search "…"         # BM25
qmd vsearch "…"        # vector
qmd query "…"          # hybrid + rerank
qmd get <path|#docid>  # single doc
qmd multi-get <glob>   # batch
qmd status
qmd mcp [--http] [--daemon] [--port N]
```

Output flags for agents: `--json`, `--files`, `--all`, `--min-score`.

**MCP tools** exposed: `query`, `get`, `multi_get`, `status`. Deploy via stdio (default) or HTTP (stateless `POST /mcp` + `GET /health`), supporting a long-lived shared server so LLM models stay loaded in VRAM across requests (~1s idle-context reload, model itself stays hot).

**SDK:** `@tobilu/qmd` as a library — `createStore({ dbPath, config: { collections } })` → `store.search({ query, … })`.

## Scale claims + evidence
- Stated scope: "markdown notes, meeting transcripts, documentation, knowledge bases" — personal-scale to small-team.
- HTTP daemon optimization claim: "LLM models stay loaded in VRAM across requests. Embedding/reranking contexts are disposed after 5 min idle and transparently recreated on the next request (~1s penalty)."
- No published corpus-size / latency benchmarks. The architectural choices (SQLite + local llama-cpp) imply a single-user-to-small-team ceiling.

## Documented limits
- **Markdown-centric.** Non-markdown sources require a pre-processing step (CHANGELOG mentions adapters; main README is markdown-only).
- **No write-path for the LLM.** QMD indexes what the filesystem holds. Agents read, not write. There is no `remember` equivalent.
- **No retention policy.** The index is whatever the filesystem is. Garbage collection = user deletes files.
- **No provenance graph.** You know which *file* a fact came from; you don't know which *episode* or *conversation* introduced it.
- **Single-user assumption.** SQLite index, local daemon. No tenancy model.
- **Embedding model is local GGUF only** — no swap-in of proprietary embeddings.

## Relation to Lethe
QMD is a **pattern reference**, not a substrate candidate. Reasons it matters to Lethe:

1. **Context-tree pattern.** The idea of attaching **human-authored context strings to collection paths** and returning them with every hit is cheap, powerful, and missing from Graphiti, Letta, and SCNS. Lethe should adopt: each scope/namespace/tag can carry a descriptive string, surfaced with results. This closes the "why is this result relevant" gap at near-zero cost.
2. **Hybrid retrieval math converges with Graphiti and SCNS.** BM25 + vector + rerank is the de-facto standard. QMD validates the shape on personal-scale; Graphiti validates at production scale; Lethe inherits the shape.
3. **HyDE sub-query is cheap to add.** SCNS currently does semantic + BM25 (audit §1); QMD shows HyDE is a drop-in third lane. Worth a WS3 gap brief.
4. **MCP-server-as-primary-surface.** QMD's MCP tool set (`query / get / multi_get / status`) is close to the **minimal agent retrieval API**. Lethe's MCP surface should ship at least this, then add `remember / promote / forget`.
5. **Not a substrate.** QMD has no lifecycle, no writes, no tenancy. Lethe does not build *over* QMD; it borrows its ideas.
6. **Hot-model HTTP daemon pattern** is a good default for any local Lethe deployment.
7. **On-device-first is a deployment mode to preserve.** Lethe shouldn't make cloud-dependence mandatory. QMD's stdio-MCP single-binary path should remain possible for Lethe too.

## Gaps / hand-waves it introduces
- **No learning from usage.** Hit/miss data is never fed back into ranking.
- **No consolidation.** Notes accumulate forever; user manages their filesystem.
- **Re-rank model choice is opaque in the README.** Quality depends heavily on which local GGUF is used.
- **Single-tenant by design.** Cannot model "agent A's memories" vs "agent B's memories" without separate collections.
- **HyDE expense unquantified.** LLM-in-the-query-path doubles compute per search; no cost numbers.
- **Context strings are human-authored.** Scales poorly; there's no auto-generation path.
- **No benchmark numbers.** Personal-tool quality; no LongMemEval / LoCoMo evidence.
