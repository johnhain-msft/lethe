# QA-P3 — Read path (`recall` + `recall_synthesis`)

> Independent QA pass on the five P3 commits landed on `origin/main`
> (`cc32807..6f63e0d`). Read-only review; no source-tree mutations were made.
> Mirrors the structure and rigor of `docs/QA-P2.md`. **Erratum E1
> (IMPLEMENTATION-followups.md) is binding**: the write-side embedder is P4
> scope, not P3, and is not critiqued here.

---

## §A Scope of review

### A.1 Commits audited

| # | SHA | Subject | Insertions | Deletions |
|---|-----|---------|------------|-----------|
| 1 | `bdd1e94` | scoring lib (per-class dispatch + 5 terms) | 1 435 | 0 |
| 2 | `fa3ef7b` | retrievers + RRF + bi-temporal filter + recall_id + recall event type | 1 487 | 0 |
| 3 | `b8e7b4e` | recall verb (+ ledger DDL fold + preferences prepend) | 2 116 | 48 |
| 4 | `494895d` | recall_synthesis verb (api §2.2; reuses commit-3 helpers) | 1 058 | 3 |
| 5 | `6f63e0d` | DMR adapter + corpus fixtures (sanity-replay smoke) | 2 814 | 45 |
| **Σ** | | | **8 910** | **96** |

Five-way commit signature matches locked **D6** verbatim.

### A.2 Toolchain footer

- `uv 0.10.0`
- `Python 3.11.14` (`.venv`)
- `Darwin 15.7.4`
- `uv sync --extra dev` → `Audited 44 packages` (no drift)

### A.3 Independent gate re-run

Every test invocation under `LETHE_HOME=$(mktemp -d -t lethe-qa-p3.XXXXXX)`.

| # | Exit gate (IMPL §2.3) | Command | Result |
|---|---|---|---|
| 1 | DMR sanity replay (eval §5.7) | `uv run pytest tests/eval/test_dmr_adapter.py -v` | **6 passed** (incl. `test_dmr_sanity_replay_meets_floor`, `test_run_eval_cli_exits_zero_on_dmr_pass`, `test_run_eval_cli_default_remains_inert`) |
| 2 | Bi-temporal pre-retriever filter, no skip on small stores | `uv run pytest tests/runtime/test_bitemporal_filter.py -v` | **13 passed** (incl. `test_filter_runs_on_small_store_no_shortcut`, `test_pre_retriever_apply_runs_filter_before_retriever`, `test_pre_retriever_apply_does_not_invoke_retriever_on_filter_failure`) |
| 3a | `recall(k=0)` prefs-only with `recall_id` | `uv run pytest tests/api/test_recall.py::test_k0_returns_preferences_only_with_recall_id -v` | **1 passed** |
| 3b | `recall(k=0)` zero `recall` events | `uv run pytest tests/api/test_recall.py::test_k0_emits_zero_recall_events -v` | **1 passed** |
| 4 | Preferences prepend: 10 KB cap + `preferences_truncated` + recency-of-revision | `uv run pytest tests/runtime/test_preferences_prepend.py -v` | **12 passed** (incl. `test_cap_constant_is_10_kb`, `test_truncates_on_cap_overflow_and_drops_older_pages`, `test_recency_ordering_is_descending_by_revised_at`) |
| 5 | `recall_id` determinism (uuidv7 RFC 9562) | `uv run pytest tests/runtime/test_recall_id_determinism.py -v` | **17 passed** (incl. `test_uuidv7_rfc9562_layout`, `test_no_ts_recorded_in_deterministic_bits`) |
| 6 | Per-class scoring (4 persistent shapes) | `uv run pytest tests/runtime/test_scoring_per_class.py tests/runtime/test_graph_ppr.py -v` | **23 + 11 passed** |
| 7 | `recall_synthesis` emits `path=synthesis`, fact_ids = S4a page-ids | `uv run pytest tests/api/test_recall_synthesis.py -v` | **20 passed** (incl. `test_events_carry_synthesis_path`, `test_event_fact_ids_are_page_ids_not_page_uris`, `test_no_bitemporal_filter_invoked`) |
| ‑ | Full pytest | `uv run pytest tests/ -q` | **343 passed** |
| ‑ | Lint | `uv run ruff check src/ tests/ cli/ scripts/` | `All checks passed!` |
| ‑ | Types | `uv run mypy src/lethe/` | `Success: no issues found in 46 source files` |

