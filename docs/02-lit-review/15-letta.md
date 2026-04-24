# 15 — Letta (formerly MemGPT)

**URL:** https://github.com/letta-ai/letta  **Type:** open-source + hosted platform (production MemGPT)  **Fetched:** 2026-04-23
**Docs:** https://docs.letta.com/guides/agents/memory, https://docs.letta.com/guides/agents/architectures/sleeptime
**Related paper:** sleep-time-compute (https://github.com/letta-ai/sleep-time-compute).
**License:** Apache-2.0 (server), proprietary cloud (api.letta.com).
**Lineage:** Letta = MemGPT (brief 11) productionized by the original authors.

## Problem framing
MemGPT (brief 11) proved LLM-as-OS as a research idea; Letta turns it into an agent platform with persistent state, memory tools the LLM calls directly, and background "sleep-time" agents that consolidate memory between turns. The framing:

> "When an LLM agent interacts with the world, it accumulates state — learned behaviors, facts, and memories. A stateful agent is one that can effectively manage this growing knowledge, maintaining consistent behavior while incorporating new experiences." — Letta docs, Memory.

Letta is the most direct precedent for Lethe's `remember/recall/promote/forget` API surface and for the dream-daemon pattern.

## Architecture
Four-concept model (verbatim from Letta docs):

| Concept | Role |
|---|---|
| **Agent** | System prompt + memory blocks + messages + tools. Stateful, persisted to DB. |
| **Memory blocks** | Labeled strings (`human`, `persona`, custom). Editable by the agent via memory tools. Attached blocks live in the system prompt. **Blocks can be shared** across agents. |
| **Messages** | In-context + out-of-context. All messages persisted; evicted ones still API-retrievable and searchable. |
| **Tools** | Server-side (sandboxed), MCP, or client-side. Includes memory-management tools the LLM calls. |
| **Runs + steps** | A single input → many sequential LLM-inference steps. |
| **Threads** | Independent message threads against the same agent — enables concurrent users on one agent. |

**Sleep-time agents** (the critical addition beyond MemGPT): a background agent associated with the primary agent, running on a cheaper model (Haiku-class), performing memory consolidation between conversations. Enabled via `enable_sleeptime=True`. Dedicated tool `memory_rethink` for asynchronous block rewrite; primary agent uses fast `memory_insert` / `memory_replace`.

## Scoring / retrieval math
Letta docs do not disclose a fixed retrieval score formula — retrieval is tool-mediated (agent calls `archival_memory_search` / `conversation_search`, underlying vector store returns matches). The scoring that *matters* for Lethe is the sleep-time consolidation decision: which blocks to merge, deduplicate, archive. The docs/community guide describe rules-of-thumb rather than a formula:
- Dedup every run.
- Light consolidation end-of-session.
- Full reorg weekly.
- Hierarchical rollup monthly.
- Block expiry tunable per type (session blocks 30d unless referenced; decision blocks never).

This is a **policy ladder**, not a scoring function — which is a design Lethe should borrow.

## API surface
Python + TypeScript SDKs. Hosted API (`api.letta.com`) with an API key. Key endpoints (from docs + README example):

```
POST   /v1/agents                        (create agent, with memory_blocks[])
POST   /v1/agents/{id}/messages          (send message, returns run + steps)
GET    /v1/agents/{id}/messages          (retrieve full history, incl. evicted)
PATCH  /v1/agents/{id}                   (update, incl. enable_sleeptime)
GET    /v1/blocks / POST /v1/blocks      (manage memory blocks; shareable)
```

Agent-side memory tools (the LLM calls these): `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`, `conversation_search`, `memory_rethink` (sleep-time only).

MCP: Letta exposes agent-as-MCP-server patterns but the primary surface is REST + SDK.

CLI: `@letta-ai/letta-code` (Node ≥18, `npm install -g`) — runs agents locally from terminal with skills + subagents.

## Scale claims + evidence
- Multi-thread: multiple users per agent without state-copy.
- All messages persisted and retrievable post-eviction — no context-window ceiling on recall.
- Model-agnostic; leaderboard at `leaderboard.letta.com` recommends Opus 4.5 / GPT-5.2 for best memory-task performance.
- No absolute throughput/latency numbers in docs at fetch time.
- Sleep-time-compute paper has companion repo with empirical numbers (not fetched in this brief; cite in WS3).

## Documented limits
- **Sleep-time cost.** Background agent = continuous inference = non-trivial token spend on a cheap model. Community guide flags: "not suited for simple, fast single-interaction tasks due to added background compute costs."
- **Block character limits.** Each block has a size cap set by the developer. Overflow requires explicit eviction to archival.
- **Shared blocks + concurrency.** Two agents writing the same block = merge conflicts the developer must resolve; docs don't specify a built-in merge strategy.
- **Model dependency for tool-use.** Smaller/weaker models fail the function-call memory loop (same structured-output constraint Graphiti has; brief 12).
- **Cloud coupling for easy mode.** Full SDK experience assumes `api.letta.com`; OSS self-host exists but loses the managed pieces.

## Relation to Lethe
Letta is the closest living implementation of what Lethe is planned to be. Direct-translation points:

1. **Memory-block = Lethe memory-item + visibility tag.** Shared blocks map to cross-agent memories; private blocks map to agent-local. Lethe's `scope` field (`00-charter.md`) serialises the same distinction.
2. **Sleep-time agent ≈ Lethe dream-daemon** (`01b-dream-daemon-design-note.md` §2). Confirms Lethe's scheduled-offline-job approach over MemGPT's per-call LLM-scheduled approach. Letta has already validated that this pattern ships.
3. **Policy ladder beats single formula.** Letta's "every run / end-of-session / weekly / monthly" cadence is exactly the `dream_levels` idea in the SCNS design note. Lethe should codify these levels as first-class (see WS3 composition design).
4. **All-messages-persisted** is a strong default. Lethe inherits: `forget` demotes visibility and score, it does not delete provenance (aligns with Graphiti's bi-temporal model, brief 12).
5. **`memory_rethink` = dream-daemon write path.** The primary agent does fast shallow writes; the background process does expensive deep rewrites. Lethe's runtime/substrate split can mirror this: runtime does `remember`, substrate consolidates.
6. **Shared-block concurrency gap is ours to solve.** Letta punts; Lethe must specify a merge/LWW/CRDT policy up front given multi-agent SCNS-style use.
7. **Don't re-implement Letta's agent runtime.** Lethe is a memory substrate + MCP surface. Letta is a full agent platform. Lethe layers under Letta, not beside it.

## Gaps / hand-waves it introduces
- **No formal utility-feedback loop.** Blocks are edited by heuristic (agent decision or cadence), not by measured retrieval success.
- **Sleep-time scheduling is thin.** `enable_sleeptime` is a boolean; the actual cadence, budget, and job-queueing are opaque.
- **No cross-agent consistency model.** Shared blocks + concurrent writers = developer problem.
- **No explicit benchmark number.** Letta claims stateful-agent superiority; published benchmark results (LongMemEval, DMR — briefs 18, 20) are in the companion leaderboard, not the README.
- **Cost model.** Sleep-time is "cheap model in background" but no accounting surface for budget caps.
- **Tenancy / isolation.** Threads exist; multi-tenant hard isolation is not documented.
- **Eviction policy for archival.** Insert is documented; archival-side decay / compaction is not.
