# QA-P4 — independent QA audit of the P4 drive

**Phase audited:** P4 (consolidate loop + write-side embedder seam + scoring tuning).
**Audit window:** `128181b^..02c4fb5` (9 commits, 41 files, +10343 / −131).
**HEAD at audit:** `02c4fb52d1c08ae27470a181372c09626ade25d5` on `origin/main`.
**Audit mode:** Read-only, facilitator-side. Mirrors `docs/QA-P3.md` + `docs/QA-G1.md` §F.1–§F.5 structure. No `src/`, `cli/`, `tests/`, or prior QA-P*/QA-G* doc was mutated. No commit was performed by the audit.
**Bound by:** Erratum E1 (write-side embedder is P4 scope; critique of Embedder Protocol design is permitted). **No QA-G2**: cross-phase coherence vs P1/P2/P3 is reserved for G2 at P6 per GO-NO-GO §7.

---

## §A. Scope

### §A.1. Commits audited

| # | SHA | Subject | Files | +ins / −del |
|---|-----|---------|-------|------|
| C1 | `2571a67` | feat(s2)(p4): migration v3→v4 — columnize `consolidation_state`, `promotion_flags`, `utility_events` | 4 | 940 / 49 |
| C2 | `51ca62f` | feat(events)(p4): per-type required fields + `validate()` branches for `promote`, `demote`, `invalidate`, `consolidate_phase` | 2 | 501 / 23 |
| C3 | `62bfe3c` | feat(consolidate)(p4): `Embedder` Protocol + `NullEmbedder` default | 3 | 366 / 0 |
| C4 | `8b4916f` | feat(consolidate)(p4): pure-function scoring lib (score + gravity + contradiction) | 8 | 1087 / 21 |
| C5 | `68f78fa` | feat(consolidate)(p4): extract + embed write path with cross-store T2 atomicity | 9 | 1519 / 20 |
| C6 | `3dff613` | feat(consolidate)(p4): phase impls (`promote` + `demote` + `invalidate`) + reconciler | 9 | 2271 / 12 |
| C7 | `ca670d0` | feat(consolidate)(p4): scheduler + loop + phases orchestration (15-min gate, per-tenant lock, 6-phase canonical order, I-11) | 8 | 2260 / 2 |
| C8 | `2e560ab` | feat(recall)(p4): wire HippoRAG PPR into `_score_one` via `S1Client.adjacency_2hop` | 3 | 1089 / 26 |
| C9 | `02c4fb5` | feat(scoring)(p4): Appendix A worked-example replay + close residual-unknown #6 (`procedure` type_priority = 0.55) | 5 | 352 / 20 |
| **Σ** | — | — | **41** | **10343 / 131** |

Per-commit stats verified via `git show --stat <SHA>` and `git diff --stat 128181b..02c4fb5 -- <paths>`. Commit graph is linear; every commit is buildable, gated, and tested (D6 — "buildable-ordered 9-commit split" honored end-to-end).

### §A.2. Toolchain footer

- `uv 0.10.0 (4d72d8d6f 2025-08-26)`
- `Python 3.11.14`
- `Darwin 15.7.4` arm64
- `uv sync` reported `Audited 44 packages` (no drift; no new dep added — D11 holds; **gap-12 §(g) row 2 audit clean**).

### §A.3. Independent gate re-run at HEAD `02c4fb5`

All commands run with `LETHE_HOME=$(mktemp -d -t lethe-qa-p4.XXXXXX)`; CWD never contained a `.lethe/` directory before or after the audit (`~/.lethe` does not exist).

| Gate | Command | Result |
|------|---------|--------|
| Full pytest | `uv run pytest tests/ -q` | **632 passed, 1 warning** in 13.23s — warning is `PydanticDeprecatedSince20` in `graphiti_core/.../search_interface.py:22` (vendored dep; inherited from P1+; not P4-origin) |
| mypy --strict | `uv run mypy --strict src/` | `Success: no issues found in 61 source files` |
| ruff check | `uv run ruff check src/ tests/ cli/ scripts/` | `All checks passed!` |
| ruff format --check | `uv run ruff format --check src/ tests/` | **27 files would be reformatted** — see §G.1 for the inheritance-vs-introduction analysis (all 27 are pre-existing drift from P1/P2/P3; P4 introduced 0 new drift) |
| Targeted P4 tests | `uv run pytest tests/runtime/test_consolidate_phases.py tests/runtime/test_consolidate_loop.py tests/runtime/test_consolidate_extract_embedder.py tests/runtime/test_consolidate_score.py tests/runtime/test_embedder_protocol.py tests/runtime/test_scoring_appendix_a.py tests/runtime/test_gravity.py tests/runtime/test_contradiction_epsilon.py tests/runtime/test_lock_heartbeat.py tests/runtime/test_ppr_wiring.py tests/runtime/test_bitemporal_p4.py tests/store/test_migrations_v3_to_v4.py tests/runtime/test_events.py -q` | **325 passed** in 11.07s |
| DMR sanity replay | `uv run pytest tests/eval/test_dmr_adapter.py -v` | **6 passed** in 2.52s — `recall@5 = 0.720`, **bit-identical to C7 baseline** (recorded in `tests/fixtures/dmr_corpus/README.md:98`). This proves C8's PPR wire-in did not perturb the read path when the optional `s1_client` is `None` (proxy fallback path) |
| Embedder SDK leak | `grep -rn "sentence_transformers\|^import openai\|^from openai" src/` | Only docstring match at `embedder_protocol.py:43` ("no `sentence_transformers`, no `openai`"); zero production imports |
| SCNS leak | `grep -rn "import scns\|from scns\|scns_" src/ cli/` | 0 hits |

**Rejected approach (recorded for cadence audit):** Per-commit `git stash`+`git checkout`+rerun was rejected upstream in the [[PLAN]] (`§A.3` rationale: "too brittle"). The chosen approach — running every C1-C9 targeted test file at HEAD — proves the new tests pass alongside the rest of the suite, not against the intermediate trees. The intermediate trees were vouched for by §m / §n READY-FOR-COMMIT cycles and by the facilitator's `AUTHORIZE COMMIT N` pre-flights; QA-P4 inherits those gates.

