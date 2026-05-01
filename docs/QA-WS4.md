# QA-WS4 — Eval & Benchmark plan + harness skeleton

**Reviewer:** WS4-QA fresh-eyes pass.
**Scope:** `docs/04-eval-plan.md` (commit `499f8c8`), `scripts/eval/**` (`1c38670`), `docs/HANDOFF.md` §10 (`4dbb2c5`).
**Substrate-binding question:** *Does WS4 give a WS5 author enough substrate to start without re-doing eval-design research, AND does the deliverable have ZERO residual SCNS dependency that survived the mid-flight course-correction?*

---

## 1. Verdict

**APPROVE-WITH-NITS.**

The eval plan is substantive, traceable, and the WS4-owns / WS4-doesn't-own boundary is drawn cleanly. The two-epoch design carries the operator-empty deferral honestly. Every gap-14 §5(1)–(5) constraint is addressed and traced in Appendix A. The skeleton imports clean, every leaf module exits 2 with the prescribed message, and every leaf docstring names its contract + cross-refs the eval plan and the motivating gap brief. The SCNS-independence audit is **clean** — every SCNS reference in the WS4 deliverables is an explicit "NOT a dependency" / "design-pattern reference only" clause; zero hits name SCNS or `session_store` as a Lethe data source, substrate, runtime dependency, or import path.

WS5 has enough substrate to start cold. Nits below are wording / cross-ref issues, not blockers.

---

## 2. Score table

| Artifact | Score | Rationale |
|---|---|---|
| eval-plan §1 (frame & scope) | 5/5 | WS4-owns vs. WS4-doesn't-own boundary is explicit; utility-vs-eval distinction (gap-02) called out cleanly. |
| eval-plan §2 (epochs) | 5/5 | Two epochs designed in; mandatory headline-tag wording specified verbatim; gating criterion is operational (≥20% operator + ≤10% author over 2 monthly runs), not calendar-based. §2.3 ("why two epochs and not one") is the kind of justification that survives review pressure. |
| eval-plan §3 (public benchmarks) | 5/5 | LongMemEval/LoCoMo/DMR all included with applicability caveats; §3.4 invariant (no accuracy without cost) is harness-enforced. |
| eval-plan §4 (Lethe-native eval set) | 5/5 | v1.0 percentages sum to 100% (0+35+25+25+15); operator at 0% with explicit deferral; symmetry policy §4.3, contamination defenses §4.4, versioning §4.5, self-collection pipeline §4.6 all present. §4.6 documents the Lethe-own opt-in audit-log capture as the v1.x operator pipeline (NOT SCNS). |
| eval-plan §5 (headline metrics) | 5/5 | Latency stratified per WS3-QA nit; intent-classifier macro-F1 is headline; extraction calibration per-domain; two-strata reporting mandatory. |
| eval-plan §6 (per-phase signals) | 5/5 | Each gap-01 §6 phase has its own metric vector with stratification axes and source metric cross-ref. WS5 input contract is concrete. |
| eval-plan §7 (chaos eval) | 5/5 | Every composition §7 failure mode has a row with pass criterion; two-stores-down matrix included with named health-endpoint states; §7.3 P0 short-circuits explicit. |
| eval-plan §8 (drift) | 5/5 | Cadence (monthly held-set re-eval, quarterly fresh adversarial, annual snapshot bump) and thresholds (5% strict-stratum regression; 5% case-retirement) specified. |
| eval-plan §9 (shadow harness) | 5/5 | Compute-don't-surface invariants explicit (no mutation, no caller-visible exceptions, wall-clock budget); implementation-independence clause present. |
| eval-plan §10 (harness layout) | 5/5 | Layout matches `scripts/eval/` exactly; stub conventions (docstring + `NotImplementedError` + `__main__` exit 2) specified and followed. |
| eval-plan §11 (reporting) | 4/5 | Report shape complete; CI-gate report described. Minor: §11.4's `eval-regression-justified:` PR-line escape hatch could use one more sentence on who can sign off (project lead? any reviewer?) — soft. |
| eval-plan §12 (open questions) | 5/5 | Honest list; "no fallback to foreign-system ingest is permitted" repeats the SCNS revocation explicitly. |
| eval-plan Appendix A (traceability) | 5/5 | Each gap-14 §5(1)–(5) constraint mapped to a §; §5(1) marked acknowledged-and-deferred at v1.0 with the v1.x migration plan referenced. |
| eval-plan Appendix B (cross-refs) | 5/5 | Every gap brief cross-referenced; WS5/WS6/WS7/WS8 touch-points named. WS7 line restates the eval-set-not-a-WS7-concern + no-SCNS rule. |
| HANDOFF §10 | 5/5 | §10.3 architectural-correction clause is unambiguous and binding; §10.4 QA reading order is specific; §10.5 WS5 reading order names the binding constraints; §10.6 open items name the right downstream owners. |
| `scripts/eval/README.md` | 5/5 | Layout, stub conventions, run example with expected exit-2, and an explicit "no foreign-system ingest at any epoch — no SCNS `session_store`" clause. |
| `scripts/eval/run_eval.py` | 5/5 | Contract docstring names CLI surface, output tree, exit codes (0/2/3/4/5); imports clean; exits 2 on `__main__`. |
| `scripts/eval/adapters/**` | 5/5 | Each adapter docstring names eval-plan §3.x and the gap brief that motivates it (longmemeval ↔ gap-01 §6 residual; locomo ↔ gap-09; dmr ↔ smoke). All exit 2. |
| `scripts/eval/lethe_native/**` | 4/5 | `loader.py` exposes `capture_opt_in_trace` as the v1.x audit-log entry point with `tenant_id, opt_in_record, trace` signature — gives WS6 a stable contract surface. `schema.py` enumerates SourceClass / IntentClass / Provenance fields cleanly. **One inconsistency** — see §4 nits — loader docstring lists `adversarial : ≥35% floor` but the eval-plan §4.1 floor is 30% (35% is the target share). |
| `scripts/eval/metrics/**` | 5/5 | `emitter.py` names `render_headline_tag`, `enforce_two_strata`, `enforce_cost_with_accuracy` as separate enforcement points; these are the three CI gates. `classifier.py` headlines macro-F1 per gap-12. `latency.py`/`extraction.py`/etc. all carry contract + cross-ref. |
| `scripts/eval/shadow/harness.py` | 5/5 | Compute-don't-surface invariants restated; `dual_dispatch` / `agreement_score` / `write_comparison_row` shape is concrete enough for WS5 to plan calibration A/B against. |
| `scripts/eval/chaos/faults.py` | 5/5 | Every single-failure mode and the two-stores-down combinations enumerated in the docstring; P0 short-circuits named; `inject` is a context manager (correct shape for fault-injection). |
| `scripts/eval/contamination/guard.py` | 5/5 | Strict / shadow modes; paraphrase-aware content match listed as a separate detection layer; `ContaminationError` is a real class (not a stub function), so downstream `except` clauses can reference it. |

