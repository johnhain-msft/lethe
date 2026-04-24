# 11 — MemGPT: Towards LLMs as Operating Systems

**URL:** https://arxiv.org/abs/2310.08560  **Type:** paper  **Fetched:** 2026-04-23
**Author:** Packer et al. arXiv:2310.08560v2 (Feb 2024).
**Code:** https://research.memgpt.ai (now folded into Letta — see brief 15).

## Problem framing
LLMs are constrained by limited context windows. Extended conversations and document analysis blow the window. MemGPT proposes **virtual context management** borrowed from hierarchical memory systems in traditional OSes: move data between fast memory (the prompt) and slow memory (external store).

This is the foundational OS-as-metaphor paper that MemOS (brief 07) later generalizes. Underpins the **DMR (Deep Memory Retrieval) benchmark** (brief 20).

## Architecture — virtual context management
Key components:
- **Main context** (the LLM's context window) — the "fast" tier. Includes a system prompt, FIFO message buffer, and an editable *core memory* block.
- **External context** — the "slow" tier, split into **recall memory** (all past message history) and **archival memory** (arbitrary long-term store).
- **Function-call API** — MemGPT gives the LLM explicit tools to *move data between tiers*: `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`, `conversation_search`, etc. The LLM is the OS.
- **Interrupts** — manage control flow between MemGPT and the user (e.g., pause when the LLM requests a memory fetch).

## Scoring / retrieval math
Retrieval is LLM-function-call-driven, not scored. When the agent needs memory, it calls `archival_memory_search` or `conversation_search` and the external store returns matches (embedding similarity under the hood). There is **no intrinsic scoring function over memories** — the LLM's decisions drive access.

## API surface — the function-call set
The five to ~ten functions the LLM can call to manage memory are the defining API. This is the shape Letta (brief 15) productionizes.

## Scale claims + evidence
- Evaluated on two domains: **document analysis** (documents far exceeding context window) and **multi-session chat** (agents that remember across sessions).
- Set the original **DMR benchmark** (brief 20). Later beaten by Zep (brief 01, 94.8 % vs MemGPT 93.4 %) — a small margin.
- No numeric scale claims in the abstract beyond "far exceeds context window."

## Documented limits
Not surfaced in the abstract. Known from follow-up literature:
- **Per-query LLM calls for memory movement are expensive** (many round-trips).
- **The LLM may choose suboptimal memory ops** — it's the "scheduler" but has no training signal for scheduling.
- **Recency bias** of the FIFO buffer conflicts with selective recall.

## Relation to Lethe
**Historical anchor; direct ancestor of Letta (brief 15) which is in Lethe's API-surface reference set.** Contributions to Lethe:

1. **The function-call-as-memory-API pattern** is the MCP-tool model. Lethe's `remember`/`recall`/`promote`/`forget` surface is philosophically the MemGPT function-call model generalized beyond conversational memory.
2. **Two-tier architecture** (fast prompt + slow external) is the simplest version of the multi-tier models that later papers (MemOS, Cognitive Weave, MAGMA) elaborate. Lethe's substrate/runtime split is at right angles to this: MemGPT's slow tier *is* Lethe's substrate.
3. **LLM-as-scheduler is not recommended for Lethe.** MemGPT's design hands memory-movement decisions to the LLM. The dream-daemon pattern (SCNS) hands them to a scheduled offline process. Lethe should go dream-daemon, not MemGPT-function-call, for the demotion/promotion decisions — because unattended multi-agent workflows need deterministic eviction, not per-call LLM creativity. See `01b-dream-daemon-design-note.md` §4 for the rationale.
4. **DMR benchmark ownership.** Because MemGPT introduced DMR, and Zep outperforms MemGPT on it by 1.4 pts, DMR is now a crowded benchmark near ceiling. WS4 should use DMR for sanity-check only, not as a primary metric — see brief 20.

## Gaps / hand-waves it introduces
- **No intrinsic scoring.** Every retrieval decision is LLM-mediated. Makes the system hard to tune without prompting the agent.
- **Crash-safety of the virtual-memory model** — what happens if the LLM crashes mid-memory-op? Not discussed in the abstract.
- **Multi-tenant concurrency silent.**
- **Cost-per-conversation.** OS-style function-call loops for every memory op compound quickly in tokens.
- **Benchmark is conversational** (DMR + multi-session chat). Does not transfer cleanly to agent-workflow tasks.
- **LLM-as-OS is a metaphor, not an implementation.** The paper delivers a subset of OS primitives (paging-like, interrupts) but doesn't deliver process isolation, scheduling fairness, memory-protection — the hard parts.
