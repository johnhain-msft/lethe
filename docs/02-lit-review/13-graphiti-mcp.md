# 13 — Graphiti MCP Server (klaviyo mirror)

**URL:** https://github.com/klaviyo/graphiti_mcp  **Type:** repo (mirror / fork of getzep/graphiti)  **Fetched:** 2026-04-23

## Fetch status
**The klaviyo repo at this URL is a clone/mirror of `getzep/graphiti`** — README is textually near-identical to brief 12, same image assets, same installation / quickstart sections, same "Zep vs Graphiti" table. The MCP server referenced in both READMEs lives at `getzep/graphiti/mcp_server/` (or its mirror path `klaviyo/graphiti_mcp/mcp_server/`).

This brief therefore treats the *MCP server component inside Graphiti* as the actual source for source #13, which is what PLAN.md item #13 is really about ("Graphiti MCP server").

## Problem framing
Give MCP-speaking AI assistants (Claude, Cursor, other MCP clients) a **context-graph memory** they can call like a native tool. MCP is the standardized protocol; Graphiti is the engine; the MCP server is the bridge.

## Architecture
An MCP server sits in front of a Graphiti instance. Both READMEs list the same feature set:
- **Episode management** — add, retrieve, delete.
- **Entity management** — entity CRUD + relationship handling.
- **Semantic and hybrid search.**
- **Group management** — for organizing related data (multi-tenant-ish primitive).
- **Graph maintenance** operations.

Deployment: Dockerized alongside Neo4j. See `mcp_server/README.md` for tools + setup.

## Scoring / retrieval math
Inherits from Graphiti (brief 12) — hybrid semantic + BM25 + graph-traversal with graph-distance rerank.

## API surface — MCP tools
Exposed as MCP tools (exact tool names live in the mcp_server README, not the repo-root README). Behavior maps one-to-one to Graphiti's Python API: add_episode, search (edges / nodes), manage groups, manage entities, maintenance.

## Scale claims + evidence
Inherits Graphiti's numbers. The MCP layer itself is a thin protocol shim.

## Documented limits
All of Graphiti's limits (brief 12 §"Documented limits") apply. The MCP server adds:
- **Deployment-specific ops burden** — user has to run Neo4j + Graphiti server + MCP server + connect MCP client (Claude/Cursor/etc.) to them.
- **MCP-tool latency** includes protocol + network overhead on top of Graphiti's sub-second retrieval.
- **No Lethe-style runtime layer on top** — calling this from an agent gets you raw graph ops, not scoring / promotion / forgetting.

## Relation to Lethe
**Two concrete uses:**

1. **API-shape reference.** PLAN.md scope call #2 commits Lethe to any-MCP-client. Graphiti's MCP server is the closest-in-scope existing MCP memory service. Lethe's MCP tool set should learn from — but not duplicate — this surface. Specifically: Lethe's tools are higher-level (`remember` / `recall` / `promote` / `forget` / `peer_message`) operating over a runtime that may internally call Graphiti's lower-level tools. Graphiti MCP = plumbing; Lethe MCP = runtime.
2. **Existence proof.** Demonstrates that an MCP-over-graph-engine service is practical and already shipped. De-risks the deployment model for Lethe.

**Important boundary call:** Lethe does **not** become a superset of Graphiti's MCP server. Consumers who only want the graph primitives can use Graphiti's MCP directly. Lethe exists to add the runtime layer the graph engine deliberately doesn't provide (per brief 12 gaps + brief 14).

## Gaps / hand-waves it introduces
- **PLAN.md had two distinct repo URLs** for items 12 (`getzep/graphiti`) and 13 (`klaviyo/graphiti_mcp`). Inspection shows the klaviyo repo is a mirror, not an independent implementation — the MCP server is the same code as Graphiti's `mcp_server/` directory. This is itself a minor hand-wave in the PLAN; noted here for synthesis.
- **No independent klaviyo documentation.** Any customization klaviyo applied is not visible from the root README alone.
- **Tool inventory not in root README** — lives in `mcp_server/README.md`. WS6 API-surface design should fetch that before deciding on tool naming / overlap.
- **Group management** is introduced as a multi-tenant-ish primitive without the depth a real multi-tenant service needs (RBAC, quotas, isolation guarantees).
