# 01b — Dream-Daemon Design Note

**Status:** on-merits evaluation, not an audit. Companion to `01-scns-memory-audit.md`.
**Source:** `/Users/johnhain/Coding_Projects/scns/src/dream/` (read-only, 2026-04-23).
**Purpose:** evaluate SCNS's dream-daemon pattern as a **candidate Lethe consolidation spine**. Per `PLAN.md` north star, this is not legacy being audited — it is a candidate contribution being tested on merits.

Verdict preview: **adopt the pattern, rebuild three of the twelve modules, export the rest.** Details in §4.

---

## 1. What the pattern is

SCNS's dream-daemon is an offline memory-metabolism loop. A gate fires when time + session-count + lock thresholds align. The daemon reads the short-term trackpad (daily logs) + durable long-term store (`MEMORY.md`), extracts typed entries, merges them into the long-term store by name (last-write-wins for contradictions; textual dedup for duplicates), prunes under a byte+line cap by priority, archives losers with a reason, applies negative-memory rules to the project's instructions file, runs weekly+monthly rollups on their own cadences, and regenerates synthesized views (`SOUL.md`, `USER.md`). All with crash-safe state in two tables of a dedicated SQLite DB.

In the language of the PDF and Memory-as-Metabolism: **the dream-daemon is a concrete implementation of anabolism (promote, consolidate) + catabolism (demote, archive) with a gate-lock-execute control plane.**

The reason this matters for Lethe is that none of the papers or reference impls studied in WS2 ships this full loop. MAGMA describes dual-stream consolidation; Memory-as-Metabolism describes the biological analogy; Cognitive Weave gives the decay math; Zep ships bi-temporal invalidation. **Nobody ships the control plane.** The dream-daemon is it.

---

## 2. Per-module evaluation

Each module is scored on three axes: *what problem it solves* (is the problem real?), *where it works* (is the solution sound within its envelope?), *where it breaks* (what ceiling would Lethe hit?). Scores are qualitative labels: `solid`, `salvageable`, `rebuild`.

### 2.1 `dream-schema.ts` — **solid**
- **Solves:** DB bootstrap separated from the broker DB so consolidation doesn't contend with session traffic.
- **Works:** trivial WAL + FK init.
- **Breaks:** no migration story beyond the seed insert. If the schema ever evolves (it will, once Lethe adds per-tenant state), migrations need a real mechanism.
- **Lethe disposition:** adopt the pattern (separate storage for consolidation state). Drop this 19-line wrapper and replace with a proper migration-capable init.

### 2.2 `dream-state.ts` — **solid**
- **Solves:** durable three-gate state (time / count / lock) across daemon restarts.
- **Works:** singleton-row (`id=1`), compare-and-swap lock via `UPDATE … WHERE lock_holder IS NULL`.
- **Breaks:** (a) single-row model assumes one vault per daemon — Lethe is multi-tenant, needs per-tenant rows; (b) lock holder is `dream-daemon-<pid>` with no PID-liveness check, only time-based stale-lock break at 5× the gate interval; (c) `last_run_*` telemetry is overwrite-only (no history).
- **Lethe disposition:** adopt, extend schema to tenant-scoped rows, add PID-liveness or equivalent keepalive, preserve history in a sibling runs-log table.

### 2.3 `dream-gates.ts` — **solid**
- **Solves:** a predicate that decides whether to run consolidation, preventing thrashy runs and races.
- **Works:** three cheap conditions (time ≥ 24 h, sessions ≥ 5, lock free) checked lock-first. Stale-lock break at 5× default.
- **Breaks:** (a) no exponential backoff on repeated failures — a crashing daemon retries every gate; (b) the `uninitialized` branch is dead code in practice because `openDreamDatabase` always initializes; (c) thresholds are compile-time constants.
- **Lethe disposition:** adopt; parameterize thresholds per tenant; add failure-backoff.

### 2.4 `memory-limits.ts` — **salvageable**
- **Solves:** keeps the entrypoint memory file within a prompt budget.
- **Works:** dual cap (200 lines OR 25 KB), UTF-8-safe byte counting.
- **Breaks:** constants are global. Different agents have different context windows; a v1 config that lets you override per tenant is the minimum.
- **Lethe disposition:** adopt the pattern, parameterize constants, expose through config.

