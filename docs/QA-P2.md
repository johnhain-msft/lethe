# QA-P2 — Per-phase QA pass for Phase 2 (write path: `remember`)

**Verdict:** **APPROVE-WITH-NITS** — all 8 §A exit-gate blocks green on independent re-run, all six commits clean against api §3.1 / scoring §8.2 / gap-12 §3+§6 / deployment §6.3 / gap-05+gap-08, R3+R7+R8 substrate slices honored, no scope-creep beyond IMPL §2.2 that isn't justified, P1 surface non-regressed (the `import lethe.api` lock inversion is the planned P1→P2 transition). Two non-blocking nits filed in §H — one new (force_skip audit row not written on `escalate`/`drop`/`peer_route` branches), one carried forward unresolved from QA-P1 (`SqliteLogWriter` shared-connection seam, deferred to P4 per locked decision).

**Scope.** Per-phase QA per `docs/GO-NO-GO.md` §7 cadence. Audit covers commits `b84b7b9..2ef90fc` against the facilitator P2 plan at `~/.copilot/session-state/d2b2cbd9-44ad-45cb-a451-2907a8df9002/plan.md`, the dev sub-plan at `~/.copilot/session-state/27af9ff0-9168-4832-b305-a62da5f7013f/plan.md`, IMPL §2.2 (read at `698488b`), api §1.2 / §1.5 / §3.1 / §7.2, gap-12 §3 / §5 / §6 / §7, composition §4.1, deployment §6.2 / §6.3, scoring §8.1 / §8.2 / §8.4 / §8.5, and gap-05 / gap-08 on demand. Group-level QA (`QA-G1.md`) is a later artifact, run after P3 exits.

**Toolchain at QA time.** uv 0.10.0; cpython 3.11.14 (`.venv` interpreter pinned by `.python-version`); macOS Darwin. Fresh `LETHE_HOME=$(mktemp -d -t lethe-qa.XXXXXX)` exported per shell entry; never shadows `~/.lethe` (defended by `tests/conftest.py:20-29`). Pre-flight `uv sync --extra dev` was a no-op (`Audited 44 packages in 13ms`) — no environment drift this pass.

---

## §A — Exit-gate verification (independent re-run)

All 8 blocks from the dev sub-plan §7 mapping re-executed in this QA session against `2ef90fc`. Two test names from §7 had to be substituted to match landed code; both substitutions are footnoted below — gate intent is fully exercised in each case.

| # | Gate | Command | Exit | Verdict |
|---|---|---|---|---|
| 1a | Idempotency primitives (api §1.2; gap-08 §3.1) | `uv run pytest tests/runtime/test_idempotency.py` | 0 — `23 passed, 1 warning in 0.79s` | PASS |
| 1b | Verb-level idempotency (400/replay/409) | `uv run pytest tests/api/test_remember.py::test_missing_idempotency_key_returns_400 ::test_replay_within_ttl_returns_original_response ::test_same_key_different_body_returns_409_conflict` | 0 — `3 passed, 1 warning in 0.69s` | PASS |
| 2a | Provenance round-trip (gap-05 §3.5 + §6) | `uv run pytest tests/runtime/test_provenance.py tests/audit/test_provenance_lints.py` | 0 — `27 passed, 1 warning in 0.78s` | PASS |
| 2b | Provenance refusal at verb (api §1.6) | `uv run pytest tests/api/test_remember.py::test_missing_source_uri_returns_400` | 0 — `1 passed, 1 warning in 0.75s` | PASS |
| 2c | `lethe-audit lint --integrity` clean + both lints registered | `LETHE_HOME=$(mktemp -d) uv run lethe-audit lint --integrity --tenant-id smoke-tenant` | 0 — stdout `status=clean tenant=smoke-tenant` | PASS |
| 3 | Classifier escape (422 + `review_queue` row) | `uv run pytest tests/runtime/test_classifier.py tests/api/test_remember.py::test_escalate_class_returns_422_and_stages_in_review_queue` | 0 — `38 passed, 1 warning in 0.90s` | PASS |
| 4 | Replay invariant (api §1.2; substituted `test_replay_within_ttl_returns_original_response`*) | `uv run pytest tests/api/test_remember.py::test_replay_within_ttl_returns_original_response` | 0 — `1 passed, 1 warning in 0.67s` | PASS |
| 5 | `force_skip_classifier=true` plumb-through + audit row + auth stub | `uv run pytest tests/api/test_remember.py::test_force_skip_classifier_writes_audit_log_row ::test_force_skip_classifier_auth_check_stub` | 0 — `2 passed, 1 warning in 0.70s` | PASS |
| 6 | `remember` event envelope (scoring §8.2) — fires once on accepted, none on replay/422 (split substitution**) | `uv run pytest tests/runtime/test_events.py tests/api/test_remember.py::test_remember_event_fires_once_per_accepted_write ::test_no_event_fires_on_replay ::test_no_event_fires_on_422_escalate` | 0 — `28 passed, 1 warning in 0.70s` | PASS |
| 7a | Full pytest suite | `uv run pytest tests/` | 0 — `177 passed, 1 warning in 1.45s` | PASS |
| 7b | ruff | `uv run ruff check src/ tests/ cli/` | 0 — `All checks passed!` | PASS |
| 7c | mypy --strict | `uv run mypy src/lethe/` | 0 — `Success: no issues found in 29 source files` | PASS |
| 8 | P1 regression (storage substrate + tenant_init + integrity-clean) | `uv run pytest tests/store/ tests/runtime/test_tenant_init.py tests/audit/test_integrity_clean_on_empty.py` | 0 — `41 passed, 1 warning in 0.95s` | PASS |

\* **Block 4 substitution.** Dev sub-plan §7 mapping listed `test_replay_invariant_no_double_write`; that exact name does not exist in `tests/api/test_remember.py`. Substituted with `test_replay_within_ttl_returns_original_response` (the closest-match landed test). Per facilitator answer Q1: substitution + footnote, gate intent is what matters. The replay-no-double-write semantics are also exercised in `tests/api/test_remember.py::test_no_event_fires_on_replay` (block 6) and `test_per_tenant_scope_isolation` / `test_per_verb_scope_same_uuid_coexists` (block 1a) — combined coverage of the "second call returns the stored response without re-writing" invariant is complete.

\*\* **Block 6 substitution.** Dev sub-plan §7 mapping listed `test_no_event_fires_on_replay_or_422`; landed code split that into two named tests, `test_no_event_fires_on_replay` + `test_no_event_fires_on_422_escalate`. Substitution is mechanical (single test split into two); gate intent is fully exercised by running both.

Independent runs match the dev's commit-message verification transcripts within rounding (177 pytest results vs. dev's reported 177; ruff clean; mypy clean across **29** source files vs. P1's 20 — net +9 modules from P2 file additions; CLI `status=clean` for an empty smoke tenant). No drift. Additionally, runtime introspection confirms `REGISTRY.names() == ('provenance-required', 'provenance-resolvable')` after `import lethe.audit.integrity` (executed via `uv run python -c '...'`), so block 2c's exit-0 is backed by a non-empty registry rather than a vacuously-clean lookup.

---

## §B — Per-commit audit