---

## 3. Major findings

**None.** No P0 issues. No SCNS regression. No floor/cap violation. No missing chaos failure mode from composition §7. No metric from gap-12/gap-06/gap-01 §6 missing from §5/§6.

---

## 4. Nits (one-liners)

- `docs/04-eval-plan.md:36` — "traceable in §13" should be "traceable in Appendix A". The doc has §1–§12 plus Appendices A/B; there is no §13. (The traceability matrix lives at line 478, Appendix A.)
- `scripts/eval/lethe_native/loader.py:23` — docstring lists `adversarial : ≥35% floor` for v1.0; per `docs/04-eval-plan.md:120`, the v1.0 floor is 30% (35% is the target share). Recommend: change to `adversarial : ≥30% floor (target 35%)` to match the eval plan's enforcement language exactly.
- `docs/04-eval-plan.md:462` — `eval-regression-justified:` PR-line escape hatch could name the sign-off authority (project lead vs. any reviewer) in one phrase. Soft; can be deferred to WS8 deploy-policy.
- `docs/04-eval-plan.md:148` — "**10% of synthetic cases** per batch are reviewed by author + adversary"; the spot-check protocol cross-ref is gap-14 §6, but a forward pointer to the disagreement-rate metric emission in `metrics/emitter.py` would help WS8 scheduling. Soft.
- `scripts/eval/lethe_native/schema.py:53` — `Case` is currently a function placeholder rather than a real frozen `@dataclass`. The docstring acknowledges this ("placeholder ... today it raises so that downstream code that tries to construct cases fails loudly"), which is fine for a stub, but a minimal frozen dataclass shell with the listed fields would let WS5 type-check planning code without an extra round-trip. Soft.

---

## 5. Stopping-criteria check

WS4 stopping criteria from the original prompt — explicit YES/NO:

| Criterion | YES/NO | Evidence |
|---|---|---|
| Eval plan addresses gap-14 §5(1)–(5) §-by-§ in a traceability matrix | **YES** | Appendix A, lines 478–489. v1.0 status of §5(1) marked "acknowledged-and-deferred" with v1.x migration plan. |
| Two reporting epochs (v1.0 preliminary / v1.x post-operator-data) explicit | **YES** | §2.1 (v1.0 + headline-tag wording), §2.2 (v1.x), §2.3 (justification). |
| Leave-v1.0 gating criterion specified | **YES** | §2.1: operator ≥20% AND author ≤10% sustained over 2 monthly re-eval runs. |
| Lethe-native eval-set composition with capped author-share | **YES** | §4.1 table; v1.0 author-curated 15% cap, v1.x 10% cap; build-fail on cap violation. |
| Contamination defenses wired to gap-05 provenance | **YES** | §4.4 (4-step defense, strict/shadow modes); `contamination/guard.py` names gap-05 as verification surface. |
| Self-collection pipeline (NOT SCNS) documented as v1.x operator source | **YES** | §4.6 (7-step pipeline); §4.6 closing clause enumerates what the pipeline does NOT do (foreign-system ingest, unscrubbed retention, opt-out survival). |
| Stratified latency | **YES** | §5.2 (path × cache × tenancy × shadow). |
| Intent-classifier macro-F1 + per-class | **YES** | §5.6; `metrics/classifier.py`. |
| Extraction P/R/disambiguation + per-domain calibration | **YES** | §5.7; `metrics/extraction.py` (cross-refs gap-06 §3). |
| Two-strata reporting mandatory on every public comparison | **YES** | §5.9; `metrics/emitter.py::enforce_two_strata`. |
| Per-phase dream-daemon signals traceable to gap-01 §6 | **YES** | §6 table; six phases with metric vectors + stratification. |
| Chaos eval covers every composition §7 failure mode + two-stores-down | **YES** | §7.1 (14 single failures), §7.2 (3 two-stores combos), §7.3 (4 P0 short-circuits). |
| Drift signals + re-eval cadence | **YES** | §8 (5 distinct signals/cadences). |
| Shadow-retrieval harness | **YES** | §9 + `shadow/harness.py`. |
| Skeleton: importable, exit-2 contract, contract docstrings | **YES** | All 18 leaf `.py` files import clean (`python3 -c "import scripts.eval.run_eval"` succeeds); 7 spot-checked stubs all print `<module>: not implemented (WS4 stub)` and exit 2; every docstring names its contract and cross-refs eval-plan §X + a gap brief. |
| HANDOFF §10 specifies WS4-QA + WS5 reading orders | **YES** | §10.4 (QA reading order, with anti-checklist), §10.5 (WS5 reading order, with binding constraints). |
| Mid-flight SCNS course-correction held throughout | **YES** | See §7 below. |

---

## 6. Ready-for-WS5 statement

**YES — WS5 (scoring formalism) has enough substrate to start cold without re-doing eval-design research.**

WS5 inherits a concrete input contract from this WS4:

1. **Per-phase calibration target.** §6 names the metric vector for each of the six dream-daemon phases (extract / score / promote / demote / consolidate / invalidate). WS5's keep/replace/extend decisions are gated by these vectors.
2. **Promotion/demotion threshold tuning targets.** §5.5 specifies *both* promotion precision and demotion recall (gap-01 §6 needed both); WS5 tunes against both.
3. **Strict-stratum tuning rule.** §5.9 + HANDOFF §10.5 binding constraint: tune scoring weights against the strict stratum (operator + adversarial + ablation + replay-only). At v1.0 the strict stratum has no operator share; HANDOFF §10.5 explicitly tells WS5 to tune against adversarial + ablation + replay-only and accept the deferral cost.
4. **Mandatory headline-tag rendering.** `metrics/emitter.py::render_headline_tag` is the single rendering point; WS5's reports go through it.
5. **No foreign-system calibration data.** HANDOFF §10.3 / §10.5 is unambiguous: do not source calibration data from SCNS or any foreign system.

WS5 can start by reading `docs/04-eval-plan.md` §6 and §5.5 cold. The reading order in HANDOFF §10.5 is sufficient.

---

## 7. SCNS-independence audit

Grep result (raw):

```
$ grep -rn -i "scns|session_store|~/.scns|/Users/johnhain/Coding_Projects/scns" \
       docs/04-eval-plan.md scripts/eval/ docs/HANDOFF.md
```

Hits in WS4-owned files (`docs/04-eval-plan.md` + `scripts/eval/**`):

