# WS5 — Scoring Formalism (v1 heuristic + v2 log-signal contract)

**Status:** Drafted by WS5 author (post-WS4). Awaiting WS5-QA fresh-eyes pass.
**Inputs reflected:** gap-03 (form & defaults), gap-02 (utility taxonomy), gap-09 §3+§7 (per-class shapes), gap-12 §3+§8 (intent dispatch), gap-13 (bi-temporal invalidate), composition §3 (S1/S2/S3 stores), eval-plan §5/§6/§10 (metrics, per-phase signals, harness), HANDOFF §8.2/§10 (binding constraint: Lethe stands on its own).
**Lit-review carries:** Cognitive Weave (decay + residual), Memory-as-Metabolism (gravity), Zep (bi-temporal), MAGMA (intent-routed weights).
**Hard constraint (HANDOFF §10):** No SCNS dependency. Calibration data is LongMemEval / LoCoMo / DMR + Lethe's own opt-in audit-log capture (`scripts/eval/lethe_native/loader.py::capture_opt_in_trace`). SCNS dream-daemon is a *design-pattern reference only*; no SCNS numbers cross into Lethe scoring as ground truth.

---

## §0 Frame

WS5 owns the **math** of scoring. WS4 owns the **calibration substrate** (eval harness, ledger, two-strata reporting). gap-03 owns the **form and the v1 defaults**. This document closes the loop:

- §1–§5 specify the v1 heuristic — explicit formulas for both scoring surfaces (consolidate-time and recall-time), exhaustive over the four persistent memory shapes (gap-09 §3).
- §6 specifies bi-temporal invalidation semantics — when does a fact's score go to floor, and how does invalidation interact with utility feedback.
- §7 is the tuning-knob table — every weight, threshold, and decay constant, with default value, calibration source, and the eval signal (eval-plan §6) that gates keep / replace / extend.
- §8 specifies the v2 learned-scorer log-signal contract — the bridge to WS4's `metrics/emitter.py` and `lethe_native/loader.py::capture_opt_in_trace`. Precise enough that a v2 author can start training tomorrow.
- §9 sketches the v1 → v2 transition. §10 lists residual unknowns. §11 is the traceability matrix.
- Appendix A is a worked numerical example — one episodic fact, one preference, one query — through both scoring surfaces.

