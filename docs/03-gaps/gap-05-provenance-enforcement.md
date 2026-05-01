# gap-05 — Provenance enforcement

**Synthesis-extension slot** (synthesis §3.5 + §2.6 — substrate-pinning is a *commitment*; this gap is its *enforcement*).
**Tier:** extension (target 50–80 lines).
**Status:** active. Composition §6 names provenance propagation as a contract; this brief specifies enforcement.
**Substrate:** brief 12 Graphiti (episodes carry provenance natively); brief 21 Karpathy (no provenance — the wiki forgets where it learned what); brief 15 Letta (per-block provenance is best-effort); SCNS dream-daemon note §2.6 (synthesis pages cite source files); composition §6 (propagation chain); gap-08 (idempotency keys feed provenance integrity); gap-10 (peer-message provenance is two-step); gap-13 (provenance is the audit trail for invalidations).

---

## 1. The gap

Composition §6 commits Lethe to "every fact in S1 has a non-null episode-id; every recall response carries the episode-id; every promote/forget records who and why." The commitment is meaningless without enforcement.

Without enforcement, the failure modes are:

1. **Orphaned facts.** A fact-edge in S1 with no episode-id (extraction bug, manual SQL, migration); recall returns a fact the system can't justify.
2. **Provenance drift.** Edge updated by consolidation; consolidation fails to update provenance; subsequent recall claims an outdated source.
3. **Peer-message confusion** (gap-10 §3.3). Recipient stores a peer-claim but elides the `derived_from` link; later it's indistinguishable from a self-observed fact.
4. **Audit trail gaps** (gap-11). A `forget(purge)` runs; no record of which source episode authorized the purge.

Karpathy's wiki (brief 21) demonstrates the long-term cost: facts in the wiki gradually decouple from their justifications; recall becomes "I think this is true because the wiki says so"; correction becomes impossible.

## 2. State of the art

- **Brief 12 Graphiti.** Native episode-id stamping; every entity/edge points to the episode that produced it. The model is right; enforcement at write-time is left to the runtime.
- **Brief 15 Letta.** Per-block provenance is best-effort; documented as developer responsibility.
- **Brief 21 Karpathy.** Concedes none.
- **SCNS dream-daemon note §2.6.** Synthesis pages cite source files at the top; consolidation rewrites preserve citations by template. Empirically reliable; not a type-system invariant.

The substrate (Graphiti episodes) is sufficient. The contribution is **type-system invariants + lints** that prevent provenance loss.

## 3. Enforcement primitives

### 3.1 Type-system invariant

- The S1 schema marks `episode_id` as `NOT NULL` on every edge that represents a fact.
- The runtime API for write is `add_fact(claim, episode_id, ...)`. There is no overload that omits `episode_id`.
- Database-level constraint refuses inserts that violate this — defense in depth.

### 3.2 Provenance propagation through consolidation

- Consolidation operations (merge, demote, contradict) **never** drop the source `episode_id` set; they expand it. A merged fact carries the union of source episodes.
- A specific consolidation operation that *replaces* a fact-edge (e.g., gap-13 contradiction-resolution writes a new edge with `valid_to` on the prior) must record the prior episode-set on the *replaced* edge, not silently lose it.
- Lint: post-consolidation, `provenance-integrity` lint asserts every live fact-edge has ≥1 episode-id.

### 3.3 Peer-message provenance (two-step, gap-10 §3.3)

- A peer-message `claim` carries `source = peer_message:from_agent:msg_id`.
- If the recipient materializes the claim into its own memory, the new episode is created with `source = self_observation, derived_from = peer_message:...`.
- The new fact-edge points to the new episode (not directly to the peer-message); the peer-message is reachable via the episode's `derived_from`.

### 3.4 Forget audit (gap-11 §3.4)

- Every `forget(soft|purge|deny)` writes to S5 a triple `(target, requester, justification, source_policy_id, ts)`.
- For `purge`, the **retention proof** (gap-08 §3.6) lives in S5 with the same triple shape; integrity check on startup asserts no fact-edge in S1 points to an episode whose proof of purge exists.

### 3.5 Lints + audits

- **lethe-audit lint:**
  - `provenance-required` — every fact-edge has an episode-id.
  - `provenance-resolvable` — every episode-id in S1 resolves to an episode in S1's episode store.
  - `peer-message-derivation` — every fact-edge whose episode has `derived_from=peer_message:...` has a corresponding inbox record.
  - `forget-proof-resolves` — every forget-event in S5 either has a live retention proof or has an alive target with non-`purge` action.
- These lints run in CI and on `lethe-audit` invocation.

## 4. Candidate enforcement strengths

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) Lint-only** | Run lints in CI, fix violations after the fact. | Cheap, low coverage; bugs survive between runs. |
| **(b) Type-system + lints** | API refuses to accept null `episode_id`; lints catch consolidation drift. | Strong runtime guarantees; consolidation is the residual risk. |
| **(c) Type-system + lints + DB constraints** | Above + database `NOT NULL`/`FOREIGN KEY` constraints. | Belt + suspenders; small dev cost. The recommendation. |

## 5. Recommendation

**Candidate (c) — type-system + lints + DB constraints.** Justification:

1. Composition §6 promises "non-null episode-id"; the cheapest enforcement is also the strongest.
2. DB constraints catch out-of-band writes (manual SQL, migration scripts, panicking debug scaffolds) that bypass the runtime API.
3. Lint coverage protects against the consolidation drift case (§3.2) — type-system can't catch it because consolidation is *allowed* to update provenance, just not to drop it.

**Stop-gap.** None. Provenance is the substrate of every other guarantee in WS3 (gap-11 forgetting, gap-13 contradiction, gap-14 eval-bias detection). Skipping it is not a v1 option.

## 6. Residual unknowns

- **Manual edits to S4a (markdown synthesis pages).** S4a is canonical; its provenance is git-history (composition §3 row S4a). Lint extension: synthesis pages must reference at least one source episode/page in their YAML frontmatter, validated by `lethe-audit lint`.
- **Cross-runtime provenance.** When a tenant ships data across deployments (WS7 migration), episode-ids must be stable. Bet: episode-ids are tenant-scoped UUIDs; preserved across migration.
- **Ext provenance for imported sources.** A `remember(source='external:rfc-1234')` — does the runtime accept arbitrary source identifiers? v1: yes, with a warning logged; the contract is "non-null", not "of an enumerated type."
- **Provenance in S3 (vector index).** S3 is rebuildable; provenance lives in S1. If a tenant queries vectors directly without S1 hydration, no provenance is returned. Composition §3 already documents S3's fence — `recall` always hydrates through S1.

## 7. Touch-points

- **gap-08 crash safety** — idempotency keys + retention proofs depend on provenance integrity.
- **gap-10 peer messaging** — two-step provenance for `claim` materialization.
- **gap-11 forgetting-as-safety** — forget audit triple writes through here.
- **gap-13 contradiction resolution** — invalidations preserve, never drop, prior provenance.
- **gap-14 eval-set bias** — provenance enables "did the eval-set leak from the same source as training data?" detection.
- **WS6 (API)** — `recall` response includes per-fact provenance; `remember` requires `episode_id` (or generates one).
- **WS7 (migration)** — episode-id stability is a migration invariant.
- **WS4 (eval)** — provenance-integrity is a CI gate, also an eval signal: facts without provenance fail the recall test.