All seven IMPL §2.3 exit gates pass on independent re-run.

---

## §B Per-commit audit

### B.1 `bdd1e94` — scoring lib

- `scoring/recency.py` implements §3.1 Cognitive-Weave decay (`R(t) = exp(−Δ/τ_r)` with τ_r per-class).
- `scoring/connectedness.py` implements **full HippoRAG PPR** per locked **D2**: power-iteration with `damping=0.85`, dangling-mass redirection to seed (personalized variant), 2-hop subgraph cap (`MAX_SUBGRAPH_NODES=500`), degree-percentile fallback when subgraph < 10 nodes. Pure-function shape over adjacency dicts. Tested by `test_graph_ppr.py` (11 cases including damping-mass conservation, subgraph cap, fallback path).
- `scoring/utility.py` matches §3.3 weighted aggregate.
- `scoring/contradiction.py` — log-dampened ε per §3.4.
- `scoring/gravity.py` — demotion-floor **multiplier** (NOT a 6th additive term): invalidated → `0.0`; above θ_demote → `1.0`; below θ_demote → `max(1.0, 1 + g_floor·gravity)`. Matches §3.5 verbatim.
- `scoring/per_class.py` — dispatch table covers **all four persistent shapes** (`episodic_fact`, `preference`, `procedure`, `narrative`) per locked **D1**; non-persistent classes (`reply_only`, `peer_route`, `drop`, `escalate`) raise `NonPersistentClass`. `DEFAULT_WEIGHTS = (0.2, 0.3, 0.2, 0.4, 0.5)` matches gap-03 §5(a) Candidate-A. Tested in `test_scoring_per_class.py` with 23 cases including `test_episodic_fact_uses_full_additive_tuple`, `test_preference_zeroes_recency_term`, `test_procedure_uses_180_day_tau_r`, `test_narrative_zeroes_recency_and_uses_priority_050`, `test_invalidated_fact_collapses_to_zero`.
- `scoring/__init__.py` exports the public dispatch surface only (no internal-term leakage).

**Verdict: clean.**

### B.2 `fa3ef7b` — retrievers + RRF + bi-temporal filter + recall_id + events

- `retrievers/semantic.py` — sqlite-vec ANN over S3, cosine top-k. Returns empty result list for `query_vec=None` (E1-compliant: no production write-side embedder at P3).
- `retrievers/lexical.py` — FTS5 over S1+S4 text; thin Protocol shim around the backend.
- `retrievers/graph.py` — graph walk over S1, degree-candidate top-k, returns `(fact_id, score)` pairs that feed `connectedness`.
- `retrievers/rrf.py` — RRF combiner; `K_CONSTANT=60` (scoring §4 default); deterministic tie-break (descending score → source priority `semantic < lexical < graph` → `fact_id` lexicographic). Tested in `test_retrievers_rrf.py` (multiple cases including determinism + tie-break).
- `retrievers/__init__.py::retrieve_all` absorbs `S3Outage` (composition §3.1 lexical fallback) and degrades gracefully; sets `degraded=True` flag.
- `bitemporal_filter.py` — pure module: `filter_facts(facts, now, t_purge_days=90)` excludes facts with `valid_to <= now` or `valid_from > now`; `T_PURGE_DAYS=90` exposed; `pre_retriever_apply()` documents the ordering contract (`test_pre_retriever_apply_does_not_invoke_retriever_on_filter_failure` proves the retriever is not consulted if the filter raises). Notably **no small-store shortcut**: `test_filter_runs_on_small_store_no_shortcut` enforces this.
- `recall_id.py` — exactly api §1.4 binding shape: 48-bit ts prefix from `ts_recorded` ms + 4-bit ver `0111` + 74 deterministic bits = leading 74 of `sha256(tenant_id ‖ query_hash)` + 2-bit variant `10`. Module docstring explicitly notes the predecessor-handoff slip (the spurious `"rec"` discriminant + ts-in-hash conflation) and supersedes it. Anti-regression test `test_no_ts_recorded_in_deterministic_bits` (test_recall_id_determinism.py:136) recomputes the 74 bits independently and asserts ts-invariance.
- `events.py` — `EventType` Literal extended with `recall`; `RecallPath = Literal["recall", "synthesis"]`; `_PER_TYPE_REQUIRED["recall"] = {"recall_id", "fact_ids", "path"}` — single-line extension with no refactor of the existing `remember` shape, exactly the extensibility contract QA-P2 §G.3 predicted. `validate()` enforces non-empty `recall_id`, non-empty `fact_ids`, and `path ∈ {recall, synthesis}` on emitted recall events.

