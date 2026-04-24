# 02 — Synthesis across the 21-brief lit review

**Scope:** cross-cuts all 21 briefs in `docs/02-lit-review/`. Answers three questions PLAN.md §WS2 poses:
1. *What does the field collectively know?* — §1.
2. *Where does it collectively hand-wave?* — §2.
3. *What must Lethe own that nobody else has solved?* — §3.

Plus: §4 unreachable sources, §5 hand-off hooks into WS3.

---

## 1. What the field collectively knows

### 1.1 Convergence on temporal knowledge graphs as the substrate

Briefs **01 Zep**, **02 MAGMA**, **05 Cognitive Weave**, **08 HippoRAG**, **12 Graphiti**, **13 Graphiti MCP** all converge on the same shape: **typed-entity nodes + typed-edge relationships + a temporal index**, retrieved by hybrid (semantic + lexical + graph-walk) scoring. The variations are edge taxonomy (MAGMA partitions into Temporal/Causal/Semantic/Entity; Cognitive Weave uses "Relational Strands"; Graphiti keeps one unified edge set with bi-temporal validity) and traversal primitive (HippoRAG picks Personalized PageRank; Graphiti picks graph-distance rerank). **The foundational shape is settled.** Lethe does not need to invent a substrate; it picks one.

### 1.2 Bi-temporal invalidation beats delete-on-contradict

**Brief 01 Zep**, **brief 12 Graphiti**, and **brief 05 Cognitive Weave** all stamp contradicted facts with an end-of-validity timestamp rather than deleting them. This preserves audit, enables "what did we know on date T" queries, and handles contradiction density without thrashing. It is the cross-paper consensus replacement for SCNS's name-keyed last-write-wins (`01b-dream-daemon-design-note.md` §2.6).

### 1.3 Async consolidation is the dominant write-path pattern

**MAGMA** (dual-stream: Synaptic Ingestion + Asynchronous Consolidation), **Letta** (sleep-time agents + `memory_rethink`), **Memory-as-Metabolism** (scheduled CONSOLIDATE + AUDIT), **SCNS** (dream-daemon; brief audited in `01-scns-memory-audit.md`), **Cognitive Weave** (Cognitive Refinement), **A-MEM** (link-on-ingest + evolution), **HippoRAG** (pre-extract, query-cheap) all separate the **fast write path** from the **slow consolidation path**. This is now a cross-paper near-consensus: the expensive memory work happens off-line, not on the critical path. Lethe inherits this by construction.

### 1.4 Hybrid retrieval is the standard

BM25 + vector + optional rerank. **QMD** (brief 17) does it on-device with RRF + LLM rerank; **Graphiti** does it at scale with graph-distance; **SCNS** already does semantic+BM25 at 0.7/0.3 weights (audit §1). The unanswered question is *which weights* — no paper publishes tuned values.

### 1.5 Function-call / tool-call is the agent-facing memory API

**MemGPT** (brief 11) established the pattern: `core_memory_append`, `archival_memory_search`, `conversation_search` — LLM-callable. **Letta** (brief 15) productionizes it; **MS Agent Framework** (brief 16) generalizes to `AIContextProvider`; **Graphiti MCP** (brief 13) and **QMD** (brief 17) expose a tool surface to MCP clients. MCP tools are the public shape. **Lethe's MCP surface is the product surface.**

### 1.6 Three memory benchmarks form the eval set, at known saturation levels

- **DMR** (brief 20) — saturated at 93–95 %. Sanity check only.
- **LongMemEval** (brief 18) — five abilities (extraction / multi-session reasoning / temporal / knowledge updates / abstention). Modern systems drop ≥30 pts vs. short-context. Primary WS4 metric.
- **LoCoMo** (brief 19) — long-horizon multi-session coherence, multi-modal, human-verified. Secondary WS4. **LoCoMo-Plus** (2602.10715) extends into non-factual memory (goals, implicit values).

