# gap-14 — Eval-set construction without confirmation bias

**PLAN.md §WS3 Track B #9** — first-class.
**Tier:** first-class (≥80 lines).
**Status:** active. Synthesis disposed this slot to "WS4 owns the eval plan"; QA §3.1 + the user prompt re-mandate a first-class WS3 brief that frames the *hazard* and hands WS4 substrate without writing the eval plan itself.
**Substrate:** brief 21 Karpathy (concedes "eval is performed by the same author who built the heuristic — confirmation bias risk"); brief 02 MAGMA (eval against held-out cognitive tasks); brief 04 memory-as-metabolism (proposes ablation-based metabolism evals); brief 14 issue #1300 (user-task is the eval set — operator-derived, not author-derived); brief 15 Letta (memory-tool usage benchmark; held-out tasks); SCNS audit §3 (no eval substrate); synthesis §3.10 + §2.13; composition §10 (open seam: eval substrate); gap-02 utility-feedback (the on-line signal that eval-set static evaluations don't capture); gap-12 intent classifier (its accuracy is the headline eval target).
**Cross-refs:** Gates WS4 (eval plan); informs gap-12 (classifier accuracy), gap-03 (scoring weight calibration), gap-02 (signal-vs-eval coupling), gap-01 (consolidation-quality eval).

---

## 1. The gap

PLAN.md §WS3 Track B #9 names this gap directly. Karpathy (brief 21) concedes the failure mode — "the same author who built the retrieval heuristic also writes the eval; the eval confirms the heuristic." The hazard is real and standard in IR research: a system tuned against an eval set co-designed with the system reports inflated metrics that do not generalize.

Lethe is *especially* exposed:

1. **Author-bias.** Whoever writes the dream-daemon's promotion rules will likely also write the "good promotion" eval cases.
2. **Survivorship-bias.** Eval cases derived from "things our agents have asked" will under-represent things they should have asked but didn't.
3. **Single-population-bias.** Eval set drawn from one tenant's traces does not generalize to a different domain (legal vs. medical vs. devops swarms).
4. **Negative-case scarcity.** "What should not be remembered" cases are harder to author than "what should be remembered" cases; classifier (gap-12) eval becomes one-sided.
5. **Drift insensitivity.** A static eval set blesses the system at v1 launch, then says nothing as the system or its inputs evolve.

Charter §3 commits to evaluation as a guard-rail. Without an eval-set methodology that resists confirmation bias, the guard-rail is a mirror.

This brief frames the **hazard** and hands WS4 substrate (taxonomy, sourcing strategy, contamination defenses, drift signals). WS4 owns the eval plan implementation.

## 2. State of the art

- **Brief 21 Karpathy.** The most explicit acknowledgement: "we did not evaluate against an external benchmark; the eval is the author's intuition." Lethe inherits the wiki's substrate; it must not inherit the wiki's eval gap.
- **Brief 14 issue #1300.** Surfaces a user-derived task: "agent A needs context from agent B." This is exactly the kind of operator-derived case that resists author-bias — neither the wiki author nor the Lethe author chose it.
- **Brief 15 Letta.** Memory-tool benchmarks (e.g. MemGPT-Eval) — held-out tasks where the agent must use memory correctly. Useful as a baseline; insufficient because designed by memory-tool authors.
- **Brief 02 MAGMA.** Cognitive tasks (working memory span, reasoning under context-load) as eval. Useful for the *substrate* layer; doesn't capture the *application* layer Lethe targets.
- **Brief 04 memory-as-metabolism §3.4.** Ablation-based eval — disable a metabolic operator; observe degradation. Powerful + cheap; under-deployed in IR.
- **SCNS audit §3.** Empirical observation only ("the system feels good"); no eval substrate.

## 3. Eval-set taxonomy

A bias-resistant eval set has multiple sources, balanced + adversarial:

| Source class | Example | Bias resistance | Cost |
|---|---|---|---|
| **Operator-derived tasks** | Issue #1300; user complaints; support tickets | Strong — neither author chose | Low (free) |
| **Adversarial cases** (held-out red-team) | Cases authored by a person not on the implementation team | Strong | Medium (requires red-team time) |
| **Ablation pairs** | Disable scoring weight W; observe recall on a fixed task | Strong (perturbation, not selection) | Low |
| **Production trace replay** (multi-tenant) | Replay one tenant's traces against a system tuned on another | Strong (cross-population) | Medium |
| **Author-curated cases** | What the implementation team thinks should work | **Weak — confirmation hazard** | Low |
| **Synthetic LLM-generated** | LLM writes "what should this remember?" cases | Medium — depends on prompt; risk of LLM-bias-confirms-system | Low |

