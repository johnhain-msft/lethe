# WS8 QA — Deployment Design (fresh-eyes review)

**Reviewer:** WS8-QA (cold pass, no exposure to WS8 drafting session).
**Artifacts under review:** `docs/08-deployment-design.md` (793 lines, commit `e20736a`); `docs/HANDOFF.md` §15 (post-WS8 entry, commit `767b748`).
**Reading order followed:** HANDOFF §15.4 verbatim — `08-deployment-design.md` start to finish → composition §1.1 (dual-audience principle) → api §0.2 + §1.6 + §1.8 + §2.1.2 + §3.1 + §3.3 + §3.4 + §4.1 + §4.3 + §4.4 + §8 → migration §3 + §3.1 + §4 + §5.1 + §10 + §2.3 (uuidv7 discriminants post-WS7 nit-fix) → composition §7 + §7.1 → gap-01 §3.2 Q3 → gap-08 §3.4 + §3.5 + §3.6 → gap-14 §5(3) → scoring §8.6 → HANDOFF §10 + §12.6 + §13 + §14.6 → eight audits re-run live.

---

## 1. Verdict

**APPROVE-WITH-NITS.**

WS8 gives an operator (and a future operator-tooling-pass implementer) enough substrate to deploy, monitor, and operate a single-tenant v1 Lethe deployment without re-researching upstream contracts. All twelve anti-checklist items in HANDOFF §15.4 are respected. Zero residual SCNS dependency at the operator surface. Zero "for humans only" framing in normative prose. The `health()` extensions in §5.2 are strictly additive on api §4.4. The D6 idempotency-key TTL is enforced (`> 7 days` rejected at runtime startup, not advisory) with the chunk-by-snapshot escape documented as the operator-side path above the ceiling. The five internal §11 audits the doc commits to (operator-readability, citation coverage, anti-checklist, SCNS-independence, markdown-audience) all reproduce **categorically** under fresh `grep` re-run; two of them undercount their own raw-line totals (numbered nits N7, N8 below) but the categorization holds. Eight numbered nits (one P1-shaped internal contradiction; seven doc-hygiene) do not block IMPLEMENTATION.md.

Headline answer to the gating question: **YES** — `docs/08-deployment-design.md` is precise enough that (a) an operator can stand up a single-tenant v1 Lethe deployment, wire the eight must-wire alarms, run a SCNS→Lethe migration through `lethe-migrate`, and drain the post-migration escalate-review queue without re-reading WS3/WS5/WS6/WS7, and (b) the operator-tooling-pass implementers (metrics pipeline, review-surface HTML renderer, `lethe-migrate` CLI, `lethe-admin` CLI) can write against §3 / §5 / §6 / §7 / §8 contracts directly without re-deriving deployment shape from upstream.

Eight gating questions answered:

