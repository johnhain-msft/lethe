# WS6 QA — Canonical API Surface (fresh-eyes review)

**Reviewer:** WS6-QA (cold pass, no exposure to WS6 implementation session).
**Artifacts under review:** `docs/06-api-design.md` (1060 lines, commit `8d7361e`); `docs/HANDOFF.md` §12 (post-WS6 entry, same commit).
**Reading order followed:** HANDOFF §12 → §10 → §11.5 → `06-api-design.md` start to finish → spot-checks on composition §3/§4/§5/§7, scoring §4/§6/§8, gap-04, gap-05, gap-08, gap-09, gap-10, gap-11, gap-12, eval-plan §4.6, `scripts/eval/metrics/emitter.py` → three audits re-run live.

---

## 1. Verdict

**APPROVE-WITH-NITS.**

WS6 gives a WS7 (migration) author and a WS6 implementation author enough verb-surface substrate to begin without re-deriving API semantics. All eleven anti-checklist items in HANDOFF §12.4 are respected. Zero residual SCNS dependency at the verb surface. The three internal audits the doc commits to (SCNS-independence, idempotency-key coverage, emit-point coverage) all reproduce cleanly under fresh `grep`. Six minor inconsistencies (numbered nits below) are doc-hygiene only and do not block WS7.

Headline answer to the gating question: **YES** — `docs/06-api-design.md` is precise enough that (a) WS7 can plan a SCNS-data → Lethe-store ingest by mapping each SCNS observation onto the existing `remember` / `forget(invalidate)` calls (§3.1 + §3.3) without inventing a shim verb, and (b) the WS6 implementation pass can write the verb stubs from §1–§5 alone without re-reading the gap briefs.

Eight gating questions answered:

| # | Question | Answer | Citation |
|---|---|---|---|
| 1 | Bi-temporal validity filter applied **pre-retrieval** verifiable? | **YES** | §2.1 step 1 (line 259): "exclude … from the candidate set entirely. This is the pre-RRF gate; not a post-score filter." Reinforced §0.3 #2 (line 47). |
| 2 | Preference 10 KB cap **unconditional** (does not gate inclusion; ordering inside cap allowed)? | **YES** | §0.3 #3 (line 48); §2.1 step 10 (line 268) — "concatenate up to 10 KB; truncate by recency-of-revision"; `preferences_truncated` exposed (line 236). Inclusion is unconditional; ordering is by revision-recency (see Nit N4 on wording vs HANDOFF §11.5). |
| 3 | `recall_id` deterministic and keyed exactly per HANDOFF §11.5? | **YES** | §1.4 lines 96–109: `uuidv7(tenant_id, ts_recorded, query_hash)`; `query_hash = sha256(canonical_json({query, intent, k, scope}))[:16]`; suffix bits derived from `sha256(tenant_id ‖ query_hash)`, not CSPRNG. (See Nit N6 on byte-layout precision.) |
| 4 | All six `consolidate_phase` emit-points around `remember()` enumerated? | **YES** | §3.1 lines 514–525: explicit ordered table — extract → score → promote → demote → consolidate → invalidate. Reaffirmed §0.3 #7 (line 52) and §5 emit-point matrix (line 938). |
| 5 | §3.3 uses gap-11 vocabulary canonical with documented aliases? | **YES** | §3.3 line 613 (`"invalidate" \| "quarantine" \| "purge"`); alias table lines 620–628 (`soft → invalidate`, `deny → quarantine`). |
| 6 | §1.6 error taxonomy includes 409 (CAS), idempotency-replay 200, forget-deny? | **YES** | §1.6 table lines 134–151: 200 `idempotency_replay` (137), 409 `version_conflict` (145), 409 `idempotency_conflict` (146), 403 `forget_denied` (143). |
| 7 | §1.4 `recall_id` derivation specific enough that two engineers implement identically? | **YES with caveat** | §1.4 names the input tuple, the hash function (sha256, 16-byte truncation), the canonicalization (`canonical_json`), and the suffix derivation (`sha256(tenant_id ‖ query_hash)`). The exact uuidv7 byte-layout (which bits are timestamp vs. derived suffix) is deferred to WS8 with a "cannot break determinism" guarantee — see Nit N6. |
| 8 | Doc explicitly disclaims transport / wire / auth / RBAC / deployment? | **YES** | §0.2 lines 32–37 (transport, wire, auth, RBAC, rate-limit values, deployment) and §8 lines 1041–1054 (closing restatement, with explicit denial of SCNS shim and SCNS-shaped verbs). |