The recommendation: **all classes contribute; author-curated cases are tagged and capped at <30% of the eval-set.** Above the cap, headline metrics are reported separately for "operator+adversarial+ablation+replay" subsets.

## 4. Candidate v1 approaches

| Candidate | Approach | Trade-offs |
|---|---|---|
| **(a) Multi-source eval set with capped author-share** | All taxonomy classes; author-curated <30% by case-count. | Strongest bias resistance; medium build cost. The recommendation. |
| **(b) Operator-only** | Only operator-derived + production-replay. | Strong bias resistance; cold-start problem (no operators yet). |
| **(c) Synthetic-only** | LLM generates eval cases. | Cheap, fast; opaque LLM bias; LLM-confirming-LLM hazard real. |
| **(d) Author-curated, transparent** | Author writes the cases; declare bias openly. | Cheap, fast; charter §3 unsatisfied. |

## 5. Recommendation

**Candidate (a) — multi-source with capped author-share — with the following hand-off to WS4:**

1. **Pre-launch eval set composition (target):** 30% operator (issue #1300, support traces sourced post-WS6), 25% adversarial red-team, 20% ablation pairs, 15% synthetic (clearly tagged), 10% author-curated.
2. **Mandatory contamination defenses:**
   - Eval-set fact-IDs are stored in S2 with a `contamination_protected` flag; `remember`-of-an-eval-fact during system operation triggers a CI-gate failure.
   - Provenance enforcement (gap-05) makes this verifiable.
3. **Drift signals (continuous post-launch):**
   - Distributional drift detector on input traces; alert when production input distribution diverges from eval-set input distribution beyond threshold.
   - Re-evaluation cadence: monthly against the held set; quarterly construction of a fresh adversarial slice.
4. **Headline metrics reported in two strata:** all-cases vs. operator+adversarial+ablation+replay-only. Public comparison MUST report both.
5. **Negative-case construction policy:** for every "should remember" case, an adversarial counterpart exists ("looks similar, should NOT remember"). Classifier (gap-12) eval is symmetric.

**Stop-gap.** WS4-deferred eval plan — but with this brief's *constraints* binding: any v1 eval-plan WS4 produces must satisfy (1)–(5). If WS4 cannot meet (1) at launch (operator data not yet available), it MUST clearly mark headline metrics as "preliminary, author-share above threshold."

## 6. Residual unknowns

- **Adversarial red-team sourcing.** Who? An internal-but-different-team reviewer? An external consultant? Open question for WS4 owner.
- **Operator-data privacy.** Real production traces contain sensitive data; the eval-set sourcing pipeline must scrub, with gap-11 sensitivity-class taxonomy. Bet: scrubbing acceptable; if it nukes too much signal, escalate.
- **Synthetic-bias detection.** When LLM-generated cases are wrong (confirming system errors), how do we know? Bet: spot-check 5% of synthetic cases against author + adversary; if disagreement > 15%, distrust the synthetic batch.
- **Ablation-pair coverage.** How many ablations are practical? Bet: per scoring weight + per gate threshold + per heuristic in gap-12 = ~30 ablation pairs; manageable.
- **Eval-set version drift.** As the system evolves, some eval cases become outdated (the right answer changes). Versioning + provenance per case; "case retirement" event in S5.

## 7. Touch-points

- **gap-01 retention engine** — consolidation-quality is one of the eval headline metrics.
- **gap-02 utility-feedback** — production utility signal is *not* the eval set; relationship: utility informs scoring; eval validates scoring. Don't conflate.
- **gap-03 scoring weights** — eval set is the calibration signal; this brief constrains what the eval set must look like.
- **gap-05 provenance enforcement** — needed for contamination protection.
- **gap-11 forgetting-as-safety** — eval-set must include "this should be forgotten" cases.
- **gap-12 intent classifier** — symmetric positive/negative cases; the brief above.
- **WS4 (eval)** — this brief is WS4's input constraint document; WS4 builds the implementation.
- **WS5 (scoring)** — scoring weight calibration uses eval-set output as ground truth; bias here propagates to scoring.
- **WS7 (migration)** — production traces from SCNS are a candidate operator-trace source; sourcing must respect SCNS users' privacy.
- **WS8 (deployment)** — drift detector + monthly re-eval are deploy-cadence dependencies.