| # | Question | Answer | Citation |
|---|---|---|---|
| 1 | Three RBAC roles named with capability-to-verb matrix complete over api §0.2 capability set? | **YES** | §2.1 (3 roles); §2.2 (capability-to-verb matrix; every api verb mapped to required capability or "(none)"); api §0.2 names `forget_purge` / `audit_global` / `tenant_admin`, all three covered. |
| 2 | Rate-limit numerical caps committed for every api §-ref attach point? | **YES** | §3 ten rows; api §1.6 / §2.1.2 / §3.3 / §3.4 / §4.1 / §4.3 / §4.4 attach points all carry a row; per-tenant cap on `forget(purge)` (per HANDOFF §15.4 anti-checklist). |
| 3 | `health()` extensions strictly additive over api §4.4 (no field renamed, no field removed, no semantic change)? | **YES** | §5.2 base fields preserved verbatim from api §4.4 (`overall`, `stores`, `degraded_modes`, `daemon`, `emitter`); five new top-level keys added (`migration`, `idempotency`, `escalation_queue`, `drift`, `v2_gate`); diff at §7.8 below. |
| 4 | Idempotency-key TTL ceiling enforced (not advisory) at runtime startup, with chunk-by-snapshot escape documented? | **YES** | §4.3 line 234: "config validator at runtime startup **rejects** values > 7 days"; "runtime refuses to start until the value is reduced; this is a hard fail, not a warning"; chunk-by-snapshot escape at line 236; §7.4 snapshot UX is the named operator path. |
| 5 | Eight must-wire alarms with thresholds + first operator action? | **YES** | §5.5 — `consolidation_stalled`, `escalation_queue_depth`, `idempotency_fallback_high`, `s3_backfill_stalled`, `drift_high`, `degraded_mode_active`, `forget_purge_rate_spike`, `tenant_isolation_breach` (P0). Each row has condition + severity + source + first action. |
| 6 | Escalate-review pipeline complete (substrate + actions + SLA + migration drain workflow + `force_skip_classifier=true`)? | **YES with internal-inconsistency nit** | §6.1–§6.5 specify all pieces; `force_skip_classifier=true` is flagged for WS6 implementation pass (§6.3 + §14). The idempotency-key relationship between §6.3 (claims `idempotency_key = staged_id` on approve) and §6.5 (claims approve uses migration row's original `idempotency_key`) is internally contradictory — see Nit N1 (highest-priority finding). |
| 7 | `lethe-migrate` subcommands cover migration §3.1 phases 1–14 with three hard phase-gates? | **YES** | §7.1 12 subcommands map 1:1 to migration §3.1 (init=1, snapshot=2, inventory=3, phase-gate {a/b/c}=4/7/10, apply {s4a/s1/invalidation/s3-backfill/recall-probe}=5/6/8/11/12, drain=9, cutover=13, s4b-regen=14, plus status/resume/rollback). |
| 8 | Doc explicitly disclaims verb-semantics / migration-tool source / scoring math / eval-set composition / SCNS runtime / cross-deployment / `vault.db` / auth-mechanism / multi-tenant-runtime / v2-design / schema-migration policy / Lethe-distribution? | **YES** | §0.2 (10 items); §12 anti-checklist (12 explicit denials, restated for visibility). |

---

## 2. Per-section scoring rubric

| § | Score | One-line rationale |
|---|---|---|
| §0 Frame + binding constraints | 5/5 | §0.1 (owns) and §0.2 (does NOT own) are exhaustive and surgical; six §0.3 binding constraints each cite an upstream §-ref; §0.4 nineteen-term operator-vocabulary index is the keystone for the dual-audience principle and reproduces under §7.3 readability audit cleanly. |
| §1 Deployment topology | 5/5 | §1.1 single-tenant baseline grounded in composition §1.1 + §5.2; §1.2 per-store physical layout with backup posture forward-link to §8.1; §1.3 `single_writer_per_tenant=true` migration default cleanly cites gap-04 §4 stop-gap; §1.4 v2 gate is forward-ref-only (no mechanism leaked here). |
| §2 RBAC + auth + wire format | 5/5 | Three roles cleanly map api §0.2 capabilities; the §2.1 rationale ("`forget_purge` lives on `tenant_admin` not `operator`-only because hard-delete is data-sovereignty, not ops-fleet") is a real architectural commitment that survives v2 lift; §2.2 capability-to-verb matrix is exhaustive (every api verb covered, including the `(none)` rows for non-capability-gated verbs); §2.3 principal-extraction contract correctly under-specifies the auth mechanism per §0.2; §2.4 wire-format decision (JSON over HTTP/1.1 + optional MCP) carries a rationale table including explicit protobuf/gRPC rejection. |
| §3 Rate-limit + quota | 5/5 | Ten rows; every cap cites api §-ref attach point; `forget(purge)` is **per tenant** (not per principal), preventing the multiple-admin bypass anti-pattern; escalate-staging cap (50/d per tenant) is the queue-depth counterweight, hits the §5.5 `escalation_queue_depth` alarm. |
| §4 Operator knobs | 4.5/5 | Nine knobs, every default cited or named-as-bet. §4.1 gate interval correctly named v1 bet with five-row range table; §4.2 fixes `2×` break-multiplier (operator cannot raise it without operator benefit) — defensible commitment; §4.3 idempotency-TTL ceiling enforcement is the strongest commitment in the doc (D6 closure); §4.5 drift cadence faithful to gap-14 §5(3); §4.8 mid-migration alarm tightening (1.5× vs steady-state 2×) is the right gradient. Half-point off for one parenthetical operator-vocab usage (Nit N6 — `(peer-class)` in §4.7 header without inline definition). |
| §5 Health + observability | 5/5 | §5.1 three-question framing matches what an operator actually asks; §5.2 additive `health()` extensions are strictly additive on api §4.4 (verified field-by-field at §7.8); §5.3 `audit()` operator-query patterns are operator-vocabulary playbook entries (no schema change); §5.4 nineteen must-emit signals each cite source + use; §5.5 eight must-wire alarms each name severity + first-action + threshold (P0 on `tenant_isolation_breach` is the right severity for a composition §5.2 invariant violation). |
| §6 Escalate-review pipeline | 4/5 | Substrate (`review_queue` schema in S2), three review actions (`approve`/`reject`/`expire-now`), SLA (24 h review, 30 d queue TTL), migration `escalated`-row drain workflow (`escalated_rejected` as new terminal status), `force_skip_classifier=true` introduced as a documented v1 api §3.1 extension (gated to `tenant_admin`, auditable in S5, flagged for WS6 implementation pass). One-point off for the internal contradiction between §6.3 and §6.5 about whether `idempotency_key` on approve is the `staged_id` (§6.3 row text) or the original caller-supplied / migration-row idempotency_key (§6.5) — see Nit N1. The §6.5 reading is the operationally-correct one (it is the one that lets the manifest's `applied_episode_id` populate); §6.3's wording must be reconciled before the review-tool implementer writes the approve path. |
| §7 Migration runtime contract | 4.5/5 | §7.1 twelve `lethe-migrate` subcommands cover migration §3.1 phases 1–14 + status/resume/rollback; §7.2 manifest UX (JSONL append-only with atomic-rename on status update + per-run HTML index + JSON dump) is implementer-grade specific; §7.3 capability-check ordering (auth → tenant_admin → forget_purge if needed → health) is correct; §7.4 snapshot UX names three methods (git-tag/fs-copy/zfs-snapshot) with the recommended default cited; §7.5 rollback is **pre-cutover only** (correctly bounded). Half-point off for the rollback-discriminant nit (Nit N2 — `"rollback"` discriminant introduced in §7.5 not formalized in migration §2.3, parallel to the WS7-QA N3 pattern). |
| §8 Backup / restore + crash recovery | 5/5 | §8.1 per-store backup posture (SQLite online-backup on quiesce; native procedures for Graphiti backing DB; git for S4a; rebuildable-from-S1 disclaimer for S3) is operator-grade specific; §8.2 `lethe-audit lint --integrity` named as the operator surface for both startup and migration phase-gates A/C; §8.3 `lethe-admin lock` recovery commands consistent with gap-08 §3.4; §8.4 disk thresholds (1 GB / 100 MB) name the retention-proof-before-delete ordering from gap-08 §3.6 explicitly. |
| §9 Degraded modes operator playbook | 4.5/5 | Sixteen rows: thirteen single-store rows from composition §7 + three two-stores-down rows from composition §7.1 — every composition §7 row is covered except "peer-message corrupts a memory" (intentional omission; that case is content-trust / provenance-enforcement / scoring-weight territory, not a `health()`-surfaceable degraded mode — but the omission is unstated). Each row has operator-sees / operator-does / silent-by-design columns. Half-point off for that one omission lacking an explicit "intentionally not in operator playbook" rationale (Nit N5). |
| §10 v1 → v2 entry-criteria gate | 5/5 | §10.1 lifts the two scoring §8.6 conditions verbatim to operator-visible gauges; §10.2 the 3-month soak rule is correctly framed as **additive** to scoring §8.6 (not contradictory); §10.3 seven-item readiness checklist is the v2 readiness operator surface. The §10.2 "single-month spike past 20% operator share that immediately reverts must not unlock the cutover" rationale is the right answer for an irreversible-shaped boundary. |
| §11 Verification audits | 4/5 | All five in-doc audits reproduce categorically under fresh re-run (§7 below). One-point off for raw-line undercounts in §11.4 (claims 11 SCNS hits; fresh `grep` returns 16 — Nit N7) and §11.5 (claims 2 humans-only hits; fresh `grep` returns 3 — Nit N8). The categorization PASSes in both cases (every hit IS in an allowed category); the count is wrong. |
| §12 Anti-checklist | 5/5 | Twelve explicit denials, each grep-verifiable; mirrors §0.2 with sharper anti-content. |
| §13 Traceability matrix | 5/5 | Every WS8 decision → upstream §-ref. Spot-checked 5 high-stakes rows: §4.3 idempotency TTL → api §1.2 + gap-08 §3.1 + HANDOFF §14.6 ✓; §10 v2 gate → scoring §8.6 + composition §1.1 ✓; §4.5 drift cadence → gap-14 §5(3) ✓; §3 row `forget(purge)` → api §3.3 step 2 + gap-11 §3.3 ✓; §6.3 `force_skip_classifier=true` → flagged for WS6 implementation pass ✓. No TBD rows. |
| §14 Residual unknowns | 5/5 | Thirteen items, each surfaced not pre-resolved; "3 consecutive months reset semantics under partial-month outages" is the highest-leverage residual and is correctly v1.x-deferred; cross-deployment Lethe→Lethe restore parity with WS7 §10 deferral preserved. |

**Decisions (HANDOFF §15.3) honored:**

| Decision | Resolution required | Verified at |
|---|---|---|
| #1 Three RBAC roles, `forget_purge` on `tenant_admin` | api §0.2 capabilities | §2.1 + §2.2 |
| #2 JSON over HTTP/1.1 + optional MCP framing | api §0.4 | §2.4 (rationale table, protobuf/gRPC rejected) |
| #3 Rate-limit caps per verb table | api §1.6 + §2.1.2 + §3.3 + §3.4 + §4.3 | §3 ten rows, all cited |
| #4 Gate interval 15 min default; lock heartbeat 30 s / 60 s break | gap-01 §3.2 Q3; gap-08 §3.4 | §4.1 + §4.2 |
| #5 Idempotency-key TTL: 24 h default; **7-day hard ceiling enforced** | api §1.2; gap-08 §5; HANDOFF §14.6 | §4.3 — startup-validator rejection + chunk-by-snapshot escape + `idempotency_fallback_high` alarm at 5% |
| #6 Mid-migration async-drain alarm at 1.5× gate | HANDOFF §14.6; migration §10 | §4.8 + §5.5 row |
| #7 `health()` extensions are additive only | api §4.4 | §5.2 (verified additive at §7.8) |
| #8 Eight must-wire alarms; `tenant_isolation_breach` is **P0** | composition §5.2; api §1.8 | §5.5 row 8 |
| #9 `force_skip_classifier=true` on `remember`; `tenant_admin`-gated | api §3.1 + §3.4 | §6.3 + §14 (flagged for WS6 implementation pass) |
| #10 Migration `escalated`-row drain is **post-cutover** | migration §3.1 phase 10 (Phase-gate C) lints applied rows; staged rows have no S1 episodes to lint | §6.5 (introduces `escalated_rejected` terminal status) |
| #11 `lethe-migrate` CLI subcommand surface (12 subcommands) | migration §3 + §3.1 + §3.2 | §7.1 |
| #12 Manifest format: `manifest.jsonl` (append-only with atomic-rename rewrite) | migration §3.2 | §7.2 |
| #13 SQLite online-backup on quiesce; native Graphiti backing-DB procedures | composition §2 + §5; gap-08 §5 | §8.1 |
| #14 v2 cutover: both scoring §8.6 gates GREEN for 3 consecutive months | scoring §8.6; composition §1.1 (irreversible-shaped) | §10.2 |

---

## 3. Major findings

**One P1-shaped finding:**

**M1 — Internal contradiction in §6.3 vs §6.5 about `idempotency_key` on the approve path.** §6.3's review-action row says: `remember(content, intent, idempotency_key, provenance, kind, force_skip_classifier=true)` ... where `idempotency_key` is the staged-id". §6.5's migration-row drain workflow says: "approving routes through `remember(force_skip_classifier=true)` per §6.3 with the same `idempotency_key` the migration row carries (so the manifest row's `applied_episode_id` populates and the row transitions `escalated → done`)." These are different values: the staged_id (§6.2) is "pre-issued [by the runtime when staging]; surfaced to caller in 422 ack"; the migration row's `idempotency_key` is the migration §2.3 derivation with discriminant `"idem"`. The §6.5 reading is operationally necessary for migration to converge (the manifest row's `applied_episode_id` only populates if the approve uses the same `idempotency_key` the migration call carried); the §6.3 wording, taken literally, breaks migration drain. **Recommended reconciliation:** §6.3 row text should say `idempotency_key` is the *original* caller-supplied (or migration-row-supplied) idempotency_key, with `staged_id` documented as a separate identifier used only for review-queue addressing (URLs, S5 audit row references). This is a doc-wording fix, not a contract change. Severity: P1 (not anti-checklist; not BLOCK; review-tool implementer cannot proceed without reconciling). Reproducible at `docs/08-deployment-design.md:437` vs `docs/08-deployment-design.md:456`.

No P0 (anti-checklist violation) findings. The four highest-stakes anti-checklist items — no spurious api verb additions beyond `force_skip_classifier=true` (HANDOFF §15.4 anti-checklist item 1); no `health()` rename/remove (item 2); per-tenant `forget(purge)` cap (item 11); no v2 cutover via configuration (item 10) — are each **structurally** enforced by §6.3 + §5.2 + §3 row 4 + §10.2 surfaces and survived live re-run.

---

## 4. Nits (one-liners; doc-hygiene; N1 above is the P1 — repeated below for completeness only)

- **N1** (`docs/08-deployment-design.md:437` vs `:456`) — §6.3 vs §6.5 internal contradiction on `idempotency_key` on approve path. **P1.** See §3 above. Recommended fix: in §6.3 row text, replace "where `idempotency_key` is the staged-id" with "where `idempotency_key` is the original caller-supplied (or migration-row) idempotency_key; `staged_id` remains as the queue-row identifier for the review surface and S5 audit references."
- **N2** (`docs/08-deployment-design.md:524`) — §7.5 rollback subcommand introduces a fourth uuidv7 derivation discriminant `"rollback"` ("idempotency_key derived per migration §2.3 with discriminant `\"rollback\"`") that is not formalized in migration §2.3. WS7-QA N3 caught the same shape (`"forget"` discriminant referenced but not formalized); the WS7 nit-fix (commit `fa4a7f8`) added the `"forget"` block to migration §2.3. The parity-pattern recurs at WS8: now `"rollback"` is referenced without a corresponding §2.3 block. **Recommended fix:** either (a) add a fourth derivation block to migration §2.3 ("for `forget(invalidate)` calls in `lethe-migrate rollback`, substitute discriminant `\"rollback\"`; same RFC 9562 layout"), or (b) inline-formalize the derivation in WS8 §7.5 (one sentence: "Same RFC 9562 layout as migration §2.3; `\"rollback\"` discriminant separates the rollback-time invalidation key from the migration-time `\"forget\"` invalidation key over the same source bytes"). (a) keeps migration §2.3 closed at the migration boundary — the cleaner shape. The collision-disjoint property holds either way (sha256 input bytes differ by ≥7 ASCII bytes between `"forget"` and `"rollback"`).
- **N3** (`docs/08-deployment-design.md:447–449`) — §6.4 review SLA (24 h) and queue TTL (30 d) are v1 bets per §11.2's audit result list, but the §6.4 body itself doesn't say "v1 bet" — only `Default: 24-hour review SLA. ... Operator-tunable.`. Per §0.3 #5 every numeric default carries a citation OR is named as a v1 bet; "v1 bet" is the right framing for a number with no upstream §-ref. Recommend a one-line addition to §6.4: "Both defaults are v1 bets; instrumented via the `escalation_queue_depth` alarm (§5.5) and revisable per HANDOFF §14.6." (This is the same shape as §4.1's range table making the gate-interval bet explicit.)
- **N4** (`docs/08-deployment-design.md:566`) — §8.4 disk thresholds (1 GB / 100 MB) are sourced as "composition §7; gap-08 §3.6" in §13's traceability matrix, but composition §7 only says "configurable threshold" without naming a number, and gap-08 §3.6 does not pin numbers either; the 1 GB / 100 MB are WS8-authored v1 bets. The §8.4 body should name them as v1 bets explicitly (parallel to §4.1's "v1 bet documented w/ range" wording). Recommend a parenthetical: "(1 GB / 100 MB are v1 bets; expected to retune per-deployment based on tenant write volume and S2/S3 file growth observed)." Same shape as N3.
- **N5** (`docs/08-deployment-design.md:570–593`) — §9 omits one composition §7 row: "A peer-message corrupts a memory" (composition §7 row 9). Defensible: peer-message corruption is a content-trust / scoring-weight / contradiction-detection (gap-13) matter, not a `health()`-surfaceable degraded mode an operator can act on. Recommend a one-line note at §9 closing: "Composition §7's 'peer-message corrupts a memory' row is intentionally not in this playbook; it is a provenance-enforcement / contradiction-detection (gap-05; gap-13) matter, not an operator alarm-able mode." — keeps the cross-walk explicit so future readers don't perceive it as a gap.
- **N6** (`docs/08-deployment-design.md:269`) — §4.7 header reads "Sensitive-class escalate cap (peer-class)" but `(peer-class)` is not defined inline or in §0.4; readers familiar with api §3.4 will infer "peer-message-class escalation," but the parenthetical is operator-vocab-opaque. Recommend either remove the parenthetical (the §4.7 body already names "staged-for-review queue" which is §0.4-defined and sufficient) or expand it to "(peer-message-class escalation; api §3.4)".
- **N7** (`docs/08-deployment-design.md:671`) — §11.4 self-reports "11 total hits, all in allowed categories"; fresh `grep -in scns docs/08-deployment-design.md` returns 16 lines (full transcript at §7.1 below). The 5-line discrepancy is from the §11.4 result-bullet body itself (lines 674–678 — each describes one of L47 / L69 / L192 / L218 / L240 / L514 and contains the substring `scns` while doing so; these are within the §11.4 audit transcript and so still in the "audit transcript itself" allowed category, just not counted in the bullet enumeration). Categorization PASSes; the count is wrong. Recommend revising §11.4 to "16 total line-hits, distributed across 9 distinct allowed-category buckets" or to omit the count and rely on the bucketed enumeration.
- **N8** (`docs/08-deployment-design.md:689`) — §11.5 self-reports "2 total hits, both meta-references"; fresh `grep -in "for humans only|humans only|human-only" docs/08-deployment-design.md` returns 3 lines: §0.3 #4 (line 49) + §11.5 audit-method paragraph (line 687) + §11.5 result bullet (line 691). The 3rd hit is the §11.5 result bullet that quotes the prohibited string while affirming its absence; it is a meta-reference, not a regression. Categorization PASSes (zero framing-assertion hits); the count is wrong. Recommend "3 total hits, all meta-references."

