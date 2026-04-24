# Lethe — Plan for the Plan

A memory-runtime service for agent systems. Named for the river of forgetting: retention is a first-class operation, not an afterthought.

> **Scope of this doc:** the plan *for producing* the Lethe implementation plan. Not the v1 plan itself. Research deliverables gate the implementation plan; calendar does not.

---

## Resolved scope calls (2026-04-23)

| # | Decision |
|---|----------|
| 1 | **Repo:** new private GitHub repo `lethe`. `git init` fresh; not a package inside scns. SCNS will eventually consume Lethe as an external dependency. |
| 2 | **Audience for v1:** any MCP-speaking client. Designed from day one as a general-purpose service, not an SCNS-internal module that happens to be extracted. |
| 3 | **Org / IP:** MSFT owns via employment, no additional constraints — no special telemetry, review gates, or licensing rails. License choice is a product question (WS0), not a compliance one. |
| 4 | **Name:** Lethe. |
| 5 | **Hybrid approach = MAGMA-style architecture on proven substrates, not a new storage engine.** Lethe sits on top of existing solid implementations — **Graphiti (Zep's Apache-2.0 temporal graph engine) is the leading substrate candidate** per the PDF ("storage substrate you can build on"). MAGMA is the reference architecture. Markdown remains the human-readable surface for trackpad and synthesized knowledge pages. Lethe's value is the **runtime layer** — scoring, promotion/demotion, consolidation, intent-aware retrieval routing, MCP surface — that sits above substrate. The composition question is therefore: *which proven components (Graphiti / Letta / MS Agent Framework / qmd) do we depend on, and what does the Lethe runtime own on top of them?* |

---

## North star

> **Lethe is a true, practical solution to agent memory management.**

That phrase is doing real work. It rules out three lazy failure modes we could drift into:

- **"Wrapper over Graphiti"** — would make Lethe a thin storage adapter. The PDF explicitly rejects this ("Graphiti is the database, not the runtime"). Lethe is the runtime.
- **"Bag of best-practices"** — stitch a scorer from Cognitive Weave, a consolidator from Memory-as-Metabolism, an API from Letta, call it done. That's a survey paper, not a product. Integration is the value.
- **"Research artifact"** — if it isn't routinely usable by any MCP-speaking agent from the day v1 ships, it failed the "practical" test.

The planning phase succeeds when we can point at the architecture and say: *markdown, SQLite, embeddings, temporal index, and consolidation loop each earn their keep; none is redundant; none is missing; and the interfaces between them are spelled out.*

**SCNS's dream-daemon is an explicit candidate contribution**, not just legacy to audit. The offline-consolidation loop, tiered-consolidation, memory-entries lifecycle, priorities, gates, and housekeeping together encode a view of how agent memory *metabolizes over time*. That view aligns with Memory-as-Metabolism. If it holds up under WS1's audit + WS3's gap analysis, it likely becomes Lethe's consolidation spine — not because we built it, but because it's probably right. WS3 will evaluate it on merits.

---

## The real research thrust

The center of gravity for this planning phase is TWO questions, not one:

**A. The composition question.** How do markdown, SQLite metadata, vector embeddings, temporal/graph indices, and a consolidation loop (our dream-daemon or its successor) compose into one coherent runtime? What does each store own? Where are the write boundaries, read paths, invalidation rules, consistency guarantees, provenance links? This is the *true-practical-solution* question — nobody in the source material has answered it cleanly, because each paper/impl optimizes one component.

**B. The gap question.** Where do the gist, the PDF, and the cited papers under-specify, hand-wave over genuinely hard problems, or document scale limits we'd blow past?

Both must be answered before the implementation plan can be written.

### Known gaps & hand-waves to investigate

Compiled on first read of both sources. Non-exhaustive; WS2 will extend this list.

**From the Karpathy gist:**
- **Scale.** "Works surprisingly well at moderate scale (~100 sources, ~hundreds of pages)." No evidence for 10k+. Retrieval strategy (index.md + grep) degrades fast. qmd is mentioned but not validated at scale.
- **Single-user assumption.** No concurrency / lock / merge story. Lethe is multi-agent by design — this is a first-class problem.
- **Consolidation is human-driven.** User "guides" ingest. Agent swarms cannot — nobody's watching. What's the unattended equivalent?
- **Contradiction handling is informal.** "LLM flags it." No mechanism, no audit trail, no resolution SLA.
- **Provenance.** Implicit in frontmatter but not mandated. Lethe must enforce.
- **No privacy / secret-sanitization story.** We already have this in SCNS; how it interacts with a markdown store is open.
- **No ACID / durability story.** Crash mid-wiki-update = corrupt wiki. Fine for a personal knowledge base; unacceptable for a service.
- **Write amplification.** "A single source might touch 10–15 wiki pages." At agent-loop frequency this is a lot of diff churn — cost + rate-limit implications.

**From agent-memory-system-plan.pdf:**
- **Utility feedback is "hardest to capture but critical."** PDF flags this, does not solve it. Scoring function collapses without it. Genuinely open; needs a concrete v1 heuristic.
- **Scoring weights ratio.** "Weighting matters more than the individual signals." No numbers. No tuning protocol. No way to know when weights are wrong.
- **Promotion criteria.** Candidate signals enumerated ("repetition across sessions, user correction, task-completion-following-pattern, explicit flagging") but no formal threshold, no calibration, no false-positive budget.
- **Contradiction resolution beyond recency.** Called out as open research. PDF ships "invalidate but don't delete" — fine as v1, but what happens at conflict density > 1/week?
- **Intent classifier (MAGMA Phase 4).** What intents? What classifier? What failure mode? Zero implementation detail.
- **Cross-agent peer messaging.** Named as open problem. Lethe's audience is *agents talking to each other* — can't defer this as casually as the PDF does.
- **Forgetting as safety.** PDF cites this as an open problem. Lethe is *named* for it. Must engage.
- **Benchmark applicability.** LongMemEval and LoCoMo are conversational-memory benchmarks. Lethe is agent-workflow memory. The mapping is not 1:1; PDF hand-waves that "use them for sanity check, your own task set matters more." Our own task set needs a concrete design.
- **Eval-set construction.** PDF says "retrospectively annotate which memories would have been useful." Who annotates? How do we avoid annotator-bias confirming the heuristic we're designing?

---

## Workstreams

Nine workstreams. Each produces a concrete artifact under `docs/` in the `lethe` repo. Implementation plan is written only after all nine land.

### WS0 — Charter
- Project mission, scope, explicit non-goals, license choice (OSS vs open-core), positioning ("runtime over substrate").
- Record the resolved scope calls above.
- **Artifact:** `docs/00-charter.md`.

### WS1 — SCNS current-state audit + dream-daemon evaluation
Inventory every memory-shaped piece of SCNS so we know what we're copying out, and **evaluate the dream-daemon pattern on its own merits** as a candidate Lethe contribution.
- `src/memory/` (17 modules: vault, indexer, embeddings, search, taxonomy, archive-store, negative-memory, lessons, sentiment, core-file-generator, tag-rejections, chunker, db).
- `src/dream/` (12 modules: dream-daemon, consolidation, tiered-consolidation, memory-entries, extraction, dream-schema, dream-gates, priorities, scheduler, housekeeping) — **write up as a design document in its own right**: what problem each piece solves, where it works, where it breaks, how it maps to Memory-as-Metabolism and MAGMA dual-stream consolidation.
- `src/observe/` writers that feed memory.
- Broker tables with memory-shaped data (`shared_state`, `memory_entries`, `quality_checks`).
- Filesystem artifacts under `~/.scns/` (vault markdown, dream.db, daily logs, archive).
- Callers: `scns_memory_search`, `scns_memory_store`, `scns_suggestions`, brain/agent-loop, team-member prompts.
- Classify each piece as **short-term trackpad**, **long-term store**, **scoring/retrieval**, **consolidation/dream**, **suggestion surface**, or **candidate-for-Lethe**.
- **Artifact:** `docs/01-scns-memory-audit.md` + `docs/01b-dream-daemon-design-note.md` + component diagram.

### WS2 — Literature + reference-impl study *(exhaustive)*
Every source linked in the PDF and the Karpathy gist gets its own research brief. No skipping, no "we already know the gist." The mandate is: for each source extract scoring math, promotion/demotion criteria, API surface, failure modes, documented scale ceilings, and benchmark numbers — then add whatever that source surfaces to the gap list in the preamble.

Exhaustive source checklist (one brief per row, stored as `docs/02-lit-review/<nn>-<slug>.md`):

**Foundational papers (from the PDF):**
| # | Source | URL |
|---|---|---|
| 01 | Zep: A Temporal Knowledge Graph Architecture for Agent Memory | https://arxiv.org/abs/2501.13956 |
| 02 | MAGMA: Multi-Graph Agentic Memory Architecture | https://arxiv.org/html/2601.03236v2 |
| 03 | Graph-Based Agent Memory: A Complete Guide (Shibui walkthrough of MAGMA) | https://shibuiyusuke.medium.com/graph-based-agent-memory-a-complete-guide-to-structure-retrieval-and-evolution-6f91637ad078 |
| 04 | Memory as Metabolism | https://arxiv.org/html/2604.12034 |
| 05 | Cognitive Weave: Spatio-Temporal Resonance Graph | https://arxiv.org/html/2506.08098v1 |
| 06 | Agent Memory Paper List (survey repo; treat as ongoing feed) | https://github.com/Shichun-Liu/Agent-Memory-Paper-List |

**Papers named from the Agent Memory Paper List (call-outs in the PDF; plus whatever else the repo highlights at read time):**
| # | Source | Notes |
|---|---|---|
| 07 | MemOS | OS-like memory tiering |
| 08 | Hippocampus (agent-memory variant) | Episodic/semantic split |
| 09 | A-MEM | Agentic memory primitives |
| 10 | MemEvolve | Lifecycle/consolidation focus |
| 11 | MemGPT (original; underpins DMR benchmark) | Tiered memory + function-call API |

**Tools & reference implementations:**
| # | Source | URL |
|---|---|---|
| 12 | Graphiti (likely substrate dependency) | https://github.com/getzep/graphiti |
| 13 | Graphiti MCP server | https://github.com/klaviyo/graphiti_mcp |
| 14 | Graphiti issue #1300 — confirms missing promotion/demotion engine (our gap to fill) | (linked from PDF) |
| 15 | Letta / MemGPT | https://github.com/letta-ai/letta |
| 16 | Microsoft Agent Framework (1.0, March 2026) | https://github.com/microsoft/agent-framework |
| 17 | qmd — local hybrid BM25/vector/LLM-rerank search over markdown | https://github.com/tobi/qmd |

**Benchmarks (dedicated brief each; applicability to agent-workflow memory is itself a gap):**
| # | Source | Notes |
|---|---|---|
| 18 | LongMemEval | Long-horizon conversational memory |
| 19 | LoCoMo | Multi-hop reasoning + temporal tracking |
| 20 | DMR (Deep Memory Retrieval, from MemGPT paper) | Retrieval recall benchmark |

**Pattern reference:**
| # | Source | URL |
|---|---|---|
| 21 | Karpathy — wiki-as-knowledge-base pattern | https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f |

Each brief follows a uniform template (problem framing / architecture / scoring or retrieval math / API surface / scale claims + evidence / documented limits / how it relates to Lethe / gaps or hand-waves it introduces). The synthesis doc (`docs/02-synthesis.md`) then draws across all 21 to answer: *what does the field collectively know, where does it collectively hand-wave, and what does Lethe need to own that nobody else has solved?*

Treat the Agent Memory Paper List as a standing subscription — re-check before the implementation plan lands to catch any paper that dropped during the planning phase.

### WS3 — Gap deep-dives + composition design *(the new center of gravity)*
Two tracks run in this workstream.

**Track A — Composition design (question A).** Explicit design exploration of how markdown + SQLite + embeddings + graph/temporal + consolidation compose. Deliverable is a reference architecture with named stores, ownership rules, read/write paths, consistency model, provenance propagation, and failure-mode analysis. Evaluates multiple candidate topologies (markdown-primary with metadata sidecars; graph-primary with markdown projections; etc.) and recommends one with rationale.

**Track B — Gap briefs (question B).** For each gap identified in WS2 (seeded by the list above), produce a research brief: what the gap is, why it matters for Lethe, state of the art, candidate v1 approaches with trade-offs, recommendation + residual unknowns.

Prioritized gap deep-dives (first pass, will extend in WS2):
1. **Utility-feedback capture** — how do we observe retrieval success without asking agents to self-report?
2. **Scoring weight calibration** — protocol for tuning the recency/connectedness/utility ratio with evidence.
3. **Markdown at scale** — write amplification, concurrent writes from multi-agent swarm, crash consistency, retrieval cost >10k pages.
4. **Unattended consolidation** — no human in the loop, no browse-and-guide. *SCNS dream-daemon evaluated here as a candidate answer.*
5. **Cross-agent peer messaging** — how do subagents share "I learned X" without context pollution.
6. **Forgetting-as-safety** — preventing reinforcement of bad beliefs.
7. **Contradiction resolution beyond timestamp-invalidation.**
8. **Intent classifier design** — what intents, what mechanism, what fallback.
9. **Eval-set construction without confirmation bias.**

- **Artifacts:** `docs/03-composition-design.md` (Track A) + `docs/03-gaps/<nn>-<gap>.md` per gap (Track B). This is the thickest workstream.

### WS4 — Eval & benchmark plan
Per PDF Phase 1: measurement before optimization.
- Public benchmarks: LongMemEval, LoCoMo, DMR — inclusions *and* limitations (conversational vs agent-workflow mismatch).
- Lethe-native eval set: ~20 real tasks from SCNS session_store + retrospective annotation. Address annotator-bias concern from gap deep-dive #9.
- Metrics: precision@k, recall@k, latency p50/p99, context-budget adherence, suggestion false-positive rate, promotion precision.
- Shadow-retrieval harness (compute but don't surface; SCNS has partial infrastructure).
- **Artifact:** `docs/04-eval-plan.md` + runnable `scripts/eval/` skeleton.

### WS5 — Scoring function design
- Formalize recency-weighted-by-access, structural connectedness, utility feedback.
- Pull candidate math from Cognitive Weave (decay + residual baseline), Memory-as-Metabolism, Zep (bi-temporal invalidation), MAGMA (intent-routed weights).
- v1 heuristic + log signal for v2 learned scorer.
- **Artifact:** `docs/05-scoring-design.md` with formulas and tuning-knob table.

### WS6 — Service & API surface
MCP-first, any-MCP-client audience.
- Core surface: `remember`, `recall`, `promote`, `forget`, `peer_message`, plus consolidation/lint hooks.
- Transports: MCP primary; HTTP fallback; CLI.
- Multi-tenant? Per-user? Per-agent-swarm? Bring-your-own-storage? **Default: yes to BYO, tenant-scoped.**
- Auth, provenance enforcement, audit log.
- SCNS compatibility shim — SCNS calls Lethe, keeps running during transition.
- **Artifact:** `docs/06-api-surface.md` with MCP schema + OpenAPI.

### WS7 — Extraction & migration strategy
- **Phase A:** stand up `lethe` repo with copied (not cut) memory modules. SCNS keeps its own copy. No behavior change in SCNS.
- **Phase B:** SCNS calls Lethe via its API; legacy path stays behind a flag for rollback.
- **Phase C:** SCNS deletes the legacy path once Lethe has soaked.
- Data migration: `~/.scns/memory` → Lethe storage root with backwards-compatible import.
- Risk register + rollback plan.
- **Artifact:** `docs/07-migration.md` with phase gating checklist.

### WS8 — Non-goals & deferred research
Explicit v1 exclusions:
- Full multi-graph MAGMA architecture (v2).
- Learned promotion classifier (heuristic v1, log for RL later).
- Semantic-merge conflict resolution (timestamp + invalidate, audit-preserving for v1).
- Rich peer-messaging protocol (minimal v1).
- **Artifact:** `docs/08-non-goals.md`.

---

## Deliverables of this planning phase

1. `docs/00-charter.md` through `08-non-goals.md`.
2. Populated gap deep-dives under `docs/03-gaps/`.
3. Runnable eval-harness skeleton (no-op stubs, real later).
4. **Implementation plan** (`docs/IMPLEMENTATION.md`) — enumerates phased work with file-level changes. Written only after WS0–WS8 land.
5. Go / no-go recommendation.

---

## Sequencing

```
WS0 (charter) ─┐
               ├── WS1 (audit)        ──┐
WS2 (lit)   ───┤                        ├── WS5 (scoring) ──┐
               └── WS3 (gaps) ──────────┤                   ├── WS6 (API) ──┐
                                        └── WS4 (eval)   ───┘               ├── WS7 (migration) ──> IMPLEMENTATION.md
                                                                            │
                                                           WS8 (non-goals) ─┘
```

WS0, WS1, WS2 can start in parallel. WS3 begins as soon as WS2 produces its first few reviews. WS4/WS5 gate on WS3. WS6+WS7+WS8 gate on WS4+WS5. Implementation plan gates on all nine.

No dates. Gate on artifacts.

---

## Initial repo setup (for the next session)

```sh
cd ~/Coding_Projects/lethe
git init
mkdir -p docs/02-lit-review docs/03-gaps scripts/eval
# Move this file to docs/PLAN.md or keep as PLAN.md at root
# Create a GitHub private repo: gh repo create lethe --private --source=. --push
```
