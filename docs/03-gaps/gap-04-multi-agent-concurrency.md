# gap-04 — Multi-agent concurrency + merge policy (graph layer)

**Synthesis-extension slot** (PLAN.md does not enumerate but synthesis §3.4 + QA §3.1 establish; charter §4.1 commits to multi-agent v1).
**Tier:** extension (target 50–80 lines).
**Status:** active. Charter §4.1: "multi-agent from day one." No reviewed substrate solves this.
**Substrate:** brief 12 Graphiti (`group_id` partitioning, no concurrency RBAC); brief 15 Letta ("shared blocks" punts concurrent-write conflicts to developers); brief 16 MS Agent Framework (no tenancy model); SCNS audit §4 (multi-agent with implicit conventions, not enforced isolation); synthesis §2.4 + §3.4; composition §5.2 + §7 row "tenant isolation" + §3.4 stress 4 (concurrent contradictions); gap-13 §3.4.
**Cross-refs:** Pairs with gap-07 (markdown-layer concurrency); gap-13 §3.4 (concurrent-write contradictions); gap-10 (peer messaging).

---

## 1. The gap

Synthesis §2.4: every reviewed substrate hand-waves multi-tenant + multi-agent concurrency. Letta's "shared blocks" punt to developers; Graphiti has groups without RBAC or quotas; qmd is single-user; MS AF has no tenancy model. SCNS operates multi-agent today via implicit conventions (audit §4) that don't survive externalization.

Charter §4.1 commits Lethe to multi-agent v1. Without a defined concurrency contract, three failure modes are likely:

1. **Lost updates.** Two agents writing the same fact-edge produce one survivor by clock race (gap-13 §3.4).
2. **Read-side anomalies.** A `recall` straddling a multi-write transaction returns a half-applied state.
3. **Tenant isolation breach** (composition §7) — the security failure mode.

Composition §5.2 commits to per-tenant partition; this brief operationalizes the *within-tenant* multi-agent story.

## 2. State of the art

- **Brief 12 Graphiti.** `group_id` is a partition key, not a lock. Two writers in the same group can race.
- **Brief 15 Letta.** Shared blocks across agents; concurrency punted ("developers handle it").
- **Brief 16 MS AF.** Each agent owns its own `AIContextProvider`; cross-agent state is out-of-band.
- **SCNS.** Single-broker SQLite arbitrates writes via per-table row locks; works at single-machine scale.

## 3. Candidate v1 approaches

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) Optimistic CAS on fact-key** | Each fact-edge has a version; writes specify expected-version; conflicts return `409` and the caller retries. | Simple; aligns with composition §5 T1/T2 ACID. Caller must handle retry. |
| **(b) Per-tenant write lock** | Single writer at a time per tenant; serializes within tenant. | Trivial correctness; throughput cap = single-writer rate. Likely too tight at swarm scale. |
| **(c) CRDT-style merge primitives** | Per-fact CRDT (LWW for scalars; OR-set for tags). | Concurrency-friendly; merge complexity; specifying CRDTs per fact-shape is research. |
| **(d) MVCC via Graphiti bi-temporal stamps** | Treat every concurrent write as bi-temporally distinct; resolve conflicts as gap-13 invalidations. | Reuses substrate; couples concurrency to contradiction handling, which is sometimes wrong (an idempotent re-write should not register as a contradiction). |

## 4. Recommendation

**Candidate (a) — optimistic CAS on fact-key — with read-only writers (peer messages, cross-tenant reads forbidden by composition §5.2).** Justification:

1. Aligns with composition §5 T1/T2: T1 includes the version check; CAS failure aborts T1; caller retries.
2. Cheap. No lock-table; no fairness queue; no CRDT specification work.
3. Falls back to gap-13 bi-temporal invalidate when CAS itself genuinely produces conflicting truth-values (not idempotent re-writes — those simply reach version-stable state).
4. The dream-daemon already serializes its own work via the per-tenant lock (note §2.2; gap-01 §3.2 Q3); CAS is the runtime-side complement on the synchronous remember/promote/forget path.

**Stop-gap if Lethe v1 cannot tolerate retry latency.** Add Candidate (b) per-tenant write-lock as a config flag (`single_writer_per_tenant=true`) for tenants with low concurrency where retry overhead is unacceptable. Default off.

## 5. Residual unknowns

- **CAS contention rate.** At what concurrent-writer count does retry storm degrade throughput? Bet: tolerable up to ~10 concurrent writers per tenant; instrument retry-rate.
- **Idempotency keys vs. version checks.** Caller-supplied UUID for `remember` (gap-08) makes retries idempotent. Combined with version-CAS on `promote/forget`, the system is convergent.
- **Peer-message write rate.** A flood of peer-messages (gap-10) into one recipient produces a write-hot-spot. Bet: cap recipient inbox at 100 unread peer-messages; back-pressure beyond.
- **Cross-tenant invariant testing.** Integration test that asserts `recall` with `group_id=A` never returns a fact written under `group_id=B` is a P0 lint and a CI gate.

## 6. Touch-points

- **gap-01 retention engine** — dream-daemon lock; CAS is independent.
- **gap-08 crash safety** — idempotency-key replay protects against retry-after-crash duplication.
- **gap-10 peer messaging** — peer-message recipient inbox throttling.
- **gap-11 forgetting-as-safety** — concurrent `forget` calls converge via version-CAS.
- **gap-13 contradiction resolution** — §3.4 concurrent-contradiction stress; this brief is gap-13's mitigation upstream.
- **WS6 (API)** — version field on every read; `If-Match` semantics on writes; `409` retry contract.
- **WS7 (migration)** — SCNS's broker-DB row-locking gets translated to CAS contracts.
