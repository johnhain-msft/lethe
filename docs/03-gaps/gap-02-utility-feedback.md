# gap-02 — Utility-feedback loop

**PLAN.md §WS3 Track B item #1** (utility-feedback capture). Synthesis §3.2.
**Tier:** first-class.
**Status:** active. The most novel claim Lethe can make (synthesis §3.2): no reviewed system closes the loop between *recall* and *score*.
**Substrate:** brief 01 (Zep), brief 02 (MAGMA), brief 04 (Memory-as-Metabolism §3.1 utility-driven reinforcement), brief 15 (Letta), brief 11 (MemGPT); SCNS audit §3.3 (`quality_checks` raw signal already logged but never fed back); dream-daemon design note §3.1 ("the only MaM mechanism not represented is utility-driven reinforcement"); synthesis §2.2 + §3.2.
**Cross-refs:** composition design §3.1 step 6 (recall ledger write), §4.4 (consolidate). Gates gap-01 candidate (b) and gap-03 weight tuning.

---

## 1. The gap

Every reviewed system scores memory at *ingest* and retrieves by *static* score. **No reviewed system ingests `recall` outcomes back into the scoring function.** Did the retrieved fact actually help? Did it appear in the agent's answer? Did the downstream tool call succeed? None of the reviewed systems close this loop.

SCNS comes closest — it logs `quality_checks` raw signal in the broker DB (audit §3.3) — but never feeds it into eviction. The dream-daemon explicitly notes (note §3.1) that *utility-driven reinforcement* is the only MaM mechanism it does not yet represent.

Why it matters for Lethe: charter §4.1 commits to "heuristic scoring v1: recency-weighted-by-access + structural connectedness + utility feedback." Without a real utility signal, the third term is a constant zero, the score collapses to "old + connected = good," and the retention engine (gap-01) demotes things by proxy of unrelated features. The "utility-aware promotion + demotion" headline becomes false.

If we ship without addressing this, the most differentiated thing Lethe could be — *the runtime that learns from recall outcomes* — disappears, and the project reduces to a Graphiti wrapper with a curated cadence schedule.

---

## 2. State of the art

- **Brief 01 Zep.** Implies traceability via temporal stamps but does not score on retrieval outcomes. The DMR/LongMemEval numbers are static-scorer numbers.
- **Brief 02 MAGMA.** Causal-edge partitioning and intent-routed weights are *retrieval-time* operations. No back-edge from retrieval-success to scoring.
- **Brief 04 Memory-as-Metabolism §3.1.** Names utility-driven reinforcement as a desired mechanism in the gravity model: facts that "do work" should accrete; facts that "fail to do work" should decay. **Vision-paper level**; no implementation, no defaults.
- **Brief 11 MemGPT.** Tier promotion (archival → core) is LLM-driven on context need, not on outcome. The core/archival boundary doesn't migrate based on whether retrieved facts paid off.
- **Brief 15 Letta.** `memory_rethink` and sleep-time agents can edit memory in light of new context, but the trigger is *new context*, not *outcome of past recall*. Closest existing primitive but not the same loop.
- **Brief 18 LongMemEval.** Eval set has ground-truth gold facts; could be used to *measure* utility-feedback uplift but is not itself a utility signal source.

