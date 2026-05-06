# IMPLEMENTATION — Lethe v1 phased work plan

**Status:** Final planning-phase deliverable (PLAN.md §Deliverables item 4).
**Audience:** the engineer (or coding agent) who has read all of `docs/00-charter.md` through `docs/08-deployment-design.md` plus `HANDOFF.md` §1–§15 and now needs to know **in what order** to write **what files**, with **what tests gating each phase**.
**Not for:** re-deciding any locked WS0–WS8 decision; specifying byte-level code or schema migrations beyond the design docs; designing v2.

---

## §0 Frame

### §0.1 What this document owns

1. **Phase ordering** for the v1 build (§1).
2. **Per-phase file-level change list** (§2 — paths to create or modify, grouped by store / module).
3. **Per-phase exit-criteria / acceptance tests** (§2 — gating eval slices, integration paths, gap-coverage tests; gated on artifacts not dates per PLAN.md §Sequencing).
4. **Phase DAG** with explicit edges (§2 + §8.b).
5. **Risk register** with prioritization rubric and mitigation phase per row (§3).
6. **Cutover gate** definition (§4 — v0→v1 first production deployment; distinguished from the v1→v2 path).
7. **Index of post-v1 deferrals** consolidated from upstream WS / HANDOFF residuals (§5).
8. **Bidirectional traceability** between phases and locked WS0–WS8 decisions (§6).
9. **Anti-checklist** of things this document MUST NOT do (§7).
10. **Verification audits** run in-doc (§8).

### §0.2 What this document does NOT own

1. **Re-deciding any WS0–WS8 locked decision.** The cascade record is HANDOFF §13 + each WS-QA + each WS-nit-fix.
2. **Byte-level code** (function bodies, schema DDL, exact SQL queries). Design docs spec contracts; bytes are the implementer's call.
3. **SCNS runtime path.** HANDOFF §10 is binding: Lethe stands on its own; no SCNS data source, no SCNS substrate, no SCNS shim in the runtime.
4. **Cross-deployment Lethe→Lethe migration.** Deferred per migration §10 + deployment §8.1 + §5 of this doc.
5. **Auth mechanism.** Deployment §2.3 specifies the contract (principal-extraction); the mechanism (OAuth / JWT / mTLS) is the implementer's call.
6. **Wire-format library.** Deployment §2.4 specifies JSON over HTTP/1.1 + optional MCP framing; the HTTP framework choice is the implementer's call.
7. **Metrics-export mechanism.** Deployment §5.4 names the must-emit signals; the exporter (Prometheus / OTLP / log-scraper) is per-deployment.
8. **v2 design.** Multi-tenant runtime, learned scorer, 2PC for cross-host T1, cross-deployment restore — all v2 surface, all out of scope.

### §0.3 Binding upstream invariants (cited; do not work around)

