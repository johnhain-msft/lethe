# gap-07 — Markdown at scale (write-amp, concurrency, retrieval ceiling)

**PLAN.md §WS3 Track B item #3** (markdown at scale — broadened per QA §3.2). Synthesis §3.8 + §2.8.
**Tier:** first-class.
**Status:** active. PLAN.md preamble explicitly enumerates four scale concerns from Karpathy: write amplification, concurrent writes from multi-agent swarm, crash consistency, retrieval cost > 10k pages. Crash consistency goes to gap-08; the other three live here.
**Substrate:** brief 21 Karpathy (explicit-limits table — ~100 sources / hundreds of pages, "single source might touch 10–15 wiki pages"); brief 17 qmd (only published on-device markdown retrieval numbers in the corpus); brief 02 MAGMA (subspace partitioning reduces fan-out); brief 06 paper-list (markdown-at-scale flagged as recurring survey concern); composition design §2.1 (S4a/S4b split); §4.1 line 8 (S4b regeneration in async path); §7 (S4b regeneration mid-write crash row); synthesis §2.8 + §3.8.
**Cross-refs:** composition §2 (S4 storage row), §4.4 (consolidate regen S4b), §5 (S4 eventual-consistency commitment), §7 (S4 failure-mode rows). Pairs with gap-04 (concurrency at write layer) and gap-08 (crash semantics).

---

## 1. The gap

PLAN.md preamble's "From the Karpathy gist" block lists the scale failure mode in detail: *"works surprisingly well at moderate scale (~100 sources, ~hundreds of pages). No evidence for 10k+. Retrieval strategy (index.md + grep) degrades fast."* And separately: *"a single source might touch 10–15 wiki pages. At agent-loop frequency this is a lot of diff churn — cost + rate-limit implications."*

Lethe is *named* for forgetting and committed to multi-agent (charter §4.1). Its target write-rate is *much higher* than Karpathy's personal-scale wiki — agent swarms produce orders of magnitude more episodes than a single human. If the markdown surface scales like Karpathy's reference implementation, three things break:

1. **Write amplification dominates cost.** Every consolidation cycle that regenerates S4b pages from S1 facts pays O(facts × pages-per-fact). At swarm scale this is a substantial portion of the runtime.
2. **Concurrent S4a edits collide.** S4a (synthesis pages, canonical, human/agent-authored) cannot use file-level last-write-wins safely — composition §5 commits S4a to "strong consistency only at the file-system level." But concurrent agent writes to the same synthesis page need a defined merge story.
3. **Retrieval over S4a degrades past Karpathy's ceiling.** qmd-style hybrid retrieval (BM25 + vector + LLM rerank) is good *up to* roughly the same scale Karpathy describes; brief 17 publishes no numbers above that.

Composition design §2.1 split the markdown layer into S4a (synthesis pages, canonical) and S4b (fact projections, derived) precisely so these problems can be scoped per layer. This brief operationalizes that split with a budget for write amplification, a regeneration policy, a concurrency policy for S4a, and a documented retrieval ceiling for the synthesis-page corpus.

If we ship without addressing this, the composition design's recommendation (Candidate C hybrid layered) loses its defense — the very thing C was supposed to fix in Candidate A (markdown-primary) reasserts itself at the S4a layer.

---

## 2. State of the art

