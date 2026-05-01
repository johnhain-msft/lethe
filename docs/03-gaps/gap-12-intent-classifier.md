# gap-12 — Intent classifier (when to remember, when to reply)

**PLAN.md §WS3 Track B #8** — first-class.
**Tier:** first-class (≥80 lines).
**Status:** active. Synthesis §3.7 (restored slot).
**Substrate:** brief 21 Karpathy ("the wiki accretes everything; the wiki is overwhelmed" — explicit failure mode of no-classifier); brief 11 MemGPT (function-calling boundary as implicit classifier); brief 15 Letta (memory-tool usage decision delegated to LLM); brief 02 MAGMA (perception filtering as intent gating); brief 04 memory-as-metabolism (admission as a metabolic gate); brief 16 MS AF (`AIContextProvider` is per-agent, no shared classifier); SCNS audit §3 (no remember-classifier; everything written passes through); synthesis §3.7; composition §6 + §10 (open seam: when does a `peer_message:claim` become a `remember`?).
**Cross-refs:** gap-02 utility-feedback (mis-classification cost), gap-10 peer-messaging (claim-handling), gap-11 forgetting-as-safety (mis-classified-as-remember requires later forget), gap-09 non-factual memory (one of the classifier's outputs).

---

## 1. The gap

Karpathy's "wiki accretes everything" failure (brief 21) is the symptom; the missing primitive is a **decision boundary**: of the things an agent could write down (every observation, every utterance, every peer message), which ones *should* be written? PLAN.md §WS3 Track B #8 names this gap directly.

If Lethe ships without an intent classifier:

1. **Memory bloat.** Every utterance gets `remember`'d; recall precision degrades; gap-07 write-amp explodes.
2. **Inverted utility.** Trivial pleasantries score equally with high-value observations; gap-02 utility signals are noise.
3. **Peer-message materialization confusion** (gap-10 §3.2 `claim`). No principled rule for when to materialize a peer claim.
4. **Audit/litigation hazard** (gap-11 sensitive-class). Sensitive payloads get remembered because the classifier didn't intercept.

The classifier is the **admission gate** to the memory system. Without it, the substrate is a firehose write-log.

## 2. State of the art

- **Brief 11 MemGPT.** Memory writes happen via function calls; the LLM is the implicit classifier (it decides when to call `archive_memory`). Quality varies with prompt + model.
- **Brief 15 Letta.** Same shape — memory tools are LLM-callable; LLM decides. Letta authors note "developer responsibility" to define the prompts that drive correct usage.
- **Brief 02 MAGMA §3.1.** Perceptual gating filters incoming sensory data before it reaches working memory. Inspirational architecture: gate as a separate module, not the cognitive worker.
- **Brief 04 metabolism §2.2.** Admission gating with energetic cost — every admit decision pays a metabolic price; encourages selectivity.
- **Brief 21 Karpathy.** Concedes lack of classifier; calls for one as future work.
- **SCNS audit §3.** No classifier; agents `remember` whatever they want.

## 3. Classification taxonomy

The classifier emits one of:
- **`remember:fact`** — factual claim worth persisting (`gravity_well = 9.8 m/s²`).
- **`remember:preference`** — durable preference (gap-09 non-factual; user prefers concise answers).
- **`remember:procedure`** — how-to (steps to deploy).
- **`reply_only`** — useful in this turn, not in future turns (the answer to "what's 2+2?").
- **`peer_route`** — should be sent to another agent, not stored locally (gap-10 §3.2 message types).
- **`drop`** — not worth memory or routing (acknowledgment tokens, pleasantries).
- **`escalate`** — sensitive-class (gap-11 §3.3); requires human review before write.

The taxonomy is the *contract*; the classifier *implementation* is the v1 question.

## 4. Candidate v1 approaches

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) Heuristic + LLM hybrid** | Cheap heuristics (length, keyword, peer-message type) trigger fast paths to `drop`/`peer_route`/`reply_only`; LLM call for the residual. | Latency + cost minimized; heuristics auditable; LLM-as-classifier covers the long tail. Heuristic drift over time. |
| **(b) LLM-only** (Letta-style) | Every candidate write goes through an LLM-call classifier. | Highest accuracy potential; uniform contract. Slow + expensive; no offline cache. |
| **(c) Caller-tagged** | Agent declares intent at write time (`remember(payload, intent='fact')`). | Cheapest; pushes burden to caller. Caller-bug risk: agent always tags `remember:fact` to avoid the classifier. |
| **(d) Heuristic-only** | Pure rules: type-based (peer-message types map to outcomes); length thresholds; verb extraction. | Cheap, deterministic. Misses subtle factual content; high false-drop rate. |
| **(e) Defer to caller, validate** | Caller declares; classifier audits async; flagged mis-classifications surface in audit. | Best of (b)+(c); v1 caller declares, v2 LLM audits offline. |

