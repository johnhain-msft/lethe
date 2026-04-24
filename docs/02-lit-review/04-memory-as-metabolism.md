# 04 — Memory as Metabolism (Miteski — "A Design for Companion Knowledge Systems")

**URL:** https://arxiv.org/html/2604.12034  **Type:** paper (vision / design)  **Fetched:** 2026-04-23
**Author:** Stefan Miteski, CODE University Berlin. April 2026, v3.642. AI-assisted research and editing (disclosed).

## Problem framing
Personal-wiki memory architectures (Karpathy's LLM Wiki, MemPalace, LLM Wiki v2) are *position-ful* — they accumulate what a specific user reinforces. That means they drift under user-coupled dynamics: retention is not neutral. Under a "truth-tracking" framing this looks like a bug; under a *companion* framing it is the job. The paper stakes three separable claims — descriptive, taxonomic, normative — and defends the normative one: a **time-structured procedural rule for resolving the mirror-vs-compensate tension** in a personal companion-memory substrate.

## Architecture — five retention operations + two mechanisms

Explicitly a governance profile over a wiki substrate (explicitly citing Karpathy's pattern as the target). Five operations:

1. **TRIAGE** — streaming path. Shallow filter at ingest; rejects obvious garbage but makes **no coherence decisions**. New entries land in a raw buffer.
2. **CONTEXTUALIZE** — fit external sources to the user's working-context depth at consolidation time (compensates for the assumption that sources have a single canonical compression).
3. **DECAY** — recency + access-frequency pressure downward.
4. **CONSOLIDATE** — scheduled (nightly / weekly), not per-query. Scores entries *against each other as well as the active wiki*. Three mutually-supporting new entries can overturn a high-gravity dominant interpretation; a lone contradiction gets quarantined.
5. **AUDIT** — periodic stress-test of highest-gravity entries: temporarily suspend them, rerun queries that relied on them, measure whether performance degrades. If the entry is dead weight, its gravity decays; if removal improves performance, archive.

Two supporting mechanisms:
- **Memory gravity** — dependency centrality applied to memory retention. Load-bearing entries get structural protection (a kind of architectural gravity). Prevents the pruner from deleting foundations to retain last-week's popular noise.
- **Minority-hypothesis retention** — variance against monoculture. Keeps quiet but potentially-overturning evidence alive long enough to accumulate.

**Three-timescale safety story (explicit):**
- Within-agent scheduled consolidation cycles.
- Cross-agent federation (family/team/department/community wikis — named as follow-on research, *not* a rescue).
- Base-model evolution — keeping the wiki **outside** model weights preserves a correction channel (swap the model, keep the wiki).

## Scoring / retrieval math
Three retention signals, **all required, weighted against each other, plus a cap on any single one dominating**:
- Recency.
- Access frequency.
- **Utility** (did the system's acting on this entry produce useful results?).

Plus **memory gravity** as a structural multiplier: entries whose removal would cascade (orphan downstream knowledge) resist eviction independent of the three signals above.

The paper does **not** publish the weighting function. That is intentional — it is a design-principle paper, not an algorithm paper.

## API surface
No runtime API. The contribution is normative: what obligations the retention policy owes the user. The five operations name the places an implementer must put code.

## Scale claims + evidence
No implementation, no benchmarks ("We do not present implementation results. This is a vision paper.") — explicitly scoped as a governance profile, not an evaluated system.

## Documented limits
- "Does not eliminate the reinforcement of user-held bad beliefs." The paper is emphatic that the safety story is partial. Structural defenses on three timescales, but not a solution.
- Federation (multi-user) is out of scope — explicitly named as where the next layer of work lives.
- AUDIT sensitivity is "an open problem" by the author's own admission.
- Circularity of coherence-on-current-wiki accepted, not escaped — batched consolidation exists to *resist* its failure modes.
- No latency / storage / throughput numbers; not implementation.

## Relation to Lethe
**This is the deepest paper in the set for the retention-policy problem.** Four direct contributions:

1. **Three-signal score (recency × access × utility) + gravity.** Feeds WS5 directly. Matches and extends the PDF gist of "recency-weighted-by-access × connectedness × utility" — adds memory gravity as a named primitive and names the *required cap* on any single signal.
2. **TRIAGE → CONSOLIDATE → AUDIT timeline.** Lethe's dream-daemon successor should have all three. SCNS has gates (≈TRIAGE) and consolidation; it does **not** have an AUDIT operation. This is a gap worth filling in v1.
3. **Minority-hypothesis retention.** Pairs with the "≥ 2 weeklies ⇒ stable" promotion rule from SCNS (`01b-dream-daemon-design-note.md` §2.11) — SCNS already has the promotion half; this paper supplies the retention-of-evidence half.
4. **Runtime-over-substrate doctrine.** "Wiki stays outside the base model weights" is exactly the Lethe positioning from `00-charter.md` §3. The correction-channel argument should be ported into the charter rationale.

## Gaps / hand-waves it introduces
- **No algorithm for memory gravity.** Dependency centrality is named but the specific metric (PageRank? indegree? weighted citation?) is not chosen. Lethe has to pick.
- **Three-signal weighting not specified.** Stated as "required" but weights are a design choice left to implementer.
- **AUDIT sensitivity.** Author admits open problem: what performance-degradation threshold triggers archival? What query set exercises the gravity-protected entries? How much audit-compute is tolerable?
- **No concurrency / multi-tenant story** within-agent; federation is deferred.
- **"Gravity" naming collides** with software "architectural gravity" metaphor; acknowledged by the author. Minor but naming-wise Lethe should be careful.
- **Utility signal capture** — defined but the *mechanism* for observing success/failure is punted (same gap as PDF #1).