### 2.5 `date-utils.ts` — **salvageable / rebuild**
- **Solves:** converting "yesterday" / "3 days ago" in free-form text to absolute dates before archival (so future retrieval is stable).
- **Works:** deterministic regex on a fixed pattern set.
- **Breaks:** English-only; fragile regex; doesn't cover "a couple weeks ago" class. Low-value cost to rebuild.
- **Lethe disposition:** rebuild with a small curated library or punt entirely to the LLM at extraction time.

### 2.6 `memory-entries.ts` — **solid, but move**
- **Solves:** markdown YAML-frontmatter round-trip for `MEMORY.md` with Zod-validated schema (`user` / `feedback` / `project` / `reference` / `prohibition`), dedup, contradiction resolution, validation, re-synthesis.
- **Works:** round-trip stable; Zod catches schema drift; `memory/core-file-generator.ts` re-imports `parseMemoryMd` (the back-dependency is deliberate).
- **Breaks:** block-split regex (`/---\n…---\n…(?=\n---\n|$)/`) is ad-hoc; a malformed entry poisons the parse. Contradiction resolution is **by entry name, last-write-wins** — that's strictly weaker than Zep's bi-temporal invalidation.
- **Lethe disposition:** adopt the schema, move to a shared `lethe/schema` module so both `memory/` and `dream/` consumers share it. Replace last-write-wins contradiction with timestamped invalidate-don't-delete (§WS3 gap #7).

### 2.7 `consolidation-priorities.ts` — **salvageable**
- **Solves:** decides which entries drop first when pressure (byte+line cap) is exceeded.
- **Works:** static priority by type (`user` / `prohibition` = critical; `feedback` = high; `project` = medium; `reference` = low), plus `trimToFit`.
- **Breaks:** *entirely static.* No decay, no recency, no utility feedback, no connectedness. This is the weakest scoring surface in the whole loop.
- **Lethe disposition:** **this is where WS5's scoring function plugs in.** Keep the API (`getEntryPriority`, `sortByPriority`, `trimToFit`) and swap the implementation for the Lethe heuristic (recency-weighted-by-access × connectedness × utility, with type as one input feature among many).

### 2.8 `consolidation.ts` — **solid**
- **Solves:** deterministic four-phase pipeline (orient → gather → consolidate → prune) that merges existing `MEMORY.md` with newly extracted entries.
- **Works:** pure functions, explicit phase logs, pairs cleanly with the daemon's gate/lock control plane.
- **Breaks:** (a) contradiction resolution inherits the name-keyed LWW from §2.6; (b) dedup is textual — "I like dark mode" and "Prefer dark UI" are not detected as duplicates without semantic similarity; (c) no provenance graph — we lose "this entry came from that daily log line."
- **Lethe disposition:** adopt the phase structure, keep the pure-function discipline, add semantic dedup + provenance linking. The 4-phase pipeline is the closest thing in the pile to a reference consolidation algorithm and should be the Lethe reference shape.

### 2.9 `extraction.ts` — **rebuild**
- **Solves:** turns observation-tagged markdown daily logs into typed entries (USER / FEEDBACK / PROJECT / REFERENCE / PROHIBITION).
- **Works:** two header formats supported; noise filter drops `pre/post-tool-use`, `session-start/end`.
- **Breaks:** regex classifier is *low precision* and tightly coupled to SCNS observer output format. `fixTypos` and `synthesizeEntry` are deterministic text munging, not LLM calls despite the names. Tool/app aggregation bolts summary *lines* in rather than emitting typed entries. An agent whose observe layer uses a different trailer format gets zero entries.
- **Lethe disposition:** **rebuild.** Lethe should extract with an LLM call against a schema it controls, and accept observer payloads in a standard shape (not markdown text). Keep SCNS's regex extractor alive as the v0 fallback for zero-config ingest.

### 2.10 `consolidation-scheduler.ts` — **solid**
- **Solves:** independent weekly (7 d) and monthly (30 d) cadences sharing the dream DB.
- **Works:** trivial singleton-row schedule table; `shouldRunWeekly` / `shouldRunMonthly` predicates.
- **Breaks:** hardcoded intervals; no backfill-on-long-gap (a daemon offline for 3 weeks runs one weekly rollup, not three).
- **Lethe disposition:** adopt, parameterize, add catch-up semantics.

