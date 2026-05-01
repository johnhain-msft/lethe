# gap-06 — Extraction quality (LLM-extraction reliability)

**Synthesis-extension slot** (synthesis §3.6 + §2.7).
**Tier:** extension (target 50–80 lines).
**Status:** active. Composition §4 ("`remember` triggers async LLM extraction") commits to LLM-mediated extraction; this brief specifies how we know it's correct.
**Substrate:** brief 12 Graphiti (uses LLM for entity/edge extraction; documents accuracy gaps); brief 11 MemGPT (LLM-as-extractor); brief 02 MAGMA (perceptual gating with confidence scoring); SCNS dream-daemon note §2.5 (extraction phase, no quality measurement); synthesis §3.6; composition §4 (write path); gap-12 (intent classifier as upstream filter); gap-13 (contradiction-resolution as downstream catch); gap-14 (eval-set is the calibration signal).

---

## 1. The gap

LLM extraction (text → entities + edges) is the runtime's most error-prone step. False positives pollute the graph; false negatives drop signal silently. Brief 12 (Graphiti) documents the failure mode: "extraction depends on prompt + model; quality varies." SCNS's dream-daemon note §2.5 has no quality measurement at all.

If Lethe ships without extraction-quality enforcement:

1. **Polluted graph.** Bad entity disambiguation merges "Apple Inc." and "apple (fruit)" into one node.
2. **Silent loss.** A fact in the source episode never becomes a graph edge; recall says "no result" forever.
3. **Drift over time.** Same model, different prompt-version, different distribution; metrics regress without alarm.
4. **Cost-quality blindness.** Dropping to a cheaper model halves cost; quality drop unmeasured.

## 2. State of the art

- **Brief 12 Graphiti.** Reports extraction quality as a model-+-prompt-+-domain function. The substrate is correct; calibration is the consumer's responsibility.
- **Brief 11 MemGPT.** LLM-as-extractor; quality bounded by the agent's own prompt.
- **Brief 02 MAGMA §3.1.** Perceptual gating with confidence scoring — keep extractions above threshold; flag below.
- **SCNS dream-daemon note §2.5.** Extraction runs; no quality measurement; bug discovery is via downstream symptoms (recall failures).

## 3. Quality dimensions

Three dimensions to measure:

1. **Recall** — of the facts present in the source episode, how many were extracted?
2. **Precision** — of the facts extracted, how many are truthful + relevant?
3. **Disambiguation** — for each extracted entity, did it bind to the correct existing node (vs. creating a duplicate)?

## 4. Candidate v1 approaches

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) Confidence-thresholded ingest** | Extractor returns confidence; below threshold → quarantine for review. | Cheap; depends on calibrated confidence. |
| **(b) Two-model adjudication** | Two extractor models; agreed extractions auto-ingest; disagreements quarantined. | Stronger; 2× cost. |
| **(c) Held-out eval + drift alarm** | Periodically re-extract a fixed eval set; alert on F1 drop > threshold. | Cheap; doesn't catch per-extraction errors. |
| **(d) Downstream-symptom monitoring** | Watch contradiction rate (gap-13) + recall failure rate; spike triggers extraction audit. | Cheap; lagging signal. |

## 5. Recommendation

**Candidates (a) + (c) + (d) — confidence threshold + held-out eval + downstream symptoms.** Justification:

1. (a) catches per-extraction outliers.
2. (c) catches model/prompt drift (gap-14 calibration).
3. (d) catches what (a) and (c) miss — composite + integration failures surfaced by the system itself.
4. Skip (b) — 2× LLM cost for marginal gain over (a)+(c)+(d).

**Quarantine semantics.** Below-confidence extractions are written to S5 in a `quarantine` state, not S1. A reviewer (or a periodic LLM auditor) advances them to ingest or rejects. The episode itself remains in S1 (gap-08 §3.1 durability is unaffected); only the extracted facts are gated.

**Stop-gap.** v0 = ingest everything; rely on gap-13 (contradiction) and gap-02 (utility) to catch errors after the fact. Acceptable for tiny corpora; degrades fast as corpus grows.

## 6. Residual unknowns

- **Confidence calibration.** Modern LLMs return confidence that is loosely correlated with correctness. Bet: per-domain calibration table; instrument and adjust.
- **Quarantine throughput.** How many extractions land in quarantine? Bet: 5% target; if > 15% sustained, threshold is mis-tuned.
- **Disambiguation v1 strategy.** Defer to Graphiti's native disambiguation (brief 12); audit miss-rate via held-out eval set; revisit if F1 < 0.85.
- **Re-extraction cadence.** When the model upgrades, do we re-extract historical episodes? Bet: only on opt-in; expensive; track in S5.

## 7. Touch-points

- **gap-01 retention engine** — extraction is a dream-daemon phase (note §2.5); resumability per gap-08 §3.3 covers crash mid-extract.
- **gap-08 crash safety** — quarantine state is durable.
- **gap-12 intent classifier** — upstream filter; classifier's `drop` decisions reduce extractor load.
- **gap-13 contradiction resolution** — downstream symptom; spike in contradictions implies extraction degradation.
- **gap-14 eval-set bias** — held-out eval includes "raw episode → expected extracted facts" pairs.
- **WS4 (eval)** — extraction F1 is a headline metric.
- **WS6 (API)** — `recall` may surface quarantined facts with a flag (operator-only).