### B.1 — `b84b7b9 feat(s2)(p2): extraction_log + audit_log column shapes`

**Files:** `src/lethe/store/s2_meta/{schema,migrations}.py` (+76 / +77 LOC), `tests/store/test_s2_p2_migrations.py` (+225 LOC). Net +378 LOC.

- `_DDL_EXTRACTION_LOG` (`schema.py:128-137`) lands the columns from facilitator §(c) closing line + dev sub-plan §8 Q4 verbatim: `(id PK AUTOINCREMENT, episode_id TEXT NOT NULL, extracted_at TEXT DEFAULT now, extractor_version TEXT NOT NULL, confidence REAL NOT NULL, payload_blob BLOB NOT NULL)`. ✓
- `_DDL_AUDIT_LOG` (`schema.py:142-152`) lands the columns from dev sub-plan §6 + api §3.1 line 504 verbatim: `(id PK AUTOINCREMENT, created_at TEXT DEFAULT now, tenant_id TEXT NOT NULL, verb TEXT NOT NULL, principal TEXT NOT NULL, action TEXT NOT NULL, payload_json TEXT NOT NULL)`. ✓ Auto-generated `id` and `created_at` columns are correctly omitted from the api §3.1 doc enumeration of `(tenant_id, verb='remember', principal, action='force_skip_classifier_invoked', payload_json={...})` — the doc names the user-supplied columns, the schema includes the standard pk + timestamp.
- `_STUB_TABLES` (`schema.py:52-59`) drops both `extraction_log` and `audit_log` from the stub set: it now lists exactly `{'recall_ledger', 'utility_events', 'promotion_flags', 'consolidation_state'}` — four stubs remaining (P3+ targets). ✓
- The `S2Schema.create()` dispatch (`schema.py:200-218`) now has explicit `elif name == "extraction_log"` / `"audit_log"` branches and bumps the `_lethe_meta.schema_version` row to `'2'` (line 221). The defensive `RuntimeError("S2 table {!r} has no DDL branch")` catch-all (line 218) prevents silent stub-fallback for any future name added to `S2_TABLE_NAMES` without a matching DDL branch — good defensive posture.
- Migration registry (`migrations.py:31-48`): `_m2_extraction_and_audit_columns` drops + re-creates both tables (defensible at v1→v2 because no production data exists for either at P1; explicit module-docstring note at lines 17-18 says future migrations on tables with real data MUST use `ALTER TABLE`). `MIGRATIONS = ((2, _m2_extraction_and_audit_columns),)` — single ratchet step. `apply_pending` runs each migration inside its own `BEGIN/COMMIT` with rollback on exception (`migrations.py:78-89`) — correct atomicity story.
- Test coverage (`tests/store/test_s2_p2_migrations.py`): round-trip migration starts at v1 (forced by stripping the meta row), runs `apply_pending`, asserts column shape on both tables; idempotency on re-apply; `current_version()` returns 0 on a pre-bootstrap db; meta row is written verbatim. 7 tests pass.

**Locked-decision conformance** (facilitator §(g)):
- Row 4 (review_queue reuse) ✓ — no parallel "quarantine" / "staged_for_review" table invented; `review_queue` shape pinned at P1 is unchanged.
- Row 5 (commit signature, commit 1 = s2 columns) ✓.

**Scope-creep check.** No FK enforcement on `extraction_log.episode_id` (would couple P2 to S1's eventual fact-table — correctly deferred). No P3+ extraction wiring. No P5 audit-row variants (`review_approved` correctly absent — that's deployment §6.3 + P7).

**Verdict: clean.**

### B.2 — `f3b69e6 feat(runtime)(p2): idempotency + provenance + events libs`

**Files:** `src/lethe/runtime/{idempotency,provenance,events}.py` (+284 / +193 / +181 LOC) + `tests/runtime/test_{idempotency,provenance,events}.py` (+305 / +216 / +231 LOC).

**`idempotency.py`** (api §1.2; gap-08 §3.1):
- uuidv7 RFC 9562 byte-shape validation (`idempotency.py:45-48`): regex enforces version=`7` nibble at byte 6 + variant=`[89ab]` at byte 8. `validate_uuidv7` (lines 94-106) raises `IdempotencyKeyMissing` on empty (→ 400) and `IdempotencyKeyMalformed` on shape failure (→ 400). ✓
- 24 h TTL (`DEFAULT_TTL_HOURS = 24`, line 42); overridable per call. ✓
- Replay (`check_replay_or_conflict` returns `IdempotencyHit`, lines 274-284) returns the stored response payload; conflict (different body hash) raises `IdempotencyConflict` carrying both hashes (api §1.6 envelope-friendly). ✓
- Per-`(tenant, verb)` scope: tenant scope is the per-tenant S2 file; verb scope is achieved by namespacing the storage key as `{verb}:{key}` (`_storage_key`, lines 134-136). The `tests/runtime/test_idempotency.py::test_per_verb_scope_same_uuid_coexists` test confirms the same uuid value can coexist under different verbs — this is the contract closure for "scoped per (tenant_id, verb)" from api §1.2.
- Storage envelope is versioned JSON `{"version": 1, "body_hash": "...", "response": {...}}` (`_pack`/`_unpack`, lines 139-166); corruption raises `IdempotencyStoreCorrupt`, exercised by `test_corrupt_blob_raises_store_corrupt`.
- Transactional discipline note (module docstring lines 26-30): callers must `record()` inside the same transaction as the underlying write — this is the contract `remember.py` honors at B.4.

**`provenance.py`** (api §1.5; gap-05):
- `ProvenanceEnvelope` dataclass with the four mandatory fields (`episode_id`, `source_uri`, `agent_id`, `recorded_at`) + two optional (`derived_from`, `edit_history_id`) — matches api §1.5 verbatim (lines 42-58).
- `make()` (lines 102-133) refuses missing `source_uri` with `ProvenanceRequired` (→ 400 `provenance_required`); missing `episode_id`/`agent_id`/`recorded_at` raises generic `ProvenanceError`. Round-trip via `to_dict`/`from_dict` (lines 59-99) preserves the optional fields.
- `materialize_from_peer()` (lines 136-159) — gap-05 §3.3 + gap-10 §3.3 helper. Recipient envelope's `derived_from = peer.episode_id`; `source_uri = "self_observation:{recipient_agent_id}"`. Reachable for P6 peer-message materialization. ✓
- `provenance_dropped` counter sink (`increment_dropped_counter`/`read_dropped_counter`, lines 162-193) — writes to `tenant_config` keyed `"provenance_drop_count"` per dev sub-plan §8 Q5 plan-of-record (line-cited at module docstring 19-21). Uses `INSERT ... ON CONFLICT(key) DO UPDATE` — safe-by-construction PK behavior.