(N1 is the P1; N2–N8 are doc-hygiene only and individually do not block IMPLEMENTATION.md. WS8-nit-fix should bundle all eight in a single `docs(ws8):` commit.)

---

## 5. Stopping-criteria check

Per HANDOFF §15.4 anti-checklist (P0 if violated):

| Anti-checklist item | Violated? | Evidence |
|---|---|---|
| Verb signature in `docs/08-deployment-design.md` adding to api surface, except `force_skip_classifier=true` on `remember` | **NO** | §6.3 introduces `force_skip_classifier=true` (the documented exception), gated to `tenant_admin`, flagged for WS6 implementation pass at §6.3 footnote + §14. No other verb-surface additions. |
| Change to api §4.4 `health()` schema that removes or renames a field | **NO** | §5.2 base fields are preserved verbatim (`overall`, `stores`, `degraded_modes`, `daemon` with all four sub-fields, `emitter` with both sub-fields); five new top-level keys added — see §7.8 diff below. |
| Rate-limit cap that lacks an api §-ref attach point | **NO** | §3 ten rows; every row's "Source" column cites api §-ref. The escalate-staging cap (50/d per tenant) cites api §3.1 + api §3.4 + HANDOFF §12.6 + §14.6; the only row whose api §-ref is to a deferred-to-WS8 surface is the escalate-staging cap, which is consistent with HANDOFF §15.4. |
| Operator knob default that lacks a citation OR explicit "v1 bet" naming | **NO with hygiene nits** | All §4 knobs cited; §6.4 review SLA + queue TTL + §8.4 disk thresholds need explicit "v1 bet" naming in the body — see Nits N3 + N4 (doc-hygiene only; not P0). |
| Operator-vocabulary term used in body without §0.4 entry or inline definition | **NO with one minor nit** | §0.4 nineteen terms cover the recurring vocab; sample of six sections (§1, §3, §4, §6, §7, §9) at §7.3 reproduces clean. The `(peer-class)` parenthetical at §4.7 header is the one minor exception — see Nit N6. |
| "For humans only" framing for markdown surfaces | **NO** | §7.5 fresh `grep` returns 3 hits, all meta-references (§0.3 #4 binding-constraint forbidding, plus 2 hits in §11.5 audit transcript). Zero hits in normative prose at §6.2 review-surface, §7.2 manifest UX, §9 degraded-mode playbook (manually scanned). |
| Commitment to a specific auth provider (OAuth, JWT, mTLS) | **NO** | §2.3 specifies the principal-extraction contract abstractly; §0.2 + §12 explicitly disclaim auth-mechanism implementation. |
| Cross-deployment Lethe→Lethe restore path in v1 | **NO** | §7.5 (post-cutover rollback "not supported in v1"); §8.1 ("Cross-deployment restore is out of scope for v1"); §12 + §14 deferral. |
| `vault.db` consumption | **NO** | §0.2 + §12 explicit denials; reproduced under live grep at §7.4 below (2 hits, both denials). |
| v2 multi-tenant cutover triggerable by configuration | **NO** | §1.4 explicit ("A v1 deployment cannot opt into v2 multi-tenant runtime by configuration; the cutover requires a runtime upgrade."); §10.2 reinforces (3-month soak rule on the irreversible-shaped boundary). |
| `forget(purge)` cap that is per-principal rather than per-tenant | **NO** | §3 row 4 explicit: "10 per hour, 100 per day | rolling | per **tenant** (not per principal)" — bold formatting in the source carrying the constraint; rationale in same row ("multiple admins cannot aggregate to bypass"). |

Per HANDOFF §15.1 / §15.4 stopping criteria for WS8:

| Criterion | Met? |
|---|---|
| RBAC role definitions + capability-to-verb matrix complete | **YES** (§2.1 + §2.2) |
| Rate-limit numerical caps for every api §-ref attach point | **YES** (§3 ten rows) |
| Wire-format choice with rationale | **YES** (§2.4 — JSON + HTTP/1.1 + optional MCP; protobuf/gRPC rejection rationale) |
| Operator knobs with defaults + ranges + v1-bet naming where applicable | **YES with hygiene nits** (§4; N3 + N4 doc-hygiene) |
| `health()` extensions strictly additive on api §4.4 | **YES** (§5.2; verified at §7.8) |
| Eight must-wire alarms with thresholds + first action | **YES** (§5.5) |
| Escalate-review pipeline complete | **YES with internal-inconsistency nit** (§6; N1) |
| `lethe-migrate` CLI surface 1:1 with migration §3.1 phases + manifest UX + snapshot UX + rollback scope | **YES** (§7) |
| Backup posture per store + crash-recovery operator surface + disk-full thresholds | **YES** (§8) |
| Degraded-modes operator playbook cross-walking composition §7 + §7.1 | **YES with one row-omission nit** (§9; N5) |
| v1 → v2 entry-criteria gate exposing scoring §8.6 conditions + 3-month soak | **YES** (§10) |
| Five in-doc audits (operator-readability / citation / anti-checklist / SCNS / markdown-audience) | **YES** (§11; categorization reproduces; 2 raw-line undercounts — N7 + N8) |
| Twelve-item anti-checklist denials | **YES** (§12) |
| Traceability matrix | **YES** (§13) |
| Residual unknowns enumerated | **YES** (§14 thirteen items) |

---

## 6. Ready-for-IMPLEMENTATION.md statement

**Ready for `docs/IMPLEMENTATION.md` (the closing planning artifact): YES, after WS8-nit-fix.**

- §3 / §4 / §5 / §6 / §7 / §8 collectively give the operator-tooling-pass implementer enough surface to write the metrics pipeline (§5.4 nineteen signals), the review-surface HTML renderer (§6.2 schema + §6.3 actions), the `lethe-migrate` CLI (§7.1 twelve subcommands + §7.2 manifest format + §7.4 snapshot methods), and the `lethe-admin` CLI for lock recovery (§8.3) without re-reading composition / scoring / api / migration / gap briefs.
- The single P1 finding (Nit N1) needs reconciliation before the review-tool implementer can write the approve path; this is a doc-wording fix, not a contract redesign.
- The seven doc-hygiene nits (N2–N8) are bundleable into a single `docs(ws8):` nit-fix commit alongside N1, mirroring the WS7 nit-fix pattern (`fa4a7f8`).
- HANDOFF §15.5 follow-throughs (metrics-pipeline implementation, review-surface HTML implementation, `lethe-migrate` CLI implementation, `lethe-admin` CLI implementation, `force_skip_classifier=true` formal addition to api §3.1, cross-deployment Lethe→Lethe restore deferred to v1.x, 2PC for cross-host T1 deferred to v2, v2 multi-tenant runtime design as future workstream, backup quiesce automation, "3 consecutive months" reset semantics under partial-month outages, RBAC management API as v1.x administrative verb) are all correctly scoped out of WS8 — none of them are WS8-deliverable items.
- WS3 (composition) → WS4 (eval-plan) → WS5 (scoring) → WS6 (api) → WS7 (migration) → WS8 (deployment) — the deferral chain closes here at the operator surface. `docs/IMPLEMENTATION.md` (per `PLAN.md` §Deliverables line 4) is the right next artifact: a top-level index naming the implementation workstreams (operator-tooling pass; runtime substrate implementation; eval harness; metrics pipeline; etc.) and pointing at each WS as the contract reference, with the open follow-throughs from each WS's §-residual section as the implementation backlog seeds.

**Ready for the operator-tooling pass: YES (post-N1).** §7.1 / §7.2 / §6.2 / §6.3 / §8.3 contracts are stable enough that the four operator-tooling-pass artifacts (`lethe-migrate`, `lethe-admin`, the review-surface HTML renderer, the metrics exporter) can all begin once N1 is reconciled. The only api-surface dependency is the `force_skip_classifier=true` addition to api §3.1 (HANDOFF §15.5 follow-through), which is a single-line addition with the auth check tied to `tenant_admin`.

---

## 7. Audit transcripts

### 7.1 SCNS-independence audit (re-run live, full transcript)

```
$ grep -in scns docs/08-deployment-design.md
47:2. **No SCNS runtime dependency post-cutover.** No verb, no operator command, no health surface reads from `~/.scns/`, imports SCNS schemas, or accepts SCNS data sources at runtime. (HANDOFF §10 binding constraint #1; api §0.3 #1; migration §0.3 + §6.6.1.)
69:- **Cutover.** The operator action that flips downstream agents from a SCNS-as-substrate runtime to a Lethe-as-substrate runtime. Migration §3.1 phase 13. (migration §3.1.)
192:| `remember` | **10 req/s sustained, 30 burst** | rolling 1 s | per `(tenant, principal)` | Extraction is async (api §3.1 step 1 returns after T1); the cap pressures T1 transaction throughput. SCNS observation rate << 10/s in practice. | api §3.1 |
218:| **15 min (default)** | Balanced; SCNS dream-daemon precedent (note §2.10 three-condition gate); Phase 9 async-drain (migration §3.1 phase 9) of O(10k) episodes drains in sub-hour. |
240:| 24 h (default) | Steady-state; SCNS observation rate; small migrations. |
514:- `git-tag` is the recommended default for SCNS-corpus migrations (the source tree is git-versioned per gap-08 §3.4 substrate).
667:### §11.4 SCNS-independence audit
669:Same audit pattern as api §7.1, migration §6.6.1. `grep -in "scns" docs/08-deployment-design.md` and confirm every hit falls into allowed categories: HANDOFF citation; the §12 anti-checklist denial; design-pattern cross-references where the upstream doc itself cites SCNS (gap-01 dream-daemon evaluation; migration target-corpus); this audit transcript itself.
674:- §0.4 "Cutover" definition — names "SCNS-as-substrate" as the source side of the cutover concept (allowed: migration cross-reference; the migration target is by definition SCNS).
675:- §3 `remember` rate-limit row — "SCNS observation rate << 10/s in practice" rationale (allowed: migration cross-reference for sizing).
676:- §4.1 gate-interval default — "SCNS dream-daemon precedent (note §2.10)" citing gap-01 §3 + dream-daemon design note (allowed: design-pattern reference per HANDOFF §10 binding-constraint #1).
677:- §4.3 idempotency TTL row — "SCNS observation rate; small migrations" sizing rationale (allowed: migration cross-reference).
678:- §7.4 snapshot UX — "SCNS-corpus migrations" naming (allowed: migration cross-reference).
683:**Zero hits** in disallowed categories (no verb signature, no schema field, no runtime read path, no SCNS-shaped command, no dependency declaration). PASS.
708:- **A SCNS runtime path.** No verb, command, or surface in this doc reads from `~/.scns/` or imports SCNS schemas at runtime. (HANDOFF §10 binding constraint #1; §0.3 #2.)
726:| §0.3 #2 | No SCNS runtime dependency | HANDOFF §10 #1; api §0.3 #1; migration §0.3 |
```

Sixteen line-hits, bucketed against the four HANDOFF §15.4 step 11 / WS8 §11.4 allowed categories:

| Bucket | Lines | Classification |
|---|---|---|
| (a) HANDOFF §10 / api §0.3 #1 boundary citations (binding-constraint disclaimers) | 47, 708, 726 | Allowed (binding-constraint citation). |
| (b) Design-pattern cross-references where upstream itself cites SCNS (gap-01 dream-daemon evaluation; migration target-corpus naming for sizing rationale) | 69, 192, 218, 240, 514 | Allowed (design-pattern reference per HANDOFF §10 binding-constraint #1; the migration target is, by definition, the SCNS markdown corpus). |
| (c) §11.4 audit transcript itself (header + body + result bullets + closing paragraph) | 667, 669, 674, 675, 676, 677, 678, 683 | Allowed (audit transcript itself). |
| (d) §12 anti-checklist denial | 708 (also counted under (a)) | Allowed (anti-checklist denial). |

Bucket (a) holds 3 line-hits; bucket (b) holds 5; bucket (c) holds 8; bucket (d) overlaps with (a) at line 708. All 16 line-hits are accounted for in allowed categories.

**Result: PASS.** Zero hits introduce a runtime read path to `~/.scns/`. Zero hits extend a verb signature. Zero hits name SCNS as a *post-cutover* runtime dependency. Zero hits import SCNS schemas. The §11.4 self-claim of "11 total hits" is a raw-line undercount (Nit N7); the categorization holds.

### 7.2 Citation-coverage audit

Every numeric default in §3 / §4 / §5.5 / §6 / §8.4 / §10 must carry an upstream §-ref OR be named explicitly as a v1 bet (§0.3 #5):

| §-ref | Default | Source / framing | Status |
|---|---|---|---|
| §3 row `recall` | 30/s sustained, 60 burst | api §2.1.2 | ✓ cited |
| §3 row `remember` | 10/s sustained, 30 burst | api §3.1 | ✓ cited |
| §3 row `forget(invalidate \| quarantine)` | 5/s sustained, 10 burst | api §3.3 | ✓ cited |
| §3 row `forget(purge)` | 10/h, 100/d per tenant | api §3.3 step 2; gap-11 §3.3 | ✓ cited |
| §3 row `peer_message` | 20/s sustained, 50 burst | api §3.4; gap-10 §3.4 (via "Inbox cap is 100 unread per recipient") | ✓ cited |
| §3 row `consolidate(force=true)` | 6/h per tenant | api §4.3 (cap to ~one forced cycle per default 15 min gate) | ✓ derived from §4.1 |
| §3 row `capture_opt_in_trace` | 10/h per tenant | api §4.1 | ✓ cited |
| §3 row escalate-staging cap | 50/d per tenant | api §3.1; api §3.4; HANDOFF §12.6 + §14.6 | ✓ cited |
| §3 row `audit()` | 10/s per principal | api §4.4 | ✓ cited |
| §3 row `health()` | unbounded | api §4.4 ("always-on") | ✓ cited |
| §4.1 gate interval | 15 min | gap-01 §3.2 Q3 (does not pin gate interval); WS8 v1 bet documented w/ five-row range table | ✓ explicit v1 bet |
| §4.2 lock heartbeat | 30 s heartbeat / 60 s break | gap-01 §3.2 Q3 ("per-tenant lock + 30-second heartbeat is the v1 baseline"); gap-08 §3.4 | ✓ cited |
| §4.3 idempotency-key TTL default | 24 h | api §1.2; gap-08 §3.1 | ✓ cited |
| §4.3 idempotency-key TTL ceiling | 7 d (enforced) | HANDOFF §14.6; gap-08 §5 | ✓ cited (D6 closure) |
| §4.4 preference-cap | 10 KB recency-of-revision | api §0.3 #3; gap-09 §6 | ✓ cited |
| §4.5 drift sample rate / threshold / re-eval / fresh-slice | 5%/h / 10% / monthly / quarterly | gap-14 §5(3) | ✓ cited |
| §4.6 recall-determinism drift tolerance | ≤5% | migration §3.1 phase 12 | ✓ cited |
| §4.8 mid-migration async-drain alarm | 1.5× gate | HANDOFF §14.6; migration §10; composition §7 | ✓ cited |
| §5.5 alarms (8 rows) | thresholds | composition §7; gap-08; gap-11; gap-14; HANDOFF §12.6 + §14.6 | ✓ cited per row |
| §6.4 review SLA / queue TTL | 24 h / 30 d | (no upstream §-ref; §11.2 acknowledges as v1 bet) | △ **Nit N3** — body should say "v1 bet" |
| §8.4 disk thresholds | 1 GB / 100 MB | composition §7 ("configurable threshold" without numbers); gap-08 §3.6 (retention-proof-before-delete ordering) | △ **Nit N4** — numbers are WS8-authored v1 bets; body should say so |
| §10.1 v2 gate condition 1 | strict-stratum operator share ≥20% | scoring §8.6; eval-plan §5.9; gap-14 §5(3) | ✓ cited |
| §10.1 v2 gate condition 2 | ≥10 000 labeled `(recall, outcome)` pairs | scoring §8.6; gap-03 §6; scoring §8.3 | ✓ cited |
| §10.2 cutover soak rule | 3 consecutive months | composition §1.1 (single-tenant baseline is irreversible-shaped); WS8 v1-bet rationale at §10.2 | ✓ explicit v1-bet rationale |

**Result: PASS with two doc-hygiene nits (N3, N4).** Every numeric default either carries a citation or is named as a v1 bet in the §11.2 result list; §6.4 + §8.4 body language could be tightened to make the v1-bet framing explicit per §0.3 #5.

### 7.3 Operator-readability (dual-audience) audit — six-section sample

Per HANDOFF §13 + composition §1.1 + WS8 §0.3 #6, every operator-facing term must be defined inline on first use OR via §0.4 cross-link. Sample sections: §1, §3, §4, §6, §7, §9.

| Section | First-use operator-vocab terms | Defined? |
|---|---|---|
| §1 (Topology) | `tenant`, `privacy boundary`, `single-writer-per-tenant` | ✓ §0.4 (`tenant`); inline at L84 + L87 ("privacy boundary"); inline at L109–113 ("single-writer-per-tenant" with rationale + `tenant_config` knob name); also gap-04 §-ref. |
| §3 (Rate-limit) | `tenant`, `principal`, `rate-limit`, `escalate-class staging cap`, `force_skip_classifier=true` (referenced indirectly via escalate-class row) | ✓ all in §0.4 (`tenant`, `principal`, `escalate / staged-for-review`); rate-limit defined inline by api §1.6 cross-ref ("api §1.6 names `429 rate_limited`"); each row's "Source" column resolves any ambiguity. |
| §4 (Operator knobs) | `gate interval`, `lock heartbeat`, `idempotency-key TTL`, `preference-cap`, `drift detector`, `recall-determinism drift tolerance`, `escalate cap`, `async-drain alarm`, `consolidate cycle`, `(peer-class)`, `v2 entry-criteria gate` | ✓ for all except `(peer-class)` parenthetical at §4.7 header (Nit N6). All others defined in §0.4 or inline. |
| §6 (Escalate-review pipeline) | `escalate / staged-for-review`, `review queue substrate`, `review SLA`, `queue TTL`, `force_skip_classifier=true`, `escalated_rejected` | ✓ §0.4 (`escalate / staged-for-review`); inline at §6.2 (review queue + schema); inline at §6.3 (`force_skip_classifier=true` rationale + auth check); inline at §6.4 (review SLA + queue TTL); inline at §6.5 (`escalated_rejected` as new terminal status). |
| §7 (Migration runtime contract) | `lethe-migrate`, `manifest`, `snapshot`, `phase-gate`, `cutover`, `capability check`, `rollback` | ✓ §0.4 (`manifest`, `snapshot`, `phase-gate`, `cutover`); inline at §7.3 (capability check ordering); inline at §7.5 (rollback scope: pre-cutover only). |
| §9 (Degraded modes) | `degraded mode`, `S3 backfill` (referenced indirectly), `tenant_scope_filter middleware` | ✓ §0.4 (`degraded mode`, `S3 backfill`); `tenant_scope_filter middleware` is composition §7 cross-ref (acceptable for an operator-action description; the operator does not invoke it directly). |

**Result: PASS with one doc-hygiene nit (N6 — `(peer-class)` at §4.7 header undefined).** Six-section sample at the densest operator-vocab surface; nineteen §0.4 terms each appear with a defined first-use anchor or inline definition. Per HANDOFF §13's "human-readable surfaces are dual-audience" cascade — confirmed at the WS8 boundary.

### 7.4 Anti-checklist audit (12 items per HANDOFF §15.4)

Reproduced verbatim from §5 stopping-criteria check above. All 12 items: **NO violation.** Two have associated doc-hygiene nits (operator-knob v1-bet naming → N3 + N4; operator-vocab inline definition → N6); none are P0.

### 7.5 D6 idempotency-key TTL ceiling parity audit

Verifies HANDOFF §15.3 decision #5: "Idempotency-key TTL: 24 h default; 7-day hard ceiling enforced at runtime startup (config validator rejects >7d). Above-ceiling escape: chunk by snapshot."

Direct quote from §4.3 (`docs/08-deployment-design.md:230–245`):

```
### §4.3 Idempotency-key TTL

**Default: 24 h** (api §1.2; gap-08 §3.1). **Operator-tunable up to a hard ceiling of 7 days.**

**Ceiling enforcement.** The config validator at runtime startup **rejects** values > 7 days
(`tenant_config.idempotency_key_ttl_seconds > 604800`). The runtime refuses to start until the
value is reduced; this is a hard fail, not a warning. Rationale: above 7 days, the
operationally-correct path is to chunk the work by snapshot (§7.4) so each chunk fits inside
the TTL window, NOT to extend the TTL further. ...

**Above-ceiling guidance (documented escape).** For migrations or batch operations exceeding
7 days, operators chunk by snapshot: split the source corpus into multiple snapshots
(migration §3.1 phase 2), run a separate migration run per snapshot, and let migration §3.2's
resumability mechanism handle within-snapshot retries. Each snapshot's run then fits inside
the 7-day ceiling.

| TTL value | Use case |
|---|---|
| 24 h (default) | Steady-state; SCNS observation rate; small migrations. |
| 24–72 h | Medium migrations; weekend ops. |
| 72 h – 7 d | Large migrations; long-running batch operations. |
| > 7 d | **Rejected by validator**; chunk by snapshot. |

**Operational metric.** `idempotency.fallback_lookup_rate_24h` ... When the rate exceeds 5%
(D8 / §5.5), the operator considers raising the TTL within the 7-day ceiling.
```

Verification:

- **Enforced (not advisory).** "rejects values > 7 days"; "runtime refuses to start until the value is reduced; this is a hard fail, not a warning". ✓
- **Mechanism.** Config validator at runtime startup; the integer comparison is `> 604800` seconds. ✓
- **Above-ceiling escape.** Chunk by snapshot, named in both the prose paragraph AND the table's `> 7 d` row, AND cross-referenced to §7.4 (snapshot UX) AND to migration §3.1 phase 2 + §3.2 (resumability). ✓
- **Range table.** Four rows from default through > 7 d are present, with the > 7 d row marked **Rejected by validator** in bold. ✓
- **Operational metric closes the loop.** `idempotency.fallback_lookup_rate_24h` exposed via `health()` (§5.2); `idempotency_fallback_high` alarm at >5% (§5.5) tells the operator when raising-toward-ceiling is the right move. ✓
- **Alarm at >5% drives operator response within ceiling, not beyond.** "operator considers raising the TTL within the 7-day ceiling"; the alarm + ceiling together create a closed feedback loop where above-ceiling escape (chunk by snapshot) is the documented operator path, not "raise TTL further." ✓

**Result: PASS.** D6 is fully closed at the WS8 boundary. The HANDOFF §14.6 "Idempotency-key TTL extension" residual, which migration §10 punted to WS8, is cleanly answered: there is no TTL extension beyond 7 days; the ceiling is enforced at startup; the chunk-by-snapshot operator path replaces TTL-stretch as the operationally-correct above-ceiling escape.

### 7.6 uuidv7 layout downstream-survival audit (WS6-N6 / WS7 §2.3 carryforward validation)

WS8 does not author uuidv7-derivation rules. Three references to `uuidv7` appear in the doc (line 173 — wire-format mapping note; line 304 — `health().migration.active_run_id` type; line 413 — `review_queue.staged_id` type). All three use `uuidv7` as a type abstraction; none re-derive bit layouts.

**Cross-derivation references.** §7.5 introduces `idempotency_key derived per migration §2.3 with discriminant "rollback"` (line 524). This invokes the migration §2.3 derivation rule with a fourth discriminant (after `"idem"`, `"epi"`, `"forget"` formalized in migration §2.3 post-WS7-nit-fix at lines 167–209).

**Cross-check vs migration §2.3 (post-WS7-nit-fix at commit `fa4a7f8`):**

| Discriminant | Formalized in migration §2.3? | Used at | RFC 9562 layout (48 + 4 + 12 + 2 + 62 = 128) |
|---|---|---|---|
| `"idem"` | ✓ lines 167–179 | Migration `remember` calls (§2.1 rows 1–7) | identical |
| `"epi"` | ✓ lines 181–195 | Episode-id derivation (Phase-gate B round-trip key) | identical |
| `"forget"` | ✓ lines 197–209 (added by WS7-nit-fix per QA-WS7 N3) | Migration `forget(invalidate)` in Phase 8 (§3.1 phase 8; §2.1 rows 8 + 9-tail) | identical |
| `"rollback"` | **NOT formalized** | WS8 §7.5 `lethe-migrate rollback` subcommand | implied identical via "per migration §2.3" wording |

The collision-disjoint property holds **operationally** (`"idem"`, `"epi"`, `"forget"`, `"rollback"` are 4 / 3 / 6 / 8 ASCII bytes respectively, all byte-distinct in the sha256 input stream `tenant_id ‖ <discriminant> ‖ source_id`; sha256 avalanche makes the four resulting 74-bit suffixes uncorrelated). The doc-hygiene gap is that migration §2.3 is no longer **closed** over all migration-time + post-migration-time discriminants once WS8 introduces `"rollback"` without a corresponding §2.3 block. This is parallel to the WS7-QA N3 pattern (`"forget"` referenced in WS7 §3.1 phase 8 but not formalized in §2.3); WS7-nit-fix (commit `fa4a7f8`) closed it for `"forget"`. WS8 introduces a second instance of the same shape, captured as Nit N2 above.

**RFC 9562 byte-layout pin (the WS6-N6 carryforward).** Verified intact in migration §2.3 post-fix:

```
48-bit ts prefix (`ts_recorded_scns`) ‖ 4-bit version `0b0111` ‖ 12-bit rand_a tail ‖
2-bit variant `0b10` ‖ 62-bit rand_b
```

with `rand_a tail ‖ rand_b = leading 74 bits of sha256(tenant_id ‖ <discriminant> ‖ source_id)`.

The WS6-N6 fix (the api §1.4 byte-layout pin) carried into WS7-nit-fix's three §2.3 blocks; the WS7→WS8 boundary preserves the layout (WS8 doesn't reauthor it). Bit math: 48 + 4 + 12 + 2 + 62 = 128. ✓

**Result: PASS-with-nit (N2).** The WS6-N6 byte-layout pin and the WS7 three-discriminant closure carry into WS8 cleanly; the only gap is the missing fourth-discriminant (`"rollback"`) formalization. This is the parity-pattern the kickoff predicted: each WS-QA validates the prior nit-fix didn't get fumbled AND catches new instances of the same shape. The fix at WS8-nit-fix (or WS7 micro-edit) is N2.

### 7.7 Cross-WS contract checks (HANDOFF §15.4 reading-order items 3–10)

Eight upstream contracts × WS8 §-refs verified:

**(i) api §0.2 + §1.6 + §2.1.2 + §3.3 + §3.4 + §4.1 + §4.3 + §4.4 + §8 ↔ WS8 §2 + §3 + §5.**

| api §-ref | What api defers | WS8 closure |
|---|---|---|
| api §0.2 | RBAC roles, capability-to-role mapping, wire format, rate-limit numbers, deployment shape | §2.1, §2.2, §2.4, §3, §1 — all closed |
| api §1.6 row 429 `rate_limited` | "WS8 cap" | §3 ten rows |
| api §1.8 cross-tenant 403 | `audit_global` capability gates cross-tenant aggregation | §2.2 row "audit() cross-tenant aggregate" → `audit_global` |
| api §2.1.2 rate-limit per `(tenant_id, principal)` | "WS8 sets value" | §3 row `recall` 30/s sustained, 60 burst |
| api §3.1 `remember` extension surface | (no extensions defined in api itself) | §6.3 + §14 introduces `force_skip_classifier=true` (the documented exception per HANDOFF §15.4 anti-checklist; flagged for WS6 implementation pass) |
| api §3.3 `forget(purge)` auth + rate-limit | `forget_purge` capability + WS8 cap | §2.2 row + §3 row 4 (per-tenant cap) |
| api §3.4 `peer_message` rate-limit | "WS8 cap" | §3 row `peer_message` 20/s sustained, 50 burst |
| api §4.1 `capture_opt_in_trace` admin auth | `tenant_admin` | §2.2 row → `tenant_admin` |
| api §4.3 `consolidate(force=true)` admin + rate-limit | `tenant_admin` + WS8 cap | §2.2 row + §3 row `consolidate(force=true)` 6/h per tenant |
| api §4.4 `health()` schema | base fields | §5.2 — preserved verbatim, additive extensions only (verified at §7.8) |

All api §-ref attach points covered. ✓

**(ii) migration §3 + §4 + §5.1 + §10 ↔ WS8 §6 + §7 + §4.8.**

- migration §3.1 phases 1–14 ↔ WS8 §7.1 twelve `lethe-migrate` subcommands (1:1 mapping with three hard phase-gates A/B/C). ✓
- migration §4 concurrency contract ↔ WS8 §1.3 (`single_writer_per_tenant=true` migration default) + `--allow-concurrent-writers` opt-in flag. ✓
- migration §5.1 `escalated`-row outcome ↔ WS8 §6.5 migration drain workflow (introduces `escalated_rejected` terminal status). ✓
- migration §10 residuals: Daily-block source-id collision → WS8 §7.4 (`snapshot_hash` augmentation); Phase 9 async-drain alarm → WS8 §4.8 (1.5× tightening); Idempotency-key TTL extension → WS8 §4.3 (7-day ceiling closes it); Phase 11 S3 backfill progress → WS8 §5.2 (`s3_backfill_progress_pct` field); manifest UX → WS8 §7.2; sensitive-content review → WS8 §6 pipeline; cross-deployment Lethe→Lethe → WS8 §7.5/§8.1 deferred; `vault.db` consumption → WS8 §0.2/§12 denied. **All 9 migration §10 residuals closed or explicitly forwarded.** ✓

**(iii) composition §7 + §7.1 ↔ WS8 §9.** 13 composition §7 rows + 3 composition §7.1 two-stores-down rows = 16; WS8 §9 has 16 rows but 1 omission ("peer-message corrupts a memory" — Nit N5) and 4 additions (clock skew, schema migration, disk full, plus 1 row reordering). Operator-action coverage **matches** the operator-actionable subset; the omitted row is content-trust / provenance, not health-surfaceable. △ N5.

**(iv) gap-01 §3.2 Q3 ↔ WS8 §4.1 + §4.2.** gap-01 commits "per-tenant lock + 30-second heartbeat is the v1 baseline"; does not pin gate interval. WS8 §4.2 inherits 30s heartbeat + 60s break (= 2× heartbeat); WS8 §4.1 names 15-min gate interval as v1 bet with five-row range table. ✓

**(v) gap-08 §3.4 + §3.5 + §3.6 ↔ WS8 §4.2 + §8.2 + §8.3 + §8.4.**
- gap-08 §3.4 lock recovery → WS8 §4.2 (lock break) + §8.3 (`lethe-admin lock` recovery commands). ✓
- gap-08 §3.5 startup integrity → WS8 §8.2 (`lethe-audit lint --integrity` runtime invocation + reconcile mode + migration phase-gate A/C invocations). ✓
- gap-08 §3.6 retention-proof-before-delete → WS8 §8.4 (refuse `forget(purge)` at < 100 MB free; "purge writes a retention proof BEFORE the delete per gap-08 §3.6, and the proof must succeed"). ✓

**(vi) gap-14 §5(3) ↔ WS8 §4.5 + §5.5 (`drift_high` alarm).** gap-14 §5(3) commits 5%/h sample, 10% threshold, monthly re-eval, quarterly fresh slice; WS8 §4.5 lifts all four to operator-knob form with §-ref. ✓

**(vii) scoring §8.6 ↔ WS8 §10.** Two gates verbatim: strict-stratum operator share ≥20% + ≥10 000 labeled `(recall, outcome)` pairs. Lifted to `health().v2_gate.{strict_stratum_operator_share_pct, labeled_pairs}` gauges. 3-month soak rule is **additive** to scoring §8.6 (not contradictory): scoring §8.6 says *what* the gate is; WS8 §10.2 says *how stable* the gate must be before unlocking the cutover. ✓

**(viii) HANDOFF §10 + §12.6 + §13 + §14.6 ↔ WS8 §13 traceability.** Spot-checked five rows in §13: §4.3 → api §1.2 + gap-08 §3.1 + HANDOFF §14.6 ✓; §10 → scoring §8.6 + composition §1.1 ✓; §4.5 → gap-14 §5(3) ✓; §3 row `forget(purge)` → api §3.3 step 2 + gap-11 §3.3 ✓; §6.3 `force_skip_classifier=true` → api §3.1 (extension noted for WS6 implementation pass) ✓. No TBD rows; no broken §-refs.

**Result: PASS with two minor nits (N2 rollback discriminant, N5 §9 row omission rationale).** All eight upstream-contract surfaces are honored at the WS8 §-refs; the deferral chain WS3→WS4→WS5→WS6→WS7→WS8 closes here.

### 7.8 `health()` additivity audit (api §4.4 ↔ WS8 §5.2 field-by-field diff)

| Field path | api §4.4 type | WS8 §5.2 type | Verdict |
|---|---|---|---|
| `overall` | `"healthy" \| "degraded" \| "down"` | `"healthy" \| "degraded" \| "down"` | identical |
| `stores.s1` | `"up" \| "down"` | `s1, ..., s5: ...` (preserved by reference; WS8 elides sub-shape with `...`) | preserved-by-elision |
| `stores.s2` | `"up" \| "down"` | (same) | preserved-by-elision |
| `stores.s3` | `"up" \| "stale" \| "down"` | (same) | preserved-by-elision |
| `stores.s4a` | `"up" \| "down"` | (same) | preserved-by-elision |
| `stores.s4b` | `"up" \| "stale"` | (same) | preserved-by-elision |
| `stores.s5` | `"up" \| "down"` | (same) | preserved-by-elision |
| `degraded_modes` | `[ string ]` | `[ string ]` | identical |
| `daemon.last_successful_consolidate_at` | `RFC3339` | `RFC3339` | identical |
| `daemon.current_run_id` | `uuidv7?` | `uuidv7?` | identical |
| `daemon.current_phase` | `string?` | `string?` | identical |
| `daemon.backoff_until` | `RFC3339?` | `RFC3339?` | identical |
| `emitter.drop_count_24h` | `int` | `int` | identical |
| `emitter.last_drop_reason` | `string?` | `string?` | identical |
| **`migration`** (object, all sub-fields) | (absent) | new | additive |
| `migration.active_run_id` | — | `uuidv7?` | added |
| `migration.active_phase` | — | enum (snapshot \| inventory \| phase_gate_a \| s4a_import \| s1_import \| phase_gate_b \| invalidation \| async_drain \| phase_gate_c \| s3_backfill \| recall_probe \| cutover \| post_cutover_s4b_regen) | added |
| `migration.s3_backfill_progress_pct` | — | `float?` 0.0–1.0 | added (closes migration §10 residual) |
| `migration.rows_pending` / `rows_done` / `rows_escalated` / `rows_failed` | — | `int` × 4 | added |
| **`idempotency`** (object) | (absent) | new | additive |
| `idempotency.key_ttl_seconds` | — | `int` | added |
| `idempotency.fallback_lookup_rate_24h` | — | `float` | added (drives §5.5 `idempotency_fallback_high` alarm) |
| **`escalation_queue`** (object) | (absent) | new | additive |
| `escalation_queue.depth_pending_review` | — | `int` | added |
| `escalation_queue.oldest_pending_age_hours` | — | `float` | added |
| **`drift`** (object) | (absent) | new | additive |
| `drift.last_eval_at` | — | `RFC3339` | added |
| `drift.last_eval_drift_pct` | — | `float` | added |
| `drift.next_scheduled_eval_at` | — | `RFC3339` | added |
| **`v2_gate`** (object) | (absent) | new | additive |
| `v2_gate.strict_stratum_operator_share_pct` | — | `float` | added |
| `v2_gate.labeled_pairs` | — | `int` | added |
| `v2_gate.consecutive_months_green` | — | `int` | added |

**Diff summary:** zero existing fields renamed; zero existing fields removed; zero existing-field semantic changes; five new top-level keys added (`migration`, `idempotency`, `escalation_queue`, `drift`, `v2_gate`). The api §4.4 invariant "`health()` never errors above the transport layer" is preserved by §5.2's "when a sub-system is unreachable, the corresponding field is `null` or omitted, never a 5xx."

**Result: PASS.** WS8 `health()` extensions are strictly additive on api §4.4. Existing api consumers continue to read the same fields with the same shapes; new operator-tooling-pass consumers (metrics exporter, dashboards, the `lethe-migrate status` HTML page) read the additive fields. HANDOFF §15.3 decision #7 ("`health()` extensions are additive only to api §4.4 — no breaking change to the published api surface") is honored.

---

## 8. Closing

WS8 closes the WS3→WS8 deferral chain cleanly. The doc that I expected to be the most over-spec-prone — a deployment design with sixteen operator knobs, eleven rate-limit rows, eight must-wire alarms, twelve `lethe-migrate` subcommands, sixteen degraded-mode rows, fifteen sections plus residuals — is instead the most **disciplined** at the operator boundary: §0.4 nineteen-term operator-vocabulary index is the keystone that lets §3 / §4 / §5 / §6 / §7 / §9 stay knob-focused without re-defining vocabulary on every page, and §13 traceability matrix makes every numeric default's upstream §-ref one grep away. The `idempotency_key_ttl_seconds > 604800` runtime-startup rejection rule (§4.3) is the single sharpest commitment in the doc — it converts the gap-08 §5 "TTL is a guess and we should instrument" residual into a hard ceiling with a documented above-ceiling operator path, replacing TTL-stretch with chunk-by-snapshot as the operationally-correct shape.

The decision to put `forget_purge` capability on `tenant_admin` rather than gating it to `operator`-only (§2.1 rationale) is the right architectural call: hard-delete is data-sovereignty, not ops-fleet. The §3 row 4 per-tenant `forget(purge)` cap (rather than per-principal) is the correct counterweight — it prevents the multiple-admin-aggregation bypass HANDOFF §15.4 anti-checklist explicitly forbids — and the §5.5 `forget_purge_rate_spike` alarm (P1) closes the loop with a behavioral check on top of the structural cap.

The decision to defer the `force_skip_classifier=true` formal addition to api §3.1 to the WS6 implementation pass (§6.3 footnote + §14) is the right shape for an ongoing-doc-update — WS8 owns the contract, WS6's implementation pass owns the api-doc edit. The single-line addition with `tenant_admin` auth check is unambiguous; until then, this doc is the contract reference. Same shape as the WS7→WS8 punt for the migration-tool source code: the contract lives one layer up; the bytes follow.

The decision to make v2 multi-tenant cutover require a runtime upgrade rather than a config flip (§1.4 + §10.2) is the right shape for an irreversible-shaped boundary: composition §1.1 single-tenant-per-deployment cannot be unwound without a fleet migration spec that does not exist; the 3-month soak rule prevents flap; the cutover decision is a deliberate operator action, not a configuration drift.

The eight numbered nits are bundleable into a single `docs(ws8):` nit-fix commit. The P1 finding (N1, the §6.3 vs §6.5 internal contradiction on `idempotency_key` on the approve path) is a doc-wording fix, not a contract change; the §6.5 reading is the operationally-correct one and §6.3 should be reconciled to match. The seven doc-hygiene nits (N2–N8) are bundleable alongside.

The rollback-discriminant carryforward nit (N2) is the same shape as WS7-QA N3 (the `"forget"` discriminant referenced but not formalized) and is a useful test of the cross-WS-QA parity pattern: each WS-QA validates the prior nit-fix didn't get fumbled AND catches new instances of the same shape at the next layer. WS7-nit-fix (commit `fa4a7f8`) closed `"forget"`; WS8-nit-fix should close `"rollback"` (either by adding a fourth block to migration §2.3, or by inline-formalizing the derivation in WS8 §7.5).

After WS8-nit-fix lands, `docs/IMPLEMENTATION.md` (per `PLAN.md` §Deliverables line 4) is the right closing artifact: a top-level index naming the implementation workstreams (operator-tooling pass; runtime substrate implementation; eval harness; metrics pipeline) and pointing at WS3–WS8 as the contract references, with each WS's §-residual section feeding the implementation backlog. The seven WS deferral chain closes; the implementation cycle opens.

**Verdict: APPROVE-WITH-NITS. Proceed to WS8-nit-fix, then `docs/IMPLEMENTATION.md`.**