**Verdict: clean.**

### B.3 `b8e7b4e` — recall verb + ledger DDL + preferences prepend

- `api/recall.py` (868 LOC) walks all 11 steps of api §2.1; line cites:
  - Step 1 (bi-temporal filter): `_filter_hits_by_kept_ids` post-retriever / pre-RRF (see §F.1 for the doc-paraphrase nit and why this is on-spec).
  - Step 2 (classify): reuses P2 classifier; `unspecified` default at low confidence.
  - Step 3 (weight tuple): per-class via `DEFAULT_WEIGHTS`.
  - Step 4 (parallel S1+S2+S3 retrieve): `retrieve_all()` with S3-outage absorption.
  - Step 5 (RRF combine): `combine()` with `k_constant=60`.
  - Step 6 (per-class score): `per_class.score()` invoked per surviving fact.
  - Step 7 (truncate): `top_k = scored[:k]`.
  - Step 8 (provenance enforcement): facts without `episode_id` dropped after scoring; tested by `test_facts_without_episode_id_are_dropped_after_scoring`.
  - Step 9 (ledger write): `write_ledger_row()` does `INSERT OR IGNORE` on `recall_id` PK; same-PK + diverged-payload raises `RecallLedgerCorruption` (substrate-bug surface).
  - Step 10 (preferences prepend): up to 10 KB cap honored, recency-of-revision ordering, `preferences_truncated` flag exposed.
  - Step 11 (emit `recall` events): one per top-k fact, all carrying the same `recall_id`, `path=recall`.
- **k=0 short-circuit** (line 683+): writes ledger, returns `recall_id` with `facts=[]` + preferences populated, emits **zero** `recall` events. `applied_filters.k_zero_short_circuit=True`. Retrievers are not consulted (`test_k0_returns_preferences_only_with_recall_id` asserts `lex.call_count == 0`, `sem.call_count == 0`, `grf.call_count == 0`).
- `runtime/preferences_prepend.py` — gap-09 §6 implementation: 10 KB cap (`PREFERENCES_CAP_BYTES = 10 * 1024`), recency-of-revision ordering with deterministic tie-break by `page_uri` descending, `preferences_truncated` flag set when any candidate is dropped. `test_cap_constant_is_10_kb` pins the constant.
- `store/s2_meta/schema.py:164–176` `_DDL_RECALL_LEDGER` matches facilitator §(d) column shape exactly: `(recall_id PK, tenant_id, query_hash, ts_recorded, classified_intent, weights_version, top_k_fact_ids JSON, response_envelope_blob)`.
- `store/s2_meta/migrations.py` — v2 → v3 ratchet via `_m3_recall_ledger_columns`: drop-and-recreate is safe because v2 `recall_ledger` is a `(id, created_at)` stub with no production writes (verified in module docstring + `test_s2_p3_migrations.py`). Module comment correctly notes that **P5+** extensions to `recall_ledger` (e.g. `recall_outcome` join indexes) MUST use `ALTER TABLE` because P3+ deployments will hold real ledger rows. Migration runs in its own transaction with rollback on failure.

**Verdict: clean** (modulo the §F.1 doc-paraphrase nit on filter ordering and §F.2 deferred-by-design items already documented in code comments).

### B.4 `494895d` — `recall_synthesis` verb