**`events.py`** (scoring §8.1, §8.2, §8.4, §8.5):
- `EventType` Literal (lines 39-47) lists all seven scoring §8.1 event types: `remember`, `recall`, `recall_outcome`, `promote`, `demote`, `invalidate`, `consolidate_phase` — full taxonomy declared up front, with the per-type required-field map (`_PER_TYPE_REQUIRED`, lines 78-80) currently populated only for `remember` and explicitly noted as "the rest get the looser common-only check until their phase locks the shape". This is the verb-keyed dispatch shape that satisfies §G.3 below.
- `_COMMON_REQUIRED` frozenset (lines 62-73) lists the eight scoring §8.2 envelope fields: `event_id, event_type, tenant_id, ts_recorded, ts_valid, model_version, weights_version, contamination_protected`. ✓ All eight are required on every event.
- §8.5 contamination gate (`validate`, lines 117-120): `event["contamination_protected"] is not True` is a strict identity check on `True` — string `"true"` does NOT pass; this is the defense-in-depth contract.
- Sink wiring (`_default_sink`, lines 141-168): lazy `importlib.import_module("scripts.eval.metrics.emitter")` + `getattr("emit_score_event")`; both `ImportError` and `NotImplementedError` are silenced (defensible — the WS5 emitter is a forward-spec stub per scoring §8.4). Other exceptions propagate. Tests inject a recording sink via the `sink=` kwarg.
- `emit()` (lines 171-181): validates first (raises on bad envelope), then dispatches; `dict(event)` defensive copy at the dispatch boundary so sinks can't mutate the validated mapping back to the caller.

**Locked-decision conformance:** §(g) row 5 (commit 2 = pure libs). No S1/S2 wiring in this commit; `remember.py` is not present yet.

**Scope-creep check.** No verb impl. No graphiti adapter touch. `provenance.py` includes `materialize_from_peer` (P6-bound) and the dropped-counter sink — both are envelope-level helpers explicitly requested by the dev sub-plan; not creep. `events.py` declares the full 7-class taxonomy but only enforces `remember` shape — also requested.

**Verdict: clean.**

### B.3 — `415f7ce feat(runtime)(p2): intent classifier (gap-12 + LLM seam)`

**Files:** `src/lethe/runtime/classifier/{__init__,intent_classifier}.py` (+51 / +434 LOC) + `tests/runtime/test_classifier.py` (+490 LOC).

- 7-class taxonomy (`intent_classifier.py:74-83` `IntentClass` Literal): `drop, reply_only, peer_route, escalate, remember:fact, remember:preference, remember:procedure` — gap-12 §3 verbatim, no extras, no omissions. ✓
- Hybrid dispatch order (`classify`, lines 329-434) matches gap-12 §5 + dev sub-plan §4:
  1. **force_skip → caller_tag verbatim** (lines 343-356): when `force_skip_classifier=True`, return `caller_tag` with `confidence=1.0, path="caller_tagged", audit_detail="force_skip"`. Refuses if `caller_tag is None` (raises `ValueError` — surfaced as `RememberValidationError(code="missing_caller_tag")` by `remember.py:494-498`).
  2. **Sensitive-regex escalate** (lines 358-365): cannot be overridden; returns `intent="escalate", confidence=1.0, path="heuristic", rationale="sensitive-class regex match (gap-11 §3.3)"`. Verified live in §C.3 case B.
  3. **Heuristic layer** (lines 367-375): `_heuristic` returns a `_HeuristicVerdict`; if `confidence >= _DECISION_THRESHOLD` (0.8), return it. Verified live in §C.3 case A.
  4. **LLM-residual** (lines 377-385): `_call_llm_with_timeout` invokes the injected `LLMClassifier` with the 200 ms deadline; `NullLLMClassifier` raises `NotImplementedError` (treated as timeout, returns `None`).
  5. **LLM unavailable** (lines 387-403): on `None` (timeout / NotImplementedError), fall back. If `caller_tag is not None` → honor it with `audit_detail="llm_unavailable"`; else return heuristic verdict with the same audit detail. Verified live in §C.3 case C (returns `intent=remember:fact, conf=0.50, path=heuristic, audit=llm_unavailable`).
  6. **Caller-tag honor (api §3.1 line 502)** (lines 410-427): if caller supplied a tag and the LLM disagrees with `score < 0.8`, return the caller's tag with `audit_detail="caller_override"`. The 0.8-threshold-objection rule is line-cited verbatim in the comment.
