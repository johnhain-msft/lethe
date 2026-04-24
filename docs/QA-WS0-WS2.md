# WS0–WS2 Foundation QA Report

**Reviewer:** fresh QA agent (session `8901ef6a`)
**Date:** 2026-04-23
**Scope:** every doc under `docs/` in `lethe` repo @ `efa2069`, plus root `PLAN.md`.
**Critical lens:** "can WS3 (gap deep-dives + composition design) proceed without re-doing research?"

---

## 1. Headline verdict

**APPROVE-WITH-NITS** — with **one MAJOR** finding that must be reconciled before WS3 kicks off. The foundation is substantively strong: templates adhered to, evidence grounded, synthesis real (not filler), and committed design decisions are defensible and explicit. But the synthesis silently **dropped three of the nine WS3 Track-B gap deep-dives that PLAN.md §WS3 explicitly mandates** (peer messaging, intent classifier, forgetting-as-safety). A WS3 author who reads `HANDOFF.md` §2.2 and not `PLAN.md` §WS3 will miss them. Fix is small (reconcile the gap lists or justify the drops); research is not wasted.

---

## 2. Per-document scores (1–5 each criterion)

| Doc | Completeness | Substance | Evidence | Template | Cross-doc | WS3-readiness | Notes |
|---|---|---|---|---|---|---|---|
| `PLAN.md` | 5 | 5 | — | — | — | — | Source of truth |
| `00-charter.md` | 5 | 5 | 5 | n/a | 5 | 5 | Clean; mission, positioning, scope, license rationale all substantive |
| `01-scns-memory-audit.md` | 5 | 5 | 5 | n/a | 5 | 5 | Exhaustive; 18 memory modules + observe path + broker tables + FS layout + classification + diagram |
| `01b-dream-daemon-design-note.md` | 5 | 5 | 5 | n/a | 5 | 5 | Per-module verdict + MaM/MAGMA mapping + transition plan |
| `02-lit-review/01-zep.md` | 4 | 4 | 5 | 5 | 5 | 4 | Abstract-bound (acknowledged); claims all verify |
| `02-lit-review/02-magma.md` | 5 | 5 | 4 | 5 | 5 | 5 | Deepest technical brief; four-subspace math captured |
| `02-lit-review/03-shibui-magma-guide.md` | 2 | 2 | n/a | partial | 4 | 2 | Unreachable; honestly declared; logged in synthesis §4 |
| `02-lit-review/04-memory-as-metabolism.md` | 5 | 5 | 4 | 5 | 5 | 5 | Richest substrate for forgetting-as-safety and scoring |
| `02-lit-review/05-cognitive-weave.md` | 4 | 4 | 4 | 5 | 5 | 4 | Scoring math acknowledged as living past fetched section |
| `02-lit-review/06-paper-list.md` | 5 | 4 | 4 | 5 | 5 | 4 | Good gap-hunting pointer list |
| `02-lit-review/07-memos.md` | 3 | 3 | 4 | 5 | 4 | 3 | Abstract-only, acknowledged; thin on scoring/API |
| `02-lit-review/08-hipporag.md` | 4 | 4 | 5 | 5 | 4 | 4 | PPR claim spot-checked and verified |
| `02-lit-review/09-a-mem.md` | 3 | 3 | 4 | 5 | 4 | 3 | Abstract-bound; scoring math "not in abstract" |
| `02-lit-review/10-memevolve.md` | 4 | 4 | 4 | 5 | 5 | 5 | Four-verb API mapping is the cleanest in the set |
| `02-lit-review/11-memgpt.md` | 5 | 5 | 4 | 5 | 5 | 5 | Function-call surface enumerated |
| `02-lit-review/12-graphiti.md` | 5 | 5 | 5 | 5 | 5 | 5 | Anchor brief; README claims all verify |
| `02-lit-review/13-graphiti-mcp.md` | 3 | 3 | 4 | 5 | 5 | 3 | Honestly disclosed as a mirror; tool inventory deferred to `mcp_server/README.md` (not fetched) |
| `02-lit-review/14-graphiti-issue-1300.md` | 5 | 5 | 5 | 5 | 5 | 5 | Issue text verified verbatim |
| `02-lit-review/15-letta.md` | 5 | 5 | 4 | 5 | 5 | 5 | Policy ladder captured; operational validation flagged as follow-up |
| `02-lit-review/16-ms-agent-framework.md` | 5 | 4 | 4 | 5 | 5 | 4 | Strategic framing; provider contract captured |
| `02-lit-review/17-qmd.md` | 5 | 5 | 5 | 5 | 5 | 5 | README text verifies verbatim |
| `02-lit-review/18-longmemeval.md` | 5 | 5 | 5 | 5 | 5 | 5 | Abstract numbers all verify |
| `02-lit-review/19-locomo.md` | 4 | 4 | 4 | 5 | 5 | 4 | LoCoMo-Plus noted; human-eval caveats explicit |
| `02-lit-review/20-dmr.md` | 4 | 4 | 4 | 5 | 5 | 4 | Ceiling-effect framing is the useful content |
| `02-lit-review/21-karpathy-wiki.md` | 5 | 5 | 5 | 5 | 5 | 5 | Explicit-limits table → Lethe-requirement table is the model per-brief synthesis |
| `02-synthesis.md` | 4 | 5 | 5 | n/a | 5 | **3** | Substantively strong; **but gap-slot list drifts from PLAN.md WS3 Track B — see §3.1** |
| `HANDOFF.md` | 4 | 5 | 5 | n/a | 4 | **3** | Inherits synthesis's WS3-slot list; same drift |

