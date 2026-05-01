# QA — WS3 (composition design + 14 gap briefs)

**Reviewer:** fresh QA agent (no prior session context).
**Date:** 2026-05-01.
**Scope:** `docs/03-composition-design.md`; `docs/03-gaps/gap-01..gap-14.md`; the post-WS3 section appended to `docs/HANDOFF.md`.
**Lens:** Does WS3 give a WS4 (eval) author and a WS5 (scoring) author enough substrate to start designing without re-doing research? Secondary lens: WS6 (API) and WS7 (migration).
**Inputs cross-checked against:** `PLAN.md` §WS3; `docs/00-charter.md`; `docs/02-synthesis.md`; `docs/02-lit-review/01..21`; `docs/QA-WS0-WS2.md` §4.

---

## 1. Score table

Per-doc, 1–5 each criterion. **Adherence** = PLAN.md §WS3 spec adherence (and template, for gap briefs). **Substance** = real analysis vs. filler. **Evidence** = citations resolve; no fabrication. **Consistency** = aligns with composition design + other briefs. **Downstream-ready** = WS4/WS5/WS6/WS7 unblock.

| Doc | Lines | Adherence | Substance | Evidence | Consistency | Downstream-ready | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `03-composition-design.md` | 423 | 5 | 5 | 5 | 5 | 5 | All five §1 questions answered; 3 topologies + trade-off table; per-store ACID rationale; 14-row failure matrix + 2-down combinations; mermaid diagram; explicit deferrals. The most-cited downstream substrate; carries its weight. |
| `gap-01-retention-engine.md` | 149 | 5 | 5 | 5 | 5 | 5 | Converts dream-daemon design-note open questions into measurable eval signals (§3.2). Score formula form pinned; numbers handed to gap-03. Excellent WS4/WS5 input. |
| `gap-02-utility-feedback.md` | 136 | 5 | 5 | 5 | 5 | 5 | Concrete signal taxonomy with cost/strength/latency table; weighted-aggregate proposal (citation 0.4 / tool 0.7 / correction 1.0 / repeat 0.1 / no-op −0.2). Solves the "candidate is concrete, not aspirational" lens directly. |
| `gap-03-scoring-weights.md` | 169 | 5 | 5 | 5 | 5 | 5 | Two formal score expressions (§3); reasoned-guess defaults pinned with rationale; reproducible BO-sweep protocol §6. The "publish what others hide" framing is the contribution. One minor consolidate-tuple normalization ambiguity (see §3.5 below). |
| `gap-04-multi-agent-concurrency.md` | 65 | 4 | 4 | 4 | 5 | 4 | Extension tier (target 50–80). Compact but answers the WS6 contract questions (CAS, 409, idempotency). Could surface more discussion of CAS contention envelopes; bullet-light residual-unknowns. |
| `gap-05-provenance-enforcement.md` | 100 | 5 | 4 | 5 | 5 | 5 | Specifies type-system invariant + DB constraints + lints. Five named lints with concrete checks. Strong WS6/WS7 input. |
| `gap-06-extraction-quality.md` | 73 | 4 | 4 | 4 | 5 | 4 | Extension tier; three quality dimensions; 4-candidate table → multi-candidate recommendation (a)+(c)+(d). Quarantine semantics specified. Light on calibration math (deferred to WS4). |
| `gap-07-markdown-scale.md` | 170 | 5 | 5 | 5 | 5 | 5 | Splits PLAN #3 into three sub-questions with budgets (`MAX_S4B_REGEN_PER_CYCLE=100`, 1000-page S4a ceiling, RRF k=60). Operationalizes composition §2.1 split. |
| `gap-08-crash-safety.md` | 103 | 5 | 5 | 5 | 5 | 5 | Implementation contract for composition §5's T1/T2. Six concrete sub-contracts (§3.1–§3.6). Idempotency-key TTL pinned. Startup integrity check + reconciler specified. Strong WS6 input. |
| `gap-09-non-factual-memory.md` | 75 | 4 | 4 | 4 | 5 | 4 | Extension tier; clean shape table (§3) mapping shape→storage→durability→recall path. Always-load preference mechanism named but not wired into composition's read paths (see §3.3 finding). |
| `gap-10-peer-messaging.md` | 111 | 5 | 5 | 5 | 5 | 5 | Verb spec (`peer_message` / `_pull` / `_status`); addressing model with three shapes; four-type enum (query/info/claim/handoff); two-step provenance. WS6-ready. |
| `gap-11-forgetting-as-safety.md` | 171 | 5 | 5 | 5 | 5 | 5 | Three forget modes formalized (invalidate/quarantine/purge) with cost + failure-mode + when-to-use. Minority-hypothesis retention specified per-cluster with timeout. Composition §7 peer-corruption row directly closed. |
| `gap-12-intent-classifier.md` | 100 | 5 | 5 | 5 | 5 | 5 | Seven-class taxonomy; heuristic+LLM hybrid recommendation; decision-boundary table §6. Mostly self-contained; classifier-accuracy as headline WS4 metric is correctly handed off. |
| `gap-13-contradiction-resolution.md` | 202 | 5 | 5 | 5 | 5 | 5 | Correctly handled as committed→monitored. Four named stress regimes with healthy/break-point thresholds and per-stress mitigation owner. Detection-signal contract (§4) is the unique contribution. |
| `gap-14-eval-set-bias.md` | 95 | 5 | 5 | 5 | 5 | 5 | Five hazards enumerated; six-source taxonomy with bias-resistance scoring; multi-source eval-set recommendation with capped author-share <30% and two-strata reporting. WS4's input-constraint document. |
| `HANDOFF.md` post-WS3 | 113 | 5 | 5 | 5 | 5 | 5 | Inventory accurate (line counts verified — see §2.1); per-WS reading orders are surgical and useful. |

