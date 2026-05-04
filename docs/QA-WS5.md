# WS5 QA — Scoring Formalism (fresh-eyes review)

**Reviewer:** WS5-QA (cold pass, no exposure to WS5 implementation session).
**Artifacts under review:** `docs/05-scoring-design.md` (600 lines, commit `e0f0705`); `docs/HANDOFF.md` §11 (commit `4e1437a`).
**Reading order followed:** HANDOFF §11 → `05-scoring-design.md` start-to-finish → spot-checks on gap-03 §5, gap-09 §3, gap-12 §3, `metrics/emitter.py` → SCNS-independence grep audit.

---

## 1. Verdict

**APPROVE-WITH-NITS.**

WS5 gives a WS6 (API) author and a WS7 (migration) author enough scoring substrate to start without re-research. All six anti-checklist items in HANDOFF §11.4 are respected. Zero residual SCNS dependency in calibration sources, baselines, or training data. Two minor internal inconsistencies (numbered nits below) are doc-hygiene only and do not block downstream workstreams.

Headline answer to the gating question: **YES** — `docs/05-scoring-design.md` is precise enough that (a) WS6 can begin implementing `recall(query)` against §4 + §6.1 and `emit_score_event(event)` against §8.2/§8.4 without re-deriving the math, and (b) WS7 can plan migration choreography knowing that scoring is two-surface, RRF-anchored at recall-time, and additive at consolidate-time with an explicit demotion-floor multiplier.

---

## 2. Scoring rubric

| § | Score | One-line rationale |
|---|---|---|
| §0 Frame | 5/5 | States Lethe-stands-alone explicitly (line 6); enumerates WS5-owns vs out-of-scope (lines 12–21). |
| §1 Two scoring surfaces | 5/5 | Both surfaces formalized, weight-tuple independence is named (line 34) as the v1.0→v1.1 risk. |
| §2 Symbols/units | 5/5 | Domain, unit, source store, and origin column for every symbol (lines 40–60); normalization range stated (line 62). |
| §3 v1 consolidate-time heuristic | 5/5 | All 6 named terms have explicit formulas (recency Cognitive Weave residual, PPR with 2-hop cap and degree-percentile fallback, gap-02 weighted aggregate with per-event table, type-priority lookup table, log-dampened ε, gravity-as-multiplier). Composed formula matches plan exactly. |
| §4 v1 recall-time heuristic | 5/5 | Filter→RRF(k=60)→intent multiplicative bonus→utility additive ramp; ordering matches Q2 resolution; no weighted-sum trace. |
| §5 per-class dispatch | 4/5 | Exhaustive over 4 persistent shapes; explicit β=0 for preference, τ_r=180d for procedure, `recall_synthesis` for narrative; non-persistent classes flagged out-of-scope. **Nit N1** below: §5.4 says narrative is added to §3.4 at 0.50 — but §3.4 table is not actually updated. |
| §6 bi-temporal invalidation | 5/5 | All 5 sub-rules present: recall-floor, gravity zeroed, T_purge=90d grace, utility-tally freeze with revalidate-replay (§6.4), log-dampened ε amplification (§6.5). |
| §7 tuning-knob table | 5/5 | Every knob has Default | Range | Calibration source | Eval signal (eval-plan §6 phase + §5 metric) | Trigger. Every calibration source is LongMemEval / LoCoMo / DMR / Lethe opt-in trace — zero foreign-system rows. Closing line (line 369) makes this verifiable. |
| §8 v2 log-signal contract | 5/5 | All 7 event types listed; envelope carries `event_id`, `tenant_id`, `ts_recorded`, `ts_valid`, `model_version`, `weights_version`, `contamination_protected`, `score_inputs`, `score_output`, `decision`, `outcome`, `provenance`. Replayability invariant stated (§8.3). `emit_score_event` sink contract is precise (input schema, contamination gate, on-disk layout). v2 entry criteria gate both ≥20% operator share AND ≥10k labeled pairs (§8.6). |
| §9 v1→v2 transition | 5/5 | Clean separation of what is learned (5 consolidate weights + 2 recall tunables + 4 per-class deltas) vs what stays heuristic (dispatch, invalidation semantics, gravity behavior, RRF shape). |
| §10 residual unknowns | 4/5 | Five honest items. **Nit N2** below: Appendix A.1 cites "residual unknown #1" for the procedure `type_priority = 0.55` placeholder, but §10 #1 is θ_promote drift — the cross-ref is wrong. |
| §11 traceability matrix | 5/5 | All 7 inputs mapped to specific §s. Lit-review carries (Cognitive Weave / MaM / Zep / MAGMA) also mapped. |
| Appendix A worked example | 5/5 | Three artifacts (preference, episodic, contradicted procedure) computed through both surfaces with arithmetic shown. Demonstrates the intent multiplicative bonus correctly lifting `f_pref` over a graph-rank-1 `f_fact`. |