### 1.7 Taxonomic vocabulary is emerging

**Brief 06 paper-list + survey** gives Form/Function/Dynamics (token-level vs parametric vs latent × factual vs experiential vs working × formation vs evolution vs retrieval). **Brief 10 MemEvolve / EvolveLab** distills 12 systems into four verbs — `encode / store / retrieve / manage`. Lethe's `remember / recall / promote / forget` maps 1:1 onto `manage` being split into `promote`+`forget`. Using EvolveLab vocabulary aligns Lethe with the broadest existing unification.

### 1.8 The dream-daemon / sleep-time pattern has shipped in production

**Letta's `enable_sleeptime=true`** is live. The SCNS dream-daemon is live on JH's personal stack. Community best-practice (from Letta forum, summarized in brief 15) already specifies a **policy ladder**: dedup every run / light consolidation end-of-session / full reorg weekly / hierarchical rollup monthly. This is no longer research-speculative.

---

## 2. Where the field collectively hand-waves

### 2.1 The retention / promotion / demotion engine — the single largest gap

Not one of the reviewed production substrates ships a principled demotion engine. **Brief 14 (Graphiti issue #1300)** is the canonical data-point: the missing feature was flagged publicly against the leading substrate, sits open/uncommented from the maintainers. Similar absence in **Zep (01)**, **MAGMA (02)**, **Cognitive Weave (05)**, **HippoRAG (08)**, **A-MEM (09)**, **MemGPT (11)**, **Letta (15)**, **QMD (17)**, **MS Agent Framework (16)**.

Only **Memory-as-Metabolism** (brief 04) proposes five named operations — TRIAGE / CONTEXTUALIZE / DECAY / CONSOLIDATE / AUDIT — and a gravity+minority-retention model, but it is an **explicitly un-implemented vision paper**. The SCNS dream-daemon and Letta sleep-time are the closest implementations and both punt on utility-weighted scoring.

### 2.2 Utility-feedback loops are universally absent

Every system scores memory at ingest and retrieves by static scoring. **No system ingests `recall` outcomes back into the scoring function.** Did the retrieved fact actually help? Did it get cited in the answer? Did the downstream tool call succeed? None of the reviewed systems close this loop. SCNS has `hit_count` data (audit §3) but doesn't feed it back into eviction. This is the lowest-cost high-impact gap Lethe can claim.

### 2.3 Scoring weights are never published

Every hybrid-retrieval paper says "we use semantic + BM25 + graph" and omits the weights. Zep's paper **explicitly says "weighting matters more than individual signals"** — and does not publish the weighting. Graphiti's README doesn't publish them either. QMD's README gestures at RRF without the constant. **There is no reusable default.** Lethe will have to pick, publish, and tune its own.

### 2.4 Cross-agent / multi-tenant memory is hand-waved

**Letta** has "shared blocks" but punts concurrent-write conflicts to developers. **Graphiti** has "groups" (brief 13) without RBAC or quotas. **QMD** is single-user by design. **MS Agent Framework** has no tenancy model. SCNS operates multi-agent today (audit §4) but with implicit conventions, not enforced isolation. No paper gives an ACID / CRDT / merge-policy story for concurrent memory writes by multiple agents. This is the SCNS-lineage problem Lethe inherits.

### 2.5 Provenance is "supported" everywhere but enforced nowhere

Graphiti "episodes" are provenance primitives; MS AF `SourceName`/`SourceLink` are optional strings; Zep implies traceability; Letta stores all messages. **None of them refuse to store a memory without provenance.** Charter §4.1 commits Lethe to *enforced* provenance — this is a Lethe differentiation point.

### 2.6 Cost and latency are absent from every accuracy benchmark

DMR, LongMemEval, LoCoMo all report accuracy. None reports tokens-per-query or p95 latency. A system burning a full context replay scores identically to a surgical retrieval. Lethe's eval (WS4) must add a cost dimension to avoid optimising for the wrong target.

### 2.7 Extraction quality is the silent upstream dependency

HippoRAG graph = LLM entity extraction. MAGMA causal edges = LLM inference. A-MEM links = LLM judgement. Graphiti episodes → facts = LLM with structured-output support. **Every modern memory system sits on an LLM-extraction layer whose correctness is unmeasured.** When the extraction is wrong, the memory is wrong, and downstream retrieval confidently returns garbage.

### 2.8 The human-legible surface tension

**Karpathy wiki (21)** and **QMD (17)** optimize for human-legible markdown; **Graphiti** and **MAGMA** optimize for graph traversal. SCNS is markdown-of-record with an index over it. Lethe's charter commits to markdown-as-surface, but the cross-paper pattern is "real data is in a graph DB; markdown is a view." Which is authoritative matters for contradiction resolution, and no paper answers it.

### 2.9 Non-factual memory (goals, preferences, values)

**LoCoMo-Plus** (2602.10715) raises this; no reviewed system models it. Lethe will need a strategy even for v1 — even if the strategy is "we don't model non-factual memory yet and here's how we'll know we need to."

### 2.10 Parametric / weight-level memory

**MemOS (brief 07)** names it as a memory type; no reviewed system delivers governance over it. Lethe's charter explicitly excludes parametric memory from v1. The field's silence justifies the non-goal.

### 2.11 Ontology / schema evolution

Custom entity/edge types (Graphiti via Pydantic; A-MEM via Zettelkasten tags; Cognitive Weave via Signifiers) are all defined *at init*. None of the papers addresses migration when the agent's domain shifts. Personal tool scale may tolerate this; long-lived agents cannot.

### 2.12 Crash-safety and durability

Karpathy's wiki concedes it has none. Letta relies on its DB. Graphiti relies on Neo4j/FalkorDB. MemGPT does not discuss it. **No reviewed paper offers a mid-consolidation crash recovery story.** SCNS relies on git. Lethe needs an explicit answer.

---

## 3. What Lethe must own

Deriving directly from §2, Lethe's differentiated contribution is the **lifecycle runtime** over an existing temporal-graph substrate:

### 3.1 Retention engine (fills §2.1)
Utility-aware promotion + demotion on a policy ladder (Letta-inspired cadence ladder), borrowing Memory-as-Metabolism's five operations, scored via a function that is *actually published* with defaults. WS3 gap #1.

### 3.2 Utility-feedback loop (fills §2.2)
Close the loop: every `recall` returns a recall-id; downstream citations and tool-call outcomes feed back as signals. Memory scores update on the consolidation cycle. This is the most novel claim Lethe can make. WS3 gap #2.

### 3.3 Published scoring weights + tuning methodology (fills §2.3)
Lethe ships with named, justified default weights for the hybrid retriever, plus a reproducible tuning harness driven by LongMemEval. WS3 gap #3.

### 3.4 Multi-agent concurrency model (fills §2.4)
Explicit contract for concurrent writes from multiple agents into shared memory. At minimum a documented conflict policy; ideally a CRDT-style merge primitive. WS3 gap #4.

### 3.5 Enforced provenance (fills §2.5)
`remember` requires a provenance reference (episode id or equivalent). `recall` returns provenance as a first-class field, not a metadata afterthought. WS3 gap #5 — "provenance as type-system invariant."

### 3.6 Cost-aware evaluation (fills §2.6)
WS4 benchmarks report (accuracy, tokens/query, p95 latency) triples. Lethe publishes Pareto frontiers, not just accuracy numbers.

### 3.7 Extraction-quality instrumentation (fills §2.7)
Lethe logs LLM-extraction decisions with confidence, exposes a "dispute" path, and supports re-extraction when the substrate's extraction was wrong. WS3 gap #6.

### 3.8 Markdown-as-view, graph-as-source-of-truth (fills §2.8)
Commit position: graph substrate (Graphiti) is authoritative; markdown surfaces are views generated on consolidation cycles. SCNS's current model is the reverse; Lethe inverts. WS3 gap #7.

### 3.9 Non-factual memory strategy (fills §2.9)
Even if v1 says "not in scope," the charter addendum must specify how we'll detect needing it and what the extension shape is. Cheap to write now, expensive to retrofit.

### 3.10 Crash-safety + durability contract (fills §2.12)
Minimum: `remember` is atomic; consolidation is resumable; mid-cycle crash is recoverable without losing episodes. Lethe's answer likely involves Graphiti's backing DB + a consolidation-log shaped like SCNS's `log.md`.

The remaining field gaps — parametric memory governance (§2.10), ontology evolution (§2.11) — are **explicit Lethe non-goals for v1** and the charter should be updated to cite this synthesis as justification.

---

## 4. Unreachable sources (honest log)

Running list of sources from PLAN.md's 21-brief checklist that could not be fetched. **Nothing was fabricated in their place.**

| # | Source | Reason | Mitigation |
|---|---|---|---|
| 03 | Shibui Medium — "Graph-Based Agent Memory: A Complete Guide" | HTTP 403 (Medium bot-wall). | Article is a walkthrough of MAGMA; primary source (brief 02) covers the same material directly from the arXiv HTML. Synthesis rests on the paper, not the walkthrough. |

No additional unreachables encountered during Batches B or C. Briefs 14–20 all fetched cleanly either from arXiv directly, GitHub READMEs, or official docs (Letta docs site, MS Learn). Where primary source material was truncated (Letta docs `guides/agents/architectures/sleeptime` returned 404; MS AF `context-providers` page returned 404), the corresponding briefs used the parent documentation pages and the sibling `agent-memory` page as substitutes and noted this explicitly. No content in briefs 14–20 is synthesized from sources that couldn't be fetched.

---

## 5. Hand-off hooks into WS3

WS3 has two tracks per PLAN.md §WS3. The synthesis points at both:

**Track A — Composition design.** §1 of this synthesis identifies the settled shape: Graphiti as substrate, Lethe as runtime, MCP as the external surface. WS3 Track A converts this into a layered architecture diagram + interface contracts.

**Track B — Gap deep-dives.** §2 identifies **twelve distinct gaps**; §3 maps the **eight** Lethe commits to owning into concrete WS3 brief slots:

| Gap | Lethe response | WS3 brief slot |
|---|---|---|
| 2.1 retention engine | §3.1 | gap-brief #1 |
| 2.2 utility feedback | §3.2 | gap-brief #2 |
| 2.3 scoring weights | §3.3 | gap-brief #3 |
| 2.4 concurrency | §3.4 | gap-brief #4 |
| 2.5 provenance enforcement | §3.5 | gap-brief #5 |
| 2.7 extraction-quality | §3.7 | gap-brief #6 |
| 2.8 markdown-vs-graph authority | §3.8 | gap-brief #7 |
| 2.12 crash safety | §3.10 | gap-brief #8 |

Nine if §3.9 (non-factual memory scoping) gets its own brief; otherwise folded into the charter addendum.

The eighth explicit gap beyond these (cost/latency, §2.6) is a WS4 concern, not WS3, and is noted in the WS4 brief.

**Named non-goals for v1** (with lit-review citations): parametric memory governance (§2.10), ontology evolution (§2.11). Charter update recommended.

**Canonical substrate recommendation:** **Graphiti** (brief 12) — Apache-2.0, bi-temporal, MCP-exposed (brief 13), demonstrably missing exactly the layer Lethe proposes to build (brief 14). Zep (brief 01) is the managed-service precedent; Lethe is Graphiti+runtime, not Zep.

**Closest living precedent to study operationally:** **Letta** (brief 15). Sleep-time compute is a live production version of what Lethe plans to ship. Run Letta, instrument it, understand the cost envelope, *then* design Lethe's dream-daemon.
