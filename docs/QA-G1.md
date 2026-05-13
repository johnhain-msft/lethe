# QA-G1 — Cross-phase coherence audit (P1 + P2 + P3)

> Group-level QA per `docs/GO-NO-GO.md` §7 (per-3-phases cadence). Run
> after P3 exit, before P4 kickoff. Audits cross-phase contracts, **not**
> per-phase exit gates — those are owned by `docs/QA-P{1,2,3}.md` and are
> cited rather than re-litigated. Erratum E1 (`docs/IMPLEMENTATION-followups.md`)
> is binding: the write-side embedder is P4 scope, not P3, and is not
> critiqued here.

---

## §A Scope

### A.1 Phases + binding-doc revisions

| Phase | Verdict (per-phase) | Commits | QA artifact |
|---|---|---|---|
| P1 — storage substrate | APPROVE-WITH-NITS | `b67ed3e..d616eb2` | `docs/QA-P1.md` |
| P2 — write path (`remember`) | APPROVE-WITH-NITS | `b84b7b9..2ef90fc` | `docs/QA-P2.md` |
| P3 — read path (`recall` + `recall_synthesis`) | APPROVE-WITH-NITS | `cc32807..6f63e0d` | `docs/QA-P3.md` |

Audit window for G1: `cc32807^..HEAD` (covers all three phases plus their
QA docs and the E1 erratum). Binding doc revisions:

- IMPL: `git show 698488b:docs/IMPLEMENTATION.md` (planning-phase ephemera
  cleanup `93eb8ad` deleted the working-tree copy; `698488b` remains the
  binding rev per HANDOFF §17).
- GO-NO-GO: `git show 93eb8ad^:docs/GO-NO-GO.md` (same).
- IMPL erratum: `docs/IMPLEMENTATION-followups.md` Erratum E1.

### A.2 Toolchain footer

- `uv 0.10.0`
- `Python 3.11.14` (`.venv`)
- `Darwin 15.7.4`
- `uv sync --extra dev` → `Audited 44 packages` (no drift)
- One-shot health pass under `LETHE_HOME=$(mktemp -d -t lethe-qa-g1.XXXXXX)`:
  - `uv run pytest tests/ -q` → **343 passed, 1 warning** in 3.90 s
  - `uv run ruff check src/ tests/ cli/ scripts/` → `All checks passed!`
  - `uv run mypy src/lethe/` → `Success: no issues found in 46 source files`

Per-phase exit gates intentionally **not** re-run — covered by QA-P1 §A
(35 tests, ruff clean, mypy clean across 20 files), QA-P2 §A (177 tests,
29 files), QA-P3 §A.3 (343 tests, 46 files). The single-shot G1 health
pass at HEAD matches QA-P3's counters exactly, confirming no regression
between QA-P3 commit `24b2086` and the G1 audit point.

### A.3 Anti-checklist (binding self-restraint)

- [x] No production code or test under `src/`, `cli/`, `tests/` modified.
- [x] `docs/QA-P1.md`, `docs/QA-P2.md`, `docs/QA-P3.md` not touched.
- [x] No re-grading of per-phase exit gates (cited only).
- [x] No write-side embedder critique filed (E1 binding).
- [x] No P1/P2/P3 locked decision re-litigated.
- [x] No commit / push performed; `docs/QA-G1.md` staged only.
- [x] All test invocations used `LETHE_HOME=$(mktemp -d -t lethe-qa-g1.XXXXXX)`.

---

## §B Cross-phase contract coherence

### B.1 Tenant-isolation flow `remember` (P2) → `recall` / `recall_synthesis` (P3)

| Hop | Site | Tenant scope honored? |
|---|---|---|
| Per-tenant root partition | `runtime/tenant_init.py` `_tenant_root() = storage_root/"tenants"/tenant_id` | ✓ (QA-P1 §C R4) |
| Per-tenant S2 file | `store/s2_meta/schema.py:S2Schema.db_path = tenant_root/"s2_meta.sqlite"` | ✓ |
| `remember` write | `api/remember.py:603-660` opens T1 over the per-tenant S2 + S1 (`group_id=tenant_id`) | ✓ (QA-P2 §B.4) |
| Idempotency lookup | `runtime/idempotency.py:134-136` `_storage_key(key, verb)` namespaces per verb; tenant scope is the per-tenant S2 file the connection points at | ✓ |
| `recall` request validation | `api/recall.py:651-652` refuses empty `tenant_id` | ✓ |
| `recall_id` derivation | `runtime/recall_id.py:96-106,113` mixes `tenant_id` into the `sha256` pre-image producing the 74 deterministic bits | ✓ |
| Ledger write | `api/recall.py:383-389` INSERT carries `tenant_id` as a column on every row | ✓ |
| Event emission | `runtime/events.py:_COMMON_REQUIRED` requires `tenant_id` on every envelope (lines 62-73) | ✓ (and matches stored uuidv7 layout fact) |
| `recall_synthesis` | `api/recall_synthesis.py:288-290` refuses empty `tenant_id`; threads it through to `compute_query_hash` + `derive_recall_id` (lines 330, 358, 377, 389) | ✓ |
| Preferences source | `api/recall.py:679 preference_source.list_preferences(tenant_id=request.tenant_id)` | ✓ |

