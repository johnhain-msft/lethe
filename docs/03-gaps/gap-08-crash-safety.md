# gap-08 — Crash safety + durability contract

**Synthesis-extension slot** (PLAN.md preamble flags ACID/durability as open; synthesis §2.12 + §3.10).
**Tier:** extension (target 50–80 lines).
**Status:** active. Charter §4.1: "remember is atomic; consolidation is resumable." Composition §5 set the ACID boundaries; this brief specifies the implementation contract.
**Substrate:** brief 12 Graphiti (relies on backing DB — Neo4j or FalkorDB — for durability); brief 21 Karpathy (concedes no crash safety); brief 11 MemGPT (no discussion); SCNS dream-daemon design note §2.2 (singleton lock + stale-lock break — partial recovery), §2.13 (try/catch per phase); synthesis §2.12 + §3.10; composition §5 (T1/T2 ACID specification).
**Cross-refs:** composition §5 (consistency model — this brief is the impl spec); §7 (failure-mode table referenced); gap-04 (idempotency keys); gap-01 (resumable consolidation); gap-11 (purge mid-flight).

---

## 1. The gap

PLAN.md preamble enumerates this gap directly: "No reviewed paper offers a mid-consolidation crash recovery story." Karpathy concedes the wiki has none. Letta relies on its DB. Graphiti relies on Neo4j/FalkorDB. SCNS relies on git for synthesis pages and per-phase try/catch for the dream-daemon (note §2.13).

Charter §4.1 commits to "remember is atomic; consolidation is resumable; mid-cycle crash is recoverable without losing episodes." Composition §5 set the ACID boundaries for T1 (remember: episode + ledger) and T2 (promote/forget: flag + log). What's missing is the **implementation contract** that makes those guarantees real:

1. **What does the caller see if the runtime crashes between line 3 (commit T1) and line 4 (extract)?** The episode is durable; the extraction is pending. Retrying `remember` with the same idempotency key must be a no-op.
2. **What does the dream-daemon do if it crashes mid-consolidation?** The lock is held; the partial work either rolls back or resumes.
3. **What does the runtime do if S2 is corrupt on startup?** WAL recovery; if recovery fails, refuse to serve.
4. **What gets logged for every recovery action so audit can trace it?**

Without these specified, the "atomic remember / resumable consolidation" charter commitment is a wish, not a contract.

## 2. State of the art

- **Brief 12 Graphiti.** Defers durability to backing DB; Neo4j cluster + WAL is the standard story.
- **SCNS dream-daemon (note §2.2 + §2.13).** Compare-and-swap lock acquisition; stale-lock break at 5× gate interval; try/catch around each phase so a phase failure doesn't abort siblings. **No resumability** — a crashed run starts over from gate-time on the next cycle. Note §2.3 break-point: "no exponential backoff on repeated failures — a crashing daemon retries every gate."
- **Brief 11 MemGPT, brief 21 Karpathy.** Silent on crash recovery.

The substrate (Graphiti backing DB durability + SQLite WAL) is sufficient for *single-store* crash recovery. The contribution is the **cross-store recovery protocol**.

## 3. The contract (spec)

### 3.1 `remember` durability

- T1 (composition §5): single-DB transaction (Graphiti backing DB *or* a coordinated 2PC if S1/S2 are physically separate; v1 default = single-machine deployment with both in same DB process).
- Caller supplies an **idempotency key** (UUID); Lethe records it in S2 alongside the episode-id. A retry of `remember` with the same key returns the prior episode-id without re-writing.
- Retry window: 24 hours (idempotency key TTL).
- **Crash between T1 commit and extraction:** dream-daemon picks up unextracted episodes from the S2 ledger on next gate (composition §4.1). No data loss; eventual extraction.

### 3.2 `promote` / `forget` durability

- T2 (composition §5): single-DB transaction over flag-write (S2) + log-append (S5, which lives in S2).
- Idempotency key per call; retry-safe.
- **Crash before flag-apply:** dream-daemon reads pending flags on next cycle, applies, clears.

### 3.3 Dream-daemon resumability

The note §2.13 break-point is "no resumability." Lethe's spec:

