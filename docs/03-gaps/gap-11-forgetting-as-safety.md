# gap-11 — Forgetting as safety

**PLAN.md §WS3 Track B item #6** (forgetting-as-safety). Synthesis §5 (restored-slot substrate pointers); QA §3.1 (slot restoration mandatory).
**Tier:** first-class.
**Status:** active. The project is *named* for forgetting (charter §1: "river of forgetting"); shipping without engaging this gap forfeits the project's identity.
**Substrate:** brief 04 Memory-as-Metabolism (richest source — explicit "safety story is partial," minority-hypothesis retention, three-timescale safety framing); brief 02 MAGMA (causal-edge partition enables targeted unlearning); brief 14 Graphiti issue #1300 (substrate has no decay/unlearn at all); brief 15 Letta (no forgetting primitive); brief 21 Karpathy (human-driven only); SCNS audit §archive-store (terminal archive — current SCNS forgetting is irreversible and not safety-framed); charter §1, §4.1 (`forget` as core verb), §4.2 (semantic-merge conflict resolution out of scope, but invalidation is in).
**Cross-refs:** composition design §4.2 (forget write path), §6 (provenance survives invalidate, removed only on purge), §7 (peer-message corruption mitigation). Pairs with gap-13 (contradiction); fed inputs from gap-01 (demotion outputs).

---

## 1. The gap

The reviewed field treats forgetting as a **scale or cost mechanism** — pruning to fit a context window (MemGPT), demoting to archival (SCNS), decaying because the gravity model says so (Memory-as-Metabolism conceptually). Brief 14 Graphiti issue #1300 confirms the leading substrate has no decay or unlearn algorithm at all. Letta's `enable_sleeptime` rewrites memory but doesn't conceptualize forgetting as a safety primitive.

**Brief 04 (Memory-as-Metabolism) is the only paper to even gesture at forgetting-as-safety**, and even there it's a "partial story" (brief 04 §3.1) framed as minority-hypothesis retention plus three-timescale safety windows. No reviewed system implements it.

For Lethe — *named* for the river of forgetting — this gap has identity weight. The charter (§4.1) commits to `forget` as a core API verb. Synthesis §3.1 lists "river of forgetting branding" as the first thing falsified by an under-served retention engine. If we ship without distinguishing **why** something is being forgotten (cost-pressure vs. correction vs. safety), three failure modes follow:

1. **Reinforcement of bad beliefs.** A confident-but-wrong fact survives because no system specifically targets falsity.
2. **Poisoning by malicious or buggy peer messages.** Composition §7 names this as a top-line failure mode; without a forget-mode that targets *episodes* (not just facts), poisoned input keeps re-deriving facts on each consolidation.
3. **Minority-hypothesis suppression.** Brief 04's specific concern: a contradicted fact may be the *correct* one; if forgetting is purely majority-driven, the system converges on whichever side is loudest.

A v1 forget primitive that isn't safety-aware is functionally a delete, and the project's name becomes false advertising.

---

## 2. State of the art

- **Brief 04 Memory-as-Metabolism §3.1.** Three-timescale safety: immediate (block harmful retrieval pre-output), consolidation-cycle (suppress reinforcement during dream-daemon pass), long-horizon (ensure forgotten content can be re-validated). Minority-hypothesis retention: when consolidating contradictory facts, retain the last representative of the minority side with a flag that blocks future demotion. **Vision-paper level**; no implementation.
- **Brief 02 MAGMA §causal-edges.** Causal partition allows targeted unlearning — "forget the consequence-graph rooted at episode E" is a tractable graph operation when causal edges are typed. Strength: enables targeted-unlearn primitive Lethe needs. Weakness: full MAGMA partitioning is v2 (charter §4.2).
- **Brief 14 Graphiti issue #1300.** Confirms substrate gap. Lethe must wrap Graphiti's bi-temporal `valid_to` with explicit forget semantics; substrate provides the primitive, not the discipline.
- **Brief 15 Letta.** `memory_rethink` + sleep-time can edit memory, but the editing is content-replacement, not categorized forgetting. No safety semantics.
- **Brief 21 Karpathy.** Forgetting is human-driven curation (delete the markdown file). Doesn't generalize to unattended.
- **SCNS archive-store** (audit §6). Archive is terminal — once archived, can't be unarchived cleanly (dream-daemon note §2.11 calls this break-point out). Not a model; rather, a confirmed-not-to-port pattern.

