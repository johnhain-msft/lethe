# gap-03 — Hybrid scoring weights + tuning methodology

**PLAN.md §WS3 Track B item #2** (scoring weight calibration). Synthesis §3.3.
**Tier:** first-class.
**Status:** active. Synthesis §2.3: every reviewed paper either omits weights or stops at "weighting matters more than the individual signals" (Zep). Lethe ships defaults.
**Substrate:** brief 01 (Zep §"weighting matters" without numbers); brief 05 (Cognitive Weave decay + residual baseline math); brief 04 (Memory-as-Metabolism gravity model); brief 08 (HippoRAG PPR + RRF); brief 12 (Graphiti hybrid retriever — semantic + BM25 + graph-distance); brief 17 (qmd RRF + LLM rerank without published constant); brief 18 (LongMemEval as primary tuning benchmark); SCNS audit §1 (today's 0.7 / 0.3 vec/kw weights — undocumented origin).
**Cross-refs:** composition design §3.1 step 4 (the "weight tuple" placeholder); gates gap-01 candidate (b) score formula and gap-02 signal weighting. Touches WS5 (scoring formalism).

---

## 1. The gap

Synthesis §2.3 names this gap precisely: every hybrid-retrieval paper says "we use semantic + BM25 + graph" and **omits the numeric weights**. Zep's paper *explicitly* says "weighting matters more than the individual signals" — and does not publish the weighting. Graphiti's README doesn't publish it. qmd gestures at RRF without the constant. SCNS uses 0.7 / 0.3 vec/kw with no recorded justification.

**There is no reusable default in the field.** Lethe must pick, publish, and tune its own — and document the tuning protocol so adopters can re-tune for their workload.

If we ship without this:
- Adopters fly blind. They can run Lethe but cannot tell whether their workload would benefit from re-weighting; nor can they reproduce our numbers.
- The retention engine (gap-01 candidate b) has no concrete formula — α/β/γ/δ/ε are unspecified.
- WS4 benchmarks become un-interpretable: a number from "Lethe with weights X" is a different system than "Lethe with weights Y" and we cannot recover X from a paper.
- The synthesis §3.3 commitment ("Lethe ships with named, justified default weights") is unmet.

This gap is unusual in that the work is not *research* — it is **publishing what every other paper hides**. The contribution is reproducibility.

---

## 2. State of the art

- **Brief 01 Zep.** Reports the +18.5% LongMemEval and 90% latency reduction headline. Method section uses "hybrid scoring." Numbers withheld. Strength: validates that hybrid wins; weakness: doesn't tell us by how much each signal contributes.
- **Brief 05 Cognitive Weave.** Has the cleanest decay math in the corpus: a residual baseline + exponential decay parameterized by `λ`. Brief 05 §3 captures the form; the constant `λ` is per-deployment. Strength: a model. Weakness: only one of the five terms in our score.
- **Brief 04 Memory-as-Metabolism.** Gravity-model attention is intuitively the same shape as recency × connectedness × utility, but not parameterized. Inspires the *form*, not the numbers.
- **Brief 08 HippoRAG.** Personalized PageRank gives the connectedness term a defensible formal substrate. PPR damping factor (typically 0.85) is the only published constant in this neighborhood.
- **Brief 12 Graphiti.** Hybrid retriever with semantic + BM25 + graph-distance. Constants live in Python defaults; not in the README.
- **Brief 17 qmd.** Uses Reciprocal Rank Fusion (RRF) with `k=60` (the literature-default RRF constant from Cormack et al.) for combining BM25 + vector. Plus LLM rerank as a final pass. **The closest thing to a published number** in the entire reviewed corpus: RRF `k=60` is a known field default and qmd at least gestures at it.
- **Brief 18 LongMemEval.** Ground-truth gold-fact annotations make it suitable as a tuning target. Published splits (extraction / multi-session reasoning / temporal / knowledge updates / abstention) let us tune per-ability. Brief 19 (LoCoMo) provides secondary signal.
- **SCNS today.** `0.7 · vec_score + 0.3 · kw_score` (audit §1). Origin: undocumented; survives because the failure mode (drift toward kw with simple queries) is in tolerance for SCNS's personal scale. Not adoptable as a Lethe default without justification.

The substrate exists for two of the five terms (decay form from brief 05; PPR/connectedness from brief 08). The other three (utility from gap-02; type-priority from dream-daemon §2.7; contradiction-penalty from gap-13) require Lethe-side defaults.

---

## 3. The score, formally

The score in gap-01 candidate (b) is:

```
score(fact) = α · type_priority(fact)
            + β · recency_decay(last_access(fact))
            + γ · connectedness(fact)
            + δ · utility_signal(fact)
            - ε · contradiction_penalty(fact)
```

Plus the **retrieval-time hybrid** at composition §3.1 step 4:

```
recall_score(fact, query) = w_sem · sem(fact, query)
                          + w_lex · bm25(fact, query)
                          + w_graph · graph_distance(fact, query_anchors)
                          + w_intent · intent_route_bonus(fact, intent)
                          + w_utility · utility_prior(fact)
```

Two distinct weight tuples: (α, β, γ, δ, ε) at consolidate-time; (w_sem, w_lex, w_graph, w_intent, w_utility) at recall-time. They are not the same numbers; they answer different questions.

---

## 4. Candidate v1 approaches

### Candidate (a) — Theory-driven defaults (publish reasoned guesses; tune later)

**Sketch.** Pin defaults from first principles + the few field anchors we have:
- **Recall-time:** w_sem = 0.5, w_lex = 0.3, w_graph = 0.15, w_intent = 0.05, w_utility = 0.0 at cold-start; w_utility ramps to 0.2 once tenant has >1k recall ledger entries (re-distributed proportionally from sem/lex). Combine via RRF with `k=60` (qmd / Cormack default), not weighted-sum, to make the tuple scale-invariant.
- **Consolidate-time:** α = 0.2 (type_priority), β = 0.3 (recency, half-life 30d), γ = 0.2 (connectedness, normalized to top-10% percentile), δ = 0.4 (utility), ε = 0.5 (contradiction penalty applied multiplicatively, not additively).
- Document each choice in a one-line rationale next to the constant.

**Cost.** Lowest. Pure publication.
**Failure mode.** Defaults wrong on real workloads. Detectable in WS4 LongMemEval; correctable.
**Eval signal.** WS4 benchmark numbers vs. published Zep / MemGPT baselines; if Lethe at default weights underperforms by >5 absolute points on any subset, defaults are wrong.

### Candidate (b) — Bayesian-optimization sweep on LongMemEval

**Sketch.** Run hyperparameter sweep (Optuna or skopt) over both weight tuples, optimizing for LongMemEval composite + LoCoMo secondary, with a penalty term for cost (tokens/query). Publish the maximum-likelihood tuple as default.
**Cost.** Modest compute (one full-eval per trial × ~50 trials). Workload investment, not implementation investment.
**Failure mode.** Overfits to LongMemEval. Real Lethe deployments may have very different query distributions.
**Eval signal.** Held-out portion of LongMemEval (not used in the sweep) + the SCNS-derived Lethe-native task set (charter §4.1) measured separately. If held-out drops vs. theory-driven baseline, sweep overfit.

### Candidate (c) — Per-tenant online tuning

**Sketch.** Ship theory-driven defaults; expose a `tune_weights(tenant_id, eval_set)` admin verb that re-runs the sweep against a tenant's recall ledger + a tenant-supplied small eval set, writing tuned weights back to S2 per-tenant config (composition §2 S2 row).
**Cost.** High implementation; requires per-tenant eval substrate.
**Failure mode.** Tenants without an eval set cannot tune; the verb becomes a hazard. Also: per-tenant tuning frustrates reproducibility ("which weights produced this number?" requires a snapshot per tenant).
**Eval signal.** Quality uplift on tenant-supplied set vs. defaults; cost overhead; reproducibility audit pass-rate.

### Candidate (d) — RRF-only at retrieval-time, weighted-sum only at consolidate-time

**Sketch.** Drop the recall-time weighted sum entirely; combine sem + lex + graph via RRF (k=60). Intent and utility as *post-RRF* re-rank passes. Recall-time tuple collapses to two parameters: RRF k, intent-bonus magnitude.
**Cost.** Lowest of the methodologically-clean options.
**Failure mode.** RRF is rank-based; loses calibrated-score information. For thresholding (e.g., "only return facts with score > X") this is bad.
**Eval signal.** Compare to (a) on LongMemEval; if delta < 1 absolute point, prefer (d) for parameter-economy.

### Trade-off table

| Axis | (a) Theory | (b) BO sweep | (c) Per-tenant | (d) RRF-only retrieval |
|---|---|---|---|---|
| Time-to-publish defaults | now | weeks | months | now |
| Numerical legitimacy | low (reasoned guesses) | high (data-driven) | highest per-tenant | low |
| Reproducibility | high | high | low (per-tenant snapshots) | high |
| Cold-start | works | works | bad (no eval yet) | works |
| Tunable downstream | yes | yes | yes (built-in) | yes |
| WS4 dependency | none | hard dep on full eval harness | dep on per-tenant eval | none |
| Composes with gap-02 | yes | yes | yes | yes (utility as post-RRF rerank) |

---

## 5. Recommendation

**Phase the deliverable. Ship (a) at v1; commit to (b) before v1.1; treat (c) as v2.**

Concretely:

1. **v1 ships theory-driven defaults from §4 candidate (a)**, each pinned with a one-line rationale. RRF `k=60` (qmd/Cormack anchor); recall-time tuple (0.5, 0.3, 0.15, 0.05, ramping 0.2 utility); consolidate-time tuple (0.2, 0.3, 0.2, 0.4, 0.5). These are *reasoned guesses* and the documentation must say so.
2. **WS4 BO sweep produces the v1.1 published defaults** (candidate b). Sweep run on full LongMemEval, validated on held-out + SCNS-native eval, with cost penalty. Output is one number per knob with a 95% confidence interval (so adopters can see *how much* the tuning gained over theory). The deliverable is `docs/05-scoring-design.md` updated with these numbers (WS5 owns it; this brief specifies the protocol).
3. **(c) per-tenant online tuning is v2.** Lethe v1 logs the substrate that makes it possible (recall ledger + outcome ledger from gap-02) but does not expose the verb.
4. **(d) RRF-only is rejected** unless the BO sweep shows weighted-sum at recall-time gains <1 absolute point — at which point we collapse and save parameters. Empirical not-now decision.

**The hybrid score-formula form is fixed at v1**: linear combination at consolidate-time, RRF-of-three-rankers at recall-time with weight-tuple post-rerank. This brief commits to the form; the numbers are what change between v1 (theory-driven) and v1.1 (BO-tuned).

**Stop-gap.** None needed. Theory-driven defaults are themselves the stop-gap; the BO sweep upgrade is post-launch work, not a v1 blocker.

---

## 6. The tuning protocol (publishable)

A reproducible protocol, runnable from `scripts/eval/tune-weights.sh` (WS4 lays this down):

1. **Eval set.** LongMemEval primary; LoCoMo secondary; SCNS-native held-out (gap-14). Split 70/15/15 train/val/test; sweep on train+val; report on test.
2. **Search space.** Each weight in [0, 1]; sum-to-1 constraint per tuple (normalized post-sample).
3. **Trials.** 50 BO trials baseline; expand to 100 if marginal-improvement curve hasn't flattened.
4. **Objective.** `0.7 · accuracy_composite + 0.3 · (1 - normalized_cost)`. Cost = mean tokens/query × p95 latency in seconds, normalized to the static-weights baseline.
5. **Output.** One JSON per swept tuple + a 95% bootstrap CI; markdown report committed to `docs/05-scoring-design.md`.
6. **Re-run cadence.** Every release; weights freeze in semver-stable form (e.g., `lethe-weights-v1.0.0`).

This is the methodology no reviewed paper publishes. It is the contribution.

---

## 7. Residual unknowns

- **Workload sensitivity.** The BO-tuned defaults are right *for the eval mix*. Real workloads differ. We bet that the SCNS-native held-out captures enough of the agent-workflow distribution to be representative; if not, candidate (c) becomes a v2 priority.
- **Cost weight.** The 0.7/0.3 accuracy/cost split in the objective is itself a free parameter. If we tune to it, accuracy dominates; tighten if real adopters complain about latency.
- **Intent-bonus magnitude.** w_intent = 0.05 is conservative; gap-12 may want more once misclassification fallback is measured.
- **Contradiction-penalty form.** ε is multiplicative on the consolidate-time score for invalidated facts. Whether multiplicative or additive matters at boundary cases (a heavily-utility-weighted fact that gets invalidated). Eval needed in gap-13.
- **Long-tail behavior.** Defaults may be right at the median fact and wrong at the extremes (highest-utility facts; never-utility-cited facts). Instrument score-distribution histograms; revisit if a quartile is flat.
- **Whether decay is recency-of-creation or recency-of-last-access.** Brief 05 uses creation; SCNS uses access. We propose access (utility-driven) and instrument both for comparison.

---

## 8. Touch-points

- **gap-01 retention engine** — owns the consolidate-time score formula; this brief owns the (α, β, γ, δ, ε) numbers.
- **gap-02 utility feedback** — owns the *signal*; this brief owns the *weight* on it.
- **gap-12 intent classifier** — w_intent magnitude is partly a function of classifier confidence (gap-12 produces a confidence which can be folded into the bonus).
- **gap-13 contradiction resolution** — owns when ε applies; this brief owns its magnitude.
- **gap-14 eval-set bias** — the BO sweep can over-fit; gap-14 owns the held-out discipline.
- **WS4 (eval)** — runs the protocol §6; produces v1.1 numbers.
- **WS5 (scoring formalism)** — formalizes the math; this brief specifies form + protocol, WS5 specifies notation.
- **WS6 (API)** — exposes `tune_weights` admin verb at v2.
- **WS7 (migration)** — SCNS shim must translate SCNS's 0.7/0.3 weights or document the difference; if Lethe defaults perform worse than SCNS's tuned weights on SCNS workloads, that's a gating signal (legacy regression).