The gap is not theoretical: brief 04 names it explicitly; SCNS proves a raw signal can be logged. The missing piece is **the ingestion path from logged signals into the scoring function**, plus a robust definition of "the signal" itself (today's `quality_checks` is one heuristic among many).

---

## 3. Defining the signal — what counts as utility?

Before candidate approaches, the brief must commit to *what we're measuring*. Three candidate signal sources, listed by signal-strength × cost:

| Signal | Source | Strength | Cost | Latency to availability |
|---|---|---|---|---|
| **Citation** — recalled fact appears in the agent's response text | Diff agent response against returned fact text (substring or embedding sim) | Medium-high (positive when present, silent when absent) | Cheap (one comparison per recall_id) | <1 s post-response |
| **Tool-call outcome** — recall preceded a tool call that succeeded | Caller passes back a `recall_id` outcome ack with `succeeded: bool` | High (causal proxy) | Requires caller cooperation | seconds–minutes |
| **Explicit user correction** — user fixes the agent and the corrected memory matches a returned fact | Compare user-correction event to recent recall ledger | Highest (ground-truth-ish, but rare) | requires correction surface | minutes–days |
| **Repeat-recall** — the same fact returned across N independent queries within a window | S2 ledger aggregation | Low-medium (popularity, not utility) | trivial | offline |
| **No-op** — recall returned but next agent action did not consult it | absence of citation + absence of tool ack | Low (negative signal, noisy) | trivial | <1 s |

**Default v1 signal set:** citation (cheap, automatic, non-blocking) + tool-call-outcome (causal, requires `recall_id` round-trip). Repeat-recall is a *secondary* signal logged but not used in the main weight (it's gameable). Explicit user correction is the ground-truth signal logged for offline analysis (gap-14 eval) but used cautiously online (low-frequency, high-variance).

Charter §4.1 already names "heuristic scoring v1" — this brief defines what *heuristic* means concretely.

---

## 4. Candidate v1 approaches

### Candidate (a) — Pull from caller (explicit `recall_outcome` API)

**Sketch.** Composition §3.1 step 6 already writes a `recall_id` to the S2 ledger and returns it to the caller. A new MCP verb `recall_outcome(recall_id, signals)` lets the caller report citation, tool-success, or correction. Server aggregates into the per-fact utility tally; dream-daemon reads on consolidate.
**Cost.** One round-trip per recall the caller chooses to ack. Storage: O(recalls × signals) in S2.
**Failure mode.** Caller may forget / refuse to ack; signal sparseness. Most existing MCP clients won't implement it.
**Eval signal.** Uplift on gap-01 promotion-precision when `recall_outcome` coverage > 30%; baseline behavior when coverage = 0%.

### Candidate (b) — Server-side passive inference (citation diff)

**Sketch.** Lethe runtime intercepts the agent's *next* response after a `recall` and diffs it against returned fact text (substring + embedding sim above threshold = citation). No caller cooperation required. Tool-success not measured, but citation alone is a meaningful signal (citation > 0 implies the agent found the fact relevant enough to cite).
**Cost.** Requires Lethe to see the agent's response — implies an MCP convention or a tracing hook. Brief 16 (MS Agent Framework) `AIContextProvider.OnInvokedAsync` is the model: invoked after the LLM response, has access to the response. The MCP equivalent is a `recall_followup` callback that the client invokes (cheaper for client to invoke automatically than to construct an explicit outcome message).
**Failure mode.** Agents that paraphrase break substring matching; embedding-sim threshold tuning becomes the eval-signal axis.
**Eval signal.** Recall@10 of "facts that were cited by the agent" against the ledger as ground truth; threshold sweep for sim cutoff.

### Candidate (c) — Hybrid (b) + opt-in (a) with weighting

**Sketch.** Always do (b) — citation diff is always available. Allow callers to opt in to (a) for stronger signal when they have it. Weight each signal: citation = 0.4, tool-success = 0.7, correction = 1.0, repeat-recall = 0.1, no-op = -0.2. Aggregate into per-fact utility score in S2.
**Cost.** Sum of (a) and (b).
**Failure mode.** Two pipelines to maintain; weight tuning becomes part of gap-03.
**Eval signal.** Same as (a) and (b) measured separately; net uplift of (c) over each individually must justify the complexity.

### Candidate (d) — Defer to v2; just log signals

**Sketch.** Build the S2 ledger; log everything; do not feed the signal into scoring at v1. Dream-daemon ignores the column; gap-01 candidate (b) δ-term is constant 0.
**Cost.** Cheapest at v1.
**Failure mode.** Forfeits the project's headline differentiation. Charter §1 + synthesis §3.2 commitments unmet.
**Eval signal.** None — we ship without measuring the loop closed.

### Trade-off table

| Axis | (a) Pull | (b) Passive | (c) Hybrid | (d) Defer |
|---|---|---|---|---|
| Caller cooperation required | yes | minimal (followup hook) | partial | none |
| Signal strength at coverage=100% | High | Medium-high | Highest | n/a |
| Signal strength at coverage=0% | Zero | Same as (b) | Same as (b) | n/a |
| Cold-start | bad (no acks yet) | good | good | n/a |
| Charter §4.1 commitment | met | met | met | unmet |
| Implementation complexity | low | medium | medium-high | trivial |
| Measurable at WS4 | yes | yes | yes | no |

---

## 5. Recommendation

**Candidate (c) — hybrid, with (b) the always-on path and (a) the opt-in stronger signal.**

Justification:

1. **(b) eliminates the cold-start problem.** From day one Lethe has a non-zero utility signal regardless of caller behavior. This matters because gap-01 candidate (b) needs a non-zero δ-term to differ from candidate (a); without (b), retention collapses to "old + connected" until callers adopt the explicit API.
2. **(a) provides the high-signal channel for cooperative callers.** SCNS itself will be the first cooperative caller; the SCNS compatibility shim (charter §4.1) can ack `recall_outcome` automatically based on its own quality_checks pipeline. This lets Lethe demonstrate the closed loop on a real workload from launch.
3. **Weighted aggregation is essential.** Repeat-recall left unweighted produces a popularity feedback loop; recommended weight pinning (citation 0.4, tool-success 0.7, correction 1.0, repeat-recall 0.1, no-op -0.2) makes the loop monotone in the right signals. gap-03 owns calibration.
4. **WS4 can measure both channels independently** (eval signal column above), so the hybrid is testable and falsifiable.

**Stop-gap if (c) is not ready at v1 cut.** Ship Candidate (b) only; opt-in API is additive. Do **not** ship (d) — that forfeits the project headline.

---

## 6. Residual unknowns

- **Citation-diff threshold.** Substring vs. embedding-sim cutoff is empirical. Bet: substring catches ~60% of citations, embedding-sim ≥0.85 catches ~85%; tune in WS4.
- **Adversarial signal.** A misbehaving caller could fake `recall_outcome` to up-weight chosen facts. Mitigation: per-tenant rate-limit on outcome reports + sanity-check (outcome of a recall_id with no ledger entry = ignored). This is gap-04-adjacent (multi-agent) and gap-11-adjacent (poisoning).
- **Decay of utility.** A fact useful in 2025 may not be useful in 2026. Should the utility signal itself decay? Bet: yes, with a half-life of ~30 days (matches recency decay in gap-03). Instrument the distribution and re-tune.
- **Negative signal asymmetry.** Penalizing no-op recalls by -0.2 may suppress facts that are *useful exactly when needed* but rarely needed. Bet: keep the asymmetry (negative signal weighted weaker than positive) and watch for under-recall complaints in WS4.
- **Cross-tenant signal pooling.** Theoretical lift from sharing utility patterns across tenants is large but privacy-incompatible. v1: per-tenant only.
- **Interaction with peer-message provenance.** A fact recalled-and-cited that originated from a *peer agent* — does the peer's utility tally also rise? Bet: yes, scaled by 0.5 to discount second-hand causation. Defers to gap-10.

---

## 7. Touch-points

- **gap-01 retention engine** — consumes the utility tally as the δ-term in candidate (b)'s blended score. Without gap-02 the term is a constant.
- **gap-03 scoring weights** — owns weight pinning for citation/tool-success/correction/repeat/no-op aggregation, and the half-life of the utility signal.
- **gap-04 multi-agent concurrency** — adversarial-signal mitigation is partly a tenant-isolation concern.
- **gap-06 extraction quality** — utility signal can also feed back into extraction confidence: facts that get cited reinforce the extraction; facts that produce no-ops on every recall raise an extraction-dispute flag.
- **gap-10 peer messaging** — peer-asserted facts get a halved utility credit.
- **gap-13 contradiction resolution** — facts on the losing side of a contradiction may carry utility tallies; the bi-temporal invalidate preserves them so a future re-validation could restore.
- **gap-14 eval-set bias** — citation-diff threshold tuning runs against the eval set; the eval set must not over-fit to citation-detected behaviors.
- **WS4 (eval)** — measures coverage and uplift; produces threshold defaults.
- **WS5 (scoring)** — turns the weighted aggregate into the formal δ-term in the score function.
- **WS6 (API)** — `recall_outcome` MCP verb (Candidate (a) channel); `recall_followup` hook (Candidate (b) channel).
- **WS7 (migration)** — SCNS shim auto-acks `recall_outcome` so the SCNS workload becomes the first cooperative caller from day one.