- Each consolidation phase emits a **checkpoint event** to S5 before starting (`phase=extraction, status=in_progress, run_id=R`) and after completing (`phase=extraction, status=done`). 
- On daemon startup, if a `run_id` has phases in `in_progress` with no matching `done`, the daemon **resumes from the last completed phase**, not from scratch.
- Phases must be idempotent: re-running an extraction phase for the same episodes must converge to the same fact-set.
- Resumability budget: at most 3 resume attempts per run before the run is marked `failed` and the lock is broken. Per-tenant exponential backoff on repeated failures (note §2.3 fix).

### 3.4 Lock recovery

- Locks have a heartbeat (gap-01 §3.2 Q3 commits to 30 s). A holder that doesn't heartbeat for 2× heartbeat interval is presumed dead; lock is broken.
- Broken-lock event logged to S5 with `(broken_holder, presumed_dead_at, broken_by)` triple.

### 3.5 Startup integrity check

- On runtime startup, `lethe-audit lint --integrity` runs:
  - S2 WAL recovery (SQLite native).
  - Reconcile orphaned T1/T2: any episode in S1 without a corresponding S2 ledger entry (or vice versa) gets a backfill or a flagged-for-review record.
  - Reconcile S5 vs. S1 state: per gap-13 detection signals.
- If integrity check fails to converge, runtime refuses to serve and emits a `degraded_startup` health-endpoint state.

### 3.6 `forget(purge)` mid-flight (composition §7 + gap-11)

- T2 surrounds `(delete from S1, delete from S3, write retention proof to S5)`. If any subset fails, the transaction aborts and the caller retries.
- For S3 (vector index), a "ghost embedding" — embedding present, fact deleted from S1 — is detected by reconciler and removed.
- Retention proof is written **before** the delete in T2 ordering; if the delete fails, the proof is reverted by transaction rollback. Never have a proof without a delete.

## 4. Recommendation

**Adopt the §3 contract as v1's implementation spec.** The structure is conservative:

- ACID where composition §5 said it; idempotency keys for caller-side retry safety.
- Phase-level checkpoints + resumability for the dream-daemon (the §note 2.13 break-point fix).
- Per-tenant exponential backoff on repeated failures (§note 2.3 fix).
- Startup integrity check + reconciler that backfills S5 (composition §7 row "S5 append fails" — this is its other half).
- Retention-proof-before-delete ordering for purge.

**Stop-gap.** None — this is the contract every other gap brief assumes. A degraded version (no resumability, no idempotency keys) is not safe to ship; charter §4.1 commitments would be unmet.

## 5. Residual unknowns

- **2PC vs. single-DB transaction.** v1 default is single-machine, single-DB; if a tenant runs Graphiti on Neo4j and Lethe-runtime on a separate host, T1 becomes a distributed transaction. Bet: defer 2PC to v2; document the single-machine constraint.
- **Idempotency key TTL.** 24 hours is a guess. If caller retries cross hours-of-darkness window, increase. Instrument.
- **Checkpoint storage cost.** S5 grows with phase events. Bet: 1 checkpoint per phase × 4 phases × N runs/year ≈ small. If S5 audit log dominates, add compaction.
- **Backup interaction.** Crash-safe within a single Lethe deployment; cross-deployment backup/restore is out of scope (WS7).
- **Concurrent run_ids.** Per-tenant lock prevents concurrent runs *within* a tenant; cross-tenant runs are independent. Documented.

## 6. Touch-points

- **gap-01 retention engine** — dream-daemon resumability + lock heartbeat originate here.
- **gap-04 multi-agent concurrency** — idempotency keys + version-CAS together produce convergent retries.
- **gap-11 forgetting-as-safety** — purge mid-flight ordering.
- **gap-13 contradiction resolution** — startup reconciler uses gap-13 detection signals.
- **WS4 (eval)** — chaos-style fault injection (kill the daemon mid-phase; assert recovery).
- **WS6 (API)** — idempotency-key contract on every write verb.
- **WS7 (migration)** — `lethe-audit lint --integrity` is a phase-gate in WS7; SCNS data import re-establishes the contract on landed data.