---

## §B. Locked decisions D1-D11 reaffirmation

Each decision from facilitator plan-of-record §e (lines 128-146) is reaffirmed below with one-line code citation. **Open** = decision not yet realized; **Closed** = decision realized in P4 tree; **Modified** = realized with a documented amendment.

| # | Decision | Status | Citation |
|---|----------|--------|----------|
| D1 | Scheduled 15-min gate + per-tenant lock (token + 30s heartbeat / 60s break) | **Closed** | `runtime/consolidate/scheduler.py:39-44` defines `GATE_INTERVAL_SECONDS=900`, `HEARTBEAT_INTERVAL_SECONDS=30`, `LOCK_BREAK_SECONDS=60`; `acquire_lock`/`heartbeat`/`clear_lock`/`mark_success_and_release` in same module |
| D2 | No `consolidate` API verb at P4 (P6 OOS) | **Closed** | `src/lethe/api/__init__.py` exports only `remember`/`recall`; no `consolidate` verb shipped. `run_one_consolidate()` is the loop entry, not a verb |
| D3 | DAG `derived_from` (multi-parent provenance) | **Closed (infra only)** | `runtime/events.py:118+` adds `derived_from: list[str]` to `_PER_TYPE_REQUIRED["promote"]`; merge/derive step itself is gap-06 P9 (no P4 caller populates it from real fact merging — see §E.6 and §G.2) |
| D4 | `consolidation_state` lock seam via `BEGIN IMMEDIATE` | **Closed** | `runtime/consolidate/scheduler.py` uses parameterized `BEGIN IMMEDIATE` in `acquire_lock()`; `consolidation_state` table created in `m4_consolidate_v4` (`store/s2_meta/migrations.py:77-99`) |
| D5 | Real PPR wiring at `_score_one` (closes QA-P3 §F.2/H.2) | **Closed at P4 C8** | `api/recall.py:584-622` calls `compute_connectedness(adj, fact_id=...)` against `s1_client.adjacency_2hop(...)` when `s1_client` is supplied; proxy fallback `rrf_score/rrf_max` retained for backward-compat |
| D6 | Buildable-ordered 9-commit split | **Closed** | Per §A.1 — every commit's test set runs green in isolation at its tip per dev-side §m/§n attestations; the 9-commit linear chain is intact in `git log --oneline 128181b..02c4fb5` |
| D7 | QA-P4 at P4 close; no QA-G2 | **Closed by this document** | This audit produces `docs/QA-P4.md`; the GO-NO-GO §7 condition "QA-G2 triggers after P6" is honored (no cross-phase audit performed) |
| D8 | Single v3→v4 migration (drop-and-recreate stubs) | **Closed at P4 C1** | `store/s2_meta/migrations.py:_m4_consolidate_v4` performs `DROP TABLE IF EXISTS consolidation_state / promotion_flags / utility_events` then `CREATE TABLE` with full columnar shape; round-trip test in `tests/store/test_migrations_v3_to_v4.py` |
| D9 | Embedder split into `extract.py` + `embed.py` + `embedder_protocol.py` | **Closed at P4 C3+C5** | Three modules exist in `src/lethe/runtime/consolidate/` (`embedder_protocol.py` 144 lines; `extract.py` 247 lines; `embed.py` 312 lines) |
| D10 | DMR fixtures stay checked-in; stretch goal regenerate via live embedder | **Closed (stretch goal NOT taken at P4)** | `tests/fixtures/dmr_corpus/{episodes.jsonl,embeddings.json}` remain `sha256-pseudo-v1`; `tests/fixtures/dmr_corpus/README.md:50-63` documents the rationale for not pulling `sentence-transformers` in (matches D11 + Erratum E1) |
| D11 | No new dep `numpy` | **Closed** | `pyproject.toml` Σ inspection: `uv sync` reports `Audited 44 packages`. No `numpy` import in `src/` (audited via `grep -rn "^import numpy\|^from numpy" src/` — 0 hits) |

---

## §C. Standing risks R1-R8 — status at P4 close

Each risk is mapped to plan-of-record §g (lines 172-196). Status: **Closed** (no further work), **Standing** (mitigation in place; not yet fully eliminated), **Open** (deferred to a later phase by design).

| # | Risk | P4 status | Closure / mitigation |
|---|------|-----------|----------------------|
| R1 | Bi-temporal filter — substrate slice | **Closed at P3** (read path); P4 adds write-side ordering: S1 `set_fact_valid_to` BEFORE S2/S5 tx (`runtime/consolidate/demote.py:91-115`, `invalidate.py:90-128`) so reconciler can recover orphans (`runtime/consolidate/_reconciler.py:61-149`) |
| R2 | Cross-store T2 atomicity | **Closed at P4 C5** | `store/shared_conn.py` provides `shared_store_connection()` context — S2 primary + ATTACH S3 (alias `s3`) with `sqlite_vec` extension loaded under enable/disable guard (A12). Caller (every phase fn + reconciler) owns `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` |
| R3 | Provenance loss (DAG `derived_from`) | **Standing → CLOSED for infra at P4 C6**; real merge consumers are P9 | `events.py:118+` requires `derived_from: list[str]` on `promote` envelopes; `consolidate/promote.py:71-93` carries the field through. Caller currently passes an empty list because no fact-merge code path exists at P4 (gap-06) — schema and validator are ready |
| R4 | Tenant isolation in consolidation_state | **Closed** | `consolidation_state` has `tenant_id` as part of its PK (`migrations.py:_m4_consolidate_v4`); `acquire_lock(tenant_id=...)` keys all lock writes; cross-tenant adjacency-mismatch raises `RecallValidationError` (`api/recall.py:712-719`) |
| R5 | Recall returns wrong/hallucinated facts | **Standing — covered by mechanism**, not eliminated | `gravity_mult = max(1.0, 1 + 0.5·gravity_value)` floor (`runtime/scoring/gravity.py`); `eps_effective = ε·(1+ln(1+contradiction_count))` log-dampened (`scoring/contradiction.py`); demote/invalidate phases tested in `test_consolidate_phases.py`. Final closure is gap-13 contradiction-resolution at P9 |
| R6 | Connectedness term meaningless without PPR | **Closed at P4 C8** | `compute_connectedness` is now called on live S1 2-hop adjacency when `s1_client` is provided; proxy fallback retained for no-graph callers and is bit-exact-equivalent to the C7 baseline (DMR `recall@5 = 0.720`) |
| R7 | Classifier accuracy | **Open by design — post-P9** (n/a at P4) | `runtime/scoring/per_class.py` ships a static `TYPE_PRIORITY` table; learned-classifier replacement is post-P9 per plan-of-record §g |
| R8 | Idempotency / replay invariant | **Closed at P4 (lock-based)**; read-path slice was closed at P3 | Per-tenant lock (D1) prevents concurrent consolidate runs; reconciler is idempotent via `tier='backfilled'` set membership (`_reconciler.py:99-149` amendment A2). Crash-atomicity across two WAL-journaled files is **NOT** guaranteed (`shared_conn.py:82` amendment A9 caveat); full crash recovery is P8 |

