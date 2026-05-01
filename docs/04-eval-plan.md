# 04 — Eval & Benchmark Plan (WS4)

**Status:** v1 plan, awaiting WS4-QA fresh-eyes pass.
**Substrate:** PLAN §WS4; gap-14 (input constraints, headline); gap-12 (classifier accuracy = headline metric); gap-06 §3 (extraction F1 + per-domain calibration); gap-01 §6 (per-phase dream-daemon eval signals); gap-02 (utility ≠ eval; relationship clarified); composition §7 (failure modes to inject); synthesis §2.6 (cost/latency framing).
**Cross-refs:** Gates WS5 (per-phase signals are the WS5 keep/replace/extend inputs); WS6 (eval surfaces shadow-retrieval verbs and the opt-in audit-log capture verb that powers v1.x operator-trace ingest); WS8 (drift detector + monthly re-eval are deploy-cadence dependencies). **Lethe stands on its own:** no Lethe artifact reads from SCNS; no Lethe code imports from the SCNS repo; no Lethe eval input comes from SCNS `session_store`. The SCNS dream-daemon remains a design-pattern reference only (WS1 audit / gap-01), not a data source.

This document specifies **what we measure, on what cases, with what defenses against confirmation bias, in what reporting epochs, with what fault injection, and via what harness shape.** It does *not* specify scoring math (WS5), API verbs (WS6), or deploy cadence (WS8); each is referenced where it touches the eval surface.

---

## 1. Frame & scope

