# QA-P1 — Per-phase QA pass for Phase 1 (storage substrate scaffolding)

**Verdict:** **APPROVE-WITH-NITS** — all four IMPL §2.1 exit gates green, R1–R4 substrate slices in place, no scope creep, no contract-byte invention beyond cited canonical pins. Two non-blocking nits documented in §H.

**Scope.** Per-phase QA per `docs/GO-NO-GO.md` §7 cadence. Audit covers commits `b67ed3e..d616eb2` against the facilitator plan at `~/.copilot/session-state/aa3fa3db-f668-46b1-9be3-ef8c94e36cdd/plan.md`, IMPL §2.1 (read from history at `698488b`), composition §2/§3.4/§3.5/§5.2/§7, and gap-08 §3.4–§3.5. Group-level QA (`QA-G1.md`) is a later artifact, run after P3 exits.

**Toolchain at QA time.** uv 0.10.0; cpython 3.11.14 (the `.venv` interpreter pinned by `.python-version`); macOS Darwin. Fresh `LETHE_HOME=$(mktemp -d -t lethe-qa.XXXXXX)` used for every disk-touching test.

---

## §A — Exit-gate verification (independent re-run)

All four IMPL §2.1 exit-gate criteria, plus the lint-and-types backstop from facilitator plan §(f) gate 5, re-executed in this QA session against the four landed commits at `d616eb2`. Initial `uv sync` was required because the QA shell's `~/.local/bin/uv` had not synced the editable install (`uv sync --extra dev` resolved a `ModuleNotFoundError: No module named 'lethe'` collection failure — environment drift, not an implementation defect).

| # | Gate | Command | Exit | Verdict |
|---|---|---|---|---|
| 1 | Per-store smoke (5 stores create cleanly) | `uv run pytest tests/store/` | 0 — `22 passed, 1 warning in 0.80s` | PASS |
| 2a | `lethe-audit lint --integrity` clean (pytest) | `uv run pytest tests/audit/test_integrity_clean_on_empty.py` | 0 — `5 passed, 1 warning in 0.70s` | PASS |
| 2b | `lethe-audit lint --integrity` clean (CLI) | `LETHE_HOME=$(mktemp -d) uv run lethe-audit lint --integrity --tenant-id smoke-tenant` | 0 — stdout `status=clean tenant=smoke-tenant` | PASS |
| 3 | tenant-init e2e (empty root → all five present → preferences-prepend `[]`) | `uv run pytest tests/runtime/test_tenant_init.py` | 0 — `6 passed, 1 warning in 0.71s` | PASS |
| 4a | api locked (pytest) | `uv run pytest tests/api/test_api_locked_for_p1.py` | 0 — `2 passed in 0.01s` | PASS |
| 4b | api locked (direct import) | `uv run python -c 'import lethe.api'` | 1 — `NotImplementedError: lethe.api verbs land in P2+; ...` | PASS (non-zero is the gate) |
| 5a | full pytest | `uv run pytest tests/` | 0 — `35 passed, 1 warning in 0.83s` | PASS |
| 5b | ruff | `uv run ruff check src/ tests/ cli/` | 0 — `All checks passed!` | PASS |
| 5c | mypy --strict | `uv run mypy src/lethe/` | 0 — `Success: no issues found in 20 source files` | PASS |

The dev's commit-message verification transcripts match the QA re-run exactly (35 tests; ruff clean; mypy clean across 20 files; CLI prints `status=clean`; `import lethe.api` raises with the documented message). No drift.

---

## §B — Per-commit audit

### B.1 — `b67ed3e chore(p1): bootstrap python toolchain`

**Files:** `pyproject.toml` (55 lines), `.python-version` (3.11), `.gitignore` (+2), `cli/lethe-audit` (12 lines), `src/lethe/__init__.py` (11 lines), `tests/conftest.py` (33 lines), `uv.lock` (1180 lines, dep-tree pin).

**Locked-toolchain conformance** (facilitator §(g)):