---

## §D. Carry-forward H-nits — status

Each H-nit filed in earlier QA cycles is tracked through P4 close.

| H-nit | Origin | P4 status | Citation |
|-------|--------|-----------|----------|
| `SqliteLogWriter` shared-connection seam | QA-P1 §H.2, QA-P2 §H.2 | **CLOSED at P4 C6** | `store/s5_log/writer.py:65-93` — new `append_with_conn(entry, *, conn)` method participates in the caller's open tx. SQL is schema-qualified as `main.{S5_LOG_TABLE_NAME}` (A4 audit) so an attached alias cannot shadow the write. Z-suffix ISO format preserved (A11) |
| IMPL §2.3 paraphrase wording | QA-P3 §F.1, QA-G1 §E.1 | **STILL OPEN** | Carry to P5 docs cleanup; no impact on P4 close |
| PPR wiring in `recall._score_one` | QA-P3 §F.2, §H.2 | **CLOSED at P4 C8** | `api/recall.py:584-622` calls `compute_connectedness(adj, fact_id=...)` on live `S1Client.adjacency_2hop` |
| Step 6 post-rerank (`w_intent`/`w_utility`) | QA-P3 §F.3 | **STILL P5+ deferred** | See §G.3 below; `tests/runtime/test_scoring_appendix_a.py:89-111` defines a test-local `_appendix_a_rerank()` helper. Plan §g.192 explicitly defers |
| `valid_from` as `t_access` proxy | QA-P3 §H.3 | **STILL P5+** | No `t_access` column added at P4 (D8 v3→v4 migration didn't touch `s1_facts`); recall still uses `valid_from` as proxy |
| `InMemoryGraphBackend` tenant-blind | QA-P1 §H.1 | **STILL OPEN** | `store/s1_graph/client.py:_InMemoryGraphBackend` remains tenant-blind; production backend (`graphiti_core`) is tenant-keyed |
| `force_skip_classifier` audit row | QA-P2 §H.1 | **STILL P5** | No audit-row emission for the dev override at P4 |
| `preferences_prepend` first-overflow | QA-P3 §H.4 | **STILL P9** | Preferences-aware step does not land until P9 + composition rework |
| `recall.py` step-ordering docs | QA-P3 §H.5 | **STILL P5 docs** | Step numbering in `api/recall.py` docstring still trails the §2.3 spec wording |

---

## §E. Per-commit audits

Each subsection inspects one commit at depth; line cites are against the file at HEAD `02c4fb5` unless otherwise noted.

### §E.1. C1 — `feat(s2)(p4): migration v3→v4` — `2571a67`

- **Migration shape** (`store/s2_meta/migrations.py:77-99`): `_m4_consolidate_v4` runs `DROP TABLE IF EXISTS consolidation_state; CREATE TABLE consolidation_state(...)` for all three tables under one `BEGIN`. D8 drop-and-recreate posture (the three tables shipped as stubs at P3 had no production callers — verified by `git log --oneline 128181b -- src/lethe/store/s2_meta/`).
- **Columnar shape**: `consolidation_state` keys on `(tenant_id, lock_token, acquired_at, last_run_at, last_heartbeat_at)` — supports both D1 (per-tenant lock) and the deployment §5.5 `consolidation_stalled` alarm (the `clear_lock` vs `mark_success_and_release` split honors A1). `promotion_flags` adds `(fact_id, tenant_id, tier, classifier_conf, ts_recorded)`. `utility_events` adds `(fact_id, tenant_id, event_kind, value, ts_recorded)`.
- **Round-trip test** (`tests/store/test_migrations_v3_to_v4.py`): 28K of test code; verifies v3 fixture + v3→v4 application + idempotent re-apply at v4. Full suite green (`uv run pytest tests/store/test_migrations_v3_to_v4.py` passes inside the §A.3 targeted run).
- **No `s1_facts` schema change**: D8 migrates only s2_meta tables; the `t_access` column nit (QA-P3 §H.3) remains open by design.
- **Verdict:** Clean. No findings.

### §E.2. C2 — `feat(events)(p4): per-type required fields + validate() branches` — `51ca62f`

- **EventType set**: `runtime/events.py:82` `EventType = Literal[...]` enumerates all 7 types from P1 (`remember`, `recall`, `recall_outcome`, `promote`, `demote`, `invalidate`, `consolidate_phase`). C2 does **not** extend the Literal; it only fills the per-type required-fields table.
- **`_COMMON_REQUIRED`** (`events.py:105`) is unchanged from P1 (`event_id`, `event_type`, `tenant_id`, `actor_id`, `ts_recorded`, `schema_version`). **`_PER_TYPE_REQUIRED`** (`events.py:118+`) is extended for the four new types:
  - `promote`: adds `fact_id`, `derived_from`, `decision`, `reasons`, `consolidation_run_id`, `model_version`, `weights_version`
  - `demote`: adds `fact_id`, `decision`, `reasons`, `consolidation_run_id`, `model_version`, `weights_version`
  - `invalidate`: adds `fact_id`, `reason`, `consolidation_run_id`, `valid_to`
  - `consolidate_phase`: adds `phase`, `run_id`, `tenant_id_for_phase` (sentinel-free), `started_at`, `finished_at`, `status`
- **`validate()` branches** (`events.py:175-242`): unified entry point routes by `event_type` to per-type checks. Membership of `event_type` checked against `_VALID_EVENT_TYPES` frozenset (`events.py:92`). On invalid type → `EventValidationError`. On missing common keys → `EventValidationError`. Per-type missing keys → `EventValidationError`.
- **Backward compat**: P1-shipped `remember` event envelope is untouched (verified by `git diff 128181b..HEAD -- src/lethe/runtime/events.py` — the `remember`-only `_REMEMBER_REQUIRED` block at `events.py:118-124` retains exactly the P1 shape: `fact_ids`, `provenance`, `contamination_protected`).
- **Verdict:** Clean. The "EventType non-refactor" §(f) literal gate flags docstring/format-line removals as if they were code removals; this is a gate-precision issue not a finding (§G.5 informational).

### §E.3. C3 — `feat(consolidate)(p4): Embedder Protocol + NullEmbedder` — `62bfe3c`

- **Protocol** (`runtime/consolidate/embedder_protocol.py:24-100`): three methods — `embed_episodes(...)`, `embed_nodes(...)`, `embed_edges(...)` — all return `list[Sequence[float]]`. Type-only surface; no SDK import. `Protocol` not `ABC` so structural subtyping is permitted (D9 split).
- **NullEmbedder** (`embedder_protocol.py:102-144`): raises `NotImplementedError` on every call with a fail-loud message ("NullEmbedder must be replaced before calling consolidate"). Default `Embedder` used at module wiring sites so tests can override; production startup will pick the production embedder once one exists. Fail-loud posture matches the Erratum E1 framing (no silent no-op).
- **SDK audit at HEAD**: `grep -rn "sentence_transformers\|openai" src/lethe/` — only the docstring at `embedder_protocol.py:43` ("no `sentence_transformers`, no `openai`") and binary `.pyc` cache. Zero production imports.
- **Strict typing**: `mypy --strict` clean against 61 source files (§A.3).
- **Verdict:** Clean. No findings.

### §E.4. C4 — `feat(consolidate)(p4): pure-function scoring lib` — `8b4916f`

- **`score.py`** (`runtime/consolidate/score.py`): `score_fact(input: ConsolidateScoreInput, *, t_now: datetime) -> float` is a pure function over a frozen dataclass. Composes per-class additive sub-score + `eps_effective` term + `gravity_mult` multiplier per scoring §3-§5.5.
- **`gravity.py`** (`runtime/consolidate/gravity.py` re-export of `lethe.runtime.scoring.gravity`): `gravity_mult(gravity_value) = max(1.0, 1 + 0.5 * gravity_value)`. **This is a MULTIPLIER, not a 6th additive** — confirmed in C9's T3 test (`test_scoring_appendix_a.py:166-198` validates `s = mult · pre_grav` with `s_no_grav` sub-assertion). Plan §i.227 gravity-floor-edge edge case (negative `pre_grav` × `mult > 1.0` = more negative) is locked by T3.
- **`contradiction.py`** (`runtime/consolidate/contradiction.py`): `eps_effective(eps, contradiction_count) = eps · (1 + ln(1 + contradiction_count))`. **Log-dampened**, not linear (T4: `eps_effective(0.5, 1) = 0.847` matches `docs/05-scoring-design.md §A.1:557`).
- **`contradiction_indicator`**: 1.0 if there exists any active contradicting fact (valid_to is NULL after a prior fact's invalidation), else 0.0. Pure indicator semantics — separates the presence flag from the count-driven `eps_effective` amplifier.
- **Verdict:** Clean. Pure-function discipline allows the consolidate score to be replayed (T1-T8 do exactly this against doc-anchored constants).

### §E.5. C5 — `feat(consolidate)(p4): extract+embed write path with cross-store T2 atomicity` — `68f78fa`

- **T2 atomicity seam** (`store/shared_conn.py:1-101`): `shared_store_connection(tenant_id) -> sqlite3.Connection` is a context manager. Opens S2 connection, executes `ATTACH DATABASE ? AS s3` with the S3 sqlite file path (parameter-bound — amendment A7), loads `sqlite_vec` under `enable_load_extension(True)` / `False` guard (A12), then applies WAL + NORMAL synchronous pragmas to both sides (A8). Caller owns `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`. **Closes QA-P1 §H.2 + QA-P2 §H.2 carry-forward shared-conn seam** (used by C6 phase impls via `s5_log/writer.append_with_conn`).
- **Crash-atomicity caveat** (`shared_conn.py:82` A9): NOT guaranteed across two WAL-journaled files. Full crash recovery is P8. Explicitly documented in module docstring.
- **`extract.py`** (`runtime/consolidate/extract.py:1-247`): `run_extract(tenant_id, *, since_cursor) -> tuple[list[EpisodeRecord], Cursor]`. Reads S1 `episodes_since(...)`. **Composite cursor** is `f"{ts_recorded}\t{episode_id}"` (A5) so ties on `ts_recorded` don't permanently skip an episode. Cursor returned from the LAST sorted episode (A10), not `max()`.
- **`embed.py`** (`runtime/consolidate/embed.py:1-312`): `embed_episodes(...)` is fully implemented. `embed_nodes(...)` / `embed_edges(...)` raise `NotImplementedError` on any non-empty input (empty-no-op only). Real bodies wire at P9 with gap-06 fact extraction. Vector dim validated against `S3Config.dim` before persistence.
- **Failure-mid-commit rollback** (covered in `tests/runtime/test_consolidate_extract_embedder.py`): when `embed_episodes` raises mid-way, the shared-conn context manager triggers ROLLBACK so neither S2 nor S3 sees the write.
- **Verdict:** Clean. T2 closure is the major P4 gate this commit owns.

### §E.6. C6 — `feat(consolidate)(p4): phase impls + reconciler` — `3dff613`

- **`promote.py`** (`runtime/consolidate/promote.py`): emits `promote` event per scoring §8.4 (decision ∈ `{promote, retain, reject}`; reasons enumerated). `derived_from` carried through but empty at P4 (R3 closure — infra-only; gap-06 P9 supplies real derivation).
- **`demote.py`** (`runtime/consolidate/demote.py:91-115`): **S1-first ordering** — writes `s1_facts.valid_to` BEFORE the S2+S5 tx so a partial mid-tx failure leaves an S1 orphan that the next reconciler run recovers. Emits `demote` event (decision ∈ `{demote, retain}`; reasons enumerated).
- **`invalidate.py`** (`runtime/consolidate/invalidate.py:90-128`): same S1-first pattern. Sets `gravity_mult` semantic to 0 (i.e., the recall path effectively zeros the score when valid_to is closed — verified in `tests/runtime/test_bitemporal_p4.py`). Per A3 it does NOT touch `utility_events` — the freeze is a **write-side defense** in the utility-event writer for FUTURE events (when `ts_recorded > valid_to` on an invalidated fact).
- **`_reconciler.py`** (`runtime/consolidate/_reconciler.py:61-149`): scans S1 for facts with `valid_to NOT NULL` that lack a corresponding S2 `promotion_flags` entry; back-fills with `tier='backfilled'`. **Idempotent via set-membership on `tier='backfilled'`** in covered set (A2). Runs in its own tx via `shared_store_connection` (A7).
- **`PhaseResult`** (`_reconciler.py:13-50`): frozen dataclass — `(phase: str, facts_processed: int, events_emitted: int, errors: list[str])` — every phase function returns this shape.
- **Carry-forward closures**: `s5_log/writer.append_with_conn` lands HERE (commit C6); previously every QA cycle since P1 had this as an open H-nit. The schema-qualified `main.{table}` SQL prevents an attached alias from shadowing the write (A4).
- **Verdict:** Clean. R2 + R3 + R8 closures land in this commit. Promote/demote/invalidate ARE called from this commit's tests (`tests/runtime/test_consolidate_phases.py`) — the loop wire-in is C7's scope; see §E.7 + §G.2.

### §E.7. C7 — `feat(consolidate)(p4): scheduler + loop + phases orchestration` — `ca670d0`

- **Scheduler** (`runtime/consolidate/scheduler.py`): five primitives wired —
  - `acquire_lock(tenant_id, *, token, conn) -> bool` — UPDATE `consolidation_state` SET lock_token=? WHERE token IS NULL OR last_heartbeat_at < now - 60s, RETURNING 1. Pre-UPDATE SELECT captures `prior_token` for S5 audit (A6).
  - `heartbeat(tenant_id, *, token, conn)` — captures fresh `datetime.now(UTC)` INSIDE the function (A2) so a stale call site cannot stamp old timestamps.
  - `clear_lock(tenant_id, *, token, conn)` — failure paths; does NOT advance `last_run_at` — avoids masking the deployment §5.5 `consolidation_stalled` alarm (A1 split).
  - `mark_success_and_release(tenant_id, *, token, conn)` — happy path; DOES advance `last_run_at`.
  - `force_clear_lock(tenant_id, *, conn)` — break-glass for tooling; emits an audit row.
  - `should_run(tenant_id, *, now, conn) -> bool` — 15-minute gate check against `last_run_at`.
- **OperationalError normalization** (A5): SQLite `OperationalError("database is locked")` is translated to `LockAcquisitionFailed(reason="busy_timeout")` so callers see one error type, not a SQLite-leak.
- **Loop** (`runtime/consolidate/loop.py:429`): `run_one_consolidate(tenant_id, *, ...) -> ConsolidateRunResult` is THE public entry point. Acquires lock → emits 6 `consolidate_phase` events in `PHASE_DISPATCH` order → calls one phase adapter per slot → on success: mark_success_and_release; on failure: clear_lock + propagate.
- **Phase dispatch** (`runtime/consolidate/phases.py:1-189`): `PHASE_DISPATCH = ("extract", "score", "promote", "demote", "consolidate", "invalidate")` — canonical I-11 order. **All six `consolidate_phase` envelopes fire in canonical order** even when the body is a no-op — this satisfies the IMPL §2.4 exit gate "6 events fire in canonical order on a synthetic tenant".
- **Adapter bodies** (`phases.py:16-43`, B-7/B-8/B-10): only `_extract_phase` calls the real `run_extract()`. The other five (score / promote / demote / consolidate / invalidate) return `_empty_result()` — **intentional P4 posture**. Promote/demote/invalidate phase **functions** (`runtime/consolidate/promote.py` etc.) exist and are tested in C6 isolation, but the loop is NOT wired to call them because the fact source is gap-06 P9. This is documented in the phases.py module docstring. See §G.2 for P5 readiness implication.
- **In-phase heartbeat** (A9 carry-forward): OUT OF SCOPE at C7 because P4 phases complete in sub-second on synthetic data. P9 phases may exceed `LOCK_BREAK_SECONDS=60` and will need in-phase heartbeat.
- **Tests**: `tests/runtime/test_consolidate_loop.py` (23K) + `tests/runtime/test_lock_heartbeat.py` (18K). Per stored-memory facts about C7's mypy gate and module-attribute monkey-patch pattern (`monkeypatch.setattr("pkg.mod.imported_name", spy)` not `m.imported_name = spy  # type: ignore`), both files conform.
- **Verdict:** Clean against the C7 scope. §G.2 flags the no-op-adapter posture as a P5 readiness item — not a P4 finding.

### §E.8. C8 — `feat(recall)(p4): wire HippoRAG PPR into _score_one` — `2e560ab`

- **Wiring site** (`api/recall.py:584-622`): `_score_one(fact_id, *, rrf_score, rrf_max, s1_client, tenant_id, ...) -> float` — when `s1_client` is supplied AND its `tenant_id` matches the request, calls `adj = s1_client.adjacency_2hop(fact_id=fact_id, tenant_id=tenant_id)` then `connectedness_value = compute_connectedness(adj, fact_id=fact_id)`. **Real connectedness, not proxy.**
- **Proxy fallback** (`api/recall.py:594-602`): when `s1_client` is `None`, uses `connectedness_value = rrf_score / rrf_max if rrf_max > 0 else 0.0`. Bit-identical to the C7 baseline because the DMR test (`tests/eval/test_dmr_adapter.py`) wires `s1_client=None` for the sanity replay; `recall@5 = 0.720` matches `tests/fixtures/dmr_corpus/README.md:98` annotation **"C7→C8 bit-identical"**.
- **Belt-and-braces clamp** (`api/recall.py:609`): `max(0.0, min(1.0, connectedness_value))` — defends against connectedness math drifting outside [0,1] in future kernel changes. Static analysis says current `compute_connectedness` cannot exceed [0,1] but the clamp is cheap insurance.
- **Tenant-mismatch validation** (`api/recall.py:712-719`): if `s1_client.tenant_id != request.tenant_id`, raises `RecallValidationError` — prevents cross-tenant adjacency leakage (A3).
- **Deep-copy via comprehension** (`api/recall.py:702`): adjacency snapshot used inside `_score_one` is built via list comprehension over the iterator — defends against the iterator being exhausted on second use.
- **Determinism narrowing** (module docstring, `api/recall.py:1-92`): documents that `response_envelope` is a function of `(request, ts_recorded, S1 adjacency at call time)`. Replay against a mutated graph WILL surface as `RecallLedgerCorruption`. Snapshot/replay machinery is a P5+ erratum.
- **Two TODOs** (`api/recall.py:619-625`): (a) P7 S1Outage absorber wrap so a momentary S1 unavailability doesn't poison every score; (b) P-later batch `adjacency_2hop` into one backend call (currently one round-trip per hit).
- **DMR sanity replay**: `tests/eval/test_dmr_adapter.py::test_dmr_sanity_replay_meets_floor` PASSED in §A.3 (`recall@5 = 0.720`).
- **Verdict:** Clean. R6 + D5 + QA-P3 §F.2/H.2 carry-forward all close in this commit.

### §E.9. C9 — `feat(scoring)(p4): Appendix A worked-example replay` — `02c4fb5`

- **Test file** (`tests/runtime/test_scoring_appendix_a.py:1-332`): nine test functions (T1-T8 plus T6b) at `±1e-3` tolerance against `docs/05-scoring-design.md §A.1-§A.2` constants.
  - T1: `score(f_pref) = 0.522` (preference, β=0, `gravity_mult=1.0`)
  - T2: `score(f_fact) = 0.397` (episodic, β=0.3 active)
  - T3: `score(f_proc) = -0.566` (procedure, strong contradiction, `gravity_mult=1.25`). Includes a sub-assertion: `s_no_grav = -0.453` and `s / s_no_grav == 1.25` — isolates multiplier from additive (regression in either narrows quickly). **Locks plan §i.227 gravity-floor-edge edge case.**
  - T4: `eps_effective(eps=0.50, count=1) = 0.847`
  - T5: RRF combine over sem/lex/graph → `(0.0489, 0.0479, 0.0454)` for `(f_pref, f_fact, f_proc)`
  - T6: rerank values via test-local `_appendix_a_rerank()` helper → `(0.0556, 0.0498, 0.0454)`
  - T6b: bonus-factor isolation (`rrf=1.0` → bonus alone): `(1.138, 1.041, 1.000)`
  - T7: top-1 ordering after rerank → `[f_pref, f_fact, f_proc]`
  - T8: `TYPE_PRIORITY["procedure"] == 0.55` and `type_priority("procedure") == 0.55` — **closes residual-unknown #6**.
- **`per_class.py` change**: `runtime/scoring/per_class.py:75-87` adds `"procedure": 0.55` to the `TYPE_PRIORITY` dict; previously fell back to `DEFAULT_TYPE_PRIORITY = 0.30`. Without this change, T3 (gravity-floor edge) would compute ≈ −0.629, outside the ±1e-3 budget. T8 isolates this table entry from T3's composed assertion.
- **`_appendix_a_rerank()` helper** (`test_scoring_appendix_a.py:89-111`): test-local private function implementing `rrf · (1 + w_intent · intent_match · classifier_conf)`. **NOT called from production `recall()` at HEAD.** This is the §G.3 / QA-P3 §F.3 carry-forward — the gate IMPL §2.4 "Appendix A worked example replays through both surfaces (consolidate + recall)" is satisfied on the consolidate side and uses a test-local stand-in on the recall side. Plan §g.192 documents the deferral.
- **`rrf_combine`** (T5): uses the production `lethe.runtime.scoring.rrf.rrf_combine` (not a re-implementation), so the assertion locks the live formula.
- **`_PER_TYPE_REQUIRED["consolidate_phase"]`** unchanged in C9 (C2 already enumerated the per-type fields).
- **Verdict:** Clean against the C9 scope. §G.3 carries the recall-surface rerank wire-in forward to P5+.

---

## §F. P5 readiness

### §F.1. Entry preconditions for P5

- All P4 gates green at HEAD `02c4fb5` (§A.3).
- `consolidate` package public surface fully exported (`runtime/consolidate/__init__.py:80-150`). P5 may import `run_one_consolidate`, the embedder Protocol, the per-phase functions, and all scoring primitives from one location.
- v3→v4 migration applied; `consolidation_state` / `promotion_flags` / `utility_events` are real tables (D8).
- T2 atomicity seam present (`store/shared_conn.py`) — P5 can write more multi-store transactions safely.

### §F.2. Deferred items the P5 owner picks up

1. **A.2 rerank wire-in into `recall()`** — `w_intent · intent_match · classifier_conf` multiplicative bonus + `w_utility · utility_value` additive. Currently lives only in `tests/runtime/test_scoring_appendix_a.py:_appendix_a_rerank`. Plan §g.192. See §G.3.
2. **Loop body adapters for promote/demote/consolidate/invalidate** — five of six C7 adapters are `_empty_result()` no-ops by design. Real wire-in is blocked on gap-06 (P9 fact extraction) but the **adapter** for each phase can be wired to call the corresponding C6 phase function `runtime/consolidate/{promote,demote,invalidate}.py` as soon as a fact source exists. See §G.2.
3. **DMR fixture regen via live embedder** (D10 stretch goal) — `tests/fixtures/dmr_corpus/README.md:101-114` documents the regeneration script. Stretch goal NOT taken at P4.
4. **`_generate_uuidv7` extraction** — 7 copies across `api/` and `runtime/consolidate/`. Documented TODOs in 5 of 7. See §G.4.
5. **Format drift cleanup** — 27 inherited-drifted files at HEAD (§G.1). Recommend opening P5 with a single docs-format commit (`uv run ruff format src/ tests/`).
6. **Step-ordering paraphrase in `recall.py`** (QA-P3 §F.1 / QA-G1 §E.1 carry-forward).
7. **`force_skip_classifier` audit row** (QA-P2 §H.1 carry-forward).
8. **`valid_from` → `t_access`** column at the P5 migration boundary (QA-P3 §H.3 carry-forward).

### §F.3. Standing risks for P5

- R5 (recall returns hallucinated facts) — final closure at gap-13 P9.
- R7 (classifier accuracy) — n/a until learned classifier replaces `TYPE_PRIORITY` post-P9.
- R8 cross-WAL crash atomicity — full closure at P8.

### §F.4. Binding docs for P5 entry

- `docs/02-synthesis.md`, `docs/03-composition-design.md` §3 + §4.4, `docs/05-scoring-design.md` §3-§5.5 + Appendix A + §6 demote-promote, `docs/06-api-design.md` §2, `docs/07-migration-design.md` §3-§5, `docs/08-deployment-design.md` §4.1-§4.2 + §5.5, `docs/04-eval-plan.md` §5.7.
- `docs/IMPLEMENTATION-followups.md` Erratum E1 — write-side embedder closure narrative (now realized at P4 C5 — IMPL-followups can be amended).
- This document (`docs/QA-P4.md`) — §F.2 + §G are the P5 owner's pickup list.

---

## §G. New H-nits filed during this audit

### §G.1. Pre-existing format drift surfaces under the new gate
- **Severity:** nit (non-blocking; non-functional).
- **Citation:** `uv run ruff format --check src/ tests/` at HEAD `02c4fb5` reports 27 files. Worktree diff at `128181b` (P4 parent) reports **38 drifted files**; `comm -23 <128181b-list> <HEAD-list>` shows **11 files P4 actively re-formatted** (i.e., when P4 touched them, P4 formatted them); `comm -13` (clean → drifted by P4) is **0 files**. P4 introduced zero new drift and improved the inherited situation by 11 files. The 27 surviving drifted files are all P1/P2/P3-touched-only files the P4 commits did not need to edit.
- **Why surfaced now**: plan-of-record §(f) is the **first** QA gate matrix to include `ruff format --check`. QA-P1, QA-P2, QA-P3, QA-G1 all ran only `ruff check`.
- **Suggested resolution:** Open P5 with a single format-only commit: `uv run ruff format src/ tests/ && git commit -m "style: ruff-format inherited drift (closes QA-P4 §G.1)"`. After that one commit, the gate is durable in CI.
- **Target phase:** P5 (housekeeping; ideally before the first feature commit).

### §G.2. Five of six C7 loop phase adapters are no-ops at P4
- **Severity:** nit (P5 readiness; intentional + documented).
- **Citation:** `runtime/consolidate/phases.py:16-43` module docstring + sub-plan amendments B-7/B-8/B-10. Of the six adapters in `PHASE_DISPATCH = ("extract", "score", "promote", "demote", "consolidate", "invalidate")`, only `_extract_phase` calls real work (`run_extract`). The other five return `_empty_result()`. The "6 `consolidate_phase` events fire in canonical order on a synthetic tenant" IMPL §2.4 exit gate is satisfied because `loop.py` emits each envelope per phase iteration regardless of body content. The promote/demote/invalidate phase **functions** in C6 (`runtime/consolidate/{promote,demote,invalidate}.py`) DO real work and are tested in isolation in `tests/runtime/test_consolidate_phases.py`.
- **Why this is correct at P4:** real adapter wiring is blocked on gap-06 (P9 fact extraction) — there is no production source of facts to promote/demote/invalidate at P4. The loop body would need to call e.g. `promote()` on a list of (fact_id, score) tuples that no P4 component produces.
- **Suggested resolution:** P5 should wire the `score` adapter (no gap-06 dependency — score-from-S2-state is feasible standalone). The other four wait for gap-06 P9.
- **Target phase:** P5 partial (score-adapter wire); P9 remainder.

### §G.3. A.2 rerank gate satisfied via test-local helper only
- **Severity:** nit (carry-forward from QA-P3 §F.3; deferral is plan-mandated).
- **Citation:** `tests/runtime/test_scoring_appendix_a.py:89-111` defines a private `_appendix_a_rerank()` test helper. T6, T6b, T7 assert against this helper. The production `api/recall.py` (`_score_one` + the sort body lines 599-645) does NOT apply `w_intent · intent_match · classifier_conf` multiplicative bonus or the `w_utility · utility_value` additive term — `recall()` at HEAD sorts hits by the consolidate-time composed score. Plan §g.192 + QA-P3 §F.3 explicitly defer the rerank wire-in to P5+.
- **IMPL §2.4 gate "through both surfaces":** the consolidate surface is bit-exact (T1-T4, T5 via `rrf_combine`); the recall surface is validated via the test-local helper (T6, T6b, T7). The audit reads this as satisfying the *spirit* of the gate but not the literal "through `recall()`" reading.
- **Suggested resolution:** Wire `w_intent` + `w_utility` into `_score_one` (or a new `_apply_a2_rerank()` step) at P5; replace `_appendix_a_rerank` with a direct call into the production function from the test.
- **Target phase:** P5+.

### §G.4. `_generate_uuidv7` duplicated 7×
- **Severity:** nit (pure tech debt; non-functional).
- **Citation:** identical (or near-identical) `_generate_uuidv7(tenant_id, discriminant, source_id) -> str` private functions exist in:
  - `src/lethe/api/remember.py`
  - `src/lethe/api/recall.py`
  - `src/lethe/runtime/consolidate/promote.py`
  - `src/lethe/runtime/consolidate/demote.py`
  - `src/lethe/runtime/consolidate/invalidate.py`
  - `src/lethe/runtime/consolidate/scheduler.py`
  - `src/lethe/runtime/consolidate/loop.py`
  - Five of seven have an inline TODO referencing the extraction; matches the stored-memory fact about RFC 9562 uuidv7 layout.
- **Suggested resolution:** Create `src/lethe/runtime/uuidv7.py` exporting `generate_uuidv7(tenant_id, discriminant, source_id) -> str` (deterministic from sha256(tenant_id ‖ discriminant ‖ source_id)) and `generate_uuidv7_random() -> str` for the per-A8 random use sites (`event_id`, `run_id`, `lock_token`). Single-source the layout asserts.
- **Target phase:** P5+.

### §G.5. `EventType non-refactor` gate is too literal — informational only
- **Severity:** informational (no fix required).
- **Citation:** The §(f) gate matrix specifies `git diff origin/main -- src/lethe/runtime/events.py | grep '^-' | grep -v 'EventType|_VALID_EVENT_TYPES|_COMMON_REQUIRED' | wc -l` and expects 0. Actual output is non-zero because the C2 commit reformatted a multi-line raise / error message and rewrote a few docstring sentences. **No semantic logic was removed.** The C2 EventType Literal at `events.py:82` retains exactly the P1 enumeration (`remember`, `recall`, `recall_outcome`, `promote`, `demote`, `invalidate`, `consolidate_phase`); `_COMMON_REQUIRED` at `events.py:105` is byte-identical to P1.
- **Suggested resolution:** Tighten the gate to inspect only logic lines, e.g., `git diff origin/main -- src/lethe/runtime/events.py | grep '^-' | grep -v '^---' | grep -v '^-#' | grep -v '^-\"\"\"' | grep -v 'EventType\|_VALID_EVENT_TYPES\|_COMMON_REQUIRED'` — or, simpler, audit the AST via `python -c "import ast; ..."` for symbol deletions only. Or accept that the gate is **intent-only** and rely on §E.2's manual line-by-line audit.
- **Target phase:** P5 gate-matrix tightening (low priority; doesn't affect closure).

---

## §H. Anti-checklist (binding self-restraint for this audit)

- [x] No production code or test under `src/`, `cli/`, `tests/` modified by this audit.
- [x] `docs/QA-P1.md`, `docs/QA-P2.md`, `docs/QA-P3.md`, `docs/QA-G1.md` not touched.
- [x] No re-grading of D1-D11 (they are CITED at §B with line refs, not RE-OPENED).
- [x] No new dep added; no SDK import added to `src/`; no SCNS reference in `src/`.
- [x] No commit / push performed by the audit; `docs/QA-P4.md` is the only new path in working tree.
- [x] All test invocations used `LETHE_HOME=$(mktemp -d -t lethe-qa-p4.XXXXXX)`.
- [x] LETHE_HOME isolation verified — `~/.lethe` does not exist on the audit host (`stat ~/.lethe` → no such path).
- [x] No QA-G2 attempted; cross-phase coherence vs P1/P2/P3 is reserved for G2 at P6 per GO-NO-GO §7.
- [x] Format-drift evidence (`/tmp/fmt-128181b.txt`, `/tmp/fmt-head.txt`) is throwaway and lives outside the repo working tree.

---

## §I. Verdict

**APPROVE-WITH-NITS.**

All 9 P4 commits (`2571a67`, `51ca62f`, `62bfe3c`, `8b4916f`, `68f78fa`, `3dff613`, `ca670d0`, `2e560ab`, `02c4fb5`) land cleanly on top of `128181b` (QA-G1). The full IMPL §2.4 exit gate set is met:

- 632/632 pytest passes; 0 mypy errors; 0 ruff check errors; DMR `recall@5 = 0.720` bit-identical.
- All 11 locked decisions D1-D11 honored (§B).
- All 8 standing risks R1-R8 either closed at P4 or carried forward with documented mitigation (§C).
- The four major P4-targeted carry-forward H-nits (SqliteLogWriter shared-conn, PPR wiring into `_score_one`, T2 atomicity, scheduler lock + heartbeat) **close at P4** (§D).

**Non-blocking nits filed (§G.1-§G.5):**
1. §G.1 — pre-existing format drift (27 files; auto-fixable; P5 cleanup).
2. §G.2 — five of six C7 phase adapters are no-ops by design; P5 wires `score` adapter, P9 wires the rest.
3. §G.3 — A.2 rerank validated via test-local helper; production `recall()` wire-in defers to P5+.
4. §G.4 — `_generate_uuidv7` duplicated 7×; extract to `runtime/uuidv7.py` at P5+.
5. §G.5 — informational: §(f) "EventType non-refactor" literal-grep gate is too strict; semantic invariant holds.

**Recommended facilitator next steps:**
- (a) Commit `docs/QA-P4.md` as a single `docs(qa)(p4)` commit.
- (b) Open P5 with `style: ruff-format inherited drift` cleanup as the first commit (closes §G.1 durably).
- (c) Capture §G.2 + §G.3 + §G.4 in the P5 plan-of-record §f gate matrix and §g standing-risk register.
- (d) Optionally tighten §(f) `EventType non-refactor` gate per §G.5 suggestion.

No CHANGES verdict reached; no fix-up commit is required.

---

*Audit produced under [[PLAN]] mode by the facilitator-side QA reviewer at `HEAD = 02c4fb5`. Read-only. `docs/QA-P4.md` is the sole working-tree change; the facilitator will commit it separately following review.*