---

## 2. Per-section scoring rubric

| § | Score | One-line rationale |
|---|---|---|
| §0 Frame | 5/5 | Owns/does-not-own boundaries (§0.1, §0.2) with exhaustive enumeration; binding constraints from HANDOFF §10 + §11.5 are restated as the eight items in §0.3, each cross-linked to the body. |
| §1 Cross-cutting contracts | 4.5/5 | §1.1–§1.8 each carry one claim with explicit consequences. Idempotency contract §1.2 is precise (24 h TTL, replay→200, conflict→409, mandatory→400). CAS contract §1.3 names idempotency-replay precedence. `recall_id` derivation §1.4 is deterministic (caveat: byte-layout deferred — N6). Provenance §1.5 names two-step peer-message materialization. Error taxonomy §1.6 covers all 11 anti-checklist hot-paths. Half-point off for one taxonomy/body inconsistency (N1). |
| §2 Read verbs | 5/5 | `recall(query)` algorithm is **pre-retrieval-filter-first** (step 1, line 259) and the §0.3 #2 binding is verifiable line-by-line. `k=0` shape (§2.1.1) is sound: `recall_id` returned, zero `recall` events, ledger row still written. `recall_synthesis` (§2.2) is correctly distinct from the fact path: no bi-temporal filter (S4a is git-versioned, not bi-temporally stamped), `path=synthesis` marker on the emit. `peer_message_pull/_status` (§2.3, §2.4) carry `cap_dropped_since_last_pull` and the `pending|delivered|acked|expired|dropped_cap` lifecycle. |
| §3 Write verbs | 4.5/5 | `remember` (§3.1) full envelope including `classified_intent`, `retention_class`, `accepted`, `escalated`, `ack`, `next_consolidate_at`. Six `consolidate_phase` emit-points enumerated in order with checkpoint semantics. `promote` and `forget` correctly named "intended-not-applied" (decision #9). `forget` modes are gap-11 canonical with aliases. **`forget(purge)` retention-proof-before-delete ordering** is explicit (§3.3 lines 668–670). Half-point off for two minor cross-ref/error-code inconsistencies (N1, N3). |
| §4 Operator/admin | 5/5 | `capture_opt_in_trace` (§4.1) idempotent, per-tenant, revocable; revocation queues retirement of previously-ingested cases (eval-plan §4.6 step 1); SCNS `session_store` explicitly excluded as a source. `emit_score_event` (§4.2) is correctly framed as **internal sink** not external verb (decision #7). `consolidate` (§4.3) admin trigger with phase reporting. `health()` and `audit()` (§4.4) operational reads with degraded-mode signaling. |
| §5 Emit-point matrix | 5/5 | Authoritative per-verb table; covers all 14 verbs + sink + admin. Sync vs. async cardinalities are explicit. Order constraints stated (e.g., `forget(purge)` is sync; `forget(quarantine)` cascade is async-serialized). Replayability invariant restated (line 953). |
| §6 Traceability matrix | 5/5 | Every verb maps to (composition §, gap §, scoring §). No TBD rows. The cross-refs survive spot-check: `recall` cites scoring §4.1–§4.5, gap-09 §6, gap-12 §3+§6, gap-05 §3 — each verifiable. |
| §7 Verification audits | 5/5 | All three audits transcribed in-doc and reproduce under live `grep` (§7 below). 14 SCNS hits, 14 boundary-clause classifications. 5/5 idempotency-key coverage. 7/7 emit-point coverage. |
| §8 Anti-checklist | 5/5 | Twelve explicit denials — transport, wire, auth, RBAC, rate-limit values, deployment, SCNS shim, SCNS-shaped verbs, scoring math, eval composition, retention internals, schema migration. Each named in WS6 anti-checklist (HANDOFF §12.4) is denied here. |

**Decisions (HANDOFF §12.3) honored:**

| Decision | Resolution required | Verified at |
|---|---|---|
| #1 forget vocabulary canonical, soft/deny aliases | gap-11 names primary | §3.3 lines 613, 620–628 |
| #2 `remember()` returns full envelope | sync classifier, async extract | §3.1 response schema lines 478–493 |
| #3 `peer_message_*` sync request, async pull-delivery | gap-10 §3.4–§3.5 | §2.3 line 407, §3.4 lines 717, 725 |
| #4 `recall(k=0)` legal, preferences-only, zero `recall` events | replay-invariant on empty case | §2.1.1 lines 287–292 |
| #5 `recall_synthesis` emits `recall` events with `path=synthesis` | distinct from facts | §2.2 lines 352–355 |
| #6 `capture_opt_in_trace` admin / per-tenant / revocable | eval-plan §4.6 step 1 | §4.1 lines 776–778 |
| #7 `emit_score_event` internal sink, not external verb | scoring §8.4 | §4.2 lines 796–841 |
| #8 `forget(quarantine)` returns estimated `cascade_count` | finalize via `audit()` | §3.3 lines 638, 659 |
| #9 `promote` / `forget` ack `intended_not_applied` | composition §4.2 | §3.2 line 569, §3.3 line 641 |

---

## 3. Major findings

**None.** No P0 (anti-checklist violation) and no P1 (under-specified emit-point or contract).

The three highest-stakes items — bi-temporal-filter-pre-retrieval (anti-checklist HANDOFF §12.4 item 4), preference-not-score-gated (anti-checklist item 5), `forget(purge)` proof-before-delete ordering (anti-checklist item 8) — are each **structurally** enforced by the algorithm steps and survived spot-check.

---

## 4. Nits (one-liners; doc-hygiene only)

- **N1** (`docs/06-api-design.md:505`) — §3.1 step 4 maps `peer_route` class to `422 invalid_request`, but §1.6 (lines 138, 149) maps `invalid_request` to **400** and reserves **422** for `classifier_escalate`. The status/symbol pairing is internally inconsistent. Recommend: `peer_route → 400 invalid_request` with hint `use_peer_message`.
- **N2** (`docs/06-api-design.md:260` vs `:501`) — §2.1 step 2 says caller-supplied intent is honored "unless classifier audit objects at ≥0.8 confidence"; §3.1 step 3 says "honored only if classifier audit confidence is < 0.8 *against* the caller's tag." The §3.1 wording is the precise one (the audit must dissent, with ≥0.8, from the caller's tag); the §2.1 wording is ambiguous about whether the threshold applies to agreement or dissent. Recommend: align §2.1 to §3.1's wording.
- **N3** (`docs/06-api-design.md:544` and `:727`) — Both cite `gap-11 §3.3` as the basis for the sensitive-class send-time scan / quota. The primary reference for sensitive-class scanning at peer-message send is **gap-10 §6**; gap-11 §3.3 is the purge auth-class section, which is a related but distinct safety surface. Recommend: cross-ref `gap-10 §6` (primary) `+ gap-11 §3.3` (auxiliary).
- **N4** (`docs/06-api-design.md:268` vs HANDOFF §11.5 line 512) — HANDOFF §11.5 says "Recall-time scoring orders preferences inside the cap"; §2.1 step 10 says "truncate by recency-of-revision." Both honor the binding constraint (inclusion is unconditional; the cap rules ordering, not gating), and gap-09 §6 does not pin an ordering. The doc's choice (recency-of-revision) is reasonable, but the wording divergence with HANDOFF §11.5 should be reconciled — either by §0.3 #3 noting that the doc adopts recency-of-revision, or by §2.1 step 10 noting the choice and citing gap-09 §6.
- **N5** (`docs/06-api-design.md:619`) — §3.3 declares `expected_version: int   // version of fact_id (mode=invalidate) or episode_id (mode=quarantine\|purge)`. For `mode=purge` with `target.fact_id` (purging a single fact-edge, not a whole episode), the comment implies the version comes from an episode, which is wrong — fact-edges have their own version. Recommend: "version of `fact_id` (mode=invalidate **or** mode=purge with fact_id target) or `episode_id` (mode=quarantine, or mode=purge with episode_id target)."
- **N6** (`docs/06-api-design.md:109`) — §1.4 implementation note delegates the exact uuidv7 byte-layout to WS8 with the constraint "cannot break determinism." Two engineers implementing against the same spec will produce identical IDs only after WS8 freezes the layout. Recommend: pin the layout in §1.4 (e.g., "48-bit ms timestamp prefix per RFC9562; 76-bit deterministic suffix = `sha256(tenant_id ‖ query_hash)[0:10]`; 4 version bits + 2 variant bits per RFC9562") to make the spec engineer-portable today.

---

## 5. Stopping-criteria check

Per HANDOFF §12.4 anti-checklist (P0 if violated):

| Anti-checklist item | Violated? | Evidence |
|---|---|---|
| Verb whose request schema names SCNS / `~/.scns/` / `session_store` / foreign data source | **NO** | §7.1 audit + live grep below — 14 hits, all boundary clauses. |
| Verb whose response mirrors a SCNS verb shape for compatibility | **NO** | §8 line 1050 explicit denial; verb shapes derive from gap briefs. |
| `remember` bypasses gap-12 classifier or accepts caller intent without ≥0.8 audit gate | **NO** | §3.1 step 3 (line 500–501) enforces the audit gate. |
| `recall` runs retriever before §4.1 bi-temporal filter, or skip-on-small | **NO** | §2.1 step 1 (line 259) — "exclude … entirely. This is the pre-RRF gate; not a post-score filter." |
| Preferences-prepend gates inclusion on score | **NO** | §0.3 #3 (line 48); §2.1 step 10 — unconditional concat to cap, truncate by revision recency. |
| Write verb without mandatory `idempotency_key` | **NO** | §7.2 — 5/5 PASS; live re-grep below. |
| Mutating verb without `expected_version` (excluding `remember`) | **NO** | `promote` §3.2 line 557, `forget` §3.3 line 616, `peer_message` carries `idempotency_key` only as it creates new — §1.3 line 94 names this exception. |
| `forget(purge)` deletes before retention proof to S5 | **NO** | §3.3 lines 668–670 — proof written to S5 *first*, atomic T2; rolls back proof on delete failure (gap-08 §3.6). |
| `recall_id` non-deterministic CSPRNG | **NO** | §1.4 line 109 — suffix bits from `sha256(tenant_id ‖ query_hash)`, explicitly "rather than from a CSPRNG." |
| External `emit_score_event` verb | **NO** | §4.2 lines 796–841 — internal sink; decision #7. |
| Transport / RPC / wire / auth / RBAC / deployment commitment | **NO** | §0.2 + §8 — twelve explicit denials. |

Per HANDOFF §12.4 stopping criteria for WS6:

| Criterion | Met? |
|---|---|
| Verb set spec'd: read + write + admin | **YES** (§2 + §3 + §4; 12 verbs + sink) |
| Cross-cutting contracts: idempotency, CAS, recall_id, provenance, error taxonomy, multi-tenant | **YES** (§1.1–§1.8) |
| Six `consolidate_phase` emit-points enumerated around `remember` | **YES** (§3.1 lines 516–525) |
| `forget` mode vocabulary canonical with aliases documented | **YES** (§3.3 lines 613, 620–628) |
| `recall(k=0)` shape sound and replay-invariant-compatible | **YES** (§2.1.1) |
| `recall_synthesis` distinct from `recall`, with `path=synthesis` marker | **YES** (§2.2) |
| Emit-point matrix authoritative per verb | **YES** (§5 lines 934–951) |
| Traceability matrix with no TBD rows | **YES** (§6 lines 962–976) |
| Three audits transcribed and live-re-runnable | **YES** (§7.1–§7.3; reproduced below) |
| Anti-checklist as closing section | **YES** (§8) |

---

## 6. Ready-for-WS7 statement

**Ready for WS7 (migration author): YES.**

- §3.1 (`remember`) is the canonical landing verb for migrated SCNS observations. Mandatory `idempotency_key` + `provenance.source_uri` give WS7 the durability to mint stable per-observation keys (e.g., `uuidv7(tenant_id, scns_observation_id)`) and preserve SCNS observation-ids as `provenance.source_uri` — the audit-trail invariant from gap-05 §6 survives the cutover.
- §3.3 (`forget(invalidate)`) is the canonical mode for SCNS archive entries. SCNS has no quarantine or purge analog, so `mode=invalidate` is the only forget-mode WS7 exercises.
- §1.4 + §1.5 (deterministic `recall_id` + provenance envelope) together establish the migration invariant: episode-ids are freshly minted Lethe-side; the SCNS-side identifier rides through as `provenance.source_uri`. WS7 does not need to forge SCNS-shaped ids into the verb surface.
- §0.3 #1 + §7.1 + §8 line 1049–1050 together close the door on the temptation to introduce a SCNS shim verb. Migration is a one-way ingest *through the existing verb surface*.
- §1.6 + §1.2 + §1.3 give WS7 the error semantics it needs to plan a restartable, partial-failure-tolerant migration: 200 idempotency-replay on retry; 409 idempotency_conflict if WS7 sends a different body for the same key (which it must therefore not do); 409 version_conflict if a target was modified between `recall` and `forget` (which WS7 must therefore CAS-resolve).

**Ready for the WS6 implementation pass: YES.** §1–§5 collectively are sufficient that an implementer can write the verb stubs, response schemas, and emit-point hooks without re-reading the gap briefs. The two verbs to be implemented in code (`capture_opt_in_trace` external; `emit_score_event` internal) have their contract surfaces nailed in §4.1 and §4.2 respectively.

---

## 7. Audit transcripts

### 7.1 SCNS-independence audit (re-run live)

```
$ grep -in -E "scns|session_store|~/\.scns" docs/06-api-design.md
```

**14 hits, all classified as boundary clauses:**

| Line | Content (excerpt) | Classification |
|---|---|---|
| 5 | "Cross-refs: … gates WS7 (migration sees the verb surface as the import target — not a SCNS shim)" | **Boundary clause — frame disclaimer.** |
| 46 | §0.3 #1: "No SCNS compatibility shim. No verb reads from `~/.scns/`, no verb imports from the SCNS repo, no verb-side data source is SCNS." | **Boundary clause — binding constraint.** |
| 792 | §4.1: "This verb does NOT import traces from any foreign system. SCNS `session_store` is not a source." | **Boundary clause — `capture_opt_in_trace` source disclaimer.** |
| 982 | §7.1 audit heading | **Audit context.** |
| 986 | §7.1 audit command | **Audit command.** |
| 988 | §7.1 expected result | **Audit expectation.** |
| 992 | §7.1 result enumeration | **Audit transcript.** |
| 993 | §7.1: "Zero verb signatures, zero schema fields, zero data sources reference SCNS." | **Audit assertion.** |
| 994 | §7.1: "`capture_opt_in_trace` ingests only Lethe's own trace store … SCNS `session_store` is explicitly excluded." | **Audit boundary clause.** |
| 996 | §7.1: "every hit should be a disclaimer or boundary clause, not a dependency" | **Audit instruction.** |
| 1049 | §8: "A SCNS compatibility shim. … No verb in this surface reads from `~/.scns/`, imports from the SCNS repo, or accepts SCNS schemas/types/data sources." | **Anti-checklist denial.** |
| 1050 | §8: "SCNS-shaped verbs. No verb in this surface mirrors a SCNS verb signature." | **Anti-checklist denial.** |
| 1054 | §8: "Schema migration policy. WS7 owns SCNS-data → Lethe-store migration (a one-way ingest into the verb surface, not a dependency)." | **Anti-checklist denial.** |

Plus two `session_store` hits both within the §4.1 / §7.1 disclaimer text (no new lines).

**Result: PASS.** Zero hits name SCNS as a verb signature, schema field, or data source. All 14 are disclaimers, audits, or anti-checklist denials.

### 7.2 Idempotency-key coverage audit (re-run live)

```
$ grep -n "idempotency_key" docs/06-api-design.md | grep -E "^([0-9]+):.*\b(remember|promote|forget|peer_message|capture_opt_in_trace)\b\("
```

| Verb | Mandatory in signature? | Cite |
|---|---|---|
| `remember` | **yes** | §3.1 line 467 (`idempotency_key: uuidv7, // mandatory; §1.2`) |
| `promote` | **yes** | §3.2 line 556 |
| `forget` | **yes** | §3.3 line 615 |
| `peer_message` | **yes** | §3.4 line 704 |
| `capture_opt_in_trace` | **yes** | §4.1 line 756 |

§1.2 line 83 enforces the contract globally: missing key → `400 missing_idempotency_key`. §1.6 line 138 confirms in the taxonomy.

**Coverage: 5/5 write verbs PASS.**

### 7.3 Emit-point coverage audit (re-run live)

Cross-check scoring §8.1 (lines 379–391, seven event types) against the §5 verb-side matrix.

| Scoring §8.1 event | Emitted by which verb(s) | Cite |
|---|---|---|
| `remember` | `remember` (sync) | §3.1 step 7, line 511; §5 line 938 |
| `recall` | `recall` (sync × top-k); `recall_synthesis` (sync × pages, with `path=synthesis`) | §2.1 step 11, line 269; §2.2 line 347; §5 lines 936–937 |
| `recall_outcome` | downstream telemetry tied to `recall_id` | §1.7 line 163; §5 lines 936–937 |
| `promote` | `promote` (async, consolidate phase 3) | §3.1 phase 3 line 522; §5 line 941 |
| `demote` | async dream-daemon (consolidate phase 4) | §3.1 phase 4 line 523; §5 — referenced via `consolidate` line 950 |
| `invalidate` | `forget(invalidate)` async; `forget(quarantine)` cascade async; `forget(purge)` sync (with `purge=true` marker); contradiction handling async | §3.3 lines 652, 661, 672; §5 lines 942–944 |
| `consolidate_phase` | `remember` × 6 around the post-write cycle; `consolidate` admin trigger × 6 | §3.1 lines 514–525; §4.3 line 868; §5 lines 938, 950 |

**Coverage: 7/7 PASS.**

### 7.4 Sink-addability spot-check (`scripts/eval/metrics/emitter.py`)

Live read: 91 lines; module-level functions `render_headline_tag` (line 51), `write_run_report` (line 63), `enforce_two_strata` (line 70), `enforce_cost_with_accuracy` (line 78). Pattern is a flat collection of sibling functions sharing the per-run report-dir invariant. Adding `emit_score_event(event)` per API §4.2 lines 800–809 is structurally compatible — it is one more module-level function with the same per-tenant on-disk layout the docstring already describes. The promise scoring §8.4 made (and which API §4.2 inherits) is met.

---

## 8. Closing

WS6 closes the API surface cleanly. The doc that I expected to be the easiest to over-spec — `forget` with three modes, two aliases, and an auth-class branch — is the most disciplined: §3.3 separates synchronous (`purge`) from async (`invalidate`, `quarantine`), names the retention-proof-before-delete ordering structurally, and surfaces estimated-vs-final `cascade_count` semantics so callers don't conflate the two. The decision to make `emit_score_event` an internal sink rather than an external verb (decision #7) is the right call: it keeps the public surface narrow and locks the v2 training-signal pipeline to the in-process emitter co-located with the existing batch-report sink.

The six nits are doc-hygiene; none warrant blocking WS7. They can be cleaned up alongside the §12.6 follow-throughs (per-tenant rate-limit values, capability-to-role mapping, wire-format/transport choice — all WS8).

**Verdict: APPROVE-WITH-NITS. Proceed to WS7.**
