# 20 — DMR (Deep Memory Retrieval)

**URL:** https://arxiv.org/abs/2310.08560 (MemGPT paper, §5 + appendix)  **Type:** benchmark (introduced inside a paper, not a standalone release)  **Fetched:** 2026-04-23
**Origin:** Packer et al., MemGPT (brief 11).  **Ref code:** https://github.com/cpacker/MemGPT (+ folded into Letta, brief 15).
**Notable follow-ups:** Zep (brief 01) reports **94.8 %** on DMR vs. MemGPT's **93.4 %** — near ceiling.

## Problem framing
DMR was introduced *inside* the MemGPT paper to motivate MemGPT itself: can a memory-augmented LLM recall specific facts injected earlier in a long, information-dense conversation, across distractor content and far past the native context window?

It is the **oldest of the three benchmarks in Lethe's eval set** (with LongMemEval and LoCoMo) and — critically — the most saturated.

## Architecture — the task shape
Dialogue-style conversation logs seeded with **numbered facts** at controlled positions, with distractor content between them:

```
User:   Let's start packing details.
System: Fact #1: apples are red.
System: Fact #2: sky is blue.
…many facts and distractors…
User:   What was Fact #2?
System: (expected: "sky is blue")
```

The task: after a long distractor tail, answer **"what was Fact #N?"** or list all facts matching a predicate. Facts are verifiable by exact match. Precision and recall are both measurable.

Hundreds to thousands of facts per session. Distractor density is controlled.

## Scoring / retrieval math
Not applicable — DMR defines the task. Systems supply their own retrieval. Evaluation is exact-match accuracy on recall queries. No published normalization for context-window size or compute — a system with a bigger native context can answer more without retrieval at all, which is part of why DMR has gotten easier over time.

## API surface
Not applicable: no library. Dataset + eval-style scripts in MemGPT / Letta repos. Reproducing published numbers requires the referenced code commit; the DMR harness is not versioned independently.

## Scale claims + evidence
- Original MemGPT results: ~93.4 % on DMR with the MemGPT virtual-context system; significantly higher than no-memory baselines with the same context budget.
- Zep paper result: **94.8 %** — i.e., **+1.4 pts** over MemGPT.
- GPT-4 / GPT-4o with long context windows score high on DMR *without* explicit memory systems, because the haystack fits natively.
- **Ceiling effect is real.** The 93–95 % band is where all modern memory systems sit.

## Documented limits
- **Synthetic and pattern-obvious.** "Fact #N: X" is a structured cue the model can learn to exploit. Real memory problems aren't numbered.
- **Low semantic density.** Facts are deliberately trivial and randomizable. Doesn't test reasoning over facts, only pointer-style lookup.
- **Distractor structure is bland.** Distractors are filler; real conversations have competing / contradictory information, which DMR doesn't model.
- **Near ceiling.** Small absolute gaps (1.4 pts, as in Zep-vs-MemGPT) are hard to distinguish from noise.
- **No temporal-reasoning, no multi-session, no abstention.** All five LongMemEval abilities (brief 18) are missing except information extraction.
- **No cost / latency dimension.** Same as LongMemEval and LoCoMo.

## Relation to Lethe
DMR is a **sanity check, not a headline metric** for Lethe. Decisions:

1. **WS4 runs DMR, but reports it as "at-ceiling confirmation" alongside LongMemEval/LoCoMo.** A Lethe configuration that scores <92 % on DMR is broken; a configuration that scores 95 % is ordinary. The spread is too narrow to tune against.
2. **LongMemEval (brief 18) + LoCoMo (brief 19) are the real targets.** DMR tells you whether the retrieval path works at all; LongMemEval tells you whether you handle the five real abilities; LoCoMo tells you whether you maintain conversational coherence.
3. **Useful for regression testing.** A DMR drop below the 92–95 % band is a cheap, fast signal that something in Lethe's ingest/retrieval pipeline broke.
4. **Synthetic-haystack framing is instructive but misleading.** Lethe must not optimize for haystack problems; utility-aware lifecycle (promote/forget) is invisible on DMR because nothing ever needs to be forgotten.
5. **Historical weight.** DMR is the benchmark every memory paper cites. Lethe needs a DMR number for comparability even though it's not the metric that drives design.
6. **Saturation proves the field needs the newer benchmarks.** LongMemEval's *≥30 pt drops* on the same SOTA systems that score 94 % on DMR — that gap is the opportunity space Lethe targets.

## Gaps / hand-waves it introduces
- **Conflation of "big context window" with "memory."** Long-context LLMs score well on DMR without a memory system, which is an indictment of the benchmark, not of memory systems.
- **No forgetting, no contradiction, no update.** The facts in DMR never change.
- **No provenance test.** A system that correctly answers "what was Fact #256?" gets full credit even if it can't cite the turn where Fact #256 appeared.
- **No cross-session, no cross-agent.** Pure single-conversation.
- **No cost model.** A system burning a full context replay per query scores the same as one retrieving surgically.
- **Versioning drift.** Exact numbers depend on which MemGPT/Letta commit the harness was run from; not a stable comparability target.
- **Benchmark-to-product gap.** Passing DMR does not mean the system is useful for agents; failing DMR does mean something is wrong.