- Python `>=3.11` → `pyproject.toml:9 requires-python = ">=3.11"` + `.python-version:1` ✓
- hatchling backend → `pyproject.toml:1-3` ✓
- ruff `check + format`; rules `E/F/I/UP/B/SIM` → `pyproject.toml:36-43` ✓
- mypy `--strict` on `src/lethe` → `pyproject.toml:45-48` ✓
- pytest with `integration` marker excluded by default → `pyproject.toml:50-55` ✓ (P2 Graphiti integration tests stay opt-in — clean defer-not-defeat)
- Console-script `lethe-audit` wired to `lethe.audit.integrity:main` → `pyproject.toml:28` ✓ (body lands in commit 4)

**LETHE_HOME isolation rule** (facilitator handoff): `tests/conftest.py:20-29` defends with `assert home.resolve() != real_home.resolve(), "...refusing"` — the fixture both `monkeypatch.setenv("LETHE_HOME", ...)` and refuses to shadow `~/.lethe`. ✓

**Scope creep check:** none. Commit body explicitly disclaims: "intentionally does NOT import lethe.api (api lock per IMPL §2.1 lands in commit 3)" — `src/lethe/__init__.py:1-11` honors this. Verdict: **clean**.

### B.2 — `371ece6 feat(s1-s5)(p1): five-store schema scaffolding`

**Files:** 22 changed; +1225 LOC; per-store layout matches IMPL §2.1 file-list verbatim (paths in `src/lethe/store/{s1_graph,s2_meta,s3_vec,s4_md,s5_log}/...`).

**Per-store conformance:**

- **S1** (`s1_graph/{__init__,schema,client}.py`): `BiTemporalStamp(valid_from, recorded_at, valid_to)` matches composition §2 row 1; `EpisodeShape` envelope is structural-only with the explicit P2-deferral comment (`schema.py:39-46`); `BASELINE_ENTITY_TYPES = ("Entity", "Episode", "ProvenanceEdge")` derives directly from the §2 row text. `client.py` introduces a `GraphBackend` Protocol + `_InMemoryGraphBackend` (private; underscore-prefixed; smoke-only) + `GraphitiBackend` stub (production seam; raises `NotImplementedError` on protocol methods until P2). `import graphiti_core` is eager at module level (`client.py:24-26`) — fail-fast on `uv sync` per facilitator guidance.
- **S2** (`s2_meta/{__init__,schema,migrations}.py`): All 10 IMPL-pinned table names enumerated in `S2_TABLE_NAMES` (`schema.py:27-38`) + `s5_consolidation_log` for the §(g)-locked S5-in-S2 backing. WAL/synchronous=NORMAL/foreign_keys=ON pragmas enforced in `open_connection` (`schema.py:135-145`) — composition §7 row "S2 SQLite down or locked" mitigation in place from line one. Six tables get a defensible minimal `(id, created_at)` stub; four tables get pinned shapes (`tenant_config` k/v, `scoring_weight_overrides` k/v, `review_queue` per deployment §6.2, `idempotency_keys` per api §1.2 + I-5). `migrations.py` ships an empty registry with `current_version()` reading the `_lethe_meta` sentinel — clean ratchet seam.
- **S3** (`s3_vec/{__init__,client}.py`): `S3Config(dim=768, ann_ef_search=64)` knobs validated in `__post_init__`. `bootstrap()` loads `sqlite-vec`, creates `vec0` virtual table + `embedding_keys` sidecar with `CHECK ((node_id IS NOT NULL) + (edge_id IS NOT NULL) + (episode_id IS NOT NULL) = 1)` enforcing composition §2 row 3 "embedding-key shape" at insert time. ✓
- **S4** (`s4_md/{__init__,layout,frontmatter}.py`): `S4Layout` creates `s4a/` + `s4b/` per composition §2.1 split. `Frontmatter` parse/serialize uses PyYAML directly (rejecting `python-frontmatter` per plan §B2). `mint_uri()` is deterministic (`s4a://<tenant_id>/<rel-posix>`) and rejects paths outside `s4a_dir`.
- **S5** (`s5_log/{__init__,writer}.py`): `ConsolidationLogWriter` Protocol + `SqliteLogWriter` (default — writes to `s5_consolidation_log` inside the S2 file per facilitator §(g) lock; T2 stays single-DB per composition §3.4) + `MarkdownLogWriter` (defined-only at P1; both methods raise `NotImplementedError` until P3+ operator-config wiring). Replay determinism enforced by `ORDER BY seq ASC` (`writer.py:67-69`) and `json.dumps(..., sort_keys=True)` (`writer.py:60`).

