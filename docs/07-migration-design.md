# 07 — Migration Design (WS7)

**Status:** v1 design, awaiting WS7-QA fresh-eyes pass.
**Substrate:** composition §1.1 (markdown dual-audience), §2 (ownership matrix), §5 (consistency model), §6 (provenance propagation), §7 (failure-mode table); api §0.3 (binding constraints), §1.2 (idempotency-key), §1.3 (version-CAS), §1.4 (`recall_id` derivation), §1.5 (provenance envelope), §3.1 (`remember`), §3.3 (`forget`), §4.1 (`capture_opt_in_trace`); scoring §4.1 (bi-temporal pre-filter), §8.3 (replay invariant); gap-04 (multi-agent concurrency), gap-05 (provenance enforcement), gap-08 (crash safety), gap-09 (non-factual memory), gap-11 (forgetting modes), gap-12 (intent classifier); HANDOFF §10 (Lethe stands on its own), §11.5 (WS6 binding constraints), §12.5 (WS7 reading order), §13 (markdown audience correction).
**Cross-refs:** Gates WS7-QA (this is the input contract); gates WS8 (deployment author sees the migration's operator-knob surface). WS6 (api) is the verb-side target of every migration call; WS7 introduces no new verbs.

This document specifies **how a SCNS markdown corpus is ingested into a freshly-stood-up Lethe tenant by calling the existing api §2–§4 verb surface, in ordered phases with hard phase-gates, idempotent on partial failure, preserving every binding invariant from upstream WS.** It does *not* specify migration-tool source code, transport, deployment shape, or any ongoing dependency on SCNS.

The headline question every WS7 artifact answers: **given a SCNS corpus on disk and a fresh Lethe tenant, what are the ordered phases, what are the gates, what survives a crash mid-phase, and how does an operator confirm the result is correct?**

---

## §0 Frame

### §0.1 What WS7 owns

- The **source inventory** — which SCNS file shapes exist on disk, and which are in / out of scope.
- The **mapping rules** — per source shape, which Lethe verb is called, with which `kind`, and how `provenance.source_uri` and `idempotency_key` are derived.
- The **phase plan** — ordered, resumable, idempotent phases with three hard phase-gates (integrity-lint pre-flight, episode-id round-trip, integrity-lint post-import).
- The **concurrency contract** — how migration tooling interacts with live ingest if the destination tenant is warm.
- The **failure-recovery story** — per phase, mapped to composition §7's degraded-mode taxonomy.
- The **verification contract** — what an operator runs to confirm the migration is correct (phase-gate outputs, provenance round-trip, recall-determinism probe, preference-cap honoring, in-doc audit transcripts).
- The **stopping criteria** — what "done" means for a tenant migration; what is deferred to WS8.

### §0.2 What WS7 does NOT own

- **Migration-tool source code.** This doc is verb-call-shaped; the implementation is a follow-up pass.
- **A migration-specific verb surface.** Migration calls the existing api §2–§4 verbs and stops. There is no `migrate_*` verb; per HANDOFF §10 + §11.5 + api §0.3 #1, no SCNS-shaped surface is introduced.
- **Transport / wire / auth / RBAC / deployment shape.** WS8.
- **Verb internals** (classifier weights, scoring math, retention engine internals). WS5 / gap-01 / gap-12.
- **The post-cutover runtime.** After cutover the runtime has no read path to SCNS; ongoing operation is composition §3 + api §2.
- **Cross-deployment migration** (Lethe → another Lethe, e.g., for tenant export). Surfaced in §10.

### §0.3 Binding constraints

These are non-negotiable. Every phase, mapping, and gate below is verifiable against them.

1. **No SCNS shim in the runtime.** Migration is a one-way ingest that calls api verbs, then stops. After cutover, no Lethe code reads `~/.scns/` or imports from the SCNS repo. (HANDOFF §10; api §0.3 #1, §8 anti-checklist last bullet.)
2. **Deterministic, restartable idempotency.** Every migration write carries `idempotency_key = uuidv7(tenant_id, ts_recorded_scns, scns_observation_id)` per §2.3 so partial runs replay cleanly within the api §1.2 24 h TTL. (HANDOFF §12.5 binding bullets 2 + 4.)
3. **Episode-id stability.** The Lethe `episode_id` minted for a given SCNS observation is invariant across resumes: `episode_id = uuidv7(tenant_id, ts_recorded_scns, scns_observation_id_hash)` with the RFC 9562 layout pinned in api §1.4 (see §0.5). (gap-05 §6 *Cross-runtime provenance* bet, scoped within-tenant.)
4. **SCNS-side identifier preserved as `provenance.source_uri`.** Audit trails survive the cutover because the SCNS-side identifier rides on every Lethe episode. (HANDOFF §12.5 step 4; gap-05 §3.)
5. **`capture_opt_in_trace` is not bypassed.** Per-tenant opt-in is the only path for trace data into the eval candidate pool; migration does not side-load eval cases. (HANDOFF §12.5; api §4.1.)
6. **`lethe-audit lint --integrity` is a hard phase-gate** — pre-flight (Phase-gate A) and post-import (Phase-gate C). (gap-08 §3.5.)
7. **Recall-determinism is preserved for in-flight `recall_id`s.** Migration only adds episodes/facts; it does not replay or re-derive `recall_id`s, so the api §1.4 derivation (deterministic on request inputs) is unaffected. (scoring §8.3 replay invariant.)
8. **Markdown is dual-audience.** S4a outputs of this migration (preference / procedure / narrative pages) are read by both humans and LLM agents (via `recall_synthesis`); the migration plan must not regress to "for humans only" framing. (composition §1.1; HANDOFF §13.)

### §0.4 Vocabulary cross-walk — three-tier shorthand vs. composition's five stores

The kickoff prompt referred to "Lethe's three-tier store (S1 episodes, S2 facts, S3 vectors)." Composition §2 names **five** stores; this doc uses the five-store vocabulary throughout to avoid drift. The cross-walk:

| Kickoff shorthand | Composition §2 store(s) | Notes |
|---|---|---|
| "S1 episodes" | **S1** (Graphiti bi-temporal index) episode payloads | Episodes are S1 rows; the prompt's "S1" matches composition's S1 in name and content. |
| "S2 facts" | **S1** fact-edges (canonical) + **S2** SQLite metadata (ledger / flags / scheduler) | Facts are *also* in S1; composition's S2 is metadata about facts, not the facts themselves. The migration writes episodes; fact-edges are derived asynchronously by the dream-daemon. |
| "S3 vectors" | **S3** (vector index) | Match. Migration backfills S3 at §3.1 phase 11. |
| (not in shorthand) | **S4a** (markdown synthesis, canonical) + **S4b** (markdown projections, derived) | Authored synthesis lands in S4a; SCNS's `MEMORY.md`-shape projections (S4b) are excluded from migration and regenerated post-cutover. |
| (not in shorthand) | **S5** (consolidation log, append-only) | Migration writes one S5 entry per phase boundary and per `forget` call (gap-05 §3.4). |

When this doc says "S1 / S2 / S3 / S4a / S4b / S5" it always means the composition §2 stores.

### §0.5 Notation

- **Source** = the SCNS markdown corpus (a snapshot of `~/.scns/memory/` and `~/.claude/CLAUDE.md`).
- **Sink** = the destination Lethe tenant, via the api §2–§4 verb surface.
- **Run** = one invocation of the migration tool against one snapshot for one tenant.
- **Manifest** = the per-run table of `(source_path, scns_observation_id, target_kind, target_verb, idempotency_key, episode_id_hint, status, applied_episode_id?)` rows. The manifest is the run's source of truth (§3.2).
- **`scns_observation_id`** = the SCNS-side identifier of one observation: frontmatter `id` if present; else a stable hash over `(file_path, optional_block_coordinates)`. Section §2.3 names the per-shape rule.
- **`ts_recorded_scns`** = the SCNS-side observation timestamp (frontmatter `createdAt` if present; else file `mtime`); **not** the migration-host wall-clock. This is what makes episode-id derivation deterministic across resumes.
- Schemas are abstract; field types follow api §0.4 conventions.

---

## §1 Source inventory

Read-only audit of `~/.scns/memory/` + `~/.claude/CLAUDE.md` produced the shapes below. The inventory is for **shape** (which mappings apply); content is not quoted in this doc.

### §1.1 Top-level shapes

| Path glob | Shape | Authored vs derived (§2.2) | In/out of WS7 scope |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | Global preference document; multi-section markdown | authored | **in** (§2.1 row 1) |
| `~/.scns/memory/lessons/<slug>.md` | Authored synthesis page with YAML frontmatter (`id`, `scope`, `project`, `tags`, `createdAt`) | authored | **in** (§2.1 rows 2–4) |
| `~/.scns/memory/negative/<uuid>.md` | Negative-rule page with frontmatter (`id`, `category`, `confidence`, `criticStatus`, `appliedTo`) | authored | **in** (§2.1 row 5) |
| `~/.scns/memory/sessions/<date>/<hash>.md` | Session digest (machine-summarized session, stable per `<hash>`) | derived | **in** (§2.1 row 6) |
| `~/.scns/memory/daily/<date>.md` | Append-only journal of timestamped tool-use blocks (`## HH:MM:SS`) | derived | **in** (§2.1 row 7) |
| `~/.scns/memory/weekly/<iso-week>.md`, `monthly/<yyyy-mm>.md` | Synthesis pages (summaries) | authored (per gap-09 §7) | **in** (§2.1 row 4) |
| `~/.scns/memory/archive/*.md` | SCNS's invalidation surface (entries moved out of active memory) | n/a | **in** as `forget(invalidate)` cascade (§3.1 phase 8) |
| `~/.scns/memory/.legacy-lessons/*` | Pre-current-schema lessons | n/a | **in** as `forget(invalidate)` cascade — same path as `archive/` |
| `~/.scns/memory/MEMORY.md`, `SOUL.md`, `USER.md` | SCNS's `MEMORY.md`-shape projections | derived (S4b-shape) | **out** (§8 anti-checklist; regenerated post-cutover) |
| `~/.scns/memory/vault.db` (+ `-shm`, `-wal`) | SCNS broker SQLite | n/a | **out** — consuming `vault.db` would require either a SCNS schema dependency (§0.3 #1 violation) or a side-channel translator that is effectively a shim. Surfaced in §10. |
| `~/.scns/memory/.taxonomy.yml`, `regression-test*`, `lessons.db` | SCNS internal config / test artifacts | n/a | **out** |
| `~/.scns/{config,secrets,state,browser-runs,logs,automations,suggestions}` | SCNS runtime / ops surfaces | n/a | **out** (not memory corpus) |

Note on weekly/monthly classification: machine-summarized weekly/monthly pages are treated as **authored** at the migration boundary because Lethe regenerates its own S4b from S1 post-cutover (composition §2 row S4b; §3.1 phase 14) — so importing them as authored S4a does not create a derived/canonical conflict.

### §1.2 Volume sketch

The migration tool is expected to handle corpora on the order of:

- 1 global preference file (~30 KB).
- 10²–10³ authored synthesis pages (lessons / weekly / monthly / negative).
- 10²–10⁴ session digests + daily journal blocks.
- 10⁰–10² archive entries.

Volume is sized at run-time from the manifest; the phase plan is not volume-sensitive within these bounds. Larger corpora are a §10 residual unknown.

### §1.3 Frontmatter conventions

The migration consumes (when present) these YAML frontmatter fields:

- `id` → seeds `scns_observation_id` (else fallback per §2.3).
- `createdAt` → seeds `ts_recorded_scns` (else file `mtime`).
- `category`, `tags` → input to `kind` classification (§3.4).
- `confidence`, `source` (e.g., `heuristic`) → captured into `provenance.source_uri` query-string for audit, but not used to route.
- `criticStatus` (e.g., `suppress`) → routes to a `forget(invalidate)`-after-import (§3.1 phase 8).
- `appliedTo` → captured into `provenance.source_uri` query-string for audit; not used to route.

Frontmatter is best-effort; pages without frontmatter fall through to the §2.3 fallback rules.

---

## §2 Mapping rules — source shape → Lethe sink

### §2.1 Mapping table

Every row is a `remember(content, kind, idempotency_key, provenance)` call against the api §3.1 surface, except where noted (`forget(invalidate)` for the archive/suppress paths).

| # | SCNS source | Verb | `kind` | Authored / derived | `lethe.extract` flag | Notes |
|---|---|---|---|---|---|---|
| 1 | `~/.claude/CLAUDE.md` (global) | `remember` (preference path) | `preference` | authored | `false` | Split per top-level `##` section per §3.3; one preference page per section. The 10 KB always-load cap (gap-09 §6; api §0.3 #3) is enforced at recall, not at migration. |
| 2 | `lessons/<slug>.md` with `category=behavior-complaint` or body matching prohibition shape | `remember` | `prohibition` | authored | `false` | gap-09 §3 — prohibitions are a preference sub-class. |
| 3 | `lessons/<slug>.md` matching the §3.4 procedure heuristic | `remember` | `procedure` | authored | `false` | gap-09 §3. |
| 4 | `lessons/<slug>.md` (default), `weekly/*.md`, `monthly/*.md` | `remember` | `narrative` | authored | `false` | gap-09 §7 — synthesis pages → narrative pages. composition §8.3 Candidate C: synthesis is **not** graph-extracted by default. |
| 5 | `negative/<uuid>.md` | `remember` | `prohibition` | authored | `false` | Frontmatter `id=<uuid>` becomes the `scns_observation_id`. |
| 6 | `sessions/<date>/<hash>.md` | `remember` | `state_fact` (or classifier-derived) | derived | `true` (default for episodes) | Session digest is a SCNS-derived summary; in Lethe it is an episode. The dream-daemon's gap-06 extraction pipeline produces fact-edges asynchronously (api §3.1 phases 1–6). |
| 7 | `daily/<date>.md`, one per `## HH:MM:SS` block | `remember` | `reference` | derived | `true` | One Lethe episode per timestamped block. Idempotency-key derivation handles per-block coordinates (§2.3). |
| 8 | `archive/*.md`, `.legacy-lessons/*` | `forget(invalidate, ...)` after a corresponding `remember` | n/a | n/a | n/a | Archive = SCNS's invalidation surface; in Lethe this is bi-temporal `valid_to`. Skip silently if no live counterpart was imported (logged to S5; not a halt). |
| 9 | `negative/<uuid>.md` with `criticStatus=suppress` | `remember` then immediate `forget(invalidate)` | `prohibition` | authored | `false` | Preserves the audit trail (the prohibition existed and was retired) rather than silently dropping. gap-11 §3.1. |

`escalate`-class returns from the api §3.1 classifier are not failures — the row's manifest entry is marked `escalated`, the operator reviews per api §3.1, and migration continues (§5.1).

### §2.2 Authored-fact vs derived-fact — the dividing line

The split mirrors composition §2.1 + §8.3 Candidate C exactly:

- **Authored** = a human typed the prose. Lands as **S4a synthesis page** with `kind ∈ {preference, prohibition, procedure, narrative}`. Lethe does **not** extract S1 fact-edges from these by default; the page is readable by agents via `recall_synthesis` (api §2.2). Frontmatter `lethe.extract: true` opts a single page into graph-extraction; the migration leaves this `false` for every authored row.
- **Derived** = SCNS's session-hook machinery wrote it. Lands as **S1 episode** via `remember`; the dream-daemon extracts S1 fact-edges asynchronously per api §3.1 phases 1–6.

The dividing line is *who wrote it*, not what shape the prose looks like. A prose-shaped session digest is still derived (the session-hook wrote it); a sentence-fragment in a lesson page is still authored (a human wrote the lesson page around it).

### §2.3 Identifier rules — `scns_observation_id`, `ts_recorded_scns`, idempotency-key, episode-id

**Per-shape `scns_observation_id` derivation:**

| Shape | `scns_observation_id` |
|---|---|
| `~/.claude/CLAUDE.md` per-section page | `claude-md:<slug-of-h2-heading>` |
| `lessons/<slug>.md` | frontmatter `id` if present; else `lessons/<slug>` |
| `negative/<uuid>.md` | frontmatter `id` (the `<uuid>`) |
| `sessions/<date>/<hash>.md` | `sessions/<date>/<hash>` (the `<hash>` is already content-stable per SCNS) |
| `daily/<date>.md` per `## HH:MM:SS` block | `daily/<date>#<HH:MM:SS>#<sequence>` where `<sequence>` is the 0-based ordinal of repeated identical timestamps in the file (collision-safe; see §10) |
| `weekly/<iso-week>.md`, `monthly/<yyyy-mm>.md` | `weekly/<iso-week>` / `monthly/<yyyy-mm>` |
| `archive/*.md`, `.legacy-lessons/*` | inherits the originating shape's `scns_observation_id` (the archive entry references it) |

**`ts_recorded_scns`:** frontmatter `createdAt` if present (RFC 3339); else file `mtime` truncated to millisecond resolution. For per-block daily entries, the block's `## HH:MM:SS` plus the file's date form the timestamp.

**`provenance.source_uri`** (api §1.5; gap-05 §3): `scns:<shape>:<scns_observation_id>` (e.g., `scns:lessons:cosmere-rpg-character-sheet-positions`, `scns:daily:2026-04-08#00:01:00#0`). Optional query-string carries audit-only frontmatter (`?category=...&confidence=...&criticStatus=...`).

**Idempotency-key** (per §0.3 #2; HANDOFF §12.5 binding) — uuidv7-shaped, deterministic on the SCNS-side identifier; mirrors api §1.4's RFC 9562 layout so the two derivations are obviously parallel:

```
idempotency_key =
  uuidv7-formatted (RFC 9562):
    bits   0..47   (48-bit ms timestamp prefix) = ts_recorded_scns in unix-ms
    bits  48..51   (4-bit version)              = 0b0111
    bits  52..63   (12-bit rand_a tail)         = leading 12 bits of sha256(tenant_id ‖ "idem" ‖ scns_observation_id)
    bits  64..65   (2-bit variant)              = 0b10
    bits  66..127  (62-bit rand_b)              = next 62 bits of sha256(tenant_id ‖ "idem" ‖ scns_observation_id)
```

The 74 deterministic bits (`rand_a` ‖ `rand_b`, less the 4 reserved bits, totaling 12 + 62 = 74 bits per RFC 9562) are drawn from the leading 74 bits of `sha256(tenant_id ‖ "idem" ‖ scns_observation_id)`. The `"idem"` discriminant separates this derivation from the episode-id derivation below over the same source bytes; without it a collision-by-construction would tie the two ids together. The embedded ms timestamp is `ts_recorded_scns` so a same-observation retry across days still matches the original key (TTL behavior at §3.2).

**Episode-id** (per §0.3 #3; gap-05 §6) — uuidv7-shaped, deterministic on `(tenant_id, ts_recorded_scns, scns_observation_id_hash)`; mirrors api §1.4's wording so the two derivations look obviously parallel:

```
episode_id =
  uuidv7-formatted (RFC 9562):
    bits   0..47   (48-bit ms timestamp prefix) = ts_recorded_scns in unix-ms
    bits  48..51   (4-bit version)              = 0b0111
    bits  52..63   (12-bit rand_a tail)         = leading 12 bits of sha256(tenant_id ‖ "epi" ‖ scns_observation_id)
    bits  64..65   (2-bit variant)              = 0b10
    bits  66..127  (62-bit rand_b)              = next 62 bits of sha256(tenant_id ‖ "epi" ‖ scns_observation_id)
```

Same RFC 9562 layout as api §1.4's `recall_id` (48 + 4 + 12 + 2 + 62 = 128 bits) and as the idempotency-key above; the only differences are the discriminant string (`"epi"` vs `"idem"`) and the timestamp source (SCNS-side observation time, not request-arrival). The 74 deterministic bits make the value RFC-conformant *and* fully reproducible from manifest inputs, which is what makes Phase-gate B (§3.1 step 7) a useful equality check.

**Forget-key** (per §3.1 phase 8; §2.1 row 8 + 9-tail) — for `forget(invalidate)` calls in the archive / invalidation phase, the per-row idempotency-key is a *second* uuidv7 derived over the originating `scns_observation_id` with discriminant `"forget"`; same RFC 9562 layout as above:

```
forget_key =
  uuidv7-formatted (RFC 9562):
    bits   0..47   (48-bit ms timestamp prefix) = ts_recorded_scns in unix-ms
    bits  48..51   (4-bit version)              = 0b0111
    bits  52..63   (12-bit rand_a tail)         = leading 12 bits of sha256(tenant_id ‖ "forget" ‖ scns_observation_id)
    bits  64..65   (2-bit variant)              = 0b10
    bits  66..127  (62-bit rand_b)              = next 62 bits of sha256(tenant_id ‖ "forget" ‖ scns_observation_id)
```

The `"forget"` discriminant separates the invalidation-call key from the original `remember`-call idempotency-key (`"idem"`) and from the episode-id (`"epi"`) over the same source bytes, so all three derivations are closed and collision-disjoint by construction.

**Rollback-key** (per deployment §7.5; `lethe-migrate rollback`) — for `forget(invalidate)` calls in the rollback subcommand (which invalidates a manifest's `done`-state rows after a pre-cutover rollback decision), the per-row idempotency-key is a *fourth* uuidv7 derived over the originating `scns_observation_id` with discriminant `"rollback"`; same RFC 9562 layout as above:

```
rollback_key =
  uuidv7-formatted (RFC 9562):
    bits   0..47   (48-bit ms timestamp prefix) = ts_recorded_scns in unix-ms
    bits  48..51   (4-bit version)              = 0b0111
    bits  52..63   (12-bit rand_a tail)         = leading 12 bits of sha256(tenant_id ‖ "rollback" ‖ scns_observation_id)
    bits  64..65   (2-bit variant)              = 0b10
    bits  66..127  (62-bit rand_b)              = next 62 bits of sha256(tenant_id ‖ "rollback" ‖ scns_observation_id)
```

The `"rollback"` discriminant separates the rollback-time invalidation key from the migration-time `"forget"` invalidation key, the original `remember`-call idempotency-key (`"idem"`), and the episode-id (`"epi"`) over the same source bytes, so all four derivations are closed and collision-disjoint by construction. The ts source is `ts_recorded_scns` (not rollback-time `now()`) so the key is fully reproducible from manifest inputs alone — the rollback subcommand reads the manifest, which carries `ts_recorded_scns` per row.

`agent_id` (api §1.5): the SCNS session-hook actor where the source carries one (sessions / daily blocks); else the operator running the migration. `derived_from` is unused — that field is the gap-10 §3.3 peer-message slot and migration is not a peer-message context.

---

## §3 Phase plan

Ordered, resumable, idempotent. Three hard phase-gates: **A** (pre-flight integrity-lint, gap-08 §3.5), **B** (episode-id round-trip, gap-05 §6), **C** (post-import integrity + provenance lint, gap-08 §3.5 + gap-05 §3.5).

### §3.1 Phases

| # | Phase | Inputs | Output | Idempotency mechanism | Exit gate | S5 entry |
|---|---|---|---|---|---|---|
| 1 | **Pre-flight** | tenant id, operator principal, snapshot path | run id; manifest skeleton | run-id is uuidv7; re-running with same run-id resumes | `health()` nominal; principal holds required capabilities | `migration_run_started{run_id, tenant_id}` |
| 2 | **Snapshot** | live SCNS tree | content-addressed snapshot (operator copies / git-tags) | snapshot is read-only by construction | snapshot_hash recorded in S5 | `migration_snapshot_recorded{run_id, snapshot_hash}` |
| 3 | **Inventory** | snapshot | manifest rows (one per row of §2.1 mapping) | manifest stored with run-id; rerun reads existing manifest | every source file maps to ≥1 manifest row or an explicit `out_of_scope` row (§1.1) | `migration_inventory_complete{run_id, row_count, out_of_scope_count}` |
| 4 | **Phase-gate A** | tenant state | `lethe-audit lint --integrity` report | n/a (read-only) | `--integrity` converges; gap-08 §3.5 | `migration_phase_gate{gate:"A", status:"pass"}` |
| 5 | **Authored synthesis import (S4a)** | manifest rows §2.1 #1–#5, #9 (without invalidation tail) | S4a pages | per-row `idempotency_key` (api §1.2); file-system atomic-rename on the S4a side (composition §5 row S4a) | every authored row has `status=done` or `status=escalated` | per-row `migration_row_applied` entries |
| 6 | **Episode import (S1)** | manifest rows §2.1 #6, #7 | S1 episodes (fact-edges async) | per-row `idempotency_key`; api §3.1 step 1 replay returns 200 | every episodic row has `status=done` or `status=escalated`; ordered deterministically by `(ts_recorded_scns, source_path)` so episode-id derivation is stable across resumes | per-row `migration_row_applied` |
| 7 | **Phase-gate B** | manifest with `applied_episode_id` populated | sample comparison report | n/a (read-only) | for ≥1% sampled rows (min 50), recomputing the §2.3 episode-id formula yields the manifest's `applied_episode_id`; gap-05 §6 | `migration_phase_gate{gate:"B", sample_size, mismatches:0}` |
| 8 | **Archive / invalidation** | manifest rows §2.1 #8, #9-tail | `forget(invalidate)` calls | per-row `idempotency_key` (a *second* uuidv7 derived as §2.3 over the originating id, with discriminant `"forget"`); `expected_version` from `audit()` lookup | every archive row resolved to `done` or `orphan_logged` | per-row `migration_invalidation_applied`; orphans logged with `migration_orphan_archive` |
| 9 | **Async drain** | runtime | dream-daemon catches up | n/a (waiting) | `health()` reports `pending_extractions=0` and `last_consolidate_at > migration_phase_8_done_at` | `migration_drain_complete{pending_extractions:0, last_consolidate_at}` |
| 10 | **Phase-gate C** | tenant state | `lethe-audit lint --integrity`, `provenance-required`, `provenance-resolvable`, `forget-proof-resolves` reports (gap-05 §3.5; gap-08 §3.5) | n/a (read-only) | every named lint passes (zero violations) | `migration_phase_gate{gate:"C", status:"pass"}` |
| 11 | **S3 backfill** | runtime | embeddings populated | `scripts/embed/rebuild.sh` (composition §7 row S3-stale) is itself idempotent (re-embeds nodes whose embedding-hash differs) | non-blocking on api surface (recall has lexical fallback per composition §3.1); operator chooses whether to wait | `migration_s3_backfill{nodes_embedded, started_at, completed_at}` |
| 12 | **Recall determinism probe** | operator-curated probe set | per-probe diff report | probe set is deterministic; rerun reproduces the diff | for each probe, returned `fact_ids` set diff is within tolerance (operator-set; default ≤5%) | `migration_recall_probe{probes_run, drift_max_pct}` |
| 13 | **Cutover** | operator action | tenant marked live | n/a | operator flips downstream agent from SCNS-as-substrate to Lethe-as-substrate (out of WS7's mechanical scope; named for completeness) | `migration_cutover{run_id, tenant_id}` |
| 14 | **Post-cutover S4b regeneration** | runtime | `MEMORY.md`-shape projections (S4b) | dream-daemon regenerates from S1 on next consolidation gate (composition §2 row S4b; §4.4) | `MEMORY.md` exists under tenant root; content_hash differs from the snapshot's `MEMORY.md` (because S4b is regenerated from S1, not copied) | `migration_s4b_regenerated{run_id}` |

Phase-gate failures halt the run; resumes pick up from the failed phase (§3.2). Phase 8 and Phase 11 are independently restartable: a failed `forget` row goes back to `pending`; a partial S3 backfill resumes from the last embedded node.

### §3.2 Resumability mechanism

- The manifest (§3.1 phase 3) is the run's source of truth. Each row carries `status ∈ {pending, in_flight, done, failed, escalated, orphan_logged}` and (after first success) the `applied_episode_id` returned by the runtime.
- Per-row `idempotency_key` makes every `remember` / `forget` re-runnable within the api §1.2 24 h TTL window — replays return 200 with the original response (api §1.2; gap-08 §3.1).
- For runs that exceed 24 h, the manifest's recorded `applied_episode_id` is the resume key: on retry, migration first issues `audit(provenance.source_uri="scns:<shape>:<scns_observation_id>")` and skips the row if a hit is returned. This avoids the api §1.2 "fresh call" path that would duplicate after TTL expiry.
- A pre-flight check in Phase 1 (resume runs only) re-derives §2.3 over the prior manifest's rows and halts on mismatch — a mismatch indicates either a tenant-id change or a source-id formula bug, and the run halts before any writes (Phase-gate B logic, run pre-flight). On fresh runs no prior `applied_episode_id` exists and the check is a no-op.

### §3.3 Section-split rule for `~/.claude/CLAUDE.md`

The global preferences file is a multi-section markdown blob. Single-page import would either bust the 10 KB always-load cap (gap-09 §6; api §0.3 #3) or force an arbitrary truncation. The migration splits it:

- **One Lethe preference page per top-level `##` heading.** Each page's stable id is a slug derived from the heading text; `scns_observation_id = claude-md:<slug>`.
- Pages preserve the original heading as their first line so the human-editable surface (composition §1.1) reads naturally.
- The 10 KB cap is enforced by the runtime at recall time (api §2.1 step 10), ordered by recency-of-revision (api §0.3 #3); migration writes every section regardless of total size and trusts the recall-time ordering.

If the source CLAUDE.md has no `##` headings (rare), the entire file lands as one page with `scns_observation_id = claude-md:root`.

### §3.4 Procedure-vs-narrative classification heuristic

For `lessons/<slug>.md` rows that are not prohibitions (§2.1 row 2 already routed them):

- **Procedure** if **all** of:
  1. Body has ≥3 `##`/`###` headings.
  2. At least one section contains an ordered list with ≥3 items.
  3. Frontmatter `tags` includes one of `procedure | how-to | guide | steps | playbook` *or* the page title contains one of those tokens.
- Else **narrative**.

The heuristic favors `narrative` (the safer, lower-priority kind per scoring §5.4) on ambiguity. Misclassification is correctable post-cutover: `forget(invalidate, fact_id)` then `remember(kind="procedure", ...)` re-import. The accuracy floor is a §10 residual unknown.

### §3.5 What migration does NOT call

- **`promote`** — not used. Promotion is a runtime feedback path (api §3.2); migration imports facts at their default priority and lets the dream-daemon score them.
- **`peer_message`** — not used. SCNS has no peer-messaging surface; migration data is single-author per row.
- **`capture_opt_in_trace`** — not used in the migration path. If the operator wants to opt the destination tenant into eval-trace ingest, that is a separate api §4.1 call after cutover (§0.3 #5; HANDOFF §12.5).
- **`emit_score_event`** — not callable (it's an internal sink per api §4.2; decision #7 in HANDOFF §12.3).

---

## §4 Concurrency contract — migration alongside live ingest

### §4.1 Cold-start case (recommended v1 path)

The destination tenant has **no other writers** for the duration of the run. The operator pauses agent ingest; migration is the sole writer; cutover follows. Phase-gate B is the simplest in this mode (no live writes interleave to perturb episode-id derivation).

### §4.2 Warm-tenant case (supported, with constraints)

If other agents must keep ingesting during migration, every migration `remember` / `forget` obeys the api §1.3 `expected_version` CAS. On `409 version_conflict`, the migration row is retried with refreshed version per gap-04 §3 candidate (a) optimistic-CAS. Convergence is guaranteed as long as the concurrent-writer count stays inside gap-04 §5's instrumentation envelope (~10 writers/tenant); the `single_writer_per_tenant=true` config flag (gap-04 §4 stop-gap) is a tenant-level alternative that serializes all writes — operationally equivalent to the cold-start case for the migration's duration.

`remember` does not take `expected_version` (it creates rather than mutates per api §3.1; api §8 anti-checklist line 7), so the only CAS surface migration touches is the `forget(invalidate)` cascade in Phase 8.

### §4.3 Recall-determinism preservation

Any `recall_id` issued before the migration began is reproducible from `(tenant_id, ts_recorded, query_hash)` (api §1.4); migration does not replay or re-derive `recall_id`s, only adds episodes/facts. The replay invariant (scoring §8.3) is preserved because:

- `recall_id` derivation depends only on request inputs, not on the contents of S1.
- Bi-temporal invariants (composition §5; scoring §6) mean that an as-of query (api §2.1 `scope.valid_at`) issued *before* the migration cutover and replayed *after* cutover with the same `valid_at` returns the pre-cutover fact-set (because migration adds new episodes, not retroactive ones — every imported episode has `recorded_at = ts_recorded_scns ≤ now`, and the bi-temporal index distinguishes `recorded_at` from `valid_from`).

A subtle case: an in-flight `recall` that started *before* migration writes a fact and finished *after* may see the new fact in its top-k. This is not a determinism violation; it is the bi-temporal model working as designed (composition §5; scoring §4.1 pre-RRF filter is on `valid_at`, not on `recorded_at`).

### §4.4 Tenant-scope invariant

Every migration call carries the destination `tenant_id`; cross-tenant migrations are not supported in one run (api §1.8). The migration tool refuses to start if the manifest contains rows for more than one tenant.

### §4.5 Per-phase locking

Phase 8 (archive/invalidation) and Phase 9 (async drain) implicitly coordinate through the dream-daemon's per-tenant lock (composition §4.4; gap-04 §3). Migration does **not** acquire that lock directly; it observes `health()` to determine when the daemon is idle. The dream-daemon's stale-lock-break (gap-08 §3.4) protects against a daemon crash holding the lock past Phase 9's exit.

---

## §5 Failure modes & recovery

Per-phase rows mapped to composition §7's degraded-mode taxonomy.

| Phase | Failure | Detection | Recovery | Composition §7 row |
|---|---|---|---|---|
| 1 Pre-flight | tenant not provisioned | `health()` returns 404 | abort run; no state to roll back | n/a |
| 1 Pre-flight | operator lacks capability (e.g., `forget_purge` not held but Phase 8 needs it) | runtime returns `403 forbidden` on capability probe | abort run; surface required capability list | api §1.6 forbidden |
| 4 Phase-gate A | integrity lint diverges | `lethe-audit lint --integrity` non-zero | fix per-row issues per gap-08 §3.5; do not proceed; this is a tenant-state problem, not a migration problem | gap-08 §3.5; composition §7 row "S5 append fails" |
| 5 S4a import | atomic-rename failure (partial write) | rename system call returns error | redo the single row; idempotent on `provenance.source_uri` | composition §7 row "S4b regeneration loop crashes mid-write" (analogous) |
| 5 S4a import | classifier returns `escalate` | api §3.1 returns `422 classifier_escalate` | manifest row marked `escalated`; run continues; operator reviews per api §3.1 escalate path | api §3.1 escalate path |
| 6 S1 import | T1 abort (S1 down or S2 locked) | `5xx store_unavailable` | retry with same `idempotency_key` (api §1.2); back off per row | composition §7 rows "S1 down" + "S2 down or locked" |
| 6 S1 import | classifier escalates a row | `422 classifier_escalate` | row marked `escalated`; run continues | api §3.1 escalate path |
| 6 S1 import | classifier returns `peer_route` | `400 invalid_request` with hint | manifest row marked `failed` with `error="peer_route_unexpected"`; investigate (no SCNS row should classify as peer) | api §3.1 peer_route branch |
| 7 Phase-gate B | episode-id mismatch | sample-comparison fails | halt; investigate non-determinism source: clock/timezone bug in `ts_recorded_scns` extraction; source-id collision (see §10); or a tenant-id rebind across the run (Phase 1 pre-check should have caught) | gap-05 §6 |
| 8 Invalidation | target not found | `forget` returns `404 not_found` | log `migration_orphan_archive` to S5; **not** a halt — orphan archives without live counterparts are normal (the source archive entry was created before the source was migrated, e.g., a lesson archived before the lesson itself was authored) | composition §6 (audit trail); gap-11 §3.1 |
| 8 Invalidation | CAS mismatch (warm-tenant) | `409 version_conflict` | retry with refreshed `expected_version` per §4.2 / gap-04 §3 | gap-04 §4 |
| 9 Async drain | daemon stuck | `health()` reports `time-since-last-successful-consolidation > 2× gate_interval` | escalate per gap-01 §3.2; do not proceed to Phase-gate C; this is a runtime problem, not a migration problem | composition §7 row "Dream-daemon stuck" |
| 10 Phase-gate C | provenance lint fails | `provenance-required` non-zero | halt; backfill provenance (typically a manifest row that lost its `source_uri` due to a tool bug); do not cut over | gap-05 §3.5 |
| 10 Phase-gate C | integrity lint fails | `lethe-audit lint --integrity` non-zero | halt; same recovery as Phase-gate A — fix the underlying inconsistency | gap-08 §3.5 |
| 11 S3 backfill | embed worker error | `rebuild.sh` non-zero exit | non-blocking on api surface (recall has lexical fallback per composition §3.1); operator can defer or retry | composition §7 rows "S3 stale" + "S3 unavailable" |
| 12 Recall probe | fact-id-set diverges from expected beyond tolerance | probe-replay diff > operator threshold | investigate (likely a §3.4 heuristic miss or an over-aggressive Phase 8 invalidation); re-import affected rows | gap-14 (eval-bias) — analogous |
| any | `409 idempotency_conflict` | api §1.2 — same key, different body | **halt and require operator review.** This is a manifest bug (the migration tool produced two writes with the same key but different content); it is not a transient failure. | api §1.2 |
| any | disk full on Lethe host | `5xx` from runtime | abort; resume after operator clears space | composition §7 row "Disk full" |

### §5.1 Escalation handling

`escalate`-class returns from api §3.1 are **first-class** outcomes for migration, not failures: the runtime's gap-12 classifier flagged the content as sensitive (gap-10 §6 / gap-11 §3.3 surface), staged the episode for review, and returned `422 classifier_escalate` with `ack="staged_for_review"`. Migration marks the manifest row `escalated` and continues. The operator drains the staged-for-review queue post-migration via the api §3.1 escalate path (an out-of-band review workflow that is itself a HANDOFF §12.6 open item; WS7 inherits, does not re-decide).

### §5.2 What is NOT a migration failure

- A row classified to `kind=narrative` that the operator later believes should have been `procedure` — this is a §3.4 heuristic outcome, correctable post-cutover via `forget` + `remember` re-import.
- An `archive/` orphan with no live counterpart — logged, not halted (§5 phase 8 row).
- A `criticStatus=suppress` row that lands as `remember` then `forget(invalidate)` — this is the §2.1 row 9 design; the audit trail is the point.
- The dream-daemon picking up a single low-confidence extraction — that is gap-06 territory, not migration.

---

## §6 Verification

How an operator confirms a run produced a correct migration. All checks are on the destination tenant, after cutover, against the run's manifest and S5 entries.

### §6.1 Phase-gate outputs

The S5 entries `migration_phase_gate{gate:"A"|"B"|"C", status:"pass"}` are the primary verification signal. Their absence (or `status:"fail"`) means the run is incomplete. An operator querying `audit(query="migration_phase_gate", run_id=...)` must see all three.

### §6.2 Provenance round-trip

For every imported episode (or a sampled subset, e.g., 5%):

The 5% sample-rate is intentionally larger than Phase-gate B's ≥1% (§3.1 step 7) because the round-trip below exercises three independent checks (steps 3–5: `audit()` lookup by `source_uri`, `episode_id` equality, and snapshot `content_hash` equality), whereas Phase-gate B verifies only the §2.3 episode-id derivation in isolation.

1. Read the manifest row's `source_path` and `scns_observation_id`.
2. Compute `expected_source_uri = "scns:<shape>:<scns_observation_id>"` (with optional query-string from §1.3).
3. `audit(query="provenance.source_uri == <expected_source_uri>")` must return exactly one hit.
4. The hit's `episode_id` must equal the manifest row's `applied_episode_id`.
5. The snapshot file's content_hash (over the original SCNS bytes) must equal the value recorded in S5 at Phase 5/6 row-application time.

A mismatch on (3), (4), or (5) is a P0 verification failure.

### §6.3 Recall-determinism on a held-out probe set

Operator-curated probe set of ~50 queries spanning the four `kind`s (preference / prohibition / procedure / narrative + episodic facts). For each probe:

1. Issue `recall(query, intent, k=10)` against the destination tenant.
2. Compare the returned `fact_ids` set against the operator's expected set (curated from prior knowledge of the SCNS corpus).
3. Drift = `|expected ∆ returned| / |expected|`.

Drift > tolerance (default 5%) on more than 10% of probes triggers an investigation per §5 phase 12. The `recall_id`s themselves are *not* compared (they depend on `ts_recorded`, which differs between probe runs); the determinism check is on the fact-id-set, which is bi-temporally stable.

### §6.4 Preference-cap honoring

`recall(k=0, scope={kind: "preference"})` against the destination tenant returns the preferences slice. Verify:

- Total `content` byte-size across `preferences[]` ≤ 10 KB (api §0.3 #3; gap-09 §6).
- Ordering is recency-of-revision (api §0.3 #3); the per-page `applied_at` (or for migrated pages, `ts_recorded_scns`) is non-increasing.
- `preferences_truncated` flag is set if and only if at least one preference page was excluded by the cap.

### §6.5 Anti-checklist verification

Run the §6.6 audit transcripts and confirm each passes. The anti-checklist:

- No verb in `docs/07-migration-design.md` reads SCNS data after cutover.
- No mapping row writes without `idempotency_key` and `provenance.source_uri`.
- No phase lacks an explicit gate or "no gate" justification.
- No language in this doc treats markdown as "for humans only" (HANDOFF §13).
- No `migrate_*` verb is introduced into the api surface.

A QA failure on any anti-checklist item is a P0; a missing or weak cross-ref is a P1.

### §6.6 Audit transcripts

Mirroring api §7.1–§7.3 and scoring §7.

#### §6.6.1 SCNS-independence audit

**Audit:** `grep -i scns docs/07-migration-design.md` — every hit must be a boundary-clause, an audit transcript, an in-doc reference to *the source corpus* (which is SCNS, by definition, since this is the migration design), or a `provenance.source_uri` literal of the `scns:<shape>:<id>` form.

**Expected result:** zero hits that name SCNS as a *runtime* dependency. Allowed hits: source-corpus references; `provenance.source_uri` form; HANDOFF §10 / api §0.3 #1 boundary citations; the §8 anti-checklist denial; this §6.6.1 audit itself.

**Result (transcribed at commit time):**

- All `scns`/`SCNS` mentions in this doc are in: §0–§3 (the migration target is, definitionally, the SCNS corpus — these are source-corpus references); §2.3 + §6.2 `provenance.source_uri` literals (audit-trail format); §0.3 #1 + §8 anti-checklist (binding-constraint disclaimers); this §6.6.1 (the audit itself); HANDOFF §10 / §12.5 citations.
- **Zero hits introduce a runtime read path to `~/.scns/`.** The §3.1 phase 13 (cutover) is the cut-line; after cutover the runtime has no SCNS dependency.
- **Zero verb signatures in the api surface are introduced or extended.** This doc calls only the existing api §2–§4 verbs.

This audit is verifiable: run `grep -in scns docs/07-migration-design.md`; every hit should be of one of the allowed kinds above.

#### §6.6.2 Idempotency-key coverage audit

**Claim:** every mapping row in §2.1 that issues a write verb carries an `idempotency_key`.

| §2.1 row | Verb | `idempotency_key`? | Derivation |
|---|---|---|---|
| 1 (CLAUDE.md per-section) | `remember` | yes | §2.3 — `scns_observation_id = claude-md:<slug>` |
| 2 (lessons prohibition) | `remember` | yes | §2.3 — frontmatter `id` or `lessons/<slug>` |
| 3 (lessons procedure) | `remember` | yes | §2.3 |
| 4 (lessons narrative / weekly / monthly) | `remember` | yes | §2.3 |
| 5 (negative) | `remember` | yes | §2.3 — frontmatter `id` (uuid) |
| 6 (sessions) | `remember` | yes | §2.3 — `sessions/<date>/<hash>` |
| 7 (daily blocks) | `remember` | yes | §2.3 — `daily/<date>#<HH:MM:SS>#<seq>` |
| 8 (archive invalidation) | `forget(invalidate)` | yes | §3.1 phase 8 — second uuidv7 with `"forget"` discriminant |
| 9 (suppress invalidation) | `remember` then `forget(invalidate)` | yes (both) | §2.3 + §3.1 phase 8 |

**Coverage: 9/9 mapping-row write paths carry mandatory `idempotency_key`. PASS.**

#### §6.6.3 Phase-gate coverage audit

**Claim:** every phase in §3.1 has either a defined exit-gate or an explicit "no gate" justification.

| Phase | Exit gate | Notes |
|---|---|---|
| 1 Pre-flight | `health()` nominal + capability check | gate present |
| 2 Snapshot | snapshot_hash recorded | gate present |
| 3 Inventory | every source maps to ≥1 manifest row or `out_of_scope` | gate present |
| 4 Phase-gate A | `lethe-audit lint --integrity` converges (gap-08 §3.5) | **hard gate** |
| 5 S4a import | every authored row done/escalated | gate present |
| 6 S1 import | every episodic row done/escalated, ordered deterministically | gate present |
| 7 Phase-gate B | episode-id sample round-trip 0 mismatches (gap-05 §6) | **hard gate** |
| 8 Archive / invalidation | every archive row done/orphan_logged | gate present |
| 9 Async drain | `pending_extractions=0`, `last_consolidate_at > phase_8_done_at` | gate present |
| 10 Phase-gate C | integrity + provenance + forget-proof lints all pass (gap-05 §3.5; gap-08 §3.5) | **hard gate** |
| 11 S3 backfill | non-blocking; operator chooses wait or defer | "no gate" justified — composition §3.1 lexical fallback survives S3 outage |
| 12 Recall probe | drift within tolerance (operator-set) | gate present |
| 13 Cutover | operator action | "no gate" justified — out of WS7 mechanical scope; named for completeness |
| 14 S4b regeneration | `MEMORY.md` exists with hash differing from snapshot | gate present |

**Coverage: 14/14 phases have a defined gate or justified "no gate". 3/3 hard phase-gates present (A, B, C). PASS.**

#### §6.6.4 Markdown-audience audit

**Claim:** no language in this doc treats markdown as "for humans only" (HANDOFF §13 cascade; composition §1.1 binding).

**Audit:** read this doc end-to-end for the patterns "for humans", "human-only", "human-readable only", "humans read", "not for LLMs", "for humans not LLMs".

**Result (transcribed at commit time):**

- §0.3 #8 explicitly affirms dual-audience and cites composition §1.1 + HANDOFF §13.
- §3.3 names the human-editable surface (CLAUDE.md split) without claiming exclusivity; the same pages are reachable via `recall_synthesis` (api §2.2).
- §1.1 + §2.1 + §6.4 use "human-editable" and "operator" and "agent" interchangeably as appropriate, never "human-only".
- §0.4 vocabulary cross-walk mentions S4b without "for humans only" framing.
- **Zero hits** for the disallowed patterns.

PASS.

---

## §7 Stopping criteria

For one tenant migration to be **complete**:

- §3.1 phases 1–14 all have S5 entries with success status.
- All three hard phase-gates (A, B, C) have `status:"pass"` S5 entries.
- §6.2 provenance round-trip: zero P0 mismatches on a 5% sample.
- §6.3 recall-determinism probe: drift within operator-set tolerance.
- §6.4 preference-cap: recall returns ≤10 KB, recency-ordered, `preferences_truncated` set correctly.
- An operator-signed `migration_run_complete{run_id, tenant_id, completed_at}` entry in S5.

After this, the tenant is cut over and the post-cutover S4b regeneration (§3.1 phase 14) runs on the next consolidation gate.

For **WS7 the deliverable** to be complete:

- This doc committed and pushed.
- HANDOFF §14 update appended (separate commit) with sub-sections 14.1–14.6 mirroring §10/§11/§12 shape.
- §6.6 audit transcripts committed in-doc with PASS results.
- §10 residual unknowns enumerated for WS8.

---

## §8 Anti-checklist — what WS7 is NOT

WS7 **does not** commit to:

- **A migration-tool source-code spec.** The doc is verb-call-shaped; the implementation is a follow-up. Owner: operator-tooling pass.
- **A `migrate_*` verb in the api surface.** Migration calls only the existing api §2–§4 verbs (HANDOFF §10 + §11.5 + api §0.3 #1; api §8 anti-checklist last bullet).
- **A SCNS compatibility shim in the runtime.** The §6.6.1 audit is the proof.
- **Consumption of `vault.db`.** The migration is corpus-only; consuming the SCNS broker SQLite would require a SCNS schema dependency (§0.3 #1 violation). Surfaced in §10.
- **Copying `MEMORY.md` / `SOUL.md` / `USER.md`.** Those are SCNS S4b-shape projections; Lethe regenerates them post-cutover from S1 (composition §2 row S4b).
- **Bypassing `capture_opt_in_trace`.** Eval-trace ingest is a separate, opt-in path (api §4.1; HANDOFF §12.5).
- **Transport / wire / auth / RBAC / deployment shape commitments.** WS8.
- **A cross-deployment Lethe→Lethe migration spec.** §10 residual unknown.
- **Synchronous fact-extraction of authored synthesis.** S4a synthesis pages migrate with `lethe.extract: false` (composition §8.3 Candidate C); operator opts in per-page if desired.
- **A guarantee that the dream-daemon completes Phase 9 in bounded time.** Daemon throughput is gap-01 territory; migration observes `health()` and waits.

---

## §9 Traceability matrix

Every WS7 decision traces back to its upstream §-ref.

| WS7 decision | Upstream §-ref(s) |
|---|---|
| Five-store vocabulary throughout (S1–S5) | composition §2 |
| Markdown is dual-audience (§0.3 #8) | composition §1.1; HANDOFF §13 |
| Migration calls only existing api verbs (§0.2, §3.5, §8) | HANDOFF §10 + §11.5 + §12.5; api §0.3 #1, §8 anti-checklist |
| Idempotency-key uuidv7 derivation (§2.3) | api §1.2 + §1.4 (RFC 9562 layout); gap-08 §3.1; HANDOFF §12.5 |
| Episode-id uuidv7 derivation (§2.3) | api §1.4 (RFC 9562 layout); gap-05 §6 |
| `provenance.source_uri = scns:<shape>:<id>` (§2.3) | api §1.5; gap-05 §3; HANDOFF §12.5 step 4 |
| Authored vs derived split (§2.2) | composition §2.1, §8.3 Candidate C; gap-09 §3 + §7 |
| Synthesis migrates with `lethe.extract: false` (§2.1, §8) | composition §8.3 Candidate C |
| CLAUDE.md split per-section (§3.3) | gap-09 §6; api §0.3 #3 |
| Procedure-vs-narrative heuristic (§3.4) | gap-09 §3; scoring §5.3, §5.4 |
| Phase-gate A pre-flight (§3.1) | gap-08 §3.5 |
| Phase-gate B episode-id round-trip (§3.1) | gap-05 §6 |
| Phase-gate C post-import lints (§3.1) | gap-05 §3.5; gap-08 §3.5 |
| Async drain via `health()` polling (§3.1, §4.5) | composition §4.4; gap-01; gap-08 §3.4 |
| S3 backfill via `scripts/embed/rebuild.sh` (§3.1) | composition §7 row "S3 stale" |
| `MEMORY.md` excluded; S4b regenerated post-cutover (§3.1 phase 14, §8) | composition §2 row S4b |
| Cold-start recommended; warm supported via CAS (§4.1, §4.2) | gap-04 §3 + §4 |
| Recall-determinism preserved via api §1.4 (§4.3) | api §1.4; scoring §8.3 |
| Tenant-scope invariant (§4.4) | api §1.8; composition §5.2 |
| Archive → `forget(invalidate)` (§2.1 row 8, §3.1 phase 8) | gap-11 §3.1 |
| `criticStatus=suppress` → `remember` then `forget(invalidate)` (§2.1 row 9) | gap-11 §3.1; gap-05 §3.4 (audit-trail invariant) |
| Escalation is a first-class outcome, not a failure (§5.1) | api §3.1 escalate path; gap-12 §6 |
| Capture-opt-in is not bypassed (§0.3 #5, §3.5) | api §4.1; HANDOFF §12.5 |

---

## §10 Residual unknowns

- **Daily-block source-id collision.** §2.3 uses `daily/<date>#<HH:MM:SS>#<seq>` where `<seq>` is the 0-based ordinal among repeated identical timestamps. If a daily file is re-edited and a block is inserted *between* two existing same-second blocks, the `<seq>` of subsequent blocks shifts and prior episode-ids no longer round-trip. **Bet:** snapshot is content-addressed (§3.1 phase 2), so an in-flight edit cannot reach the migration; for the multi-snapshot case (re-running migration against a *new* snapshot of an evolving corpus), record the snapshot_hash in the manifest so the source-id formula can be augmented to `daily/<date>#<HH:MM:SS>#<seq>@<snapshot_hash[:8]>` if collisions are observed. Surfaced not pre-resolved.
- **Heuristic accuracy for §3.4 procedure-vs-narrative classification.** Regex-shaped heuristic; if precision drops below 80% on a labeled sample, swap for an LLM classifier — same gap-12 §6 pattern as `remember`. Instrument in the operator-tooling pass.
- **Volume thresholds where Phase 9 (async drain) becomes a multi-hour wait.** Bounded by dream-daemon gate cadence × episode count; instrument and set an explicit operator alarm (`time-since-last-successful-consolidation > N × gate_interval`). gap-01 territory; migration observes, does not fix.
- **Sensitive-content escalation policy at scale.** Migration honors `422 classifier_escalate` (§5.1), but the post-migration review workflow is HANDOFF §12.6 open. WS8 / project ops own the staged-for-review queue.
- **Cross-deployment Lethe→Lethe migration.** Bet: same shape as SCNS→Lethe but with `provenance.source_uri = lethe:<src_tenant>:<episode_id>`. Deferred to a v1.x follow-up; not blocked by anything in this doc.
- **`vault.db` consumption.** §1.1 / §8 exclude it; if a future operator policy requires SCNS broker metadata in Lethe (e.g., SQLite-side intent classifications), the path is to write a one-time exporter that emits the same SCNS-corpus-shaped markdown rows for migration to consume — keeping the §0.3 #1 boundary intact. Not in WS7 v1.
- **Operator UX for inspecting the manifest mid-run.** CLI / JSON / HTML — implementation-pass concern. Punted.
- **Idempotency-key TTL extension.** api §1.2 sets 24 h; gap-08 §5 names it as a guess and recommends instrumentation. For very large corpora that exceed 24 h to drain, §3.2 falls back to `audit(provenance.source_uri=...)` lookup; instrument the fallback rate and consider lifting the TTL if the rate is high.
- **Phase 11 S3 backfill duration.** Volume-sensitive; not a blocker because lexical fallback survives. WS8 may want to expose progress via `health()`.

---

## §11 Change log

- **(this commit)** Initial WS7 design — source inventory, mapping rules, ordered phase plan with three hard phase-gates, concurrency contract, failure-recovery table, verification contract, audit transcripts, traceability, residual unknowns. Awaiting WS7-QA fresh-eyes pass.
