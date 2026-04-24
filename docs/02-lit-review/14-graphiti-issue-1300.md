# 14 — Graphiti issue #1300: Temporal decay algorithms for retention

**URL:** https://github.com/getzep/graphiti/issues/1300  **Type:** open issue (bot-filed, open, uncommented by maintainers)  **Fetched:** 2026-04-23
**Title:** "Temporal decay algorithms for retention in real-time knowledge graphs"
**Filed:** 2026-03-05 by `teekoo5` (Skene Growth bot-agent, external to getzep).
**State at fetch:** open, 0 comments, 0 reactions, no label.

## Problem framing
The issue filing itself is the data point. A third-party "growth analysis" agent scanned Graphiti (brief 12) and flagged that the project **lacks temporal-decay / node-decay algorithms for retention management**. Verbatim claim:

> "Real-time knowledge graphs lack temporal decay algorithms for retention management."

> Suggested prompt: *"Implement a node-decay function that flags unused data clusters after 30 days, generating a weekly 'Graph Cleanup' report to re-engage the admin."*

That the filing came from a bot selling a growth product does not change its accuracy. Graphiti has no decay, no eviction, no demotion engine — this brief + brief 12 + the Graphiti README together establish that fact.

## Architecture
Not applicable: the issue proposes architecture, does not describe existing architecture. The proposal itself — *"flag unused data clusters after N days → cleanup report → human re-engages"* — is a thin, human-in-the-loop sketch of what a memory-maintenance layer would look like. It is **not** a design; it is a symptom report.

## Scoring / retrieval math
Not applicable: the issue suggests decay but specifies no decay function. The implicit shape is an age-threshold rule (`last_touched > 30 days ⇒ flag`), which is a simpler policy than the utility-weighted decay Lethe needs (SCNS audit §3, Cognitive Weave brief 05, Memory-as-Metabolism brief 04).

## API surface
Not applicable: nothing added to the Graphiti API. The proposal would add **one** new concept — a "graph cleanup report" — but does not specify its shape (CLI? email? endpoint?).

## Scale claims + evidence
Not applicable: no scale claims. The issue implies that without decay, unused clusters accumulate and degrade graph performance/relevance, but offers no measurement.

## Documented limits
The issue *is* the documented limit, filed against Graphiti:
- No node-decay function.
- No cluster-aging / flagging mechanism.
- No automated cleanup report.
- No re-engagement / maintenance loop.

Maintainer silence (0 comments, 0 labels after ~7 weeks open at fetch) is itself a signal: this is not on the Graphiti team's near-term roadmap. Graphiti's focus is ingest + bi-temporal retrieval, not lifecycle.

## Relation to Lethe
**This is the WS3 anchor.** The entire reason Lethe exists as a separate project is captured in this issue: Graphiti is the right substrate, and the missing piece is the promotion/demotion/decay engine that this issue identifies.

Concrete implications:

1. **Lethe's `promote` / `forget` verbs (`00-charter.md` §4.1) answer this issue directly.** Lethe is the "temporal decay + retention management" layer on top of Graphiti that the issue asks for.
2. **Maintainer silence justifies forking the responsibility, not forking the code.** Lethe composes over Graphiti rather than patching it. The decay layer lives in Lethe; Graphiti's bi-temporal substrate is untouched.
3. **The 30-day age-threshold suggestion is too weak.** Lethe's demotion must be utility-aware (hit rate, dwell time, recall-after-eviction), not just recency-aware. Cognitive Weave (brief 05) and Memory-as-Metabolism (brief 04) supply the richer model; SCNS audit §3 shows SCNS already has hit-count data to seed it.
4. **"Cleanup report → re-engage admin" is the wrong default for unattended agents.** Lethe's dream-daemon (`01b-dream-daemon-design-note.md`) runs autonomously on scheduled wake cycles, not via human re-engagement. Human-in-the-loop is optional, not mandatory.
5. **Issue attribution is suspect but evidence is real.** The filing bot is trying to sell a product; the underlying claim is independently verifiable against Graphiti's README and source. Cite the issue for its *existence as an open, uncommented gap*, not for the bot's proposed fix.

## Gaps / hand-waves it introduces
- **Conflates decay with cleanup.** Decay (score attenuation over time) and cleanup (removal of flagged items) are different operations. The issue runs them together.
- **Assumes admin-in-the-loop.** Weekly report → admin re-engages. Does not scale to hundreds of agents or to autonomous deployments.
- **No utility signal.** Pure recency ignores whether a cluster is actually used. A 31-day-old cluster that's queried daily should not be flagged.
- **No promotion counterpart.** Decay/demotion without promotion is one-directional and bleeds the graph.
- **No contradiction-aware interaction with Graphiti's bi-temporal model.** If a fact has `valid_to` set by contradiction, does decay still apply? The issue doesn't ask.
- **No measurement.** What proves the decay is working? Graph-size budget? Retrieval precision? Agent task success? None specified.

These gaps are the WS3 brief set: each one becomes a gap deep-dive.