- `api/recall_synthesis.py` (418 LOC) implements api §2.2 distinct-path semantics.
- **Code-share, not copy-paste drift**: `write_ledger_row` and `emit_recall_events` are **imported** from `api.recall`, not redefined (lines 59–74 of recall_synthesis.py). Same ledger DDL, same event-emission pipeline.
- `recall_id` derivation uses synthesis-specific intent discriminants `_INTENT_URI` / `_INTENT_QUERY` mixed into the `query_hash` payload, so synthesis recall_ids are **always distinct** from fact-recall ids for the "same" string (`test_uri_and_query_forms_get_distinct_ids_for_same_string`, `test_recall_id_distinct_from_recall_verb_for_same_query`).
- Page-id derivation: deterministic `uuid` from leading 16 bytes of `sha256(page_uri)` — `test_event_fact_ids_are_page_ids_not_page_uris` asserts `fact_ids` carry these page-ids, not the raw URIs.
- Hard-fails on S4a outage (`S4aOutage(SynthesisError)`) for both URI form and query form (`test_s4a_outage_bubbles_uri_form`, `test_s4a_outage_bubbles_query_form`).
- Events emitted with `path="synthesis"` (`test_events_carry_synthesis_path`).
- Ledger row uses a synthesis-distinct `weights_version` value (`test_ledger_row_uses_synthesis_weights_version`).
- Replay semantics identical to `recall.py` (idempotent on same payload; raises corruption on diverged payload).
- **Bi-temporal filter NOT applied** — see §C.4 below for the explicit verification.

**Verdict: clean.**

### B.5 `6f63e0d` — DMR adapter + corpus fixtures

- `scripts/eval/adapters/dmr.py` is wired-executable per locked **D3**: it loads `tests/fixtures/dmr_corpus/{episodes.jsonl, embeddings.json}` into a fresh tenant, drives the full `recall` pipeline, and asserts the eval §5.7 saturated-benchmark floor (`test_dmr_sanity_replay_meets_floor`).
- `scripts/eval/run_eval.py` CLI: `--adapter dmr` exits 0 on pass (`test_run_eval_cli_exits_zero_on_dmr_pass`); default remains inert (`test_run_eval_cli_default_remains_inert`) so CI-by-default does not run a heavy fixture path.
- `scripts/eval/fixtures/build_dmr_embeddings.py` is a fixture-build-time tool **only** (164 LOC under `scripts/eval/fixtures/`); not imported by any production / runtime path (verified by grep: zero hits in `src/lethe/`). E1-compliant: there is no production write-side embedder.
- `tests/fixtures/dmr_corpus/README.md` documents fixture-build provenance (model + seed) per locked **D8** reproducibility requirement.
- `tests/fixtures/dmr_corpus/{episodes.jsonl, embeddings.json}` are checked-in (D8) — `test_dmr_corpus_fixtures_present_and_parseable` and `test_sanity_replay_raises_on_missing_fixture[…]` enforce presence + parseability.

**Verdict: clean.**

---

## §C Cross-cutting checks

### C.1 Provenance enforcement on the recall path

Facts lacking an `episode_id` are dropped **after** scoring but **before** the ledger write — `test_facts_without_episode_id_are_dropped_after_scoring` (test_recall.py:402) asserts this end-to-end. The recall response carries provenance on every surviving fact (`test_happy_path_returns_top_k_with_provenance` line 290–291: `assert "episode_id" in f.provenance`). Provenance enforcement reuses the P2 `runtime/provenance.py` lib — no copy-paste in the recall verb.

### C.2 Tenant isolation in `recall_id`

`tenant_id` is the first byte-sequence into the `sha256` hash input that produces the 74 deterministic bits (`recall_id.py:96–106`). `test_different_tenant_yields_different_id` (test_recall_id_determinism.py:70) asserts cross-tenant retrieval of the "same query" produces different `recall_id`s. The 48-bit ts prefix is the only timestamp-bearing region; ts is **not** mixed into the deterministic bits (`test_no_ts_recorded_in_deterministic_bits`).

### C.3 `recall_synthesis` ↔ `recall` code-sharing

`recall_synthesis.py:59–74` imports `write_ledger_row` and `emit_recall_events` directly from `api.recall`. Single source of truth for ledger atomicity (INSERT-OR-IGNORE + diverged-payload corruption check) and event emission (`path` literal + per-type validation). No drift surface — any future fix to ledger-write semantics in `recall.py` propagates automatically.

### C.4 **Bi-temporal filter is NOT invoked from `recall_synthesis`** (user reminder; mandatory verification)

`api/recall_synthesis.py:337` carries an explicit comment: *"NO bi-temporal filter is applied here (api §2.2 step 3). … Skipping the filter is intentional, not an oversight."*

