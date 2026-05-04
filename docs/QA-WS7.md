# WS7 QA — Migration Design (fresh-eyes review)

**Reviewer:** WS7-QA (cold pass, no exposure to WS7 drafting session).
**Artifacts under review:** `docs/07-migration-design.md` (545 lines, commit `11e6366`); `docs/HANDOFF.md` §14 (post-WS7 entry, commit `6010009`).
**Reading order followed:** HANDOFF §14.4 verbatim — `07-migration-design.md` start to finish → composition §1.1 (dual-audience principle) + §2 + §5 + §6 + §7 → gap-08 §3.5 (phase-gate A/C) → gap-05 §3 + §6 (phase-gate B; provenance) → gap-09 §3 + §6 + §7 (preference / procedure / narrative shapes; 10 KB cap) → gap-04 §3 + §4 (cold-start vs warm-tenant) → gap-11 §3 (forget vocabulary) → api §1.2/§1.3/§1.4/§1.5/§3.1/§3.3/§4.1 → eval-plan §4.6 → HANDOFF §10 + §11.5 + §12.5 → five audits re-run live.

---

## 1. Verdict

**APPROVE-WITH-NITS.**

WS7 gives an operator (and a future migration-tool implementer) enough substrate to plan and execute an in-place SCNS-corpus → Lethe-tenant migration without re-researching upstream contracts. All twelve anti-checklist items in HANDOFF §14.4 are respected. Zero residual SCNS dependency at the post-cutover runtime surface. The four internal audits the doc commits to (SCNS-independence, idempotency-key coverage, phase-gate coverage, markdown-audience) all reproduce cleanly under fresh `grep`. The fifth audit the kickoff explicitly requested — uuidv7 layout parity vs api §1.4, validating the WS6-N6 carryforward — passes: bit math is identical (48 + 4 + 12 + 2 + 62 = 128) and the `"idem"` / `"epi"` discriminant strategy prevents collision-by-construction over identical source bytes. Six minor inconsistencies (numbered nits below) are doc-hygiene only and do not block WS8.

Headline answer to the gating question: **YES** — `docs/07-migration-design.md` is precise enough that (a) an operator can run a SCNS-corpus → Lethe-tenant migration phase-by-phase against the existing api §2–§4 verb surface without inventing a shim, and (b) a migration-tool implementer can write the CLI / manifest / phase-gate runners directly from §1–§6 alone without re-reading the gap briefs.

Eight gating questions answered:

| # | Question | Answer | Citation |
|---|---|---|---|
| 1 | Three hard phase-gates present and hard-halt on failure? | **YES** | §3.1 Phase 4 (gate A — `lethe-audit lint --integrity`), Phase 7 (gate B — episode-id sample round-trip), Phase 10 (gate C — provenance + integrity + forget-proof lints); §3.1 prose ("Phase-gate failures halt the run"); §5 halt rows. |
| 2 | Idempotency-key derivation deterministic, RFC 9562-conformant, parallel to api §1.4? | **YES** | §2.3 lines 167–179: 48-bit `ts_recorded_scns` prefix + 4-bit version `0b0111` + 12-bit `rand_a` + 2-bit variant `0b10` + 62-bit `rand_b`; deterministic 74 bits from `sha256(tenant_id ‖ "idem" ‖ scns_observation_id)`. |
| 3 | Episode-id derivation deterministic, layout-parallel to idempotency-key, discriminant prevents collision? | **YES** | §2.3 lines 181–193: identical layout, discriminant `"epi"` (vs `"idem"`); collision argument explicit at line 179. |
| 4 | Every §2.1 mapping row carries `idempotency_key` + `provenance.source_uri = scns:<shape>:<id>`? | **YES** | §6.6.2 9/9 PASS; reproduced under fresh re-run (§7.2 below). |
| 5 | `capture_opt_in_trace` excluded from migration path? | **YES** | §3.5 explicit; §0.3 #5; §8 anti-checklist. |
| 6 | No `migrate_*` verb / no SCNS shim / no post-cutover SCNS read path? | **YES** | §0.2, §0.3 #1, §3.5, §6.6.1, §8; §3.1 phase 13 cutover is the cut-line. |
| 7 | Markdown dual-audience (composition §1.1 + HANDOFF §13) preserved? | **YES** | §0.3 #8 explicit affirmation; §3.3 cites §1.1 directly; §6.6.4 zero "for humans only" hits in normative prose. |
| 8 | Doc explicitly disclaims migration-tool source code / transport / wire / auth / RBAC / deployment? | **YES** | §0.2; §8 ten-item anti-checklist; §11.5 binding citations. |