**Q1–Q4 honored:**

| Question | Resolution required | Verified at |
|---|---|---|
| Q1: gravity = demotion-floor (not 6th additive term)? | YES | §3.6 lines 155–170; the additive tuple `(α, β, γ, δ, ε)` is closed; multiplier is conditional on `score_pre_grav < θ_demote`. |
| Q2: RRF + post-rerank (not weighted-sum)? | YES | §4.2 + §4.3 + §4.5; no `w_sem · sem + w_lex · lex + w_graph · graph` form anywhere; recall-time §7 rows for `w_sem/w_lex/w_graph` are explicitly marked "informational; folded into RRF" (lines 347–349). |
| Q3: 4 persistent shapes exhaustive? | YES | §5.1–§5.4 + §5.5 dispatch table; non-persistent intents `reply_only`/`peer_route`/`drop`/`escalate` flagged out-of-scope (line 210, line 237). |
| Q4: `emit_score_event` extends `metrics/emitter.py` (not sibling)? | YES | §8.4 line 427: "extend `scripts/eval/metrics/emitter.py` with `emit_score_event(event)`"; structurally compatible — the target module is a 91-line flat collection of sibling functions (`write_run_report`, `enforce_two_strata`, `enforce_cost_with_accuracy`, `render_headline_tag`); adding one more module-level function follows the existing pattern. |

---

## 3. Major findings

**None.** No P0 (anti-checklist violation) or P1 (under-specified emit-point) findings.

---

## 4. Nits (one-liners; doc-hygiene only)

- **N1** (`docs/05-scoring-design.md:261` and `:271` vs `:128–141`) — §5.4 states narrative is added to the §3.4 type-priority table at `0.50`, and §5.5 dispatch table assumes the value, but the §3.4 table itself does not contain a `narrative` row. Add the row or change the prose to "narrative type-priority is 0.50, override of §3.4."
- **N2** (`docs/05-scoring-design.md:550` vs `:488`) — Appendix A.1 `f_proc` calculation cites "residual unknown #1" for the `type_priority = 0.55` placeholder; §10 #1 is the `θ_promote` drift item. The procedure-type-priority gap is not enumerated in §10 at all. Either add it as §10 #6 and renumber the cross-ref, or move it to the §11.6 follow-throughs list (HANDOFF already names it there at line 517).
- **N3** (`docs/05-scoring-design.md:269`) — §5.5 dispatch table row for `preference, prohibition` shows `ε cap = 0.30`, but the cell for `narrative` shows `0.50` while §5.4 specifies `β = 0` and does not state an ε cap. Minor: either state "narrative ε cap = 0.50 (default)" in §5.4 prose or mark the table cell as inheriting the default.
- **N4** (`docs/05-scoring-design.md:533`) — Appendix A `f_pref` line writes `recency = 0`, which is correct in *contribution* (β=0 zeros it) but is not the value of `recency(f)` itself (the §3.1 formula yields a positive number). Minor presentation; consider "β · recency = 0 (β=0)" instead.
- **N5** (`docs/05-scoring-design.md:402`) — `contamination_protected` in the §8.2 envelope is shown with literal `true` rather than as a JSON-typed field. Schema-presentation nit; consider `"boolean (mandatory; see §8.5)"` for consistency with the other typed entries.

---

## 5. Stopping-criteria check

Per HANDOFF §11.4 anti-checklist (P0 if violated):

| Anti-checklist item | Violated? |
|---|---|
| Any §7 row that names SCNS / `~/.scns/` / foreign system as calibration source | **NO** |
| A generic per-class formula with "adjust per class" hand-waving | **NO** — §5.1–§5.4 each give explicit overrides; §5.5 is a closed table |
| §8 envelope missing `contamination_protected`, `tenant_id`, `model_version`, or `weights_version` | **NO** — all four present (§8.2 lines 396–402) |
| Consolidate-time formula places gravity as 6th additive term | **NO** — §3.6 is a multiplier on the bracket, conditional on `score_pre_grav < θ_demote` |
| Recall-time formula uses weighted-sum over sem/lex/graph | **NO** — §4.2 RRF only; §7 lines 347–349 mark the weighted form "informational; folded into RRF" |
| v1.0 calibration plan assumes operator-trace data exists | **NO** — `δ` and `w_utility` rows in §7 explicitly source from "Lethe opt-in trace (post-deploy)" / ramp 0→0.2 from 1k→10k entries; §7.5 ledger ramp guarantees zero contribution at v1.0 cold-start |

Per HANDOFF §11 stopping criteria for WS5 (line 451 et seq.):