The design rationale chain:
- **composition §1 row 48 (S5 row)** — bi-temporal stamps live in **S1 only** (Graphiti's substrate); S4a (synthesis pages) has no `valid_from` / `valid_to` semantics.
- **composition §3.2** — S4a is the qmd-style markdown corpus (git-versioned, page-keyed).
- **composition §5.1** — S1 ↔ S4a inconsistency is allowed by design; the synthesis surface intentionally surfaces narrative pages including those whose underlying S1 facts have been superseded.

The guard test `test_no_bitemporal_filter_invoked` (test_recall_synthesis.py:553–593) is **meaningful**: it monkeypatches `bt_module.filter_facts` with a spy that records every call; runs `recall_synthesis(...)` end-to-end; and asserts `len(calls) == 0`. The spy proxies through to the real implementation (so a positive-call assertion would still observe correct downstream behavior), which means the test catches the case where someone wires the filter in via a copy-paste from `recall.py`. The test wraps the filter at its source-module attribute (not a re-import alias), so it cannot be bypassed by a `from … import filter_facts` shortcut at the call site without breaking other tests.

**Conclusion: bi-temporal filter is correctly suppressed for `recall_synthesis`, the suppression is documented, and the test is a real guard.** Verified on-spec.

### C.5 Embedder absence (E1 compliance)

`grep -rn` for embedder model loads in `src/lethe/` returns zero hits in production paths. The only embedding-producing code is `scripts/eval/fixtures/build_dmr_embeddings.py` — a fixture-build-time script under `scripts/eval/fixtures/`, not imported by `src/lethe/`. The DMR adapter loads pre-computed embeddings from `tests/fixtures/dmr_corpus/embeddings.json`. P3 is E1-compliant: the embedder seam at `runtime/consolidate/extract.py` is reserved for P4 (verified vacant — that path does not yet exist in the tree).

### C.6 Lexical fallback on S3 outage

`runtime/retrievers/__init__.py::retrieve_all` catches `S3Outage` from the semantic backend and continues with lexical+graph results, setting `degraded=True`. `test_s3_outage_falls_back_to_lexical` (test_recall.py:564) exercises this end-to-end: provides a `query_vec` so semantic is **attempted** (`sem.call_count == 1`), induces `S3Outage`, asserts the response carries `store_health == {"s3_used": False, "degraded": True}` and that lexical results survive. Composition §3.1 fallback contract honored.

### C.7 Ledger atomicity

`write_ledger_row` (recall.py module-level, reused by recall_synthesis.py) does `INSERT OR IGNORE` on the `recall_id` PK in a single statement. Legitimate replay (same `(tenant_id, ts_recorded, query_hash)` → same `recall_id` → same payload) is a silent no-op (`test_replay_is_silent_noop`, `test_legitimate_replay_is_silent_noop`); same-PK + diverged-payload raises `RecallLedgerCorruption` (`test_same_pk_different_payload_raises`, `test_same_pk_different_payload_raises_corruption`). The ledger row is written **before** event emission, so a downstream event-bus failure does not strand un-ledgered events.

---

## §D Locked-decision compliance

| # | Locked value | Evidence | Status |
|---|---|---|---|
| D1 | All 4 persistent shapes scored | `scoring/per_class.py` dispatch table; `test_episodic_fact_uses_full_additive_tuple`, `test_preference_zeroes_recency_term`, `test_procedure_uses_180_day_tau_r`, `test_narrative_zeroes_recency_and_uses_priority_050`; `test_per_class_scoring_exercises_all_four_persistent_shapes` exercises all four through the verb | ✓ honored |
| D2 | Full HippoRAG PPR | `scoring/connectedness.py` PPR power-iteration + 2-hop subgraph cap + degree-percentile fallback; `test_graph_ppr.py` (11 cases). **See §F.2** for the deferred recall-verb wiring (no graph backend at P3) — module is shipped, tested, and ready for P4+ wiring | ✓ honored (lib); P4-deferred wiring is documented in code |
| D3 | DMR wired-executable (not skip-marker) | `scripts/eval/adapters/dmr.py` end-to-end runs `recall`; `test_dmr_sanity_replay_meets_floor` asserts the floor; CLI exits 0 on pass | ✓ honored |
| D4 | Preferences prepend: 10 KB cap + truncated flag + recency-of-revision | `runtime/preferences_prepend.py`; `test_cap_constant_is_10_kb`, `test_truncates_on_cap_overflow_and_drops_older_pages`, `test_recency_ordering_is_descending_by_revised_at`, `test_truncated_is_false_only_when_every_page_kept` | ✓ honored |
| D5 | `recall_outcome` join-key plumbed at P3, emission deferred to P9 | `recall_id` is the deterministic join key; `events.py` `_PER_TYPE_REQUIRED` extends only `recall` (not `recall_outcome`); no `recall_outcome` emission code in `recall.py` or anywhere in `src/lethe/` | ✓ honored |
| D6 | 5-way commit signature | `git log --oneline cc32807..HEAD` matches the 5-commit shape exactly | ✓ honored |
| D7 | QA-G1 deferred to separate `/clear` pass | N/A for this pass; flagged in §I as the recommended next-action | ✓ noted |
| D8 | Checked-in deterministic DMR fixture | `tests/fixtures/dmr_corpus/{episodes.jsonl, embeddings.json, README.md}` present; README documents model + seed | ✓ honored |

---

## §E Risk-touch table

| # | Risk | P3 touch | Status |
|---|---|---|---|
| R1 | S2 substrate footprint | Ledger DDL fold (v2 → v3) drops the `(id, created_at)` stub and lands the columned shape; future extensions go via `ALTER TABLE` per migration docstring | substrate slice **closed at P3** |
| R3 | Tenant isolation | `recall_id` mixes `tenant_id` into the sha256 input (test_recall_id_determinism `test_different_tenant_yields_different_id`); `applied_filters` and ledger rows scoped per tenant | in-progress (closure at P7 transport) |
| R4 | Cross-tenant 404 backstop | Not in P3 scope (transport-layer) | **deferred to P7** |
| R5 | Provenance integrity | Recall path drops facts without `episode_id` after scoring (test_recall.py:402); recall_synthesis fact_ids are deterministic page-ids derived from URIs | in-progress (closure at P8 cutover) |
| R6 | Connectedness signal source | PPR implemented + tested (D2); recall-verb wiring uses an RRF-rank-derived proxy pending the live graph backend (see §F.2) | **lib closes at P3**; verb-wiring closes at P4+ |
| R8 | Ledger atomicity | INSERT-OR-IGNORE on deterministic PK; corruption surface for diverged-payload (3 tests) | in-progress (closure at P9 with `recall_outcome` ingest) |

---

## §F Spec drift / inconsistencies

### F.1 IMPL §2.3 paraphrase: *"before any retriever runs"* vs api §4.1 *"before any ranker is consulted"* (doc-paraphrase, not code drift)

`recall.py` invokes the retrievers, then applies `_filter_hits_by_kept_ids` to drop invalid-window facts from the union **before** RRF / scoring. This is consistent with:

- **api §4.1** (binding): filter is *"pre-RRF" / "before any ranker is consulted"* ✓
- **scoring §4.1** (binding): same wording ✓
- **IMPL §2.3** exit-gate paraphrase: *"before any retriever runs"* — strictly read, this would require pre-pushdown into the lexical / vector backends, which the FactStore Protocol explicitly notes backends MAY pushdown but are not required to.

The verb-level guard `test_bitemporal_filter_excludes_invalid_window_facts_pre_scoring` (test_recall.py:356) asserts **outcome semantics** (excluded fact never appears in response or events; `applied_filters["pre_filter_excluded"]` is set) which is what the binding doc requires. The IMPL paraphrase is the looser of the two — recommend the IMPL doc be re-aligned to the api / scoring wording in a future docs pass. **Not a code drift; flagging as a P4-prep doc-cleanliness item.**

### F.2 Connectedness term in `recall.py` uses an RRF-rank-derived proxy, not full PPR (deferred-by-design, documented in code)

`scoring/connectedness.py` implements full HippoRAG PPR (D2 honored at the lib level + tested in `test_graph_ppr.py`). `recall.py::_score_one` currently feeds `connectedness_value = rrf_score / rrf_max` to `per_class.score()` rather than calling `connectedness.ppr_score()`, with the in-code comment that the PPR seed-set wiring lands once the live graph backend lands at P4+.

This is the D2-vs-R6 boundary: **D2 says "implement PPR"** (honored — module is shipped, tested, exported); **R6 says "use connectedness in recall"** (partial — proxy until graph backend is live). The proxy is monotonic in RRF rank, so directionality is preserved; the magnitude is bounded `[0, 1]` and feeds the additive term without violating the per-class formula's domain constraints. **Acceptable for P3** because there is no graph backend to query against at this phase; **MUST be re-validated when P4+ lands the graph seam** (flagged in §G).

### F.3 Step 6 post-rerank `w_intent · intent_match · classifier_conf + w_utility(t_now) · utility(f)` is not yet applied (D5-adjacent, deferred-by-design)

api §2.1 step 6 + scoring §4.5 specify a post-rerank that multiplies by `(1 + w_intent · intent_match · classifier_conf)` and adds `w_utility(t_now) · utility(f)`. `recall.py` currently calls `per_class.score()` (the §3 additive composed formula) without applying the §4.5 multiplicative intent bonus or utility prior. **Vacuous at P3**: the read-side classifier outputs an intent label but no `classifier_conf`, and the utility-events ledger does not yet have ≥1000 events (the §4.4 utility prior denominator threshold). The implementation is **on-spec for the P3 substrate state** but the call site will need the §4.5 post-rerank wired in once classifier confidence + a populated utility ledger exist. Flagged for P5+ as a pre-condition for the utility-aware ranker landing.

---

## §G Integration-readiness for P4

### G.1 Embedder seam at `runtime/consolidate/extract.py` is unblocked

The P3 read path does not foreclose the P4 write-side embedder. Specifically:
- `retrievers/semantic.py` accepts `query_vec=None` and returns empty results (E1-compliant), so the read path does not require an embedder to function — the P4 embedder lands on the **write** side and the read side will start consuming non-trivial vectors automatically.
- `tests/fixtures/dmr_corpus/embeddings.json` proves the read-path pipeline drives end-to-end with pre-computed vectors; P4 only needs to land the write-side production of those vectors.
- No P3 file imports from `runtime/consolidate/`, so the P4 module landing is collision-free.

### G.2 Consolidation scheduler can read `recall_ledger` rows P3 writes

The recall_ledger v3 column shape `(recall_id PK, tenant_id, query_hash, ts_recorded, classified_intent, weights_version, top_k_fact_ids JSON, response_envelope_blob)` is sufficient for the P4 consolidation chain to:
- Join recall events to ledger rows on `recall_id` (D5 join-key).
- Filter by tenant + time window (`tenant_id`, `ts_recorded`).
- Enumerate referenced facts via `top_k_fact_ids` JSON (a P5 index lands here per migration docstring).

The migration module's explicit P5+ guidance (*"recall_ledger extensions MUST use ALTER TABLE"*) protects P4 from accidentally drop-recreating a populated table.

### G.3 `recall_outcome` event-type plumbing (user reminder; mandatory verification)

D5 locked: `recall_outcome` join-key plumbed at P3, emission deferred to P9. Verification:

- `events.py` `EventType` Literal already enumerates `recall_outcome` from earlier phases (it was QA-P2 §G.3-extensible by design).
- `_PER_TYPE_REQUIRED` extends only the `recall` event-type at P3 — exactly the one-line addition pattern QA-P2 §G.3 predicted (`_PER_TYPE_REQUIRED["recall"] = {"recall_id", "fact_ids", "path"}`). No refactor of the `remember` shape; no churn of common-fields validation.
- When P9 lands `recall_outcome` emission, the wire-up is a **second one-line addition**: `_PER_TYPE_REQUIRED["recall_outcome"] = {"recall_id", "outcome_kind", …}`. No restructuring of the `validate()` dispatch (it already iterates the dict). No retroactive event-type re-versioning required.
- `recall_id` is the deterministic join key; `recall_outcome` events emitted at P9 will reference the same `recall_id` written to the ledger at P3.

**Conclusion: events.py is extensible for `recall_outcome` without a refactor; the consolidation chain landing at P4 is unblocked by the D5 deferral.**

---

## §H Non-blocking nits (deferred to a later phase with phase tag)

### H.1 IMPL §2.3 paraphrase wording — *(P4 docs cleanup)*

§F.1: re-align IMPL §2.3's *"before any retriever runs"* to the binding api §4.1 / scoring §4.1 wording *"before any ranker is consulted"*. Implementation already matches the binding text; the IMPL doc is the outlier. Pure docs-fix; ship with the next P4 doc pass.

### H.2 PPR wiring into the recall verb — *(P4+, gated on live graph backend)*

§F.2: replace the `rrf_score / rrf_max` proxy in `recall.py::_score_one` with `connectedness.ppr_score(seed_facts)` once the P4+ graph backend exposes the personalization seed set. Lib is shipped + tested; only the wiring is missing.

### H.3 `_score_one` uses `valid_from` as `t_access` — *(P4+, gated on utility ledger)*

gap-03 §7 specifies "last-access" timestamp; current implementation substitutes `valid_from` because no utility ledger exists at P3. Defensible (recency-of-record approximates recency-of-access in the absence of access events); replace once the utility ledger is wired.

### H.4 `preferences_prepend.build_envelope` stops at first overflow — *(P9, fairness)*

The envelope builder drops all subsequent pages once any page would exceed the 10 KB cap, rather than greedy first-fit. Spec only says "truncate by recency-of-revision", and the current behavior is deterministic + conforms to the recency ordering, but a small revision could fit a later (smaller) page after dropping a larger one. Cosmetic packing improvement, not a correctness issue.

### H.5 Step ordering in `recall.py`: preferences fetched up-front (line ≈678) — *(P5 docs)*

api §2.1 step 10 ordering puts "Prepend preferences" after the ledger write. Implementation fetches preferences up-front (to compute response shape early), then assembles the envelope after retrieval. Functionally equivalent (no data dependency between preferences and retrieval), but the source comment could explicitly note the divergence-from-doc-ordering and why.

### Carry-forward (non-regressed, no P3 touch)

- QA-P1 §H.2 / QA-P2 §H.2 `SqliteLogWriter` shared-connection — still P4 territory; P3 did not touch S5.
- QA-P2 §H.1 `force_skip_classifier` audit row — still P3+ territory unrelated to the read path; not regressed.

**No embedder-shaped finding is filed (E1 forbids).**

---

## §I Verdict

**APPROVE-WITH-NITS.**

Justification:
- All 7 IMPL §2.3 exit gates pass on independent re-run under fresh `LETHE_HOME` (§A.3).
- All 5 commits are individually clean (§B.1–B.5); commit signature matches D6 exactly.
- All cross-cutting checks pass (§C.1–C.7), including the user-mandated explicit verification that the bi-temporal filter is **NOT** invoked from `recall_synthesis` (§C.4 — guarded by `test_no_bitemporal_filter_invoked` with proper monkeypatch + spy + zero-call assertion + composition §3.2 / §5.1 / §1 row 48 cross-references).
- All 8 locked decisions D1–D8 are honored (§D); D5 plumbing leaves P4 consolidation unblocked.
- Risk register touch-points (R1, R3, R4, R5, R6, R8) handled per facilitator §(d); no premature closure claims.
- No spec-drift items rise to REQUEST-CHANGES level: the three §F items are all (a) doc-paraphrase, (b) deferred-by-design with in-code comments, or (c) vacuous-at-P3 with the call site ready to wire.
- Integration-readiness for P4 verified (§G), including explicit confirmation that `events.py` is one-line-extensible for `recall_outcome` without refactor (§G.3 — user-mandated).
- Full pytest 343/343, ruff clean, mypy clean across 46 source files. No P1+P2 regression.

**Recommended next action**: facilitator authorizes the QA-P3.md commit, then proceeds to the QA-G1 cross-phase pass (locked D7) on a fresh `/clear`.

---

## Anti-checklist (binding self-restraint)

- [x] No production code or test under `src/`, `cli/`, `tests/` was modified.
- [x] `docs/QA-P1.md` and `docs/QA-P2.md` not touched (verified pre/post).
- [x] No write-side embedder critique filed (E1 binding).
- [x] No P1/P2 locked decision re-litigated.
- [x] No commit / push performed; `docs/QA-P3.md` staged only.
- [x] All test invocations used `LETHE_HOME=$(mktemp -d -t lethe-qa-p3.XXXXXX)`.
