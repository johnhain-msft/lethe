# GO/NO-GO — Lethe planning-phase exit recommendation

**Status:** Final planning-phase deliverable (`PLAN.md` §Deliverables item 5).
**Audience:** the project owner deciding whether to begin the implementation phase
(IMPLEMENTATION.md P1).
**Not for:** re-deciding any locked WS0–WS8 decision; proposing new design;
gating on calendar; requiring v2 design as a v1 prerequisite.

This artifact evaluates **planning-phase output as a coherent whole**. It does not
re-audit individual WS deliverables — those are audited at `docs/QA-WS{0-WS2,3,4,5,6,7,8}.md`.
The parity is: WS-QA validates each WS's self-audits; this pass validates
IMPLEMENTATION.md's self-audits and checks coherence across the WS substrate.

---

## §1 Verdict

**GO.**

Every PLAN.md §Deliverable except this one has landed (HANDOFF §16.4 roll-call).
All nine workstreams + per-WS QA + per-WS nit-fixes are on `origin/main`.
IMPLEMENTATION.md §6.2 reverse-traceability matrix realizes 40/40 locked decisions
across WS3 + WS5 + WS6 + WS7 + WS8 (re-verified at §4.2 below). The five
in-doc audits in IMPLEMENTATION.md §8 pass on independent re-run (§4 below).
The five high-stakes cross-WS seams audited at §4.1 are coherent — every
contract is consistent at every boundary. The deferral set named at HANDOFF §16.6
"For pause / NO-GO" substrate clears the §5 coherence bar (Named + Bounded +
Not-load-bearing-for-charter). The three charter §North-star failure modes
("wrapper over Graphiti"; "bag of best-practices"; "research artifact") are
evaded with cited evidence (§3 below).

The planning phase has produced a true-and-practical path to v1, not a survey
paper. The implementation phase is unblocked. Begin P1 of IMPLEMENTATION.md.

The verdict is **not** GO-WITH-CONDITIONS because no audit surfaced a
coherence break or a load-bearing deferral. Two minor follow-ups are surfaced
at §6 + §7 as **implementation-phase-tracked** items (not gating conditions);
they belong to the implementation-phase orchestrator, not to a pre-implementation
remediation pass.

---

## §2 Planning-phase output summary

### 2.1 Deliverables roll-call (PLAN.md §Deliverables)

| # | Deliverable | Path | Status |
|---|---|---|---|
| 1 | Charter through deployment-design (recast from "non-goals") | `docs/00-charter.md` … `docs/08-deployment-design.md` | ✅ all 9 landed |
| 2 | Gap deep-dives | `docs/03-gaps/gap-{01..14}-*.md` | ✅ 14 briefs |
| 3 | Eval-harness skeleton | `scripts/eval/` (per HANDOFF §10.1) | ✅ skeleton + adapters/metrics/chaos/contamination |
| 4 | IMPLEMENTATION.md | `docs/IMPLEMENTATION.md` | ✅ 678 lines, single commit `698488b` |
| 5 | **Go / no-go recommendation** | `docs/GO-NO-GO.md` | ✅ **this artifact** |

### 2.2 Workstream artifacts (line counts; verified `wc -l`)

| WS | Artifact | Lines | QA | Nit-fix commit |
|---|---|---|---|---|
| WS0 | `docs/00-charter.md` | (verified) | QA-WS0-WS2 | (covered with WS1+WS2) |
| WS1 | `docs/01-scns-memory-audit.md` + `docs/01b-dream-daemon-design-note.md` | (verified) | QA-WS0-WS2 | — |
| WS2 | `docs/02-synthesis.md` + `docs/02-lit-review/{01..22}-*.md` (22 briefs) | 22-brief total | QA-WS0-WS2 | — |
| WS3 | `docs/03-composition-design.md` + `docs/03-gaps/gap-{01..14}-*.md` | composition (verified); 14 gap briefs (149+136+169+65+100+73+170+103+76+111+171+100+202+95) | QA-WS3 | — |
| WS4 | `docs/04-eval-plan.md` | (verified) | QA-WS4 | — |
| WS5 | `docs/05-scoring-design.md` | (verified) | QA-WS5 | `b559021` |
| WS6 | `docs/06-api-design.md` | (verified) | QA-WS6 | `8cea51d` + `8b95b9c` |
| WS7 | `docs/07-migration-design.md` | (verified) | QA-WS7 | `fa4a7f8` |
| WS8 | `docs/08-deployment-design.md` | (verified) | QA-WS8 | `079cff2` |
| — | `docs/IMPLEMENTATION.md` | 678 | (this artifact) | — |
| — | `docs/HANDOFF.md` | (cascade record §1–§16) | (this artifact) | (this commit + next) |

Total docs corpus: 11,278 lines across `docs/` (verified `wc -l`).

### 2.3 Locked-decision count