| Hit | Classification |
|---|---|
| `docs/04-eval-plan.md:5` "**Lethe stands on its own:** no Lethe artifact reads from SCNS; no Lethe code imports from the SCNS repo; no Lethe eval input comes from SCNS `session_store`. The SCNS dream-daemon remains a design-pattern reference only (WS1 audit / gap-01), not a data source." | ✅ Explicit "NOT a dependency" clause. Top-of-doc binding. |
| `docs/04-eval-plan.md:36` "(In particular, SCNS `session_store` is **not** a v1 input — Lethe stands on its own, and SCNS remains a design-pattern reference only.)" | ✅ Explicit "NOT a v1 input" clause. |
| `docs/04-eval-plan.md:54` "(c) faking an operator slice by importing from a foreign system that does not share Lethe's data model or consent boundary (the failure mode the SCNS revocation closes)." | ✅ Explicit revocation acknowledgment. |
| `docs/04-eval-plan.md:179` "no foreign-system import, no SCNS dependency, and no path that bypasses tenant consent." | ✅ Explicit "NOT a dependency" clause on the §4.6 self-collection pipeline. |
| `docs/04-eval-plan.md:194` "Does not import traces from any foreign system (no SCNS `session_store`, no other memory-system's audit log, no data broker)." | ✅ Negative-clause anti-list. |
| `docs/04-eval-plan.md:510` "WS7 (migration) — eval-set ingest is **not** a WS7 concern. WS7 should not plan against SCNS or any foreign system as a Lethe substrate or data source." | ✅ Explicit binding-on-WS7 anti-clause. |
| `scripts/eval/README.md:70` "no foreign-system ingest at any epoch — no SCNS `session_store`, no other memory-system's audit log, no data broker." | ✅ Negative-clause in skeleton README. |

Hits in `docs/HANDOFF.md`:

| Hit | Classification |
|---|---|
| `:19, :48, :98` (WS1 audit reference: `docs/01-scns-memory-audit.md`) | ✅ WS1 deliverable name; pre-existing inventory; design-pattern reference only. |
| `:142, :143, :342, :343` (WS2/WS3 design-pattern references: SCNS write-path consensus, SCNS LWW replaced by bi-temporal, SCNS-CLAUDE.md → preference pages, SCNS broker-DB → CAS) | ✅ Pre-existing WS2/WS3 cross-references for design patterns; not WS4-introduced; not data-source claims. |
| `:189, :197` (`/Users/johnhain/Coding_Projects/scns` is "**read-only** for this project. Never modify."; SCNS inventory raw output cross-ref) | ✅ Explicit read-only / inventory-reference framing; pre-existing. |
| `:378` "A mid-WS4 course correction revoked an earlier assumption that SCNS `session_store` would be the v1.0 operator-trace source." | ✅ Documents the revocation. |
| `:380` "**Lethe is independent.** No Lethe artifact reads from `~/.scns/`. No Lethe code imports from the SCNS repo. No Lethe eval input comes from `session_store`. The SCNS dream-daemon remains a **design-pattern reference only**…" | ✅ Binding independence clause for all downstream WS. |
| `:385, :386, :387, :404, :426` (anti-checklist + binding constraints on WS5/WS6/WS7) | ✅ Anti-clauses, all framed as "do NOT plan / do NOT read / NOT a concern". |

**Code-level audit:**

```
$ grep -rn -i "scns\|session_store" scripts/eval/*.py scripts/eval/**/*.py
scripts/eval/README.md:70:foreign-system ingest at any epoch — no SCNS `session_store`, no other
```

Zero hits in any `.py` file under `scripts/eval/`. Zero imports of SCNS-related modules. Zero references to `~/.scns/`, `session_store`, or any SCNS path in code.

**Result: PASS.** Every SCNS reference in the WS4 deliverables is either (a) an explicit "NOT a dependency" / "design-pattern reference only" clause, or (b) a pre-existing WS1/WS2/WS3 reference acknowledged from earlier workstreams. There are zero sentences in WS4-owned artifacts that name SCNS or `session_store` as a Lethe data source, substrate, runtime dependency, or import path. The mid-flight course correction held.

---

## 8. Handoff status

No `/handoff` written — verdict is APPROVE-WITH-NITS, not REQUEST-CHANGES. The five nits in §4 above are wording/cross-ref issues that the next WS4 author (or a self-fix commit) can fold in opportunistically; none gates WS5 or WS6.

WS4 is closed from a QA perspective. WS5 may proceed against the reading order in HANDOFF §10.5.