**Test coverage** (22 tests across 5 files): bootstrap idempotence on every store; PRAGMAs verified on S2; embedding-key CHECK constraint exercised on S3; frontmatter round-trip on S4; replay ordering + S2-file-collocation invariant on S5. Coverage breadth is bounded to "prove the gate" — no speculative ANN tuning, no embedding generation, no extraction.

**Scope creep check:** none. `EpisodeShape` is envelope-only (gap-05 enforcement deferred to P2); `_InMemoryGraphBackend` is explicitly private and underscore-prefixed; `MarkdownLogWriter` raises rather than implementing. Verdict: **clean** (one nit moved to §H).

### B.3 — `848f131 feat(runtime)(p1): tenant_init bootstrap + api lock`

**Files:** `src/lethe/runtime/{__init__,tenant_init}.py`, `src/lethe/api/__init__.py`, `tests/{runtime,api}/test_*.py` + package markers.

- `tenant_init.bootstrap(tenant_id, storage_root) -> TenantBootstrap` creates `<storage_root>/tenants/<tenant_id>/` and brings up all five stores idempotently (`tenant_init.py:124-175`). Per-tenant root is the substrate-level R4 partition seam (composition §5.2). ✓
- `preferences_prepend(tenant_id, storage_root)` returns `[]` at P1 with explicit P3 deferral comment + `storage_root` retained in the signature so callers don't drift to a one-arg shape that would break at P3 (`tenant_init.py:191-194`). Honest seam — closes the IMPL §2.1 "preferences-prepend path returns empty" gate without speculating on the qmd-class index contract.
- `src/lethe/api/__init__.py` raises `NotImplementedError("lethe.api verbs land in P2+; ...")` on import (`api/__init__.py:9-12`). Verified: `import lethe.api` exits 1 with that message.
- Critically, `src/lethe/__init__.py` does NOT import `lethe.api`; the second test (`test_top_level_lethe_does_not_import_api`) snapshots `sys.modules`, clean-imports `lethe`, asserts `lethe.api not in sys.modules`, and **restores** the snapshot in a `try/finally` (the restoration was added in commit 4 to fix a bug discovered during gate 5 — see B.4). This guards plan §B5: the api lock must not fire on every consumer of the package.

**Scope creep check:** none. No verb body, no classifier, no idempotency runtime, no events.py — all explicitly P2+ per IMPL §2.2. Verdict: **clean**.

### B.4 — `d616eb2 feat(audit)(p1): integrity lint registry + lethe-audit CLI`

**Files:** `src/lethe/audit/{__init__,integrity}.py`, `tests/audit/test_integrity_clean_on_empty.py`, `tests/api/test_api_locked_for_p1.py` (bug-fix only — see below).

