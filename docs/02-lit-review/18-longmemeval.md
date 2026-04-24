# 18 — LongMemEval

**URL:** https://arxiv.org/abs/2410.10813  **Type:** benchmark (paper + dataset + code)  **Fetched:** 2026-04-23
**Authors:** Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu (2024).
**Repo:** https://github.com/xiaowu0162/LongMemEval  **Dataset:** https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
**Primary headline result:** commercial assistants drop ≥30 pts on long histories; SOTA tops out at 30–70 % per task.

## Problem framing
Existing long-context benchmarks (e.g., needle-in-a-haystack) test retrieval in a single long prompt. They do not test **long-term interactive memory** — agents that accumulate state across hundreds of sessions and millions of tokens, with users referencing prior facts, updating them, and asking temporal questions. LongMemEval fills that gap.

## Architecture — the five abilities tested
The benchmark is defined by **five core long-term-memory abilities** a chat assistant must exhibit:

1. **Information extraction** — recall specific facts from extensive chat history.
2. **Multi-session reasoning** — aggregate and synthesize info spread across many sessions.
3. **Temporal reasoning** — reason over explicit timestamps and event order.
4. **Knowledge updates** — detect and adapt when a user fact changes.
5. **Abstention** — refuse to answer when the info was never provided.

Dataset: **500 expert-authored questions**, embedded in **attribute-controlled, scalable user-assistant histories**, with examples scaling to **~1.5 M tokens** across hundreds of sessions. Evidence can be needle-buried or wide-scattered.

## Scoring / retrieval math
Not applicable: benchmark defines the **task**, not a retrieval formula. Evaluated systems supply their own retrieval. Scoring is task-level accuracy per ability bucket; overall numbers reported per system.

The paper also runs an **ablation of memory-system design choices** — this is the part Lethe should mine:
- **Value granularity.** Indexing by *conversational round* beats indexing by *session*. → implication for Lethe's episode granularity.
- **Fact-augmented key expansion.** Indexing entries with explicit extracted user facts boosts recall. → implication for Lethe's ingest: extract facts, attach as keys.
- **Time-aware query expansion.** Including temporal context in the query matters. → implication for Lethe: exploit Graphiti's bi-temporal model at query-time, not just at ingest.

## API surface
Benchmark, not a library. Usage = load dataset → run your memory system → score against gold answers. No stable API; consult the repo for evaluation harness.

## Scale claims + evidence
- **500 questions.**
- **Up to 1.5 M tokens** per example session history (hundreds of sessions).
- Tested against "latest commercial assistants" and long-context LLMs including **GPT-4o**. Commercial assistants show **≥30 % absolute accuracy drop** on long histories vs. short contexts.
- SOTA range **30–70 %** on specific ability buckets.

Independent reports from other papers (Zep, brief 01; Graphiti, brief 12) cite **+18.5 % over baseline** for memory-graph systems on LongMemEval — this is the evidence-of-gap number Lethe should care about.

## Documented limits
- **English-only, chat-assistant framing.** Does not test agent-tool workflows, code-editing agents, or multi-agent SCNS-style systems.
- **Synthetic / attribute-controlled histories.** Authored, not organic. Transfer to real production traffic is implied, not proven.
- **500 questions is small-to-moderate.** Fine for per-ability diagnosis; not for fine-grained system tuning.
- **Abstention ability is genuinely hard.** Modern LLMs are biased to answer; abstention scores are the lowest bucket in published results.
- **No cost / latency dimension.** Pure accuracy. A system scoring 70 % at $10/query is not comparable to 65 % at $0.10/query.

## Relation to Lethe
**LongMemEval is Lethe's primary evaluation benchmark.** Specific decisions it drives:

1. **WS4 uses LongMemEval as the headline metric.** DMR (brief 20) is at ceiling; LoCoMo (brief 19) is complementary; LongMemEval spans the five abilities Lethe must actually support.
2. **The five abilities map to Lethe's API.**
   - Information extraction → `recall`.
   - Multi-session reasoning → `recall` with cross-episode synthesis (Graphiti graph traversal, brief 12).
   - Temporal reasoning → Graphiti bi-temporal queries surfaced through `recall(as_of=…)`.
   - Knowledge updates → Graphiti edge invalidation + Lethe `promote`/`forget`.
   - Abstention → Lethe must return *empty-with-rationale*, not best-guess. Cheap to miss; commit to it early.
3. **Value-granularity ablation = decision point.** Lethe ingests at *round* granularity, not session granularity. SCNS audit §2 currently mixes both; Lethe should standardize on round.
4. **Fact-augmented key expansion = dream-daemon duty.** The daemon extracts user-fact keys during consolidation; runtime uses them at retrieval.
5. **Time-aware query expansion.** Lethe's `recall` should accept (or infer) a temporal anchor and expand the query accordingly.
6. **Expect +18.5 %-class gains, not +2 %.** The published spread between naive RAG and memory-graph systems is ~20 pts. Lethe targeting <5 pts of improvement over Graphiti-alone is under-aiming.

## Gaps / hand-waves it introduces
- **No cost metric.** Retrieval accuracy without compute cost disadvantages lean systems. Lethe should track tokens-per-query alongside accuracy.
- **No retention metric.** Tests recall; doesn't test *forgetting* (abstention is the closest proxy, and it's weak).
- **Single-user framing.** No cross-user privacy-leak test. Relevant for SCNS-style multi-agent deployments.
- **No tool-call / action memory.** Chat-assistant only. Agent tasks that succeed or fail based on *action* memory (e.g., "last time this fixed the bug") are out of scope.
- **Needle-based evidence placement may be easier than organic drift.** Facts placed deliberately are unlike facts that contradict each other accidentally across a year.
- **Gold-answer format is narrow** — shift-of-topic abstentions may be judged wrong even when principled.
- **Benchmark-fit risk.** Systems tuned to the five abilities may plateau on production traffic that doesn't decompose the same way.
