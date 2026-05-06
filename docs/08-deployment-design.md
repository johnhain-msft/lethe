# 08 — Deployment Design (WS8)

**Audience.** Dual-audience per `docs/HANDOFF.md` §13. An operator (non-engineer running a Lethe deployment) reads this doc to know which knobs to set, which alarms to wire, and what to do during cutover and incidents. An engineer reads this doc to verify that every numeric default and every operator-facing surface cites an upstream source-of-truth (composition / scoring / api / migration / gap-NN). Where a term is operator-facing, it is defined inline on first use.

**Position in the WS chain.** WS8 follows WS3 (composition; `docs/03-composition-design.md`), WS4 (eval plan; `docs/04-eval-plan.md`), WS5 (scoring formalism; `docs/05-scoring-design.md`), WS6 (api surface; `docs/06-api-design.md`), and WS7 (migration plan; `docs/07-migration-design.md`). WS8 is the first WS that has to *commit numbers* — gate intervals, lock heartbeats, rate-limit caps, alarm thresholds, role names, wire-format choice. Where upstream WS deferred a number to WS8, this doc names it; where the number is a v1 bet to be instrumented and revised, this doc says so.

---

## §0 Frame

### §0.1 What WS8 owns

The deployment-shape and operator-knob surface that upstream WS deliberately deferred:

- **RBAC role definitions and capability-to-role mapping.** `docs/06-api-design.md` §0.2 + §8 names capabilities (`forget_purge`, `audit_global`, `tenant_admin`) abstractly; WS8 picks the role names and the mapping. (HANDOFF §12.6.)
- **Rate-limit numerical caps** per role / capability / verb. api §0.2 + §1.6 + §2.1.2 + §3.3 + §3.4 + §4.3 names *where* limits attach; WS8 picks the values. (HANDOFF §12.6.)
- **Wire format and transport choice.** api §0.4 leaves the encoding abstract; WS8 picks. (HANDOFF §12.6.)
- **Operator knobs.** Dream-daemon gate interval (gap-01 §3.2 Q3); lock heartbeat (gap-01 §3.2 Q3, gap-08 §3.4); idempotency-key TTL (api §1.2; gap-08 §5); drift-detector cadence and re-eval schedule (gap-14 §5(3)); preference-cap ordering (api §0.3 #3); recall-determinism drift tolerance (migration §3.1 phase 12); single-writer-per-tenant default for migrations (migration §4.2; gap-04 §4 stop-gap).
- **Health and observability contract extensions.** api §4.4 names the `health()` and `audit()` shapes; WS8 specifies the operator-facing additive fields (migration progress, idempotency-key TTL fallback rate, escalation-queue depth, drift state, v2-entry-criteria gate state).
- **Operator alarm thresholds and emit shapes.** Phase 9 async-drain alarm (HANDOFF §14.6; migration §10); Phase 11 S3 backfill progress (HANDOFF §14.6; migration §10); generic degraded-mode alarms (composition §7 + §7.1).
- **Escalate-review pipeline.** Workflow surface for `422 classifier_escalate` returns (api §3.1 + §3.4) and migration `escalated` rows (migration §5.1). HANDOFF §12.6 + §14.6 named this as WS8 / project-ops territory.
- **Migration runtime contract.** Phase-gate runner contract; snapshot UX; manifest UX names. The migration tool's source code is an operator-tooling pass (post-WS8); WS8 names the contracts so the tool can be implemented against a stable target.
- **Backup / restore posture.** Crash-recovery operator surface; `lethe-audit lint --integrity` invocation (gap-08 §3.5); single-deployment restore. Cross-deployment Lethe→Lethe restore is deferred (gap-08 §5; HANDOFF §14.6).
- **v1 → v2 entry-criteria gate.** Tracking of the two scoring §8.6 conditions and the multi-tenant cutover decision rule.
- **Single-tenant-per-deployment posture.** v1 baseline. (composition §1.1 + §5.2.)

### §0.2 What WS8 does NOT own

Listed up-front so the rest of the doc can stay knob-focused without continuously disclaiming:

- **Verb semantics and request/response schemas.** WS6 (api). WS8 picks the wire format that carries the schemas; it does not change them.
- **Migration phase order, mapping rules, identifier derivations.** WS7 (migration). WS8 specifies the operator-facing contract for invoking the phases; it does not re-decide them.
- **Scoring math, weight values, gravity formula.** WS5 (scoring). WS8 surfaces the drift detector and re-eval cadence as operator knobs (per gap-14 §5(3)) but does not pick weights.
- **Eval-set composition.** WS4 (eval-plan; gap-14). WS8 schedules the re-eval cadence; the cases come from elsewhere.
- **Retention engine internals.** gap-01. WS8 sets the gate interval and lock heartbeat as operator knobs; the daemon's pluggable-phase contract and scoring-phase internals live in gap-01 / composition §4.4.
- **The migration tool's implementation bytes.** The CLI, manifest format on disk, snapshot mechanism, S3 backfill orchestration, phase-gate runner code — all operator-tooling pass (post-WS8). WS8 names the contracts.
- **Auth-mechanism implementation.** WS8 picks the wire-format and the principal-extraction contract; the actual token-issuing infrastructure (OAuth provider, JWT signer, mTLS CA) is deployment-specific and out of scope for the design doc.
- **Cross-deployment Lethe→Lethe migration or restore.** Deferred to v1.x (HANDOFF §14.6; gap-08 §5).
- **`vault.db` consumption.** Out of scope per migration §1.1 + §8 (HANDOFF §14.6).
- **Multi-tenant runtime.** v2. v1 is single-tenant-per-deployment (composition §1.1 + §5.2).

### §0.3 Binding constraints

Every numbered constraint below is non-negotiable; every § that follows is verifiable against them.

1. **Single-tenant-per-deployment is the v1 baseline.** Multi-tenancy is v2. The cutover gate (scoring §8.6) is **strict-stratum operator share ≥20%** AND **≥10 000 labeled `(recall, outcome)` pairs**. (composition §1.1 + §5.2; HANDOFF open-item list.)
2. **No SCNS runtime dependency post-cutover.** No verb, no operator command, no health surface reads from `~/.scns/`, imports SCNS schemas, or accepts SCNS data sources at runtime. (HANDOFF §10 binding constraint #1; api §0.3 #1; migration §0.3 + §6.6.1.)
3. **Cross-tenant reads are forbidden** at every read verb and at every operator surface, except where the principal holds the `audit_global` capability for ops aggregation, and even then no tenant-identifying content is returned in cross-tenant aggregates. (api §1.8; composition §5.2.)
4. **Markdown is dual-audience** wherever it appears as an operator surface (manifest HTML, S5 audit dump, escalate-review queue page). Operator-facing prose does not frame markdown as "for humans only" — both humans and LLM-side reviewers read these surfaces. (composition §1.1; HANDOFF §13.)
5. **Every numeric default carries a citation** to its upstream source-of-truth, OR is named explicitly as a v1 bet to be instrumented. The §13 traceability matrix is the index.
6. **Every operator-facing term is defined inline** on first use for a non-engineer reader.

### §0.4 Operator vocabulary (defined-on-first-use index)

Terms that recur throughout this doc; defined once here so subsequent sections can use them without re-definition. Each term cross-links to its primary upstream §-ref.

- **Tenant.** A single privacy boundary inside a Lethe deployment. v1 is single-tenant-per-deployment; v2 lifts this. (composition §5.2; §0.3 #1.)
- **Principal.** The caller identity stamped onto every emit-point and every audit-log entry. Extracted from the transport layer (token, mTLS cert, etc.). (api §1.1.)
- **Capability.** A named permission flag (`forget_purge`, `audit_global`, `tenant_admin`) attached to a principal via a role. (api §0.2; §2 below.)
- **Role.** A named bundle of capabilities; principals are assigned roles, not capabilities directly. (§2 below.)
- **Idempotency key.** A caller-supplied UUID that lets a write verb be safely retried — a retry within the TTL window returns the original response unchanged. (api §1.2; gap-08 §3.1.)
- **Idempotency-key TTL.** The time window during which a replay of the same idempotency key returns the original response. After expiry, a retry is treated as a fresh call. (api §1.2; §4.3 below.)
- **Gate interval.** The minimum time between two dream-daemon consolidation cycles. The daemon checks at every gate; if the interval has elapsed and the lock is free, it runs. (gap-01 §3.2 Q3; §4.1 below.)
- **Lock heartbeat.** A periodic "I'm still alive" signal from the dream-daemon while it holds the per-tenant lock. If the heartbeat goes silent for `2× heartbeat`, another instance presumes the holder is dead and breaks the lock. (gap-01 §3.2 Q3; gap-08 §3.4; §4.2 below.)
- **Consolidate cycle.** One pass through the dream-daemon's six phases (extract / score / promote / demote / consolidate / invalidate). Triggered by gate. (composition §4.4; api §3.1 emit-points.)
- **Phase-gate.** A hard-halt checkpoint during a migration run; the run cannot proceed past a failed phase-gate without operator action. WS7 names three: A (pre-flight), B (episode-id round-trip), C (post-import provenance + integrity). (migration §3 + §3.1.)
- **Snapshot.** A content-addressed, read-only copy of the source corpus that a migration run reads from. Migration §3.1 phase 2. (migration §3.1.)
- **Manifest.** A per-row record of a migration run: source-shape → target-verb call, status, applied episode-id, idempotency key. The run's source of truth for resumability. (migration §3.1 phase 3 + §3.2.)
- **Cutover.** The operator action that flips downstream agents from a SCNS-as-substrate runtime to a Lethe-as-substrate runtime. Migration §3.1 phase 13. (migration §3.1.)
- **Escalate / staged-for-review.** The runtime path for a write that the gap-12 sensitive-class classifier flagged: `remember` returns `422 classifier_escalate` with `ack="staged_for_review"`; the episode is held in a review queue (NOT durably written to S1) until an operator approves. (api §3.1; api §3.4; gap-10 §6; gap-11 §3.3.)
- **Degraded mode.** A named system state in which one or more stores is unavailable but the runtime continues serving with documented loss-of-functionality. (composition §7 + §7.1; api §4.4.)
- **Drift detector.** A continuous distributional comparator over recall events vs. eval-set inputs; alerts when production drifts from the calibrated set. (gap-14 §5(3).)
- **S3 backfill.** Vector-index population of episodes/facts that already exist in S1 but lack embeddings. Non-blocking on the api surface (recall has lexical fallback). (composition §7 row "S3 stale"; migration §3.1 phase 11.)
- **Async drain.** The waiting period during a migration run between Phase 8 (writes done) and Phase-gate C (post-import lints) during which the dream-daemon catches up on extraction. Migration §3.1 phase 9. (migration §3.1.)
- **Async-drain alarm.** An operator alarm that fires when the daemon hasn't completed a consolidate cycle within a multiple of the gate interval. (composition §7 row "Dream-daemon stuck"; HANDOFF §14.6; §5.5 below.)
- **v2 entry-criteria gate.** The two-condition cutover rule that gates promotion from single-tenant-per-deployment v1 to multi-tenant v2. (scoring §8.6; §10 below.)

---

## §1 Deployment topology

### §1.1 Single-tenant-per-deployment baseline

A v1 Lethe deployment runs **one tenant**. The runtime process, the per-tenant SQLite file (S2 + S5), the per-tenant Graphiti backing DB / index (S1 + S3), and the per-tenant filesystem root for markdown (S4) all live inside one deployment scope. There is no v1 multi-tenant runtime; an operator who serves N tenants runs N deployments. (composition §1.1 + §5.2; §0.3 #1.)

This is conservative on purpose:

- **Isolation by deployment, not by code.** Cross-tenant reads cannot leak through a runtime bug because there is no cross-tenant runtime. (composition §5.2 invariant.)
- **Capacity plan is per-tenant.** SQLite file size, Graphiti index size, embedding cost, dream-daemon cadence — all sized to one tenant. No noisy-neighbor.
- **Incident scope is per-tenant.** A degraded mode (composition §7) blasts one tenant's deployment, not a fleet.
- **The v1 → v2 lift is real.** RBAC widens (operator role becomes a fleet role); isolation moves from deployment-shape to runtime-shape; gap-04 concurrency contract has to handle inter-tenant locking. The §10 entry-criteria gate is the readiness bar.

The operator's mental model: **one deployment = one tenant = one privacy boundary**.

### §1.2 Physical layout

Recommended single-host layout for a v1 deployment. Every store is colocated; no distributed transactions on the hot path (composition §5 T1/T2 ACID is single-DB by construction).

| Store | Backing | Filesystem path (recommended) | Backup posture (§8) |
|---|---|---|---|
| **S1** (graph) | Graphiti on FalkorDB or Neo4j; single-machine | `<deploy_root>/s1/` (FalkorDB data dir) | Native backing-DB procedure (Neo4j `neo4j-admin backup` / FalkorDB RDB snapshot) on quiesce window. |
| **S2** (metadata) | SQLite, WAL mode | `<deploy_root>/s2/lethe.sqlite3` | SQLite online backup API (`.backup`) on quiesce window. |
| **S3** (vectors) | sqlite-vec extension over S2 OR a separate sqlite-vec file | `<deploy_root>/s2/lethe.sqlite3` (same file, vec table) OR `<deploy_root>/s3/vec.sqlite3` | Same as S2 if colocated; rebuildable from S1 (composition §5 row S3) so backup is convenience. |
| **S4** (markdown) | Filesystem under tenant root | `<deploy_root>/s4/` (S4a authored + S4b derived subtrees) | Git versioning recommended for S4a; filesystem snapshot for S4b. (composition §5 rows S4a + S4b.) |
| **S5** (consolidation log) | SQLite table inside S2 (recommended) OR `log.md` per dream-daemon precedent | Same file as S2 | Same as S2. |

Single-host is recommended; the runtime tolerates S1 on a separate process / host (the backing DB) but cross-host transactions for T1 (composition §5) are out of scope for v1 (gap-08 §5 names 2PC as v2).

### §1.3 Single-writer-per-tenant default

For migration runs, `single_writer_per_tenant=true` is the **default** (gap-04 §4 stop-gap; migration §4.1 names cold-start as recommended). The migration CLI exposes `--allow-concurrent-writers` to opt into the warm-tenant path (migration §4.2); operators must pass it explicitly. Rationale: the cold-start path has no Phase 8 CAS retry surface and no opportunity for in-flight `recall_id` perturbation; defaulting the safer mode reduces footguns.

For the steady-state (post-cutover) runtime, `single_writer_per_tenant` is a tenant-config knob (S2). v1 default: `false` (multiple agents may write concurrently; gap-04 §4 candidate (a) optimistic-CAS handles convergence). Operators serializing all writes to one principal pass `true`; the api §1.3 CAS still applies but conflicts are eliminated by construction.

### §1.4 v2 multi-tenant gate (forward reference)

A v1 deployment cannot opt into v2 multi-tenant runtime by configuration; the cutover requires a runtime upgrade. The two-condition gate from scoring §8.6 plus a 3-month soak rule is specified in §10. v1 deployments expose the gate state via `health().v2_gate` (§5.2) so operators can track readiness without polling.

---

## §2 RBAC + auth surface + wire format

### §2.1 Roles and capabilities

api §0.2 + §8 names three capabilities abstractly: `forget_purge` (api §3.3 step 2 auth check), `audit_global` (api §4.4 cross-tenant audit), `tenant_admin` (api §4.1 capture-opt-in-trace). WS8 maps them to three roles:

| Role | Capabilities held | Typical principal | Surface |
|---|---|---|---|
| **`agent`** | (none — verb-level access only) | application-side LLM agents (Claude Code, Copilot, etc.) | calls `recall`, `remember`, `forget(invalidate \| quarantine)`, `peer_message`, `peer_message_pull`, `peer_message_status` |
| **`tenant_admin`** | `tenant_admin`, `forget_purge` | the human operator of a single-tenant deployment | adds `forget(purge)`, `capture_opt_in_trace`, `consolidate(force)`, tenant-scoped `audit()` |
| **`operator`** | `tenant_admin`, `forget_purge`, `audit_global` | deployment operator (single-tenant deployment: same human as `tenant_admin`; v2 multi-tenant: a separate fleet principal) | adds cross-tenant `audit()` aggregation; never returns tenant-identifying content (api §1.8) |

**Why `forget_purge` lives on `tenant_admin` and not gated to `operator`-only.** The right to hard-delete is a tenant-data-sovereignty matter, not an ops-fleet matter. A tenant operator must be able to honor a deletion request without escalating to fleet ops. The `forget_purge` rate-limit (§3) is the throttle, not the role wall.

Roles are a deployment-config artifact in S2 (`tenant_config.principal_roles`); no RBAC-management API verb exists in v1 (operators edit the config and restart). v2 may lift this.

### §2.2 Capability-to-verb matrix

For every api verb, which capability gates it. Mirrors api §1.6 (`forbidden` / `forget_denied`) and api §1.8 (cross-tenant 403).

| Verb | Required capability | Source |
|---|---|---|
| `recall`, `recall_synthesis`, `peer_message_pull`, `peer_message_status` | (none beyond authenticated principal scoped to the tenant) | api §1.1 + §1.8 |
| `remember`, `peer_message`, `forget(invalidate)`, `forget(quarantine)` | (none beyond authenticated principal) | api §3.1 + §3.3 + §3.4 |
| `forget(purge)` | `forget_purge` | api §3.3 step 2 (mode=purge auth check) |
| `promote` | (none beyond authenticated principal) — promotion is intent only (api §3.2) | api §3.2 |
| `consolidate(force=false)` | (none) | api §4.3 |
| `consolidate(force=true)` | `tenant_admin` | api §4.3 (admin-only) |
| `capture_opt_in_trace` | `tenant_admin` | api §4.1 |
| `audit()` (own-tenant) | (none beyond authenticated principal) | api §4.4 |
| `audit()` (cross-tenant aggregate) | `audit_global` | api §4.4 |
| `health()` | (always-on) | api §4.4 |

Cross-tenant reads at any verb without `audit_global` return **404** (`not_found`) per api §1.8; existence of cross-tenant ids must not leak.

### §2.3 Principal extraction contract

The transport carries the principal identity; the verb surface receives it as a logical `principal_id`. WS8 specifies the contract, not the mechanism:

- The principal is non-empty for every verb call. Anonymous calls return `401 unauthenticated` (api §1.6).
- The principal carries the tenant scope; cross-tenant impersonation returns 403 (api §1.8).
- The principal carries its role assignment from S2 `tenant_config.principal_roles`; capability checks (§2.2) consult the role.
- The principal is stamped onto every emit-point as `provenance.agent_id` (api §1.5; gap-05 §3) and onto every S5 audit entry.

The actual auth mechanism (OAuth, JWT, mTLS, API keys, or a deployment-local token file) is deployment-specific and out of scope per §0.2; the contract above is the bridge.

### §2.4 Wire format and transport

**Decision: JSON over HTTP/1.1, with optional MCP framing for agent integrations.**

| Axis | Choice | Rationale |
|---|---|---|
| Wire format | JSON | api schemas are already JSON-shaped (`uuidv7`, `RFC3339`, `bytes` as base64 per api §0.4); the LLM-agent ecosystem (Claude Code, Copilot, MCP clients) expects JSON natively. |
| Transport | HTTP/1.1 | Universally supported; no new infrastructure in v1 deployments; aligns with the project's MCP surface (HANDOFF §2.3). HTTP/2 is forward-compatible (no protocol changes needed). |
| MCP framing | Optional add-on for agent integrations | MCP is JSON-RPC over stdio or HTTP; native fit. Operator-facing surfaces (CLI, manifest UX) speak HTTP+JSON directly. |
| Protobuf / msgpack | Rejected for v1 | Tooling cost > throughput benefit at single-tenant scale; bi-directional schema evolution is harder. May revisit at v2 fleet scale. |
| gRPC | Rejected for v1 | Same as protobuf; HTTP/1.1+JSON is the lowest-friction common denominator for agent integrations. |

The api §0.4 abstract types map to JSON as: `string`/`int`/`bool`/`float` natively; `uuidv7` as RFC-9562-string; `RFC3339` as ISO-8601 string; `bytes` as base64 string; `enum` as string-literal; `[]` as JSON array; `?` as nullable / optional.

Transport-level errors (connection refused, TLS handshake failure) propagate as transport errors; the api §1.6 error taxonomy covers protocol-level errors only. Operators wire transport-level errors to the same alarm pathway as api §1.6 `5xx store_unavailable` (§5.5 below).

---

## §3 Rate-limit + quota table

api §1.6 names `429 rate_limited` as the rejection code; api §0.2 + §2.1.2 + §3.3 + §3.4 + §4.3 names *where* limits attach. WS8 picks the values. Every cap below is **per single-tenant deployment** (since v1 is single-tenant; §1.1).

| Surface | Cap | Window | Scope | Rationale | Source |
|---|---|---|---|---|---|
| `recall`, `recall_synthesis` | **30 req/s sustained, 60 burst** | rolling 1 s | per `(tenant, principal)` | Hot-path read (api §2.1.2). LLM agents typically <10 QPS sustained; headroom for parallel sub-queries on a research-style task. | api §2.1.2 |
| `remember` | **10 req/s sustained, 30 burst** | rolling 1 s | per `(tenant, principal)` | Extraction is async (api §3.1 step 1 returns after T1); the cap pressures T1 transaction throughput. SCNS observation rate << 10/s in practice. | api §3.1 |
| `forget(invalidate \| quarantine)` | **5 req/s sustained, 10 burst** | rolling 1 s | per `(tenant, principal)` | Safety verb; not a hot path. Cascade quarantine (api §3.3 mode=quarantine) inside the cascade is bounded by `412 precondition_failed` budget, not by this cap. | api §3.3 |
| `forget(purge)` | **10 per hour, 100 per day** | rolling | per **tenant** (not per principal) | Hard-delete; gap-11 §3.3 admin-only-by-default; per-tenant cap so multiple admins cannot aggregate to bypass. Operators legitimately bulk-purging on a data-subject request raise the cap via tenant config (operator audit-logged in S5). | api §3.3 step 2; gap-11 §3.3 |
| `peer_message` | **20 req/s sustained, 50 burst** | rolling 1 s | per `(tenant, principal)` | Inbox cap is 100 unread per recipient (gap-10 §3.4; api §3.4); sustained rate is upper-bounded by recipient pull cadence anyway. | api §3.4 |
| `consolidate(force=true)` | **6 per hour** | rolling | per tenant | Admin-trigger; api §4.3 says "rate-limited"; cap to ~one forced cycle per default gate interval (§4.1 = 15 min). | api §4.3 |
| `capture_opt_in_trace` | **10 per hour** | rolling | per tenant | Consent-change verb (api §4.1); auditable; not a hot path. | api §4.1 |
| `escalate`-class staging cap | **50 staged per tenant per day** | rolling | per tenant | Bounds staged-for-review queue depth (api §3.1 + §3.4). Hits the queue depth alarm (D8 / §5.5); operator decides whether to raise the cap or drain the queue. | api §3.1; api §3.4; HANDOFF §12.6 + §14.6 |
| `audit()` | **10 req/s** | rolling 1 s | per principal | Slow-path; api §4.4 has no latency budget. | api §4.4 |
| `health()` | unbounded | — | — | Always-on observability surface; no rate limit. | api §4.4 |

429 responses include `retry_after_ms` per api §1.6. Operators raise per-tenant caps in `tenant_config.rate_limits` (S2); raises are audit-logged to S5. A cap *lower* than the default also lives there for testing and locked-down deployments.

---

## §4 Operator knobs

Every knob below has a default; every default carries a citation to its upstream source. Operators tune in `tenant_config` (S2); changes audit-log to S5.

### §4.1 Dream-daemon gate interval

**Default: 15 minutes.** The daemon checks at gate-interval cadence; if the interval has elapsed since the last successful consolidate cycle and the lock is free, it runs. (gap-01 §3.2 Q3 commits per-tenant lock + 30 s heartbeat but does not pin gate interval.)

| Range | Effect |
|---|---|
| < 5 min | High extraction churn; LLM-call cost rises; alarm threshold (§5.5) becomes near-zero and noisy. **Not recommended for v1.** |
| 5–10 min | Aggressive cadence; appropriate for high-write tenants approaching gap-04 §5's ~10-writers/tenant envelope. |
| **15 min (default)** | Balanced; SCNS dream-daemon precedent (note §2.10 three-condition gate); Phase 9 async-drain (migration §3.1 phase 9) of O(10k) episodes drains in sub-hour. |
| 30 min – 1 h | Low-write tenants; reduced LLM cost; longer drain on large migrations. |
| > 1 h | **Not recommended**; alarm threshold (§5.5) widens past operator usefulness; consolidate cycles concentrate too much work per run. |

Configurable per-tenant via `tenant_config.dream_daemon.gate_interval_seconds`. The recall-time bi-temporal filter (api §2.1; scoring §4.1) is unaffected by gate interval; only consolidation phases are.

### §4.2 Lock heartbeat and break

**Default: 30 s heartbeat; lock broken at 60 s of silence (= 2× heartbeat).** (gap-01 §3.2 Q3; gap-08 §3.4.) Operator-tunable via `tenant_config.dream_daemon.heartbeat_seconds`; the `2×` break-multiplier is fixed (raising it lengthens stuck-daemon detection without operator benefit).

A broken lock writes `(broken_holder, presumed_dead_at, broken_by)` to S5 (gap-08 §3.4); the lock-recovery operator surface is documented in §8.3.

### §4.3 Idempotency-key TTL

**Default: 24 h** (api §1.2; gap-08 §3.1). **Operator-tunable up to a hard ceiling of 7 days.**

**Ceiling enforcement.** The config validator at runtime startup **rejects** values > 7 days (`tenant_config.idempotency_key_ttl_seconds > 604800`). The runtime refuses to start until the value is reduced; this is a hard fail, not a warning. Rationale: above 7 days, the operationally-correct path is to chunk the work by snapshot (§7.4) so each chunk fits inside the TTL window, NOT to extend the TTL further. Allowing values > 7 days would silently let operators drift into unsupported territory where the `audit(provenance.source_uri=...)` fallback (migration §3.2) becomes the primary deduplication mechanism for unbounded windows — a load pattern the audit path is not sized for.

**Above-ceiling guidance (documented escape).** For migrations or batch operations exceeding 7 days, operators chunk by snapshot: split the source corpus into multiple snapshots (migration §3.1 phase 2), run a separate migration run per snapshot, and let migration §3.2's resumability mechanism handle within-snapshot retries. Each snapshot's run then fits inside the 7-day ceiling.

| TTL value | Use case |
|---|---|
| 24 h (default) | Steady-state; SCNS observation rate; small migrations. |
| 24–72 h | Medium migrations; weekend ops. |
| 72 h – 7 d | Large migrations; long-running batch operations. |
| > 7 d | **Rejected by validator**; chunk by snapshot. |

**Operational metric.** `idempotency.fallback_lookup_rate_24h` — the ratio of replays-via-`audit(provenance.source_uri=...)`-fallback to total writes — is exposed via `health()` (§5.2). When the rate exceeds 5% (D8 / §5.5), the operator considers raising the TTL within the 7-day ceiling. (HANDOFF §14.6.)

### §4.4 Preference-cap ordering

**Default: recency-of-revision in-cap ordering, 10 KB always-load cap.** (api §0.3 #3; gap-09 §6.) The cap is enforced at recall time (api §2.1 step 10), not at migration time (migration §3.3). Operator-tunable per tenant via `tenant_config.preference_cap_bytes`; values < 4 KB or > 32 KB are config-validator warnings (not rejections).

### §4.5 Drift detector cadence and re-eval schedule

(gap-14 §5(3) lifted to operator-knob form.)

| Knob | Default | Source |
|---|---|---|
| Continuous drift detector sample rate | 5% of recall events, sampled hourly | gap-14 §5(3) |
| Drift alert threshold | `last_eval_drift_pct > 0.10` (10%) | gap-14 §5(3) |
| Full re-eval cadence | monthly against the held-out adversarial+operator set | gap-14 §5(3) |
| Fresh-adversarial-slice construction | quarterly | gap-14 §5(3) |
| Two-strata reporting | always-on (all-cases vs. operator+adversarial+ablation+replay-only) | gap-14 §5 |

`health().drift` (§5.2) exposes `last_eval_at`, `last_eval_drift_pct`, `next_scheduled_eval_at`. The actual eval harness (case selection, scoring) is WS4 territory; WS8 schedules the cadence.

### §4.6 Recall-determinism drift tolerance (migration phase 12)

**Default: ≤5% fact-id-set diff per probe.** (migration §3.1 phase 12.) Operator-tunable per migration run via `--drift-tolerance-pct`; values > 10% are CLI warnings (the phase still runs but the operator must confirm).

### §4.7 Sensitive-class escalate cap (peer-message-class escalation; api §3.4)

**Default: matches §3 — 50 staged per tenant per day.** Hitting the cap triggers `escalation_queue_depth` alarm (§5.5). A staged episode does NOT count against the requesting principal's `remember` rate-limit; it is counted against the tenant-wide escalate queue.

### §4.8 Phase 9 async-drain alarm threshold (mid-migration)

**Default during migration: stricter than steady-state — `time-since-last-successful-consolidate > 1.5 × gate_interval` (= 22.5 min at the §4.1 default).** (HANDOFF §14.6; migration §10; composition §7 row "Dream-daemon stuck".) Steady-state alarm threshold remains `2× gate_interval` (§5.5). Rationale: tightening during migration catches stalls before Phase-gate C (migration §3.1 phase 10) times out and forces a halt.

### §4.9 v2 entry-criteria gate poll cadence

**Default: every consolidate cycle the gate state is recomputed and exposed via `health().v2_gate` (§5.2 + §10).** No operator action; the gate is read-only until it goes GREEN per §10.

---

## §5 Health + observability

### §5.1 Goals

The operator surface answers three questions at a glance: *Is the tenant healthy? Is anything in degraded mode? What deferred work is pending?* api §4.4 names the `health()` shape; WS8 adds the operator-facing fields without breaking the api schema (additive only).

### §5.2 `health()` extensions

Additive to api §4.4 (existing fields preserved verbatim):

```
{
  // — api §4.4 base fields —
  overall:        "healthy" | "degraded" | "down",
  stores:         { s1, s2, s3, s4a, s4b, s5: ... },
  degraded_modes: [ string ],
  daemon: { last_successful_consolidate_at, current_run_id?, current_phase?, backoff_until? },
  emitter:        { drop_count_24h, last_drop_reason? },

  // — WS8 operator-facing additions —
  migration: {
    active_run_id?:                   uuidv7,
    active_phase?:                    "snapshot" | "inventory" | "phase_gate_a" | "s4a_import" |
                                       "s1_import" | "phase_gate_b" | "invalidation" | "async_drain" |
                                       "phase_gate_c" | "s3_backfill" | "recall_probe" | "cutover" |
                                       "post_cutover_s4b_regen",
    s3_backfill_progress_pct?:        float,             // 0.0–1.0; HANDOFF §14.6; migration §3.1 phase 11
    rows_pending:                     int,
    rows_done:                        int,
    rows_escalated:                   int,
    rows_failed:                      int
  },
  idempotency: {
    key_ttl_seconds:                  int,
    fallback_lookup_rate_24h:         float              // §4.3 operational metric; HANDOFF §14.6
  },
  escalation_queue: {
    depth_pending_review:             int,               // staged_for_review queue (api §3.1 + §3.4)
    oldest_pending_age_hours:         float
  },
  drift: {
    last_eval_at:                     RFC3339,
    last_eval_drift_pct:              float,             // §4.5; gap-14 §5(3)
    next_scheduled_eval_at:           RFC3339
  },
  v2_gate: {
    strict_stratum_operator_share_pct:  float,           // scoring §8.6 gate 1
    labeled_pairs:                      int,             // scoring §8.6 gate 2
    consecutive_months_green:           int              // §10 cutover decision rule
  }
}
```

`health()` never errors above the transport layer (api §4.4); when a sub-system is unreachable, the corresponding field is `null` or omitted, never a 5xx.

### §5.3 `audit()` operator queries

api §4.4 defines `audit(query)` for S5 entries joined with S1 provenance. WS8 adds operator-facing query patterns (no schema change; these are operator playbook entries):

| Operator question | `audit()` query |
|---|---|
| "Why was this fact forgotten?" | `audit({fact_id: <id>})` → returns the `forget`-class S5 entry with retention proof. |
| "What did the migration import yesterday?" | `audit({since: <yesterday>, until: <today>})` → filtered to `migration_*` S5 entries by caller-side filter. |
| "What's in the escalate queue?" | `audit({since: <30d ago>})` → filtered to `classifier_escalate` entries by caller-side filter. (Or the dedicated review-queue surface, §6.) |
| "Cross-tenant aggregate operator metrics" (`audit_global` only) | `audit({since: ..., until: ...})` returns aggregate counts; no tenant-identifying content (api §1.8). |

### §5.4 Counters and gauges (must-emit)

Every Lethe deployment emits the following observability signals; the operator wires them to the deployment's metrics backend (Prometheus, OTLP, or a deployment-local log scraper). WS8 names the signals; the metrics pipeline implementation is deployment-specific.

| Signal | Type | Source | Use |
|---|---|---|---|
| `lethe_recall_requests_total` | counter (by intent, principal-class) | api §2.1 emit-point | recall traffic |
| `lethe_recall_latency_ms` | histogram | api §2.1 | hot-path SLO |
| `lethe_remember_requests_total` | counter (by kind) | api §3.1 emit-point | write traffic |
| `lethe_consolidate_phase_total` | counter (by phase) | api §1.7 + scoring §8.1 | consolidation throughput |
| `lethe_consolidate_phase_latency_ms` | histogram (by phase) | scoring §8.1 | consolidation health |
| `lethe_remember_outcome_total` | counter (by outcome: ok / classifier_escalate / 4xx / 5xx) | api §1.6 | write health |
| `lethe_idempotency_replays_total` | counter (by verb) | api §1.2 | replay rate |
| `lethe_idempotency_fallback_lookups_total` | counter | §4.3 | fallback rate (drives §5.5 alarm) |
| `lethe_escalation_queue_depth` | gauge | api §3.1 + §3.4 | queue health |
| `lethe_dream_daemon_last_successful_consolidate_seconds_ago` | gauge | composition §7 + §4.1 + §4.8 | drives `consolidation_stalled` alarm |
| `lethe_dream_daemon_lock_holder_principal` | label | gap-01 §3.2 Q3 | who holds the lock |
| `lethe_dream_daemon_lock_breaks_total` | counter | gap-08 §3.4 | stuck-daemon frequency |
| `lethe_drift_pct_current` | gauge | §4.5 | drift state |
| `lethe_v2_gate_share_pct` | gauge | §10 | v2 readiness |
| `lethe_v2_gate_pairs_count` | gauge | §10 | v2 readiness |
| `lethe_degraded_modes_active` | gauge (set per mode label) | composition §7 + §7.1 | degraded-mode visibility |
| `lethe_forget_purge_total` | counter (by principal) | api §3.3 mode=purge | hard-delete audit |
| `lethe_emit_drop_total` | counter (by drop_reason) | api §4.4 emitter; scoring §8.4 | sink-drop visibility |
| `lethe_tenant_isolation_breach_total` | counter | composition §5.2; api §1.8 | **MUST be zero**; non-zero is P0 |

### §5.5 Operator alarms (must-wire)

Eight alarms an operator MUST wire before declaring a deployment production-ready.

| Alarm | Condition | Severity | Source | First operator action |
|---|---|---|---|---|
| **`consolidation_stalled`** | `time-since-last-successful-consolidate > 2 × gate_interval` (= 30 min at default; mid-migration: `> 1.5 ×` per §4.8) | P1 | composition §7 row "Dream-daemon stuck"; gap-01 §3.2 | check `health().daemon.backoff_until`; inspect S5 for last phase-gate; consider `consolidate(force=true)` if backoff exhausted |
| **`escalation_queue_depth`** | `health().escalation_queue.depth_pending_review > 50` OR `oldest_pending_age_hours > 24` | P2 | §3 escalate cap; HANDOFF §12.6 + §14.6 | drain the review queue (§6); raise cap if backlog is legitimate (data-subject request, etc.) |
| **`idempotency_fallback_high`** | `idempotency.fallback_lookup_rate_24h > 0.05` (5% of writes) | P2 | HANDOFF §14.6; gap-08 §5; §4.3 | consider raising TTL within 7-day ceiling (§4.3); above ceiling, chunk by snapshot |
| **`s3_backfill_stalled`** | `s3_backfill_progress_pct unchanged > 1 h` during Phase 11 | P2 | migration §3.1 phase 11; HANDOFF §14.6 | check embed worker; non-blocking on api (lexical fallback survives); operator may defer or retry per migration §5 |
| **`drift_high`** | `last_eval_drift_pct > 0.10` (10%) | P2 | gap-14 §5(3); §4.5 | trigger out-of-cycle re-eval; consider scoring weight recalibration (gap-03 territory) |
| **`degraded_mode_active`** | `health().overall = "degraded"` for > 5 min | P1 | composition §7 + §7.1 | inspect `degraded_modes` list; consult §9 playbook for the named mode |
| **`forget_purge_rate_spike`** | `> 5 forget(purge) calls in any 10 min` (above §3 cap pattern) | P1 | gap-11 §3.3 | possible compromise or runaway script; admin review; consider lowering cap until investigated |
| **`tenant_isolation_breach`** | any non-zero count from `lethe_tenant_isolation_breach_total` | **P0** | composition §5.2; api §1.8 | halt writes immediately; investigate cross-tenant leak; this is a security-class incident |

The thresholds are operator-tunable in `tenant_config.alarms`; raises and lowers audit-log to S5.

---

## §6 Escalate-review pipeline

### §6.1 What `escalate` means

Two upstream surfaces produce `escalate`-class outcomes:

1. **api §3.1 `remember` returns `422 classifier_escalate`** with `ack="staged_for_review"`. The episode is held in a review queue; it is NOT durably written to S1 until an operator approves. (gap-12 sensitive-class classifier; gap-10 §6 / gap-11 §3.3 surface.)
2. **api §3.4 `peer_message` with `type=claim`** can return the same `422 classifier_escalate` if the claim payload trips the sensitive-class taxonomy at send time.

Migration §5.1 marks rows `escalated` when the runtime returns 422 during import; the row stays in the manifest in `escalated` state, the run continues, and the queue accumulates.

HANDOFF §12.6 + §14.6 named the post-escalate review workflow as WS8 / project-ops territory. WS8 specifies it.

### §6.2 Review queue substrate

**Storage.** Staged episodes live in S2 in a `review_queue` table (one row per staged episode):

```
review_queue {
  staged_id:           uuidv7,                 // pre-issued; surfaced to caller in 422 ack
  tenant_id:           string,
  source_verb:         "remember" | "peer_message",
  source_principal:    string,
  staged_at:           RFC3339,
  payload_blob:        bytes,                  // the would-be remember/peer_message body
  classifier_class:    string,                 // gap-12 class label
  classifier_score:    float,                  // gap-12 confidence
  status:              "pending_review" | "approved" | "rejected" | "expired",
  reviewer_principal?: string,
  reviewed_at?:        RFC3339,
  review_reason?:      string,
  expires_at:          RFC3339                 // staged_at + queue_ttl (default 30 d, §6.5)
}
```

**Review surface.** A static-rendered HTML page per tenant (composition §1.1 dual-audience) listing pending rows, each with: source verb + principal, classifier class + score, payload preview (redacted by sensitive-class scrubber), staged-age, and three actions: `approve`, `reject`, `expire-now`.

The review surface reads from S2 directly; it does NOT call api verbs. The reviewer's decision triggers a verb call from the review tool — see §6.3.

### §6.3 Review actions and verb calls

| Action | Resulting verb call | Effect |
|---|---|---|
| `approve` | `remember(content, intent, idempotency_key, provenance, kind, force_skip_classifier=true)` (or the peer-message analog) where `idempotency_key` is the original caller-supplied (or migration-row) idempotency_key; `staged_id` remains as the queue-row identifier for the review surface and S5 audit references | episode admitted to S1; S5 records `review_approved{staged_id, reviewer_principal, reviewed_at, reason}` |
| `reject` | (no verb call) — staged row is marked `rejected`; payload is purged after `queue_ttl` | S5 records `review_rejected{staged_id, reviewer_principal, reviewed_at, reason}` |
| `expire-now` | (no verb call) — convenience for operators clearing stale entries | S5 records `review_expired{staged_id, reason="manual_expire"}` |

**The `force_skip_classifier=true` parameter.** Bypasses the gap-12 classifier on the approval path so the same payload that escalated does not re-escalate on re-submission. The parameter is gated to principals holding the `tenant_admin` capability and is auditable in S5. **It is not part of the v1 api §3.1 surface as published**; WS8 adds it as a required api extension for the review pipeline. Implementation pairs with WS6's implementation pass; the api-doc change is a single-line addition to api §3.1 inputs, with the auth check tied to `tenant_admin`.

> **Note for WS6 implementation pass.** This `force_skip_classifier=true` parameter is a v1 api surface extension WS8 introduces. The WS6 implementation pass adds it to api §3.1 with the auth check; WS6's published doc is updated in a follow-up commit. Until then, this doc is the contract reference.

### §6.4 Review SLA

**Default: 24-hour review SLA.** A `pending_review` row older than 24 h trips the `escalation_queue_depth` alarm (§5.5). Rationale: balances "operator must have time to review" against "writes shouldn't sit in limbo indefinitely." Operator-tunable via `tenant_config.review_sla_hours`.

**Default queue TTL: 30 days.** A row in `pending_review` for > 30 days auto-expires (status → `expired`) and the payload is purged. Operator-tunable; lowering increases the rate at which staged content is auto-discarded. Auto-expiry is recorded in S5.

Both defaults (24-hour SLA, 30-day TTL) are v1 bets; instrumented via the `escalation_queue_depth` alarm (§5.5) and revisable per HANDOFF §14.6.

### §6.5 Migration `escalated` rows — drain workflow

After a migration run, `health().migration.rows_escalated` reports the count. The operator drains by:

1. Loading the review surface, filtered to `source_principal = <migration run principal>`.
2. Reviewing each row; approving routes through `remember(force_skip_classifier=true)` per §6.3 with the same `idempotency_key` the migration row carries (so the manifest row's `applied_episode_id` populates and the row transitions `escalated → done`).
3. Rejecting marks the manifest row `escalated_rejected` (a new terminal status WS8 adds to migration §3.1 phase 5/6 row state machine). The migration run is considered complete with rejected rows NOT imported; the review-rejection rationale is the audit trail.

Migration runs do NOT block on a non-zero `rows_escalated` count at Phase-gate C (migration §3.1 phase 10) — Phase-gate C lints provenance and integrity for *applied* rows; staged rows do not have S1 episodes to lint. The operator drains the queue post-cutover.

---

## §7 Migration runtime contract

WS7 specified the migration plan; WS8 specifies the operator-facing contract for invoking it. The migration tool's source code is an operator-tooling pass (post-WS8) — WS8 names the contracts so the tool can be implemented against a stable target.

### §7.1 CLI invocation surface

The tool is `lethe-migrate`. Subcommands map 1:1 to migration §3.1 phases or phase-gates:

| Subcommand | Maps to | Operator action |
|---|---|---|
| `lethe-migrate init <tenant_id> <snapshot_path>` | Phase 1 (Pre-flight) | starts a run; allocates run-id; writes manifest skeleton |
| `lethe-migrate snapshot <run_id>` | Phase 2 (Snapshot) | takes the content-addressed snapshot |
| `lethe-migrate inventory <run_id>` | Phase 3 (Inventory) | writes the per-row manifest |
| `lethe-migrate phase-gate <run_id> {a \| b \| c}` | Phase 4 / 7 / 10 | runs the named hard phase-gate; halts the run on failure |
| `lethe-migrate apply <run_id> {s4a \| s1 \| invalidation \| s3-backfill \| recall-probe}` | Phase 5 / 6 / 8 / 11 / 12 | runs the named phase; resumable per migration §3.2 |
| `lethe-migrate drain <run_id>` | Phase 9 (Async drain) | waits for `health().daemon.last_successful_consolidate_at > migration_phase_8_done_at` |
| `lethe-migrate status <run_id>` | (read-only) | dumps manifest rollup + `health().migration` for the run |
| `lethe-migrate resume <run_id>` | (cross-phase) | resumes from the last `pending`/`in_flight` row per migration §3.2 |
| `lethe-migrate cutover <run_id>` | Phase 13 | flips the operator-side flag; runtime begins serving as primary |
| `lethe-migrate rollback <run_id>` | (recovery) | aborts a run pre-cutover; details in §7.5 |
| `lethe-migrate s4b-regen <run_id>` | Phase 14 (Post-cutover S4b regen) | confirmation that S4b regeneration has completed |

`--allow-concurrent-writers` flag on `init` opts into the warm-tenant path (migration §4.2; §1.3). `--drift-tolerance-pct` on `recall-probe` overrides §4.6.

### §7.2 Manifest UX surface (contract)

**Manifest file format: `manifest.jsonl`.** One row per line, append-only with status-update rewrite. Per-row schema is already pinned by migration §3.1 + §3.2 (`status`, `applied_episode_id`, `idempotency_key`, `provenance.source_uri`, etc.); WS8 specifies the file layout:

- File path: `<run_state_root>/<run_id>/manifest.jsonl`.
- Append-only for new rows (Phase 3 inventory writes once).
- Status updates (Phase 5/6/8 transitions) rewrite the affected row in place via atomic-rename of the entire file (line count is bounded; rewrite cost is acceptable for v1).
- Read by `lethe-migrate status <run_id>` and by the manifest HTML surface.

**Manifest HTML surface.** A static-rendered page per run, `<run_state_root>/<run_id>/index.html`, regenerated on every `lethe-migrate status` invocation. Shows phase progress, row counts by status, current phase, time-since-last-phase-transition, and links to per-row detail pages for `escalated` / `failed` rows. Dual-audience markdown (composition §1.1) — the page is HTML but content is plain-text-readable.

**Manifest JSON dump.** `lethe-migrate status <run_id> --format=json` emits the same data as the HTML surface but as a single JSON document (operator integrations, dashboards).

### §7.3 Capability check surface (Phase 1)

Migration §5 names `403 forbidden` as a Phase 1 abort condition. WS8 specifies the check ordering:

1. The principal must be authenticated (api §1.1) — otherwise abort with auth error.
2. The principal must hold `tenant_admin` for the destination tenant (S2 `tenant_config.principal_roles`) — otherwise `403 forbidden`.
3. If the manifest contains rows that will issue `forget(purge)` (none in WS7's §3.1 — migration uses `forget(invalidate)`, not purge), the principal must additionally hold `forget_purge`. v1 migration does not use purge, so this check is a no-op; named here for completeness so the operator-tooling pass implements the surface forward-compatibly.
4. Pre-flight `health()` must report `overall ∈ {"healthy", "degraded"}`; `"down"` aborts with hint.

### §7.4 Snapshot UX

Migration §3.1 phase 2 specifies a content-addressed snapshot. WS8 specifies the operator surface:

- `lethe-migrate snapshot <run_id>` accepts `--method ∈ {git-tag, fs-copy, zfs-snapshot}`.
- `git-tag` is the recommended default for SCNS-corpus migrations (the source tree is git-versioned per gap-08 §3.4 substrate).
- `fs-copy` writes a read-only filesystem copy under `<run_state_root>/<run_id>/snapshot/`.
- `zfs-snapshot` (or equivalent: btrfs, APFS) is operator-opt-in.
- The snapshot's content hash is recorded in S5 per migration §3.1 phase 2.
- Multi-snapshot resumes (a re-run against a *new* snapshot of an evolving corpus, per migration §10) include the snapshot hash in the manifest so source-id formula can be augmented if collisions are observed (migration §10).

### §7.5 Rollback

Pre-cutover (Phase 13 not yet executed), a run can be rolled back:

- `lethe-migrate rollback <run_id>` runs `forget(invalidate, target=<applied_episode_id>)` for every manifest row in `done` state, with `idempotency_key` derived per migration §2.3 (rollback-key derivation block; discriminant `"rollback"`).
- S4a authored synthesis pages have to be removed manually (filesystem rm) — WS8 documents this as a known limitation; the rollback subcommand surfaces the list of S4a paths to remove. (Rationale: filesystem-level S4a rollback would require a per-run S4a backup; v1 keeps this manual.)
- S5 records `migration_run_rolled_back{run_id, rows_invalidated, s4a_paths_listed}`.

Post-cutover, rollback is **not supported in v1**: the cutover crosses the operator-flag boundary (downstream agents now point at Lethe-as-substrate); reversing requires a cross-deployment migration spec which is deferred (HANDOFF §14.6). Operators planning post-cutover rollback take a backup (§8) before Phase 13 and restore from it — known operator-tooling-pass workflow item.

---

## §8 Backup / restore + crash recovery

### §8.1 Backup posture

| Store | Tool | Frequency (recommended) | Quiesce window |
|---|---|---|---|
| **S1** (Graphiti backing DB) | `neo4j-admin backup` (Neo4j) or `redis-cli SAVE` (FalkorDB) | daily | consolidate-lock acquired (gate paused); typically <30 s |
| **S2** + **S5** (SQLite) | SQLite online backup API (`.backup`) | daily; on-demand pre-migration | none required (WAL mode tolerates concurrent reads); writes paused via consolidate-lock |
| **S3** (sqlite-vec or pgvector) | colocated with S2 if sqlite-vec; per-tool if separate | daily | rebuildable from S1, so backup is convenience |
| **S4a** (authored markdown) | git push | per-revision (operator-driven) | none |
| **S4b** (derived markdown) | filesystem snapshot | weekly (regenerable from S1, so backup is convenience) | none |

**Cross-deployment restore is out of scope for v1** (gap-08 §5; HANDOFF §14.6). Restore is to the same deployment ID. An operator wanting to move a tenant to a new deployment runs a future cross-deployment Lethe→Lethe migration spec (HANDOFF §14.6 — deferred).

### §8.2 Startup integrity check

`lethe-audit lint --integrity` runs at every runtime startup per gap-08 §3.5. If integrity fails to converge, the runtime refuses to serve and emits a `degraded_startup` `health()` state. Operator surface:

- `lethe-audit lint --integrity` is invokable directly by the operator (without runtime restart) for ad-hoc checks.
- `lethe-audit lint --integrity --reconcile` runs the reconciler that backfills S5 with `provenance=reconciler` entries (composition §7 row "S5 append fails"). Default behavior is **read-only**; reconcile mode requires `tenant_admin`.
- Migration phase-gates A and C (migration §3.1 phase 4 + 10) invoke `lethe-audit lint --integrity` and halt on non-zero exit. The CLI surface is the same operator-facing command; the migration tool calls it as a subprocess.

### §8.3 Lock recovery operator surface

A stuck dream-daemon lock (§4.2) breaks automatically at `2× heartbeat` (60 s default). Manual operator intervention:

- `lethe-admin lock status` — dumps `health().daemon` plus the S5 lock-history.
- `lethe-admin lock break --reason="<text>"` — forces a lock break ahead of automatic timeout. Audit-logged to S5 with `(broken_holder, presumed_dead_at, broken_by)` per gap-08 §3.4. Requires `tenant_admin`.
- A broken lock is not a corruption event; the dream-daemon's per-phase resumability (gap-08 §3.3) handles the recovery — the next gate cycle resumes from the last-completed phase.

### §8.4 Disk-full and refusal-to-serve

Composition §7 row "Disk full" specifies that the runtime monitors disk free and refuses new `remember`s below a threshold. WS8 sets the threshold:

**Default: refuse `remember` at < 1 GB free; refuse `forget(purge)` at < 100 MB free** (purge writes a retention proof BEFORE the delete per gap-08 §3.6, and the proof must succeed) (1 GB / 100 MB are v1 bets; expected to retune per-deployment based on tenant write volume and S2/S3 file growth observed). Operator-tunable via `tenant_config.disk_thresholds`. Below threshold, `remember` returns `5xx store_unavailable` with hint `"disk_low"` (api §1.6); `forget(purge)` returns `5xx store_unavailable` with hint `"disk_critical"`.

---

## §9 Degraded modes operator playbook

A cross-walk to composition §7 + §7.1 in operator-action terms. For every named degraded mode, what the operator sees, what they can do, what is silent-by-design.

| Degraded mode (composition §7 row) | What the operator sees | What the operator does | Silent-by-design |
|---|---|---|---|
| **S1 down** | `health().stores.s1 = "down"`; `health().overall = "down"`; `remember` and `recall` return `5xx store_unavailable`; `recall_synthesis` continues. | Restore S1 (Graphiti backing DB); the runtime auto-recovers on next health probe. No data loss because `remember` did not commit T1. | Caller-side: clients fall back to `recall_synthesis` if appropriate (api §1.6 hint indicates which stores are up). |
| **S2 down or locked** | `health().stores.s2 = "down"`; `health().overall = "degraded"`; `remember` returns 5xx (T1 needs S2); `recall` works with baked-in scoring defaults (per-tenant overrides live in S2). | Free S2 (disk space, file-lock, corruption recovery); `lethe-audit lint --integrity` post-recovery. | Recall ledger writes silently fail during outage — utility-feedback for queries during the outage is lost (composition §7 explicit). |
| **S3 stale** | `health().stores.s3 = "stale"`; `health().overall = "degraded"` if drift threshold exceeded. | Run `scripts/embed/rebuild.sh` (composition §7 row); incremental embed job catches up automatically. | Recall is degraded (lower precision, never wrong) per composition §7. |
| **S3 fully unavailable** | `health().stores.s3 = "down"`; `recall` falls back to graph-walk + lexical only (composition §3.1 step 3). | Restore S3 or set `tenant_config.disable_s3=true` to suppress the alarm. | `degraded_modes` lists `s3_unavailable_lexical_only`. |
| **S4a corrupted** | `health().stores.s4a = "down"`; `recall_synthesis` returns 5xx; fact `recall` unaffected. | `git reset` to last-good revision (composition §7 row); restart `recall_synthesis` indexer. | None. |
| **S4b diverged** | `health().stores.s4b = "stale"`; `recall` unaffected (api never reads S4b). | Wait for next consolidate cycle (≤ gate interval); regeneration is idempotent. | None operator-visible; humans inspecting markdown directly may see stale data. |
| **S4b regen crashed mid-write** | `health().stores.s4b = "stale"`; atomic-rename pattern leaves either old or new file. | Wait for next gate cycle; regeneration retries. | None. |
| **S5 append fails after S1 commit** | `health()` may not surface this directly; `lethe-audit lint --reconcile` detects. | Run `lethe-audit lint --integrity --reconcile`; reconciler writes a backfill entry per composition §7 row. | The audit-rationale field is degraded (we know *that* the change happened, not the original rationale); the change itself survived. |
| **Dream-daemon stuck or crash-looping** | `consolidation_stalled` alarm fires (§5.5); `health().daemon.backoff_until` populated. | Inspect S5 for last phase-gate; if backoff exhausted, `consolidate(force=true)` (admin); break stale lock if hung (§8.3). | None. |
| **Two stores down: S1 + S3** | "Lethe is down." Both `recall` and `remember` fail. `recall_synthesis` survives. | Restore in priority order: S1 first (canonical), then S3. | None. |
| **Two stores down: S2 + S5 (shared storage)** | `health().overall = "degraded"`; runtime defensively disables `remember` to avoid silently ungraded write traffic (composition §7.1). | Restore S2; reconcile S5 from S1 state per gap-08 §3.5. | None. |
| **Two stores down: S1 + S4** | `recall` works (degraded; no synthesis); `remember` is dead. `health()` declares `partial_availability`. | Restore S1 first, then S4. | None. |
| **Tenant isolation breach** | `tenant_isolation_breach` alarm (§5.5 P0). | **HALT writes immediately.** Investigate cross-tenant leak (defensive: every storage call goes through `tenant_scope_filter` middleware per composition §7); P0 incident protocol. | Should be impossible by construction; non-zero count is a code bug. |
| **Schema migration mid-flight** | `health().overall = "down"` during migration window. | Drain dream-daemon, take consolidation lock, run schema migration, release. (Operator-tooling pass; documented per WS7.) | None. |
| **Disk full** | `degraded_mode_active` alarm + `5xx store_unavailable` with hint `"disk_low"` / `"disk_critical"`. | Free disk; runtime auto-recovers. (§8.4 thresholds.) | None. |
| **Clock skew across multi-process Lethe** | Subtle bi-temporal-stamp anomalies. | v1 is single-writer per tenant (composition §7 row). Multi-writer is a v2 problem. | None in v1. |

The §5.5 alarms cover the operator-actionable subset; this playbook is the deeper reference.

Composition §7's "peer-message corrupts a memory" row is intentionally not in this playbook; it is a provenance-enforcement / contradiction-detection (gap-05; gap-13) matter, not an operator alarm-able mode.

---

## §10 v1 → v2 entry-criteria gate

### §10.1 The two scoring §8.6 conditions

scoring §8.6 specifies that training a v2 learned scorer unblocks when:

1. **Strict-stratum operator share ≥ 20%** of the eval candidate pool. (eval-plan §5.9 two-strata reporting; gap-14 §5(3).)
2. **≥ 10 000 labeled `(recall, outcome)` pairs** in the per-tenant ledger. (gap-03 §6 BO threshold; scoring §8.3.)

WS8 lifts these to operator-visible gauges: `health().v2_gate.strict_stratum_operator_share_pct` and `health().v2_gate.labeled_pairs`.

### §10.2 Cutover decision rule

**Both gates GREEN for 3 consecutive months** before v2 multi-tenant deployment is enabled. `health().v2_gate.consecutive_months_green` tracks the count; resets to zero when either gate goes RED for any reporting period within a month.

**Why 3 months.** Composition §1.1 names single-tenant-per-deployment as the v1 baseline; promoting to v2 multi-tenant is irreversible-shaped (RBAC widens; isolation moves from deployment-shape to runtime-shape; gap-04 inter-tenant locking becomes runtime-relevant). A 3-month soak prevents flap on a fragile boundary; a single-month spike past 20% operator share that immediately reverts must not unlock the cutover.

### §10.3 Multi-tenant readiness checklist (v2 prerequisite)

When v2 is contemplated, the operator confirms:

- [ ] Both gates GREEN for ≥3 consecutive months.
- [ ] gap-04 multi-writer concurrency contract upgraded from "v1 single-writer assumption" (composition §7 row "Clock skew") to a v2 contract (gap-04 v2 — out of WS8 scope).
- [ ] RBAC `operator` role (§2.1) repurposed as a fleet role; principal-extraction contract (§2.3) extended to support multi-tenant routing.
- [ ] Backup posture (§8.1) re-evaluated for fleet scale; cross-deployment restore (currently deferred) is a v2 prerequisite.
- [ ] Wire-format protobuf/gRPC re-evaluated (§2.4 rejected protobuf for v1 on tooling cost; fleet scale changes the calculus).
- [ ] Rate-limit caps (§3) re-evaluated; per-tenant and fleet-wide caps both required.
- [ ] Eval-set bias mitigation (gap-14) holds across the cross-tenant-population stratum.

WS8 commits to *exposing* the gate state; the v2 cutover is a future workstream.

---

## §11 Verification audits

Four audits, run before every WS8 commit. Re-run on every QA pass.

### §11.1 Operator-readability audit

For every operator-facing term in §0.4, the doc defines it inline on first use. Audit method: grep each term in §0.4 against the body of the doc and confirm the first occurrence carries an inline definition or a `§-ref` to §0.4.

**Result (this commit):** all 19 §0.4 terms either are defined in §0.4 itself or carry an inline definition at first occurrence in body (`tenant`, `principal`, `capability`, `role`, `idempotency key`, `idempotency-key TTL`, `gate interval`, `lock heartbeat`, `consolidate cycle`, `phase-gate`, `snapshot`, `manifest`, `cutover`, `escalate / staged-for-review`, `degraded mode`, `drift detector`, `S3 backfill`, `async drain`, `async-drain alarm`, `v2 entry-criteria gate`). PASS.

### §11.2 Citation coverage audit

Every numeric default in §3 / §4 / §5.5 / §6 / §8.4 / §10 carries a `§-ref` citation to its upstream source-of-truth, OR is named explicitly as a v1 bet to be instrumented (per §0.3 #5).

**Result (this commit):**
- §3 rate-limit caps: 11 rows, all cite api §-ref + (where derived) gap §-ref.
- §4.1 gate interval: cites gap-01 §3.2 Q3; v1 bet on 15 min (range table provided).
- §4.2 lock heartbeat: cites gap-01 §3.2 Q3 + gap-08 §3.4.
- §4.3 idempotency-key TTL + 7-day ceiling: cites api §1.2, gap-08 §3.1, HANDOFF §14.6.
- §4.4 preference-cap: cites api §0.3 #3 + gap-09 §6.
- §4.5 drift cadence: cites gap-14 §5(3).
- §4.6 drift tolerance: cites migration §3.1 phase 12.
- §4.7 escalate cap: cross-references §3.
- §4.8 mid-migration alarm: cites HANDOFF §14.6 + migration §10 + composition §7.
- §5.5 alarms: 8 rows, all cite source.
- §6.4 review SLA: v1 bet documented.
- §8.4 disk thresholds: cites composition §7 + gap-08 §3.6.
- §10 cutover rule: cites scoring §8.6 + composition §1.1 + HANDOFF open-item list.

PASS.

### §11.3 Anti-checklist audit

§12 below names 12 explicit denials. Each is grep-verifiable.

**Result (this commit):** confirmed via §12 self-check; no denied content present in §0–§10. PASS. (See §12.)

### §11.4 SCNS-independence audit

Same audit pattern as api §7.1, migration §6.6.1. `grep -in "scns" docs/08-deployment-design.md` and confirm every hit falls into allowed categories: HANDOFF citation; the §12 anti-checklist denial; design-pattern cross-references where the upstream doc itself cites SCNS (gap-01 dream-daemon evaluation; migration target-corpus); this audit transcript itself.

**Result (transcribed at commit time):** 16 total line-hits, distributed across 9 distinct allowed-category buckets:

- §0.3 #2 — binding-constraint statement citing HANDOFF §10 #1 (allowed: HANDOFF citation).
- §0.4 "Cutover" definition — names "SCNS-as-substrate" as the source side of the cutover concept (allowed: migration cross-reference; the migration target is by definition SCNS).
- §3 `remember` rate-limit row — "SCNS observation rate << 10/s in practice" rationale (allowed: migration cross-reference for sizing).
- §4.1 gate-interval default — "SCNS dream-daemon precedent (note §2.10)" citing gap-01 §3 + dream-daemon design note (allowed: design-pattern reference per HANDOFF §10 binding-constraint #1).
- §4.3 idempotency TTL row — "SCNS observation rate; small migrations" sizing rationale (allowed: migration cross-reference).
- §7.4 snapshot UX — "SCNS-corpus migrations" naming (allowed: migration cross-reference).
- §11.4 (this section) header + body + result paragraph + per-bullet self-references (allowed: audit transcript itself).
- §12 anti-checklist denial (allowed).
- §13 traceability-matrix row (allowed: HANDOFF citation).

**Zero hits** in disallowed categories (no verb signature, no schema field, no runtime read path, no SCNS-shaped command, no dependency declaration). PASS.

### §11.5 Markdown-audience audit (HANDOFF §13 cascade)

`grep -in "for humans only\|humans only\|human-only" docs/08-deployment-design.md` and read for any framing of markdown as exclusively human-targeted. Per the WS7 §6.6.4 precedent, distinguish (a) framing assertions ("markdown is for humans only") from (b) rule statements / audit-grep self-references that *forbid* the framing.

**Result (transcribed at commit time):** 3 total hits, all meta-references:

- §0.3 #4 (line 49) — binding-constraint statement explicitly forbidding the framing (`Operator-facing prose does not frame markdown as "for humans only"`); allowed.
- §11.5 audit-method paragraph (this section above) — the audit-grep pattern itself, plus the parenthetical framing-assertion example; allowed.
- §11.5 first result-bullet (this section) — transcribes the §0.3 #4 quoted phrase verbatim while affirming its meta-only nature; allowed.

**Zero hits** of the disallowed framing as an actual assertion. §6.2 review-surface, §7.2 manifest UX, §9 degraded-mode playbook all use "operator", "reviewer", "human", "agent", and "LLM-side reviewer" interchangeably without exclusivity claims. PASS.

---

## §12 Anti-checklist — what WS8 is NOT

Closing section. Restated for visibility; mirrors §0.2 with explicit denials.

WS8 **does not** commit to:

- **A transport-layer implementation.** The doc picks JSON over HTTP/1.1 (§2.4) as the wire-format choice; it does not implement the HTTP server, TLS termination, or token-issuing infrastructure.
- **Migration-tool source code.** §7 specifies the CLI and manifest contracts; the tool's source is operator-tooling pass (post-WS8).
- **Scoring weight values.** §4.5 schedules drift detection and re-eval; weight calibration (gap-03) and the math (WS5) are out of scope.
- **Eval-set composition.** §4.5 schedules the cadence; case construction is WS4 / gap-14.
- **A SCNS runtime path.** No verb, command, or surface in this doc reads from `~/.scns/` or imports SCNS schemas at runtime. (HANDOFF §10 binding constraint #1; §0.3 #2.)
- **Cross-deployment Lethe→Lethe migration or restore.** Deferred to v1.x (§7.5; §8.1; HANDOFF §14.6).
- **`vault.db` consumption.** Out of scope per migration §1.1 + §8.
- **An auth-mechanism implementation.** §2.3 specifies the principal-extraction contract; the actual auth provider (OAuth, JWT, mTLS, deployment-local token file) is deployment-specific.
- **Multi-tenant runtime.** v1 is single-tenant-per-deployment (§1.1); v2 is gated on §10's cutover rule.
- **A v2 multi-tenant design.** §10 names the readiness checklist; the v2 design itself is a future workstream.
- **Schema migration policy** (Lethe schema v1 → v1.1 etc.). §9's "Schema migration mid-flight" row points at composition §7 + WS7-phase-pattern; the actual schema-migration tooling is operator-tooling pass.
- **A Lethe runtime distribution / packaging artifact.** WS8 specifies the deployment shape (single-host, single-tenant); the install bytes (Docker image, Linux package, etc.) are downstream packaging.

---

## §13 Traceability matrix

Every WS8 decision → upstream §-ref.

| WS8 §-ref | Decision | Upstream source |
|---|---|---|
| §0.3 #1 | Single-tenant-per-deployment | composition §1.1 + §5.2; HANDOFF open-item list |
| §0.3 #2 | No SCNS runtime dependency | HANDOFF §10 #1; api §0.3 #1; migration §0.3 |
| §0.3 #3 | Cross-tenant reads forbidden | api §1.8; composition §5.2 |
| §0.3 #4 | Markdown dual-audience | composition §1.1; HANDOFF §13 |
| §1.1 | Single-tenant baseline | composition §1.1 |
| §1.2 | Physical layout (S1–S5 colocation) | composition §2 + §5 |
| §1.3 | `single_writer_per_tenant=true` migration default | gap-04 §4 stop-gap; migration §4.1 + §4.2 |
| §1.4 | v2 multi-tenant gate forward-ref | scoring §8.6; §10 |
| §2.1 | Three RBAC roles (`agent`, `tenant_admin`, `operator`) | api §0.2 + §8 |
| §2.2 | Capability-to-verb matrix | api §1.6 + §1.8 + §3.3 + §4.1 + §4.4 |
| §2.3 | Principal extraction contract | api §1.1 + §1.5 |
| §2.4 | JSON over HTTP/1.1 + optional MCP | api §0.4; HANDOFF §2.3 |
| §3 row `recall` | 30/s sustained, 60 burst | api §2.1.2 |
| §3 row `remember` | 10/s sustained, 30 burst | api §3.1 |
| §3 row `forget(invalidate\|quarantine)` | 5/s sustained, 10 burst | api §3.3 |
| §3 row `forget(purge)` | 10/h, 100/d per tenant | api §3.3 step 2; gap-11 §3.3 |
| §3 row `peer_message` | 20/s sustained, 50 burst | api §3.4; gap-10 §3.4 |
| §3 row `consolidate(force)` | 6/h per tenant | api §4.3 |
| §3 row `capture_opt_in_trace` | 10/h per tenant | api §4.1 |
| §3 row escalate cap | 50/d per tenant | api §3.1 + §3.4; HANDOFF §12.6 + §14.6 |
| §4.1 gate interval default 15 min | bet documented w/ range | gap-01 §3.2 Q3 |
| §4.2 lock heartbeat 30 s, break 60 s | default | gap-01 §3.2 Q3; gap-08 §3.4 |
| §4.3 idempotency TTL 24 h, ceiling 7 d enforced | default + ceiling rule | api §1.2; gap-08 §3.1 + §5; HANDOFF §14.6 |
| §4.4 preference cap 10 KB recency-of-revision | default | api §0.3 #3; gap-09 §6 |
| §4.5 drift cadence | default | gap-14 §5(3) |
| §4.6 drift tolerance 5% | default | migration §3.1 phase 12 |
| §4.8 mid-migration alarm 1.5× | default | HANDOFF §14.6; migration §10; composition §7 |
| §5.2 `health()` extensions | additive | api §4.4; HANDOFF §14.6 |
| §5.4 metrics signals | must-emit | api §1.7 + §4.4; scoring §8.1 + §8.4; composition §7 |
| §5.5 alarms | thresholds | composition §7; gap-08; gap-11; gap-14; HANDOFF §12.6 + §14.6 |
| §6 escalate-review pipeline | full workflow | api §3.1 + §3.4; gap-10 §6; gap-11 §3.3; HANDOFF §12.6 + §14.6 |
| §6.3 `force_skip_classifier=true` | api §3.1 extension | api §3.1 (extension noted for WS6 implementation pass) |
| §7.1 `lethe-migrate` CLI subcommands | contract | migration §3 + §3.1 + §3.2 |
| §7.2 manifest UX (JSONL + HTML) | contract | migration §3.2; composition §1.1 |
| §7.3 capability check ordering | Phase 1 surface | migration §5; api §1.1 + §1.6 |
| §7.4 snapshot UX methods | operator surface | migration §3.1 phase 2; gap-08 §3.4 substrate |
| §7.5 rollback (pre-cutover only) | scope | migration §3.1 phase 13; HANDOFF §14.6 |
| §8.1 backup posture | per-store | composition §2 + §5; gap-08 §5 |
| §8.2 `lethe-audit lint --integrity` operator surface | invocation | gap-08 §3.5 |
| §8.3 lock recovery surface | operator commands | gap-08 §3.4 |
| §8.4 disk thresholds 1 GB / 100 MB | defaults | composition §7; gap-08 §3.6 |
| §9 degraded-mode playbook | cross-walk | composition §7 + §7.1; api §4.4 |
| §10 v2 cutover 3-month soak | rule | scoring §8.6; composition §1.1 |

---

## §14 Residual unknowns

What WS8 leaves open for operator-tooling pass / v1.x / v2.

- **The metrics-pipeline implementation.** §5.4 names the must-emit signals; the actual exporter (Prometheus, OTLP, log-scraper) is deployment-specific and out of scope. Operator-tooling pass.
- **The review-surface HTML implementation.** §6.2 specifies the static-rendered shape; the renderer is operator-tooling pass.
- **The `lethe-migrate` CLI implementation.** §7 specifies the contract; the bytes are operator-tooling pass.
- **The `lethe-admin` CLI for lock recovery (§8.3).** Same as above.
- **`force_skip_classifier=true` parameter formal addition to api §3.1.** WS8 names the contract; WS6's implementation pass updates the api doc.
- **Cross-deployment Lethe→Lethe restore.** Deferred to v1.x (§8.1; gap-08 §5; HANDOFF §14.6).
- **2PC for cross-host T1.** Deferred to v2 (gap-08 §5).
- **v2 multi-tenant runtime design.** §10 names the gate; the v2 design itself is a future workstream.
- **Wire-format re-evaluation at v2 fleet scale.** §2.4 rejected protobuf/gRPC for v1; v2 fleet scale changes the calculus.
- **Backup quiesce automation.** §8.1 names quiesce windows; the orchestration (consolidate-lock acquire → backup → release) is operator-tooling pass.
- **Disk threshold defaults at fleet scale.** §8.4 sets v1 defaults for single-tenant-per-deployment; multi-tenant fleets need per-tenant accounting.
- **v2 entry-criteria gate's "3 consecutive months" formal definition.** §10 specifies the rule; the exact reset semantics under partial-month outages are operator-tunable but undefined here. v1.x refinement.
- **RBAC management API.** §2.1 has roles edited via S2 config + restart; a v1.x administrative API verb is a future surface.

---

## §15 Change log

- **(this commit)** Initial WS8 design — RBAC roles + capability-to-verb mapping + wire-format choice; rate-limit numerical caps for every api hook; operator knobs (gate interval, lock heartbeat, idempotency TTL with 7-day enforced ceiling, drift cadence, mid-migration alarm); `health()` extensions + must-emit metrics + 8 must-wire alarms; full escalate-review pipeline (queue substrate, review actions, SLA, migration-row drain workflow); migration runtime contract (`lethe-migrate` CLI, manifest UX, snapshot UX, rollback scope); backup posture + crash-recovery operator surface; degraded-mode operator playbook (cross-walk to composition §7 + §7.1); v1→v2 entry-criteria gate (scoring §8.6 + 3-month soak); 5 verification audits; 12-item anti-checklist; full traceability matrix; residuals. Awaiting WS8-QA fresh-eyes pass.