| Criterion | Met? |
|---|---|
| Two scoring surfaces formalized with explicit math | **YES** |
| Per-term derivations carry explicit formulas, units, ranges, lit-review provenance | **YES** |
| Per-class dispatch exhaustive over 4 persistent shapes | **YES** |
| Bi-temporal invalidation semantics specified end-to-end | **YES** |
| Tuning-knob table comprehensive (default, range, source, eval signal, trigger) | **YES** |
| v2 log-signal contract: 7 events, common envelope, replayability, sink contract, two-gate entry | **YES** |
| Worked numerical example | **YES** |

---

## 6. Ready-for-WS6 / Ready-for-WS7 statement

**Ready for WS6 (API author):** YES.
- §4 + §6.1 give the request-time scoring path; §6.1 is unambiguous about apply-filter-before-retrieval (no score-then-filter).
- §8.2/§8.4 give a sufficient `emit_score_event` contract: a WS6 implementer can add the function to `scripts/eval/metrics/emitter.py` directly; the module structure (flat module of stub batch-sink functions) matches.
- §5.2 preference always-load (10 KB cap, scoring orders inside cap; does not gate inclusion) is precise enough to specify the `recall` response shape.
- HANDOFF §11.5 binding constraints (deterministic `recall_id` keying on `tenant_id + ts_recorded + query_hash`; six consolidate-phase emit boundaries; bi-temporal filter pre-retrieval; preference always-load is unconditional) are stated in the right place.

**Ready for WS7 (migration author):** YES.
- §6 invalidate-not-delete + T_purge grace window establishes the migration semantics (no destructive purges during cutover).
- §3 + §5 define what features need to be reconstructable from migrated data: `t_create`, `t_access`, `valid_from`, `valid_to`, `kind` frontmatter, S3 graph edges. Anything else is computable.
- §7 calibration ramp (`w_utility` silent below 1k entries) means a fresh-tenant migration will not over-fit cold-start.

---

## 7. SCNS-independence audit result

```
$ grep -rn -i "scns\|session_store\|~/.scns\|/Users/johnhain/Coding_Projects/scns" \
    docs/05-scoring-design.md docs/HANDOFF.md \
    | grep -v "^docs/HANDOFF.md.*WS[0-3]"
```

**Hits in `docs/05-scoring-design.md` (4 total — all classified as boundary clauses):**

| Line | Content | Classification |
|---|---|---|
| 6 | "Hard constraint (HANDOFF §10): No SCNS dependency. … SCNS dream-daemon is a *design-pattern reference only*; no SCNS numbers cross into Lethe scoring as ground truth." | **Boundary clause — explicit non-dependency.** |
| 323 | "Calibration source — public benchmark (LongMemEval / LoCoMo / DMR) and/or Lethe opt-in audit-log capture. **No SCNS dependency.**" | **Boundary clause — column-spec disclaimer.** |
| 369 | "**No SCNS calibration source appears in any row.** Verifiable: `grep -i scns docs/05-scoring-design.md` returns the binding constraint statement only." | **Boundary clause — verifiable closing assertion on §7.** |
| 506 | Traceability matrix row: `HANDOFF.md` §10 (binding constraint) → §0 (frame), §7 (no-SCNS-source verifiable), §8.5 (privacy invariants). | **Boundary clause — traceability pointer.** |

**Result: PASS.** Zero sentences in `docs/05-scoring-design.md` name SCNS as Lethe scoring data, calibration source, baseline, or training pool. Four hits, four explicit non-dependency clauses.

**Hits in `docs/HANDOFF.md` (excluded by grep filter for WS0–WS3 substrate context, plus reviewed inline):** all are either historical inventory (lines 19, 48, 98, 142, 143, 189, 197, 342, 343), §10 binding-constraint statement (lines 378–387, 404, 426), or §11.4/§11.5 reading-order instructions to WS5-QA / WS6 enforcing the same boundary (lines 449, 459, 462, 479, 482, 504). None are scoring-substrate dependencies.

---

## 8. Closing

WS5 closes the scoring loop cleanly. The §8 v2 log-signal contract is the deliverable I expected to be the weakest (forward-spec for code that doesn't exist yet) and is in fact the strongest — the sink shape genuinely is addable to `metrics/emitter.py` without redesign, the replayability invariant is sufficient for offline `(features, outcome)` derivation, and the two-gate entry criteria (≥20% operator + ≥10k pairs) honestly defer learned-scorer work without making v1.0 contingent on it.

The five nits are doc-hygiene; none warrant blocking WS6/WS7. They can be cleaned up in a follow-up commit alongside the §11.6 follow-throughs (procedure `type_priority` BO sweep, gravity computation cost at scale, utility/recency half-life decoupling).

**Verdict: APPROVE-WITH-NITS. Proceed to WS6.**