- `LintRegistry` is a mutable list of `(name, callable)` lints; `REGISTRY = LintRegistry()` is the module-level seam P2/P5/P8 register against. **Empty at P1 by design** — `test_registry_starts_empty_at_p1` asserts `REGISTRY.names() == ()`. ✓
- `LintResult.status` is `"clean"` when `findings == ()` else `"dirty"` — the gate-2 contract.
- `lint_integrity(tenant_id, storage_root)` calls `bootstrap()` first (matches gap-08 §3.5 "integrity check is part of boot sequence"; safe because bootstrap is idempotent), then runs `REGISTRY.run(tenant_root)`.
- CLI: `argparse` subcommand `lint --integrity --tenant-id <id> [--storage-root <path>]`; exit `0` on clean, `1` on dirty, `2` on argparse error. The `--integrity` flag is required at P1 (`integrity.py:524-526`) — clean future-proofing for the P5/P8 lint subcommand expansions.
- **Bug-fix in `tests/api/test_api_locked_for_p1.py`:** the original commit-3 version of `test_top_level_lethe_does_not_import_api` destructively cleared `sys.modules` for all `lethe.*` entries without restoring them. After the audit test file landed (with top-level `from lethe.audit import ...` cached against the pre-clear module instances), this test would silently strand subsequent tests holding stale references. The fix snapshots `sys.modules` and restores in a `try/finally`. This was a real bug in commit-3 code masked by test-collection order; the fix is correct and commit-message-disclosed.

**Test coverage** (5 tests): clean path (registry empty); CLI clean exit-0; CLI dirty exit-1 (monkeypatched fake-failing-lint to verify the exit-code branch); registry-empty invariant; empty-tenant-id rejection.

**Scope creep check:** none. No concrete lints landed (P2/P5/P8 own those). Verdict: **clean**.

---

## §C — R1–R4 substrate-slice assessment

| Risk | P1 commitment (per facilitator plan §(d)) | Landed evidence | Status |
|---|---|---|---|
| **R1** Markdown write amplification | "S4 `layout.py` partitions per `<storage_root>/<tenant_id>/{s4a/,s4b/}`; substrate boundary is set here." | `src/lethe/store/s4_md/layout.py:9-32` materialises the s4a/s4b split per-tenant; `tenant_init.bootstrap` calls `S4Layout.create()` per tenant. Compaction is correctly NOT here (P3+ load). | substrate-slice **CLOSED** as scoped; remains an open standing hazard until post-cutover load test (per GO-NO-GO §6.1 closing-note) |
| **R2** Crash-mid-write corruption | "S2 connection helper enforces `journal_mode=WAL` + `synchronous=NORMAL`; audit/integrity registry seam exists for P2/P5/P8 lints." | `src/lethe/store/s2_meta/schema.py:135-145` sets WAL + synchronous=NORMAL + foreign_keys=ON; verified by `tests/store/test_s2_smoke.py::test_s2_schema_pragmas_set` (asserts `journal_mode='wal'`, `synchronous == 1`, `foreign_keys == 1`). Lint registry: `src/lethe/audit/integrity.py:447-465`. | substrate-slice **CLOSED**; standing risk per GO-NO-GO §6.2 — do NOT mark closed until P8 |
| **R3** Provenance loss | "Lint registry placeholder created; concrete lints land in P2 (gap-05 §3.5)." | Same registry as R2 (`integrity.py:447-465`); `BASELINE_ENTITY_TYPES` includes `ProvenanceEdge` so the schema seam exists. No `provenance_required` / `provenance_resolvable` lint code — correct deferral. | substrate-slice **CLOSED**; standing risk; lints land in P2 |
| **R4** Tenant isolation breach | "Per-tenant root path in S4; per-tenant SQLite file in S2/S5; per-tenant subdir in S3; Graphiti `group_id` on S1." | Per-tenant root: `tenant_init._tenant_root() = storage_root/"tenants"/tenant_id` (`tenant_init.py:122-123`). S2: `S2Schema(tenant_root).db_path = tenant_root/"s2_meta.sqlite"` (per-tenant file). S3: `S3Client.db_path = tenant_root/"s3_vec.sqlite"` (per-tenant file). S4: `S4Layout` rooted at the tenant directory. S5: lives inside the per-tenant S2 file (so per-tenant by transitivity). S1: `S1Client.bootstrap()` calls `backend.bootstrap_tenant(tenant_id)` passing the tenant id as the Graphiti group_id (`client.py:127-132`). | substrate-slice **CLOSED**; runtime alarm + cross-tenant 404 still owed at P7 |