### 2.11 `tiered-consolidation.ts` — **salvageable**
- **Solves:** rolling daily logs into weekly summaries and weeklies into monthly summaries; archiving low-value entries along the way.
- **Works:** normalized-lesson dedup (lowercase + strip); the "stable pattern appears in ≥ 2 weeklies" rule is a simple, defensible promotion signal.
- **Breaks:** (a) extraction is bullet + session-hook regex only — same format coupling as §2.9; (b) low-value detection is regex heuristic (no learned or scored signal); (c) no re-ingest path — once archived, can't unarchive cheanly.
- **Lethe disposition:** adopt the **tiering idea** (daily → weekly → monthly with archive at each step). Rebuild on top of Lethe's scored extraction + Lethe's scoring function. The "≥ 2 weeklies ⇒ stable" promotion heuristic is one of the better explicit criteria in the whole codebase and should survive into v1.

### 2.12 `housekeeping.ts` — **SCNS-specific, not candidate**
- **Solves:** retention prune for `otel_spans`, `otel_metrics`, `events` on the *broker* DB + optional VACUUM.
- **Works:** gracefully skips missing tables.
- **Breaks:** tightly coupled to SCNS broker schema. Not generically reusable.
- **Lethe disposition:** **not ported.** Lethe may want an analogous housekeeper over its own tables, but the module as written stays in SCNS.

### 2.13 `dream-daemon.ts` — **the thing itself**
- **Solves:** single orchestration entrypoint that sequences gate → lock → extract → consolidate → resynthesize → write → apply-negatives → tiered weekly/monthly → core-file regen → housekeep, with dry-run and force-run modes.
- **Works:** each sub-step wrapped in try/catch so a failure in (say) negative-memory application does not abort rollups. Lock holder tag is `dream-daemon-<pid>`.
- **Breaks:** (a) no heartbeat in the lock (only time-based stale-lock break); (b) `forceRun` ignores gates but still honors lock, which is correct but worth documenting; (c) no streaming progress — a long run is opaque; (d) deeply coupled to SCNS vault layout + broker DB for housekeeping.
- **Lethe disposition:** **the shape is the contribution.** A Lethe `ConsolidationDaemon` will look structurally identical: gate → lock → run-with-phases → write. Rebuild the implementation from scratch with tenant scoping, heartbeats, streaming progress, and plug-in phases (so `negative-memory-applicator` becomes one of many optional phases, not hardcoded).

### 2.14 `index.ts` — barrel. No evaluation needed.

---

## 3. Mapping to Memory-as-Metabolism and MAGMA

### 3.1 Memory-as-Metabolism (MaM)

MaM frames agent memory as a flux: anabolism (synthesis, consolidation, promotion) balanced by catabolism (pruning, decay, forgetting), with ATP-like energy budgets constraining both. The dream-daemon implements this almost literally:

| MaM concept | Dream-daemon module |
|---|---|
| Anabolism — promote observations to durable memory | `extraction.ts` + `consolidation.ts` (orient/gather/consolidate phases) |
| Catabolism — prune and archive | `consolidation.ts` (prune phase) + `archive-store.ts` + `tiered-consolidation.ts` low-value archival |
| Tiered lifetimes (short → mid → long) | daily → weekly → monthly tiering in `tiered-consolidation.ts` |
| Energy / rate budget | three-gate predicate in `dream-gates.ts` (time + sessions + lock) |
| Homeostasis — entrypoint size stays bounded | `memory-limits.ts` + `consolidation-priorities.ts:trimToFit` |
| "Don't do this" rules as immunological memory | `negative-memory-store.ts` + `negative-memory-applicator.ts` |

The only MaM mechanism **not** represented is *utility-driven reinforcement* — the idea that retrievals which actually helped the agent get a boost. SCNS logs the raw signal (`quality_checks`) but never feeds it back (see audit §3.3 + §8.4). That's a Lethe gap-deep-dive (#1 in WS3), not a dream-daemon flaw per se — the daemon just doesn't see the signal today.

### 3.2 MAGMA dual-stream consolidation