`grep -rn "tenant_id" src/lethe/` shows no path that skips the scope. The
substrate-level R4 partition (per-tenant directory + per-tenant SQLite
file + Graphiti `group_id=tenant_id`) is honored by every cross-phase
call site. **Contract holds end-to-end.**

### B.2 Idempotency keying vs `recall_id` keying — disjoint namespaces, shared uuidv7 layout

The two surfaces share the **canonical RFC 9562 uuidv7 layout** (48-bit ts
prefix + version `0111` + variant `10` + 74 deterministic bits derived
from a `sha256` over tenant-scoped inputs — the layout fact stored in
session memory) but inhabit **disjoint storage keyspaces** with no
collision risk:

| Surface | Keyspace | Key derivation | Storage |
|---|---|---|---|
| `idempotency_keys` (P2) | client-supplied uuidv7 (api §1.2) | `_storage_key = "{verb}:{key}"` (`runtime/idempotency.py:134-136`); `verb` namespace prevents same-uuid collision across verbs | `s2_meta.idempotency_keys.key` (PK) |
| `recall_ledger` (P3) | server-derived deterministic uuidv7 | `derive_recall_id(tenant_id, ts_recorded_ms, query_hash)` (`runtime/recall_id.py:75-128`) where `query_hash = sha256(canonical_json({query, intent, k, scope}))[:16]` | `s2_meta.recall_ledger.recall_id` (PK) |

Concretely:

- The two PK columns live on **different tables** within the same per-tenant
  S2 file (`schema.py:_DDL_IDEMPOTENCY_KEYS` line ~120 vs `_DDL_RECALL_LEDGER`
  line ~165). SQLite scopes PRIMARY KEY constraints per-table; even a hash
  collision on the uuid string would not be enforced as a conflict.
- `recall.py:209-216` is explicit about this: *"There is no `idempotency_key`
  field: `recall_id` is itself the idempotency key for the read path."*
  i.e. `recall` deliberately does NOT consult `idempotency_keys` — it uses
  `INSERT OR IGNORE` on the deterministic `recall_id` instead.
- A client-supplied uuidv7 idempotency key would need a multi-attribute
  collision (same 48-bit ms timestamp prefix AND identical leading 74
  bits of `sha256(tenant_id ‖ query_hash)`) to be byte-identical to a
  server-derived `recall_id`. Even if it occurred, the values land in
  separate tables so neither surface can poison the other.

`recall_id.py:21-26` documents the predecessor-handoff slip (the spurious
`"rec"` discriminant + `ts_recorded` in the hash) as superseded — the
anti-regression test `test_no_ts_recorded_in_deterministic_bits`
(QA-P3 §B.2 line cite) is the standing guard. **No keyspace conflict;
shared layout is correct.**

### B.3 Provenance-envelope reuse on the read path

The P2 envelope (`runtime/provenance.py`) is **imported, not copied** on
the P3 read path:

- `api/remember.py:76-77` imports `ProvenanceRequired` + `make as
  make_provenance` from `lethe.runtime.provenance` (P2 author site).
- `api/recall.py` does NOT re-derive provenance bytes; provenance is
  carried through on the surviving `Fact` records from the retrievers
  (`recall.py:402` `test_facts_without_episode_id_are_dropped_after_scoring`
  cited in QA-P3 §C.1) and surfaced to the caller in the response envelope.
- `grep -rn "from lethe.runtime.provenance\|import provenance" src/lethe/`
  returns the two `remember.py` imports above — no parallel import in
  `recall.py` / `recall_synthesis.py`. The recall path consumes provenance
  *as data on the Fact records* it never strips it; the validation
  contract from `provenance.py` is the single source of truth and is
  invoked at the write site only (correct: validation happens once, at
  ingest).

