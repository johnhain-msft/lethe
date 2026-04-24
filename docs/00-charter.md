# 00 — Lethe Charter

**Status:** ratified 2026-04-23 from `PLAN.md` scope resolution.
**Audience:** every subsequent workstream traces decisions back to this doc.

---

## 1. Mission

**Lethe is a memory-runtime service for agent systems.**

Named for the river of forgetting — retention is a first-class operation, not an afterthought. Most "agent memory" projects optimize for *remembering*; Lethe treats *what to stop remembering, when, and safely* as an equal citizen of the API.

The planning phase succeeds when we can point at the architecture and say: *markdown, SQLite, embeddings, temporal index, and consolidation loop each earn their keep; none is redundant; none is missing; and the interfaces between them are spelled out.*

## 2. North star

> **Lethe is a true, practical solution to agent memory management.**

That phrase is load-bearing. It rules out three failure modes we could drift into:

1. **"Wrapper over Graphiti."** A thin storage adapter around Zep's temporal graph engine. The source PDF explicitly rejects this: *Graphiti is the database, not the runtime.* Lethe is the runtime.
2. **"Bag of best-practices."** Stitch a scorer from Cognitive Weave, a consolidator from Memory-as-Metabolism, an API from Letta, and call it done. That's a survey paper, not a product. Integration is the value.
3. **"Research artifact."** If Lethe is not routinely usable by any MCP-speaking agent the day v1 ships, it failed the *practical* test.

"Practical" means: installable, documented, benchmarked, with a migration story, a license that permits adoption, and an API that a dev can learn in an afternoon.

## 3. Positioning — runtime over substrate

Lethe does **not** implement a new storage engine. Lethe is the runtime layer that sits above proven substrates.

| Layer | Owned by | Candidate components |
|---|---|---|
| Substrate (storage) | External dependency | **Graphiti** (Zep, Apache-2.0 temporal graph); SQLite; filesystem for markdown; embedding store (sqlite-vec / pgvector / equivalent) |
| Runtime (Lethe) | **This project** | Scoring, promotion/demotion, consolidation (dream-daemon candidate), intent-aware retrieval routing, provenance enforcement, MCP surface, eval harness |
| Surface | Consumer of Lethe | MCP clients, CLI, HTTP fallback; markdown remains the human-readable surface for trackpad + synthesized knowledge pages |

The composition question — *which substrates do we depend on, and what does Lethe own on top of them?* — is the subject of WS3 Track A. This charter only commits to the positioning: **runtime, not storage.**

## 4. Scope

### 4.1 In scope (v1)

