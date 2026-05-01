# gap-13 — Contradiction resolution beyond timestamp-invalidation

**PLAN.md §WS3 Track B item #7** (contradiction resolution beyond timestamp-invalidation).
**Tier:** first-class.
**Status:** **WS2 committed the v1 answer** (HANDOFF.md §2.3: bi-temporal invalidate, don't delete; synthesis §1.2). This brief documents that commitment, **stress-tests it at high contradiction density**, names the break-points that move us off it, and defines the eval signal that detects them. **It does not re-litigate the choice.**
**Substrate:** brief 01 Zep (bi-temporal primitive); brief 12 Graphiti (`valid_from / valid_to` is native); brief 05 Cognitive Weave (timestamped invalidation in resonance graph); brief 02 MAGMA (causal-edge partitioning enables typed contradiction); SCNS audit §1 (current name-keyed last-write-wins — strictly weaker, replaced by this commitment); dream-daemon design note §2.6 (LWW break-point); synthesis §1.2 + §2.5 + §3.10.
**Cross-refs:** composition design §5 (T1/T2 ACID boundaries); §6 (provenance survives invalidate); §7 (peer-message corruption row). Pairs with gap-11 (forget modes — invalidate is the substrate); gap-01 (contradiction-penalty term in score); gap-03 (ε weight on contradiction).

---

## 1. The gap

PLAN.md §WS3 explicitly listed contradiction resolution as a Track B gap because the source PDF flags it as open: bi-temporal invalidation is a clean v1 answer, but **what happens at conflict density > 1/week?** The PDF asks the question; it does not answer it.

The WS2 review converged on a settled answer for v1: **bi-temporal invalidate, don't delete.** Synthesis §1.2 calls this "the cross-paper consensus replacement for SCNS's name-keyed last-write-wins." Briefs 01 (Zep), 05 (Cognitive Weave), and 12 (Graphiti) all stamp contradicted facts with an end-of-validity timestamp; the substrate (Graphiti) ships the primitive natively.

For Lethe specifically, the gap that remains is **not "what does v1 do" — that's settled — but "where does the v1 answer break, and how do we detect we've hit the break-point?"** Without the break-point analysis:

- We may ship v1 confident the substrate handles contradiction, then quietly degrade as the rate increases past a threshold no one defined.
- WS5 (scoring) can't pin the ε weight on contradiction-penalty without knowing what the realistic conflict-density distribution looks like.
- gap-11 (forget) and this brief share the bi-temporal substrate; if it breaks, both break together. We need a coordinated detection signal.

This brief converts a **disposed gap** into a **monitored commitment** — the v1 answer is fixed; the eval signal that says "v1 is no longer enough" is what's added.

---

## 2. State of the art

The committed answer summarized:

- **Brief 01 Zep §architecture.** When a fact's truth-value changes, write a new fact-edge with `valid_from = now()` and update the previous edge to `valid_to = now()`. Both edges are queryable; default `recall` filters by `valid_to IS NULL OR valid_to > query_time`.
- **Brief 12 Graphiti.** Native `valid_from / valid_to` on every edge. The `recorded_at` (when we *learned* the fact) is also kept, giving bi-temporality. Substrate ships the primitive; Lethe's job is to *use* it correctly.
- **Brief 05 Cognitive Weave §"resonance graph."** Same shape, with a residual-baseline term in the decay function so a re-validated fact recovers gracefully.
- **Brief 02 MAGMA causal-edges.** Adds a typed-edge dimension: contradictions on a *causal* edge are different from contradictions on a *semantic* edge. v1 doesn't partition this way; v2 candidate.

What v1 does **not** do:

- **Semantic merge.** Charter §4.2 explicit non-goal: "v1 uses timestamp-invalidation with audit trail (à la Zep bi-temporal). Semantic merge is open research." Two contradictory facts both stay; the system does not attempt to *fuse* them.
- **Conflict negotiation.** No mechanism for asking the agent (or another agent) "which side is right?" — the resolution is *temporal* (most recent wins for default queries) plus *audit-preserving* (older side queryable in audit mode).
- **Causal-edge specialization.** All edges treated equivalently for invalidation purposes.

---

## 3. Where bi-temporal invalidate breaks (the stress tests)

The PDF's question — *what happens at conflict density > 1/week?* — needs to be operationalized. Four named stress regimes, each with a detection signal.

### 3.1 Stress 1 — high contradiction density on a single fact

**Scenario.** Fact F is contradicted N times in T days, oscillating: A → ¬A → A → ¬A. Each contradiction creates a new edge with new bi-temporal stamps; the audit trail grows.

**Where it breaks.**
- Storage: O(N) edges per fact. At density 10/week, one year's accumulation = ~520 edges/fact. Bounded but not ignorable.
- Recall: default query (`valid_to IS NULL`) returns the most recent; correct.
- Audit: querying "what did we believe on date D" still works — but if N > 100, the audit becomes hard to read.
- **Score signal noise:** the contradiction-penalty term ε in gap-01 candidate (b) score depends on contradiction count or rate; oscillation inflates it without a real loss of confidence.

**Detection signal.** Per-fact contradiction-count distribution. Healthy: median 0, p99 < 5. Break-point: p99 ≥ 20 within any 30-day window for a given tenant.

**v1 mitigation.** None at the substrate level. At the score level, gap-03 ε can be re-shaped from "count" to "log(count)" to dampen oscillation. Detected post-launch, fixed in v1.x.

### 3.2 Stress 2 — high contradiction density across the substrate

**Scenario.** The *aggregate* contradiction rate across all facts in a tenant exceeds a threshold (e.g., 1/week per fact on average, or hundreds of contradictions per dream-daemon cycle).

**Where it breaks.**
- The dream-daemon's consolidation cycle gets dominated by contradiction handling. Other phases (extraction, scoring, projection regen) starve.
- S5 consolidation log grows fast; audit becomes impractical without indexing.
- **Indicates upstream extraction quality issue (gap-06):** if extraction were precise, real-world contradictions are rare; high aggregate rate often means LLM-extraction is producing spurious "contradictions" between paraphrases of the same fact.

**Detection signal.** `contradictions_per_consolidation_cycle / facts_processed_per_cycle`. Healthy: < 0.05 (5%). Break-point: > 0.20 sustained across 5 consecutive cycles.

**v1 mitigation.** This is a gap-06 (extraction quality) signal at root; the *symptom* shows in this gap. Mitigation: extraction-confidence threshold on contradictions (only invalidate if both sides have confidence > 0.7); below threshold, log without invalidating, flag for human review.

### 3.3 Stress 3 — adversarial / poisoned contradictions

**Scenario.** A peer message (gap-10) or a buggy ingest pipeline injects a wave of contradictions designed to invalidate good facts.

**Where it breaks.**
- Bi-temporal invalidate is *symmetric* — the most recent assertion wins, regardless of source quality. A malicious peer can trivially "invalidate" any fact by asserting its negation.
- Provenance survives (gap-05) so audit is intact; but *recall* is degraded for the duration.

**Detection signal.** Contradiction events where the *contradicting* side has provenance trust-score below threshold (e.g., from a peer agent flagged as low-trust). Healthy: 0. Break-point: any.

**v1 mitigation.** This is the **canonical case for `forget(quarantine)`** (gap-11 §3.2). The poisoned episode is quarantined; cascade-invalidate restores the prior facts. Bi-temporal invalidate alone does *not* solve this; it needs gap-11. The two gaps are coupled.

### 3.4 Stress 4 — simultaneous contradictions from concurrent agents

**Scenario.** Agent A asserts F at the same time agent B asserts ¬F. Both writes hit S1; race condition determines which is "more recent."

**Where it breaks.**
- Composition §5.2 (multi-tenant + multi-agent isolation) holds within a tenant: agents share S1. Without serialization on the fact-key, both writes can produce conflicting valid_from stamps with sub-millisecond differences.
- The "winner" is determined by clock resolution, not semantic priority.

**Detection signal.** Pairs of edges on the same `(subject, predicate, object)` triple with `valid_from` within 100 ms of each other. Healthy: rare (< 0.1% of writes). Break-point: > 1% sustained.

**v1 mitigation.** Defer to gap-04 (multi-agent concurrency). The gap-04 lock-or-merge policy on writes to the same triple is the substrate; this brief consumes its decision.

---

## 4. The detection-signal contract

What this brief commits to: **Lethe instruments four metrics from day one** so the breakpoints in §3 are observable. (Ops dashboard, not API surface.)

| Metric | Source | Healthy | Break-point | Action on break |
|---|---|---|---|---|
| Per-fact contradiction count, p99 over 30d | S1 query | < 5 | ≥ 20 | Reshape ε term in gap-03; consider per-fact rate-limit on invalidation |
| Aggregate contradiction rate per cycle | S5 | < 5% | > 20% sustained | Investigate extraction quality (gap-06); raise extraction-confidence threshold |
| Low-trust-side contradiction count | S1 ⨝ S2 trust scores | 0 | any | Trigger gap-11 quarantine workflow; alert |
| Concurrent-write contradictions (Δ valid_from < 100 ms) | S1 | < 0.1% | > 1% | Engage gap-04 lock policy upgrade |

These are not just metrics — they are the **eval signal** that decides whether bi-temporal-only is still adequate at v1.x or whether a v2 mechanism (semantic merge, causal-edge partitioning, conflict negotiation) is needed.

---

## 5. Candidate v1 approaches

The choice between candidates was settled by WS2; this section preserves the considered options for completeness and to make explicit what v1 is *not* doing.

### Candidate (a) — Bi-temporal invalidate (committed)

**Sketch.** Per §2 above. Graphiti's native primitive; Lethe wraps it with the score-side ε term and the detection signals from §4.
**Cost.** Lowest. Substrate native.
**Failure modes.** §3.1–§3.4.
**Eval signal.** §4 metrics.

### Candidate (b) — Bi-temporal + semantic merge (rejected for v1; charter §4.2)

**Sketch.** When two facts contradict, run an LLM merge pass that produces a single reconciled fact with a higher-confidence stamp.
**Cost.** LLM call per contradiction; high.
**Failure mode.** Hallucinated merges; opacity (no audit of *what* was merged); reproducibility.
**Why rejected for v1.** Charter §4.2 explicitly defers semantic merge as "open research."

### Candidate (c) — Bi-temporal + causal-edge partitioning (rejected for v1; deferred to v2)

**Sketch.** Adopt MAGMA's causal/semantic/temporal/entity edge taxonomy; treat contradictions on causal edges differently from semantic.
**Cost.** Schema complexity; ontology evolution problem (synthesis §2.11).
**Why rejected for v1.** Multi-graph MAGMA is charter §4.2 v2 target.

### Candidate (d) — Bi-temporal + voting (rejected for v1)

**Sketch.** When N contradictions exist, the side with the majority of provenance count wins.
**Cost.** Low impl, but breaks brief 04 minority-hypothesis retention (gap-11 §4).
**Why rejected.** Direct conflict with gap-11 safety commitment.

### Trade-off table

| Axis | (a) Bi-temporal | (b) +Merge | (c) +Causal partition | (d) +Voting |
|---|---|---|---|---|
| Substrate-native | ✅ | partial | partial | ✅ |
| Audit preserving | ✅ | partial (merged fact loses sides) | ✅ | ✅ |
| Charter compatible | ✅ | ❌ §4.2 | ❌ §4.2 | ✅ but breaks gap-11 |
| Reproducible | ✅ | ❌ (LLM) | ✅ | ✅ |
| Handles §3 stresses | partial — needs gap-11 + gap-06 + gap-04 to fill | better on §3.1, worse on §3.3 | better on §3.1, neutral on §3.3 | catastrophic on §3.3 |
| v1 ready | ✅ | ❌ | ❌ | ❌ |

---

## 6. Recommendation

**Candidate (a) — bi-temporal invalidate (committed by WS2).** No re-litigation.

Lethe v1 ships with:

1. Bi-temporal `valid_from / valid_to / recorded_at` on every fact-edge (Graphiti native).
2. Default `recall` filter: `valid_to IS NULL OR valid_to > now()`.
3. Audit-mode recall (`recall(query, as_of_date=D)`) returning what was valid on date D.
4. Score-side contradiction penalty ε from gap-03 (form here, magnitude there).
5. **The four §4 detection signals instrumented from day one**, surfaced in `lethe-audit lint` and the ops dashboard.

The signals decide, post-launch, whether v1.x needs to extend.

**Stop-gap.** None — this *is* the v1 answer; if it has a degraded mode, it's the gap-11 quarantine fallback for adversarial cases (§3.3) plus the gap-06 extraction-confidence threshold for noise cases (§3.2).

---

## 7. Residual unknowns

What we are still betting on:

- **Conflict density distribution in real workloads.** We don't know whether agent-workflow memory has §3.2-class contradiction rates > 20% or whether it stays comfortably under. Bet: under, *if* extraction quality (gap-06) is good. The two are coupled.
- **Audit query latency at high invalidation density.** A fact with 500+ historical edges may make audit queries slow. Graphiti has no published p99 for this regime. Instrument; if p99 audit > 5 s, add summarization or compaction (post-v1).
- **Score-term shape for ε.** Gap-03 §4 candidate (b) uses ε multiplicatively; if oscillation (§3.1) is common, log-shaping is the fix. Empirical.
- **`as_of_date` semantics across concurrent writes.** If two agents write near-simultaneously, an audit query for `as_of_date = now()` returns whichever's stamp won. Documented edge case; gap-04 owns the policy.
- **Re-validation as inverse of invalidate.** A fact correctly re-asserted after being invalidated should not just write a new edge — it should set `valid_to = NULL` on the original (cheap, audit-preserving). Whether to expose this as a `revalidate` API verb is open. Bet: yes, post-v1, gated as admin-only.

---

## 8. Touch-points

- **gap-01 retention engine** — score formula consumes the contradiction-penalty term ε; demotion of the losing side is a separate decision (the loser is still queryable in audit; whether it's also demoted is a score question).
- **gap-03 scoring weights** — owns the magnitude of ε and its functional form (linear vs. log).
- **gap-04 multi-agent concurrency** — owns the §3.4 break-point's lock policy.
- **gap-05 provenance enforcement** — bi-temporal stamps mean the older side is preserved; provenance must travel with it so audit queries know *who said what when*.
- **gap-06 extraction quality** — high aggregate contradiction rate (§3.2) is often an extraction-noise symptom; gap-06 owns the upstream fix.
- **gap-10 peer messaging** — peer-source weighting + low-trust-side detection (§3.3).
- **gap-11 forgetting-as-safety** — shares the bi-temporal substrate. Adversarial contradictions (§3.3) trigger gap-11 quarantine. The two gaps are coupled at the substrate.
- **WS4 (eval)** — runs the §4 detection signals as eval-set criteria; produces the "is bi-temporal still enough?" verdict per release.
- **WS5 (scoring)** — owns the formal definition of ε.
- **WS6 (API)** — exposes `recall(..., as_of_date=)` for audit; gates `revalidate` (post-v1).
- **WS7 (migration)** — SCNS's name-keyed LWW data must be re-stamped on import: the latest entry per name keeps `valid_to=NULL`, prior entries get retroactive `valid_to=<next-overwrite-time>` from the SCNS audit trail. Documented in migration phasing.
- **WS8 (non-goals)** — semantic merge (charter §4.2) explicitly out; this brief reaffirms.