- **I-1.** Single-tenant-per-deployment v1 baseline. (composition §1.1 + §5.2; deployment §1)
- **I-2.** No SCNS runtime dependency. (HANDOFF §10 + §11.5 + §12.5; api §0.3 #1)
- **I-3.** Markdown is dual-audience (LLM + human). (HANDOFF §13; composition §1.1)
- **I-4.** Bi-temporal validity filter applied **pre-retriever**, not post-rerank. (api §2.1 step 1; scoring §4.1)
- **I-5.** Every write verb has a mandatory `idempotency_key`. 24 h TTL default; 7-day enforced ceiling. (api §1.2; deployment §4.3)
- **I-6.** `recall_id` derivation is deterministic uuidv7 keyed on `(tenant_id, ts_recorded, query_hash)`. (api §1.4)
- **I-7.** `forget(purge)` writes retention proof to S5 **before** the delete commits. (gap-08 §3.6)
- **I-8.** Episode-id is non-null on every fact; `provenance.source_uri` carries the originating reference. (gap-05 §6)
- **I-9.** `capture_opt_in_trace` is the only path for trace data into the eval-candidate pool. (api §4.1)
- **I-10.** `tenant_isolation_breach` is a P0 alarm; cross-tenant reads return 404 (not "empty"). (deployment §5.5; composition §5.2)
- **I-11.** Six `consolidate_phase` emit-points fire in canonical order: `extract → score → promote → demote → consolidate → invalidate`. (api §3.1; scoring §8.1)
- **I-12.** `health()` extensions are additive only; no breaking change to the published api §4.4 schema. (deployment §5.2)
- **I-13.** Migration calls only existing api verbs (no `migrate_*` verb on the wire). (migration §0.3 + §8)

---

## §1 Phase ordering rationale

Bottom-up. Each layer's contract surface is fully landed before any layer above it begins its acceptance tests. Five-store decomposition (composition §2) drives the substrate ordering; api verb dependencies (api §2–§4) drive the runtime ordering; deployment surface (deployment §1–§10) closes the operator-side contracts; migration (migration §3) and eval harness (eval §4–§8) plug in last; cutover is the terminal gate.

```
Substrate            P1  storage scaffolding (S1–S5 schemas + tenant-init)
                          │
Write path           P2  remember + idempotency + provenance + classifier-escape
                          │
Read path            P3  recall / recall_synthesis (bi-temporal filter pre-retrieve;
                          │  RRF + per-class scoring formulas; ledger; preferences prepend)
                          │
Lifecycle core       P4  consolidate loop + scoring tuning (six emit-phases; gravity; ε)
                          │
Lifecycle writes     P5  promote + forget {invalidate|quarantine|purge}; CAS; retention-proof
                          │
Surface completion   P6  peer-messaging + admin / ops verbs (capture_opt_in_trace; audit; health baseline)
                          │
Operator surface     P7  RBAC + transport + rate-limits + observability + escalate-review
                          │
Migration tooling    P8  lethe-migrate + lethe-admin + manifest + phase-gates A/B/C
                          │
Eval wiring          P9  LongMemEval/LoCoMo/DMR replay + chaos + drift + opt-in trace ingest
                          │
Cutover              P10 first production deployment + v2_gate gauges initialized
```

PLAN.md §Sequencing diagram puts WS0→WS8 in the design dimension; this DAG puts P1→P10 in the build dimension. They do not commute: design WS gating is artifact-on-artifact ("WS5 needs WS3"); build phase gating is contract-on-test ("P3 needs the bi-temporal filter green on DMR sanity"). Both forms of gating are artifact-not-date per PLAN.md §Sequencing.

The bottom-up shape is forced by three locked constraints: (a) the read path can't be tested until the write path can produce facts (P2 → P3); (b) consolidate can't run until both paths exist (P3 → P4); (c) deployment can't gate on rate-limits unless the verbs they protect exist (P6 → P7). Top-down was considered and rejected — would require stub-everywhere infrastructure that the implementer would then have to rip out.

WS sources by phase:

| Phase | Primary WS | Secondary WS |
|---|---|---|
| P1 | composition | gap-08 |
| P2 | api §3.1, gap-05, gap-12 | composition §4, gap-08 |
| P3 | api §2, scoring §3–§5 | composition §3, gap-09 |
| P4 | scoring §3.5 + §6, gap-01 | gap-13, deployment §4.1–§4.2 |
| P5 | api §3.2–§3.3, gap-11 | gap-08 §3.6, gap-04 |
| P6 | api §2.3–§2.4 + §3.4 + §4, gap-10 | eval §4.6 |
| P7 | deployment §2 + §3 + §5 + §6 | api §0.2 (deferred items) |
| P8 | migration §3 + §6.6 | deployment §7 + §8 |
| P9 | eval §4–§8, gap-14 | scoring §8.4 + §8.6 |
| P10 | composition §1.1, deployment §1 + §10 | scoring §8.6 |

---

## §2 Phases

Each phase has: **Goal**, **File-level changes** (paths), **Exit gates** (artifact tests; gated, not dated), **Upstream §-refs**, **DAG edges**, **OOS-for-this-phase**.

File-paths use the project's existing layout: `src/lethe/<store>/`, `src/lethe/api/`, `src/lethe/runtime/`, `cli/`, `scripts/eval/`, `tests/`. Where a path is not yet conventionalized, I prefix with `src/lethe/` and let the implementer rename if required — the path is a routing hint, not a binding location.

### §2.1 P1 — Storage substrate scaffolding

**Goal.** Bring up S1–S5 with schemas, tenant-init, and integrity-lint hooks. No verbs land yet; the substrate must exist so P2 has a target.

**File-level changes (create):**
- `src/lethe/store/s1_graph/{__init__,schema,client}.py` — Graphiti client wrapper; entity-type registry; episode shape; bi-temporal stamp helpers (`valid_from / valid_to / recorded_at`).
- `src/lethe/store/s2_meta/{__init__,schema,migrations}.py` — SQLite (WAL) connection helper; tables: `recall_ledger`, `utility_events`, `promotion_flags`, `consolidation_state`, `extraction_log`, `tenant_config`, `scoring_weight_overrides`, `review_queue`, `audit_log`, `idempotency_keys`.
- `src/lethe/store/s3_vec/{__init__,client}.py` — sqlite-vec (single-tenant default) adapter; embedding-key shape `(node_id | edge_id | episode_id)`; ANN configuration knob.
- `src/lethe/store/s4_md/{__init__,layout,frontmatter}.py` — filesystem layout under `<storage_root>/<tenant_id>/{s4a/,s4b/}`; YAML frontmatter parse/serialize; stable-URI minting.
- `src/lethe/store/s5_log/{__init__,writer}.py` — append-only consolidation log; SQLite-backed table or `log.md` per dream-daemon precedent (operator config).
- `src/lethe/runtime/tenant_init.py` — composition §3.5 bootstrap: create empty stores; seed default config; emit `health()`-ready signal.
- `src/lethe/audit/integrity.py` — hooks for `lethe-audit lint --integrity` (gap-08 §3.5) — placeholder lint registry; concrete lints land in P2/P5/P8.
- `cli/lethe-audit` — entry-point stub wired to `src/lethe/audit/integrity.py`.

**Tests / exit gates:**
- All five store schemas create cleanly from empty tenant root (per-store smoke).
- `lethe-audit lint --integrity` returns clean on empty tenant.
- Tenant-init bootstrap (composition §3.5) end-to-end: empty root → all five stores present → preferences-prepend path returns empty.
- No api verb is exposed yet; importing `src/lethe/api/` raises `NotImplementedError` by design.

**Upstream §-refs.** composition §2 (S1–S5 ownership matrix); composition §3.5 (tenant-init); gap-08 §3.4–§3.5 (integrity-lint contract).

**Depends on.** None (root of DAG).
**OOS for this phase.** All verbs (P2+); embedding generation pipeline (P3); consolidation scheduler (P4); review queue actions (P7).

### §2.2 P2 — Write path (`remember`)

**Goal.** Land the canonical write. Idempotency, provenance, classifier escape, and the `remember` event emitter all wire here.

**File-level changes (create / modify):**
- `src/lethe/api/remember.py` — verb implementation: input validation; idempotency-key check (24 h TTL via `s2_meta.idempotency_keys`); classifier dispatch (gap-12); episode persistence to S1 + extraction-log to S2; provenance envelope enforcement (api §1.5; gap-05 §3); response envelope (api §3.1 — `episode_id, idempotency_key, classified_intent, retention_class, accepted, escalated, ack, next_consolidate_at`).
- `src/lethe/runtime/classifier/{__init__,intent_classifier}.py` — gap-12 §3 7-class taxonomy (`drop, reply_only, peer_route, escalate, remember:fact, remember:preference, remember:procedure`); caller-tagged-intent honored unless classifier objects ≥0.8 (api §3.1); `force_skip_classifier=true` path (deployment §6.3) — gated to `tenant_admin` (P7 wires the auth check; here the parameter is plumbed and the audit row is written).
- `src/lethe/runtime/provenance.py` — envelope shape (api §1.5); two-step materialization for peer-message; `derived_from` set on peer-materialized facts (gap-05 §3.2); `provenance_dropped` surfaced.
- `src/lethe/runtime/idempotency.py` — uuidv7-shaped key validation; replay→200 with stored response; conflict→409; mandatory on every write (api §1.2). 7-day ceiling rejection at startup is wired in P7.
- `src/lethe/runtime/events.py` — emit-point library; first event landed: `remember`. Sink defaults to `scripts/eval/metrics/emitter.py::emit_score_event` (per scoring §8.4 — internal sink).
- `src/lethe/audit/lints/provenance_required.py` + `provenance_resolvable.py` (gap-05 §3.5) — registered into `lethe-audit lint --integrity`.
- `tests/api/test_remember.py` + `tests/runtime/test_classifier.py` + `tests/runtime/test_idempotency.py` + `tests/runtime/test_provenance.py`.

**Tests / exit gates:**
- Idempotency-key coverage audit (api §7.2): `remember` is a write verb, has mandatory key — PASS.
- Provenance round-trip: every persisted episode has non-null `episode_id` and resolvable `provenance.source_uri` (gap-05 §6).
- Classifier escape: `escalate`-class input returns 422 with `staged_for_review` ack and a row in `s2_meta.review_queue` (final review actions are P7).
- Replay invariant: same `idempotency_key` within TTL returns the originally-stored response with `ack=idempotency_replay` (api §1.2).
- `force_skip_classifier=true` parameter accepted; audit-log row written; auth check stubbed (P7 enforces).
- `remember` event fires once per accepted write; envelope contains `tenant_id, model_version, weights_version, contamination_protected` (scoring §8.2).

**Upstream §-refs.** api §1.2, §1.5, §3.1, §7.2; gap-05; gap-08 §3.6; gap-12 §3 + §6; deployment §6.3; scoring §8.2 + §8.4.

**Depends on.** P1.
**OOS for this phase.** `recall` (P3); promote / forget (P5); peer-message materialization (P6); auth enforcement of `force_skip_classifier` (P7).

### §2.3 P3 — Read path (`recall` + `recall_synthesis`)

**Goal.** Land both recall surfaces. Bi-temporal filter pre-retrieve (I-4); per-class scoring formulas (math from scoring §3–§5; tuning is P4); preferences prepend with 10 KB cap; deterministic `recall_id`; ledger write; emit `recall` × top-k.

**File-level changes (create / modify):**
- `src/lethe/api/recall.py` — algorithm per api §2.1: (1) bi-temporal filter; (2) classify; (3) weight-tuple; (4) parallel S1+S2+S3 retrieve; (5) RRF; (6) post-rerank with `w_intent` and `w_utility`; (7) truncate to `budget_tokens`; (8) provenance enforcement; (9) ledger write to `s2_meta.recall_ledger`; (10) preferences prepend (10 KB cap from S4a `kind: preference` pages); (11) emit `recall` × top-k.
- `src/lethe/api/recall_synthesis.py` — distinct path (api §2.2) returning S4a markdown pages by stable URI or query; emits `recall` events with `path=synthesis` marker; `fact_ids` set to S4a page-ids (uuidv7-hashed stable URIs).
- `src/lethe/runtime/recall_id.py` — uuidv7 derivation per api §1.4 (48-bit ts + 4-bit ver + deterministic 74 bits from `sha256(tenant_id ‖ "rec" ‖ ts_recorded ‖ query_hash)`; discriminant matches the migration §2.3 pattern).
- `src/lethe/runtime/scoring/{__init__,recency,connectedness,utility,gravity,contradiction,per_class}.py` — formulas from scoring §3–§5: per-term derivations (Cognitive Weave decay; HippoRAG PPR with 2-hop subgraph cap + degree-percentile fallback; utility weighted aggregate; MaM gravity as demotion-floor multiplier; log-dampened ε). Per-class dispatch (scoring §5) — explicit per-class formulas for episodic-fact / preference / procedure / narrative.
- `src/lethe/runtime/retrievers/{semantic,lexical,graph,rrf}.py` — three retrievers + RRF combiner (k=60 default per scoring §4); composition §3.1 lexical fallback survives S3 outage.
- `src/lethe/runtime/bitemporal_filter.py` — applied **before** any retriever (I-4); covers `valid_from / valid_to / recorded_at`; `T_purge=90 d` grace window.
- `src/lethe/runtime/preferences_prepend.py` — gap-09 §6 unconditional include up to 10 KB; recency-of-revision ordering inside cap; `preferences_truncated` flag exposed.
- `src/lethe/runtime/events.py` — adds `recall` event type (one per top-k) with `recall_id` join key.
- `tests/api/test_recall.py` + `tests/api/test_recall_synthesis.py` + `tests/runtime/test_bitemporal_filter.py` + `tests/runtime/test_preferences_prepend.py` + `tests/runtime/test_recall_id_determinism.py`.
- `scripts/eval/run_eval.py` — wire DMR adapter (`scripts/eval/adapters/dmr.py`) for sanity-replay smoke test.

**Tests / exit gates:**
- **DMR sanity replay** (eval §5.7) — saturated benchmark used as floor; passing means the read path returns *something* sensible.
- Bi-temporal filter unit test: invalid-window facts excluded **before** any retriever runs (no score-then-filter; no skip on small stores).
- `recall(k=0)` returns preferences-only response with `recall_id`; zero `recall` events emitted.
- Preferences prepend: 10 KB cap honored; `preferences_truncated` exposed when capped; ordering is recency-of-revision.
- `recall_id` determinism: same `(tenant_id, ts_recorded, query_hash)` → same `recall_id` (replay invariant for scoring §8.3).
- Per-class scoring: each of the four persistent shapes uses its declared formula (scoring §5); non-persistent classifier outputs (`reply_only, peer_route, drop, escalate`) are noted out-of-scope.
- `recall_synthesis` emits `recall` events with `path=synthesis`; `fact_ids` are S4a page-ids.

**Upstream §-refs.** api §1.4, §2.1, §2.1.1, §2.2; scoring §3–§5, §4.1, §8.2, §8.3; composition §3.1, §3.2, §3.5; gap-09 §6.

**Depends on.** P2 (no facts to recall without `remember`).
**OOS for this phase.** Weight tuning beyond the gap-03 §5 candidate (a) defaults (P4); `consolidate_phase` events (P4); `recall_outcome` events from utility-feedback (P9 wires the ingest path; the join-key is plumbed here).

### §2.4 P4 — Consolidate loop + scoring tuning

**Goal.** Six emit-phases fire in canonical order (I-11). Gravity multiplier (Q1 — demotion-floor, not 6th additive term). Log-dampened ε (gap-13). v1 weight defaults (gap-03 §5 candidate (a)). Per-tenant lock with 30 s heartbeat / 60 s break (gap-01 §3.2 + gap-08 §3.4 → deployment §4.2).

**File-level changes (create / modify):**
- `src/lethe/runtime/consolidate/{__init__,scheduler,loop,phases}.py` — main loop; six phases (`extract → score → promote → demote → consolidate → invalidate`); per-phase emit; gate interval 15 min default (deployment §4.1); per-tenant lock w/ 30 s heartbeat (deployment §4.2).
- `src/lethe/runtime/consolidate/extract.py` — extraction from new episodes (calls extraction-confidence log in S2); references gap-06 quality instrumentation (drift detection wires in P9).
- `src/lethe/runtime/consolidate/score.py` — consolidate-time additive scoring per scoring §3 (`score(f) = gravity_mult(f) · [α·type + β·recency + γ·connectedness + δ·utility − ε_eff·contradiction]`).
- `src/lethe/runtime/consolidate/promote.py` + `demote.py` + `invalidate.py` — per-phase logic; emit `promotion_flags` updates to S2; bi-temporal `valid_to` writes to S1; utility-tally freeze on invalidate (scoring §6); revalidate-replay semantics.
- `src/lethe/runtime/consolidate/contradiction.py` — gap-13 §3.1 detection; log-dampened ε amplification; revalidate-on-evidence path.
- `src/lethe/runtime/consolidate/gravity.py` — MaM-style gravity; cascade-cost computation (`O(|N_2hop|)` per fact per consolidate; HANDOFF §11.6 #3 residual — instrumented for batched/cached reformulation if S3 grows beyond ~10⁶ edges).
- `src/lethe/runtime/events.py` — adds `promote, demote, invalidate, consolidate_phase` event types.
- `tests/runtime/test_consolidate_phases.py` + `tests/runtime/test_scoring_appendix_a.py` + `tests/runtime/test_gravity.py` + `tests/runtime/test_contradiction_epsilon.py` + `tests/runtime/test_lock_heartbeat.py`.

**Tests / exit gates:**
- Scoring Appendix A worked-example replay: preference, episodic fact, procedure (with active contradiction) all produce the documented numerical outputs through both surfaces (consolidate + recall).
- All six `consolidate_phase` events fire in canonical order on a synthetic tenant (I-11).
- Gravity demotion-floor unit test (scoring §3.5 Q1): gravity multiplies a tier floor; it is **not** added as a 6th term.
- Log-dampened ε unit test: ε amplifies on repeated contradiction without diverging (gap-13 §3.1).
- Lock heartbeat: 30 s heartbeat extends; 60 s silence breaks the lock; recovery via `lethe-admin lock` path (stub here; fully landed in P8).
- Default weight tuple (`α=0.2, β=0.3, γ=0.2, δ=0.4, ε=0.5`; RRF `k=60`; `w_intent=0.15`; `w_utility` ramp 0→0.2) — matches gap-03 §5 candidate (a).

**Upstream §-refs.** scoring §3, §3.5, §5, §6, §8.1; gap-01 §3.2; gap-08 §3.4; gap-13 §3.1; deployment §4.1, §4.2.

**Depends on.** P3 (consolidate operates over the recall-shaped fact set).
**OOS for this phase.** `forget` cascade and retention-proof (P5); admin trigger `consolidate(force)` (P6); BO sweep for weight tuning (deferred to v1.1 per HANDOFF §11.6 #4).

### §2.5 P5 — Lifecycle write verbs (`promote`, `forget`)

**Goal.** Land the explicit lifecycle writes. `promote` returns an "intended-not-applied" ack. `forget` modes `{invalidate | quarantine | purge}` with alias mapping (`soft → invalidate, deny → quarantine`). Retention-proof-before-delete for purge (I-7). `expected_version` CAS (I-5 partner).

**File-level changes (create / modify):**
- `src/lethe/api/promote.py` — input `(fact_id, reason?, idempotency_key, expected_version)`; response `{flag_id, expected_version_consumed, applies_at_next_consolidate, ack="intended_not_applied"}`; writes to `s2_meta.promotion_flags` (consumed at next P4 consolidate).
- `src/lethe/api/forget.py` — input `(target, mode, reason, idempotency_key, expected_version)`; mode dispatch: `invalidate` → bi-temporal `valid_to=now`; `quarantine` → quarantine flag + estimated `cascade_count` synchronous (final via `audit()`); `purge` → synchronous, retention-proof to S5 **first**, then delete (I-7).
- `src/lethe/runtime/forget/{cascade_estimate,retention_proof,purge}.py` — cascade-count walker; retention-proof envelope (gap-08 §3.6); purge admin-only (auth check stubbed; P7 enforces); rate-limit attach point (P7 enforces).
- `src/lethe/runtime/cas.py` — `expected_version` check; 409 with retry hint; idempotency-replay precedence over CAS (api §1.3).
- `src/lethe/runtime/events.py` — adds `forget` event variants per mode.
- `src/lethe/audit/lints/forget_proof_resolves.py` (gap-08 §3.6) — registered into `lethe-audit lint --integrity`.
- `tests/api/test_promote.py` + `tests/api/test_forget.py` + `tests/runtime/test_cas.py` + `tests/runtime/test_retention_proof_ordering.py`.

**Tests / exit gates:**
- `forget(purge)` retention-proof-before-delete ordering (gap-08 §3.6): inject failure between proof-write and delete; recover with `purge` not-yet-committed but proof present and resolvable.
- `forget(quarantine)` returns synchronous `cascade_count` estimate; `audit()` query post-async returns final count (≥ estimate).
- `expected_version` CAS conflict: stale write returns 409 with retry hint; concurrent `idempotency_key` replay returns 200 (replay precedence).
- Alias mapping accepted: `soft → invalidate, deny → quarantine` documented in §3.3.
- `promote` returns `ack="intended_not_applied"`; flag visible in `s2_meta.promotion_flags`; consumed at next consolidate (P4 round-trip).

**Upstream §-refs.** api §1.3, §3.2, §3.3; gap-04 §3 candidate (a); gap-08 §3.6; gap-11 §3.

**Depends on.** P4 (promote consumed at consolidate; cascade walker uses gravity / connectedness).
**OOS for this phase.** Auth enforcement of admin-only purge (P7); rate-limit cap (P7).

### §2.6 P6 — Peer-messaging + admin / ops verbs

**Goal.** Complete the verb surface. Peer-messaging (sync request/response with async pull-based delivery; gap-10 §3.4–§3.5). `capture_opt_in_trace` (admin, idempotent, revocable + retires previously-ingested cases). `consolidate(force)`, `audit()`, `health()` baseline.

**File-level changes (create / modify):**
- `src/lethe/api/peer_message.py` — sync verb; persists to S2 inbox table; sensitive-class send-time scan returns 422 (gap-10 §6 / gap-11 §3.3); inbox cap 100 unread, oldest non-`query` dropped (gap-10 §3.4); `cap_dropped_since_last_pull` surfaced.
- `src/lethe/api/peer_message_pull.py` + `peer_message_status.py` — async pull (gap-10 §3.5); `mark_read?` parameter; status query by `msg_id`.
- `src/lethe/api/capture_opt_in_trace.py` — admin verb; idempotent action `{enable, revoke}`; revocation queues retirement of previously-ingested cases (eval §4.6 step 1).
- `src/lethe/api/consolidate_force.py` — admin trigger; fires the P4 loop out-of-band; rate-limit attach point (P7).
- `src/lethe/api/audit.py` — operator-readable query (per-tenant unless caller has `audit_global`); query patterns per deployment §5.3.
- `src/lethe/api/health.py` — baseline schema (api §4.4); extensions land in P7.
- `src/lethe/runtime/events.py` — adds `recall_outcome` event type (utility-feedback path; ingest is P9).
- `src/lethe/runtime/inbox.py` — peer-message inbox cap logic; per-recipient ordering.
- `tests/api/test_peer_message.py` + `tests/api/test_capture_opt_in_trace.py` + `tests/api/test_audit.py` + `tests/api/test_health.py`.

**Tests / exit gates:**
- Peer-message inbox cap drops oldest non-`query` (gap-10 §3.4); cap-dropped surfaced on next pull.
- Sensitive-class send-time scan returns 422 with `classifier_escalate` (gap-10 §6 / gap-11 §3.3).
- `capture_opt_in_trace(revoke)` retires previously-ingested cases (eval §4.6 step 1; verified by absence in P9 case-set on next refresh).
- All four message types (`query | info | claim | handoff`) on the wire (gap-10 §3).
- `health()` baseline returns the api §4.4 documented fields.
- `consolidate(force)` triggers P4 loop synchronously and returns ack with run-id.

**Upstream §-refs.** api §2.3, §2.4, §3.4, §4.1, §4.3, §4.4; gap-10 §3, §3.4, §3.5, §6; gap-11 §3.3; eval §4.6.

**Depends on.** P5.
**OOS for this phase.** RBAC enforcement (P7); rate-limit caps (P7); `health()` extensions for migration/escalate/drift/v2_gate (P7).

### §2.7 P7 — Deployment surface (RBAC + transport + observability)

**Goal.** Operator-side contracts land. RBAC (3 roles + capability-to-verb matrix); JSON-over-HTTP/1.1 (+ optional MCP framing); rate-limit table (11 rows); `health()` additive extensions; 8 must-wire alarms; escalate-review pipeline; formal addition of `force_skip_classifier=true` to api §3.1 input schema.

**File-level changes (create / modify):**
- `src/lethe/auth/{__init__,rbac,principal}.py` — three roles (`agent / tenant_admin / operator`); capability map (`forget_purge` on `tenant_admin`; `audit_global` on `operator`; `tenant_admin` on `tenant_admin` + `operator`); principal-extraction contract (deployment §2.3) — mechanism is implementer's choice; tests use a stub provider.
- `src/lethe/transport/http_json/{__init__,server,framing}.py` — JSON over HTTP/1.1; optional MCP framing; verb routing; error taxonomy (api §1.7).
- `src/lethe/transport/mcp/{__init__,server}.py` — MCP variant of the same routing; reuses the same verb implementations.
- `src/lethe/runtime/rate_limit.py` — 11 rows from deployment §3 (recall 30/s; remember 10/s; forget(invalidate|quarantine) 5/s; forget(purge) 10/h-100/d per tenant; peer_message 20/s; consolidate(force) 6/h; capture_opt_in_trace 10/h; escalate-staging 50/d; audit 10/s; health unbounded; per-tenant). Returns 429 with `retry_after`.
- `src/lethe/runtime/idempotency.py` (modify) — startup-time validation of TTL config; reject values >7 days (deployment §4.3).
- `src/lethe/api/health.py` (modify) — additive extensions: `migration_progress, idempotency_fallback_rate, escalation_queue_depth, drift_state, v2_gate.{operator_share, labeled_pairs}`. No field renamed/removed (I-12).
- `src/lethe/runtime/alarms/{__init__,wiring}.py` — 8 must-wire alarms (deployment §5.5): `consolidation_stalled, escalation_queue_depth, idempotency_fallback_high, s3_backfill_stalled, drift_high, degraded_mode_active, forget_purge_rate_spike, tenant_isolation_breach (P0)`. Sink is per-deployment (OOS).
- `src/lethe/runtime/review_queue/{__init__,actions,sla}.py` — review actions (`approve / reject / expire-now`); 24 h SLA; 30 d TTL; `escalated_rejected` terminal status (deployment §6).
- `src/lethe/api/remember.py` (modify) — formal `force_skip_classifier=true` parameter addition (deployment §6.3; HANDOFF §15.5 #5); auth check `tenant_admin` capability; audit-log row.
- `src/lethe/runtime/metrics.py` — 18 must-emit signals (deployment §5.4); exporter pluggable (OOS — implementer's choice).
- `tests/auth/test_rbac.py` + `tests/transport/test_http_json.py` + `tests/runtime/test_rate_limit.py` + `tests/runtime/test_idempotency_ttl_ceiling.py` + `tests/api/test_health_extensions.py` + `tests/runtime/test_alarms.py` + `tests/runtime/test_review_queue.py`.

**Tests / exit gates:**
- Rate-limit caps enforced per deployment §3 table (429 with `retry_after`).
- `force_skip_classifier=true` rejected on `agent` role (403); accepted on `tenant_admin` (200 with audit-log row).
- `tenant_isolation_breach` alarm wires to P0 sink; cross-tenant read returns 404 (not "empty"); auth-missing returns 403 (I-10).
- `health()` schema additive-only audit: every api §4.4 field still present and identically-typed.
- Idempotency-key TTL >7 days rejected at startup (deployment §4.3); within ceiling accepted.
- Review queue: stale row past 30 d TTL → `expired`; manual `expire-now` works; `approve` lands the staged episode as durable; `reject` → `escalated_rejected`.

**Upstream §-refs.** deployment §1, §2, §3, §4.3, §5.2, §5.4, §5.5, §6; api §0.2, §1.6, §1.7, §3.1, §4.4; HANDOFF §15.5.

**Depends on.** P6.
**OOS for this phase.** Migration tooling (P8); eval harness wiring (P9); cutover (P10); metrics-export mechanism (per-deployment); auth-mechanism implementation (per-deployment).

### §2.8 P8 — Migration tooling (`lethe-migrate` + `lethe-admin`)

**Goal.** 12-subcommand `lethe-migrate` CLI mapping 1:1 to migration §3.1 phases / phase-gates. `manifest.jsonl` (atomic-rename on status update). Snapshot UX (`git-tag / fs-copy / zfs-snapshot`). Hard phase-gates A (pre-flight integrity-lint), B (episode-id round-trip), C (post-import provenance + integrity lint). `lethe-audit lint --integrity` operator surface. `lethe-admin lock` recovery.

**File-level changes (create):**
- `cli/lethe-migrate` — entry point.
- `src/lethe/migrate/{__init__,plan,manifest,snapshot,phase_runners,gates}.py` — 14 phase runners; manifest JSONL append-only with atomic-rename status update; snapshot adapters.
- `src/lethe/migrate/mappings/{claude_md,lessons,negative,sessions,daily,weekly_monthly,archive,suppress}.py` — one per migration §2.1 mapping row; each emits a `remember` (and where applicable, a follow-up `forget(invalidate)`).
- `src/lethe/migrate/identifiers.py` — uuidv7-shaped derivations per migration §2.3: idempotency-key with `"idem"` discriminant; episode-id with `"epi"` discriminant; same 48 + 4 + 12 + 2 + 62 bit layout.
- `src/lethe/migrate/heuristic.py` — 3-test conjunction for procedure-vs-narrative classification (migration §3.4); favors narrative on ambiguity.
- `cli/lethe-admin` — entry point; subcommands `lock {list,break,heartbeat-status}`, `audit lint --integrity`.
- `src/lethe/admin/{__init__,lock,backup}.py` — lock recovery surface (gap-08 §3.4); backup posture per store (deployment §8.1).
- `src/lethe/audit/lints/{provenance_required,provenance_resolvable,forget_proof_resolves,episode_id_present,no_dangling_edges}.py` — full lint registry; called by phase-gates A and C.
- `tests/migrate/test_phase_gates.py` + `tests/migrate/test_identifiers_uuidv7.py` + `tests/migrate/test_manifest.py` + `tests/migrate/test_heuristic.py` + `tests/admin/test_lock_recovery.py`.

**Tests / exit gates:**
- All three hard phase-gates halt on simulated failure (migration §3.1 + §6.6.3).
- Provenance round-trip on a 5% sample (migration §6.2): every sampled episode has `provenance.source_uri = scns:<shape>:<id>` resolvable and `episode_id` matches the deterministic derivation.
- Recall-determinism probe: ~50 queries pre/post-migration; fact-id-set diff within 5% drift tolerance (migration §6.3; deployment §4.6).
- 9/9 mapping-row write paths have idempotency keys (migration §6.6.2 audit).
- Identifier derivation: `idempotency_key` and `episode_id` over the same source bytes do not collide (discriminant separation, migration §2.3).
- `lethe-admin lock break` recovers from a stuck lock; `lethe-audit lint --integrity` invocation surface matches Phase-gates A + C calls.

**Upstream §-refs.** migration §0.3, §2.1, §2.3, §3.1, §3.4, §6.2, §6.3, §6.6; deployment §7, §8.1, §8.3; gap-08 §3.4, §3.5.

**Depends on.** P7 (migration calls only existing api verbs over the runtime surface; rate-limit + auth are operator-configured per migration §4).
**OOS for this phase.** Cross-deployment Lethe→Lethe migration (deferred per migration §10 + §5 of this doc); `vault.db` consumption (deferred); manifest HTML renderer (per-deployment).

### §2.9 P9 — Eval harness wired in

**Goal.** LongMemEval primary + LoCoMo secondary + DMR sanity replays running end-to-end via `scripts/eval/`. `lethe_native::loader.capture_opt_in_trace` ingest path live (paired with the api §4.1 external verb). Chaos harness exercises every composition §7 row including the two-stores-down §7.1 matrix. Drift detector (5%/h continuous; monthly re-eval; quarterly fresh adversarial slice; annual eval-set bump). Headline-tag emitter renders preliminary-tag wording at v1.0 (eval §3.4 invariant).

**File-level changes (modify / extend):**
- `scripts/eval/run_eval.py` — full pipeline: case-set load → adapter dispatch → metric collection → emitter render. Already stubbed in WS4.
- `scripts/eval/adapters/longmemeval.py` — primary slice runner (eval §5).
- `scripts/eval/adapters/locomo.py` — secondary signal (informative; not gate-blocking per D2).
- `scripts/eval/adapters/dmr.py` — sanity floor (already exercised in P3).
- `scripts/eval/lethe_native/loader.py::capture_opt_in_trace` — ingest impl (contract was set in WS4); pairs with api §4.1 verb landed in P6.
- `scripts/eval/metrics/emitter.py::emit_score_event` + `render_headline_tag` — internal sink + headline-tag rendering (scoring §8.4; eval §3.4).
- `scripts/eval/chaos/faults.py` — exercise every composition §7 row including two-stores-down §7.1.
- `scripts/eval/drift/{__init__,detector,cadence}.py` — 5%/h continuous sample; monthly held-set re-eval; quarterly fresh adversarial slice; annual eval-set version bump (gap-14 §5(3); deployment §4.5).
- `scripts/eval/contamination/checks.py` — `contamination_protected` gate (already stubbed in WS4); enforce on every emit.
- `tests/eval/test_run_eval_e2e.py` + `tests/eval/test_chaos_two_stores_down.py` + `tests/eval/test_drift_detector.py` + `tests/eval/test_capture_opt_in_trace_ingest.py` + `tests/eval/test_headline_tag_emitter.py`.

**Tests / exit gates:**
- LongMemEval primary slice runs end-to-end; report rendered with preliminary-tag wording.
- LoCoMo runs in the same pipeline; report rendered (informative; not gate-blocking).
- Chaos harness exercises every composition §7 row including the two-stores-down §7.1 matrix; degraded-mode signaling correct in `health()`.
- Drift detector flags a synthetic 12% drift; alarm path lights `drift_high`.
- `capture_opt_in_trace(enable)` flows trace data into the ingest pool; `(revoke)` retires it.
- Headline-tag emitter renders the v1.0 preliminary-tag wording on every public report (eval §3.4 invariant).
- No emit bypasses `contamination_protected` gate.

**Upstream §-refs.** eval §3.4, §4.6, §5, §6, §7, §8; scoring §8.4, §8.6; gap-14 §5(3); deployment §4.5, §5.5; composition §7, §7.1.

**Depends on.** P7 (rate-limits + RBAC must exist for `capture_opt_in_trace` admin path) and P8 (chaos harness uses the lock-recovery surface).
**OOS for this phase.** Reviewer-recruitment workflow for the 35% adversarial slice (HANDOFF §10.6 / WS8 deferred); v1.1 BO sweep for weight tuning (HANDOFF §11.6 #4).

### §2.10 P10 — Cutover (first production deployment)

**Goal.** Single-tenant-per-deployment v1 baseline brought up. Both `v2_gate` gauges live and reporting in `health()` (NOT yet GREEN — that is the v1→v2 path, not the v0→v1 cutover). Deployment §9 degraded-mode playbook validated end-to-end on staged failure. 3-month soak begins for any future v1→v2 path.

**File-level changes (create / modify):**
- `docs/RUNBOOK.md` — operator runbook (per-deployment; the file lives in the deployed instance's repo, not the lethe library repo). Path here is illustrative.
- `src/lethe/runtime/v2_gate.py` — gauges feed `health().v2_gate.{operator_share, labeled_pairs}` (deployment §10; scoring §8.6). Always reports; GREEN status requires both ≥20% strict-stratum operator share AND ≥10k labeled `(recall, outcome)` pairs sustained for 3 consecutive months (deployment §10).
- (no new src files; this phase is integration + deployment + soak, not new modules)
- `tests/integration/test_full_lifecycle.py` — end-to-end: `remember` → wait for consolidate → `recall` returns the expected fact with score ≥ threshold → `forget(invalidate)` → `recall` excludes it.
- `tests/integration/test_degraded_modes.py` — every deployment §9 row simulated; operator-action column verified.

**Tests / exit gates:**
- All P1–P9 phase gates green on a staged production-shaped tenant.
- Deployment §9 degraded-mode playbook validated end-to-end (15 rows including two-stores-down §7.1).
- `health().v2_gate.operator_share` reports a number (likely 0% at v0→v1 cutover; that is correct — `capture_opt_in_trace` opt-ins drive it upward over time).
- `health().v2_gate.labeled_pairs` reports a count.
- 3-month soak monitoring active; the soak counter resets on either gauge dipping below threshold (HANDOFF §15.5 reset semantics under partial-month outages is deferred to v1.x — soak counts only fully-GREEN months).
- v1 baseline declared production-ready by operator sign-off.

**Upstream §-refs.** composition §1.1; deployment §1, §9, §10; scoring §8.6; HANDOFF §15.3 decision #14.

**Depends on.** P9.
**OOS for this phase.** v2 multi-tenant runtime design (deferred); cross-deployment restore (deferred); fleet-scale wire-format re-evaluation (deferred).

---

## §3 Risk register

Prioritization rubric:
- **P0** = project-blocking. Failure here means v1 doesn't ship.
- **P1** = v1-quality. Failure ships a degraded v1 that fails the charter's "true and practical" test.
- **P2** = deferrable. Degrades gracefully or is post-v1 by design.

The implementer should re-evaluate priority as evidence accumulates; the rubric is the durable surface, the assignments are starting points.

| ID | Risk | Priority | Mitigation phase | Source |
|---|---|---|---|---|
| R1 | Markdown write amplification at scale | **P0** | P1 + P3 | gap-07; PLAN gap #3 |
| R2 | Crash-mid-write corruption | **P0** | P2 + P5 + P8 | gap-08 §3.5, §3.6 |
| R3 | Provenance loss | **P0** | P2 + P5 + P8 | gap-05 §3, §6 |
| R4 | Tenant isolation breach | **P0** | P7 | composition §5.2; deployment §5.5; locked WS8 #8 |
| R5 | Scoring weight miscalibration | **P1** | P4 + P9 | gap-03 §5; scoring §7 |
| R6 | Utility-feedback signal loss | **P1** | P3 + P6 + P9 | gap-02; HANDOFF §10.5 |
| R7 | Intent classifier mis-routes | **P1** | P2 + P7 | gap-12 §3, §6 |
| R8 | Idempotency-key TTL edge cases | **P1** | P2 + P7 + P8 | HANDOFF §14.6; deployment §4.3 |
| R9 | Contradiction oscillation at conflict density >1/week | P2 | P4 | gap-13 §3.1 |
| R10 | Peer-message UX bloat | P2 | P6 | gap-10 §3 |
| R11 | Eval-set confirmation bias | P2 | P9 | gap-14 §5 |
| R12 | Non-factual scope creep | P2 | P3 | gap-09 §3, §7 |
| R13 | Extraction-quality drift | P2 | P9 | gap-06; HANDOFF §15.5 |
| R14 | Multi-agent concurrency at fleet scale | P2 | P7 (v1 stop-gap) | gap-04; HANDOFF §15.5 (v2 deferred) |
| R15 | Forgetting-as-safety enforcement gaps | P2 | P5 | gap-11 §3 |
| R16 | Retention-engine tuning | P2 | P4 (v1 bets) | gap-01 §3.2; deployment §4.1, §4.2 |

**Cross-phase mitigation notes.**

- R2 spans P2 (idempotency replay invariant), P5 (retention-proof-before-delete), P8 (`lethe-audit lint --integrity` Phase-gates A + C). Each phase closes one slice.
- R3 spans P2 (envelope enforcement on write), P5 (forget-proof resolution), P8 (provenance round-trip on 5% sample at Phase-gate B/C).
- R6 spans P3 (`recall_outcome` join-key plumbed), P6 (`capture_opt_in_trace` admin verb), P9 (ingest path live). The v1.0 strict stratum has empty operator share; this is an accepted deferral cost (HANDOFF §10.5), not a v1 blocker — hence P1 not P0.
- R8: 24 h default + 7 d enforced ceiling closes HANDOFF §14.6's TTL-extension residual. `audit(provenance.source_uri=...)` fallback in P8 covers >24 h migration runs.
- R14 (v1): `single_writer_per_tenant=true` is the migration default (gap-04 §4 stop-gap; deployment §1). v2 multi-writer concurrency is HANDOFF §15.5 deferred and out of scope for this implementation plan.

---

## §4 Cutover gate

The v0→v1 cutover is the **first production deployment** of a single-tenant-per-deployment v1 baseline (composition §1.1; deployment §1). It is **not** the v1→v2 cutover (deployment §10 + scoring §8.6; explicitly deferred per §5 below).

Conditions for v0→v1 cutover:

1. All P1–P9 phase gates green on a staged production-shaped tenant (per §2 exit criteria).
2. Eval slices pass per WS4 thresholds: DMR sanity floor met (P3); LongMemEval primary slice runs end-to-end with preliminary-tag wording (P9).
3. Deployment §9 degraded-mode playbook validated end-to-end on staged failure (P10).
4. `health().v2_gate.{operator_share, labeled_pairs}` gauges initialized and reporting (NOT GREEN — that's the v1→v2 path).
5. Operator sign-off on the runbook (per-deployment; outside the lethe library repo).

The 3-month soak rule (deployment §10) gates v1→v2, not v0→v1. At cutover, the soak counter starts at zero. Soak counts only fully-GREEN months (HANDOFF §15.5 reset-semantics-under-partial-month-outages is deferred to v1.x).

Cross-references: composition §1.1 (single-tenant-per-deployment baseline); deployment §1 (topology) + §10 (v1 → v2 entry-criteria gate); scoring §8.6 (v2 gates).

---

## §5 Post-v1 deferrals

Index of every "deferred" item across upstream WS, with citation.

| Deferral | Source | Phase that would close it (post-v1) |
|---|---|---|
| Cross-deployment Lethe→Lethe restore | deployment §8.1; HANDOFF §15.5 | future migration spec |
| Cross-deployment Lethe→Lethe migration spec | migration §10; HANDOFF §14.6 | future migration spec |
| 2PC for cross-host T1 | gap-08 §5; HANDOFF §15.5 | v2 |
| v2 multi-tenant runtime | composition §1.1; deployment §10; HANDOFF §15.5 | v2 design WS |
| Metrics-pipeline implementation (Prometheus / OTLP / log-scraper) | deployment §5.4; HANDOFF §15.5 | per-deployment / operator-tooling |
| Review-surface HTML implementation | deployment §6.2; HANDOFF §15.5 | operator-tooling |
| `lethe-migrate` CLI bytes | migration §3 (contract); deployment §7; HANDOFF §15.5 | operator-tooling (post-WS8) |
| `lethe-admin` CLI bytes | deployment §8.3; HANDOFF §15.5 | operator-tooling |
| `emit_score_event` impl | scoring §8.4; api §4.2; HANDOFF §11.6, §12.6 | wired in P9 (sink); contract was set WS5 |
| `capture_opt_in_trace` external verb impl | api §4.1; HANDOFF §12.6 | wired in P6 |
| `vault.db` consumer | migration §1.1, §8; HANDOFF §14.6 | future migration spec or v1.x |
| Classifier accuracy upgrade (gap-12 → LLM) | migration §10 §3.4; HANDOFF §15.5 | v1.x post-cutover instrumented |
| RBAC management API verb | deployment §2.1; HANDOFF §15.5 | v1.x |
| Backup quiesce automation | deployment §8.1; HANDOFF §15.5 | operator-tooling |
| "3 consecutive months" reset semantics under partial-month outages | deployment §10; HANDOFF §15.5 | v1.x refinement |
| Formal addition of `force_skip_classifier=true` to api §3.1 | deployment §6.3; HANDOFF §15.5 | wired in P7; api §3.1 doc edit pending |
| BO sweep for scoring weights | gap-03 §5 candidate (b); HANDOFF §11.6 #4 | v1.1 |
| Per-tenant retune | scoring §7; HANDOFF §11.6 | v1.x post-`capture_opt_in_trace` data |
| Reviewer-recruitment workflow for adversarial 35% slice | eval §10.6; HANDOFF §10.6 | WS8 / project-ops |
| Drift detector cadence integration with deploy-cadence | deployment §4.5; HANDOFF §10.6 | per-deployment |
| Daily-block source-id collision under multi-snapshot migration | migration §10 | operator-tooling |
| Procedure-vs-narrative heuristic accuracy floor | migration §10; HANDOFF §14.6 | operator-tooling |
| Phase 9 async-drain volume threshold | migration §10; deployment §4.7 | per-deployment |
| Phase 11 S3 backfill duration & progress UX | migration §10; HANDOFF §14.6 | operator-tooling |
| Sensitive-content escalation review workflow at scale | migration §5.1; deployment §6; HANDOFF §12.6 | WS8 / project-ops |
| Manifest UX surface (CLI / JSON / HTML) | migration §10; HANDOFF §14.6 | operator-tooling |
| Wire-format re-evaluation at v2 fleet scale | deployment §2.4; HANDOFF §15.5 | v2 |
| Disk thresholds at fleet scale | deployment §8.4; HANDOFF §15.5 | v2 |

---

## §6 Traceability matrix

### §6.1 Forward direction — phase × workstream

For each phase, the WS contracts implemented:

| Phase | composition | scoring | api | migration | deployment | eval | gap briefs |
|---|---|---|---|---|---|---|---|
| P1 | §2 (S1–S5), §3.5 | — | — | — | — | — | gap-08 §3.4–§3.5 |
| P2 | §4.1, §6 | §8.2, §8.4 | §1.2, §1.5, §3.1, §7.2 | — | §6.3 (force_skip plumbed) | — | gap-05, gap-08 §3.6, gap-12 |
| P3 | §3.1, §3.2, §3.5 | §3–§5, §4.1, §8.2, §8.3 | §1.4, §2.1, §2.1.1, §2.2 | — | — | §5.7 (DMR sanity) | gap-09 §6 |
| P4 | §4.4 | §3, §3.5, §5, §6, §8.1, §8.6 (gauges only) | §3.1 (consolidate_phase emit) | — | §4.1, §4.2 | — | gap-01 §3.2, gap-13 §3.1 |
| P5 | §4.2, §6 | — | §1.3, §3.2, §3.3 | — | — | — | gap-04 §3, gap-08 §3.6, gap-11 §3 |
| P6 | §3.3 | §8.4 (sink) | §2.3, §2.4, §3.4, §4.1, §4.3, §4.4 | — | — | §4.6 | gap-10 §3, gap-11 §3.3 |
| P7 | §5.2, §7 | — | §0.2, §1.6, §1.7, §3.1 (force_skip), §4.4 | — | §1, §2, §3, §4.3, §5.2, §5.4, §5.5, §6 | — | — |
| P8 | §3.5 | — | §1.2, §1.5, §3.1, §3.3, §4.1 | §0.3, §2.1, §2.3, §3.1, §3.4, §6.2, §6.3, §6.6 | §7, §8.1, §8.3 | — | gap-08 §3.4, §3.5 |
| P9 | §7, §7.1 | §8.4, §8.6 | §4.1 | — | §4.5, §4.6, §5.5 | §3.4, §4.6, §5, §6, §7, §8 | gap-14 §5(3) |
| P10 | §1.1, §9 | §8.6 | §4.4 | — | §1, §9, §10 | — | — |

### §6.2 Reverse direction — locked decisions → realizing phase

Drawn from each WS's "Decisions locked" list in HANDOFF §11.3 (WS5; 7 implicit decisions), §12.3 (WS6; 9), §14.3 (WS7; 10), §15.3 (WS8; 14), plus HANDOFF §13 (markdown audience cascade).

| WS | # | Locked decision (abbrev) | Realizing phase |
|---|---|---|---|
| WS3 | — | Single-tenant-per-deployment v1 baseline (composition §1.1) | P10 (cutover); P1 (substrate isolation) |
| WS3 | — | Five-store decomposition S1–S5 (composition §2) | P1 |
| WS3 | — | Hybrid layered topology Candidate C (composition §8.3) | P1 + P3 |
| WS3 | — | Markdown dual-audience (composition §1.1; HANDOFF §13 cascade) | P3 (recall_synthesis); P8 (manifest); P9 (reports) |
| WS5 | 1 | Consolidate-time additive scoring with gravity as demotion-floor (Q1) | P4 |
| WS5 | 2 | Recall-time RRF + post-rerank (Q2) | P3 |
| WS5 | 3 | Per-class dispatch over four persistent shapes (Q3) | P3 (formulas) + P4 (consolidate-time) |
| WS5 | 4 | v2 log-signal contract: 7 event types; replayability invariant (Q4) | P2 (`remember`), P3 (`recall`), P4 (`promote/demote/invalidate/consolidate_phase`), P6 (`recall_outcome`) |
| WS5 | 5 | Bi-temporal invalidation: gravity zeroed; T_purge=90 d; utility-tally freeze | P4 (invalidate) + P5 (forget) |
| WS5 | 6 | v1 default weight tuple (`α=0.2 β=0.3 γ=0.2 δ=0.4 ε=0.5`; RRF k=60; w_intent=0.15) | P4 |
| WS5 | 7 | v2 entry-criteria gate (≥20% strict-stratum operator share AND ≥10k labeled pairs) | P10 (gauges); v2 design (deferred) |
| WS6 | 1 | `forget` mode vocabulary `{invalidate|quarantine|purge}` + aliases | P5 |
| WS6 | 2 | `remember()` returns full envelope; sync classifier; async extraction | P2 |
| WS6 | 3 | `peer_message_*` sync verbs + async pull-based delivery | P6 |
| WS6 | 4 | `recall(k=0)` legal: preferences-only, zero recall events | P3 |
| WS6 | 5 | `recall_synthesis` emits `recall` events with `path=synthesis` | P3 |
| WS6 | 6 | `capture_opt_in_trace` admin, idempotent, per-tenant, revocable | P6 |
| WS6 | 7 | `emit_score_event` is internal sink, not external verb | P2/P3/P4/P6 emit; P9 sink |
| WS6 | 8 | `forget(quarantine)` returns estimated cascade_count | P5 |
| WS6 | 9 | `promote` and `forget` return "intended-not-applied" ack | P5 |
| WS7 | 1 | Five-store vocabulary used throughout; "three-tier" absorbed | P8 |
| WS7 | 2 | Corpus-only migration; `vault.db` out-of-scope for v1 | P8 (and post-v1 §5 deferral) |
| WS7 | 3 | SCNS S4b-shape projections NOT copied; regenerate post-cutover | P8 + P10 |
| WS7 | 4 | CLAUDE.md splits per top-level `##` heading into preference pages | P8 |
| WS7 | 5 | Authored synthesis migrates with `lethe.extract: false` | P8 |
| WS7 | 6 | Idempotency-key derivation with `"idem"` discriminant | P8 |
| WS7 | 7 | Episode-id derivation with `"epi"` discriminant; deterministic across resumes | P8 |
| WS7 | 8 | Cold-start migration recommended; warm-tenant via `expected_version` CAS | P8 (cold-start path); P5 (CAS) |
| WS7 | 9 | `criticStatus=suppress` → `remember` then `forget(invalidate)` (audit-preserving) | P8 |
| WS7 | 10 | Phase 11 S3 backfill non-blocking on api surface | P8 (with §5 deferred progress UX) |
| WS8 | 1 | Three RBAC roles (`agent / tenant_admin / operator`) | P7 |
| WS8 | 2 | JSON over HTTP/1.1 + optional MCP framing | P7 |
| WS8 | 3 | Rate-limit cap table (11 rows; per-tenant) | P7 |
| WS8 | 4 | Gate interval 15 min default; lock heartbeat 30 s / 60 s break | P4 |
| WS8 | 5 | Idempotency-key TTL: 24 h default; 7-day hard ceiling enforced at startup | P2 (TTL) + P7 (ceiling enforcement) |
| WS8 | 6 | Mid-migration async-drain alarm at 1.5× gate | P7 (alarm wiring) + P8 (migration tooling) |
| WS8 | 7 | `health()` extensions additive only | P7 |
| WS8 | 8 | 8 must-wire alarms; `tenant_isolation_breach` is P0 | P7 |
| WS8 | 9 | `force_skip_classifier=true` parameter; `tenant_admin`-gated; auditable | P2 (plumbed) + P7 (auth check + api §3.1 formal addition) |
| WS8 | 10 | Migration `escalated`-row drain post-cutover; `escalated_rejected` terminal | P7 (review queue) + P8 (manifest status) |
| WS8 | 11 | `lethe-migrate` CLI subcommand surface (12 subcommands) | P8 |
| WS8 | 12 | Manifest format `manifest.jsonl` (atomic-rename) | P8 |
| WS8 | 13 | Backup posture: SQLite online-backup on quiesce; native for Graphiti | P8 |
| WS8 | 14 | v2 cutover decision rule: both gates GREEN for 3 consecutive months | P10 (gauges + soak) |

Coverage: 40/40 locked decisions mapped to a realizing phase. Zero unrealized-decision rows. (The implementer should treat any locked-decision-without-realizing-phase as a bug in this matrix and surface it.)

---

## §7 Anti-checklist

This document MUST NOT do any of the following. A QA failure on any item is P0.

1. **Re-decide any WS0–WS8 locked decision.** The cascade record (HANDOFF §13 + each WS-QA + each WS-nit-fix) is source-of-truth. Where this doc references a decision, it cites the §-ref; it does not restate the rationale.
2. **Specify byte-level code** — function bodies, exact schema DDL, SQL queries beyond what design docs already specify. The design docs spec contracts; bytes are the implementer's call.
3. **Specify the SCNS runtime path.** HANDOFF §10 binding. Lethe stands on its own.
4. **Add cross-deployment Lethe→Lethe migration.** Deferred per §5.
5. **Specify the auth mechanism.** Deployment §2.3 specifies the contract (principal-extraction); the mechanism (OAuth / JWT / mTLS) is the implementer's call.
6. **Pin a wire-format protocol implementation library.** Deployment §2.4 specifies JSON over HTTP/1.1 + optional MCP framing; the HTTP framework choice is the implementer's call.
7. **Specify a metrics-export mechanism.** Deployment §5.4 lists the must-emit signals; the exporter is per-deployment.
8. **Add a v2 design** of any kind (multi-tenant runtime, learned scorer, 2PC, cross-deployment restore).
9. **Reorder anything HANDOFF §15.4 anti-checklist forbids** at the deployment surface (no api §4.4 field renamed/removed; no auth-mechanism commitment; no `vault.db` consumption; no v2 cutover triggerable by configuration).
10. **Frame markdown as "for humans only"** anywhere (HANDOFF §13 cascade; composition §1.1 binding).

Verifiable checks:
- (1)+(2): grep `docs/IMPLEMENTATION.md` for re-statements of design rationale; flag prose that is not citation-shaped.
- (3): `grep -in scns docs/IMPLEMENTATION.md` — every hit must fall into the allowed categories listed in §8.a.
- (4)+(8): grep for "cross-deployment", "v2 design", "multi-tenant runtime"; expect only deferral-side mentions (§5).
- (5)+(6)+(7): grep for "OAuth", "JWT", "mTLS", "Prometheus", "OTLP", "gRPC", "protobuf"; expect zero binding-side commitments.
- (10): grep for "for humans only" / "human-only"; expect zero hits as binding assertions.

---

## §8 Verification audits

Five audits, full transcripts in-doc (per WS8 §11.4 precedent). Re-runnable.

### §8.a SCNS-independence grep audit

Command: `grep -in scns docs/IMPLEMENTATION.md`.

Expected: every hit falls into one of these allowed categories:
- HANDOFF §10 / api §0.3 / migration §0.3 boundary citation.
- Migration / dream-daemon design-pattern cross-reference.
- §5 deferral row (`vault.db` consumer; cross-deployment from-SCNS migration).
- §7 anti-checklist denial.
- §8.a audit transcript itself.

Transcript (re-run by reader; this list updates if the doc is revised):
- §0.2 #3 — boundary statement (allowed).
- §0.3 I-2 — HANDOFF §10 citation (allowed).
- §2.3 — references to migration §3.1 mappings using SCNS shape names (allowed: design-pattern reference; migration calls api verbs only).
- §2.8 — `provenance.source_uri = scns:<shape>:<id>` literal in identifiers description (allowed: audit-trail format internal to Lethe's provenance store after import).
- §2.8 OOS row — `vault.db` consumption deferral (allowed: §5 deferral cross-ref).
- §5 — multiple rows for SCNS-related deferrals (allowed: deferral index).
- §7 #3 — anti-checklist denial (allowed).
- §8.a — audit transcript itself (allowed).

**Verdict: PASS** (every hit categorizable as allowed).

### §8.b Phase-cycle audit

Edge list (P_n → {dependencies}):
- P1 → {} (root)
- P2 → {P1}
- P3 → {P2}
- P4 → {P3}
- P5 → {P4}
- P6 → {P5}
- P7 → {P6}
- P8 → {P7}
- P9 → {P7, P8}
- P10 → {P9}

Topological order: P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P10. (Tie-breaks at P9 inherit from both P7 and P8; the order P7→P8→P9 is the unique sort that respects both edges.)

Cycle check: every edge points strictly to a lower-numbered phase. No back-edges. **Verdict: ACYCLIC. PASS.**

Cross-edge check vs PLAN.md §Sequencing diagram: WS0→WS8 design ordering does not constrain build-phase ordering directly (different dimensions per §1), but the build-phase ordering must not violate any WS-level dependency claim. Spot-check:
- P3 cites scoring §3–§5 (WS5) — WS5 is upstream of WS6/WS7/WS8 in the design DAG; consistent.
- P7 cites deployment §2 + §3 (WS8) — WS8 is the terminal design WS; P7 sits midway in the build DAG; consistent because P7 implements WS8's contracts (the contracts predate the build, by definition of "land WS0–WS8 first").
- P9 cites eval §4 + §5 (WS4) — WS4 is upstream of WS5 in the design DAG; the build DAG places eval wiring at P9 because the verbs it exercises (`recall`, `remember`, `capture_opt_in_trace`) are P3/P2/P6.

No design-DAG violation observed. **PASS.**

### §8.c Coverage audit

Forward coverage (every phase cites ≥1 WS source):
- P1: 4 sources. P2: 7. P3: 9. P4: 7. P5: 5. P6: 7. P7: 11. P8: 11. P9: 9. P10: 5. **PASS.**

Reverse coverage (every locked decision in HANDOFF §13 cascade has a realizing phase):
- §6.2 enumerates 40/40 locked decisions across WS3 (4) + WS5 (7) + WS6 (9) + WS7 (10) + WS8 (14).
- Zero unmatched rows. **PASS.**

(Citation-coverage is subsumed: every numeric default in this doc inherits from an upstream §-ref; this doc introduces zero new numeric defaults of its own. Spot-check: rate-limit caps cite deployment §3; weight defaults cite scoring §3 + gap-03 §5; idempotency TTL cites api §1.2 + deployment §4.3. No orphan numbers.)

### §8.d Anti-checklist self-check

Each §7 item has a verifiable check (listed inline at §7). Re-run:
- (1)+(2): no rationale-restatement prose detected; every design assertion is §-ref-shaped.
- (3): see §8.a audit — all SCNS hits in allowed categories.
- (4): "cross-deployment" appears only in §5 deferral rows and §7 #4 denial.
- (5)+(6)+(7): no commitment to OAuth/JWT/mTLS/Prometheus/OTLP/gRPC/protobuf.
- (8): "v2" appears only in §5 deferral rows, §6.2 reverse-traceability "v2 design" rows, and §10 v1→v2 distinction.
- (9): `health()` schema additions in P7 §2.7 are additive; api §4.4 baseline preserved (§6.2 WS8 #7).
- (10): "for humans only" / "human-only" framing — zero binding hits; only meta-references in §0.3 I-3 and §7 #10.

**Verdict: PASS.**

### §8.e Operator-readability spot-check

The implementer is engineer-class. File-level paths and acceptance criteria must be unambiguous.

Spot-checks:
- P1 §2.1: every store has a concrete file path under `src/lethe/store/<store>/`. PASS.
- P2 §2.2: every test file has a concrete `tests/...` path. PASS.
- P3 §2.3: scoring formulas are §-ref'd to scoring §3–§5; not restated. PASS.
- P7 §2.7: deployment §3 rate-limit table is referenced by row count (11) and partial enumeration; full table is at deployment §3. PASS (engineer can fetch the table).
- P8 §2.8: 12 `lethe-migrate` subcommands are §-ref'd to deployment §7.1 + migration §3.1; not restated. PASS.

Ambiguity hunt: search for "TBD", "FIXME", "TODO" — should be zero in the body of this doc. **Verdict: PASS** (any future occurrence is a regression).

---

## §9 Residuals

Implementation-plan-local open items the implementer encounters even after all phases land. Distinct from §5 (which is upstream-deferred).

1. **Test-file paths use `tests/<area>/` convention.** This is a hint, not a binding location; the project may consolidate under `tests/integration/` or split per-store. The implementer chooses.
2. **`src/lethe/` package layout** is a routing hint. Where the project's existing layout (e.g., `src/lethe/runtime/` already vs. flat `src/`) differs, the implementer renames; the contracts are the binding part, not the paths.
3. **Phase-internal task ordering** is not specified. Inside P3, e.g., the implementer may write `recall_synthesis` before or after `recall`; the gate is at the phase exit, not phase-internal.

Total: **3 residuals**, all acceptable as implementer-discretion.

---

## §10 Changelog

- **v1** — initial implementation plan. Phases P1–P10; risk register R1–R16; 5 in-doc audits (SCNS-independence; phase-cycle DAG; coverage; anti-checklist self-check; operator-readability spot-check).