**Aggregate:** 4.7 / 5 across 16 docs.

---

## 2. PLAN-mandated 9-gap mapping (verified)

| PLAN.md §WS3 Track B item | Brief | First-class? | Lines | Verdict |
|---|---|---|---:|---|
| #1 utility-feedback capture | gap-02 | ✅ | 136 | covered |
| #2 scoring weight calibration | gap-03 | ✅ | 169 | covered |
| #3 markdown at scale | gap-07 | ✅ | 170 | covered (write-amp + concurrency + retrieval ceiling all addressed) |
| #4 unattended consolidation | gap-01 | ✅ | 149 | covered (dream-daemon evaluated on merits per PLAN north star) |
| #5 cross-agent peer messaging | gap-10 | ✅ | 111 | covered |
| #6 forgetting-as-safety | gap-11 | ✅ | 171 | covered |
| #7 contradiction resolution beyond LWW | gap-13 | ✅ | 202 | covered (HANDOFF originally disposed this to "committed by WS2" but post-WS3 reinstated with stress-test framing — appropriate) |
| #8 intent classifier design | gap-12 | ✅ | 100 | covered |
| #9 eval-set bias | gap-14 | ✅ | 95 | covered (HANDOFF originally deferred to WS4; reinstated as WS4 input-constraint doc — appropriate) |

All 9 PLAN items are first-class with ≥80 lines (gap-14 is 95). Mapping is real, not lossy. ✅

### 2.1 HANDOFF inventory accuracy

`wc -l docs/03-composition-design.md docs/03-gaps/*.md`:

```
423 03-composition-design.md
149 gap-01    136 gap-02    169 gap-03    65 gap-04    100 gap-05
 73 gap-06    170 gap-07    103 gap-08    75 gap-09    111 gap-10
171 gap-11    100 gap-12    202 gap-13    95 gap-14
2142 total
```

HANDOFF §7.2 table matches exactly. ✅

---

## 3. Findings (BLOCKER / MAJOR / MINOR / NIT)

No BLOCKER or MAJOR findings. All findings below are MINOR or NIT — they tighten cross-doc consistency without blocking WS4/WS5/WS6/WS7.

### 3.1 [MINOR] `recall_synthesis` verb is named but not enumerated for WS6