- **Brief 21 Karpathy.** The explicit-limits table is the only published scale-ceiling reference in the corpus. ~100 sources, ~hundreds of pages. Retrieval = `index.md` + grep, "degrades fast" past the ceiling. Write amplification: 10–15 pages touched per source. Concurrency: single-user, no story.
- **Brief 17 qmd.** On-device hybrid retrieval over markdown corpus. BM25 + vector + LLM rerank with RRF combination. Substrate exists; published scale numbers are absent (READMEs gesture at "personal-scale" but don't quantify).
- **Brief 02 MAGMA.** The four-subspace partitioning (Temporal/Causal/Semantic/Entity) is one mechanism for *reducing* per-write fan-out by routing each fact-update to one subspace. Lethe v1 doesn't partition this way (charter §4.2), but the principle — partition the write target — applies here as the per-page-domain split (S4a = authored, S4b = derived).
- **Brief 06 paper-list.** Markdown-at-scale recurs as a survey-level concern; no paper in the list shipped a fix.
- **SCNS** (audit). Operates roughly within Karpathy's ceiling on JH's personal stack. Not stress-tested at multi-tenant scale.

The substrate gives us decent retrieval primitives (qmd) and a reduction-of-fan-out principle (MAGMA-style routing). What's missing is **quantitative budgets** — how much write-amp is tolerable, what regeneration policy stays under it, what retrieval ceiling triggers the fallback.

---

## 3. The three sub-questions

This brief addresses three distinct scale problems. Each gets its own commitment.

### 3.1 Write amplification (S4b)

**The problem.** S4b pages are derived from S1 facts; on each consolidation cycle, the dream-daemon must decide which pages to regenerate.

**Three regen policies:**

| Policy | Mechanic | Pro | Con |
|---|---|---|---|
| **Full regen** | regenerate all S4b pages every cycle | simple; always fresh | cost ∝ \|S4b\| every cycle |
| **Incremental** | track which facts changed; regenerate pages whose facts changed | bounded per-cycle work; matches Karpathy's "10–15 pages/source" budget | requires fact-→-page reverse index in S2 |
| **On-read** | don't materialize S4b; render on user request | zero write-amp | latency on read; loses the "human-readable file at a stable path" affordance |

**v1 commitment.** **Incremental regen with a per-cycle budget.** The budget caps the number of pages a single consolidation cycle may regenerate (default `MAX_S4B_REGEN_PER_CYCLE = 100`). Excess pages get a `regen_pending` flag in S2 and roll over to the next cycle. The reverse-index (fact-id → list-of-S4b-pages) lives in S2. Falls back to on-read for any page above the budget.

**Why incremental.** Full regen blows the cost budget at swarm scale (Karpathy's 10–15 pages × thousands of episodes = tens of thousands of regenerations per cycle). On-read kills the affordance the markdown surface was created for ("you can `cat` MEMORY.md and see your agent's beliefs"). Incremental respects both: write-amp is bounded; the file at the stable path stays current within one cycle plus budget overflow.

**Quantitative anchor.** SCNS's daily logs + MEMORY.md cycle has historically operated under Karpathy's ceiling; the daemon design note §2.10 cadence (daily/weekly/monthly) keeps amplification manageable for a single-vault personal stack. Lethe's per-tenant budget extends the same shape.

### 3.2 Concurrency on S4a (synthesis pages)

**The problem.** Composition §5 row 6 commits S4a to "strong consistency only at the file-system level (atomic file-replace or git)." The graph cites S4a, never rewrites it. But two agents (or an agent + a human) may try to edit the same synthesis page simultaneously.

**Three concurrency policies:**

| Policy | Mechanic | Pro | Con |
|---|---|---|---|
| **File-level LWW** | atomic rename; whoever's rename lands second wins | simple | silent data loss |
| **Git-style merge** | every edit is a commit; conflicts surface as merge markers, resolved manually | preserves all attempts; aligns with synthesis §git-versioned recommendation | requires git substrate per tenant; conflict resolution UX |
| **Section-locked** | section-level lock with timeout; agents lock a section before editing | fine-grained; bounded conflict | requires markdown structure parsing; sections are not always cleanly defined |

**v1 commitment.** **Git-style merge as the recommended deployment**, with file-level LWW as the zero-config fallback. Lethe runtime does not implement section-locking in v1 (premature; gap-04-adjacent).

**Specifically:** if the tenant storage root is a git repo (recommended in composition §5 row 6), Lethe's S4a writes are commits; conflicts produce merge-marked files and a `lint --conflicts` surface. If not, atomic-rename LWW with a one-line warning in startup logs ("S4a is non-versioned; concurrent writes may lose data").

This is in line with charter §4.1 ("BYO storage") — the heavier guarantee is opt-in.

### 3.3 Retrieval ceiling on S4a

**The problem.** qmd-class hybrid retrieval over markdown is brief 17's substrate. Scale ceiling is undocumented but Karpathy puts it in the hundreds of pages.

**v1 commitment.** **Document the ceiling at the substrate's published numbers; provide a fall-through to S1 above it.**

Concretely:
- For S4a corpus < 1000 pages per tenant: qmd-style retrieval (BM25 + vector + LLM rerank, RRF k=60). This is the Karpathy regime, scaled 10× by leveraging proper indexing.
- For S4a corpus ≥ 1000 pages: page-level facts (which page is most relevant) are extracted into S1 as nodes-with-text-attributes, treated as graph-recall targets. The S4a retriever still works for full-text but is no longer the primary path.
- Cap published as a per-tenant config; the *measurement* to pick the right cap comes from WS4.

The 1000-page threshold is a **reasoned guess** anchored on Karpathy + a 10× factor (proper indexing infrastructure should buy at least an order of magnitude). WS4 measures.

---

## 4. Candidate v1 approaches (full-stack)

Three end-to-end candidates that fold the three sub-questions into a single recommendation.

### Candidate (a) — Conservative: incremental regen, file-LWW S4a, no S4a retrieval ceiling enforcement

**Sketch.** §3.1 incremental, §3.2 file-LWW (no git), §3.3 unbounded qmd retrieval; if it degrades, document.
**Cost.** Lowest impl.
**Failure mode.** Silent data loss on concurrent S4a writes; user surprise at degraded retrieval past the ceiling.
**Eval signal.** Concurrent-write data-loss test count (any > 0 = problem).

### Candidate (b) — Recommended: incremental regen with budget + reverse index; git-recommended for S4a; documented retrieval ceiling

**Sketch.** §3.1 incremental + budget (`MAX_S4B_REGEN_PER_CYCLE`); §3.2 git-recommended + file-LWW fallback with explicit warning; §3.3 documented threshold with S1 fallback above.
**Cost.** Moderate. Reverse-index in S2; git integration optional.
**Failure mode.** Budget overflow buildup if pending list isn't drained.
**Eval signal.** Pending-regen queue depth over time (healthy: oscillates near zero; broken: monotonic growth).

### Candidate (c) — Aggressive: full regen, section-locking S4a, mandatory page→S1 indexing

**Sketch.** §3.1 full regen; §3.2 section-lock; §3.3 always extract pages to S1.
**Cost.** Highest impl + runtime.
**Failure mode.** Full regen blows cost; section-lock UX problems; mandatory S1 extraction couples S4a to LLM extraction quality (gap-06).
**Eval signal.** Cost-per-cycle.

### Trade-off table

| Axis | (a) Conservative | (b) Recommended | (c) Aggressive |
|---|---|---|---|
| Write amp at swarm scale | bounded (incremental) | bounded + budget cap | unbounded (full) |
| Concurrent S4a safety | silent data loss | git-versioned safe; file-LWW fallback warned | safe; UX problems |
| Retrieval scale | unbounded but degrades | bounded + documented fallback | always uses S1 |
| Implementation cost | low | moderate | high |
| Runtime cost | low | low + small reverse-index | high |
| Composes with composition §5 | partially | fully | over-couples to S1 |
| Aligns with charter §4.1 BYO | yes | yes | no (mandatory git) |

---

## 5. Recommendation

**Candidate (b).** All three sub-questions get a defined budget + a documented fallback.

Justification:

1. **Each sub-question has a quantitative answer** (`MAX_S4B_REGEN_PER_CYCLE = 100`, S4a corpus threshold = 1000 pages, RRF k=60), pinned with reasoned-guess rationale. This is the same "publish what others hide" stance gap-03 takes for scoring weights.
2. **The composition design's S4a/S4b split is operationalized** rather than restated. The split was the hard architectural choice; this brief turns it into a runnable policy.
3. **Falls back gracefully.** Budget overflow doesn't crash; concurrent S4a writes don't corrupt; retrieval past the ceiling switches to S1. None of the failure modes is silent except the file-LWW path (which is gated behind a startup warning).
4. **Cheap to upgrade.** Section-locking, git-mandatory, and full-regen are all post-v1 upgrades that don't require schema changes; they replace policies, not data structures.

**Stop-gap if (b) is not ready at v1 cut.** Ship (a) — file-LWW + incremental without budget enforcement. Document the silent-data-loss failure as a known v1 limitation. WS4 measures whether the failure manifests in real workloads.

---

## 6. Residual unknowns

- **Real-world fact-→-page fan-out.** Karpathy's 10–15 is a personal-scale anchor. Lethe's number depends on how synthesis pages are structured. Bet: 5–20 with long tail; instrument the histogram.
- **MAX_S4B_REGEN_PER_CYCLE = 100** is reasoned-guess. WS4 measures whether the queue oscillates or grows.
- **Git substrate cost.** Per-tenant git repo adds disk + I/O. For multi-tenant deployments with thousands of low-traffic tenants, this may not amortize. Bet: acceptable; tenants who don't write to S4a pay nothing.
- **LLM rerank cost.** qmd-style LLM rerank is per-query; for high-QPS workloads it dominates. Cap at top-50 candidates pre-rerank; tune in WS4.
- **Markdown structure ambiguity.** Section-level operations (locking, citation) require parsing markdown into a structured tree. Heading-based structure works for well-formed pages; arbitrary markdown is messier. Defer; v1 doesn't need it.
- **Cross-tenant retrieval invariant.** The retrieval ceiling is per-tenant; aggregate across tenants is irrelevant because composition §5.2 forbids cross-tenant reads.
- **Interaction with `forget(purge)` (gap-11).** Purging a fact must invalidate its S4b page caches and re-trigger regeneration. The reverse-index supports this; instrument purge-cascade latency.

---

## 7. Touch-points

- **gap-01 retention engine** — consolidation-cycle work includes S4b regen; the per-cycle budget here interacts with the dream-daemon's overall time budget.
- **gap-04 multi-agent concurrency** — owns the *graph*-layer concurrency; this brief owns the *markdown*-layer concurrency. Together they cover composition §5.2.
- **gap-05 provenance enforcement** — S4b pages reference fact-ids; provenance survives the projection; lint surfaces facts-without-pages and pages-without-facts.
- **gap-06 extraction quality** — S4a → S1 extraction (when corpus exceeds the retrieval ceiling) inherits gap-06's confidence requirements.
- **gap-08 crash safety** — atomic-rename + git pattern matches composition §7 row 7 (S4b crash mid-write); gap-08 owns the durability contract.
- **gap-11 forgetting-as-safety** — purge invalidates S4b; reverse-index makes it possible.
- **WS4 (eval)** — measures regen-budget queue depth; S4a retrieval quality at and above 1000-page threshold.
- **WS6 (API)** — `lint --conflicts` for git-merge surfacing; no per-page MCP verbs at v1.
- **WS7 (migration)** — SCNS's MEMORY.md is an S4b file (derived); SCNS daily logs are S4a candidates if treated as authored-narrative, otherwise consumed and discarded per current SCNS pattern.