The substrate exists conceptually (brief 04) and primitive-wise (Graphiti `valid_to`, MAGMA causal partition). The discipline — **what forget *means***, with a contract — has to be Lethe's contribution.

---

## 3. Three forget modes (the v1 commitment)

Composition design §4.2 already names three modes. This brief defines them precisely.

### 3.1 `forget(invalidate)` — bi-temporal soft delete (default)

**Semantics.** Set `valid_to = now()` on the fact-edge in S1. Bi-temporal stamp preserves the fact in audit; it disappears from default `recall` (which queries `valid_to IS NULL OR valid_to > now()`). Reversible: a `revalidate` admin verb (post-v1) can reset `valid_to = NULL` if the fact is later re-validated.

**When to use.** The default. Caller said "I no longer believe this," or the dream-daemon decided the fact's score crossed the demotion threshold. Provenance untouched.

**Cost.** O(1) write. No data loss; storage cost grows linearly with invalidations.

**Failure mode.** Storage pressure on long-running deployments. Mitigation: `forget(purge)` for entries older than retention horizon and not part of any active provenance chain (gap-08 retention policy).

### 3.2 `forget(quarantine)` — episode-level isolation for safety

**Semantics.** Mark the *episode* (S1 raw payload), not just derived facts, as quarantined. The quarantine flag does three things: (a) excludes the episode from any future re-extraction; (b) marks every fact derived from it `valid_to = now()` (cascade invalidate); (c) writes a quarantine entry in S5 with reason and quarantining principal (caller agent or dream-daemon).

**When to use.** The episode itself is suspect — poisoned by a malicious peer message, came from a buggy ingest pipeline, contains content that violated a safety rule. Quarantine targets the *source* so the next consolidation cycle doesn't re-derive the bad facts.

**Cost.** O(facts derived from episode) cascade write, capped by per-episode-fan-out (typically <50). Episode payload preserved for audit.

**Failure mode.** Cascade can be expensive if a single episode produced thousands of facts (rare). Mitigation: cap the cascade at a per-cycle budget; flag oversize cascades for human review.

### 3.3 `forget(purge)` — hard delete with retention proof

**Semantics.** Hard-delete fact-edge or episode from S1, embeddings from S3, projections from S4b. Write a **retention proof** to S5: `(target_id, requested_by, reason, deleted_at, hash_of_deleted_content)` so the system can later prove the deletion happened (legal-class operations: GDPR / right-to-be-forgotten / similar).