- **MCP-first service.** Any MCP-speaking client is a first-class consumer. HTTP fallback + CLI come free.
- **Multi-agent from day one.** Concurrent writes, peer messaging (minimal), tenant scoping.
- **Bring-your-own storage (BYO).** Tenant-scoped storage root; default bundled (SQLite + markdown + embedding store) for the zero-config path.
- **Provenance enforcement.** Every memory has a traceable origin; retrieval carries provenance through.
- **Core API surface.** `remember`, `recall`, `promote`, `forget`, `peer_message`, plus consolidation / lint hooks.
- **Retention as first-class.** Promotion, demotion, consolidation, and safe forgetting are API-level operations, not cron jobs.
- **Heuristic scoring v1.** Recency-weighted-by-access + structural connectedness + utility feedback. Log signals for a v2 learned scorer.
- **Unattended consolidation.** No human in the loop. (SCNS's dream-daemon pattern evaluated as the candidate spine in WS1/WS3.)
- **Eval harness.** Public benchmarks (LongMemEval, LoCoMo, DMR) + Lethe-native task set from SCNS history. Shadow-retrieval mode.
- **SCNS compatibility shim.** SCNS calls Lethe through its API; legacy path behind a flag during transition.

### 4.2 Out of scope (explicit non-goals for v1 — detailed in WS8)

- **Full multi-graph MAGMA architecture.** v1 ships with a simpler topology; multi-graph is a v2 research target.
- **Learned promotion classifier.** v1 uses a heuristic with logged signals; a supervised/RL classifier is v2.
- **Semantic-merge conflict resolution.** v1 uses timestamp-invalidation with audit trail (à la Zep bi-temporal). Semantic merge is open research.
- **Rich peer-messaging protocol.** v1 ships the minimum primitive ("I learned X, here's the provenance"); a full protocol (negotiation, conflict, trust) is deferred.
- **Being a storage engine.** Lethe does not implement a new database. If a gap forces us to, that's a design failure to revisit the substrate choice, not a license to ship one.
- **Being a framework.** Lethe is a service with an API. It is not a library that takes over your agent loop.
- **Being a UI.** Markdown is the human surface; Lethe provides the data and the hooks. A wiki/browser is a separate product if anyone builds one.

## 5. License

### 5.1 Constraints

- **IP is MSFT-owned** via the author's employment. No additional telemetry, review-gate, or licensing constraints imposed by the employer.
- License choice is therefore a **product question**, not a compliance one.

### 5.2 Options considered

| Option | Argument for | Argument against |
|---|---|---|
| **Apache-2.0** | Matches Graphiti (leading substrate candidate); permissive enough for broad adoption including commercial MCP clients; includes explicit patent grant — non-trivial given employment-owned IP. | None material. |
| **MIT** | Simplest, most familiar. | No explicit patent grant. Given MSFT authorship, the Apache patent clause is a feature, not a cost. |
| **AGPL-3.0** | Protects against closed-source forks. | Poisonous to the MCP-client audience. A memory service embedded in a proprietary agent under AGPL is effectively unadoptable. Kills the "practical" test. |
| **Open-core** (OSS core + commercial add-ons) | Preserves a commercial path if the project grows. | Premature. Adds governance overhead before the v1 architecture is even proven. Can be revisited post-v1 if warranted. |
| **Source-available (BSL, PolyForm, etc.)** | Middle ground. | Same adoption friction as AGPL for the MCP-client audience, without its FSF-approval benefits. |

### 5.3 Recommendation

**Apache-2.0.** Decision rationale:

1. **Substrate alignment.** The leading substrate candidate (Graphiti) is Apache-2.0. Staying in the same license family eliminates a class of licensing-compatibility questions.
2. **Patent grant.** With MSFT-owned IP sitting under the author's commits, Apache's explicit patent grant is the correct default — it gives downstream adopters the clarity MIT cannot.
3. **Adoption surface.** MCP clients will include commercial products. Apache is the strongest "yes, you can ship this inside your product" signal.
4. **Reversibility.** Going from Apache to a more restrictive license later is hard but not impossible; going from AGPL/BSL to Apache later is trivial. We can tighten, not loosen.

**Final decision deferred to repo-root `LICENSE` commit** — this charter records the recommendation. If the decision changes, update this section with the rationale.

## 6. The 5 resolved scope calls (2026-04-23)

Recorded verbatim from `PLAN.md` for durability inside the repo.

| # | Decision |
|---|----------|
| 1 | **Repo:** new private GitHub repo `lethe`. `git init` fresh; not a package inside SCNS. SCNS will eventually consume Lethe as an external dependency. |
| 2 | **Audience for v1:** any MCP-speaking client. Designed from day one as a general-purpose service, not an SCNS-internal module that happens to be extracted. |
| 3 | **Org / IP:** MSFT owns via employment, no additional constraints — no special telemetry, review gates, or licensing rails. License choice is a product question (WS0), not a compliance one. |
| 4 | **Name:** Lethe. |
| 5 | **Hybrid approach = MAGMA-style architecture on proven substrates, not a new storage engine.** Lethe sits on top of existing solid implementations — **Graphiti (Zep's Apache-2.0 temporal graph engine) is the leading substrate candidate** per the PDF ("storage substrate you can build on"). MAGMA is the reference architecture. Markdown remains the human-readable surface for trackpad and synthesized knowledge pages. Lethe's value is the **runtime layer** — scoring, promotion/demotion, consolidation, intent-aware retrieval routing, MCP surface — that sits above substrate. The composition question is therefore: *which proven components (Graphiti / Letta / MS Agent Framework / qmd) do we depend on, and what does the Lethe runtime own on top of them?* |

## 7. Success criteria for the planning phase

Planning succeeds when, at the end of WS0–WS8, a reader can:

1. Name every external dependency Lethe takes and why.
2. Name every component Lethe owns and why it is not the substrate's responsibility.
3. Point to a scoring function with numbers and a tuning protocol.
4. Point to a consolidation loop with a failure-mode analysis.
5. Point to an eval harness with a benchmark matrix and an acknowledged applicability gap (conversational-memory benchmarks vs. agent-workflow memory).
6. Read a migration plan that lets SCNS adopt Lethe with a rollback path.
7. Read a non-goals list long enough to make the scope credible.

If any of these is missing, the implementation plan is premature.

## 8. Governance (lightweight)

- **Private repo** during planning phase. Open-source after v1 charter review, under the license above.
- **One maintainer** (the author) during planning; contribution governance documented post-v1.
- **Artifacts are the source of truth.** No decision counts until it lands in `docs/` with a commit.
- **No dates.** Gate on artifacts, not calendar. (Per `PLAN.md`.)

## 9. Change log

- **2026-04-23** — Ratified from `PLAN.md` scope resolution. First commit.