`03-composition-design.md:79–80` introduces the verb `recall_synthesis(uri | query)` as the S4a-targeted retrieval path. It is not listed in:
- `HANDOFF.md` §8.3 WS6 reading order, which enumerates `remember / recall / promote / forget / peer_message / peer_message_pull / peer_message_status`.
- The `mermaid` block in `03-composition-design.md:333` (`MCP server\n(remember / recall / promote / forget / peer_message)`).
- `03-composition-design.md:412–414` deferred-to-downstream list (which explicitly names verb signatures as WS6's deliverable).

**Effect on WS6 author:** they may overlook S4a retrieval altogether or assume `recall` itself spans S4a. **Fix:** one-line addition to HANDOFF §8.3 + the mermaid label. NIT-adjacent; flagged MINOR because it's a verb the API author can miss entirely.

### 3.2 [MINOR] Tenant-init "always-load" preference path has no read-path entry

`docs/03-gaps/gap-09-non-factual-memory.md:36` commits to MemGPT-style "always-load on tenant init" for `kind=preference` pages. The composition design's read-paths (§3.1–§3.4) describe `recall`, `recall_synthesis`, `peer_message_inbox`, and audit reads — but no tenant-init / context-bootstrap path. WS6 needs to know whether this is a per-call header injection, a session-start preload, or a separate verb.

**Effect on WS6 author:** ambiguity around how preferences enter agent context.
**Fix:** either add §3.5 "tenant-init bootstrap" to composition design, or have gap-09 §3 specify the mechanism (likely: implicit prepend on every `recall` response when `kind=preference` results exist for the tenant).

### 3.3 [MINOR] Latency budget is tight when intent classifier hits LLM residual

`03-composition-design.md:60` sets `recall` p95 ≤ ~250 ms.
`docs/03-gaps/gap-12-intent-classifier.md:85` sets the LLM-residual classifier path to "200 ms median." Median, not p95. If the residual LLM path's p95 is appreciably worse (likely), then total `recall` p95 = (intent p95) + (parallel retrieval) + (rerank) + (ledger write) blows the 250 ms budget on the LLM-residual branch.

**Effect:** WS4 must measure this stratified by classifier path; WS6 may need separate latency commitments for "heuristic-classified" vs. "LLM-classified" recalls.
**Fix:** composition §3.1 should explicitly say "p95 budget under heuristic-only classification; LLM-residual cases excluded or measured separately." gap-12 §7 already lists "latency budget" as a residual unknown — harmonize the two docs.

### 3.4 [MINOR] gap-14 §5(1) creates a chicken-and-egg at v1 launch

`docs/03-gaps/gap-14-eval-set-bias.md:65` commits the eval-set composition target to "30% operator (issue #1300, support traces sourced post-WS6)" — but at v1 launch there are by definition zero operators. The brief acknowledges this with "If WS4 cannot meet (1) at launch (operator data not yet available), it MUST clearly mark headline metrics as 'preliminary, author-share above threshold'" (line 74).

This is honest, but the WS4 author needs to know up-front that **v1.0 metrics will be tagged "preliminary" and the operator-derived slice will only fill in over time**. Worth surfacing in HANDOFF §8.1 reading order so the WS4 author plans for two reporting epochs (v1 launch / v1.x once operators exist) from day one.

**Fix:** one-sentence note in HANDOFF §8.1 or in gap-14 §5 step 1 making the launch-tag explicit. Not blocking.

### 3.5 [MINOR] gap-03 sum-to-1 constraint conflicts with consolidate-time defaults

`docs/03-gaps/gap-03-scoring-weights.md:138` (§6 step 2): "sum-to-1 constraint per tuple (normalized post-sample)."
`docs/03-gaps/gap-03-scoring-weights.md:74` (§4(a) consolidate-time defaults): α=0.2, β=0.3, γ=0.2, δ=0.4, ε=0.5 — sums to 1.6.

Whether ε is "in the tuple" (subtracted, so the constraint is on |α|+|β|+|γ|+|δ| only and ε is independent) is ambiguous. The recall-time tuple at §4(a) does sum to 1.0 (0.5+0.3+0.15+0.05+0.0). The consolidate-time form `score = α·... + β·... + γ·... + δ·... − ε·...` (§3) is consistent with ε being a *penalty multiplier* outside the convex combination.

**Effect on WS5:** the formalism author needs the sum-to-1 constraint disambiguated. Probably the intent is "sum-to-1 over positive contribution terms; ε is a separate penalty magnitude in [0, 1]" — if so, say it.
**Fix:** one-sentence clarification in gap-03 §6 step 2.

### 3.6 [NIT] Component diagram omits peer-message verb labels

`03-composition-design.md:333`: the `MCP server` node is labeled `(remember / recall / promote / forget / peer_message)`. `peer_message_pull` and `peer_message_status` (gap-10 §3) are not surfaced. The diagram's PEER node is labeled "Peer-message dispatcher" without verbs. Cosmetic; doesn't affect contract.

### 3.7 [NIT] Extension-tier briefs are inconsistently structured

The HANDOFF prescribes a uniform "what is the gap / why it matters / state of the art / candidate v1 approaches with trade-offs / recommendation + residual unknowns / touch-points" template. All 14 briefs hit those sections, but several extension-tier briefs (gap-04, gap-06, gap-09) compress the candidate-trade-off step into a single inline table without a separate "candidates with sketch+cost+failure-mode prose" subsection. The first-class briefs (gap-01, gap-02, gap-03, gap-07, gap-11) all use the longer prose-per-candidate form.

This is fine — extension tier is explicitly compact — but a reader skimming for a uniform shape will notice the asymmetry. Not a structural problem.

### 3.8 [NIT] Brief 04 minority-hypothesis attribution is slightly extended

`docs/02-lit-review/04-memory-as-metabolism.md:16` says "a lone contradiction gets quarantined" within the CONSOLIDATE operator description, and §3.1 (line 45) says "the safety story is partial." `docs/03-gaps/gap-11-forgetting-as-safety.md:29` cites brief 04 as proposing "minority-hypothesis retention plus three-timescale safety windows." The three-timescale framing is in brief 04 (line 23); the precise phrase "minority-hypothesis retention" is gap-11's reframing of "lone contradiction quarantined."

This is a fair extrapolation, not fabrication, but a strict reader could ask "where exactly does brief 04 say 'minority-hypothesis retention'?" — answer: it says the equivalent thing in different words. Acceptable; flag for awareness.

### 3.9 [NIT] HANDOFF §2.2 vs. §7.2 disposition for PLAN #7 and #9

`HANDOFF.md` §2.2 (the pre-WS3 setup section) said PLAN #7 (contradiction beyond LWW) was "committed by WS2" and PLAN #9 (eval-set bias) was "deferred to WS4," explicitly excluding both from WS3 slots. The post-WS3 update §7.2 then lists gap-13 (contradiction) and gap-14 (eval-set bias) as first-class WS3 deliverables.

This is a *deliberate* scope expansion (acknowledged by the user prompt and addressed by the prior QA), not an inconsistency. Worth noting in HANDOFF §7.2 with a one-line "scope expansion vs. §2.2 disposition" callout so future readers don't see the §2.2 claim and assume gap-13/gap-14 don't exist.

---

## 4. Per-rubric findings

### 4.1 Composition design rigor (criterion #5 — CRITICAL)

- **Does it punt on consistency?** No. `03-composition-design.md` §5 is a per-store table with explicit "required guarantee / why sufficient / crash recovery" columns. §5.1 enumerates the non-ACID assumptions explicitly. Score: **5**.
- **Failure-mode matrix coverage:** §7 has 14 rows; §7.1 covers two-stores-down combinations (S1+S3, S2+S5, S1+S4). Each row has Detection / Effect-on-remember / Effect-on-recall / Mitigation. Peer-message corruption (row 9) is the most carefully treated and links to gap-05 / gap-10 / gap-11. Score: **5**.
- **Recommendation rationale traceable to charter + synthesis:** §8.3 cites charter §3 (markdown commitment), synthesis §2.8 (markdown-vs-graph tension), and brief 17 (qmd reference impl) for the dividing-line argument. Not asserted; derived. Score: **5**.

### 4.2 WS4-readiness (eval author — criterion #6)

- ✅ **Eval-signal definitions per gap.** gap-01 §3.2 (4 signals), gap-02 §4 (eval-signal column on every candidate), gap-03 §4 (per-candidate eval signal), gap-06 §4 (4-candidate table includes eval signals), gap-12 §7 (residual unknowns include classifier-accuracy target), gap-13 §4 (four detection signals with healthy/break-point thresholds).
- ✅ **Bias hazards owned.** gap-14 §1 enumerates 5 hazards; §3 has the 6-source taxonomy.
- ✅ **Retrospective annotation protocol.** gap-14 §5(1) commits target shares; gap-01 §4(b) eval signal references "retrospectively-annotated SCNS task set (per gap-14)." Coupled correctly.
- ✅ **Benchmark applicability.** gap-03 §6 step 1 fixes LongMemEval primary, LoCoMo secondary, SCNS-native held-out (gap-14) — consistent with synthesis and HANDOFF §2.3.
- ⚠️ One missing piece: a **single index** of "all eval signals across all gaps" would save the WS4 author a search. HANDOFF §8.1 partly fills this but gap-by-gap. NIT.

**WS4-readiness score: 5.** WS4 author can start without re-research; finding 3.4 above (operator-data chicken-and-egg) is the only thing they should know about up-front.

### 4.3 WS5-readiness (scoring author — criterion #7)

- ✅ **Scoring-weight calibration protocol.** gap-03 §6 is publishable.
- ✅ **Utility-feedback observation mechanism.** gap-02 §3 (signal taxonomy) + §4 (candidate (c) hybrid path) + §5 (recommendation) is concrete, not aspirational. Per-signal weights pinned (citation 0.4 / tool 0.7 / correction 1.0 / repeat 0.1 / no-op −0.2).
- ✅ **Candidate scoring math collected.** gap-03 §3 has both formulas in one place: consolidate-time `score(fact)` (5 terms) and recall-time `recall_score(fact, query)` (5 terms). gap-01 §4(b) references the same form. Consistent.
- ✅ **Relationship to retention/promotion engine.** gap-01 §3.2 makes gap-02's signal the δ-term in gap-01 candidate (b)'s score. Without gap-02, gap-01 collapses to candidate (a). Coupling is explicit.
- ⚠️ Finding 3.5 (sum-to-1 ambiguity on consolidate tuple) is the one thing WS5 will hit immediately.

**WS5-readiness score: 5 (with the §3.5 nit).** WS5 author can start without re-research.

### 4.4 WS6-readiness (API author — criterion #8)

- ✅ Store-call routing per verb: composition §3 (read paths) + §4 (write paths) is verb-by-verb.
- ✅ Write-path semantics: §4.1 (`remember`), §4.2 (`promote`/`forget`), §4.3 (`peer_message`), §4.4 (`consolidate`).
- ✅ Idempotency rules: gap-08 §3.1, §3.2 — caller-supplied UUID, 24h TTL, retry-safe.
- ✅ Error model: composition §7 + gap-04 §6 (409 retry on CAS).
- ⚠️ Finding 3.1 (missing `recall_synthesis` in HANDOFF list).
- ⚠️ Finding 3.2 (preference-load mechanism missing from read paths).
- ⚠️ Finding 3.3 (latency budget tight on LLM-classifier path).

**WS6-readiness score: 4.5.** Three minor findings to harmonize but no blocker.

### 4.5 WS7-readiness (migration author — criterion #9)

- ✅ SCNS→Lethe data mapping: HANDOFF §8.4 + gap-09 §7 (CLAUDE.md → preferences; SCNS synthesis → narratives), gap-13 §8 (SCNS LWW data → bi-temporal re-stamp), gap-04 §6 (broker-DB row-locking → CAS), gap-11 §8 (archive-store → invalidate).
- ✅ Rollback gates: gap-08 §3.5 (`lethe-audit lint --integrity` is a phase-gate); composition §7 row "schema migration" specifies drain + lock + run + release.
- ✅ Soak-period definition: covered by PLAN.md WS7 itself; composition §11 + various gap "post-launch" residual-unknowns frame the cadence. Adequate at this level.

**WS7-readiness score: 5.**

---

## 5. Evidence spot-checks (criterion #4)

Five citations checked against the cited briefs. All verified:

1. **gap-11 §2** cites brief 04 §3.1 for "safety story is partial." Brief 04 line 45: "Does not eliminate the reinforcement of user-held bad beliefs. The paper is emphatic that the safety story is partial." ✅ Accurate.

2. **gap-03 §4(a)** uses RRF `k=60` attributed to "qmd / Cormack default." Brief 17 line 33: "Exact RRF constant and LLM-reranker model are repo-readable but not surfaced in the README." gap-03 explicitly calls this out as the *Cormack* default with qmd as a gesture, not as a qmd-published number. ✅ Honest attribution.

3. **gap-01 §2** cites brief 14 for "Graphiti ships no decay or unlearn algorithms." Brief 14 line 15: "Graphiti has no decay, no eviction, no demotion engine — this brief + brief 12 + the Graphiti README together establish that fact." ✅ Accurate.

4. **gap-07 §2** cites brief 21 for "~100 sources, ~hundreds of pages" and "10–15 pages per source." Brief 21 line 19: "At moderate scale (~100 sources, ~hundreds of pages) this works without embeddings." Line 22: "A single source can touch 10–15 wiki pages." ✅ Accurate.

5. **gap-13 §2** cites brief 12 for "Native `valid_from / valid_to` on every edge" and bi-temporal `recorded_at`. Cross-checked against the composition design's Graphiti row (`03-composition-design.md:32`): "Bi-temporal facts: typed entity nodes, typed edges with `(valid_from, valid_to, recorded_at)`." ✅ Internally consistent.

No fabrications detected. The minor extrapolation in finding 3.8 is the only item where wording is reinterpreted, and it's a reasonable rephrasing.

---

## 6. Cross-doc consistency (criterion #10)

Verified:
- Composition §2 ownership matrix vs. gap briefs:
  - gap-10 places peer-message inbox in S2 — matches composition §2 S2 row "operational ledger." ✅
  - gap-11 places retention proof in S5 — matches composition §2 S5 row "consolidation log; append-only." ✅
  - gap-09 places preferences/procedures/narratives in S4a typed pages — matches composition §2.1 S4a definition. ✅
  - gap-01 promotion-flag write to S2 — matches composition §4.2 T2 spec. ✅
- gap-11 + gap-13 both consume bi-temporal `valid_to`; semantics consistent.
- gap-04 idempotency-key contract (§5) + gap-08 §3.1 idempotency-key contract — both 24h TTL, both UUID-keyed. ✅
- gap-04 inbox-cap-100 + gap-10 §3.4 inbox-cap-100. ✅

Inconsistencies: only the three minor findings 3.1 / 3.2 / 3.5.

---

## 7. Verdict

**APPROVE-WITH-NITS.**

WS3 substantively satisfies the lens. A WS4 author starting from `gap-14` + `gap-12` + `gap-06 §3` + `gap-01 §6` + `composition §7` has everything they need to draft `04-eval-plan.md` without re-research. A WS5 author starting from `gap-03 §3 + §6` + `gap-02 §3 + §5` + `gap-01 §4(b)` has both the form and the protocol. WS6 and WS7 are also adequately served (`composition §3–§7` + the per-verb pointers in `gap-04`/`gap-08`/`gap-10`/`gap-11`/`gap-12`).

### Recommended fixes before WS4/WS5 begin

Authoritative fix list for the WS3 author (or a small follow-up commit). None block WS4/WS5 from starting; addressing them tightens the handoff:

1. **[3.1]** Add `recall_synthesis` to HANDOFF §8.3 WS6 verb list and to the mermaid diagram label in `03-composition-design.md:333`.
2. **[3.2]** Specify the always-load preference mechanism — add §3.5 "tenant-init bootstrap" to composition design, or have `gap-09 §3` name the mechanism (recommended: implicit prepend of `kind=preference` synthesis pages onto every `recall` response, capped per gap-09 §6 "always-load bandwidth"). Either way, WS6 needs an unambiguous read-path entry.
3. **[3.3]** In `03-composition-design.md` §3.1, qualify the p95 ≤ 250 ms budget as "under heuristic-only classification; LLM-residual recall p95 measured separately." Cross-link to `gap-12 §7` latency-budget unknown.
4. **[3.4]** One-sentence note in HANDOFF §8.1 making explicit that v1.0 eval reports will be tagged "preliminary, author-share above threshold" until operator data accumulates.
5. **[3.5]** In `gap-03 §6` step 2, disambiguate the sum-to-1 constraint: "sum-to-1 over the four positive contribution weights (α, β, γ, δ); ε is a separate penalty magnitude in [0, 1]."
6. **[3.6]** (NIT) Update the mermaid component diagram to include `peer_message_pull / peer_message_status` on the MCP server label.
7. **[3.9]** (NIT) In HANDOFF §7.2, add a one-line "scope-expansion vs. §2.2 disposition" callout for gap-13 + gap-14.

### What WS3 got right (worth preserving)

- The five-store decomposition with explicit "owns / derives from / does NOT own" columns (`03-composition-design.md` §2) is the single most useful artifact for downstream authors.
- Per-store ACID rationale (§5 table) is the answer to the user prompt's "do NOT punt on consistency" instruction. It does not punt; it commits per boundary with rationale.
- Failure-mode matrix (§7) including the two-down combination matrix (§7.1) is the level of rigor WS6 / WS7 need.
- gap-13's framing as "committed→monitored, with detection signals" rather than re-litigating the WS2 decision is exactly the right move.
- gap-14 hands WS4 a constraint document, not an eval design — the right scope split.
- Cross-references between briefs are dense and bidirectional; the "Open seams handed to gap briefs" table at `03-composition-design.md:389–404` is the single best navigation aid in the WS3 corpus.

WS3 is closed. WS4 and WS5 can proceed.