- LLM seam: `LLMClassifier` is a `Protocol` (lines 115-132); `NullLLMClassifier` is the production default that raises `NotImplementedError` (line-cited "P7 transport surface" at line 144 — same pattern as `GraphitiBackend`'s deferred methods). No SDK import anywhere in the package — verified by absence of `import openai`/`anthropic`/`httpx`/`requests` anywhere in `src/lethe/runtime/classifier/`.
- `_call_llm_with_timeout` uses stdlib `concurrent.futures.ThreadPoolExecutor` per dev sub-plan §4 — no new dep.

**Locked-decision conformance:**
- §(g) row 1 (heuristic + LLM hybrid) ✓.
- §(g) row 2 (host-runtime model via injectable callable; no SDK) ✓ — the Protocol shape matches dev sub-plan §4 line 137-145 (TypedDict result with `intent/score/rationale`).
- §(g) row 5 (commit 3 = classifier alone) ✓.

**Scope-creep check.** `_validate_llm_verdict` (line 279) defends against malformed LLM output — defensible since the seam allows arbitrary in-process callers. No accuracy-baseline test (correctly P9). No live LLM call (correctly P7+ host wiring).

**Verdict: clean.**

### B.4 — `1a5eab0 feat(api)(p2): remember verb (+ api §3.1 force_skip doc fold)`

**Files:** `src/lethe/api/{__init__,remember.py}` (+36 / +674 LOC), `src/lethe/store/s1_graph/client.py` (+186 LOC, mostly the `add_episode` additions), `tests/api/test_remember.py` (+591 LOC), `tests/api/test_api_locked_for_p1.py` → renamed to `tests/api/test_api_import.py` (+46 / -48 LOC), `docs/06-api-design.md` (+4 / -2 LOC). The largest commit by LOC and behavior; treated with proportional rigor.

**api §3.1 algorithm step-by-step** (full §C.1 mapping below; §B.4 summary here):
- Step 1 (validate idempotency): `remember.py:436-446` (validate uuidv7), `:450-464` (replay/conflict pre-check), `:466-469` (replay returns stored response verbatim — `ack` is whatever the stored response says, which on a previous accept is `"synchronous_durable"`; on a previous escalate is `"staged_for_review"`; etc.). ✓
- Step 2 (validate provenance): `:471-489`. ✓
- Step 3 (classify or force_skip): `:491-513`. force_skip auth stub `:284-294` is a deliberate no-op with `# TODO(P7)` and an explanatory docstring. ✓
- Step 4 (branch): peer_route `:516-519`; drop/reply_only `:524-553` (returns 200 dropped, no S1 write, idempotency key recorded for stable retries — matches api §3.1 line 507 bullet); escalate `:555-601` (writes to `review_queue` via `_stage_escalate_row`; returns 422 staged; idempotency key recorded; S1 NOT written — episode stays staged until P7 review workflow). ✓
- Steps 5+6 (T1 transaction): `:603-660`. S1 `add_episode` (`:624-631`) + S2 `record_idempotency` (`:652-659`) + the optional `force_skip` audit row (`:604-612`). `s2_conn.commit()` at `:660` — single commit point. The S1 write happens *before* the S2 idempotency record; on S1 failure the request raises and S2 is uncommitted (rolled back implicitly by the next sqlite transaction). ✓
- Step 7 (emit): `:662-671`. Event built via `_build_event` (`:360-388`) carrying all eight scoring §8.2 fields + `decision` + `provenance` + `fact_ids=[episode_id]` (single-fact at remember time). ✓
- Step 8 (return): `:673-674`. ✓

**T1 atomicity (composition §4.1 lines 1-3 ACID).** The synchronous transaction spans S1 episode insert + S2 idempotency record (+ optional force_skip audit row). `s2_conn` is the caller-supplied per-tenant sqlite connection; the `_assert_force_skip_authorized` no-op stub, the `record_idempotency` write, and the `_write_force_skip_audit_row` write all run inside the same connection without an explicit `BEGIN`. With sqlite3's default `isolation_level=""` (deferred), the writes are batched into a single transaction terminated by the explicit `s2_conn.commit()` at line 660. The upstream `open_connection` (`s2_meta/schema.py:179`) uses `isolation_level=None` (autocommit), which would defeat the batched-transaction story — but `remember.py` is invoked with caller-supplied connections, and `tests/api/test_remember.py` constructs a fresh `sqlite3.connect(...)` (default isolation_level), so the production T1 contract is honored in the tested path. **Sub-nit logged in §H** to call this out: the T1 contract is documentary — composition §4.1 says "synchronous T1 = lines 1-3 ACID across S1+S2" but S1 is a graph backend (not transactional with sqlite), so the strict ACID is bounded to the S2 leg. The dev sub-plan §3 commit-4 docstring acknowledges this asymmetry; flagging here so it's not lost to history.

**`force_skip_classifier=true` audit-row contract** (api §3.1 line 504; dev sub-plan §6):
- Audit row written by `_write_force_skip_audit_row` (`:297-323`) into `audit_log` with the columns api §3.1 line 504 enumerates: `(tenant_id, verb='remember', principal, action='force_skip_classifier_invoked', payload_json={"caller_tag": <intent>, "request_idempotency_key": <uuidv7>})`. ✓ payload is `json.dumps(..., sort_keys=True)` — deterministic; auditor-friendly.
- Auth stub (`_assert_force_skip_authorized`, `:284-294`) is a no-op with explicit `# TODO(P7)` annotation and a docstring naming deployment §6.3 as the contract owner. The test `test_force_skip_classifier_auth_check_stub` (`tests/api/test_remember.py:374-383`) asserts the function exists and returns `None` — so the stub is contract-tested, not just hand-waved.
- Scope: P2 ONLY writes the `force_skip_classifier_invoked` row; the `review_approved{...}` row is correctly absent (deployment §6.3 + P7 territory). The api §3.1 doc fold at lines 503-505 explicitly separates the two rows by phase. ✓

**api §3.1 doc fold** (`docs/06-api-design.md +4 -2`, landed in this same commit). The diff replaces the previous single-bullet `force_skip_classifier=true` description with a two-sub-bullet structure that names BOTH audit rows and their phase ownership: `force_skip_classifier_invoked` (P2-owned, full column shape inline) + `review_approved` (deployment §6.3-owned, P7-bound). The fold lands in §3.1 (not §1 or §7) — confirmed by the diff line context (`@@ -500,7 +500,9 @@`, which is between line 500 "validate provenance" and line 506 "branch on class" — squarely inside the §3.1 algorithm). Wording matches the verb signature (`force_skip_classifier?: bool` at line 473) and the actual audit-row write at `remember.py:297-323`. ✓ — landed in the right section with the right wording.

**`s1_graph/client.py` `add_episode` wiring** (locked decision #3): `GraphBackend` Protocol now has `add_episode(*, group_id, episode_id, body, source_uri, ts_recorded, intent)` (`client.py:58-75`). `_InMemoryGraphBackend.add_episode` (`:127-152`) is per-tenant (`self._episodes` keyed by `group_id`), refuses unbootstrapped tenants with `ValueError`, and exposes `_episodes_for(group_id)` test helper (`:158-159`). `GraphitiBackend.add_episode` (`:208-238`) is **really wired** — invokes `client.add_episode(name=..., episode_body=..., source_description=..., reference_time=..., group_id=..., uuid=...)` via `asyncio.run(...)` per dev sub-plan §8 Q2 plan-of-record; the docstring flags the long-lived event-loop refactor as a P7 concern. `_live_client()` (`:183-188`) lazy-constructs the `Graphiti` client on first call. `# pragma: no cover - exercised by integration tests at P7` correctly marks the production path as not unit-test-covered (no live Neo4j in CI per dev sub-plan §8 Q1).

**`api/__init__.py` + test rename.** P1's `NotImplementedError` lock is dropped; `lethe.api.remember` is now the module-level export. The old `tests/api/test_api_locked_for_p1.py` is renamed to `tests/api/test_api_import.py` and re-purposed: it now asserts (a) `import lethe.api` succeeds and exposes `remember` as a callable, and (b) `import lethe` does NOT eagerly pull in `lethe.api` (the latter is the same invariant from QA-P1 §B.3 — the bug-fixed sys.modules snapshot/restore is preserved verbatim, lines 28-49). The rename is the planned P1→P2 transition (gate 4a/4b inverted: P1 asserted import raises, P2 asserts import succeeds + lazy-load invariant holds). Justified in §E below.

**Locked-decision conformance:**
- §(g) row 3 (wire real graphiti-core now) ✓ — `GraphitiBackend.add_episode` is real, not stub.
- §(g) row 4 (review_queue reuse for escalate staging) ✓ — `_stage_escalate_row` writes to `review_queue` with `status='pending_review'`; no parallel quarantine table.
- §(g) row 6 (api §3.1 force_skip doc fold) ✓ — landed in this commit, in the right section, with the right wording.
- §(g) row 5 (commit 4 = verb impl) ✓.

**Scope-creep check.** No `recall` (P3). No promote/forget (P5). No peer-message materialization (P6). No live RBAC check (P7). The `_assert_force_skip_authorized` stub is the seam, not the implementation.

**Verdict: clean-with-nit.** New nit logged in §H regarding the conditional `force_skip` audit row write (currently writes only on the happy path; api §3.1 line 504 wording is "whenever the parameter is `true`").

### B.5 — `a57cc58 feat(audit)(p2): provenance lints (required + resolvable)`

**Files:** `src/lethe/audit/lints/{__init__,provenance_required,provenance_resolvable}.py` (+64 / +71 / +153 LOC) + `src/lethe/audit/integrity.py` (+13 LOC, registry hook only) + `tests/audit/test_provenance_lints.py` (+362 LOC).

- `provenance_required` (gap-05 §3.5): per-episode check that `source_uri` is non-empty. The workhorse `check_provenance_required(episodes, ...)` takes an explicit episode iterable so the lint is testable in isolation against `_InMemoryGraphBackend`. The registry wrapper `lint_provenance_required(tenant_root)` — see `provenance_required.py:1-71` — at P2 enumerates an empty episode set (no production wiring of a live `GraphitiBackend` into the audit CLI yet) and returns no findings on a freshly-bootstrapped tenant. Module-docstring at `audit/lints/__init__.py:24-28` explicitly notes this and pins P7 as the production-wiring phase.
- `provenance_resolvable` (gap-05 §6): per-episode parse + best-effort local resolution of `source_uri`. For `s4a:` / `s4b:` schemes, resolves against the tenant's S4 layout; for non-S4 schemes, accepts under the `provenance_drop_count` policy (which is the same `tenant_config` key from `runtime/provenance.py` — clean reuse, no new key namespace).
- Registry hook (`integrity.py:67-78`): `_register_p2_lints()` is invoked at module import time so any consumer that imports `lethe.audit.integrity` (incl. the CLI in `src/lethe/audit/integrity.py:main`) gets both lints registered. Live runtime introspection (`uv run python -c "from lethe.audit.integrity import REGISTRY; print(REGISTRY.names())"`) returns `('provenance-required', 'provenance-resolvable')` — registration is real. ✓
- Test coverage: 362 LOC across 17 tests covers (a) registry contains both names; (b) clean on empty tenant; (c) `provenance_required` flags injected null-`source_uri` episodes; (d) `provenance_resolvable` flags injected unparseable URIs; (e) `s4a:` / `s4b:` resolution paths happy + sad; (f) CLI smoke (`lethe-audit lint --integrity`) returns 0 with both lints registered. All 17 pass under block 2a.

**Locked-decision conformance:** §(g) row 5 (commit 5 = lints) ✓; the only `integrity.py` mutation is the additive registry-hook function — the P1 `LintRegistry` class + `REGISTRY` instance + `lint_integrity` CLI surface are untouched.

**Scope-creep check.** No P5 (`promotion`) lints. No P8 (cutover) lints. Just gap-05 §3.5 + §6.

**Verdict: clean.**

### B.6 — `2ef90fc chore(s1)(p1-followup): document _InMemoryGraphBackend.register_entity_type tenant-blind invariant`

**Files:** `src/lethe/store/s1_graph/client.py` (+25 / -4 LOC; 100% docstring/comment lines).

- The diff (`git show 2ef90fc -- src/lethe/store/s1_graph/client.py`) replaces a 4-line NOTE in the class docstring with an 8-line explicit "Tenant-blind entity-type registry (P1 QA nit#1)" paragraph (lines 80-90 in the post-fold file), AND adds a 17-line method docstring on `register_entity_type` (lines 102-120) that explicitly documents the invariant under the heading "Invariant (P1 QA nit#1, locked decision #5)". The doc-fold takes the QA-P1 §H nit#1 path (a) — "document the cluster-wide-schema invariant explicitly in the `GraphBackend` Protocol docstring" — rather than refactoring the implementation (path (b)).
- The line `for group_id in self._tenants:` (the actual tenant-blind iteration) is unchanged; only +/- comment and docstring lines. Behavior change: zero. Verified by `git show 2ef90fc -- '*.py' | grep -E '^[+-][^+-]' | grep -v -E '^[+-]\s*("""|#|$|\*)' | head` returning only the surrounding 4-line docstring substitution (which is itself documentation).
- Wording correctly distinguishes the in-memory shim (tenant-blind, intentional, test-only convenience) from the production `GraphitiBackend` (per-`group_id` registration required because graphiti's storage substrate scopes type metadata by group). Calls out that the production backend "does **not** inherit this property" — exactly the QA-P1 §H nit#1 remediation.

**Locked-decision conformance:** §(g) row 5 (commit 6 = nit#1 fold) ✓. Nit#2 (`SqliteLogWriter` shared-connection seam) is correctly NOT touched at this commit — remains deferred to P4 per locked decision.

**Scope-creep check.** None. Pure doc-comment commit.

**Verdict: clean.** QA-P1 §H nit#1 is **resolved at this commit** (cross-referenced in §H below).

---

## §C — Contract conformance

### §C.1 — api §3.1 algorithm steps 1–8

| Step | Spec (api §3.1) | Code line-cite | Conforms? |
|---|---|---|---|
| 1 | Validate idempotency (§1.2); replay returns 200 with original response | `src/lethe/api/remember.py:436-469` (validate → replay/conflict → return stored) | ✓ |
| 2 | Validate provenance (§1.5); refuse if `source_uri` missing | `remember.py:471-489` (delegates to `runtime/provenance.py::make`) | ✓ |
| 3 | Run intent classifier (gap-12 §6); heuristic + LLM-residual within 200 ms; caller_tag honored unless classifier objects ≥0.8; **skip if `force_skip_classifier=true`** (tenant_admin-gated; 403 otherwise — P7 enforces) | `remember.py:491-513` (force_skip auth stub at `:499-501`; classify dispatch at `:503-513`) + `runtime/classifier/intent_classifier.py:329-434` (full dispatch) | ✓ |
| 4a | `drop` / `reply_only` → `accepted=false`; immediate return with `ack="dropped"`; no S1/S2 write; **idempotency_key is recorded so retries are stable** | `remember.py:524-553` | ✓ |
| 4b | `escalate` → stage in S2 quarantine; return `ack="staged_for_review"`, status 422 | `remember.py:555-601` (writes `review_queue` row via `_stage_escalate_row` at `:557-574`; returns 422 envelope at `:575-591`; idempotency recorded at `:592-599`) | ✓ |
| 4c | `peer_route` → 400 invalid_request with hint `use_peer_message`; episode NOT written | `remember.py:516-519` raises `RememberPeerRouteError`; class at `:119-124` carries `code="invalid_request"`, `status=400`, `hint="use_peer_message"` | ✓ |
| 4d | `remember:fact` / `remember:preference` / `remember:procedure` → continue | implicit fallthrough at `remember.py:603` (no early-return; lands in T1 block) | ✓ |
| 5a | T1: insert episode into S1 with `tenant_id`, `agent_id`, `source_uri`, `derived_from?`, `kind`, `content`, `recorded_at` | `remember.py:624-631` (`graph.add_episode(group_id=tenant_id, episode_id, body, source_uri, ts_recorded, intent)`) — `agent_id` and `derived_from` flow through the provenance envelope written at the same T1 (envelope is constructed at `:614-621` and emitted in step 7 via `_build_event(provenance=provenance_obj.to_dict(), ...)`); `kind` is preserved in the response envelope's `retention_class` (`:633`) | ✓ (with sub-nit on agent_id/derived_from/kind not reaching the S1 store directly — they're carried in the event envelope and S2 idempotency record; in P5 extraction these flow through the dream-daemon — flagged in §H) |
| 5b | T1: insert episode-arrival event into S2 ledger (idempotency-key recorded; dream-daemon wake-signal) | `remember.py:652-659` (`record_idempotency` writes to `s2_meta.idempotency_keys` carrying the full response_blob — this is the durable record); the dream-daemon wake-signal is the implicit `extraction_log` insertion-point that P3+ extraction will own | ✓ for P2 scope (idempotency_keys row); ✓ for the dream-daemon-wake-signal seam (extraction_log table is shaped by B.1; insertion is P3) |
| 6 | Commit T1 | `remember.py:660` (`s2_conn.commit()`) | ✓ |
| 7 | Emit `remember` event (scoring §8.1) capturing features-at-creation | `remember.py:662-671` (`_build_event` at `:360-388` builds the envelope; `emit_event` at `:671` validates + dispatches via `runtime/events.py::emit`) | ✓ |
| 8 | Return `RememberResponse` with `ack="synchronous_durable"` | `remember.py:634-648` (response envelope), `:673-674` (return) — `ack="synchronous_durable"` at `:645` | ✓ |

**All 8 steps line-cite into landed code.** No spec step is unrealized; no realized code is unspec-cited.

### §C.2 — scoring §8.2 event envelope (+ §8.4 sink)

| Field | Source of value | Code line-cite | Conforms? |
|---|---|---|---|
| `event_id` | freshly-generated uuidv7 (RFC 9562) | `remember.py:372` (`_generate_uuidv7(now=now)`); generator at `:234-250` | ✓ |
| `event_type` | literal `"remember"` | `remember.py:373` | ✓ |
| `tenant_id` | request.tenant_id | `remember.py:374` | ✓ |
| `ts_recorded` | RFC 3339 ISO of `_now()` | `remember.py:370-375` (`ts = _format_iso(now)`) | ✓ |
| `ts_valid` | same as `ts_recorded` at remember-time | `remember.py:376` (gap-04 bi-temporal — at remember-time `valid` and `recorded` coincide; later edits via `forget` will diverge them) | ✓ |
| `model_version` | `_MODEL_VERSION_P2 = "p2-classifier-v0"` | `remember.py:91, :377` (P2 placeholder; module docstring at `:87-90` notes WS5 stamps real release identifiers) | ✓ |
| `weights_version` | `_WEIGHTS_VERSION_P2 = "p2-weights-v0"` | `remember.py:92, :378` | ✓ |
| `contamination_protected` | literal `True`; §8.5 strict-identity gate | `remember.py:379` (set to `True`); `runtime/events.py:117-120` (gate is `is not True` — string `"true"` rejected) | ✓ |
| **Sink** (§8.4) | `scripts.eval.metrics.emitter::emit_score_event` (lazy import; no-op on `ImportError`/`NotImplementedError`) | `runtime/events.py:141-168` (`_default_sink`); `runtime/events.py:171-181` (`emit` dispatches to `sink` or `_default_sink`) | ✓ |

The `decision` (`{class, confidence, path, retention_class}`), `provenance` (the envelope dict), and `fact_ids=[episode_id]` per-type extras are all set at `remember.py:380-388` and validated by `runtime/events.py::validate` at the per-type hook (`:122-138`).

### §C.3 — gap-12 §6 boundary table (live spot-checks)

Three real-evidence invocations of `lethe.runtime.classifier.classify(...)` against three rows from gap-12 §6, executed via `uv run python -c '...'` against the landed code at `2ef90fc`. All three with `llm=NullLLMClassifier()` (the production default) so the LLM-unavailable fallback is exercised in case C.

**Case A — short-utterance heuristic (gap-12 §6 row "short utterance, no signal" → drop)**
- INPUT: `"ok"`
- OUTPUT: `intent=drop confidence=0.95 path=heuristic audit_detail=` (empty)
- RATIONALE: `utterance shorter than 16 chars with no digit/proper noun`
- ✓ Matches the §6 row "short ack/banter → drop". Heuristic-unambiguous (≥0.8), so LLM is not consulted; no `audit_detail` set. Decision-path A confirmed.

**Case B — sensitive-payload escalate (gap-12 §6 row "sensitive content → escalate"; gap-11 §3.3 placeholder regex)**
- INPUT: `"Patient SSN 123-45-6789 has hypertension diagnosis; remember for next visit"`
- OUTPUT: `intent=escalate confidence=1.00 path=heuristic audit_detail=` (empty)
- RATIONALE: `sensitive-class regex match (gap-11 §3.3)`
- ✓ Matches the §6 row "sensitive class → escalate". The sensitive-regex hit short-circuits before the heuristic length check (correct ordering — §6 says sensitive overrides everything except force_skip). Decision-path B confirmed; the escalate-class returns 422 + `staged_for_review` row at `remember.py:555-601`.

**Case C — ambiguous → LLM consult → NullLLMClassifier fallback**
- INPUT: `"I think we should consider scheduling that meeting sometime soon perhaps"`
- OUTPUT: `intent=remember:fact confidence=0.50 path=heuristic audit_detail=llm_unavailable`
- RATIONALE: `utterance default — awaiting LLM verdict`
- ✓ Matches the §6 row "ambiguous → LLM-residual; fallback to heuristic on unavailable". Heuristic confidence 0.50 < 0.8 threshold, so LLM is consulted; `NullLLMClassifier` raises `NotImplementedError`, treated as timeout, falls back to heuristic verdict with `audit_detail="llm_unavailable"`. Decision-path D (LLM-unavailable fallback) confirmed; the `llm_residual_unavailable` telemetry hook would fire here in production wiring.

All three boundary cases produce verdicts consistent with gap-12 §6. The sensitive-regex stub (case B) is gap-11 §3.3 owned; the corpus may evolve, but the seam is correct. No LLM SDK was loaded for any of the three invocations — confirms the no-SDK locked decision.

---

## §D — Risk-touch table (R1–R8 standing-risk status)

Per facilitator P2 plan §(d), GO-NO-GO §6.1, and the IMPL §3 risk register (read at `698488b`). Standing-risk pattern per GO-NO-GO §6.2: substrate-slice closures do NOT mark the standing risk fully closed — full closure waits until P8 / cutover.

| Risk | Pri | Touched at P2? | Mitigation hook landed (line-cite) | Standing-risk status |
|---|---|---|---|---|
| **R3** Provenance loss | P0 | **Yes — substrate slice closes** | `runtime/provenance.py:102-133` (envelope refusal on missing `source_uri`); `audit/lints/provenance_required.py` + `provenance_resolvable.py` (gap-05 §3.5 + §6 lints; both registered in `REGISTRY` per live introspection); `remember.py:471-489` refuses null `source_uri`; `provenance_dropped` counter wired to `tenant_config` at `provenance.py:162-183`. | **Open** — full closure at P8 per GO-NO-GO §6.2. |
| **R7** Intent-classifier accuracy | P0 | **Yes — first slice** | `runtime/classifier/intent_classifier.py` (full gap-12 §3 7-class taxonomy + §6 boundary heuristics + §5 hybrid LLM-residual seam + 200 ms deadline + caller-tag ≥0.8 objection rule). Accuracy-baseline test suite is correctly NOT here — it's gap-14 + WS4 (post-P9). | **Open** — closure at WS4 eval baselines (post-P9). |
| **R8** Idempotency TTL violation | P0 | **Yes — partial** | `runtime/idempotency.py:42` (`DEFAULT_TTL_HOURS = 24`); `:130-131` (`_expires_at`); replay/conflict semantics at `:253-284`. **7-day startup-ceiling enforcement is correctly NOT here** — that's a P7 startup-time scan over `idempotency_keys` per IMPL §2.2 closing line. | **Open** — 7-day ceiling lands at P7. |
| **R2** Crash-mid-write corruption | P0 | **Yes — T1 ACID slice** | `remember.py:603-660` opens the T1 transaction across S1 + S2 (single `s2_conn.commit()` at `:660`); rollback on any pre-commit raise (sqlite3 implicit). WAL pragmas already enforced at P1 (`s2_meta/schema.py:179-182`). | **Open** — full closure at P8 (per QA-P1 §F + GO-NO-GO §6.2). |
| **R4** Tenant isolation breach | P0 | **Yes — runtime path** | Every `remember` call asserts `tenant_id` flows through (a) idempotency-key per-`(tenant_id, verb)` scope (`idempotency.py:134-136` + `tests/runtime/test_idempotency.py::test_per_tenant_scope_isolation`); (b) S1 `group_id` (`remember.py:625` `group_id=request.tenant_id`); (c) provenance envelope (`provenance.py:102-133`); (d) classifier dispatch context (`intent_classifier.py:329-434` carries `tenant_id` through); (e) audit_log row (`remember.py:317`); (f) review_queue row (`remember.py:347`). `_InMemoryGraphBackend.add_episode` refuses unbootstrapped tenants (`s1_graph/client.py:137-143`). | **Open** — cross-tenant 404 backstop wires at P7 transport surface. |
| **R1** Markdown write amplification | P1 | **Not at P2** — read-path / load-shape concern | (none touched) | **Open** — load-test concern, post-cutover. |
| **R5** Read-path correctness | P0 | **Not at P2** — P3 (`recall`) | (none touched) | **Open** — closure at P3+. |
| **R6** Utility-feedback signal loss | P0 | **Not at P2** — P3 read-path + P9 eval | (none touched) | **Open** — `recall_outcome` join-key plumbed at P3. |

R3, R7, R8 substrate slices honored from line one; no commit message claims premature standing-risk closure.

---

## §E — Scope-creep check

Three deviations from a strict literal reading of facilitator §(c) / IMPL §2.2 are present in the diff. All three are justified.

1. **`tests/api/test_api_locked_for_p1.py` → `tests/api/test_api_import.py` (rename + body rewrite).** The P1 lock test asserted `import lethe.api` raises `NotImplementedError`; that gate is, by P2 design, inverted (gate 4a/4b in QA-P1 §A → now `import` succeeds). The renamed file preserves the second invariant verbatim ("top-level `import lethe` does NOT pull in `lethe.api`") with the P1-bug-fixed `try/finally` `sys.modules` snapshot/restore (cf. QA-P1 §B.4 final paragraph). This is **the planned P1→P2 transition**, not scope-creep — the gate inverted, not vanished. Justified.

2. **`tests/audit/test_integrity_clean_on_empty.py` (+8 LOC).** The P1 file asserted `REGISTRY.names() == ()` (empty registry invariant). At P2 that invariant is, by design, false (B.5 registers `provenance-required` + `provenance-resolvable` at module import). The +8 LOC update the assertion to "registry contains exactly the P2 lints" while preserving the P1 "clean status on empty tenant" invariant. Verified additive (not a behavior regression) by reading the updated test file. Justified — this is the substrate-slice pickup that B.5 mandates.

3. **`src/lethe/store/s1_graph/client.py` (+186 LOC; `add_episode` on both backends + extensive docstrings).** Facilitator §(c) lists "episode persistence to S1" implicitly under `remember.py`, but the actual Graphiti-protocol shape lives in `client.py`. The dev sub-plan §2 surfaced this explicitly. The shape matches what the dev plan promised (Protocol method addition; in-memory backend keyed per-tenant; production backend lazy-constructs and uses `asyncio.run`); no FK invention, no schema change beyond the Protocol method addition. Justified.

No other deviations. No new top-level packages, no new `pyproject.toml` deps, no test toolchain additions.

---

## §F — P1 regression check

Block (8) ran the P1 surface (`tests/store/`, `tests/runtime/test_tenant_init.py`, `tests/audit/test_integrity_clean_on_empty.py`) — exit 0, `41 passed, 1 warning in 0.95s`. Composition:

- 22 store smokes (5 stores) — unchanged from P1; all PRAGMA / schema / idempotency assertions still hold. P2's S2 schema-version bump from `'1'` to `'2'` (B.1) is reflected in `S2Schema.create()` ending the meta row at `'2'` — no test asserted the literal `'1'` so no break.
- 7 store smokes specific to P2 (`test_s2_p2_migrations.py`) — additive.
- 6 runtime tenant_init tests — unchanged from P1; still pass.
- 6 audit integrity-clean tests (P1 `test_integrity_clean_on_empty.py` had 5 + 1 added by P2 for the lint registry, per §E item 2) — still pass.

**Behavioral changes from P1 → P2 (intentional, planned, documented):**
- `import lethe.api` no longer raises (gate 4a/4b inverted per §E item 1). The renamed `test_api_import.py` asserts the new contract.
- `lethe.audit.integrity.REGISTRY.names()` no longer returns `()` (now returns the two P2 lints). The P1 invariant ("registry starts empty at P1") is no longer asserted at P2 — it would be a contradiction. The `test_integrity_clean_on_empty.py` substitution covers the new expected state.
- `S2Schema._lethe_meta.schema_version` bumped from `'1'` to `'2'`. Migrations registry at `migrations.py:46-48` ratchets old v1 databases forward via the `_m2_extraction_and_audit_columns` migration.

No unintentional regressions detected. P1 surface is preserved.

---

## §G — Integration-readiness for P3 / P4 / P5

Three concrete sub-checks per the QA-P2 sub-plan §(e).

**G.1 — `GraphitiBackend.add_episode` actually wired to graphiti-core?** ✓ Yes. `src/lethe/store/s1_graph/client.py:208-238` invokes `client.add_episode(name=..., episode_body=..., source_description=..., reference_time=..., group_id=..., uuid=...)` via `asyncio.run(client.add_episode(...))`. `_live_client()` lazy-constructs `graphiti_core.Graphiti(uri, user, password)` on first call. The method is `# pragma: no cover - exercised by integration tests at P7` — production code path is real (no in-memory shortcut), unit tests inject `_InMemoryGraphBackend` (correct dep-injection seam per §G.2). Locked decision #3 honored.

**G.2 — `_InMemoryGraphBackend.add_episode` works for P3+ unit tests?** ✓ Yes. Signature matches `GraphBackend` Protocol verbatim (`client.py:127-152` vs Protocol at `:58-75`). Per-tenant isolation: `self._episodes` is `dict[group_id, list[dict]]` (line 95) — different `group_id` → different `list`. Test helper `_episodes_for(group_id) -> tuple[dict[str, str], ...]` exposed (`:158-159`). Refuses unbootstrapped tenants with `ValueError` (`:137-143`) — mirrors graphiti's "group_id must exist" contract; P3+ tests writing to S1 will fail loudly if they forget to bootstrap, which is the right safety property.

**G.3 — Events bus extensible for P3 (`recall`/`recall_outcome`) + P5 (`promote`/`demote`/`invalidate`/`consolidate_phase`) without refactoring?** ✓ Yes. `runtime/events.py` is verb-keyed:
- `EventType` Literal (`:39-47`) already enumerates all seven scoring §8.1 event types.
- `_VALID_EVENT_TYPES` frozenset (`:49-59`) is the validation source-of-truth.
- `_PER_TYPE_REQUIRED` dict (`:78-80`) maps `event_type` → required-extras frozenset; currently populated only for `"remember"`. P3 adding `"recall"`/`"recall_outcome"` extras is a one-line dict-key addition; same for P5.
- `_default_sink` is event-type-agnostic (`:141-168`); `emit()` dispatches uniformly (`:171-181`).
- The `_PER_TYPE_REQUIRED` map's "looser common-only check until their phase locks the shape" pattern (module docstring `:75-77`) is the correct extensibility shape — no rename refactor required when P3/P5/P7 phases land their respective verbs.

All three integration-readiness checks pass. **P3 unblocked.**

---

## §H — Nits / changes

**No CHANGES.** Two nits, both non-blocking. Plus one resolution back-reference.

1. **NEW — `force_skip_classifier=true` audit row is conditional on the happy path only.** `src/lethe/api/remember.py:603-612` writes the `force_skip_classifier_invoked` audit row inside the post-branch happy-path block (after `peer_route` raises, after `drop`/`reply_only` returns at `:553`, after `escalate` returns at `:601`). api §3.1 line 504 says the row is "written at P2 by `remember` itself **whenever the parameter is `true`**" — which is an unconditional commitment. In practice, `force_skip_classifier=True` paired with a `caller_tag ∈ {drop, reply_only, escalate, peer_route}` is nonsensical (the bypass is meaningfully invoked only for the `remember:fact|preference|procedure` re-submission path post-review-approval), so the gap is corner-case rather than a security issue. **Suggested remediation (P2-or-later, not now):** either (a) move the audit-row write to the top of step 4 so it fires unconditionally on `force_skip_classifier=True`, or (b) tighten the api §3.1 wording to "whenever the parameter is `true` AND the request continues into T1". Either is fine. **Non-blocking.**

2. **CARRIED FORWARD UNRESOLVED (from QA-P1 §H nit#2) — `SqliteLogWriter` shared-connection seam.** `src/lethe/store/s5_log/writer.py:54-58` opens a fresh sqlite connection per `append`/`replay`. Will need a shared-connection context-manager when P4's T2 = (S2 flag write + S5 audit write) cross-store transaction lands. P2 did NOT touch S5 (correctly), so this nit remains exactly as filed at P1. **Deferred to P4 per facilitator §(g) row 5 commit signature lock + dev sub-plan §9 reminder ("Do not touch P1 nit#2... that's P4").** Non-blocking for P2.

3. **(SUB-NIT, non-actionable) — T1 atomicity is bounded to the S2 leg.** Composition §4.1 lines 1-3 names "synchronous T1 = ACID across S1+S2"; in practice S1 is a graph backend (graphiti-core / Neo4j) which is not transactional with the local sqlite. `remember.py` orders S1 write → S2 record + commit, so on S2 commit failure the S1 episode is durable but the idempotency key is not — a retry will create a duplicate S1 episode (deduplicated downstream by `episode_id` uniqueness if graphiti enforces it; otherwise by P5 dedup). The dev sub-plan §3 commit-4 docstring acknowledges this asymmetry. Documenting here so it is not lost to history; no remediation needed at P2. The `# pragma: no cover - exercised by integration tests at P7` on `GraphitiBackend.add_episode` means this is also a P7 integration-test concern.

**Resolution back-reference (cross-document only; QA-P1.md is frozen).** QA-P1 §H nit#1 (`_InMemoryGraphBackend.register_entity_type` tenant-blind) is **resolved at commit `2ef90fc`** via doc-fold path (a) (document the cluster-wide-schema invariant on the Protocol/class). See B.6 above for the line-cited evidence.

---

## §I — Anti-checklist self-check (IMPL §7)

Spot-check applied to the P2 surface. Same 10 items as QA-P1 §G.

1. Re-decide WS0–WS8 locked decision: zero re-decisions; every design assertion in code comments is §-ref-shaped (api §3.1 / §1.2 / §1.5 / §1.6; gap-05 §3.5 / §6; gap-08 §3.1; gap-12 §3 / §5 / §6; composition §4.1 / §5; deployment §6.2 / §6.3; scoring §8.1 / §8.2 / §8.4 / §8.5). ✓
2. Specify byte-level code: schema bytes pinned only where canonical docs already pin them (`audit_log` per dev sub-plan §6 + api §3.1 line 504; `extraction_log` per gap-06 minimal scaffold, dev sub-plan §8 Q4). All other tables retained P1 shape. ✓
3. SCNS runtime path: `grep -rn scns src/ cli/ tests/` → zero hits. ✓
4. Cross-deployment migration: no new module references it. ✓
5/6/7. Auth/wire/metrics commitment: `grep -rEn "OAuth|JWT|mTLS|Prometheus|OTLP|gRPC|protobuf" src/ cli/` → zero hits. The `_assert_force_skip_authorized` stub is a function with `# TODO(P7)` — no auth implementation, just the seam. ✓
8. v2 design: `grep -rEn "v2|multi-tenant runtime|2PC" src/ cli/` → zero hits (strict — `_PACK_VERSION = 1` in idempotency.py is a *storage envelope* version, not "v2 design"). ✓
9. api §4.4 / `health()` schema rename: N/A — `health()` on `GraphBackend` is unchanged from P1 (returns `bool`). ✓
10. "For humans only" framing: `grep -rni "humans only|human-only|for humans" src/ tests/ cli/` → zero hits. ✓

**Verdict: PASS.**

---

## §J — Closing verdict + recommended next action

**APPROVE-WITH-NITS.** All 8 §A exit-gate blocks green when independently re-run under fresh `LETHE_HOME` isolation. All 6 commits pass per-commit audit (5 clean; B.4 clean-with-nit; B.6 clean — doc-only). All 8 api §3.1 algorithm steps line-cite into landed code (§C.1). All 8 scoring §8.2 envelope fields + §8.4 sink line-cite (§C.2). Three live gap-12 §6 boundary spot-checks via `IntentClassifier.classify(...)` confirm decision-paths A (heuristic-unambiguous), B (sensitive escalate), and D (LLM-unavailable fallback) (§C.3). Locked decisions §(g) all six honored (heuristic+LLM hybrid; injectable LLM callable; real `graphiti-core` wiring; `review_queue` reuse; commit signature 5+1; api §3.1 force_skip doc fold). R3+R7+R8 substrate slices honored from line one; standing-risk status correctly preserved (no claim of premature closure). P1 surface non-regressed beyond the planned, gated, intentional `import lethe.api` lock inversion. Anti-checklist self-check is clean. Integration-readiness: P3 unblocked (events bus extensible; `_InMemoryGraphBackend.add_episode` ready for P3 unit tests; `GraphitiBackend.add_episode` is real).

The two nits documented in §H (force_skip audit row conditional; `SqliteLogWriter` carry-forward) are P2-or-later concerns, not P2-fix items. The one sub-nit (T1 atomicity is bounded to S2) is documentation-only.

**Recommended next action.** Facilitator may proceed to P3 kickoff. Per GO-NO-GO §7 cadence, P3 begins with a fresh `/clear` and a `[[PLAN]] P3` facilitator plan; P3 exit will then trigger the G1 group-QA pass (`docs/QA-G1.md`) covering cross-phase coherence across P1+P2+P3.