**No drift surface.** Any future change to the envelope shape in
`provenance.py` propagates to the recall response automatically because
the recall path passes through the same dict-shaped record.

### B.4 Event-bus extensibility — predicted P4 shape

`runtime/events.py` (read at HEAD) confirms the one-line-extension
pattern QA-P2 §G.3 predicted and QA-P3 §G.3 verified:

- **EventType Literal** (lines 53-61) already enumerates **all seven**
  scoring §8.1 event types up front: `remember, recall, recall_outcome,
  promote, demote, invalidate, consolidate_phase`. P3 did NOT need to
  edit the Literal — only `_VALID_EVENT_TYPES` and `_PER_TYPE_REQUIRED`.
- **`_VALID_EVENT_TYPES` frozenset** (lines 63-72) — same seven names; no
  P4-driven edit required.
- **`_PER_TYPE_REQUIRED` dict** (lines 87-95) at HEAD currently carries
  two entries: `"remember": frozenset({"fact_ids","decision","provenance"})`
  (P2) and `"recall": frozenset({"recall_id","fact_ids","path"})` (P3).
- **`validate()` dispatch** (lines 109-178) iterates the dict generically
  — adding new event types requires no refactor of the function.
- **Common gates** (`_COMMON_REQUIRED` lines 75-86 + the explicit
  `contamination_protected is True` strict-identity check at lines
  130-133) sit **above** the per-type dispatch, so any P4 event type
  inherits §8.2 + §8.5 enforcement automatically.