MAGMA's central architectural move is *two parallel consolidation streams* — **episodic** (who/what/when, timestamped, local) and **semantic** (generalizations, timeless, global) — with bidirectional promotion (recurring episodic → semantic) and demotion (contradicted semantic → back to episodic for revisit).

The dream-daemon today is **single-stream**. Every entry in `MEMORY.md` is semantic-ish (typed by role, not time-scoped). Daily logs are episodic-ish but they are a *trackpad*, not a durable episodic store — by design they get consumed and discarded.

The tiered `daily → weekly → monthly` structure is **adjacent to** MAGMA's dual-stream but not the same thing. Dream-daemon tiers are time-scope reductions of the same stream; MAGMA streams are categorically different memory types.

| MAGMA concept | Dream-daemon analogue | Gap |
|---|---|---|
| Episodic stream | daily logs + weekly/monthly rollups (ephemeral) | No durable episodic store after monthly rollup |
| Semantic stream | `MEMORY.md` typed entries | Exists |
| Episodic → semantic promotion | "≥ 2 weeklies ⇒ stable" heuristic in `tiered-consolidation.ts` | Narrow; only covers lesson-shaped patterns |
| Semantic → episodic demotion on contradiction | `archive-store.ts` with `reason=superseded` | Archive is terminal, not re-ingestable |
| Intent-routed retrieval | `search.ts` weights 0.7 vec / 0.3 kw uniformly | Not intent-aware |

**Implication for Lethe:** the dream-daemon is the right control plane, but the storage underneath it needs to become *two-stream* to match MAGMA. This is exactly the composition question WS3 Track A must answer — do we run two parallel consolidations on two substrates (episodic on temporal-graph via Graphiti, semantic on structured markdown), or one consolidation writing into two stores?

---

## 4. Verdict and transition plan

**Verdict:** the dream-daemon pattern becomes Lethe's consolidation spine. The 12-module shape survives with three rebuilds, three adoptions-with-parameterization, and one dropped (`housekeeping` stays SCNS-internal).

| Module | Disposition |
|---|---|
| `dream-daemon.ts` | adopt shape, rewrite: tenant scoping, heartbeats, pluggable phases |
| `dream-schema.ts` | adopt, add migrations |
| `dream-state.ts` | adopt, multi-tenant + PID liveness |
| `dream-gates.ts` | adopt, parameterize, backoff on failure |
| `consolidation.ts` | adopt, add semantic dedup + provenance |
| `consolidation-priorities.ts` | adopt API, swap impl for Lethe scoring function |
| `consolidation-scheduler.ts` | adopt, parameterize, add catch-up |
| `tiered-consolidation.ts` | adopt tiering + "≥ 2 weeklies" promotion, rebuild extraction |
| `memory-entries.ts` | move to shared schema module, replace LWW contradiction with timestamped invalidation |
| `memory-limits.ts` | adopt, parameterize |
| `date-utils.ts` | rebuild or drop (LLM handles it) |
| `extraction.ts` | **rebuild** — LLM-driven against Lethe schema; regex variant as v0 fallback |
| `housekeeping.ts` | **not ported** — SCNS-internal |

**Biggest single open question** that this note does **not** resolve (feeds WS3 gap deep-dives):
1. **Two-stream or one?** Does Lethe run one consolidation writing to two stores (MAGMA dual-stream), or two consolidations, or stay one-stream v1 and defer MAGMA to v2? The dream-daemon as written is one-stream; going to two-stream is a meaningful architectural step.
2. **Utility feedback loop.** Where in the gate/lock/execute shape does `quality_checks`-class signal get consumed? Pre-gate (influence whether to run), during priority (influence trim order), or post-consolidate (re-score surviving entries)?
3. **Lock semantics at multi-tenant scale.** The current single-holder lock works for 1 vault / 1 machine. Lethe's multi-tenant default needs per-tenant locks + a fairness story.
4. **Phase plug-in contract.** The rewrite should accept phases as plugins (`NegativeMemoryApplierPhase`, `TieredRollupPhase`, etc.). What's the contract? Return a diff? Emit events? Commit in-band?

These are WS3 deep-dive topics. The dream-daemon, as a pattern, is the right spine to hang them on.

---

## 5. Change log

- **2026-04-23** — First draft, post-audit. Ratified as the candidate consolidation spine for Lethe, subject to WS3 resolution of the four open questions above.