WS4 owns:
- The **eval set** (composition, sourcing, contamination defenses, versioning).
- The **benchmark adapters** (LongMemEval, LoCoMo, DMR) and their applicability caveats.
- The **headline metrics** (precision@k, recall@k, latency p50/p99, context-budget adherence, suggestion FP rate, promotion precision; plus classifier F1, extraction F1, cost).
- The **shadow-retrieval harness** (compute-don't-surface) and the **chaos/fault eval** harness.
- The **reporting protocol** (two epochs, two strata, public-comparison template).

WS4 does **not** own:
- **Scoring math.** Weights, decay constants, the `δ·utility_signal` term — WS5. WS4 produces the calibration *signal* (eval-set output); WS5 turns it into numbers.
- **Utility-feedback loop.** gap-02 §1 is explicit: utility informs scoring; eval validates scoring; the two are not the same surface. The utility ledger (citation-diff, repeat-recall, no-op penalty) is *upstream of* scoring; the eval set is *downstream of* both. Conflating the two re-introduces the confirmation hazard gap-14 was written to prevent.
- **API surface.** WS6 owns verbs; WS4 consumes them.
- **Deploy cadence.** WS8 owns scheduling of the monthly held-set re-eval and the drift-detector alarm; WS4 specifies the cadence and the threshold, WS8 wires it.

The headline question every WS4 artifact answers: **does a change to retention/scoring/extraction make Lethe better, by what stratum, at what cost, against an eval set the implementer did not solely author?**

---

## 2. Reporting epochs

Two epochs are designed in from day one (gap-14 §5(1) closing clause; HANDOFF §8.1).

### 2.1 v1.0 — launch (preliminary, operator slice empty)

**v1.0 composition (acknowledged-and-deferred deviation from gap-14 §5(1)):** 0% operator / 35% adversarial / 25% ablation / 25% synthetic / 15% author-curated. The 30% operator-derived target from gap-14 §5(1) is a **v1.x target, not a v1.0 launch target**. Lethe ships before any operator data exists; there is no pre-existing operator-trace source the project will ingest from. (In particular, SCNS `session_store` is **not** a v1 input — Lethe stands on its own, and SCNS remains a design-pattern reference only.) The deferral is explicit, traceable in §13, and carried by the two-epoch design.

**Headline-tag (mandatory on every v1.0 public report or comparison):**

> `preliminary — operator slice empty (0%); author + adversarial + ablation + synthetic only; v1.x target 30% operator-derived`

The tag is rendered by `metrics/emitter.py` (§10) and is non-removable at the harness layer — a CI gate fails the build if a v1.0 report is emitted without the tag.

**Gating criterion to leave v1.0:** operator-derived share ≥ 20% by case-count, *and* author-curated share ≤ 10% (the v1.x cap, tighter than the v1.0 cap of 15%), sustained over two consecutive monthly re-eval runs. Operator data accumulates from Lethe's own opt-in audit-log capture (§4.6) once Lethe is deployed; below the threshold, we stay in v1.0 reporting mode regardless of calendar time.

### 2.2 v1.x — post-operator-data

Once the gating criterion is met, the report tag drops the `preliminary` qualifier and the public comparison template publishes both strata (§5.9) without the operator-empty warning. Composition rebalances to the gap-14 §5(1) targets: 30% operator / 25% adversarial / 20% ablation / 15% synthetic / 10% author-curated. The eval-set version bumps (`v1.x.0`); the previous snapshot remains available for reproducibility.

The operator-derived material at v1.x comes entirely from Lethe's own opt-in audit-log capture (§4.6) — production Lethe tenants who consent to having their traces feed the eval set, with provenance and privacy-scrub. There is no path that involves importing traces from any other system.

### 2.3 Why two epochs and not one

A single-epoch plan would force one of three errors: (a) delaying any public eval until operator data accumulates (charter §3 says guard-rail evaluation is non-negotiable), (b) shipping author-heavy v1 numbers as if they were definitive (the exact failure gap-14 was written to prevent), or (c) faking an operator slice by importing from a foreign system that does not share Lethe's data model or consent boundary (the failure mode the SCNS revocation closes). Two explicit epochs lets us ship measured-and-tagged numbers from day one and upgrade the rigor as Lethe's own substrate matures, with no foreign-system dependency on the critical path.

---

## 3. Public benchmarks — inclusions and limitations

Synthesis §1.6 names three memory benchmarks at known saturation levels; we adopt all three with explicit caveats. None replaces the Lethe-native set (§4); each measures something Lethe must be *competitive* on, not optimal-against.

### 3.1 LongMemEval

**What it measures.** Long-horizon temporal recall over conversational turns; the agent must answer questions whose evidence is dispersed across hundreds of prior turns.

**Why we use it.** It is the closest public proxy for Lethe's `recall(query, intent, scope)` over a long episode tail. It exercises the temporal-vs-semantic split (gap-01 §6 residual: "two-stream Q1 outcome — until WS4 measures the temporal-vs-semantic split on LongMemEval, we don't know whether one-stream is sufficient").

**Caveats.**
- Conversational, not agent-workflow. PLAN §WS4 names this caveat directly. Agent workflows have tool-call/structured-output traces; LongMemEval does not.
- Single-tenant. Cross-tenant or multi-agent isolation (gap-04) cannot be measured here.
- Author-of-benchmark bias: LongMemEval was authored by memory-system researchers; the cases reflect what they thought a memory system should do.

**How we run it.** `adapters/longmemeval.py` maps LongMemEval cases onto the common `Case` schema (`lethe_native/schema.py`) and routes them through `recall`. Latency is measured per §5.2.

### 3.2 LoCoMo (and LoCoMo-Plus)

**What it measures.** Long-horizon dialogue memory over multi-session conversations. LoCoMo-Plus extends with non-factual content (preferences, goals; synthesis §2.9).

**Why we use it.** LoCoMo-Plus is the only public benchmark that exercises non-factual memory at all. gap-09 (non-factual memory) is otherwise unmeasured; LoCoMo-Plus is the v1 proxy.

**Caveats.**
- Conversational again; same agent-workflow mismatch.
- Saturation: top systems already score near ceiling on LoCoMo. Headroom is small. We use it as a *non-regression* benchmark, not a leaderboard target.
- Non-factual cases are a small slice of LoCoMo-Plus; per-class F1 is noisy.

### 3.3 DMR

**What it measures.** Dialogue memory recall; short-horizon factual lookup over conversational context.

**Why we use it.** DMR is the most-saturated of the three (synthesis §1.6); a regression here is a strong "something broke" signal. We treat DMR as a smoke test, not a discrimination signal.

**Caveats.** Saturation makes DMR insensitive to improvement; useful only for regressions.

### 3.4 What none of them measure

Synthesis §2.6 is explicit: **DMR, LongMemEval, LoCoMo all report accuracy. None reports tokens-per-query or p95 latency.** A system burning a full context replay scores identically to a surgical retrieval. This is the gap the Lethe-native eval set (§4) and the cost dimension (§5.8) close. Public-benchmark numbers without cost numbers are *not* WS4 outputs; the harness emits both or neither.

Other gaps the public benchmarks miss: context-budget adherence (§5.3), suggestion FP rate (§5.4), promotion precision and demotion recall (§5.5), fault tolerance (§7), drift sensitivity (§8). All of these are Lethe-native-set responsibilities.

---

## 4. Lethe-native eval set

The Lethe-native set is the substrate that resists confirmation bias (gap-14). Every WS4 headline number that *isn't* a public-benchmark passthrough is computed against this set.

### 4.1 Composition targets, by source class

Per gap-14 §3 taxonomy. v1.0 percentages reflect the operator-empty deferral (§2.1); v1.x percentages restore the gap-14 §5(1) targets.

| Source class | v1.0 share | v1.x target | Bias resistance | Cost |
|---|---|---|---|---|
| **Operator-derived (Lethe's own opt-in audit-log capture)** | **0%** (acknowledged-and-deferred per §2.1) | 30% | Strong — neither implementer nor benchmark-author chose; Lethe's own deployed users contribute via opt-in | Low (free; pipeline lives in Lethe; see §4.6) |
| **Adversarial red-team** | **35%** | 25% | Strong — written by reviewer not on implementation team | Medium (reviewer time) |
| **Ablation pairs** | **25%** | 20% | Strong — perturbation, not selection | Low (programmatic) |
| **Synthetic LLM-generated** | **25%** | 15% | Medium — tagged, spot-checked, capped | Low |
| **Author-curated** | **15%** (cap) | 10% (cap) | **Weak — confirmation hazard; capped** | Low |

**v1.0 rebalance rationale.** With operator at 0% (§2.1), the 30 percentage points are redistributed to the three strongest bias-resistance classes (adversarial +10, ablation +5, synthetic +10) with a small bump to author-curated (+5, but still capped at 15%) to fill remaining coverage gaps. Adversarial gets the largest share because it is the strongest bias-resistance class authored by humans (the only class that can probe boundaries the implementer would not think to probe). Synthetic gets a temporary boost with the 5% spot-check budget doubled to 10% to compensate for the increased reliance on it.

**Floor enforcement at v1.0.** Author-curated is **never** allowed above 15% by case-count at v1.0 (10% at v1.x); below this cap the eval-set build fails and the harness refuses to emit a "headline" report (it can still emit per-stratum reports, but they are not aggregated into a headline). Adversarial below 30% at v1.0 also fails the build — with the operator slice empty, adversarial is the load-bearing bias-resistance class.

**Migration plan v1.0 → v1.x.** As Lethe's opt-in audit-log capture (§4.6) accumulates operator-derived candidates, they enter the eval set in monthly batches. Each batch displaces synthetic and author-curated cases first (since those are the weakest bias-resistance classes), then ablation and adversarial proportionally to maintain symmetry policy (§4.3). The migration is complete when the v1.x target distribution is hit and sustained for two consecutive monthly re-eval runs; at that point §2.1's gating criterion is satisfied.

### 4.2 Construction protocol & sourcing

**Operator-derived (v1.0 share: 0%; v1.x target: 30%).**

- v1.0: **empty slice.** No foreign-system import. The operator-derived class at v1.0 is acknowledged-and-deferred per §2.1; the headline-tag flags this on every public report.
- v1.x source: Lethe's own opt-in audit-log capture (§4.6). Production Lethe tenants who consent contribute their own traces; selection within consented traces is biased toward turns that exhibit operator-derived signal (the operator edited the system's response, retrieved a stale memory, filed a complaint, or invoked `recall_outcome` with a corrective signal). These are operator-derived cases that neither the implementation team nor any benchmark author chose.
- Throughout: GitHub-issue-class tasks where a real user names a memory-system failure (Graphiti issue #1300 is the canonical exemplar) are admissible *if and only if* they describe a failure pattern that can be reproduced inside Lethe with synthetic data; the issue itself is the inspiration, the case is constructed inside the Lethe harness from scratch. This is not foreign-data ingest.

**Adversarial red-team (v1.0 share: 35%; v1.x target: 25%).**

- v1 sourcing rule: **internal-but-different-team reviewer.** A reviewer not on the WS4/WS5 implementation team writes the cases. The reviewer is given the seven-class intent taxonomy (gap-12 §3) and the seven failure modes from composition §7 and asked to author cases that adversarially probe boundaries.
- v1.x sourcing rule: external consultant pass added on top of the internal reviewer.
- Output: a slice tagged `source=adversarial`, with the reviewer's notes captured in S5 for audit.
- v1.0 emphasis: at 35%, adversarial is the load-bearing bias-resistance class while operator is empty. Reviewer throughput is the v1.0 schedule risk; if adversarial cannot reach 35% before launch, headline reports are blocked until it does (per §4.1 floor enforcement).

**Ablation pairs (v1.0 share: 25%; v1.x target: 20%).**

- Generated programmatically: per scoring weight (α, β, γ, δ, ε; gap-03), per gate threshold (classifier confidence; extraction confidence; consolidation gate interval), per heuristic in gap-12 §6. Rough budget per gap-14 §6 residual: ~30 ablation pairs at v1.x; v1.0 budget is ~40 pairs (the 5% boost folds in additional weight × intent-class cross terms).
- Each pair: `(baseline_case, perturbed_case)` where perturbation is a single weight or threshold change. The eval question: does the metric move in the predicted direction?
- Ablation pairs are the **strongest** bias-resistance class — they are perturbations, not selected examples — and v1.0 leans on them disproportionately for that reason.

**Synthetic LLM-generated (v1.0 share: 25%; v1.x target: 15%).**

- LLM authors cases against the same seven-class taxonomy. Tagged `source=synthetic`. Cases are visible to the harness but **never** counted in the operator+adversarial+ablation+replay-only stratum (§5.9).
- Spot-check protocol (gap-14 §6): at v1.0, **10% of synthetic cases** per batch are reviewed by author + adversary (doubled from the v1.x 5% to compensate for the elevated synthetic share); if disagreement > 15%, the entire batch is distrusted (set aside, not deleted; tagged `synthetic_distrusted`). The disagreement-rate is itself a metric, emitted on every build.
- v1.x reverts to the 5% spot-check sample once synthetic share drops back to 15%.

**Author-curated (v1.0 share: 15%; v1.x cap: 10%).**

- Implementation team writes cases. Tagged `source=author`. **Always** excluded from the strict-stratum report (§5.9). The implementation team gets to write cases for their own coverage benefit; those cases never appear in a public headline number.

### 4.3 Negative-case symmetry policy

Per gap-14 §5(5): for every "should remember" case, an adversarial counterpart exists ("looks similar, should NOT remember"). Same for `recall` (relevant vs. distractor) and `forget` (must-purge vs. must-not-purge). The policy applies across **all** source classes — operator, adversarial, ablation, synthetic, author. Eval-set build fails if any class has a positive-to-negative ratio outside [0.7, 1.3]; classifier (gap-12) and forget-gate (gap-11) evals are symmetric by construction.

### 4.4 Contamination defenses

Per gap-14 §5(2):

1. Every Lethe-native eval-set fact gets a `contamination_protected = true` flag in S2 keyed by stable fact-id.
2. The runtime's `remember` write path checks the flag; a system attempt to `remember` a `contamination_protected` fact during normal operation is a CI-gate failure (the gate is `contamination/guard.py`, §10).
3. Provenance enforcement (gap-05) makes the check verifiable — every fact-id has a stable provenance chain back to its eval-set source, and the gate compares the *content* (not just the id) to detect content-level contamination via paraphrase.
4. Eval-set fact-ids are versioned per §4.5; a retired eval fact loses its protected flag and is allowed back into the runtime's `remember` path on the next build.

The contamination guard runs in two modes: **strict** (CI-gate, fails the build) and **shadow** (logs only, used during development). The harness emits `contamination_events` as a metric on every run.

### 4.5 Versioning & retirement

- Each case has a stable `case_id`, a `version`, a `source` tag, and a provenance pointer to its origin record (Lethe tenant-id + opt-in record for operator cases, reviewer-id for adversarial, ablation-spec for ablation, LLM-generation-batch-id for synthetic, author-id for author-curated).
- The eval set is published as immutable snapshots (`eval-set@v1.0.0`, `eval-set@v1.0.1`, …); a snapshot id is reproducible and is recorded with every report.
- **Case retirement.** When ground truth changes (a fact becomes stale, a procedure is deprecated, a preference is reversed), the case is retired, *not* deleted. A `case_retirement` event lands in S5 with `(case_id, prior_version, retired_at, reason)`. Reports against an old snapshot continue to score the retired case at its prior ground truth; reports against the new snapshot exclude it.
- Eval-set version drift detection: if more than 5% of cases retire between snapshots, the system flags an alarm (drift-of-truth, distinct from drift-of-input in §8).

### 4.6 Operator-trace ingest (Lethe self-collection; v1.x pipeline)

The v1.0 operator slice is empty (§2.1, §4.1, §4.2). The v1.x operator slice is sourced **entirely from Lethe's own opt-in audit-log capture** — there is no foreign-system import, no SCNS dependency, and no path that bypasses tenant consent.

**Pipeline shape (v1.x; placeholder at v1.0):**

1. **Opt-in capture (WS6 surface).** A Lethe tenant explicitly opts in to having their `recall` / `remember` / `forget` / `peer_message` traces flow into the eval-set candidate pool. Opt-in is per-tenant and revocable; revoked tenants' previously-ingested cases are retired (§4.5) on the next snapshot. The verb that exposes opt-in lives in WS6's surface; this doc defines the contract WS6 must satisfy.
2. **Operator-signal selection.** From consented traces, select turns that exhibit operator-derived signal: the operator edited the system's response, the operator invoked `recall_outcome` with a corrective signal (gap-02), the operator manually `forget`-ed a fact the system retained, or the operator filed a complaint via the audit channel. These signals identify cases neither the implementation team nor any benchmark author chose — the bias-resistance property gap-14 §3 demands.
3. **Sensitivity classification.** Apply the gap-11 §3.3 sensitivity-class taxonomy to every candidate turn: PII, secrets/credentials, sensitive-class regex hits, third-party-named entities. Each class gets a scrub action (redact, hash, drop-turn, escalate).
4. **Scrub.** Apply actions; produce a scrubbed candidate.
5. **Review.** A reviewer (not on the implementation team, per the adversarial sourcing rule §4.2) confirms the scrub is sufficient. Scrubbed cases that fail review are dropped from the eval set, not retried with a weaker scrubber.
6. **Signal-loss check.** If scrubbing destroys the case's evaluative value (the question becomes ambiguous after redaction; the answer is no longer derivable from the scrubbed turns), the case is dropped. gap-14 §6 names this directly: "if it nukes too much signal, escalate."
7. **Audit log.** The scrub decision per case lands in S5 with provenance pointing at the original Lethe tenant-id, opt-in record, and reviewer-id. The original is retained per the tenant's consent terms; the eval-set candidate is the scrubbed version.

**v1.0 status of this pipeline.** None of steps 1–7 are exercised at v1.0 because there are no operator traces to ingest. The opt-in capture verb is a WS6 design dependency; the scrub-and-review pipeline is implemented as a stub-and-spec at v1.0 so the contract is clear, with a v1.x activation gate.

**What this pipeline explicitly does not do.**
- Does not import traces from any foreign system (no SCNS `session_store`, no other memory-system's audit log, no data broker).
- Does not capture from Lethe tenants who have not opted in.
- Does not retain unscrubbed operator traces in the eval set.
- Does not survive opt-out: revocation triggers retirement of previously-ingested cases.

**Why self-collection only.** Foreign-system ingest creates three liabilities: (a) consent boundary mismatch (operators of system X did not consent to system Y's eval), (b) data-model mismatch (foreign system's traces require structural rewriting that itself introduces bias), and (c) dependency on a system Lethe is supposed to stand independent of. Self-collection eliminates all three at the cost of a slower v1.0 → v1.x transition. The two-epoch design (§2) absorbs that cost.

---

## 5. Headline metrics

Every public WS4 report emits this metric vector. Per-metric stratification is specified per row.

### 5.1 Retrieval quality

- **precision@k** for k ∈ {1, 5, 10}. "Of the top-k results returned by `recall`, how many are relevant?"
- **recall@k** for k ∈ {1, 5, 10}. "Of the relevant facts in the eval-set ground truth, how many appear in the top-k?"
- **nDCG@k** for k ∈ {5, 10}. Position-aware quality; rewards relevant results higher in the rank.

Strata: per intent class (gap-12 §3), per source class (§4.1), per epoch (§2).

### 5.2 Latency

Per WS3-QA latency-stratification nit, latency is **always** stratified; an aggregate p50/p99 across all paths is meaningless and is not emitted.

- **p50, p99** per:
  - **Path:** `recall` (fact path), `recall_synthesis` (S4a path), `remember` (write path), `consolidate` (dream-daemon cycle), `forget` (any mode).
  - **Cache state:** cold start vs. warm.
  - **Tenancy:** single-tenant vs. multi-tenant (v1.x; placeholder at v1.0 since multi-tenant is gap-04 future).
  - **Shadow vs. live:** §9 shadow-retrieval reports its own latency.

### 5.3 Context-budget adherence

- **% of recalls fitting declared budget.** Caller declares a token budget; harness measures whether the response fits. Misses are the over-budget tail.
- **Over-budget tail distribution.** p95, p99 over-budget excess (in tokens). Gives WS5 a knob to tune.

### 5.4 Suggestion false-positive rate

For systems that surface `promote` suggestions or `forget` suggestions to the agent: of suggestions accepted by the agent, how many were wrong (later reversed)? The FP rate is the headline; the per-class breakdown (promote-FP, forget-FP) is the diagnostic.

### 5.5 Promotion precision and demotion recall

Both, not just promotion (gap-01 §6 needs both signals to decide keep/replace/extend on the dream-daemon's score-and-promote phase).

- **Promotion precision.** Of the facts the dream-daemon promoted, how many were correctly promoted (still relevant N days later, or cited downstream)?
- **Demotion recall.** Of the facts that *should* have been demoted (no utility signal, contradicted, retired by ground truth), how many did the dream-daemon actually demote?

### 5.6 Intent-classifier F1 (gap-12 headline metric)

Per-class F1 over the seven taxonomy classes (`remember:fact`, `remember:preference`, `remember:procedure`, `reply_only`, `peer_route`, `drop`, `escalate`). Headline is **macro-F1** (unweighted average) — this prevents a high-prevalence class from dominating. Per-class F1 is a diagnostic.

Baseline target per gap-12 §7 residual: 85% macro-F1 on the held-out symmetric set. Below 85%, the classifier itself is degrading recall; gap-12 §5 stop-gap (heuristic-only with high `escalate` rate) becomes the v1 fallback.

### 5.7 Extraction quality (gap-06 §3)

Three dimensions, all reported:
- **Recall.** Of facts present in the source episode, how many were extracted?
- **Precision.** Of facts extracted, how many are truthful and relevant?
- **Disambiguation accuracy.** For each extracted entity, did it bind to the correct existing node (vs. creating a duplicate)?

Plus a **per-domain calibration table** (gap-06 §3 names per-domain calibration explicitly): F1 per domain class (devops vs. legal vs. medical vs. consumer-product, etc., as they emerge in the eval set). Enables per-domain threshold tuning.

Threshold targets per gap-06 §6: quarantine rate target 5%, alarm at sustained > 15%; disambiguation F1 alarm at < 0.85.

### 5.8 Cost (fills synthesis §2.6)

- **Tokens per `recall`** (input + output, separately).
- **Tokens per `remember`** (extraction LLM call cost).
- **LLM calls per consolidation cycle** (extraction + classifier residual + synthesis-page regeneration).
- **Cost per benchmark question** for each public benchmark, alongside accuracy.

The accuracy-only public-benchmark report is **not allowed** by the harness (§3.4); cost is required.

### 5.9 Two-strata reporting (gap-14 §5(4))

Every public report or comparison emits **two** numbers per metric:

- **All-cases stratum:** all source classes pooled, including author-curated and synthetic.
- **Strict stratum:** operator + adversarial + ablation + replay-only. Author-curated and synthetic are excluded.

Both numbers are mandatory on every public comparison. Reporting only the all-cases number is a CI-gate failure; reporting only the strict stratum is allowed when the all-cases number would be uninformative (e.g., a tenant-specific subset). The headline target metric is the **strict-stratum number**; the all-cases number is the diagnostic.

---

## 6. Per-phase dream-daemon eval signals

gap-01 §6 is explicit: WS4 owns the eval signals that decide keep/replace/extend on each dream-daemon phase. WS5 will use these to choose module-level changes; the signals must be measurable per phase, not as an aggregate.

| Phase | What it does | Eval signal (the keep/replace/extend question) | Source metric (§5) | Stratification |
|---|---|---|---|---|
| **Extract** | Episode → entities + edges via LLM. | Does extracted F1 (recall, precision, disambiguation) clear gap-06 thresholds, per domain? Quarantine rate stable? | §5.7 | Per domain; per model version |
| **Score** | Compute (α·recency + β·structural + γ·intent + δ·utility + ε·…) per fact. | Does the resulting rank order agree with operator-derived ground-truth on the strict stratum? Promotion precision + demotion recall both improving? | §5.1 (nDCG), §5.5 | Per source class; per intent class |
| **Promote** | Score-above-threshold facts move from candidate → active. | Promotion precision; suggestion FP rate (when surfaced). | §5.4, §5.5 | Per intent class |
| **Demote** | Score-below-threshold or contradicted facts move active → candidate or invalid. | Demotion recall; absence-of-recall complaints (utility-feedback, gap-02). | §5.5; cross-ref gap-02 | Per source class |
| **Consolidate** | Synthesis pages regenerated; rollups computed. | Synthesis-page recall quality (`recall_synthesis` precision@k); regeneration cost (LLM calls); divergence between S1 and S4b within budget. | §5.1, §5.8; cross-ref composition §7 | Per page-class |
| **Invalidate** | Bi-temporal `valid_to` set on contradicted facts (gap-13). | Did the right side win? Operator-derived contradiction cases as ground truth. | §5.1 against contradiction-class cases | Per contradiction type |

Each phase produces a metric vector per build. The WS5 author reads §6 of this doc as the input contract: a phase whose vector regresses by more than the threshold (set per phase by WS5) is a candidate for replace/extend; a phase whose vector improves is keep.

The harness emits per-phase reports independently of the headline aggregate. WS5 should not need to reconstruct per-phase signals from a pooled report — `metrics/emitter.py` writes one row per phase per run.

---

## 7. Chaos / fault eval

Composition §7 is the input contract. Every named failure mode gets injected; pass criterion is **"degrade, don't fail"** per the §7 mitigation column.

### 7.1 Single-failure modes (composition §7)

| Failure | Inject via | Pass criterion |
|---|---|---|
| **S1 (Graphiti) down** | `chaos/faults.py` blocks Graphiti calls; returns connection error | `remember` returns 5xx with retry-after; `recall_synthesis` (S4a) still works; harness asserts the split |
| **S2 (SQLite) down or locked** | Lock the SQLite file; force `SQLITE_BUSY` | `remember` soft-fails per row 2; recall ledger writes fail; scoring falls back to baked-in defaults; recall otherwise works |
| **S3 (vector index) stale** | Drop a fraction of vectors from the index | Recall is degraded but never wrong; rerank still pulls fresh attributes from S1; lexical-only fallback catches what S3 misses |
| **S3 fully unavailable** | Disable vector index entirely | `recall` flow §3.1 step 3 collapses to graph-walk + lexical only; precision/recall delta measured |
| **S4a (synthesis pages) corrupted** | Truncate or paraphrase a synthesis page | `recall_synthesis` returns degraded results (missing pages); `recall` (fact path) unaffected |
| **S4b (markdown projections) diverged** | Modify a markdown projection out of band | No effect on `recall`; reconciler diff detects the divergence within one consolidation cycle |
| **S4b regeneration crash mid-write** | Kill the regeneration process between write and rename | Atomic-rename leaves either old or new file, never partial |
| **S5 (consolidation log) append fails** | Block S5 appends after S1 update | Reconciler writes a backfill entry tagged `provenance=reconciler, evidence=s1_state_diff`; S5-coverage% emitted as a system-health metric |
| **Peer-message corruption** | Inject a contradicting peer claim | Provenance distinguishes peer-asserted from self-observed; bi-temporal invalidate (gap-13) marks one side `valid_to=now`; provenance survives; `forget(quarantine)` works on the poisoned episode |
| **Dream-daemon stuck or crash-looping** | Hold the lock past 5× gate interval | Stale-lock break fires; failure backoff fires; ops alarm on `time-since-last-successful-consolidation > 2 × gate_interval` |
| **Tenant isolation breach** | Inject a missing `group_id` filter | Integration test asserts cross-tenant reads return zero; if any return non-zero, P0 fail |
| **Schema migration mid-flight** | Trigger a migration during normal ops | `remember` and `recall` are blocked during the migration window; drain + lock + migrate + release path measured |
| **Disk full** | Fill the disk to threshold | `remember` returns 5xx below threshold; no silent corruption |
| **Clock skew across runtime instances** | Inject ±60s clock offset per instance | Single-tenant single-writer assumption holds at v1; multi-writer is documented as a v2 problem (gap-04) |

### 7.2 Two-stores-down matrix (composition §7.1)

Three combinations measured at v1:

- **S1 + S3 down.** `recall` is dead; `recall_synthesis` survives; `remember` is dead. Health-endpoint named state: `lethe-down-fact-path`. Pass criterion: state is correctly reported, `recall_synthesis` continues to serve.
- **S2 + S5 down (shared storage).** No utility-feedback, no consolidation scheduling, no audit. Recall and remember technically work but the loop is open. Pass criterion: `remember` is defensively disabled; health-endpoint state `degraded-read-only`.
- **S1 + S4 down.** `recall` works (degraded; no synthesis); `remember` is dead. Pass criterion: state is `partial-availability` and the health endpoint surfaces the split.

`chaos/faults.py` parameterizes single-failure and two-stores-down injection from one config; the harness runs the full matrix on every WS4 build.

### 7.3 Non-pass criteria

A chaos run is **not** a pass if any of the following occur, regardless of the per-row criterion:
- Silent data corruption (any).
- Cross-tenant data exposure (any).
- A health-endpoint state inconsistent with the actual store state.
- An alarm that should have fired but didn't.

These four are P0 gates; they short-circuit the WS4 build.

---

## 8. Drift signals & re-eval cadence

gap-14 §5(3):

- **Distributional drift detector on input traces.** Continuously running; alerts when production input distribution diverges from eval-set input distribution beyond threshold. Threshold is set per-feature (turn-length, intent-class distribution, peer-vs-self ratio); aggregate drift is a JS-divergence proxy. Detection signal lands in S5 and triggers a manual eval-set top-up review.
- **Monthly held-set re-eval.** WS8 schedules; WS4 specifies the cadence (monthly) and the failure criterion (any headline metric regresses by > 5% on the strict stratum without an accompanying intentional change record).
- **Quarterly fresh adversarial slice.** Internal-but-different-team reviewer (per §4.2 sourcing rule) authors a fresh slice each quarter. Old slices remain in the set; new slices are appended. This is the primary defense against "the eval set itself is now familiar to the implementer."
- **Annual eval-set version bump.** Snapshot rolls forward; retired cases (§4.5) are dropped from the new snapshot; new operator-derived material is folded in.
- **Drift-of-truth alarm.** Distinct from drift-of-input (§4.5): if more than 5% of cases retire between snapshots, alarm.

---

## 9. Shadow-retrieval harness design

PLAN §WS4 names a "shadow-retrieval harness (compute but don't surface)" as a WS4 deliverable.

**Principle.** Production answers continue to come from the current system. A *shadow* path runs the candidate system on the same query in parallel; its results are emitted to the eval store, never to the caller. This lets us measure proposed retention/scoring/extraction changes against live queries without exposing callers to risk.

**Architecture.**
1. Caller issues `recall(query, intent, scope)`.
2. The runtime dispatches the query to **both** the production retrieval path and the shadow path.
3. Production path returns its result to the caller; the runtime records it.
4. Shadow path returns its result to the harness; the runtime records it without exposing it to the caller.
5. `metrics/emitter.py` writes a comparison row per query: `(query_id, prod_result_summary, shadow_result_summary, prod_latency, shadow_latency, agreement_score)`.

**Compute-don't-surface invariants.** The shadow path:
- Cannot mutate any store. Reads only.
- Cannot raise exceptions visible to the caller. All shadow exceptions are logged to S5 and counted as a `shadow_error` metric.
- Cannot exceed a configurable wall-clock budget. If the shadow path is slower than budget, its result is dropped (counted as `shadow_timeout`); the production path is unaffected.

**Implementation independence.** The shadow harness is a Lethe-internal facility; it does not depend on, dual-write to, or read from any external system. The dual-dispatch and agreement-scoring are both implemented inside `shadow/harness.py` (§10).

**Use cases.**
- A/B-test a new scoring weight without exposing callers.
- Validate a new extraction prompt against live episodes without contaminating the runtime.
- Measure regression of a candidate dream-daemon implementation against the production daemon over a real workload.

**Reporting.** Shadow-vs-production reports are emitted on every shadow run; they are **not** the headline metrics (which come from the eval set + public benchmarks), but they are a strong signal for "should we cut over?"

---

## 10. Harness architecture (`scripts/eval/`)

The directory layout, contracts, and exit conventions for the runnable skeleton. The skeleton lands as a sibling commit (`feat(ws4):`) to this doc. Language: Python 3, stdlib only at v1; future ML-eval deps (numpy, datasets, etc.) are deferred until needed.

```
scripts/eval/
├── README.md                       # what this tree is, how to run, contract index
├── run_eval.py                     # top-level harness entry; argparse over benchmark|stratum|epoch
├── adapters/
│   ├── __init__.py
│   ├── longmemeval.py              # contract: load LongMemEval; map to common Case schema
│   ├── locomo.py                   # contract: load LoCoMo (+ LoCoMo-Plus); map to Case
│   └── dmr.py                      # contract: load DMR; map to Case
├── lethe_native/
│   ├── __init__.py
│   ├── loader.py                   # contract: load Lethe-native cases by source-class + version
│   └── schema.py                   # contract: Case dataclass; source_class; provenance; tags
├── metrics/
│   ├── __init__.py
│   ├── retrieval.py                # contract: precision@k, recall@k, nDCG
│   ├── latency.py                  # contract: p50/p99 with stratification
│   ├── budget.py                   # contract: context-budget adherence
│   ├── classifier.py               # contract: intent-classifier F1, per-class
│   ├── extraction.py               # contract: extraction P/R/disambiguation
│   ├── cost.py                     # contract: tokens-per-verb, LLM-call-count
│   └── emitter.py                  # contract: write metric rows, render headline-tag
├── shadow/
│   ├── __init__.py
│   └── harness.py                  # contract: dual-path runner; compute-don't-surface
├── chaos/
│   ├── __init__.py
│   └── faults.py                   # contract: inject named failure modes from composition §7
├── contamination/
│   ├── __init__.py
│   └── guard.py                    # contract: CI gate; fail on system-remember of protected eval fact
└── reports/
    └── .gitkeep                    # report dir; per-epoch/run-id subdirs land here
```

**Stub conventions (every `.py`):**
- Module docstring naming the contract and cross-refs to this doc and the gap brief that motivates it.
- Public function signatures with `raise NotImplementedError` bodies (so import-time wiring is exercised).
- `if __name__ == "__main__":` block prints `"<module>: not implemented (WS4 stub)"` and exits 2 (conventional EX_USAGE).

**Snapshot path conventions:**
- Eval-set snapshots: `eval/sets/<snapshot-id>/cases.jsonl` (path is for reference; the directory does not yet exist at v1.0 and is created by the loader when implemented).
- Reports: `eval/reports/<epoch>/<run-id>/{summary.json, per-phase/, per-stratum/, per-benchmark/}`.

---

## 11. Reporting & artifacts

### 11.1 Report shape

Per run, the harness emits:

- `summary.json` — run id, epoch tag, headline tag (§2.1), composition stats (per-source-class case counts), all-cases and strict-stratum metric vectors per §5.
- `per-phase/` — one file per dream-daemon phase per §6.
- `per-stratum/` — all-cases.json and strict.json per §5.9.
- `per-benchmark/` — longmemeval.json, locomo.json, dmr.json each with accuracy + cost (§3.4 invariant).
- `chaos.json` — per-failure-mode pass/fail per §7; two-stores-down matrix per §7.2.
- `shadow.json` — agreement-score histograms per §9 (only present when shadow path was active).
- `contamination.json` — `contamination_events` count, mode (strict/shadow).
- `provenance.json` — eval-set snapshot id; runtime version; model versions used.

### 11.2 Public comparison template

For a public comparison (Lethe vs. another system; or Lethe v1.0 vs. v1.x):
- Headline tag rendered if v1.0.
- Per-metric: strict-stratum number (headline) + all-cases number (diagnostic), side by side.
- Per-public-benchmark: accuracy + cost, both columns mandatory.
- Composition stats published (so a reader can verify the strict stratum is not gamed by under-populating it).

### 11.3 Where reports live

`eval/reports/<epoch>/<run-id>/`. Reports are committed to the repo on a tag boundary (every release); intermediate reports live in the eval store only.

### 11.4 CI-gate report

Every PR touching scoring (WS5), retention (gap-01), extraction (gap-06), or eval (this doc) runs the harness and emits a CI-gate report. Headline regressions on the strict stratum > 5% block merge unless the PR description includes an `eval-regression-justified:` line with a reviewer.

---

## 12. Open questions / residual unknowns

- **Synthetic-bias detection threshold.** 15% disagreement (§4.2) is a bet. If the spot-check regularly clears or regularly fails, retune.
- **Ablation-pair coverage.** ~30 pairs is a bet (gap-14 §6). If the per-pair signal-to-noise is low, expand to per-(weight × intent-class) cross product (~100 pairs) at the cost of a bigger ablation budget.
- **Operator-slice ramp rate (v1.0 → v1.x).** How fast Lethe's own opt-in audit-log capture (§4.6) accumulates eligible cases is unknown until Lethe is deployed. If opt-in rate is low or if scrubbing destroys most candidate signal, the v1.0 tag stays attached longer than planned. The two-epoch design absorbs this; no fallback to foreign-system ingest is permitted.
- **Red-team sourcing for v1.x.** Internal-but-different-team for v1; external consultant for v1.x — the consultant pipeline is unspecified. Open question for WS8 (deployment) to coordinate.
- **Eval-set version drift events.** > 5% retirement triggers an alarm (§4.5); the *response* to the alarm is unspecified (rebuild from scratch? selective top-up?). Will be set on the first occurrence.
- **Shadow-harness wall-clock budget.** What budget for the shadow path is "fast enough not to be dropped"? Unknown until production traffic patterns are observed; set conservatively at 2× production p99 at v1.0 and tune.
- **Cost-of-cost-measurement.** Counting tokens per query has its own overhead; not free. Bet: < 1% overhead via in-process counters; if not, shadow-only cost measurement.

---

## Appendix A — Traceability matrix (gap-14 §5(1)–(5))

Required by the WS4 stopping criteria: every gap-14 §5 constraint is addressed §-by-§.

| gap-14 §5 constraint | Addressed in |
|---|---|
| **§5(1)** Pre-launch eval-set composition (30/25/20/15/10) with two reporting epochs | §2 (epochs); §4.1 (composition with v1.0 deferral); §4.2 (sourcing); §11.2 (public template). **v1.0 status: acknowledged-and-deferred, not satisfied.** v1.0 ships with operator share = 0% (the 30%-target slice is empty); the deviation is mandatory-tagged on every public report (§2.1) and the v1.x migration plan (§4.1) restores the gap-14 §5(1) target. The two-epoch design carries the deferral. |
| **§5(1) closing clause** "If WS4 cannot meet (1) at launch ... mark headline metrics as 'preliminary, author-share above threshold'" | §2.1 (headline-tag wording, mandatory render in `metrics/emitter.py`). v1.0 wording: `preliminary — operator slice empty (0%); author + adversarial + ablation + synthetic only; v1.x target 30% operator-derived` |
| **§5(2)** Mandatory contamination defenses (`contamination_protected` flag, CI-gate, provenance enforcement) | §4.4; §10 (`contamination/guard.py`); §11.1 (`contamination.json`) |
| **§5(3)** Drift signals + re-eval cadence (monthly held set; quarterly fresh adversarial slice) | §8 |
| **§5(4)** Headline metrics in two strata (all-cases vs. operator+adversarial+ablation+replay-only); both reported on every public comparison | §5.9; §11.2 (template enforces both) |
| **§5(5)** Negative-case construction policy (every "should remember" has an adversarial counterpart; classifier eval is symmetric) | §4.3 (policy); §5.6 (per-class symmetric F1) |

---

## Appendix B — Cross-refs

- **gap-01 retention engine** (§6) — per-phase eval signals; this doc §6 is gap-01's downstream consumer. Two-stream Q1 outcome (gap-01 §6 residual) measured by §3.1 (LongMemEval) + §6 (consolidate phase).
- **gap-02 utility-feedback** — utility ≠ eval; relationship clarified in §1. Citation-diff threshold tuning runs against the eval set per gap-02 §6; the eval set must not over-fit to citation-detected behaviors (gap-14 §5 + §4.3 negative-case symmetry).
- **gap-03 scoring weights** — per-phase signals (§6) calibrate the (α, β, γ, δ, ε) weights; WS5 owns the math, this doc owns the calibration substrate.
- **gap-04 multi-agent concurrency** — tenant-isolation breach (§7.1) is a P0 chaos pass criterion; multi-tenant latency stratification is a v1.x metric (§5.2).
- **gap-05 provenance enforcement** — verifies contamination protection (§4.4); episode-id stability is an eval-set invariant (§4.5).
- **gap-06 extraction quality** — §5.7 metrics; per-domain calibration table is the gap-06 §3 contract.
- **gap-08 crash safety** — quarantine-state durability is exercised by §7 chaos eval (S5-coverage%).
- **gap-09 non-factual memory** — LoCoMo-Plus (§3.2) is the v1 proxy; per-class F1 in §5.6 covers `remember:preference`.
- **gap-10 peer messaging** — peer-message corruption (§7.1); peer-asserted facts get halved utility credit (gap-02 §6) but full eval-ground-truth weight in §4 cases.
- **gap-11 forgetting-as-safety** — sensitivity-class taxonomy is the privacy-scrub pipeline backbone (§4.6); `forget` mode-correctness is a chaos pass criterion.
- **gap-12 intent classifier** — §5.6 macro-F1 is the **headline metric**; symmetric pos/neg per gap-14 §5(5) implemented in §4.3.
- **gap-13 contradiction resolution** — invalidation correctness is a §6 phase signal; bi-temporal pass criterion in §7.1 (peer-message corruption).
- **gap-14 eval-set bias** — input-constraint document; Appendix A traces all §5(1)–(5).
- **WS5 (scoring formalism)** — reads §6 (per-phase signals) as input contract; uses §5.5 (promotion precision + demotion recall) for keep/replace/extend on the score function.
- **WS6 (API)** — owns the verbs (`recall`, `remember`, `forget`, `peer_message`, `recall_outcome`, etc.) the harness calls; owns the health-endpoint named states in §7.2.
- **WS7 (migration)** — eval-set ingest is **not** a WS7 concern. WS7 should not plan against SCNS or any foreign system as a Lethe substrate or data source. The v1.x operator slice comes from Lethe's own opt-in audit-log capture (§4.6); the WS6 surface owns the opt-in verb.
- **WS8 (deployment)** — schedules monthly held-set re-eval and drift-detector alarms (§8); chaos eval CI integration is a deploy-cadence dependency.