**Out of scope.** Calibration values themselves (those are emitted from WS4's harness against LongMemEval / LoCoMo / DMR — gap-03 §5). Index implementation (composition §3.2/§3.3). API surface (WS6). Migration choreography (WS7).

---

## §1 Two scoring surfaces

Lethe scores facts on **two distinct surfaces** with **distinct weight tuples**, per gap-03 §3:

| Surface | When invoked | Inputs | Output | Decision driven |
|---|---|---|---|---|
| **Consolidate-time** | Async dream-daemon phases (eval-plan §6: extract / score / promote / demote / consolidate / invalidate) | Fact features over a window (recency, connectedness, utility tally, type-priority, contradiction count) | Scalar `score(f) ∈ ℝ` | Retention vs. demotion vs. promotion to S3 |
| **Recall-time** | Synchronous, per query | Per-query candidate set (sem rank, lex rank, graph rank, intent match, utility prior) | Per-candidate scalar `rerank(f, q)` | Top-k for context assembly |

The two surfaces share *some* substrate (utility tally is read by both; type-priority is read by both), but the **weights are independent** and **the formula shapes differ** (additive at consolidate-time vs. RRF + post-rerank at recall-time). Tuning them separately is required: gap-03 §7 names this as a primary v1.0 → v1.1 risk if the two surfaces are conflated.

---

## §2 Symbols, units, value ranges

| Symbol | Domain | Unit | Source store | Origin |
|---|---|---|---|---|
| `f` | Fact | — | S2 (canonical) | Composition §3.1 |
| `q` | Query | — | request-scoped | Recall API (WS6) |
| `t_now` | Wall clock | seconds (UTC) | runtime | — |
| `t_create(f)`, `t_access(f)` | Wall clock | seconds | S2 | gap-03 §7 |
| `valid_from(f)`, `valid_to(f)` | Wall clock or ∞ | seconds | S2 | gap-13 §2 |
| `τ_r` | Recency half-life | days | config | gap-03 §4(a) |
| `τ_u` | Utility half-life | days | config | gap-02 §3 |
| `recency(f)` | Recency decay | [0,1] | computed | §3.1 |
| `connectedness(f)` | Structural prominence | [0,1] | S3 (graph) | §3.2, HippoRAG-style PPR |
| `utility(f)` | Weighted utility tally | ℝ (≥0 typical) | S2 audit ledger | §3.3, gap-02 |
| `type_priority(f)` | Class boost | [0,1] | S2 frontmatter | §3.4 |
| `contradiction_count(f)` | Active contradictions | ℕ | S2 + gap-13 detector | §3.5 |
| `gravity(f)` | Removal-cascade cost | [0,1] | S3 | §3.6, MaM |
| `sem(f, q)`, `lex(f, q)`, `graph(f, q)` | Per-ranker rank position | ℕ⁺ (1 = best) | retrievers | §4.1 |
| `intent_match(f, q)` | Class agreement | [0,1] | classifier | §4.2, gap-12 |
| `α, β, γ, δ, ε` | Consolidate weights | ℝ | config | gap-03 §3 |
| `w_sem, w_lex, w_graph, w_intent, w_utility` | Recall weights | ℝ | config | gap-03 §3 |
| `k` | RRF constant | ℕ⁺ | config (=60) | Cormack et al. |
| `T_purge` | Post-invalidate grace | days | config (=90) | §6.3 |

All scalars are dimensionless after normalization. Per-term outputs are normalized to **`[0,1]`** before weighting (§3.1–§3.6 each specify the normalizer). Composed scores are unbounded but in practice fall in `[-1, 2]` for v1 defaults; thresholds in §7 are stated against this empirical range.

---

## §3 v1 consolidate-time heuristic

**Composed formula:**

```
score(f) = gravity_mult(f) · [ α · type_priority(f)
                             + β · recency(f)
                             + γ · connectedness(f)
                             + δ · utility(f)
                             − ε_eff · contradiction(f) ]
```

with `gravity_mult(f)` a **demotion-floor multiplier** (Q1 resolution) — see §3.6. Defaults from gap-03 §5: `α=0.2, β=0.3, γ=0.2, δ=0.4, ε=0.5`.

### §3.1 Recency decay

Cognitive Weave (lit-review §05) formulates retention as a **decaying baseline plus residual**: `r(t) = r_∞ + (1 − r_∞) · exp(−Δt / τ_r)`. We adopt the Lethe form:

```
recency(f) = r_∞ + (1 − r_∞) · exp( − max(0, t_now − t_access(f)) / τ_r )
```

- `Δt` is **last-access**, not creation (gap-03 §7 bet — preferences and prohibitions stay live as long as they're cited; cold storage decays faster).
- `r_∞ = 0.05` is the residual baseline (Cognitive Weave default; prevents true zero so a single recall can revive a stale fact).
- `τ_r = 30 d` for episodic facts. Per-class overrides in §5.
- Output range: `[0.05, 1.0]`. Normalizer: native.

### §3.2 Structural connectedness

HippoRAG-style **personalized PageRank** over S3's graph slice, with damping `d = 0.85` (standard PageRank value). Seed mass on `f`; report stationary probability of `f` itself relative to its 2-hop neighborhood.

```
connectedness(f) = percentile_rank( PPR(f; d=0.85, seeds={f}) , N_2hop(f) )
```

- `N_2hop(f)` is `f`'s 2-hop subgraph (cap at 500 nodes for cost).
- **Fallback** (subgraph too small, < 10 nodes): `degree_percentile(f) = degree(f) / max_degree(N_1hop(f))` (gap-03 §4(a)).
- Output range: `[0, 1]`. Normalizer: percentile rank.

### §3.3 Utility signal

gap-02 §3 weighted aggregate over the recall-ledger window `[t_now − τ_u, t_now]`, exponentially decayed:

```
utility(f) = Σ_e   w_event(e.kind) · exp( −(t_now − e.t) / τ_u )
                          for e in ledger(f) ∩ [t_now − τ_u, t_now]
```

with per-event weights from gap-02 §3:

| Event kind | `w_event` |
|---|---|
| citation | 0.4 |
| tool_success | 0.7 |
| correction | 1.0 |
| repeat_recall | 0.1 |
| no_op | −0.2 |

- `τ_u = 30 d` default.
- Output range: empirical `[0, ~5]` for active facts; **clipped + min-max normalized to `[0, 1]`** at the per-tenant 95th percentile of the ledger window.
- **Frozen on invalidate** — see §6.4.

### §3.4 Type priority

Lookup table indexed by `kind` frontmatter (S4a / composition §3.1):

| `kind` | `type_priority` |
|---|---|
| `prohibition` | 1.00 |
| `preference` | 0.85 |
| `user_fact` | 0.70 |
| `feedback` | 0.55 |
| `project_fact` | 0.40 |
| `reference` | 0.25 |
| (default — unclassified episodic) | 0.30 |

Output range: `[0.25, 1.0]`. Source: dream-daemon vocabulary alignment (gap-09 §3, gap-12 §3 mapping).

### §3.5 Contradiction penalty

Multiplicative-magnitude penalty, **log-dampened against oscillation** per gap-13 §3.1 (v1 mitigation):

```
contradiction(f) = 1   if contradiction_count(f) > 0  else  0
ε_eff             = ε · (1 + log(1 + contradiction_count(f)))
```

So the additive contribution is `−ε_eff` when contradicted, `0` otherwise. Log-dampening prevents a single highly-contradicted fact from dominating the term while still raising the cost of repeat contradictions. `contradiction_count(f)` resets on revalidate (gap-13 §7).

### §3.6 Gravity multiplier (Q1: demotion-floor, not 6th additive term)

Memory-as-Metabolism (lit-review §04) frames structural facts as **gravitationally protected** — their removal cascades. We honor MaM by treating gravity as a **demotion-floor guard**, not a sixth additive term (Q1 resolution):

```
gravity(f)      = clip( cascade_cost(f) / cascade_cost_99pct , 0, 1 )
gravity_mult(f) = 1.0                                  if score_pre_grav(f) ≥ θ_demote
                = max( 1.0, 1 + g_floor · gravity(f) ) if score_pre_grav(f) <  θ_demote
```

where:
- `cascade_cost(f)` = number of edges in S3 broken if `f` is removed, weighted by edge-class.
- `θ_demote` is the demotion threshold (§7).
- `g_floor = 0.5` default — a fully-gravity-bound fact gets a 50% lift above the demote floor, sufficient to cross `θ_demote` from any plausible pre-grav score in `[0, 1]`.

This keeps the additive tuple `(α, β, γ, δ, ε)` closed (gap-03 stable) while expressing MaM intent. **Invalidated facts have `gravity_mult = 0`** (§6.2) — they cannot resist demotion.

---

## §4 v1 recall-time heuristic

Per Q2 resolution, the recall-time form is **RRF combine + weighted post-rerank** (gap-03 §5 recommendation), not the gap-03 §3 weighted-sum derivation.

### §4.1 Bi-temporal validity filter (pre-RRF)

Applied **before** any ranker is consulted:

```
valid(f, t_now) ≡ (valid_to(f) IS NULL OR valid_to(f) > t_now)
                  AND valid_from(f) ≤ t_now
```

Invalid facts are excluded from the candidate set entirely → effective recall score `−∞` (§6.1). This is cheaper than scoring-then-filtering and keeps invalid facts off the hot path.

### §4.2 RRF combine over sem/lex/graph

For each ranker `r ∈ {sem, lex, graph}` produce ranked list of valid candidates; combine via Reciprocal Rank Fusion (Cormack et al.):

```
rrf(f, q) = Σ_{r ∈ {sem,lex,graph}}  1 / (k + rank_r(f, q))
```

with `k = 60` (qmd / Cormack default; gap-03 §5).

### §4.3 Intent-routed multiplicative bonus (MAGMA-style)

Per gap-12 §3, the intent classifier emits a class label and confidence over 7 classes (4 persistent + 3 non-persistent). For persistent classes, define `intent_match(f, q)` as the agreement between the stored fact's `kind` and the query's intent (e.g., a `preference` fact matches an `update_preference` intent at 1.0; matches an `episodic_recall` intent at 0.5; matches a `procedure_lookup` intent at 0.0):

| Intent class \ fact `kind` | `prohibition` | `preference` | `user_fact` | `procedure` | `narrative` |
|---|---|---|---|---|---|
| `update_preference` | 0.5 | 1.0 | 0.3 | 0.0 | 0.0 |
| `state_fact` | 0.3 | 0.3 | 1.0 | 0.0 | 0.0 |
| `procedure_lookup` | 0.5 | 0.0 | 0.0 | 1.0 | 0.0 |
| `narrative_recall` | 0.0 | 0.0 | 0.3 | 0.0 | 1.0 |

For non-persistent intent classes (`reply_only`, `peer_route`, `drop`, `escalate`) the bonus is `0` — out of scope for scoring (Q3 resolution).

### §4.4 Utility prior (additive, ramped)

Additive on the post-RRF score, **ramped on operator-trace volume** (gap-03 §4(a)):

```
w_utility(t) = 0   if N_ledger(t) <  1 000
             = 0.2 · min(1, (N_ledger(t) − 1 000) / 9 000)   otherwise
```

So `w_utility` ramps `0 → 0.2` linearly between 1k and 10k ledger entries. Until 1k entries, the prior is silent (avoids overfit on sparse signal).

### §4.5 Composed recall-time formula

```
rerank(f, q) = rrf(f, q)
             · (1 + w_intent · intent_match(f, q) · classifier_conf(q))
             + w_utility(t_now) · utility(f)
```

with v1 defaults `w_intent = 0.15`, `w_utility = 0.0 → 0.2` (ramp). Numerical example in Appendix A.

---

## §5 Per-class dispatch and per-class formulas

Dispatch is by `kind` frontmatter (S4a) at consolidate-time and by `intent` (gap-12) at recall-time. **Exhaustive over the 4 persistent memory shapes** (gap-09 §3) — non-persistent classes (`reply_only`, `peer_route`, `drop`, `escalate`) are **out of scope for scoring** (Q3): they never produce a stored fact and never reach a scoring surface.

### §5.1 Episodic fact (`kind ∈ {user_fact, project_fact, feedback, reference}`)

Defaults of §3 + §4 unchanged. `τ_r = 30 d`, full additive tuple `(α, β, γ, δ, ε) = (0.2, 0.3, 0.2, 0.4, 0.5)`.

### §5.2 Preference (`kind ∈ {preference, prohibition}`)

- **`β = 0`** — preferences do not decay with time. A preference stated once is live until invalidated.
- **`ε` capped at 0.3** — gap-13 mandates revision-wins for preferences (the new statement supersedes the old; both stay in the audit log but only the new is `valid_to = NULL`). Penalizing the surviving preference for the existence of a now-invalidated predecessor is double-counting.
- **Always-loaded into context up to a per-tenant cap of 10 KB** (gap-09 §6). Recall-time scoring is used only to **order preferences inside the cap**, not to gate inclusion.
- Recall-time: `intent_match` table §4.3 row 1 applies; otherwise §4 unchanged.

### §5.3 Procedure (`kind = procedure`)

- **`τ_r = 180 d`** — procedures decay slowly (a how-to remains valid for months even unused).
- **Supersession via `valid_to`**, not via `ε`: a procedure replaced by a newer version of itself sets `valid_to = t_supersession` on the old, `valid_from = t_supersession` on the new. The old's `contradiction_count` is **not** incremented (it's a supersession, not a contradiction).
- **Connectedness scored against the procedure-graph**, not the fact-graph: edges are `next_step` / `precondition_of` / `subprocedure_of` (composition §3.3 graph slice `procedure_seq`). Same PPR formula §3.2, different subgraph.
- Recall-time: `procedure_lookup` intent → `intent_match = 1.0` row §4.3.

### §5.4 Narrative (`kind = narrative`)

- **`β = 0`** — narratives are append-mostly; their score should not decay just because nobody asked.
- **Recall-time path is `recall_synthesis(uri | query)`** (composition §3.2): narratives are summarized at recall, not retrieved as raw rows. Scoring is **page-level** (the whole narrative document), not fact-level.
- **Type-priority high** (`narrative` is added to the §3.4 table at `0.50` between `feedback` and `project_fact`).
- Recall-time: `narrative_recall` intent → `intent_match = 1.0`. The score governs **which narrative to summarize**, not which fact-rows to surface.

### §5.5 Dispatch table

| `kind` | `τ_r` (d) | `β` | `ε` cap | Connectedness graph | Recall path |
|---|---|---|---|---|---|
| `user_fact`, `project_fact`, `feedback`, `reference` | 30 | 0.30 | 0.50 | fact-graph | RRF + rerank |
| `preference`, `prohibition` | — (β=0) | 0.00 | 0.30 | fact-graph | always-load + rerank-inside-cap |
| `procedure` | 180 | 0.30 | 0.50 (supersession non-contradiction) | procedure-seq | RRF + rerank |
| `narrative` | — (β=0) | 0.00 | 0.50 | narrative-doc edges | `recall_synthesis` page-level |

---

## §6 Bi-temporal invalidation semantics

Lethe commits to bi-temporal invalidate (gap-13 candidate (a)). Score interactions:

### §6.1 Default recall filter — invalid → recall floor

```
valid(f, t_now)  ≡  (valid_to(f) IS NULL OR valid_to(f) > t_now)  AND  valid_from(f) ≤ t_now
recall_score(f, q) = −∞  if not valid(f, t_now)
```

Invalid facts are excluded from RRF candidate sets entirely (§4.1). Effective floor: `−∞`.

### §6.2 Consolidate-time treatment — gravity zeroed

Invalid facts are **still scored** (the score is needed for audit replay and for the v2 learned-scorer training set), but `gravity_mult = 0` is forced. They cannot resist demotion. The pre-grav additive score remains computable from the historical features; it is not overwritten on invalidate (replayability invariant §8.3).

### §6.3 Score-floor below default — purge after grace

`forget(purge)` is **not** synonymous with invalidate. After invalidate, a fact persists in S2 with `valid_to ≠ NULL` for `T_purge = 90 d` (default), during which:
- It is unreachable to recall (§6.1).
- It remains visible to audit / replay (gap-05).
- A `revalidate` event (gap-13 §7) can thaw it (clears `valid_to`, restores `gravity_mult`, thaws utility tally per §6.4).

After `T_purge`, a `purge` event scrubs the row per the privacy-first audit pattern (gap-05). Purge is irreversible.

### §6.4 Utility-tally freeze on invalidate

Utility events arriving after `valid_to` for a now-invalidated fact **do not increment the live tally**. They are still *recorded* in the audit ledger (gap-02 §6 invariant), but they are not aggregated into `utility(f)` until/unless a `revalidate` thaws the freeze. This prevents the situation where a popular-but-wrong fact accrues utility weight while invalidated and then springs back to a high score on revalidate.

A `revalidate` event:
1. Clears `valid_to`.
2. Resets `contradiction_count = 0`.
3. **Replays** post-invalidate utility events into the live tally.

### §6.5 ε amplification — log-dampened (cf. §3.5)

`ε_eff = ε · (1 + log(1 + contradiction_count(f)))` per gap-13 §3.1 v1 mitigation. Repeat contradictions raise the penalty without runaway growth. `contradiction_count` resets on revalidate.

---

## §7 Tuning-knob table

Every weight, threshold, and decay constant. Columns:

- **Symbol** — name in the formulas.
- **Default** — gap-03 §5 candidate (a).
- **Range** — empirical search bound (gap-03 §6 BO sweep).
- **Calibration source** — public benchmark (LongMemEval / LoCoMo / DMR) and/or Lethe opt-in audit-log capture. **No SCNS dependency.**
- **Eval signal (eval-plan §)** — the per-phase signal (eval-plan §6) and headline metric (eval-plan §5) that gate keep/replace/extend.
- **Trigger** — what shifts the knob from keep to replace (drop) vs. extend (re-tune).

| Symbol | Default | Range | Calibration source | Eval signal | Trigger |
|---|---|---|---|---|---|
| **Consolidate-time additive weights** |
| `α` (type_priority weight) | 0.20 | [0.05, 0.40] | LongMemEval extract phase + opt-in trace | §6 *score* phase + §5.5 promotion-precision | Promotion-precision drop > 5pp |
| `β` (recency weight) | 0.30 | [0.10, 0.50] | LongMemEval + LoCoMo recency strata | §6 *score* + §5.6 demotion-recall | Demotion-recall < 0.7 |
| `γ` (connectedness weight) | 0.20 | [0.05, 0.40] | LoCoMo multi-hop + opt-in trace | §6 *score* + §5.4 multi-hop EM | Multi-hop EM ↓ ≥ 3pp |
| `δ` (utility weight) | 0.40 | [0.10, 0.60] | Lethe opt-in trace only (post-deploy) | §6 *score* + §5.5 promotion-precision | Promotion-precision delta on operator strata |
| `ε` (contradiction weight) | 0.50 | [0.20, 1.00] | LongMemEval + adversarial set (eval-plan §5.7) | §6 *invalidate* + §5.7 contradiction-recall | Contradiction-recall < 0.85 |
| **Consolidate-time constants** |
| `τ_r` (recency half-life, episodic) | 30 d | [7 d, 90 d] | LongMemEval + opt-in trace | §6 *score* + §5.6 demotion-recall | Stale-citation rate > 10% |
| `τ_r` (procedure override) | 180 d | [60 d, 365 d] | DMR procedure subset + opt-in trace | §6 *score* per-class | Procedure stale-recall > 10% |
| `τ_u` (utility half-life) | 30 d | [7 d, 90 d] | Lethe opt-in trace | §6 *score* + §5.5 | Promotion-precision drift |
| `r_∞` (recency residual baseline) | 0.05 | [0.01, 0.20] | Cognitive Weave default + ablation | §6 *score* ablation | Cold-fact revival rate < 0.5% |
| `g_floor` (gravity demotion-floor) | 0.50 | [0.20, 1.00] | Synthetic cascade-cost benchmark | §6 *demote* + §5.6 | Cascade-break events post-demote |
| `θ_demote` | 0.20 | [0.10, 0.40] | LongMemEval + opt-in trace | §6 *demote* + §5.6 | Demotion-recall < 0.7 |
| `θ_promote` | 0.70 | [0.50, 0.90] | LongMemEval + opt-in trace | §6 *promote* + §5.5 | Promotion-precision < 0.85 |
| `PPR damping d` | 0.85 | [0.70, 0.95] | HippoRAG default + ablation | §6 *score* + §5.4 multi-hop | Multi-hop EM regression |
| `2-hop subgraph cap N` | 500 | [100, 2000] | Cost benchmark | §6 *score* latency budget | p95 score-phase latency > 5s/window |
| **Recall-time weights** |
| `RRF k` | 60 | [10, 100] | Cormack default + ablation on LoCoMo | §6 *recall* + §5.1 nDCG@10 | nDCG@10 drop ≥ 2pp |
| `w_sem` (informational; folded into RRF) | — | — | — | — | — |
| `w_lex` (informational; folded into RRF) | — | — | — | — | — |
| `w_graph` (informational; folded into RRF) | — | — | — | — | — |
| `w_intent` (intent multiplicative bonus) | 0.15 | [0.05, 0.30] | LongMemEval intent-routed strata | §6 *recall* + §5.2 intent-conditioned nDCG | Intent-strata regression > 2pp |
| `w_utility` (recall prior, ramped) | 0 → 0.2 | ramp [1k, 10k] entries | Lethe opt-in trace ledger | §6 *recall* + §5.5 | Stale-utility recall > 5% |
| **Utility per-event weights** (gap-02 §3) |
| `w_event[citation]` | 0.40 | [0.20, 0.60] | gap-02 derivation + ablation | §6 *score* utility-aggregate | δ-term sensitivity |
| `w_event[tool_success]` | 0.70 | [0.40, 1.00] | gap-02 + ablation | §6 *score* | δ-term sensitivity |
| `w_event[correction]` | 1.00 | [0.50, 1.50] | gap-02 (ground-truth signal) | §6 *score* | Promotion-precision response |
| `w_event[repeat_recall]` | 0.10 | [0.05, 0.30] | gap-02 + ablation | §6 *score* | Saturation guard |
| `w_event[no_op]` | −0.20 | [−0.50, −0.05] | gap-02 (negative signal) | §6 *score* | Demotion-recall response |
| **Per-class overrides** |
| Preference always-load cap | 10 KB | [4 KB, 32 KB] | gap-09 §6 + opt-in trace | §6 *recall* + §5.5 preference-strata | Preference-strata recall regression |
| Preference `β` cap | 0 | fixed | gap-09 §3 + gap-13 revision-wins | structural | n/a |
| Preference `ε` cap | 0.30 | [0.10, 0.50] | gap-13 + ablation | §6 *invalidate* preference-strata | Preference revision-precision |
| Procedure `τ_r` | 180 d | (see above) | (see above) | (see above) | (see above) |
| Narrative recall path | `recall_synthesis` | flag | composition §3.2 | §6 *recall* + §5.8 narrative-strata | Narrative-strata nDCG@10 |
| **Lifecycle / invalidate** |
| `T_purge` | 90 d | [30 d, 365 d] | Privacy review + audit retention SLO | §6 *invalidate* + §5.7 | Audit-replay completeness |
| Contradiction-density alarm | 0.05 (5% of window) | [0.02, 0.20] | gap-13 §4 detector | §6 *invalidate* + §5.7 | Detector false-alarm rate |
| Citation-similarity cutoff | 0.82 (cosine) | [0.70, 0.95] | gap-02 + ablation | §6 *score* | δ-term noise |

**No SCNS calibration source appears in any row.** Verifiable: `grep -i scns docs/05-scoring-design.md` returns the binding constraint statement only.

---

## §8 v2 learned-scorer log-signal contract

The bridge to a learned scorer. **Precise enough that a v2 author can begin training tomorrow.**

### §8.1 Event taxonomy

Seven event types, each with one JSON schema:

| Event | Emitted on | Cardinality | Purpose |
|---|---|---|---|
| `remember` | New fact written to S2 | per write | Captures features-at-creation |
| `recall` | Per-query candidate reranked | per query × per top-k candidate | Scoring inputs at recall-time |
| `recall_outcome` | Citation / tool-call / correction / no-op observed downstream | per outcome | Joins to a prior `recall` via `recall_id` |
| `promote` | Fact promoted to S3 (or higher tier) | per promote | Decision + score-at-decision |
| `demote` | Fact demoted from S3 (or to purge-pending) | per demote | Decision + score-at-decision |
| `invalidate` | Fact's `valid_to` set | per invalidate | Reason + supersession pointer |
| `consolidate_phase` | Per dream-daemon phase boundary | per phase per window | Aggregate stats for replay context |

### §8.2 Common event envelope

```json
{
  "event_id":               "uuidv7",
  "event_type":             "remember | recall | recall_outcome | promote | demote | invalidate | consolidate_phase",
  "tenant_id":              "string (privacy boundary)",
  "ts_recorded":            "RFC3339 (system time)",
  "ts_valid":               "RFC3339 (bi-temporal valid time; for recall = query-time, for remember = ingest-time)",
  "model_version":          "semver of the scorer package (v1.x.y)",
  "weights_version":        "hash of the active config (sha256 of the §7 knob table snapshot)",
  "contamination_protected": true,
  "fact_ids":               ["S2 fact uuids"],
  "score_inputs":           { "type": float, "recency": float, "connectedness": float,
                              "utility": float, "contradiction": float, "gravity": float },
  "score_output":           float,
  "decision":               "string (event-type-specific enum)",
  "outcome":                "string | null (only on recall_outcome)",
  "provenance":             { "source_uri": "...", "edit_history_id": "..." }
}
```

`contamination_protected` (gap-05 + eval-plan §4.4 invariant) is **mandatory** on every event. Events failing this flag are dropped at the emitter (defense-in-depth).

### §8.3 Replayability invariant

```
( log + S1/S2/S3 snapshot at t )  →  score(t)   is deterministic.
```

I.e., given the audit log up to time `t` and a frozen snapshot of the stores at `t`, replaying the log reproduces every score the system computed. This is the property that lets a v2 author derive `(features, outcome)` training pairs offline without re-running the production system.

The join key for training is `recall.recall_id ↔ recall_outcome.recall_id`. Outcomes can be sparse (no_op is silent); the v2 author treats absence-of-outcome over a window as a `no_op` outcome with `w_event = −0.2`.

### §8.4 Sink contract

Per Q4 resolution, **extend `scripts/eval/metrics/emitter.py` with `emit_score_event(event)`**. Forward-spec (not implemented in WS5):

```python
def emit_score_event(event: dict) -> None:
    """
    Append a v2-learned-scorer training signal to the per-tenant audit log.

    Events are validated against the §8.2 envelope schema, gated on
    `contamination_protected`, and written append-only to:
        <run_dir>/score_events/<tenant_id>/<yyyy>/<mm>/<dd>.jsonl

    Pairs with lethe_native/loader.py::capture_opt_in_trace for v1.x
    operator-trace ingest into the eval candidate pool (eval-plan §4.6).
    """
```

The emitter is a **batch sink today** (`write_run_report`, `enforce_two_strata`); `emit_score_event` is the per-event escape hatch. Co-locating keeps the eval-pipeline metric surface unified and matches the post-WS4 HANDOFF §10 reading that names `metrics/emitter.py` as the v2 signal sink.

### §8.5 Privacy / contamination invariants

- Every event carries `contamination_protected = true`. Public-benchmark replays (LongMemEval / LoCoMo / DMR) emit with `contamination_protected = false` *and* are written to a separate `bench/` shard. The v2 trainer must respect the boundary (gap-05 + eval-plan §4.4).
- `tenant_id` is the privacy boundary. Cross-tenant joins are forbidden at training time; per-tenant fine-tuning is the v2 default mode (gap-03 §5 v2 plan).
- `provenance` is mandatory on `remember` and `recall_outcome` (gap-05). Missing provenance → emit drop + alarm.

### §8.6 v2 entry criteria

Training a learned scorer **unblocks** when both:

1. **Strict-stratum operator share ≥ 20%** of the eval candidate pool (eval-plan §5.9 two-strata reporting). Below this, the learned scorer would over-fit the public-benchmark replay shape.
2. **≥ 10 000 labeled `(recall, outcome)` pairs** in the per-tenant ledger (gap-03 §6 BO threshold; pairs are joins per §8.3).

Until both gates pass, the v1 heuristic remains **canonical**. v1.1 (BO sweep over §7 ranges; gap-03 candidate b) is the intermediate stop.

---

## §9 v1 → v2 transition

What gets **learned** in v2:
- The 5 consolidate-time weights `(α, β, γ, δ, ε)`.
- The 2 recall-time tunables not folded into RRF (`w_intent`, `w_utility`-ramp).
- The 4 per-class deltas (per-shape weight overrides from §5.5).

What stays **heuristic** even in v2:
- Per-class dispatch (§5) — the `kind` → formula choice is a structural decision, not a weight.
- Bi-temporal invalidation semantics (§6) — these are correctness properties, not optimization targets.
- Gravity demotion-floor behavior (§3.6) — structural, not a weight.
- The RRF combine shape (§4.2) — gap-03 §5 commits to RRF; the learned scorer optimizes the *post*-RRF rerank.

**Transition sequence:**

1. **v1.0** — theory-driven defaults from gap-03 §5 (this doc).
2. **v1.1** — BO sweep over §7 ranges using public-benchmark replays; gap-03 candidate (b). Triggered when WS4 harness goes green on §6 per-phase signals.
3. **v1.x** — per-tenant retune from opt-in trace; gap-03 §5 second milestone.
4. **v2** — learned scorer, gated on §8.6 entry criteria.

---

## §10 Residual unknowns

Items WS5 commits to *naming* but not closing in v1:

1. **Promotion-threshold drift** — `θ_promote = 0.70` is theory-driven. First operator-trace ledger will reveal whether it should be class-conditional.
2. **Gravity computation cost at scale** — `cascade_cost` is `O(|N_2hop|)` per fact per consolidate. May need batched / cached reformulation if S3 grows beyond ~10⁶ edges per tenant.
3. **Preference always-load bandwidth** — the 10 KB cap interacts with S2 read latency at recall-time. May need a streamed top-k preferences path.
4. **Utility-half-life vs recency-half-life decoupling** — both default `30 d`. They are conceptually independent; v1.1 BO sweep should treat them independently.
5. **Intent-bonus saturation** — `(1 + 0.15 · intent_match · classifier_conf)` saturates at `1.15`. If classifier confidence becomes systematically high (e.g., post-fine-tune), the bonus may be too small to discriminate. Re-tune w_intent at v1.1.

---

## §11 Traceability matrix

| Required input | Reflected in §s |
|---|---|
| `gap-03-scoring-weights.md` (form & defaults) | §1, §2, §3 (full), §4 (full), §7 (every row) |
| `gap-02-utility-feedback.md` (signal taxonomy) | §3.3, §6.4, §7 (utility per-event weights), §8.1 (`recall_outcome`) |
| `gap-09-non-factual-memory.md` §3+§7 (per-class shapes) | §5 (full), §7 (per-class overrides) |
| `gap-12-intent-classifier.md` §3+§8 (classifier dispatch) | §4.3 (intent-match table), §5 (dispatch by `intent`), §5.5 |
| `03-composition-design.md` §3 (S1/S2/S3 layout) | §2 (source-store column), §3.2 (graph slice), §5.4 (`recall_synthesis`) |
| `04-eval-plan.md` §5+§6+§10 (metrics, per-phase signals, harness) | §7 (every row's eval-signal column), §8.4 (sink), §8.6 (entry criteria) |
| `HANDOFF.md` §10 (binding constraint) | §0 (frame), §7 (no-SCNS-source verifiable), §8.5 (privacy invariants) |

| Lit-review brief | Reflected in |
|---|---|
| `02-lit-review/05-cognitive-weave.md` | §3.1 (decay + residual baseline) |
| `02-lit-review/04-memory-as-metabolism.md` | §3.6 (gravity as demotion-floor) |
| `02-lit-review/01-zep.md` | §6 (bi-temporal invalidate semantics) |
| `02-lit-review/02-magma.md` | §4.3 (intent-routed multiplicative bonus) |

---

## Appendix A — Worked example

**Setup.** Tenant `t_alice`, `t_now = 2025-12-01T12:00Z`. Three artifacts:

- `f_pref` — `kind = preference`: "Alice prefers Pacific timezone for meetings." Created `2025-09-15`, last accessed `2025-11-20`, cited 8× (citation), 1× tool_success, 0 contradictions.
- `f_fact` — `kind = user_fact`: "Alice's project is named Lethe." Created `2025-10-01`, last accessed `2025-11-05`, cited 3× (citation), 0 contradictions.
- `f_proc` — `kind = procedure`: "Run `pytest -k smoke` before pushing." Created `2025-08-01`, last accessed `2025-10-01`, cited 1×, 1 contradiction (count=1, log-amplifier active).

**Query.** `q = "What's Alice's preferred meeting time?"` → classifier emits `intent = update_preference`, `classifier_conf = 0.92`.

### A.1 Consolidate-time scores at `t_now`

**`f_pref`** (preference; β=0, ε cap 0.30):
- `type_priority = 0.85`
- `recency = 0` (β=0 — preferences don't decay)
- `connectedness = 0.40` (PPR percentile in fact-graph)
- `utility = 0.4·8·exp(−11/30) + 0.7·1·exp(−11/30) ≈ (3.2 + 0.7)·0.694 ≈ 2.71`. After 95th-pct min-max normalize (assume 95th-pct ledger value = 4): `≈ 0.68`.
- `contradiction = 0`, so `−ε_eff·contradiction = 0`.
- `score_pre_grav = 0.20·0.85 + 0 + 0.20·0.40 + 0.40·0.68 − 0 = 0.17 + 0.08 + 0.272 = 0.522`.
- `gravity = 0.6` (highly cited preference); `score_pre_grav (0.522) ≥ θ_demote (0.20)` → `gravity_mult = 1.0`.
- **`score(f_pref) = 0.522`**. Above `θ_promote = 0.70`? No. Above `θ_demote = 0.20`? Yes. → **retain**.

**`f_fact`** (episodic):
- `type_priority = 0.70`
- `recency = 0.05 + 0.95·exp(−26/30) ≈ 0.05 + 0.95·0.420 ≈ 0.45`.
- `connectedness = 0.35`.
- `utility = 0.4·3·exp(−26/30) ≈ 1.2·0.420 ≈ 0.50`. Normalize: `≈ 0.13`.
- `contradiction = 0`.
- `score_pre_grav = 0.20·0.70 + 0.30·0.45 + 0.20·0.35 + 0.40·0.13 = 0.14 + 0.135 + 0.07 + 0.052 = 0.397`.
- `gravity = 0.2`; pre-grav above `θ_demote` → `gravity_mult = 1.0`.
- **`score(f_fact) = 0.397`**. → **retain**.

**`f_proc`** (procedure; `τ_r = 180`):
- `type_priority = 0.55` (procedures aren't in §3.4; treat as `feedback` tier in v1; **residual unknown #1**).
- `recency = 0.05 + 0.95·exp(−61/180) ≈ 0.05 + 0.95·0.713 ≈ 0.73`.
- `connectedness = 0.30` (procedure-seq graph).
- `utility = 0.4·1·exp(−61/30) ≈ 0.4·0.130 ≈ 0.052`. Normalize: `≈ 0.013`.
- `contradiction = 1`, `ε_eff = 0.50·(1+log 2) = 0.50·1.693 = 0.847`.
- `score_pre_grav = 0.20·0.55 + 0.30·0.73 + 0.20·0.30 + 0.40·0.013 − 0.847·1 = 0.11 + 0.219 + 0.06 + 0.005 − 0.847 = −0.453`.
- `gravity = 0.5`; `score_pre_grav < θ_demote` → `gravity_mult = max(1.0, 1+0.5·0.5) = 1.25`. `score = 1.25 · −0.453 = −0.566`.
- **`score(f_proc) = −0.566`**. Well below `θ_demote`. → **demote** (despite gravity floor — the floor only lifts the multiplier on a non-negative pre-grav score; with strong contradiction the additive went negative). gap-13 contradiction-resolution then dominates.

### A.2 Recall-time score for `q`

Validity filter: all three valid (none have `valid_to` set).

RRF over sem/lex/graph (illustrative ranks):

| Fact | rank_sem | rank_lex | rank_graph | rrf |
|---|---|---|---|---|
| `f_pref` | 1 | 1 | 2 | 1/61 + 1/61 + 1/62 ≈ 0.0489 |
| `f_fact` | 3 | 4 | 1 | 1/63 + 1/64 + 1/61 ≈ 0.0479 |
| `f_proc` | 5 | 8 | 5 | 1/65 + 1/68 + 1/65 ≈ 0.0454 |

Intent-match (`update_preference` row, §4.3): preference 1.0, user_fact 0.3, procedure 0.0. `classifier_conf = 0.92`.

Multiplicative bonus `1 + 0.15 · intent_match · 0.92`:
- `f_pref`: `1 + 0.15·1.0·0.92 = 1.138`
- `f_fact`: `1 + 0.15·0.3·0.92 = 1.041`
- `f_proc`: `1 + 0 = 1.000`

Utility prior (assume `N_ledger = 0` for v1.0 strict stratum) → `w_utility = 0`.

```
rerank(f_pref, q) = 0.0489 · 1.138 + 0 = 0.0556
rerank(f_fact, q) = 0.0479 · 1.041 + 0 = 0.0498
rerank(f_proc, q) = 0.0454 · 1.000 + 0 = 0.0454
```

Top-1 is `f_pref`. The intent multiplicative bonus correctly lifts the preference above the user_fact despite the user_fact having a graph-rank-1 hit. This is the MAGMA intent-routed-weight effect, expressed at the rerank surface.

### A.3 Emitted events

Per §8 contract, this query emits:
- 1× `recall` event with `recall_id = uuid_v7()`, `fact_ids = [f_pref, f_fact, f_proc]`, `score_inputs` and `score_output` per candidate (3 nested entries).
- 0–1× `recall_outcome` event later — when (or if) a downstream citation, tool-call, or correction is observed.
- 0× `consolidate_phase` (this is a recall, not a consolidate phase).

The v2 trainer joins the `recall` row to whichever `recall_outcome` arrives within the per-tenant outcome-window (default 1 h); absent an outcome, treats as `no_op` with `w_event = −0.2`.

---

**End of WS5 scoring formalism.** Next: WS5-QA fresh-eyes pass against this doc + the seven required inputs.

