# gap-01 — Retention engine (utility-weighted promotion + demotion; unattended consolidation)

**PLAN.md §WS3 Track B item #4** (unattended consolidation) — synthesis §3.1 retention engine.
**Tier:** first-class.
**Status:** active. SCNS dream-daemon evaluated here on its own merits as the v1 candidate spine, per PLAN.md north-star.
**Substrate:** `docs/01b-dream-daemon-design-note.md` (per-module verdicts §2; MaM/MAGMA mapping §3; transition plan §4); brief 04 (Memory-as-Metabolism); brief 02 (MAGMA dual-stream); brief 15 (Letta `enable_sleeptime`); brief 14 (Graphiti issue #1300); brief 12 (Graphiti capabilities); synthesis §1.3 + §1.8 + §2.1 + §3.1; charter §4.1 commitments.
**Cross-refs:** composition design §4.4 + §10. Touches gap-02 (utility signal), gap-03 (scoring), gap-04 (concurrency), gap-08 (crash safety), gap-11 (forget modes).

---

## 1. The gap

The single largest cross-paper field gap (synthesis §2.1): not one of the reviewed production substrates ships a principled demotion engine. Graphiti issue #1300 (brief 14) is the canonical public confirmation against the leading substrate. Every other reviewed substrate — Zep, MAGMA, Cognitive Weave, HippoRAG, A-MEM, MemGPT, Letta, qmd, MS Agent Framework — has the same hole. Memory-as-Metabolism (brief 04) names five operations (TRIAGE / CONTEXTUALIZE / DECAY / CONSOLIDATE / AUDIT) but is an explicitly-unimplemented vision paper. Letta's sleep-time (brief 15) is the closest production precedent and it punts on utility-weighted scoring.

For Lethe specifically, the gap matters because charter §4.1 commits to "retention as first-class" — promotion, demotion, consolidation, and safe forgetting as API-level operations, not cron jobs. If we ship without a principled retention engine, three things happen: (a) the substrate accumulates monotonically until performance and cost degrade; (b) the "river of forgetting" branding (charter §1) is unfounded; (c) the utility-feedback loop (gap-02) has nowhere to land — signals about which memories paid off cannot drive any decision because there is no decision to drive.

A v1 ship without this is not a memory runtime; it is a memory accumulator with a recall API.

---

## 2. State of the art

The field-level position, citing briefs:

- **Brief 04 Memory-as-Metabolism.** Richest conceptual substrate. Five operations; gravity-driven attention; minority-hypothesis retention; three-timescale safety. Strength: complete vocabulary. Weakness: not implemented; numerical defaults absent.
- **Brief 02 MAGMA.** Dual-stream (episodic / semantic) consolidation with bidirectional promotion (recurring episodic → semantic) and demotion (contradicted semantic → episodic-for-revisit). Strength: well-specified. Weakness: research artifact; subspace partitioning may be premature for v1.
- **Brief 15 Letta.** Ships `enable_sleeptime=true` in production. The community policy ladder (dedup every run / light consolidation EOS / full reorg weekly / hierarchical rollup monthly; brief 15 §4) is the most validated cadence schedule available. Weakness: scoring is implicit; no published utility weights.
- **Brief 12 Graphiti.** Substrate; per brief 14 issue #1300 ships **no decay or unlearn algorithms**. Bi-temporal `valid_from / valid_to` is a primitive Lethe must wrap; Graphiti will not retire facts on its own.
- **Brief 04 §3.1** explicitly flags that the safety story is partial without retention; brief 11 (MemGPT) tiers (core / archival) but tier-membership is LLM-driven without explicit scoring.
- **Brief 21 Karpathy.** Uses human-driven curation as the retention mechanism; explicitly does not generalize to unattended scenarios.

The SCNS dream-daemon (`docs/01b-dream-daemon-design-note.md`) is the only fully-implemented unattended-consolidation control plane in the reviewed corpus. The note already evaluated each of its 12 modules on merits (note §2) and laid out the transition plan (note §4). The job of *this* gap brief is **not** to re-explain the note — it is to (a) confirm the note's verdict that the pattern survives into v1, (b) name the break-points the note flagged as open, and (c) define the eval signal that decides *keep / replace / extend* per phase.

---

## 3. The dream-daemon as v1 candidate — on-merits evaluation

The note's verdict (§4): **adopt the pattern; rebuild three of twelve modules; export the rest.** This brief affirms that verdict and adds the eval-signal commitment.

### 3.1 What the dream-daemon already gives us

- A **gate → lock → execute** control plane (note §2.13). Every reviewed system either has no control plane or hand-waves one; the dream-daemon ships a working three-condition gate (time + sessions + lock-free) with a stale-lock break.
- A **four-phase pipeline** (orient → gather → consolidate → prune; note §2.8). Pure functions, explicit phase logs. The closest thing in the WS2 set to a reference consolidation algorithm; note §3.1 already pairs it with MaM anabolism/catabolism.
- A **tiering schedule** (daily → weekly → monthly; note §2.10–§2.11). The "≥ 2 weeklies ⇒ stable pattern" promotion heuristic in `tiered-consolidation.ts` is one of very few explicit, defensible promotion criteria in the entire corpus.
- A **typed memory vocabulary** (`user / feedback / project / reference / prohibition`; note §2.6) with a static priority order that maps cleanly onto WS5 scoring inputs.
- **Negative-memory application** — writing prohibitions back to the agent's instructions file is unique in the reviewed corpus and aligns with brief 04's "don't do this" immunological-memory framing.

### 3.2 Break-points the design note flagged + their eval signals

The note §4 names four open questions. This brief converts each into a *measurable eval signal* that decides keep / replace / extend.

| Note open question | Composition-design touchpoint | Eval signal that decides disposition |
|---|---|---|
| **Q1. Two-stream or one?** (MAGMA dual vs. SCNS single-stream) | composition §2 (S1 owns episodes + facts; one substrate, possibly two extraction phases) | WS4 `recall@10` on LongMemEval temporal vs. semantic-knowledge subsets, measured with (a) one-stream extraction and (b) two-stream extraction. Decision rule: if (b) lifts the temporal subset ≥5 absolute points without dropping semantic by >2, adopt two-stream; else stay one-stream and revisit at v2. |
| **Q2. Where does utility feedback enter?** | gap-02 ingestion path; composition §4.4 | A/B the three injection points (pre-gate / during-priority / post-consolidate) on a simulated utility-log replay across one consolidation cycle. Measure retained-fact precision on a held-out recall set. Decision rule: pick highest precision-uplift × inverse-cost. Default expected-winner: post-consolidate priority-rescore (cheapest, latest information). |
| **Q3. Lock semantics at multi-tenant scale** | gap-04 + composition §5.2 | Integration test with N concurrent tenants × M agents/tenant × T duration; measure lock-acquire-latency p99, starvation incidents, lost-update count from missed gates. Decision rule: per-tenant lock + 30-second heartbeat is the v1 baseline; promote to fairness queue if starvation > 1% in soak. |
| **Q4. Phase plug-in contract** | composition §4.4 dream-daemon loop | Developer-friction proxy: can a new phase (e.g., custom dedup rule) be added in <50 lines without touching the daemon core? Decision rule: v1 contract is `phase = function (state) → diff + log entries`; if a real second phase (negative-memory applicator) doesn't fit cleanly, redesign before v1. |

Each is an ungated open question today; this brief commits Lethe to **the eval signal that resolves it** rather than to the answer in advance.

### 3.3 Modules requiring rebuild (note §4 verdict, this brief unchanged)

- `extraction.ts` — rebuild as LLM-driven against a Lethe schema. Composition design §4.1 line 4 (extraction step) is where the rebuild lives. Eval signal: gap-06 (extraction quality).
- `memory-entries.ts` contradiction handling — replace name-keyed last-write-wins with timestamped bi-temporal invalidate. Eval signal: gap-13.
- `housekeeping.ts` — not ported; Lethe gets its own analog, scoped to S2/S5 retention.

The seven "adopt-with-parameterization" modules and the one "shape-is-the-contribution" module (`dream-daemon.ts` itself) move forward unchanged in pattern, rewritten in implementation for tenant scoping, heartbeats, and pluggable phases.

---

## 4. Candidate v1 approaches

The on-merits evaluation in §3 settles "what spine?" — dream-daemon. What remains open is **which scoring discipline the spine applies during the consolidate + prune phases.** Three candidates:

### Candidate (a) — Static-priority + capacity (dream-daemon as-shipped)

**Sketch.** Adopt SCNS `consolidation-priorities.ts` verbatim: type-keyed priority (`user / prohibition` critical, `feedback` high, `project` medium, `reference` low), `trimToFit` to byte+line cap.
**Cost.** Lowest. Already implemented.
**Failure mode.** Entirely static — no recency, no utility, no connectedness. Synthesis §3.1 explicitly names this as "the weakest scoring surface in the whole loop." A long-running agent eventually pins critical-but-unused entries while evicting actively-used reference material.
**Eval signal.** Recall@10 on a multi-month synthetic workload where a single `reference`-typed fact is queried daily; static priority will evict it, exposing the failure.

### Candidate (b) — Heuristic blend (recommended)

**Sketch.** Score = `α·type_priority + β·recency_decay(last_access) + γ·connectedness(graph_degree) + δ·utility_signal(gap-02) - ε·contradiction_penalty(gap-13)`. Defaults published per gap-03; tunable per tenant. Promote on score crossing high threshold; demote on crossing low.
**Cost.** One score-computation per fact per consolidation cycle (cheap; bounded by gate frequency, not query frequency).
**Failure mode.** Default weights wrong → either over-prunes (false demotions) or under-prunes (memory bloat). gap-03 owns the calibration protocol.
**Eval signal.** Promotion-precision and demotion-recall against a retrospectively-annotated SCNS task set (per gap-14). Cost dimension: tokens/query post-pruning vs. pre-pruning.

### Candidate (c) — LLM-judged retention

**Sketch.** During consolidate phase, batch each candidate fact into an LLM call with the prompt "should this still be retained, given recent activity?" Result drives keep / demote / forget.
**Cost.** Highest — N facts × LLM cost per cycle. At swarm scale this is prohibitive.
**Failure mode.** Reproducibility (same fact judged differently across runs); cost dominates substrate cost; opacity (no published criterion).
**Eval signal.** Promotion-precision uplift over Candidate (b), divided by cost-multiplier. Adopt only if uplift / cost-multiplier > 1.5×.

### Trade-off table

| Axis | (a) Static | (b) Heuristic blend | (c) LLM-judged |
|---|---|---|---|
| Implementation cost | trivial | moderate (gap-03 dependency) | moderate impl, high runtime |
| Runtime cost / cycle | O(1)/fact | O(1)/fact | O(LLM)/fact |
| Reproducibility | ✅ | ✅ | ❌ |
| Adapts to actual usage | ❌ | ✅ (via β, δ) | partially (single-call, no memory of trend) |
| Closes utility-feedback loop | ❌ | ✅ | partially |
| Shippable v1 | ✅ | ✅ | ❌ (cost) |
| Fits dream-daemon plug-in contract (§3.2 Q4) | ✅ | ✅ | ✅ |

---

## 5. Recommendation

**Candidate (b) — heuristic blend.** Justification:

1. It is the only candidate that **operationalizes the utility-feedback signal** gap-02 produces. (a) ignores it; (c) consults it implicitly via prompt context but does not weight it. Closing the loop is the single strongest novel claim Lethe can make (synthesis §3.2); a v1 retention engine that doesn't *use* the signal forfeits it.
2. Costs are bounded and predictable. Score-per-fact is O(1) arithmetic; consolidation-cycle cost stays linear in S1 size with a per-cycle cap (`MAX_FACTS_RESCORED = 10k` is a reasonable v1 cap; refined in gap-07).
3. It composes with the dream-daemon plug-in contract (§3.2 Q4): the score function is one phase, demotion is another, promotion is a third. None of these need the daemon core to know anything they don't already know.
4. Defaults can be published (charter §4.1 + synthesis §2.3), making Lethe the first reviewed system with reproducible retention numbers.

**Stop-gap if (b) is not ready at v1 cut.** Ship Candidate (a) static-priority but **log every score-input the heuristic would have used** (recency, connectedness proxy, utility signal) into S2 from day one. This means the moment (b) lands, we have months of replay data to tune defaults against — there is no cold-start. This is essentially the synthesis §3.2 strategy applied to retention itself.

**Why not defer the engine entirely.** Charter §1 ("river of forgetting") is the project's identity. Deferring means shipping under a name the runtime doesn't earn.

---

## 6. Residual unknowns

What we are still betting on; what to instrument post-launch.

- **Two-stream Q1 outcome.** Until WS4 measures the temporal-vs-semantic split on LongMemEval, we don't know whether one-stream is sufficient. Bet: it is, for v1; instrument the loss against a held-out temporal subset to detect when v2 should adopt two-stream.
- **Negative-memory generalization.** SCNS writes prohibitions back to the agent's instructions file — that surface is SCNS-specific. For Lethe, the analog is "S4a synthesis page named PROHIBITIONS.md per tenant" or equivalent. Whether agents in the wild use it is open; instrument retrieval of `type=prohibition` facts to detect whether the negative-memory channel is being consulted.
- **Promotion threshold drift.** As utility signals accumulate, the score distribution shifts. Whether thresholds need re-calibration on a quarterly cadence is empirical. Instrument promotion-rate and demotion-rate as system-health metrics.
- **Tiered rollup with multi-tenant catch-up.** Note §2.10 break: "daemon offline 3 weeks runs one weekly rollup, not three." The fix is catch-up semantics, but the *correct* catch-up policy (replay all missed weeks vs. coalesce into one) is unsettled. v1: coalesce, log the coalescing event in S5 for audit.
- **Interaction with peer-message episodes** (gap-10). Should peer-asserted facts decay faster by default? Brief 04 §3.1 hints "minority-hypothesis retention" is the right framing — this brief defers to gap-10 + gap-11 for the safety dimension.

---

## 7. Touch-points

- **gap-02 utility-feedback loop** — produces the `δ·utility_signal` term in §4 candidate (b). Without gap-02, candidate (b) collapses to (a).
- **gap-03 scoring weights** — owns the (α, β, γ, δ, ε) defaults and tuning protocol. The score formula is here; the numbers are there.
- **gap-04 multi-agent concurrency** — owns lock semantics (§3.2 Q3).
- **gap-06 extraction quality** — feeds the rebuilt `extraction.ts` (§3.3); the dream-daemon re-extracts on dispute.
- **gap-08 crash safety** — owns T1/T2 transactionality + resumable consolidation, the implementation substrate of the daemon's resilience.
- **gap-11 forgetting-as-safety** — the demotion outputs of this engine are the *inputs* to gap-11's three forget modes. A demoted fact may be `invalidate`d, `quarantine`d, or `purge`d depending on safety policy.
- **gap-13 contradiction resolution** — replaces the dream-daemon's name-keyed LWW (§3.3) with bi-temporal invalidate.
- **WS4 (eval)** — the §3.2 eval signals are WS4 work-items.
- **WS5 (scoring)** — formalizes the score function; this brief specifies the *shape*, WS5 the *math*.
- **WS6 (API)** — exposes `promote` and `forget` MCP verbs that drive the synchronous flag-write half of the engine (composition §4.2).
- **WS7 (migration)** — the SCNS dream-daemon is being copied (not cut) per WS7 phase A; this brief is the spec for the rebuild that lands in Lethe.