**Predicted P4 extension** (per IMPL §2.4 file list "`runtime/events.py`
— adds `promote, demote, invalidate, consolidate_phase` event types"):
four one-line `_PER_TYPE_REQUIRED` entries, e.g.

```
_PER_TYPE_REQUIRED["promote"] = frozenset({"fact_id", "expected_version_consumed", ...})
_PER_TYPE_REQUIRED["consolidate_phase"] = frozenset({"phase_name", "tenant_id_lock_token", ...})
```

plus per-type `if event_type == "..."` branches in `validate()` for any
event-type that needs intra-field shape constraints (parallel to the
existing `remember` and `recall` branches at lines 156-178). **No common-path
refactor required.** P4 also benefits from the strict-`True` contamination
gate — `consolidate_phase` events emitted inside the dream-daemon will
fail-fast on `contamination_protected="true"` (string) per §8.5.

### B.5 Schema / DDL coherence — migration ratchet 1 → 2 → 3 → (P4)

`store/s2_meta/{schema,migrations}.py` ratchets cleanly across the three
phases. Every named table in `S2_TABLE_NAMES` (10 tables + the
`s5_consolidation_log` lodged inside S2 per §(g)) accounted for:

| Table | v1 (P1) | v2 (P2) | v3 (P3) | P4 owner? |
|---|---|---|---|---|
| `recall_ledger` | stub | stub | **columned** (D6) | extensions via ALTER (P5+ recall_outcome indexes) |
| `utility_events` | stub | stub | stub | **P4+** (consolidate writes utility events) |
| `promotion_flags` | stub | stub | stub | **P4** (consolidate consumes promote flags; QA-P3 cites IMPL §2.4) |
| `consolidation_state` | stub | stub | stub | **P4** (per-tenant lock state + last-run cursor; gap-01 §3.2) |
| `extraction_log` | stub | **columned** (P2 minimal scaffold per gap-06) | columned | **P4** (`runtime/consolidate/extract.py` writes confidence rows) |
| `tenant_config` | k/v | k/v | k/v | open k/v — no migration |
| `scoring_weight_overrides` | k/v | k/v | k/v | open k/v |
| `review_queue` | columned (deployment §6.2) | columned | columned | P7 indexes |
| `audit_log` | stub | **columned** (deployment §6.3) | columned | P5/P7 add row variants |
| `idempotency_keys` | columned (api §1.2 + I-5) | columned | columned | unchanged |

Migration discipline (`migrations.py` module docstring lines 17-22):

> *"v2 [...] drops and recreates each — no data preservation required.
> v3 [...] same drop-and-recreate semantics as v2 (table is an empty stub
> at v2 — no verb writes to it before P3). Future migrations (P4+) for
> tables that may already hold rows MUST use ALTER TABLE rather than
> drop-and-recreate."*

This is the **standing rule that protects P4** from accidentally
drop-recreating a populated `recall_ledger` (which holds real production
rows from the moment P3 ships). The rule is also re-stated in
`_m3_recall_ledger_columns` docstring (lines 53-60). **No breaking
column-shape change occurred between P1 and P3** for any table that ever
had a non-stub shape.

P4 will add two migration steps:

- v3 → v4: `consolidation_state` columned (per-tenant lock token, last-run
  cursor — gap-01 §3.2 + gap-08 §3.4). Drop-and-recreate is safe (still a
  stub at v3).
- v4 → v5 (or fold into v4): `promotion_flags` columned. Drop-and-recreate
  safe iff P5's `promote` verb hasn't shipped yet — IMPL §2.5 sequencing
  confirms `promotion_flags` is consumed at next P4 consolidate but
  *written* by the P5 `promote` verb, so v4 (P4 ships) gets to columnize
  before v5 (P5 ships) starts writing. **Sequencing holds.**
- `utility_events` may stay stub through P4 if consolidate writes only
  to `extraction_log` first; the migration docstring's ALTER-TABLE
  commitment kicks in once any verb starts writing real rows.

### B.6 Bi-temporal stamping — store-by-store rule for P4

Composition §1 row 48 + §3.2 + §5.1 fix the rule: **only S1 carries
`(valid_from, valid_to)` semantics; S4a (markdown synthesis pages) and
S2/S3/S5 do not.** P3's `recall_synthesis` skip is the canonical
realization of this rule (`api/recall_synthesis.py:340` explicit comment;
guard test `test_no_bitemporal_filter_invoked` at QA-P3 §C.4).

**Rule for P4 facilitator pickup:**

| P4 store touch | Bi-temporal filter / stamp? | Rationale |
|---|---|---|
| `runtime/consolidate/extract.py` reads new episodes from **S1** | ✓ stamp episode at write; filter at read | S1 = canonical bi-temporal substrate (composition §1 row 48) |
| `runtime/consolidate/score.py` scores S1 facts | ✓ filter pre-RRF when consolidate scoring overlaps the recall scoring path | scoring §4.1 + api §4.1 binding "before any ranker is consulted" — same rule that recall.py honors at line 747 |
| `runtime/consolidate/promote.py` writes `promotion_flags` to **S2** | ✗ no `valid_from/valid_to` columns on `promotion_flags` (S2 = ledger/state, not fact substrate) | S2 carries `created_at` + `updated_at` only (cf. `tenant_config`, `audit_log` schemas) |
| `runtime/consolidate/demote.py` writes `valid_to` on **S1** facts | ✓ this IS the bi-temporal write — sets `valid_to = now` | composition §1 row 48 — demote = bi-temporal supersession |
| `runtime/consolidate/invalidate.py` writes `valid_to` on **S1** facts | ✓ same as demote with the additional gravity-floor flag | scoring §3.5 + IMPL §2.4 |
| `runtime/consolidate/extract.py` writes embeddings to **S3** | ✗ S3 (sqlite-vec virtual table) has no bi-temporal columns | S3 keys by `(node_id|edge_id|episode_id)`; lifecycle is S1-driven (orphan-on-`valid_to` is a P4 cleanup question, not a stamp question) |
| Any **S4a** touch (synthesis page write/regen) | ✗ no filter, no stamp | composition §3.2 (qmd-style markdown), §5.1 (allowed S1↔S4a inconsistency); `recall_synthesis` precedent |
| Any **S5** consolidation-log write | ✗ S5 is append-only event log; `appended_at` only | `_DDL_S5_LOG` carries `seq + kind + payload_json + appended_at` |
| `extraction_log` confidence rows in **S2** | ✗ `extracted_at` only; no bi-temporal columns | `_DDL_EXTRACTION_LOG` (P2 scaffold) carries `extracted_at` + `extractor_version` only |

**Summary rule for P4**: stamp/filter on S1 only; everything else uses
its native timestamp column (`created_at` / `updated_at` / `appended_at` /
`extracted_at`). The P3 `recall_synthesis` skip pattern is the canonical
proof that "no bi-temporal filter" is a first-class supported posture,
not an oversight — P4 should mirror the same explicit-comment pattern at
the S4a / S2-state / S5 / S3 call sites it lands.

### B.7 Test isolation hygiene

- `tests/conftest.py:20-29` defends `LETHE_HOME` with both `monkeypatch.setenv`
  and an explicit `assert home.resolve() != real_home.resolve()` refusal
  to shadow `~/.lethe`. Re-verified at HEAD (file unchanged from the
  shape QA-P1 §B.1 cited).
- `grep -rn "from tests\|import tests" src/ cli/` returns **zero hits**
  at HEAD — production code never imports test fixtures.
- The G1 single-shot health pass (`pytest tests/ -q` → 343 passed) ran
  under a fresh `mktemp -d` LETHE_HOME with no leakage into `~/.lethe`
  (verified by absence of any side effect on the host filesystem).

**Hygiene holds across all three phases.**

---

## §C Risk-register status across P1 + P2 + P3

Per `git show 93eb8ad^:docs/GO-NO-GO.md` §6.1 (P0+P1 risk register).
"Standing risk" = §6.2 cross-phase tracking; do NOT mark closed at any
single phase exit.

| ID | Risk | P1 | P2 | P3 | Standing? | Next phase |
|---|---|---|---|---|---|---|
| R1 | Markdown write amplification | substrate slice closed (S4 layout per-tenant; QA-P1 §C) | not touched | not touched | yes — load-test boundary post-cutover | post-cutover |
| R2 | Crash-mid-write corruption | substrate slice closed (WAL + lint registry seam; QA-P1 §C) | T1 ACID slice closed (`remember.py` single S2 commit; QA-P2 §F R2) | not touched | yes — full closure at P8 | P5 + P8 |
| R3 | Provenance loss | substrate slice closed (lint registry + ProvenanceEdge baseline; QA-P1 §C) | substrate slice closed (`provenance.py` envelope refusal + 2 lints registered; QA-P2 §F R3 + §B.2) | substrate slice held (recall path drops facts without `episode_id` after scoring; QA-P3 §C.1, §D R5) | yes — full closure at P8 | P5 + P8 |
| R4 | Tenant isolation breach | substrate slice closed (per-tenant root + per-tenant S2/S3 + Graphiti `group_id`; QA-P1 §C) | non-regressed | non-regressed (`tenant_id` mixed into `recall_id` deterministic bits; QA-P3 §C.2) | runtime alarm + cross-tenant 404 still owed | **P7** |
| R5 | Scoring weight miscalibration | not touched | not touched | lib-level closed (5-term per-class dispatch + `DEFAULT_WEIGHTS = (0.2,0.3,0.2,0.4,0.5)`; QA-P3 §B.1, §D D1) | yes — calibration sweep post-cutover | P4 (defaults wired into consolidate) + P9 (sweep) |
| R6 | Utility-feedback signal loss | not touched | not touched | join-key plumbed (`recall_id` written to ledger; D5; QA-P3 §D D5, §G.3) | yes — closes asymptotically post-cutover | **P9** (recall_outcome ingest) |
| R7 | Intent classifier mis-routes | not touched | substrate slice closed (heuristic + LLM hybrid; gap-12 §3 + §5; QA-P2 §B.3) | classifier reused on recall path (`recall.py` step 2) | LLM upgrade is post-v1 deferral #19 | **P7** (LLM transport) |
| R8 | Idempotency-key TTL edge cases | not touched | substrate slice closed (24 h default + per-(tenant,verb) namespacing; QA-P2 §B.2 idempotency) | non-regressed | yes — full closure at P8 | P7 + P8 |

**No premature-closure claim** anywhere in the three phases. Every
"closed" entry above is the substrate-level slice; standing risks
(R2/R3/R6) remain open per GO-NO-GO §6.2.

---

## §D Standing-risk regression check

Confirm R3 / R5 / R8 substrate slices from earlier phases are not eroded
by the P3 additions.

### D.1 R3 — provenance integrity (P2 slice not eroded by P3)

- `audit/integrity.py:65-78` — `REGISTRY` populated by `_register_p2_lints()`
  on import. Re-verified by health-pass `mypy` clean across 46 files
  (registry not pruned).
- `audit/lints/` directory at HEAD: `__init__.py`,
  `provenance_required.py`, `provenance_resolvable.py` — both lints
  still present (QA-P2 §B.2 registered them; QA-P3 didn't touch).
- `runtime/provenance.py:102-133` envelope refusal on missing
  `source_uri` still in place (no P3 commit touched the file).
- P3 read path drops facts without `episode_id` **after** scoring but
  **before** ledger write — `recall.py:402` per QA-P3 §C.1 — so a
  provenance-broken fact never reaches the ledger or the events bus.
  Net effect: **R3 substrate is reinforced, not eroded**.

### D.2 R5 — idempotency edges (P2 slice not eroded by P3)

- `runtime/idempotency.py:134-136` — `_storage_key("{verb}:{key}")`
  per-verb namespacing intact.
- `idempotency.py:139-166` versioned envelope `{"version": 1, "body_hash":
  "...", "response": {...}}` intact (no P3 edits to the module).
- `idempotency_keys` table DDL unchanged through v3 (verified by
  table-state matrix in §B.5).
- P3 added `recall_id` keying which inhabits a **disjoint table** (§B.2)
  so it cannot collide with idempotency keys.

### D.3 R8 — ledger atomicity (newly opened by P3, internally consistent)

- `recall_ledger` is the first ledger surface the system ships; P3 lands
  it with `INSERT OR IGNORE` on the deterministic PK + diverged-payload
  corruption raise (`recall.py:383-389`, QA-P3 §C.7).
- The P3 implementation deliberately writes the ledger row **before**
  emitting events (QA-P3 §C.7 line cite) so a downstream event-bus
  failure does not strand un-ledgered events. The reverse failure mode
  (events emit but ledger write fails) raises and short-circuits the
  verb — no half-state visible to callers.
- 343/343 tests green at HEAD; health pass confirms the substrate slice
  is intact.

---

## §E Spec-doc coherence — contradictions surfaced by the three phases

### E.1 IMPL §2.3 paraphrase vs api §4.1 / scoring §4.1 (already filed in QA-P3 §F.1)

IMPL §2.3 exit-gate paraphrase says *"before any retriever runs"*; the
binding api §4.1 and scoring §4.1 wording is *"before any ranker is
consulted"*. Implementation honors the binding wording (`recall.py:747`
applies `filter_facts` post-retrieve, pre-RRF). **Doc paraphrase, not
code drift.** Carry-forward to §G as H-nit (P4 docs cleanup).

### E.2 IMPL §6.2 narrative-count typo (filed in GO-NO-GO §6.3 #2)

GO-NO-GO §6.3 already noted *"the narrative says '40/40 locked decisions';
the table enumerates 44 rows"*. Not opened or worsened by any of P1/P2/P3.
**No new finding.**

### E.3 No new contradictions surfaced

A targeted cross-doc sweep against the cross-phase contracts (B.1–B.7)
revealed **no other contradictions** between binding docs (api ↔
scoring ↔ composition ↔ state ↔ IMPL ↔ go-no-go) introduced by the three
phases.

---

## §F P4 readiness

### F.1 Concrete file list — all-new, no collision with P1/P2/P3

`ls src/lethe/runtime/` at HEAD confirms **no `consolidate/` directory
exists yet** — the entire P4 surface is greenfield within `runtime/`.
P3 imports nothing from `runtime/consolidate/` (verified by §G.1 of QA-P3
+ confirmed at G1 audit). Per IMPL §2.4 file list:

- `src/lethe/runtime/consolidate/__init__.py`
- `src/lethe/runtime/consolidate/scheduler.py` — 15 min default gate (deployment §4.1)
- `src/lethe/runtime/consolidate/loop.py` — six-phase canonical order (I-11)
- `src/lethe/runtime/consolidate/phases.py`
- `src/lethe/runtime/consolidate/extract.py` — extraction + **embedder seam (E1)**
- `src/lethe/runtime/consolidate/score.py` — wires the P3 `runtime/scoring/` lib at consolidate-time
- `src/lethe/runtime/consolidate/promote.py`
- `src/lethe/runtime/consolidate/demote.py`
- `src/lethe/runtime/consolidate/invalidate.py`
- `src/lethe/runtime/consolidate/contradiction.py` — gap-13 §3.1 log-dampened ε
- `src/lethe/runtime/consolidate/gravity.py` — MaM-style cascade-cost
- Modify: `src/lethe/runtime/events.py` — add `_PER_TYPE_REQUIRED` entries for `promote/demote/invalidate/consolidate_phase` (B.4 prediction)
- Tests: `tests/runtime/test_consolidate_phases.py`, `test_scoring_appendix_a.py`, `test_gravity.py`, `test_contradiction_epsilon.py`, `test_lock_heartbeat.py`

### F.2 Write-side embedder seam at `runtime/consolidate/extract.py` (E1)

Per Erratum E1 the embedder lands inside or alongside `extract.py` as
part of the dream-daemon async chain (composition §4.1 lines 4-8).
**Concrete proposed seam-file shape** (suggested for the P4 facilitator;
not binding):

| File | Purpose | Notes |
|---|---|---|
| `src/lethe/runtime/consolidate/extract.py` | Extraction over new episodes; **calls** the embedder for each new node/edge | Per IMPL §2.4 — also writes the extraction-confidence row to S2 `extraction_log` (P2 columns are ready) |
| `src/lethe/runtime/consolidate/embed.py` *(suggested split)* | Pure embedding orchestration: `embed_nodes(...)`, `embed_edges(...)`, `embed_episodes(...)` returning S3-shaped vectors keyed by the §B.5 embedding-key invariant (`CHECK ((node_id IS NOT NULL) + (edge_id IS NOT NULL) + (episode_id IS NOT NULL) = 1)` from `s3_vec/client.py`) | Splitting embed from extract makes the embedder model-injection seam isolatable for tests + DMR fixture rebuilds. Not strictly required by IMPL §2.4 (the doc folds them into `extract.py`), but matches the P3 split between `runtime/scoring/` lib and `api/recall.py` call site. |
| `src/lethe/runtime/consolidate/embedder_protocol.py` *(suggested)* | `Embedder` Protocol mirroring the P2 `LLMClassifier` Protocol pattern (`runtime/classifier/intent_classifier.py:115-132`); `NullEmbedder` raises `NotImplementedError` for production-by-default; tests inject a fake | Same locked-decision pattern as gap-12 §(g) row 2 ("host-runtime model via injectable callable; no SDK"). No `import sentence_transformers` / `import openai` in `src/lethe/`. |
| Existing reuse: `scripts/eval/fixtures/build_dmr_embeddings.py` | Fixture-build-time only; do NOT promote this to production import — its model + seed pin (`tests/fixtures/dmr_corpus/README.md`) is the D8 reproducibility anchor and should stay test-tree-bound | QA-P3 §C.5 cites zero `src/lethe/` hits — keep that posture |
| Existing consumer: `src/lethe/store/s3_vec/client.py` | Already has `bootstrap()` + `vec0` virtual table; embedder writes through this | No change required at P4; the embedder produces the vectors; `s3_vec.client` persists them |
| Existing consumer: `src/lethe/runtime/retrievers/semantic.py` | Reads S3 vectors at recall-time (P3) | E1 chain closes here: P4 writes vectors → P3 reads them. No retriever change required |

**Bridge to fixtures**: P4 should not change the `tests/fixtures/dmr_corpus/embeddings.json` shape — D8 + the DMR adapter (`scripts/eval/adapters/dmr.py`) are what proves the read pipeline still works while the embedder lands. The P4 health gate is "DMR sanity replay still passes when fixture vectors are deleted and re-built by the live embedder" (a stretch goal, not the gate).

### F.3 D5 plumbing for `recall_outcome` — the rough edge

D5 ("`recall_outcome` join-key plumbed at P3, emission deferred to P9")
is the seam P4+ inherits. State at HEAD:

- `events.py:EventType` already enumerates `recall_outcome` (§B.4 above).
- `_PER_TYPE_REQUIRED["recall_outcome"]` is **absent** — emission stays
  on the looser common-only check until P9 wires the shape.
- `recall_id` is the deterministic join key, written to
  `recall_ledger.recall_id` (PK) at P3.
- **Rough edge**: `recall_ledger` lacks a join index for the eventual
  `recall_outcome` ingest (e.g. an index on `(tenant_id, ts_recorded)`
  to support time-window aggregations). The migration docstring (§B.5)
  flags this as a P5+ ALTER TABLE; **P4 should not need to touch it**
  — but P4's facilitator should confirm during planning that no
  consolidate-time read pattern requires the index earlier.
- **No code rough edge for P4**: the consolidate loop does not (yet)
  consume `recall_outcome` events (those are P9 ingest into the utility
  ledger). P4's only event-bus interaction is **emission** of
  `consolidate_phase` events (one per phase × per consolidate run, I-11),
  which is the §B.4 one-line extension.

### F.4 Per-tenant lock seam (gap-01 §3.2 + gap-08 §3.4 → deployment §4.2)

Not yet plumbed; nothing in P1/P2/P3 forecloses. P4 lands:

- `consolidation_state` table columned (per-tenant lock token, heartbeat
  timestamp, last-run cursor) — drop-and-recreate safe (still stub at v3).
- Lock acquire / 30 s heartbeat / 60 s break logic in
  `runtime/consolidate/scheduler.py`.
- `lethe-admin lock` recovery path is stubbed at P4 and fully landed at
  P8 (per IMPL §2.4 exit gates).

### F.5 PPR wiring bridge (QA-P3 §F.2)

`recall.py::_score_one` currently feeds `connectedness_value = rrf_score
/ rrf_max` into `per_class.score()` as a proxy for the full HippoRAG PPR.
The PPR lib (`scoring/connectedness.py`) is shipped + tested at P3.
**P4 wires the proxy into the real PPR call site** once the live graph
backend exposes the personalization seed set (per IMPL §2.4 + QA-P3 §H.2).
This is the single-largest "wire-it-up" item P4 inherits.

---

## §G Carry-forward H-nits (across all three QA docs)

Phase-tagged disposition recommendations:

| ID | Source | Disposition | Notes |
|---|---|---|---|
| QA-P1 §H.1 | `_InMemoryGraphBackend.register_entity_type` tenant-blind | **P2-or-later docs/behavior fix** (still open at G1) | Smoke-only stub; not a production code path. Either document the cluster-wide-schema invariant in the `GraphBackend` Protocol docstring or drop the per-tenant loop. Non-blocking. |
| QA-P1 §H.2 / QA-P2 §H.2 | `SqliteLogWriter` opens fresh connection per call | **P4** (T2 transaction owner) | Becomes a real concern when P4 lands the T2 = (S2 flag write + S5 audit write) transaction — needs a shared-connection context manager. Not blocking before P4. |
| QA-P2 §H.1 | `force_skip_classifier` audit row not written on `escalate`/`drop`/`peer_route` branches | **P5** (audit-of-no-effect path) | Per QA-P2: rationale acceptable for P2 since only the accepted-write branch needs the audit row at v1 RBAC (P7 owns the broader audit posture). |
| QA-P3 §H.1 | IMPL §2.3 paraphrase wording ("before any retriever runs") | **P4 docs cleanup** | Re-align to api §4.1 / scoring §4.1 binding wording. Pure docs-fix. |
| QA-P3 §H.2 | PPR wiring into the recall verb | **P4+** (gated on live graph backend) | Lib shipped + tested; only the wiring is missing. See §F.5. |
| QA-P3 §H.3 | `_score_one` uses `valid_from` as `t_access` proxy | **P4+** (gated on utility ledger) | Recency-of-record approximates recency-of-access until utility events flow. |
| QA-P3 §H.4 | `preferences_prepend.build_envelope` first-overflow drop (not greedy first-fit) | **P9** (fairness packing) | Cosmetic; current behavior is deterministic and conforms to the §10 KB cap + recency ordering. |
| QA-P3 §H.5 | `recall.py` step-ordering (preferences fetched up-front) | **P5 docs** | Functionally equivalent to the api §2.1 step-10 ordering; source comment could note the divergence. |

**No embedder-shaped finding is filed (E1 binding).**

---

## §H Verdict

**APPROVE-WITH-NITS** — cross-phase coherence holds.

Justification:

- All seven cross-phase contracts (B.1–B.7) hold end-to-end at HEAD
  with line-cited evidence; no contract break detected.
- Risk register (§C) is honest — every "closed" entry is a substrate-level
  slice; standing risks R2/R3/R6 remain open per GO-NO-GO §6.2.
- Standing-risk regression check (§D) confirms R3, R5, R8 substrate
  slices are intact at HEAD; P3 reinforces R3 (drop-no-provenance facts
  before ledger) and opens R8 cleanly (deterministic-PK INSERT-OR-IGNORE
  with corruption-on-divergence raise).
- Spec-doc coherence (§E) surfaces only the IMPL §2.3 paraphrase issue
  already filed in QA-P3 §F.1; no new contradictions.
- P4 readiness (§F) is verified: greenfield `runtime/consolidate/`
  surface (no collision); concrete embedder-seam shape proposed (§F.2)
  honoring E1 + the Protocol-injection precedent from gap-12; D5 rough
  edge documented (§F.3); per-tenant lock seam is open (§F.4); PPR
  wiring bridge is the single-largest wire-up item P4 inherits (§F.5).
- Carry-forward H-nits (§G) are all non-blocking and tagged by phase
  for opportunistic pickup; none rise to REQUEST-CHANGES.
- One-shot health pass at HEAD: 343 pytest pass, ruff clean, mypy clean
  across 46 source files. Matches QA-P3 counters exactly — no regression
  between QA-P3 commit and the G1 audit point.

**Recommended next action**: facilitator authorizes the QA-G1.md commit
(per the binding `John Hain` author identity rule + Co-authored-by Copilot
trailer), then proceeds to P4 kickoff (`/clear` + `[[PLAN]] P4`).