R1–R4 substrate hooks are credible. The R4 evidence is the strongest — partitioning is enforced at the path level so it would be hard to accidentally unwind in P2+. R5–R8 correctly NOT touched at P1 per the plan's risk-mitigation matrix.

---

## §D — Protocol-seam future-proofing (B1)

The `GraphBackend` Protocol surface at P1:

```python
def bootstrap_tenant(self, group_id: str) -> None: ...
def register_entity_type(self, type_name: str) -> None: ...
def health(self) -> bool: ...
```

A real Graphiti adapter at P2 will need to grow methods like `insert_episode(...)`, `extract_facts(...)`, `add_edge(...)`, etc. Adding methods to a `Protocol` is a non-breaking change in static structural typing — existing callers and existing implementations stay valid. The `_InMemoryGraphBackend` is explicitly private (leading underscore + module docstring disclaimer) so removing/replacing it later is internal refactor, not API churn. The `GraphitiBackend` is sketched at P1 (constructor stores conn params; protocol methods raise `NotImplementedError` with `pragma: no cover - P2`) so the seam to populate is staked out without speculative bytes.

`graphiti_core` is imported eagerly at module level (`client.py:24-26`) so a broken/missing dep fails at `uv sync`, never silently shipping a no-Graphiti substrate. Good defensive posture.

**Verdict:** the in-memory backend is not so over-fit that a real Graphiti adapter would require breaking changes. Seam is honest. ✓

---

## §E — Test-coverage breadth

35 tests landed at P1; bounded to the four exit gates plus minimal invariant guards:

- 22 store smokes — schemas create cleanly, idempotence, pragmas, frontmatter round-trip, S5 replay determinism, embedding-key CHECK constraint.
- 6 runtime tests — bootstrap returns all-ready, layout matches expected paths, idempotence, preferences-prepend `[]`, empty-tenant-id rejection.
- 2 api lock tests — direct-import raises; top-level `import lethe` does NOT pull in `lethe.api`.
- 5 audit tests — clean status, CLI exit codes (0 + 1), registry-starts-empty invariant, empty-tenant-id rejection.

**Speculative-coverage check:** zero pre-pinning of P2+ contract bytes detected. No `remember()` test, no scoring test, no consolidation test, no event-emit test, no idempotency-replay test. The `test_review_queue_shape_pinned` test pins 13 columns from deployment §6.2 which is the closest thing to pre-pinning — but the pin is on a doc that already locks the shape, not a fresh contract invention, so it's defensible. Likewise the `idempotency_keys` table shape pre-pins api §1.2 wording. Both are noted, not flagged.

**Verdict:** breadth is appropriate for "just enough to prove the four exit gates". ✓

---

## §F — Standing-risk status confirmation

Per `docs/GO-NO-GO.md` §6.2 (standing-risk pattern):

| Standing risk | P1 status | Closing phase |
|---|---|---|
| R2 (crash-mid-write corruption) | substrate-posture slice closed (WAL + lint registry seam); **NOT marked fully closed** | P8 |
| R3 (provenance loss) | substrate-posture slice closed (lint registry seam + ProvenanceEdge baseline type); **NOT marked fully closed** | P8 |
| R6 (utility-feedback signal loss) | NOT touched at P1; recall_outcome join-key plumbed at P3 | P9 |

No commit message claims premature closure. The facilitator plan's §(d) risk table explicitly tags R2 as "Partial (substrate-prep)" and R3 as "Hook only" — both honored in the landed code. ✓

---

## §G — Anti-checklist self-check (IMPL §7)

Spot-check of the 10 anti-checklist items applied to the P1 source/test/CLI surface:

1. **Re-decide WS0–WS8 locked decision.** No re-decision; every design assertion in code comments is §-ref-shaped (composition §2 row N; gap-08 §3.5; api §1.2; deployment §6.2). ✓
2. **Specify byte-level code.** Schema bytes pinned only where canonical docs already pin them (`review_queue` per deployment §6.2; `idempotency_keys` per api §1.2 + I-5). All other S2 tables get a defensible minimal stub; explicit P2/P4/P5/P7 ratchet plan in `migrations.py` docstring. ✓
3. **Specify SCNS runtime path.** `grep -rn scns src/ cli/ tests/` → zero hits. ✓
4. **Cross-deployment migration.** No new module references it. ✓
5/6/7. **Auth/wire/metrics commitment.** `grep -rEn "OAuth|JWT|mTLS|Prometheus|OTLP|gRPC|protobuf" src/ cli/` → zero hits. ✓
8. **v2 design.** `grep -rEn "v2|multi-tenant runtime|2PC" src/ cli/` → zero hits. ✓
9. **api §4.4 / `health()` schema rename or removal.** N/A — no health endpoint landed yet. ✓
10. **"For humans only" framing.** `grep -rni "humans only|human-only|for humans" src/ tests/ cli/` → zero hits. ✓

**Verdict: PASS.**

---

## §H — Nits / changes

**No CHANGES.** Two nits only; both non-blocking and do NOT require a fix-commit before P2 begins.

1. **`_InMemoryGraphBackend.register_entity_type` is tenant-blind.** `src/lethe/store/s1_graph/client.py:66-68` — the method loops over `self._tenants` and adds `type_name` to every registered tenant's set, regardless of which `S1Client` triggered the call. Real Graphiti behaviour is that entity-type schemas are cluster-wide (not per-`group_id`), so this happens to match production semantics, but as a smoke-only stub used only in `tests/store/test_s1_smoke.py` and `tests/runtime/test_tenant_init.py` it weakens the R4 narrative slightly: a multi-tenant assertion test cannot demonstrate type-registration isolation against this backend. Suggested remediation (P2-or-later, not now): either (a) document the cluster-wide-schema invariant explicitly in the `GraphBackend` Protocol docstring, or (b) drop the `for group_id in self._tenants` loop and store types in a global set (matching real Graphiti). Either is fine. **Non-blocking.**

2. **`SqliteLogWriter` opens a fresh connection per `append`/`replay`.** `src/lethe/store/s5_log/writer.py:54-58` notes this is intentional for statelessness; combined with `isolation_level=None` (autocommit) on `open_connection`, the `with self._connect() as conn` blocks in `append`/`replay` are benign-but-redundant (no implicit transaction to commit). Will need to be reconsidered when P4's `T2 = (S2 flag write + S5 audit write)` lands — that transaction needs a single shared connection or an explicit `BEGIN/COMMIT` wrapper. The seam doesn't preclude that, but the current `_connect()`-per-call pattern would have to change. Suggested remediation (at P4, not now): introduce a context-manager that yields a shared connection for cross-store writes. **Non-blocking.**

---

## §I — Closing verdict + recommended next action

**APPROVE-WITH-NITS.** All four IMPL §2.1 exit gates green when independently re-run under fresh `LETHE_HOME` isolation. R1–R4 substrate slices honored from line one (per-tenant partitioning is real on every store; WAL + synchronous=NORMAL on S2; lint registry seam exists; api lock fires correctly while top-level `import lethe` does not trip it). Locked toolchain (Python 3.11; hatchling; uv; ruff check+format; mypy --strict) honored without deviation. S5-in-S2 §(g) backing default is honored; `MarkdownLogWriter` is defined-but-stubbed for P3+ operator-config. Anti-checklist self-check is clean — zero "for humans only" framing, zero v2 scope creep, zero auth/wire/metrics commitments, zero re-statement of design rationale.

The two nits documented in §H are P2-or-later concerns, not P1-fix items. The standing risks R2/R3/R6 remain explicitly open (none claimed-closed in any commit message).

**Recommended next action:** facilitator may proceed to P2 kickoff. Per GO-NO-GO §7 cadence, P2 begins with a fresh `/clear` and a `[[PLAN]] P2` facilitator plan; P3 exit will then trigger the G1 group-QA pass (`docs/QA-G1.md`) covering cross-phase coherence across P1+P2+P3.