---

## 2. Per-section scoring rubric

| § | Score | One-line rationale |
|---|---|---|
| §0 Frame + binding constraints | 5/5 | Owns/does-not-own boundaries (§0.1, §0.2); eight §0.3 binding constraints each cite a verifiable upstream §-ref; §0.4 vocabulary cross-walk absorbs the kickoff's "three-tier" shorthand without contradicting composition §2; §0.5 notation pins `ts_recorded_scns` as observation-time (not host-clock), the keystone for cross-resume determinism. |
| §1 Source inventory | 5/5 | Read-only audit of `~/.scns/memory/` + `~/.claude/CLAUDE.md`; every shape partitioned in/out of scope with §2.1-row or §8-anti-checklist citation; `vault.db` excluded with §0.3 #1 reasoning; `MEMORY.md`/`SOUL.md`/`USER.md` excluded as S4b-shape (regenerated post-cutover). |
| §2 Mapping rules + §2.3 identifier derivations | 4.5/5 | 9-row table exhaustive over §1.1 in-scope shapes; §2.2 authored-vs-derived line is faithful to composition §2.1 + §8.3 Candidate C; §2.3 idempotency-key and episode-id derivations are RFC 9562-conformant and visually parallel to api §1.4. Half-point off for two minor wording issues (N2, N3). |
| §3 Phase plan + resumability | 4.5/5 | 14-phase ordered table with three hard gates (A/B/C) + 11 soft gates / "no gate" justified; §3.2 manifest-as-source-of-truth + 24h-TTL idempotency replay + `audit(provenance.source_uri)` fallback; §3.3 CLAUDE.md split per `##` (10 KB cap honored at recall, not migration); §3.4 procedure-vs-narrative heuristic explicit (3-test conjunction; favors narrative on ambiguity); §3.5 explicit list of verbs migration does NOT call. Half-point off for two sequencing nits (N4, N5). |
| §4 Concurrency contract | 5/5 | §4.1 cold-start as recommended v1 path; §4.2 warm-tenant via api §1.3 `expected_version` CAS retry per gap-04 §3 candidate (a), with `single_writer_per_tenant=true` stop-gap (gap-04 §4) named; §4.3 recall-determinism preservation correctly grounded in api §1.4 input-determinism + composition §5 bi-temporal `recorded_at`/`valid_from` distinction; §4.4 tenant-scope refuses cross-tenant runs; §4.5 per-phase locking via `health()` polling (not direct lock acquisition). |
| §5 Failure modes & recovery | 5/5 | Per-phase rows mapped onto composition §7 (S5 append, S1 down, S2 locked, S3 stale, dream-daemon stuck, disk full); §5.1 escalation as first-class outcome (`422 classifier_escalate` → manifest `escalated`, run continues); `409 idempotency_conflict` correctly distinguished as halt-and-review (manifest bug, not transient); §5.2 explicit non-failures (heuristic outcomes, archive orphans, suppress-then-invalidate). |
| §6 Verification + §6.6 audits | 4.5/5 | §6.1 phase-gate S5 entries; §6.2 5% provenance round-trip with three checks (source_uri / episode_id / content_hash); §6.3 ~50-probe recall-determinism with operator-set drift tolerance (default 5%); §6.4 preference-cap honoring (`recall(k=0)`); §6.6 four audits all reproduce under fresh re-run. Half-point off for one sample-rate divergence note (N1). |
| §7 Stopping criteria | 5/5 | Per-tenant criteria (S5 phase-gate entries × 3, provenance round-trip P0-clean, recall-determinism within tolerance, preference-cap honored, operator-signed `migration_run_complete`); per-deliverable criteria (doc + HANDOFF §14 + audits in-doc + §10 residuals). |
| §8 Anti-checklist | 5/5 | Ten explicit denials — migration-tool source-code spec, `migrate_*` verb, SCNS shim, `vault.db` consumption, `MEMORY.md`/`SOUL.md`/`USER.md` copying, `capture_opt_in_trace` bypass, transport/wire/auth/RBAC/deployment, cross-deployment Lethe→Lethe, sync fact-extraction of authored synthesis, dream-daemon throughput guarantee. |
| §9 Traceability matrix | 5/5 | 23 decisions mapped to upstream §-refs; spot-checks survive (composition §1.1 / §2 / §8.3 Candidate C; api §1.2/§1.4/§1.5/§1.8/§3.1; gap-04/05/08/09/11/12; HANDOFF §10/§11.5/§12.5/§13). No TBD rows. |
| §10 Residual unknowns | 4.5/5 | Nine items, each surfaced not pre-resolved; daily-block source-id collision mitigation (snapshot_hash augmentation if observed) is the most consequential and is correctly bet-shaped; §3.4 heuristic accuracy floor (80% precision threshold) named; cross-deployment Lethe→Lethe and `vault.db` consumption deferred with paths sketched. Half-point off for one minor classification hedge (N6). |