- HANDOFF §13 cascade record: WS3 (4 implicit) + WS5 (7) + WS6 (9) + WS7 (10) + WS8 (14) = **44 locked decisions** total surfaced across the planning phase.
- IMPLEMENTATION.md §6.2 reverse-traceability matrix tabulates **40** of these (WS3 4 + WS5 7 + WS6 9 + WS7 10 + WS8 14 = 44 — note the IMPL §6.2 caption says 40/40 but the table itself lists 44 rows; the discrepancy is a counting error in IMPL §6.2's narrative line, not a coverage gap; see §6 residual #2 below).

### 2.4 Cascade record (HANDOFF §11–§15 architectural corrections)

Three architectural corrections landed during the planning phase (HANDOFF §10–§13):

1. **§10 — Lethe stands on its own** (no SCNS runtime dependency). Surfaced at WS4; binding from that point on. Realized as IMPLEMENTATION.md I-2 + §7 anti-checklist #3 + §8.a SCNS-independence audit.
2. **§11 — WS6 binding constraints** (api derives from composition + scoring; not from `vault.db`). Surfaced at WS5→WS6 transition. Realized as api §0.3 binding constraints.
3. **§13 — Markdown is dual-audience** (LLM + human; not human-only). Surfaced at WS6, drove WS7 + WS8 corrections. Realized as IMPLEMENTATION.md I-3 + §7 anti-checklist #10.

All three propagate cleanly into IMPLEMENTATION.md (verified §4.3 below).

---

## §3 Charter failure-mode assessment

PLAN.md §North star and `docs/00-charter.md` define three failure modes that
the planning phase MUST evade. Verdict per failure mode:

### 3.1 "Wrapper over Graphiti" — **EVADED**

The charter test: "would Lethe reduce to a thin storage adapter over Graphiti?"

Evidence of evasion:

- **Composition §2** decomposes Lethe into **5 stores** (S1 episodic graph, S2 metadata SQLite, S3 vector index, S4 markdown surface, S5 audit log). Graphiti is the substrate for **S1 only**. S2/S3/S4/S5 are Lethe-owned.
- **Composition §8.3 Candidate C** is the chosen topology: hybrid layered (graph-primary for facts, markdown-primary for authored synthesis). Two alternative topologies (§8.1 Candidate A markdown-primary; §8.2 Candidate B graph-primary) were considered and rejected with cited rationale. The choice **does not collapse to "Graphiti + markdown adapter"** — it places markdown as a canonical store with provenance propagation rules of its own (composition §6).
- **Scoring §3 + §4** specify a v1 consolidate-time + recall-time scoring formalism (recency + connectedness + utility + type-priority + contradiction-penalty + gravity-as-demotion-floor). Graphiti has no scorer; this is Lethe-owned per gap-03 + scoring §0 framing.
- **API §3.1** specifies a `consolidate_phase` emit chain (`extract → score → promote → demote → consolidate → invalidate`) that Graphiti does not provide. The dream-daemon (composition §4.4) is the runtime that fires it.
- **Migration §0.3** explicitly forbids `migrate_*` verbs on the wire — migration calls only existing api verbs. This means Lethe's runtime is the only path; Graphiti is never reached directly.

**Verdict: EVADED.** The runtime is Lethe-shaped; Graphiti is the substrate
for one of five stores. PLAN.md §North-star "Lethe is the runtime" passes.

### 3.2 "Bag of best-practices" — **EVADED**

The charter test: "would Lethe reduce to a stitched survey — Cognitive Weave's
scorer + MAM's consolidator + Letta's API + Zep's bi-temporal — with
integration left to the implementer?"

Evidence of evasion:

- **Composition §2 ownership matrix + §6 provenance propagation + §7 failure-mode analysis** specify integration as a binding contract: every store has a named owner, a named ownership rule, a named consistency model (§5), a named failure-mode response (§7). Integration is the product, not "left to the implementer."
- **IMPLEMENTATION.md §6.2** maps every locked design decision to a build phase (40/44 in the matrix; see §2.3 + §6 res#2). This is end-to-end realization, not stitching.
- **Scoring §3.6 gravity-as-demotion-floor** is an example of integration over best-practice stitching: Cognitive Weave proposes gravity as a 6th additive term; scoring §3.6 explicitly rejects that and uses it as a multiplicative demotion-floor instead. The decision is justified at WS5 §Q1 + §3.6 with cited rationale.
- **API §1.5 provenance envelope** is mandatory on every write verb (gap-05 §3); no other paper enforces this. It's a Lethe-binding integration choice, not a borrowed pattern.
- **Bi-temporal validity filter applied pre-retriever** (api §2.1 step 1; scoring §4.1; IMPLEMENTATION.md I-4): Zep applies bi-temporal post-rerank; Lethe applies pre-retrieve. The choice is justified at scoring §4.1; this is integration-level engineering, not adoption.

**Verdict: EVADED.** Integration is contract-shaped, not survey-shaped.

### 3.3 "Research artifact" — **EVADED-WITH-CAVEAT**

The charter test: "would Lethe ship as a research substrate that no agent can
routinely use?"

Evidence of evasion:

- **API §3** specifies five core verbs (`remember`, `recall`, `promote`, `forget`, `peer_message_*`) plus admin/ops surface (§4). The verb count is bounded; the surface is implementable.
- **IMPLEMENTATION.md §2.10 P10** is a concrete cutover gate (first production deployment, single-tenant-per-deployment v1 baseline). The cutover gate at §4 enumerates 5 conditions, all check-shaped.
- **Eval substrate is wired**: DMR (sanity floor at P3 exit), LongMemEval (primary at P9 exit), LoCoMo (signal at P9), chaos + drift + opt-in trace ingest (P9). Per HANDOFF §10.1, the `scripts/eval/` skeleton is in-tree.
- **Deployment §1–§10** spells out an operator-shaped surface: roles, transports, rate-limits, observability, escalate-review pipeline, backup posture, degraded-mode playbook. This is operator-runnable substrate, not academic prose.

**Caveat (the "WITH-CAVEAT" qualifier):** The v1.0 eval substrate ships with
empty operator-share at the strict stratum (HANDOFF §10.5 — accepted deferral).
This means the LongMemEval primary slice runs end-to-end at P9 with
preliminary-tag wording (IMPL §4 cutover #2), not with full strict-stratum
results. Two consequences:

- The implementation-phase orchestrator should treat LongMemEval at P9 as a
  **wiring gate** (the harness runs end-to-end on a tenant-shaped fixture; the
  numbers are preliminary-tagged), not as a v1-quality gate. The v1-quality
  gate is the strict-stratum operator share, which builds up post-cutover via
  `capture_opt_in_trace` opt-ins.
- This caveat is explicitly named at HANDOFF §10.5 and tracked at IMPL §3 R6
  (P1, not P0). It does NOT collapse evasion of failure mode #3 because the
  v1 deployment IS routinely usable — agents call `remember`/`recall`, get
  results, see consolidation behavior. The caveat is a measurement-side
  caveat, not a usability-side one.

**Verdict: EVADED-WITH-CAVEAT.** v1 ships routinely usable; eval-quality
measurement is provisional until opt-in trace data accumulates. The caveat
is honest, named, and tracked.

---

## §4 Coherence audit

### 4.1 Cross-WS seam audit (5 high-stakes seams)

The seams selected are the contracts most likely to fracture between docs.
Each seam crosses ≥3 docs; all are mid-to-high-stakes (P0/P1 risks attached).

#### Seam 1 — v2-gate substrate (scoring §8.6 ↔ deployment §10 ↔ IMPL §4)

- **scoring §8.6** specifies the two-condition v2 entry-criteria gate
  (operator-share + labeled-pairs).
- **deployment §10** lifts both conditions to operator-visible gauges:
  `health().v2_gate.strict_stratum_operator_share_pct` and
  `health().v2_gate.labeled_pairs`. Adds the 3-month soak rule.
- **deployment §5.2** specifies the `v2_gate` schema additions to `health()`:
  `strict_stratum_operator_share_pct` (gate 1), `labeled_pairs` (gate 2),
  `consecutive_months_green` (soak counter).
- **IMPLEMENTATION.md §2.10 P10** wires gauges
  (`health().v2_gate.{operator_share, labeled_pairs}` per `src/lethe/runtime/v2_gate.py`).
- **IMPLEMENTATION.md §4 cutover gate condition #4** requires both gauges
  initialized and reporting (NOT GREEN — that's v1→v2, not v0→v1).

**Coherence check:** field names are consistent across all three docs:
`operator_share` / `labeled_pairs` (with the deployment §5.2 prefix
`strict_stratum_operator_share_pct` being the wire-format-explicit form of the
abbreviated `operator_share` used at IMPL §2.10 + §4). The
v0→v1 vs v1→v2 distinction is preserved at every layer. The 3-month soak
counter is named at deployment §10 + IMPL §4 and not load-bearing for v0→v1.

**Verdict: COHERENT.**

#### Seam 2 — migration phases ↔ `lethe-migrate` subcommands ↔ P8

- **migration §3.1** defines 14 phases (Pre-flight … Post-cutover S4b regen),
  with three hard phase-gates A/B/C at phases 4/7/10.
- **deployment §7.1** maps `lethe-migrate` subcommands 1:1 to migration §3.1
  phases (12 subcommands cover phases 1–14 + cross-phase resume + recovery).
- **IMPLEMENTATION.md §2.8 P8** §-refs both deployment §7.1 and migration §3.1
  for the `cli/lethe-migrate` surface; phase-gates A/B/C are realized via
  `lethe-migrate phase-gate <run_id> {a|b|c}`.

**Coherence check:** every migration phase has a `lethe-migrate` subcommand;
every subcommand has a phase. The three phase-gates A/B/C reference the
underlying lints — gate A `lethe-audit lint --integrity` (gap-08 §3.5),
gate B episode-id round-trip (gap-05 §6), gate C provenance-required +
provenance-resolvable + forget-proof-resolves (gap-05 §3.5 + gap-08 §3.5).
The lints all exist in the gap briefs; the wiring at deployment §7.1 references
them by name; the implementer at P8 has unambiguous targets.

**Verdict: COHERENT.**

#### Seam 3 — Lock heartbeat (gap-08 §3.4 ↔ gap-01 §3.2 Q3 ↔ deployment §4.2 ↔ IMPL §3 R8 + §2.4 P4)

- **gap-08 §3.4** sets the contract: lock heartbeat with `2× heartbeat`
  break-multiplier; gap-01 §3.2 Q3 sets the heartbeat default at 30 s.
- **deployment §4.2** picks the operator default: 30 s heartbeat, 60 s break
  (= 2× heartbeat). Operator-tunable via `tenant_config.dream_daemon.heartbeat_seconds`;
  break-multiplier fixed.
- **IMPLEMENTATION.md §2.4 P4** wires this: per-tenant lock w/ 30 s heartbeat;
  test at `tests/runtime/test_lock_heartbeat.py`. Crash-recovery via
  `lethe-admin lock` path stub (P4) + full landing at P8.
- **IMPLEMENTATION.md §3 R8** tracks idempotency-key TTL edge cases
  (a related but distinct concern — TTL: 24 h default, 7-day enforced ceiling).
  Note: R8 is the idempotency-TTL risk, not the lock-heartbeat risk; the
  lock-heartbeat risk is implicit at R2 (crash-mid-write) which P5 + P8 close.

**Coherence check:** the 30 s / 60 s / 2× numbers are consistent across
gap-08 + gap-01 + deployment §4.2 + IMPL §2.4. The break-multiplier-fixed
constraint is named at deployment §4.2 and not contradicted elsewhere.

**Verdict: COHERENT.**

#### Seam 4 — Tenant isolation (composition §5.2 ↔ deployment §5.5 ↔ IMPL I-10 + §3 R4)

- **composition §5.2** invariant: "No cross-tenant reads, ever." Tenant scope
  is a top-level partition on every store (Graphiti `group_id`, per-tenant
  SQLite file, per-tenant subdir in S3, per-tenant root path in S4).
- **composition §7** failure-mode row: tenant isolation breach is
  "should be impossible by construction; treat as P0 bug. Defensive: every
  storage call goes through `tenant_scope_filter` middleware."
- **deployment §5.5** wires the alarm: `tenant_isolation_breach` is **P0**;
  triggers HALT writes; cross-tenant reads return **404** (`not_found`) per
  api §1.8 (existence of cross-tenant ids must not leak).
- **IMPLEMENTATION.md I-10** restates as binding upstream invariant.
- **IMPLEMENTATION.md §3 R4** tracks as P0 risk with mitigation phase P7.
- **IMPLEMENTATION.md §2.7 P7** wires the alarm
  (`src/lethe/runtime/alarms/wiring.py` enumerates all 8 must-wire alarms
  including `tenant_isolation_breach (P0)`); cross-tenant read returns 404.

**Coherence check:** all four docs agree on (a) the invariant (no cross-tenant
reads); (b) the enforcement mechanism (`tenant_scope_filter` middleware +
`tenant_isolation_breach` alarm); (c) the wire response (404, not 403, not
empty); (d) the priority (P0). The 404-not-empty distinction is the most
fragile and is preserved at all four layers (composition §5.2 + deployment §5.5
+ api §1.8 + IMPL I-10 + IMPL §2.7).

**Verdict: COHERENT.**

#### Seam 5 — Provenance + migration rollback discriminant (gap-05 §6 ↔ migration §2.3 ↔ IMPL §3 R3)

- **gap-05 §6** specifies: episode-ids are tenant-scoped UUIDs preserved
  across migration (cross-runtime provenance bet); `provenance.source_uri` is
  mandatory + non-null + originating-reference-shaped.
- **migration §2.3** locks the rollback-key derivation: a *fourth* uuidv7
  derived over `scns_observation_id` with discriminant `"rollback"`,
  collision-disjoint from `"idem"` (the original `remember`-call
  idempotency-key), `"forget"` (migration-time invalidation), and `"epi"`
  (the episode-id discriminant). All four use `ts_recorded_scns` (not
  rollback-time `now()`), so keys are reproducible from manifest inputs alone.
- **IMPLEMENTATION.md §3 R3** tracks provenance-loss as P0 with mitigation
  phases P2 + P5 + P8.

**Coherence check:** the four discriminants (`"idem"`, `"forget"`, `"epi"`,
`"rollback"`) are pairwise collision-disjoint by construction (different
discriminant strings → different sha256 inputs → different uuidv7 layouts).
This is the substrate that makes `forget(invalidate)` on rollback safe even
when the original migration `forget` already fired. The migration §2.3
rollback-key block was nit-corrected at WS8-QA N2 (commit `079cff2`); the
final wording is operationally-correct (verified by reading migration §2.3
lines 211–223). Provenance integrity is end-to-end: gap-05 §6 contract →
migration §2.3 derivation → IMPL §2.2 P2 envelope enforcement → IMPL §2.5 P5
forget-proof resolution → IMPL §2.8 P8 `lethe-audit lint --integrity` at
phase-gates A + C.

**Verdict: COHERENT.**

### 4.2 Locked-decision realization (re-verification of IMPL §6.2)

Re-derived the locked-decision count from HANDOFF §13 cascade record:

| WS | Count (HANDOFF) | Realized in IMPL §6.2 | Unmatched |
|---|---|---|---|
| WS3 (composition; implicit, drawn from §1.1 + §2 + §8.3 + cascade) | 4 | 4 | 0 |
| WS5 (HANDOFF §11.3) | 7 | 7 | 0 |
| WS6 (HANDOFF §12.3) | 9 | 9 | 0 |
| WS7 (HANDOFF §14.3) | 10 | 10 | 0 |
| WS8 (HANDOFF §15.3) | 14 | 14 | 0 |
| **Total** | **44** | **44** | **0** |

**IMPL §6.2 narrative line says "40/40"; the table itself enumerates 44 rows.**
The discrepancy is a counting mistake in IMPL §6.2's narrative
("Coverage: 40/40 locked decisions mapped to a realizing phase") — the actual
count is 44. The table content is correct; only the count-narrative is off
by 4. This is benign (no decision is unrealized; no row is missing) and is
captured as §6 residual #2 below.

**Reverse-coverage verdict: COMPLETE.** Every locked decision has a realizing
phase. The narrative count needs a one-character fix (40 → 44); the structural
realization is sound.

### 4.3 Architectural-correction lineage

Three corrections in HANDOFF §10–§13 propagate into IMPLEMENTATION.md:

| Correction | HANDOFF | Realized in IMPL |
|---|---|---|
| Lethe stands on its own (no SCNS runtime dependency) | §10 + §11.5 + §12.5 | I-2 + §0.2 #3 + §7 anti-checklist #3 + §8.a SCNS-independence audit (14 hits, all categorized allowed) |
| WS6 binding constraints (api derives from composition + scoring) | §11.5 + §12.5 | §0.3 (binding upstream invariants I-1 through I-13) |
| Markdown is dual-audience (LLM + human; not human-only) | §13 | I-3 + §7 anti-checklist #10 (zero "for humans only" / "human-only" binding hits) |

All three propagate without loss. The §8.d anti-checklist self-check confirms
zero binding violations.

### 4.4 Independent re-run of IMPL §8 audits

Per the parity pattern (this artifact validates IMPL's self-audits, not its
WS sources):

| Audit | IMPL §8 claim | Re-run | Verdict |
|---|---|---|---|
| §8.a SCNS-independence grep | 14 hits, all allowed | Re-ran `grep -in "scns" docs/IMPLEMENTATION.md`: 14 hits matched (lines 28, 38, 315, 522, 555, 566, 577, 579, 584, 591, 592, 594, 640, 678). All categorized in IMPL §8.a's allowed list. | **PASS** |
| §8.b Phase-cycle DAG | ACYCLIC, P1→P10 topo order | Re-derived edge list from §2 dependency rows: P1→{}; P2→{P1}; P3→{P2}; P4→{P3}; P5→{P4}; P6→{P5}; P7→{P6}; P8→{P7}; P9→{P7,P8}; P10→{P9}. Every edge points to lower-numbered phase. No back-edges. Topo sort: P1→P2→P3→P4→P5→P6→P7→P8→P9→P10 (unique, satisfies both edges into P9). | **PASS** |
| §8.c Coverage | 10/10 forward + 40/40 reverse | Forward: every P1–P10 row in §6.1 cites ≥1 WS source (counts: 4/7/9/7/5/7/11/11/9/5 — all ≥1). Reverse: 44 rows enumerated in §6.2 (see §4.2 above; the narrative "40/40" is a counting typo for 44/44). | **PASS** (with §6 res#2 narrative-typo follow-up) |
| §8.d Anti-checklist self-check | All 10 items pass | Spot-re-verified items #3 (SCNS), #4 (cross-deployment), #5–#7 (auth/wire/metrics), #8 (v2), #10 (human-only). All evidence holds. | **PASS** |
| §8.e Operator-readability | (DROPPED per D4) | Audit dropped per plan-mode D4: stylistic, not coherence-shaped; QA-WS8 already covers operator-readability at the deployment-doc level. | (n/a) |
| **§8.f (added) Citation-integrity** | (per plan-mode D4) | Sampled all §-refs in IMPL §6.2 reverse-traceability matrix and §3 risk-register source column. Every cited section exists in the cited doc. One stylistic finding: composition uses `## N` headings while scoring/api/migration/deployment use `## §N`; IMPL §6.2 cites all of them as "<doc> §N", which is the standard convention but disagrees with composition's literal heading style. **No coherence break — all sections resolve.** Worth normalizing in a downstream nit-fix (see §6 res#1). | **PASS** |

Five audits pass on independent re-run (with one narrative-typo and one
heading-style follow-up surfaced as residuals).

---

## §5 Deferral-coherence assessment

### 5.1 The bar (3-condition conjunctive, per plan-mode D3)

A deferral is COHERENT if it clears all three:

1. **Named.** Appears in IMPLEMENTATION.md §5 (or HANDOFF §15.5 + §16.x) with
   source §-ref AND the phase that would close it post-v1.
2. **Bounded.** v1 surface degrades gracefully without it; no v1 verb returns
   500; no v1 invariant breaks. There exists a v1 user story that succeeds
   without the deferred surface.
3. **Not-load-bearing for charter.** Deferring it does not collapse one of
   the three failure-mode evasions in §3.

A deferral failing ANY of the three is SCOPE-CREEP-SHAPED.

### 5.2 Deferral-by-deferral verdict

The deferrals named at HANDOFF §16.6 "For pause / NO-GO" substrate, plus
extended set from IMPLEMENTATION.md §5 (28 rows):

| # | Deferral | Source | Closes | Named | Bounded | Not-load-bearing | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | v1.0 strict-eval-stratum empty operator share | HANDOFF §10.5 | post-cutover trace ingest | ✅ | ✅ (v1 ships; LongMemEval is wiring gate, not quality gate) | ✅ (caveat at §3.3; doesn't collapse evasion #3) | **COHERENT** |
| 2 | gap-03 §5 candidate (a) defaults vs calibrated tuple | HANDOFF §11.6 #4; gap-03 §5 | v1.1 BO sweep at P9 | ✅ | ✅ (defaults are operationally usable; scoring §6 acknowledges tuning is post-v1) | ✅ (charter test is "true and practical"; defaults satisfy it) | **COHERENT** |
| 3 | `lethe-migrate` CLI bytes | migration §3 contract; HANDOFF §15.5 | operator-tooling pass post-WS8 | ✅ | ✅ (contract is set at deployment §7.1; bytes are implementer's call per IMPL §0.2) | ✅ (charter is about runtime not tooling) | **COHERENT** |
| 4 | `lethe-admin` CLI bytes | deployment §8.3; HANDOFF §15.5 | operator-tooling pass | ✅ | ✅ (same logic as #3; runtime serves verbs; admin is operator-side) | ✅ | **COHERENT** |
| 5 | Review-surface HTML implementation | deployment §6.2; HANDOFF §15.5 | operator-tooling | ✅ | ✅ (review queue substrate exists in S2; HTML is presentation) | ✅ | **COHERENT** |
| 6 | Cross-deployment Lethe→Lethe restore | deployment §8.1; HANDOFF §15.5 | future migration spec | ✅ | ✅ (single-tenant-per-deployment v1 baseline doesn't require it) | ✅ (v2 surface) | **COHERENT** |
| 7 | Cross-deployment Lethe→Lethe migration spec | migration §10; HANDOFF §14.6 | future migration spec | ✅ | ✅ | ✅ | **COHERENT** |
| 8 | Metrics-pipeline impl (Prometheus / OTLP / log-scraper) | deployment §5.4; HANDOFF §15.5 | per-deployment | ✅ | ✅ (must-emit signals are named; exporter choice is operator-side per IMPL §0.2 #7) | ✅ | **COHERENT** |
| 9 | `force_skip_classifier=true` formal addition to api §3.1 | deployment §6.3; HANDOFF §15.5 | wired in P7; api §3.1 doc edit pending | ✅ | ⚠️ **see below** | ✅ | **COHERENT (with edge note)** |
| 10 | v2 multi-tenant runtime | composition §1.1; deployment §10; HANDOFF §15.5 | v2 design WS | ✅ | ✅ (v1 is single-tenant-per-deployment by design) | ✅ (v2 is explicitly out-of-scope per anti-checklist) | **COHERENT** |
| 11 | 2PC for cross-host T1 | gap-08 §5; HANDOFF §15.5 | v2 | ✅ | ✅ (single-tenant + single-writer-per-tenant default closes v1; gap-04 §4) | ✅ | **COHERENT** |
| 12 | BO sweep for scoring weights | gap-03 §5 candidate (b); HANDOFF §11.6 #4 | v1.1 | ✅ | ✅ (candidate (a) defaults run at v1.0) | ✅ | **COHERENT** |
| 13 | Per-tenant retune | scoring §7; HANDOFF §11.6 | v1.x post-trace data | ✅ | ✅ (single-tenant-per-deployment means per-tenant retune is per-deployment retune; v1 ships with global defaults) | ✅ | **COHERENT** |
| 14 | Reviewer-recruitment workflow for adversarial 35% slice | eval §10.6; HANDOFF §10.6 | WS8 / project-ops | ✅ | ✅ (bias mitigation is provisional at v1.0; live tracking begins post-cutover) | ✅ | **COHERENT** |
| 15 | RBAC management API verb | deployment §2.1; HANDOFF §15.5 | v1.x | ✅ | ✅ (v1 RBAC has 3 fixed roles + capability table; management is operator-tooling) | ✅ | **COHERENT** |
| 16 | "3 consecutive months" reset semantics under partial-month outages | deployment §10; HANDOFF §15.5 | v1.x refinement | ✅ | ✅ (gates v1→v2; doesn't gate v0→v1; soak counter starts at zero on cutover per IMPL §4) | ✅ | **COHERENT** |
| 17 | Backup quiesce automation | deployment §8.1; HANDOFF §15.5 | operator-tooling | ✅ | ✅ (manual procedure at deployment §8.1 is operator-runnable; automation is downstream) | ✅ | **COHERENT** |
| 18 | `vault.db` consumer | migration §1.1, §8; HANDOFF §14.6 | future migration or v1.x | ✅ | ✅ (corpus-only migration is the v1 contract per WS7 #2; `vault.db` is observation-side, not memory-side) | ✅ | **COHERENT** |
| 19 | Classifier accuracy upgrade (gap-12 → LLM) | migration §10 §3.4; HANDOFF §15.5 | v1.x post-cutover | ✅ | ✅ (heuristic classifier ships at v1.0; LLM upgrade is an accuracy-bet, not a contract change) | ✅ | **COHERENT** |
| 20 | `emit_score_event` impl | scoring §8.4; HANDOFF §11.6 | wired in P9 (sink); contract set at WS5 | ✅ | ✅ (sink is wired at P9; emit-points fire from P2/P3/P4/P6) | ✅ | **COHERENT** |
| 21 | `capture_opt_in_trace` external verb impl | api §4.1; HANDOFF §12.6 | wired in P6 | ✅ | ✅ (verb contract at api §4.1; impl at IMPL §2.6 P6) | ✅ | **COHERENT** |
| 22 | Drift-detector cadence integration with deploy-cadence | deployment §4.5; HANDOFF §10.6 | per-deployment | ✅ | ✅ (drift-detector contract at deployment §4.5; cadence is operator-tunable) | ✅ | **COHERENT** |
| 23 | Daily-block source-id collision under multi-snapshot migration | migration §10 | operator-tooling | ✅ | ✅ (cold-start migration recommended per WS7 #8; multi-snapshot is the warm path) | ✅ | **COHERENT** |
| 24 | Procedure-vs-narrative heuristic accuracy floor | migration §10; HANDOFF §14.6 | operator-tooling | ✅ | ✅ (heuristic at migration §3.4; accuracy-bet, not contract change) | ✅ | **COHERENT** |
| 25 | Phase-9 async-drain volume threshold | migration §10; deployment §4.7 | per-deployment | ✅ | ✅ (1.5× gate alarm at deployment §4.7 protects the boundary) | ✅ | **COHERENT** |
| 26 | Phase-11 S3 backfill duration & progress UX | migration §10; HANDOFF §14.6 | operator-tooling | ✅ | ✅ (non-blocking on api surface per WS7 #10; UX is operator-tooling) | ✅ | **COHERENT** |
| 27 | Sensitive-content escalation review workflow at scale | migration §5.1; deployment §6; HANDOFF §12.6 | WS8 / project-ops | ✅ | ✅ (substrate at deployment §6.1–§6.5; scale is operations) | ✅ | **COHERENT** |
| 28 | Manifest UX surface (CLI / JSON / HTML) | migration §10; HANDOFF §14.6 | operator-tooling | ✅ | ✅ (contract at deployment §7.2; UX is operator-side) | ✅ | **COHERENT** |
| 29 | Wire-format re-evaluation at v2 fleet scale | deployment §2.4; HANDOFF §15.5 | v2 | ✅ | ✅ (JSON-over-HTTP/1.1 at v1; protobuf/msgpack rejected for v1 per deployment §2.4 with rationale) | ✅ | **COHERENT** |
| 30 | Disk thresholds at fleet scale | deployment §8.4; HANDOFF §15.5 | v2 | ✅ | ✅ (single-tenant-per-deployment v1 doesn't need fleet-scale accounting) | ✅ | **COHERENT** |

**Note on #9 (`force_skip_classifier=true` formal api §3.1 addition):** The
parameter is documented in deployment §6.3 + IMPLEMENTATION.md §6.2 (WS8 #9
realizes at P2 + P7 with "api §3.1 formal addition" called out). The
*formal addition to api §3.1* is the doc edit, not the contract change —
the contract is already binding via IMPL §6.2. The doc edit is a coherence
follow-up; it does not gate v1. Verdict stays COHERENT, with the doc-edit
itself surfaced as §6 res#3 below.

### 5.3 Aggregate verdict

**30/30 deferrals COHERENT.** Zero SCOPE-CREEP-SHAPED. The deferral set is
the shape of "v1 is true and practical with these exact deferrals," not
"v1 reduces to a substrate for v2." The implementation phase inherits a
clean v1 scope.

---

## §6 Residual risks the implementation phase inherits

### 6.1 P0 + P1 risks from IMPL §3

These are live items the implementation phase must track. The go/no-go does
NOT pre-close them; it surfaces them so the implementation-phase orchestrator
budgets attention.

| ID | Risk | Pri | Mitigation phase | Closing notes for implementation orchestrator |
|---|---|---|---|---|
| R1 | Markdown write amplification at scale | P0 | P1 + P3 | Substrate-level mitigation only; load-test boundary is post-cutover. |
| R2 | Crash-mid-write corruption | P0 | P2 + P5 + P8 | Idempotency replay invariant (P2) + retention-proof-before-delete (P5) + `lethe-audit lint --integrity` at gates A+C (P8). Each phase closes one slice; **no single phase fully closes R2.** Track end-to-end. |
| R3 | Provenance loss | P0 | P2 + P5 + P8 | Same shape as R2 — multi-phase end-to-end protection. |
| R4 | Tenant isolation breach | P0 | P7 | Closes at P7 (alarm wiring + cross-tenant 404). Pre-P7, the substrate prevents cross-tenant reads by partitioning (composition §5.2); the alarm is the runtime backstop. |
| R5 | Scoring weight miscalibration | P1 | P4 + P9 | v1 defaults at P4; calibration sweep at P9 + post-cutover. |
| R6 | Utility-feedback signal loss | P1 | P3 + P6 + P9 | The empty-strict-stratum-operator-share caveat (HANDOFF §10.5; §3.3 above). Closes asymptotically post-cutover via `capture_opt_in_trace` ingest. |
| R7 | Intent classifier mis-routes | P1 | P2 + P7 | v1 heuristic; LLM upgrade is deferral #19. |
| R8 | Idempotency-key TTL edge cases | P1 | P2 + P7 + P8 | TTL contract: 24 h default + 7-day enforced ceiling at startup. R8 = the edge case where a migration run exceeds 24 h and re-issues a key whose TTL expired; the `audit(provenance.source_uri=...)` fallback at P8 covers this. |

### 6.2 Risks NOT closed by any single phase (cross-phase tracking required)

R2, R3, R6 each span 3 phases. The implementation-phase orchestrator should
track these as **standing risks** through cutover, not mark them closed at
any single phase exit. Suggested artifact: a per-phase QA pass that asserts
the slice closed in that phase still holds at every subsequent phase exit
(parity with the WS-QA pattern of re-asserting upstream invariants).

### 6.3 Implementation-phase-tracked items (NOT gating conditions)

Three items surfaced by this go/no-go that the implementation-phase orchestrator
should track but that do NOT gate the start of P1:

1. **Heading-style normalization** (§4.4 §8.f finding): composition uses
   `## N` while other docs use `## §N`; IMPL §6.2 cites all as "<doc> §N".
   No coherence break. A downstream nit-fix may normalize composition to
   `## §N`. Owner: implementation-phase orchestrator (or anyone editing
   composition next).
2. **IMPL §6.2 narrative-count typo** (§4.2): the narrative says "40/40
   locked decisions"; the table enumerates 44 rows. A one-character fix
   (40 → 44) on the IMPL §6.2 closing sentence. Owner: same.
3. **api §3.1 formal addition of `force_skip_classifier=true`** (§5.2 #9):
   the parameter is in deployment §6.3 + IMPL §6.2 WS8 #9 realizing at P2 + P7,
   but the api §3.1 doc text doesn't yet enumerate it. A doc-edit to api §3.1
   makes the contract maximally discoverable from the api doc alone.
   Owner: api doc author; safe to fold into the next api §3 edit.

These three are surfaced for awareness, not for blocking. The implementation
phase should fold them in opportunistically.

---

## §7 Cadence recommendation

Per PLAN.md §Sequencing "no dates; gate on artifacts," the implementation
phase should adopt the same artifact-gating cadence used in the planning
phase. The phase-exit-on-gate-pass pattern from IMPLEMENTATION.md §2 already
encodes this for each P1–P10 phase.

**Recommended QA cadence: per-3-phases.**

Group as:

| Group | Phases | Rationale |
|---|---|---|
| **G1 Substrate + ingress** | P1 + P2 + P3 | Storage + write path + read path. Contract set: bi-temporal pre-filter; idempotency; provenance envelope. Mid-stack QA point. |
| **G2 Runtime completion** | P4 + P5 + P6 | Consolidate + lifecycle writes + surface completion. Contract set: scoring at consolidate-time + recall-time; CAS; retention-proof; peer-messaging. |
| **G3 Operator + tooling** | P7 + P8 + P9 | RBAC + transport + observability + migration tooling + eval wiring. Contract set: RBAC roles; rate-limits; alarms; `lethe-migrate` surface; eval slice gates. |
| **G4 Cutover** | P10 | First production deployment; v2_gate gauges initialized. |

Each group exit triggers a QA pass mirroring the WS-QA pattern. The QA
reviewer audits the group's exit gates against IMPLEMENTATION.md §2.{phase}
exit criteria, runs §6.2 reverse-traceability for the locked decisions
realizing in the group, re-runs the §3 risk register for risks closed
in-group, and surfaces nits.

**Why per-3-phases (not per-phase, not per-eval-gate):**

- **Per-phase** is over-rotation. Planning-phase coverage of locked decisions
  is heavy (44/44 mapped at IMPL §6.2); per-phase QA would mostly re-verify
  cite-and-implement work. Use per-phase only if a phase exit surfaces a
  contract-shape question.
- **Per-eval-gate** is under-rotation. Skips P5 + P6 + P7 + P8 surfaces where
  R3 + R4 P0 risks actually live; eval-gates wouldn't catch a missed
  slice in those phases.
- **Per-3-phases** matches the natural seam structure (substrate / runtime /
  operator / cutover) and lands a QA pass at every contract-shape boundary.

**Caveat:** the implementation-phase orchestrator owns the final cadence
call. This recommendation is a starting shape, not a binding schedule.
If P1 reveals a contract-shape question that wasn't surfaced in planning,
the orchestrator may insert a P1-exit QA pass and not wait for the G1 group
exit. Conversely, if G1 lands cleanly, the orchestrator may collapse G2's
QA into G3's at an end-of-runtime audit point. The cadence is artifact-gated,
not date-gated; the recommendation respects that.

**Specific recommended QA artifacts:**

- `docs/QA-G1.md` (after P3 exit) — `APPROVE-WITH-NITS` shape.
- `docs/QA-G2.md` (after P6 exit) — same.
- `docs/QA-G3.md` (after P9 exit) — same.
- `docs/QA-G4.md` (after P10 exit; pre-cutover-sign-off) — verdict shape
  is GO-FOR-CUTOVER / NO-GO-FOR-CUTOVER.

---

## §8 Anti-checklist self-check

Per HANDOFF §16.6 anti-checklist for the go/no-go pass:

| # | Constraint | Self-check | Verdict |
|---|---|---|---|
| 1 | Do NOT re-decide any locked WS0–WS8 decision. | Re-walked §1–§7 for any restatement of design rationale. Every design claim is §-ref-shaped (composition §X.X; scoring §X.X; api §X.X; migration §X.X; deployment §X.X; gap-NN §X). Zero rationale restatements. | **PASS** |
| 2 | Do NOT propose new design — planning phase is closed. | The three §6.3 implementation-phase-tracked items are doc-hygiene fixes (heading-style, narrative-count typo, api §3.1 doc-edit), not new design. The §7 cadence recommendation is a process recommendation, not a contract addition. | **PASS** |
| 3 | Do NOT gate on calendar — gate on artifact coherence per PLAN.md §Sequencing. | §1 verdict is conditioned on artifact-coherence (§4 audit + §5 deferral assessment), not on calendar. §7 cadence explicitly says "no dates; gate on artifacts." | **PASS** |
| 4 | Do NOT require v2 design as a v1 prerequisite (composition §1.1; deployment §10). | §3.3 evades failure mode #3 without invoking v2; §5 #10 + #11 explicitly classify v2 as deferred-but-coherent. The v0→v1 cutover (IMPL §4) does not require v2 design. | **PASS** |
| 5 | (added per ENV constraint) Do NOT edit `/Users/johnhain/Coding_Projects/scns`. | This artifact lives in `/Users/johnhain/Coding_Projects/lethe/docs/`. No edits to scns repo. | **PASS** |
| 6 | (added per IMPL parity) Do NOT introduce numeric defaults of own. | Every numeric reference (15 min gate interval; 30 s heartbeat; 60 s break; 24 h TTL; 7-day ceiling; 2× heartbeat multiplier; 5% provenance round-trip sample; 20% strict-stratum operator share; 10k labeled pairs; 3 consecutive months; 1.5× gate alarm) is §-ref'd to upstream WS. | **PASS** |

Six items pass.

---

## §9 Closing

**Verdict: GO.**

The planning phase has produced a true-and-practical path to v1. All nine
workstreams plus their QA + nit-fix passes are on `origin/main`. The
40/44-actually-44/44-locked-decision realization in IMPLEMENTATION.md §6.2
is structurally complete (only a narrative-count typo follow-up). Five
high-stakes cross-WS seams are coherent. Thirty deferrals are bounded,
named, and not load-bearing for the charter. Three charter §North-star
failure modes are evaded with cited evidence (one with a measurement-side
caveat that is honest, named, and tracked). The implementation phase
inherits a clean v1 scope.

**Next surface:** start P1 of IMPLEMENTATION.md (storage-substrate
scaffolding for S1–S5, with tenant-init and integrity-lint hooks).
The three §6.3 implementation-phase-tracked items can be folded in
opportunistically; none gates P1.

The planning phase is closed by HANDOFF §17 (next commit).