---

## 3. Findings by severity

### 3.1 MAJOR — WS3 gap-brief list drifts from PLAN.md §WS3 Track B

**Where:** `docs/02-synthesis.md` §5 (lines 160–173) and `docs/HANDOFF.md` §2.2 (lines 87–102).

**Evidence.** `PLAN.md` §WS3 (lines 151–160) enumerates **nine** prioritized gap deep-dives:
1. utility-feedback capture
2. scoring weight calibration
3. markdown at scale
4. unattended consolidation
5. cross-agent peer messaging
6. forgetting-as-safety
7. contradiction resolution beyond timestamp invalidation
8. intent classifier design
9. eval-set construction without confirmation bias

`HANDOFF.md` §2.2 (the authoritative WS3 kickoff table) lists **eight** slots. Mapping PLAN→HANDOFF:

| PLAN # | PLAN topic | HANDOFF slot | Status |
|---|---|---|---|
| 1 | utility feedback | gap-02 | ✅ |
| 2 | scoring weights | gap-03 | ✅ |
| 3 | markdown at scale | partially gap-07 (markdown-as-view vs graph-as-source) | ⚠️ reframed to authority question; scale/concurrency/write-amp dimension not carved out |
| 4 | unattended consolidation | gap-01 (retention engine) | ✅ absorbed |
| 5 | cross-agent peer messaging | **none** | ❌ dropped |
| 6 | forgetting-as-safety | **none** | ❌ dropped |
| 7 | contradiction resolution | — | ✅ already settled as committed decision (HANDOFF §2.3: "bi-temporal invalidate, don't delete") |
| 8 | intent classifier | **none** | ❌ dropped |
| 9 | eval-set bias | WS4 per HANDOFF §2.2 | ✅ explicitly deferred with justification |