## 5. Recommendation

**Candidate (a) — heuristic + LLM hybrid.** Justification:

1. Most observations are clearly one class via cheap heuristics: ack tokens are `drop`, peer-message `claim` is a candidate `remember`, length-< 8 chars is `drop`, sensitive-class regex hit is `escalate`.
2. The LLM call is the residual filter — handles ambiguous content where heuristics underperform.
3. Auditable: every classification logs the heuristic-or-LLM path; gap-02 utility-feedback can flag mis-classifications.
4. Bridges cleanly to (e) v2: as caller-declarations mature, the classifier becomes the auditor.

**Stop-gap.** v0 = Candidate (d) heuristic-only with a high `escalate` rate. Anything ambiguous escalates; humans triage. Cheap, safe, slow.

**What we explicitly reject.** Candidate (c) alone — the SCNS audit shows agents will under-think their own intent declarations.

## 6. Decision boundary specification

| Input shape | Heuristic decision | LLM-residual? |
|---|---|---|
| Utterance < 16 chars | `drop` (unless contains digit / proper noun) | No |
| Peer-message `info` | `reply_only` (recipient observes, doesn't store) | Optional |
| Peer-message `claim` | LLM classifies as remember-or-drop | Yes |
| Tool-call result | `remember:procedure` if marked `idempotent`; else LLM | Yes |
| Sensitive-regex hit | `escalate` (gap-11) | Skip — escalate immediately |
| Caller-tagged `remember:fact` | Honor unless classifier objects (≥0.8 LLM confidence) | Audit-async |

Default behaviors are commitments; instrumentation logs deviations and feeds gap-02.

## 7. Residual unknowns

- **Classifier accuracy baseline.** Unknown until WS4 builds the eval set (gap-14). Bet: 85% F1 on a held-out set is the target; below that, the classifier itself is degrading recall.
- **LLM latency budget.** v1 = 200 ms median for the residual path; if exceeded, tighten heuristics. Revisit when corpus grows.
- **Drift detection.** Classifier behavior drifts as agent population shifts; gap-02 utility signals + periodic re-eval against fixed eval set (gap-14).
- **Cost ceiling.** LLM-call per ambiguous write × write-rate is the top-line cost; budget per tenant cap. Above cap, fall back to heuristic-only (Candidate d) for the overflow.
- **Multi-class outputs.** A single utterance may be both `remember:fact` and `peer_route` (worth storing AND sending elsewhere). v1: classifier emits *primary* class; secondary action is composable. Document.

## 8. Touch-points

- **gap-02 utility-feedback** — feedback signals identify mis-classifications.
- **gap-09 non-factual memory** — `remember:preference` is the main non-factual class; classifier output drives storage shape.
- **gap-10 peer-messaging** — peer-message `claim` is the canonical "ambiguous: remember or not" case.
- **gap-11 forgetting-as-safety** — sensitive-class triggers `escalate`; classifier is one of two sensitive-class detectors (the other is at retrieval time).
- **gap-13 contradiction resolution** — classifier's `remember:fact` rate determines contradiction frequency; mis-classifying preferences as facts pollutes contradiction signal.
- **gap-14 eval-set bias** — the eval set MUST include intent-classification cases that adversarially target heuristic boundaries.
- **WS4 (eval)** — classifier accuracy is the headline metric.
- **WS5 (scoring)** — score weight for `remember:procedure` vs `remember:fact` may differ; bridges to gap-03.
- **WS6 (API)** — caller-tagged intent on `remember`; intent class returned in the response.