**Decisions (HANDOFF §14.1) honored:**

| Decision | Resolution required | Verified at |
|---|---|---|
| #1 Five-store vocabulary throughout | Composition §2 | §0.4 cross-walk; used consistently §2–§4 |
| #2 Corpus-only migration (no `vault.db`) | §0.3 #1 boundary | §1.1 row 10; §8 anti-checklist; §10 residual |
| #3 SCNS S4b not copied; Lethe regenerates | composition §2 row S4b | §1.1 row 9; §3.1 phase 14; §8 anti-checklist |
| #4 CLAUDE.md splits per `##`; 10 KB at recall not migration | gap-09 §6; api §0.3 #3 | §3.3 |
| #5 Synthesis `lethe.extract: false` | composition §8.3 Candidate C | §2.1 col 6; §8 anti-checklist |
| #6 Idempotency-key with `"idem"` discriminant | api §1.2 + §1.4 | §2.3 lines 167–179 |
| #7 Episode-id with `"epi"` discriminant; `ts_recorded_scns` not host-clock | gap-05 §6 | §2.3 lines 181–193; §0.5 |
| #8 Cold-start recommended; warm via CAS | gap-04 §3 candidate (a), §4 stop-gap | §4.1, §4.2 |
| #9 `criticStatus=suppress` → `remember` then `forget(invalidate)` | gap-11 §3.1; gap-05 §3.4 | §2.1 row 9; §3.1 phase 8 |
| #10 Phase 11 S3 backfill non-blocking | composition §3.1 lexical fallback | §3.1 phase 11; §6.6.3 "no gate" justified |

---

## 3. Major findings

**None.** No P0 (anti-checklist violation) and no P1 (under-specified gate / missing cross-ref) findings.

The four highest-stakes items — three hard phase-gates hard-halting on failure (anti-checklist HANDOFF §14.4 item 7), no `migrate_*` verb on the api surface (item 1), no post-cutover SCNS read path (item 2), uuidv7 discriminant collision-prevention (item 5) — are each **structurally** enforced by the §3.1 / §0.3 / §2.3 / §6.6.1 surfaces and survived live re-run.

---

## 4. Nits (one-liners; doc-hygiene only)

- **N1** (`docs/07-migration-design.md:341` vs `:213`) — §6.2 samples 5% for the provenance round-trip (three checks: source_uri lookup + episode_id match + content_hash match); §3.1 Phase-gate B samples ≥1% (min 50) for the episode-id round-trip (one check). The two audits are different and the larger §6.2 sample is justifiable, but the rate divergence is unstated. Recommend a one-line note in §6.2 explaining why 5% > 1%.
- **N2** (`docs/07-migration-design.md:39` vs `:167–179`) — §0.3 #2 abbreviates the idempotency-key as `uuidv7(tenant_id, scns_observation_id)`, omitting `ts_recorded_scns` from the input tuple. §2.3 actually embeds `ts_recorded_scns` in the 48-bit timestamp prefix. Recommend "uuidv7(tenant_id, ts_recorded_scns, scns_observation_id) per §2.3" to match §0.3 #3's three-input wording for episode-id.
- **N3** (`docs/07-migration-design.md:214` and `:412` vs §2.3) — §3.1 phase 8 introduces a `"forget"` discriminant for the per-row `forget(invalidate)` idempotency-key, and §6.6.2 row 8 cites it, but §2.3 only formalizes `"idem"` and `"epi"`. Recommend §2.3 add a third derivation block ("for forget calls in Phase 8 / §2.1 row 8 + 9-tail, substitute discriminant `"forget"`; same RFC 9562 layout") to keep §2.3 closed over all three derivations.
- **N4** (`docs/07-migration-design.md:229`) — §3.2 says the cross-run-conflict check ("no `applied_episode_id` from a prior run conflicts with the §2.3 formula re-derived from current manifest inputs") runs "in Phase 1." On a fresh run no prior `applied_episode_id` exists (no-op); on a resume run the manifest exists from the prior run's Phase 3 (feasible). Wording should be "Phase 1 (resume runs only) re-derives §2.3 over the prior manifest's rows and halts on mismatch."
- **N5** (`docs/07-migration-design.md:207` vs `:208`) — Phase 1's S5 entry is `migration_run_started{run_id, tenant_id, snapshot_hash}` but `snapshot_hash` is recorded by Phase 2 ("snapshot_hash recorded in S5"). Either Phase 1 emits a placeholder and Phase 2 amends, or the field cannot be present at Phase 1 emit time. Recommend re-sequence: Phase 1 emits `migration_run_started{run_id, tenant_id}`; Phase 2 emits `migration_snapshot_recorded{run_id, snapshot_hash}`.
- **N6** (`docs/07-migration-design.md:86`) — §1.1 marks `weekly/<iso-week>.md` and `monthly/<yyyy-mm>.md` as "authored (per gap-09 §7)" but the row description hedges with "machine-or-human-authored summaries"; gap-09 §7 line 76 simply says "SCNS synthesis pages → narrative pages by default" without classifying authored-vs-derived. The conservative call (treat as authored, default `lethe.extract: false`) is reasonable, but the table's confident "authored" disagrees with the prose hedge. Recommend either drop the hedge or note that machine-summarized weekly pages are still treated as authored at the migration boundary because Lethe regenerates S4b from S1 post-cutover anyway.