Four **new** gap slots were added that PLAN did not list: provenance enforcement (§3.5), extraction-quality instrumentation (§3.7), markdown-vs-graph authority (§3.8, absorbing part of #3), crash-safety (§3.10). These are defensible extensions — PLAN.md §WS2 explicitly invited this. The problem is not the additions; it is the **silent deletions** of PLAN items #5, #6, and #8.

- **peer messaging (PLAN #5)** — synthesis §2.4 covers "cross-agent / multi-tenant" but conflates concurrency-of-writes with peer-messaging ("I learned X — here's the provenance"). PLAN.md calls this out explicitly (PLAN.md line 67: "Lethe's audience is *agents talking to each other* — can't defer this as casually as the PDF does"). Charter §4.1 commits to `peer_message` as a core API verb. A WS3 author needs a dedicated slot or an explicit deferral with rationale.
- **forgetting-as-safety (PLAN #6)** — PLAN.md line 68: "Lethe is *named* for it. Must engage." Memory-as-Metabolism brief 04 supplies strong substrate (§3.1: "safety story is partial"; minority-hypothesis retention; three-timescale safety). Synthesis mentions the phrase nowhere. Given the name of the project this is a surprising omission.
- **intent classifier (PLAN #8)** — MAGMA brief 02 supplies direct substrate (`{Why, When, Entity}` taxonomy + routed traversal). Charter §4.1 commits to "intent-aware retrieval routing." No WS3 slot.

**Impact on the critical lens.** A WS3 agent reading `HANDOFF.md` §2.2 will have 8 gap-brief slots to execute. To discover that three PLAN-mandated gaps are missing, they must independently diff HANDOFF against PLAN. Substrate exists in the briefs (04, 02, 15, 16) so research is not wasted — but the WS3 author has to re-surface it themselves. That's navigation overhead, not re-research; hence MAJOR not BLOCKER.

**Fix suggestion (do NOT apply — QA-only).** Either:
(a) **add three gap-brief slots to `HANDOFF.md` §2.2**:
  - `gap-10: cross-agent peer messaging` — substrate: briefs 15 (Letta shared blocks + punt), 16 (MS AF no primitive), synthesis §2.4, charter §4.1 `peer_message` commitment.
  - `gap-11: forgetting-as-safety` — substrate: brief 04 Memory-as-Metabolism §3.1 and §"documented limits"; connects to charter §1 "river of forgetting" framing.
  - `gap-12: intent classifier` — substrate: brief 02 MAGMA router; brief 16 MS AF absence; charter §4.1 "intent-aware retrieval routing."
(b) OR **amend `02-synthesis.md` §5 and `HANDOFF.md` §2.2** with an explicit "Reclassified / deferred gaps" subtable that lists PLAN #5/#6/#8 and records where they were folded (e.g., peer-messaging folded into gap-04 concurrency; forgetting-as-safety is gap-01's framing; intent classifier deferred to WS6 API design) with rationale.

Option (a) is safer — the substrate supports it cheaply.

---

### 3.2 MAJOR — PLAN gap #3 ("markdown at scale") reframed, scale/concurrency dimension narrowed

**Where:** `docs/02-synthesis.md` §3.8 maps PLAN #3 → "markdown-as-view vs graph-as-source-of-truth" (authority question). That is a real and valuable question, and the synthesis answers it (markdown = view, graph = source). But PLAN.md §WS3 #3 specifically enumerates **scale** concerns: "write amplification, concurrent writes from multi-agent swarm, crash consistency, retrieval cost >10k pages." Only crash consistency survives as its own slot (gap-08 crash-safety). Write amplification, concurrent-writes-from-swarm, and retrieval cost >10k are not carved out. Karpathy's 100-source ceiling (brief 21) is cited but not operationalized as a WS3 deep-dive.

**Fix suggestion.** Either add `gap-13: markdown scale / write-amp / retrieval >10k` or broaden gap-07 explicitly to include the scale dimensions from PLAN #3.

---

### 3.3 MINOR — brief 13 (Graphiti MCP) is a near-duplicate of brief 12

**Where:** `docs/02-lit-review/13-graphiti-mcp.md` §"Fetch status" (lines 5–8).

**Finding.** Brief 13 honestly declares that the klaviyo URL in PLAN is a mirror of `getzep/graphiti`, and defers to brief 12. PLAN.md listed these as separate rows. The brief is honest but ~60 % of its content is cross-references. The substantive gap — the `mcp_server/README.md` with the actual tool inventory — is not fetched (HANDOFF §4 item 4 confirms). For WS6 API design this is a real hole; for WS3 composition it is tolerable.

**Fix suggestion.** HANDOFF §4 already names this. No change required at WS3 kickoff; note is sufficient.

---

### 3.4 MINOR — abstract-only briefs (07 MemOS, 09 A-MEM) are thin on scoring + API

**Where:** briefs 07 (lines 19–23) and 09 (lines 22–26).

**Finding.** Each brief explicitly says "not in the fetched abstract" for scoring math and API surface. This is honest non-fabrication (per convention §3.2), not filler. But for WS3 gap-03 (scoring weights) and any future scoring-synthesis, the A-MEM link-quality story and the MemCube addressing primitives would be useful. Depth deferred, not destroyed.

**Fix suggestion.** Optional: fetch paper HTML for §3–§5 of each, add a one-paragraph addendum. Not WS3-blocking.

---

### 3.5 MINOR — brief 04 Memory-as-Metabolism is dated-forward (arXiv 2604.12034)

**Where:** `docs/02-lit-review/04-memory-as-metabolism.md` line 4 ("April 2026, v3.642").

**Finding.** arXiv ID 2604.12034 corresponds to an April 2026 submission. Given the session date of 2026-04-23 this is plausibly current but I could not spot-verify (arXiv link not fetched in this QA because the key findings are qualitative). The paper ID pattern is consistent with other 26xx refs used across briefs (02 MAGMA 2601.03236, 19 LoCoMo-Plus 2602.10715). Internally consistent; no evidence of fabrication.

**Fix suggestion.** None; flagged for transparency only.

---

### 3.6 MINOR — brief 14 (#1300) author attribution slightly off

**Where:** `docs/02-lit-review/14-graphiti-issue-1300.md` line 5 ("Filed: 2026-03-05 by `teekoo5` (Skene Growth bot-agent, external to getzep)").

**Finding.** Fetched issue page shows the filing is attributed to "Skene Growth" (the product) with no user handle surfaced in the rendered comment body. "teekoo5" as the GitHub username could not be confirmed from the rendered page alone. Impact: zero on the brief's substantive claim (Graphiti lacks decay algorithms — fully verified). Username detail is unnecessary for the argument and is attributable to cached metadata the reviewer saw but I did not confirm.

**Fix suggestion.** Drop the specific username; keep "Skene Growth bot-agent" attribution.

---

### 3.7 NIT — SCNS memory audit counts modules as "18," PLAN.md §WS1 said "17"

**Where:** `PLAN.md` line 88 vs `docs/01-scns-memory-audit.md` §1 title.

**Finding.** Counting difference, not a substantive gap. Audit table lists actual modules; PLAN estimate was approximate.

**Fix suggestion.** None.

---

### 3.8 NIT — synthesis §4 says "briefs 14–20 all fetched cleanly" — `docs/HANDOFF.md` §4 item 4 says Graphiti `mcp_server/README.md` was not fetched

**Where:** `docs/02-synthesis.md` lines 148–150 vs `HANDOFF.md` line 181.

**Finding.** The synthesis statement is technically about the 21 primary URLs; the `mcp_server/README.md` is a *secondary* URL referenced from brief 13. Not a contradiction, just imprecise. HANDOFF catches it honestly.

**Fix suggestion.** None.

---

## 4. WS3-readiness assessment per PLAN gap

Using the critical lens verbatim.

| PLAN #WS3 gap | Substrate present? | WS3 slot exists? | WS3 author can start? |
|---|---|---|---|
| 1 utility feedback | Yes — briefs 01, 02, 04, 15; audit §3.3 (quality_checks) | gap-02 | ✅ |
| 2 scoring weights | Yes — briefs 01, 04, 05, 08, 12, 17; synthesis §2.3 | gap-03 | ✅ |
| 3 markdown at scale | Partial — brief 21 scale ceiling; synthesis §2.8 focuses on authority, not scale | partial (gap-07 + gap-08) | ⚠️ WS3 author must re-derive scale scope |
| 4 unattended consolidation | Yes — dream-daemon note; briefs 04, 15 | gap-01 | ✅ |
| 5 peer messaging | Partial — briefs 15, 16; charter commitment | **NO** | ❌ needs slot |
| 6 forgetting-as-safety | Strong — brief 04 whole paper is about this | **NO** | ❌ needs slot |
| 7 contradiction resolution | Yes — committed (HANDOFF §2.3) | n/a (committed) | ✅ |
| 8 intent classifier | Yes — brief 02 MAGMA; charter | **NO** | ❌ needs slot |
| 9 eval-set bias | Yes — briefs 18–20; deferred to WS4 | WS4 | ✅ |

**Track A (composition design):** Charter §3, synthesis §1, and the dream-daemon note §3 together supply substrate for the composition-design deliverable. Candidate topologies are not explicitly enumerated as "A / B / C" in one place, but Graphiti-as-substrate + markdown-as-view is committed, and the two-stream-vs-one-stream question is flagged as open (dream-note §3.2 + §4 open question #1). Store boundaries are discussed (audit §1, note §3.2 table); consistency models are committed at the bi-temporal level (HANDOFF §2.3). WS3 Track A has enough to start.

---

## 5. Evidence grounding — random spot-checks

Five briefs spot-checked against primary URLs via `web_fetch`:

| Brief | Claim sampled | URL | Verified? |
|---|---|---|---|
| 01 Zep | 94.8 vs 93.4 DMR; +18.5 % LongMemEval; 90 % latency reduction; 12 p / 3 tables | arXiv:2501.13956 abstract | ✅ exact match |
| 08 HippoRAG | NeurIPS 2024, up to +20 %, 10–30× cheaper, 6–13× faster, PPR | arXiv:2405.14831 abstract | ✅ exact match |
| 14 #1300 | Skene Growth bot filing, node-decay proposal, Graphiti lacks temporal decay | GitHub issue page | ✅ content verbatim (username caveat, §3.6) |
| 17 QMD | Install, CLI verbs, MCP tool set (query/get/multi_get), context-tree distinctive feature | `github.com/tobi/qmd` README | ✅ verbatim |
| 18 LongMemEval | five abilities, 500 questions, 30 % drop, ICLR 2025 | arXiv:2410.10813 abstract | ✅ numbers match; brief doesn't cite ICLR 2025 publication venue (NIT) |

No fabrication detected across spot-checks. Confidence in evidence grounding: **high**.

---

## 6. Template adherence

All 21 briefs structurally follow the 8-section template per HANDOFF §3.2. Brief 03 (Shibui) is an exception: it carries the sections as headers but marks each "Not retrievable" — allowed by the "never fabricate" rule and acknowledged in synthesis §4. All other briefs fill each section with real content, even when the fetched material was thin (honest "not in fetched abstract" entries). No empty sections, no filler.

---

## 7. Cross-doc consistency

- **Synthesis ↔ lit-review briefs.** Synthesis §1 and §2 each claim cross-brief convergences. Ten spot-checks of the form "synthesis says X; does brief Y support it?" all landed. §1.3 (async consolidation) cites MAGMA + Letta + MaM + SCNS + Cognitive Weave + A-MEM + HippoRAG — each of those briefs does support the claim.
- **Audit ↔ dream-daemon note.** Audit §6 tags `dream/*` as candidate-for-lethe; note §4 gives per-module dispositions. Consistent; note clearly dominant for dream specifics.
- **Charter ↔ synthesis ↔ HANDOFF.** Committed decisions in HANDOFF §2.3 all trace to synthesis §3 or the charter. `remember/recall/promote/forget` → charter §4.1 → brief 10 `encode/store/retrieve/manage`. LongMemEval primary → brief 18 → synthesis §1.6. Graphiti substrate → synthesis §5 → briefs 12/14.
- **PLAN ↔ HANDOFF.** Diverges on WS3 gap list (finding §3.1 above). Otherwise consistent.

---

## 8. Known gaps escalation check

Synthesis §2 enumerates **twelve** field gaps; PLAN.md preamble enumerates ~17 gaps + hand-waves (Karpathy × 8 + PDF × 9). Coverage overlap:

- Scale (Karpathy) → synthesis §2.8 partial (authority only, not scale).
- Single-user assumption → synthesis §2.4 concurrency.
- Consolidation is human-driven → synthesis §2.1 retention engine + §3.1.
- Contradiction handling informal → synthesis §1.2 (settled) + §2.5 (provenance).
- Provenance → synthesis §2.5 + §3.5. ✅
- Privacy/secret sanitization → **not addressed in synthesis**; audit §2 flags the SCNS pipeline as candidate-for-lethe but synthesis doesn't carry it forward. Minor gap.
- ACID/durability → synthesis §2.12 + §3.10. ✅
- Write amplification → not addressed in synthesis (folds into dropped PLAN #3 scale scope).
- Utility feedback → synthesis §2.2 + §3.2. ✅
- Scoring-weights ratio → synthesis §2.3 + §3.3. ✅
- Promotion criteria → synthesis §3.1 (retention engine). ✅
- Contradiction resolution beyond recency → synthesis §1.2 settled. ✅
- Intent classifier → **dropped** (finding §3.1).
- Peer messaging → **dropped** (finding §3.1).
- Forgetting-as-safety → **dropped** (finding §3.1).
- Benchmark applicability → synthesis §1.6 + §2.6 cost dim + briefs 18/19/20. ✅
- Eval-set construction → deferred to WS4 with WS3 mention. ✅

Synthesis **did** extend the list with new gaps: extraction-quality instrumentation (§2.7), non-factual memory (§2.9), parametric memory (§2.10), ontology evolution (§2.11). These are meaningful additions. But the 3 silent drops + the privacy gap + the write-amp gap add up to five known PLAN concerns that either disappeared or were narrowed.

---

## 9. Verdict

**APPROVE-WITH-NITS** — with two conditions that should be cleared before WS3 starts:

1. **(MANDATORY)** Reconcile HANDOFF §2.2 with PLAN.md §WS3 Track B. Either add gap slots for peer messaging, forgetting-as-safety, and intent classifier (recommended — substrate exists in briefs 02/04/15/16), or add an explicit "deferred / reclassified" subtable with rationale. See finding §3.1.
2. **(RECOMMENDED)** Broaden gap-07 or add a dedicated slot for PLAN #3's scale dimension (write amplification, concurrent-writes-from-swarm, retrieval >10k). See finding §3.2.

Everything else is NIT or MINOR and does not block WS3 from starting. Template discipline, evidence grounding, and synthesis substance are all strong. The dream-daemon design note in particular is unusually high-quality for a WS1 artifact — it is already doing WS3 work for the consolidation gap, which is why that gap is the most WS3-ready of the nine.

**Signed off on the understanding that the two conditions are addressed in a single follow-up commit before the first WS3 gap-brief lands.**