**When to use.** Rare. Compliance requirement, secret-redaction (related to PLAN.md preamble's privacy/secret-sanitization point — synthesis §8 noted this dropped during synthesis), or post-quarantine cleanup of confirmed-malicious content.

**Cost.** Heaviest. Provenance broken (only the retention-proof remains). Cannot be reversed.

**Failure mode.** Audit trail thinned. Mitigation: purge is *logged and rate-limited*; admin-only by default; `forget(invalidate)` is preferred for almost every case.

### 3.4 The default is `invalidate`, not `purge`

This is the most important policy choice in this brief. The reason: brief 04's three-timescale safety requires that "forgotten" content remain *re-validatable on the long-horizon timescale*. Hard delete forecloses that. Invalidate preserves it.

`forget()` without a mode argument means `invalidate`. `purge` is opt-in, gated, audited.

---

## 4. Minority-hypothesis retention

Brief 04's specific safety contribution. The mechanism, mapped to Lethe:

- During consolidation, when the dream-daemon would demote a fact under cost pressure (gap-01), it checks: *does this fact represent the last surviving counter-evidence to a recently-promoted fact?*
- If yes, set a `protect_minority=true` flag in S2, blocking demotion until either (a) a re-validation event resolves the contradiction definitively (then minority can be invalidated), or (b) a configurable timeout passes (`MIN_MINORITY_RETENTION = 90 days`), after which the minority can be demoted normally.
- The flag is per-contradiction-cluster (identified via gap-13's bi-temporal cluster), not per-fact. One representative fact per cluster gets the flag.

**Why this matters.** It defends against majority-by-noise convergence: if 100 episodes assert X and 1 asserts ¬X, naive utility-weighted demotion silently kills ¬X. Minority-hypothesis retention says "the contradiction is more important than the count" until it's resolved.

---

## 5. Candidate v1 approaches

### Candidate (a) — Three modes + minority retention (full §3 + §4)

**Sketch.** Implement all three forget modes; implement minority-hypothesis retention; expose `forget(target, mode, reason)` MCP verb.
**Cost.** Moderate impl. S5 retention-proof schema + cascade-invalidate + minority-tracking.
**Failure mode.** Minority-retention false positives (flagged where contradiction is just transient noise) cause storage bloat. Mitigation: 90-day timeout caps.
**Eval signal.** Adversarial peer-message replay (a poisoned peer episode quarantined, observe that derived facts no longer surface). Minority-hypothesis: synthetic contradiction injection, observe that the rare-side survives ≥1 consolidation cycle.

### Candidate (b) — Two modes (invalidate + purge); skip quarantine

**Sketch.** Drop quarantine; rely on per-fact invalidation cascading via dream-daemon's normal contradiction handling.
**Cost.** Lower impl.
**Failure mode.** **Composition §7 row "peer-message corrupts a memory" specifically requires episode-level quarantine to prevent re-derivation.** Without it, the next consolidation re-extracts from the bad episode and reintroduces the bad facts. Forgetting becomes a treadmill against re-derivation.
**Eval signal.** Same adversarial replay as (a); without quarantine, observe re-derivation cycle.

### Candidate (c) — Single mode (`invalidate`) only; defer everything else to v2

**Sketch.** Bi-temporal `valid_to` is the only forget operation v1 ships. Quarantine and purge are v2.
**Cost.** Minimal.
**Failure mode.** Forfeits safety story. Charter §1 unmet. Composition §7 peer-corruption mitigation gone. PLAN.md preamble privacy/secret-sanitization concern un-addressable.
**Eval signal.** None — we ship without a safety primitive.

### Trade-off table

| Axis | (a) Three modes | (b) Two modes | (c) Invalidate only |
|---|---|---|---|
| Safety story (charter §1) | strong | partial | absent |
| Re-derivation defense | yes | no | no |
| Compliance-class deletes | yes | yes (purge) | no |
| Minority retention | yes | no | no |
| Implementation cost | moderate | low-moderate | minimal |
| API surface clarity | one verb, three modes | one verb, two modes | one verb |
| Reversibility (default mode) | reversible | reversible | reversible |
| Composes with gap-13 | yes | yes | yes |

---

## 6. Recommendation

**Candidate (a) — three modes + minority retention.**

Justification:

1. **Composition §7 demands it.** The peer-message-corruption mitigation row in the failure-mode matrix specifies episode-level quarantine. Without it, the composition design's own failure-mode analysis is unworkable.
2. **Charter §1 demands it.** "River of forgetting" is the project's name; shipping with a single mode (Candidate c) collapses forgetting back to "delete" — exactly what Lethe is supposed to *not* be.
3. **Brief 04 substrate is rich enough.** Minority-hypothesis retention is the one concrete safety mechanism the field has named; implementing it is cheap (one flag, per-cluster) and the only paper to propose it is the only paper Lethe has any reason to differentiate against on safety.
4. **Cost is bounded.** Quarantine cascade is O(facts/episode) ≈ <50; minority flag is O(contradictions); purge is rate-limited. None of this changes the system's complexity class.

**Stop-gap if (a) is not ready at v1 cut.** Ship Candidate (b) (invalidate + purge), document quarantine as "v1.1 deliverable," and cap peer-message ingestion at a low rate so the re-derivation treadmill is bounded. **Do not ship Candidate (c)** — it is incompatible with the composition design.

---

## 7. Residual unknowns

- **Quarantine cascade safety.** When quarantining episode E, do we cascade to facts that were *also* derivable from other (clean) episodes? Bet: no — invalidate the fact-edge that was derived from E specifically, leave any fact-edge derived from clean episode E' untouched. This requires per-edge provenance (gap-05) which Lethe enforces; without enforced provenance this disambiguation is impossible.
- **Minority threshold.** "Last surviving counter-evidence" needs a precise definition. Bet: a contradiction cluster (gap-13) where one side has count ≤ 1 and the other has count ≥ 3. Tunable.
- **Purge audit retention.** How long do we keep retention-proofs in S5? Bet: 7 years (matches default GDPR audit horizon). Per-tenant overridable.
- **Interaction with backups.** A purge that doesn't propagate to backups isn't really a purge. Out-of-scope for v1; documented as a v2 + WS7 concern.
- **Authorization model.** Who can call `forget(purge)` vs. `forget(quarantine)` vs. `forget(invalidate)`? Bet: invalidate = any agent with write access to the fact's tenant; quarantine = any agent + dream-daemon; purge = admin-role only. Final auth model is WS6.
- **Peer-asserted facts default-quarantine on dispute.** If a peer-asserted fact is contradicted by a self-observed fact, should the policy default to `invalidate` (treat both equally) or `quarantine` (assume peer is suspect)? Bet: invalidate by default; `quarantine` requires explicit caller signal. Re-visit if adversarial-peer rate is high in production.
- **"Forget what I asked you to forget" — meta-forgetting.** The retention-proof in S5 is a record that something was forgotten. If a user later asks Lethe to forget the *fact that they asked to forget X*, we'd have to delete the retention proof. Out of scope for v1; documented as a known meta-problem.

---

## 8. Touch-points

- **gap-01 retention engine** — produces the demotion outputs; the *mode selection* (invalidate vs. quarantine vs. purge) is owned here.
- **gap-04 multi-agent concurrency** — concurrent `forget` calls on the same fact: last-write-wins on the bi-temporal stamp is fine; ACID via T2 (composition §5 row 2).
- **gap-05 provenance enforcement** — minority-hypothesis identification depends on per-edge provenance being type-enforced; quarantine cascade depends on it.
- **gap-07 markdown scale** — purges of facts whose only S4b view is in a synthesis page need a rebuild trigger.
- **gap-08 crash safety** — purge mid-flight (deleted from S1 but S5 retention-proof not yet written) is a recovery hazard; T2 transaction covers it.
- **gap-10 peer messaging** — peer-corruption mitigation lives here; the quarantine mode is what lets gap-10 survive a poisoning episode.
- **gap-13 contradiction resolution** — bi-temporal `valid_to` is the substrate; this brief and gap-13 share it. gap-13 owns the *detection* of contradictions; this brief owns the *response*.
- **WS4 (eval)** — adversarial-replay test suite; minority-survival test.
- **WS6 (API)** — `forget(target, mode, reason)` signature + auth model.
- **WS7 (migration)** — SCNS's archive-store maps to `invalidate`; SCNS has no analog of quarantine or purge; documented in migration phasing.
- **WS8 (non-goals)** — semantic-merge conflict resolution (charter §4.2) is out; this brief reaffirms invalidate-don't-merge.