---

## 5. Stopping-criteria check

Per HANDOFF §14.4 anti-checklist (P0 if violated):

| Anti-checklist item | Violated? | Evidence |
|---|---|---|
| Verb signature in `docs/07-migration-design.md` naming `migrate_*` or extending the api surface | **NO** | §0.2 ("There is no `migrate_*` verb"); §3.5 (verbs migration does NOT call); §8 anti-checklist item 2. |
| Post-cutover read path from runtime to `~/.scns/` or `vault.db` | **NO** | §0.3 #1 (binding constraint); §3.1 phase 13 (cutover is the cut-line); §6.6.1 audit assertion; §8 anti-checklist items 3 + 4. |
| Migration row that writes without `idempotency_key` or without `provenance.source_uri` | **NO** | §6.6.2 9/9 PASS; reproduced live (§7.2). |
| Idempotency-key or episode-id derivation using non-deterministic CSPRNG suffix | **NO** | §2.3 — both derivations from `sha256(tenant_id ‖ "idem" \| "epi" ‖ scns_observation_id)`, not CSPRNG. |
| Idempotency-key omits discriminant separator (`"idem"`) and would collide with episode-id | **NO** | §2.3 line 179 explicit collision argument; `"idem"` and `"epi"` byte-distinct in sha256 input stream. |
| Phase that lacks both an exit gate and a justified "no gate" notation | **NO** | §6.6.3 14/14 PASS; reproduced live (§7.3). |
| Pre-flight Phase-gate A or post-import Phase-gate C that is not a *hard* halt | **NO** | §3.1 phases 4 + 10 marked **hard gate** in §6.6.3; §3.1 prose "Phase-gate failures halt the run"; §5 halt rows confirm. |
| "S4b copy from SCNS" path | **NO** | §1.1 row 9 (out-of-scope); §3.1 phase 14 regenerates from S1; §8 anti-checklist item 5. |
| Migration call to `capture_opt_in_trace` | **NO** | §0.3 #5; §3.5; §8 anti-checklist item 6. |
| Migration call to `promote`, `peer_message`, or `emit_score_event` | **NO** | §3.5 explicit non-calls. |
| "For humans only" framing for markdown surfaces | **NO** | §6.6.4 zero hits in normative prose; reproduced live (§7.4). §0.3 #8 explicit affirmation. |
| Transport / wire / auth / RBAC / deployment-shape commitment | **NO** | §0.2; §8 anti-checklist item 7. |

Per HANDOFF §14.1 / §7 stopping criteria for WS7:

| Criterion | Met? |
|---|---|
| Source inventory complete (every shape under `~/.scns/memory/` + `~/.claude/CLAUDE.md` partitioned in/out of scope) | **YES** (§1.1) |
| Mapping rules: every in-scope shape → verb call with `kind`, idempotency-key, provenance.source_uri | **YES** (§2.1 9 rows; §2.3 identifier rules) |
| Phase plan: ordered, resumable, idempotent, with three hard phase-gates (A pre-flight, B episode-id round-trip, C post-import) | **YES** (§3.1 14 phases; §3.2 resumability) |
| Concurrency contract: cold-start (recommended) + warm-tenant via api §1.3 CAS | **YES** (§4) |
| Failure-mode table mapped onto composition §7 | **YES** (§5) |
| Verification contract: phase-gate outputs + provenance round-trip + recall-determinism probe + preference-cap honoring + audit transcripts | **YES** (§6) |
| Stopping criteria for one-tenant migration + WS7 deliverable | **YES** (§7) |
| Anti-checklist as closing section | **YES** (§8 ten-item denial list) |
| Traceability matrix | **YES** (§9 23 rows) |
| Residual unknowns enumerated for WS8 | **YES** (§10 nine items) |
| Four in-doc audits (SCNS-independence / idempotency-coverage / phase-gate / markdown-audience) | **YES** (§6.6.1–§6.6.4; live re-run reproduces) |

---

## 6. Ready-for-WS8 statement

**Ready for WS8 (deployment author): YES.**

- §3 names every operator action point WS8 builds the UX around: snapshot creation (Phase 2), capability checks (Phase 1), manifest inspection (Phase 3 + §3.2), phase-gate halts (Phases 4 / 7 / 10), drift-tolerance configuration (Phase 12), cutover trigger (Phase 13), S4b regeneration wait (Phase 14).
- §4.1 vs §4.2 gives WS8 the cold-start-vs-warm-tenant decision surface; §4.2 names `single_writer_per_tenant=true` (gap-04 §4 stop-gap) as the tenant-level alternative WS8 may set as default.
- §10 enumerates the instrumentation hooks WS8 must expose: idempotency-key TTL extension instrumentation; Phase 9 async-drain operator alarm (`time-since-last-successful-consolidation > N × gate_interval`); Phase 11 S3 backfill progress via `health()`; manifest UX (CLI / JSON / HTML).
- §3.1 Phase 1 capability check pins the WS6-deferred capability-to-role mapping as a WS8-owned input — migration is the first operational consumer of the rate-limit / capability surface api §0.2 + §1.6 deferred.
- §5.1 marks `escalate`-class rows as `escalated` and continues; the staged-for-review queue workflow is correctly punted to HANDOFF §12.6 (project-ops territory, not WS7).
- The migration-tool implementation pass (CLI, manifest format, snapshot mechanism, S3 backfill orchestration, phase-gate runners) is verb-call-shaped and can begin once WS8 freezes the operator UX surface.

**Ready for the migration-tool implementation pass: YES.** §1–§6 collectively are sufficient that an implementer can write the manifest schema, the per-row verb-call dispatch, the phase-gate runners, and the verification probes without re-reading the gap briefs. The two discriminant strings (`"idem"`, `"epi"`, plus the third `"forget"` referenced in §3.1 phase 8 — see Nit N3) are the only ID-derivation primitives needed.

---

## 7. Audit transcripts

### 7.1 SCNS-independence audit (re-run live)

```
$ grep -in scns docs/07-migration-design.md | wc -l
80
```

Bucketed against the five HANDOFF §14.4 step 11 allowed categories:

| Bucket | Count | Representative lines |
|---|---|---|
| (a) Source-corpus references (the migration target is, definitionally, the SCNS markdown corpus) | ~52 | 7, 9, 17, 31, 63, 67, 75, 82–92, 109, 110, 126, 132, 133, 135, 145, 149, 151, 153, 156, 158, 161, 163, 167, 174, 176, 181, 188, 190, 195, 208, 212, 219, 235, 239, 256, 279, 306, 307, 343, 347, 356, 366 |
| (b) `provenance.source_uri = scns:<shape>:<id>` literals (audit-trail format internal to Lethe's own provenance store post-import) | ~6 | 165, 228, 344, 393, 508 |
| (c) HANDOFF §10 / api §0.3 #1 boundary citations (binding-constraint disclaimers) | ~12 | 28, 38–41, 373, 376, 389, 393–395, 397, 442, 444 |
| (d) §8 anti-checklist denials (explicit non-dependency statements) | ~5 | 486, 487, 488, 535, 536 |
| (e) §6.6.1 audit transcript itself (the audit is allowed to discuss SCNS) | ~5 | 385, 387, 389, 393, 394, 397 |

**Result: PASS.** Zero hits introduce a runtime read path to `~/.scns/`. Zero hits extend a verb signature in the api surface. Zero hits name SCNS as a *post-cutover* runtime dependency. The §3.1 phase 13 cutover is the cut-line; after cutover the runtime has no SCNS read path. The in-doc §6.6.1 claim of 80 hits all-allowed reproduces.

### 7.2 Idempotency-key / provenance coverage audit (re-run live)

Walk every row of §2.1 and confirm each maps to a verb that takes `idempotency_key` *and* every imported row gets a `provenance.source_uri` of `scns:<shape>:<id>` form:

| §2.1 row | SCNS source | Verb | `idempotency_key` derivation (§2.3) | `provenance.source_uri` form |
|---|---|---|---|---|
| 1 | `~/.claude/CLAUDE.md` per-section | `remember` | `claude-md:<slug-of-h2>` | `scns:claude-md:<slug>` |
| 2 | `lessons/<slug>.md` (prohibition) | `remember` | frontmatter `id` or `lessons/<slug>` | `scns:lessons:<id>` |
| 3 | `lessons/<slug>.md` (procedure) | `remember` | same | `scns:lessons:<id>` |
| 4 | `lessons/<slug>.md` / `weekly/*` / `monthly/*` (narrative) | `remember` | frontmatter `id` / `weekly/<iso-week>` / `monthly/<yyyy-mm>` | `scns:{lessons\|weekly\|monthly}:<id>` |
| 5 | `negative/<uuid>.md` | `remember` | frontmatter uuid | `scns:negative:<uuid>` |
| 6 | `sessions/<date>/<hash>.md` | `remember` | `sessions/<date>/<hash>` | `scns:sessions:<date>/<hash>` |
| 7 | `daily/<date>.md` per `## HH:MM:SS` block | `remember` | `daily/<date>#<HH:MM:SS>#<seq>` | `scns:daily:<date>#<HH:MM:SS>#<seq>` |
| 8 | `archive/*.md`, `.legacy-lessons/*` | `forget(invalidate)` | second uuidv7 with `"forget"` discriminant (§3.1 phase 8) | inherits originating shape (§2.3 row 7) |
| 9 | `negative/<uuid>.md` with `criticStatus=suppress` | `remember` then `forget(invalidate)` | both keys derived per §2.3 + §3.1 phase 8 | `scns:negative:<uuid>` |

**Coverage: 9/9 mapping-row write paths PASS.** Every imported row carries both `idempotency_key` (mandatory per api §1.2) and `provenance.source_uri = scns:<shape>:<id>` (per gap-05 §3 + api §1.5). The api §1.2 contract (missing key → `400 missing_idempotency_key`) is enforced globally; the migration tool cannot bypass it.

The only nit: the `"forget"` discriminant referenced in §3.1 phase 8 + §6.6.2 row 8 is not formally specified in §2.3 (which closes over `"idem"` and `"epi"` only). See Nit N3.

### 7.3 Phase-gate audit (re-run live)

Walk every phase in §3.1 and verify either an exit gate or a justified "no gate" notation; verify the three hard gates are present and hard-halt on failure:

| Phase | Exit gate | Hard halt? | Source for hard-halt |
|---|---|---|---|
| 1 Pre-flight | `health()` nominal + capability check | n/a (soft gate; abort run on fail) | §3.1 row + §5 row |
| 2 Snapshot | `snapshot_hash` recorded in S5 | n/a | §3.1 row |
| 3 Inventory | every source maps to ≥1 manifest row or `out_of_scope` | n/a | §3.1 row |
| **4 Phase-gate A** | `lethe-audit lint --integrity` converges (gap-08 §3.5) | **YES** | §3.1 prose ("Phase-gate failures halt the run"); §5 row "do not proceed; this is a tenant-state problem"; §6.6.3 marks **hard gate** |
| 5 S4a import | every authored row done/escalated | n/a | §3.1 row |
| 6 S1 import | every episodic row done/escalated, ordered deterministically | n/a | §3.1 row |
| **7 Phase-gate B** | sample episode-id round-trip 0 mismatches (gap-05 §6) | **YES** | §5 row "halt; investigate non-determinism source"; §6.6.3 marks **hard gate** |
| 8 Archive / invalidation | every archive row done/orphan_logged | n/a | §3.1 row; §5 row "log `migration_orphan_archive` to S5; **not** a halt" |
| 9 Async drain | `pending_extractions=0` + `last_consolidate_at > phase_8_done_at` | n/a | §3.1 row + §5 row "do not proceed to Phase-gate C" |
| **10 Phase-gate C** | integrity + provenance + forget-proof lints all pass (gap-05 §3.5; gap-08 §3.5) | **YES** | §5 row "halt; backfill provenance ... do not cut over"; §6.6.3 marks **hard gate** |
| 11 S3 backfill | non-blocking; operator chooses wait or defer | "no gate" justified | composition §3.1 lexical fallback survives S3 outage |
| 12 Recall determinism probe | drift within operator-set tolerance (default ≤5%) | n/a (soft; investigation triggered, not auto-halt) | §5 row |
| 13 Cutover | operator action | "no gate" justified | out of WS7 mechanical scope; named for completeness |
| 14 S4b regeneration | `MEMORY.md` exists with hash differing from snapshot | n/a | §3.1 row |

**Coverage: 14/14 phases gated or "no gate" justified. 3/3 hard phase-gates (A, B, C) present and hard-halt-confirmed.** §3.1 prose ("Phase-gate failures halt the run; resumes pick up from the failed phase") is the umbrella halt rule; §5 per-row recovery columns confirm hard-halt at each of the three gates with no auto-skip path.

### 7.4 Markdown-audience audit (re-run live)

```
$ grep -niE "for humans only|humans not LLMs|not for LLMs|LLMs can'?t|human-only|for humans, not" docs/07-migration-design.md
```

6 hits total, all classified:

| Line | Content (excerpt) | Classification |
|---|---|---|
| 45 | §0.3 #8: "the migration plan must not regress to 'for humans only' framing" | **Binding-constraint statement (negation; affirms dual-audience).** |
| 376 | §6.5 anti-checklist: "No language in this doc treats markdown as 'for humans only'" | **Anti-checklist denial.** |
| 442 | §6.6.4 audit claim: "no language in this doc treats markdown as 'for humans only'" | **Audit claim.** |
| 444 | §6.6.4 audit instruction: pattern list "for humans, human-only, ... not for LLMs" | **Audit pattern list.** |
| 450 | §6.6.4 result: "never 'human-only'" | **Audit result line.** |
| 451 | §6.6.4 result: "without 'for humans only' framing" | **Audit result line.** |

Manual scan of §3.3 (CLAUDE.md split): line 236 says "the human-editable surface (composition §1.1) reads naturally" — explicitly cites the composition §1.1 dual-audience binding, **not** a regression.
Manual scan of §2.1 (S4a synthesis pages): row 1 col 6 references §3.3; row 4 cites composition §8.3 Candidate C. No "humans only" framing.
Manual scan of §6.4 (preference-cap verification): no audience claim made. Neutral.

**Result: PASS.** Zero "for humans only" framing in normative prose. All 6 hits are inside §0.3 #8 (binding-constraint affirming dual-audience), §6.5 (anti-checklist denial), or §6.6.4 (audit transcript quoting the prohibited patterns to define the audit). The HANDOFF §13 cascade survives intact at the WS7 boundary.

### 7.5 uuidv7 layout parity audit (WS6-N6 carryforward validation)

Side-by-side comparison of api §1.4 (line 109) and `07-migration-design.md` §2.3 (lines 167–193):

| Field | api §1.4 (`recall_id`) | WS7 §2.3 (idempotency-key) | WS7 §2.3 (episode-id) |
|---|---|---|---|
| Total bits | 128 | 128 | 128 |
| 48-bit ts prefix | `ts_recorded` (request-arrival ms) | `ts_recorded_scns` (observation ms) | `ts_recorded_scns` (observation ms) |
| 4-bit version (RFC 9562) | `0b0111` | `0b0111` | `0b0111` |
| 12-bit `rand_a` | leading 12 bits of `sha256(tenant_id ‖ query_hash)` | leading 12 bits of `sha256(tenant_id ‖ "idem" ‖ scns_observation_id)` | leading 12 bits of `sha256(tenant_id ‖ "epi" ‖ scns_observation_id)` |
| 2-bit variant (RFC 9562) | `0b10` | `0b10` | `0b10` |
| 62-bit `rand_b` | next 62 bits of same sha256 | next 62 bits of same sha256 | next 62 bits of same sha256 |
| Deterministic bits total | 74 | 74 (12 + 62) | 74 (12 + 62) |
| Bit-position math | 48 + 4 + 12 + 2 + 62 = 128 | 48 + 4 + 12 + 2 + 62 = 128 | 48 + 4 + 12 + 2 + 62 = 128 |

**Layout parity: PASS.** All three derivations use the identical RFC 9562 bit layout. WS7 §2.3 is more explicit than api §1.4 about the bit boundaries (api §1.4 collapses `rand_a ‖ rand_b` into a single "74-bit deterministic suffix"), but the resulting byte layout is identical. The WS6-N6 fix (the api §1.4 byte-layout pin that made the spec engineer-portable) carries cleanly into WS7 §2.3.

**Discriminant collision-prevention: PASS.** The two WS7 derivations (`idempotency_key`, `episode_id`) consume identical structural inputs — `tenant_id` and `scns_observation_id`. Without a separator they would collide-by-construction (same sha256 input → same hash output → same `rand_a ‖ rand_b` → same uuidv7 minus the 6 fixed bits). The discriminant strings `"idem"` and `"epi"` are inserted into the sha256 byte stream **between** `tenant_id` and `scns_observation_id`, so the two derivations consume distinct byte streams (`tenant_id ‖ "idem" ‖ scns_observation_id` vs `tenant_id ‖ "epi" ‖ scns_observation_id`) and produce distinct hash outputs. The discriminants are 4 ASCII bytes each (32 bits per discriminant), making the sha256 inputs differ by ≥32 bits regardless of the surrounding values — sha256's avalanche property ensures the outputs are uncorrelated.

The api §1.4 `recall_id` derivation has no discriminant because its input tuple `(tenant_id, query_hash)` is structurally distinct from migration's `(tenant_id, scns_observation_id)` — `query_hash` is `sha256(canonical_json({query, intent, k, scope}))[:16]`, so a `recall_id` would have to hash-collide a `scns_observation_id` to a `query_hash` for a cross-derivation collision, which is sha256-second-preimage hard.

The semantic difference between the two timestamp inputs (api §1.4 uses `ts_recorded` request-time; WS7 §2.3 uses `ts_recorded_scns` observation-time) is documented in §2.3 prose ("a same-observation retry across days still matches the original key") and §0.5 notation ("**not** the migration-host wall-clock"). Using request-time would break cross-day resume because the migration tool's wall-clock advances; using observation-time is the keystone that makes the migration replay-stable across resumes (the property Phase-gate B at §3.1 phase 7 actually verifies).

**Result: PASS.** The WS6-N6 byte-layout pin carries cleanly into WS7 §2.3; the `"idem"` / `"epi"` discriminant strategy is sound; the timestamp-source semantic difference is documented and intentional. The kickoff's "did the WS6-N6 fix get fumbled?" check resolves: NO, it survived the WS7 carryforward intact.

---

## 8. Closing

WS7 closes the migration loop cleanly. The doc that I expected to be the easiest to over-spec — a 14-phase plan with three hard gates, a 9-row mapping table, and a CAS contract for warm-tenant runs — is the most disciplined: §3.1 separates ordered phases from gated phases from "no gate"-justified phases without mixing them; §2.3 makes the three uuidv7 derivations (recall_id, idempotency-key, episode-id) structurally parallel so a future engineer can read api §1.4 and §2.3 side-by-side and see the WS6-N6 carryforward at a glance; §6.6's four in-doc audit transcripts are not a substitute for fresh re-runs (this QA pass re-ran all four plus a fifth uuidv7-parity audit and reproduced the §6.6 results) but they are a useful bootstrapping aid for any future audit pass.

The decision to make `criticStatus=suppress` migrate as `remember` then immediate `forget(invalidate)` (decision #9; §2.1 row 9) is the right call: it preserves the gap-05 §3.4 audit-trail invariant (the prohibition existed and was retired) rather than silently dropping the row, which would leave a hole in the post-cutover provenance graph.

The decision to not consume `vault.db` (decision #2; §1.1 row 10; §10) is also the right call. The path to bringing SCNS broker metadata into Lethe — write a one-time exporter that emits SCNS-corpus-shaped markdown for migration to consume (§10) — keeps the §0.3 #1 boundary intact and is correctly deferred to a future operator-policy decision.

The six nits are doc-hygiene; none warrant blocking WS8. They can be cleaned up alongside the §10 follow-throughs (daily-block source-id collision instrumentation, §3.4 heuristic accuracy floor instrumentation, idempotency-key TTL extension, Phase 11 S3 backfill progress UX — all WS8 / operator-tooling pass).

**Verdict: APPROVE-WITH-NITS. Proceed to WS8.**
