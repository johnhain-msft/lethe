# 19 — LoCoMo (Evaluating Very Long-Term Conversational Memory of LLM Agents)

**URL:** https://arxiv.org/abs/2402.17753  **Type:** benchmark (paper + dataset)  **Fetched:** 2026-04-23
**Authors:** Maharana, Lee, Tulyakov, Bansal, Barbieri, Fang (Snap Research + UNC, 2024). Published at ACL 2024.
**Dataset:** https://github.com/snap-research/locomo
**Follow-on:** **LoCoMo-Plus** — arXiv:2602.10715 (2026), extends to latent non-factual cognitive memory (goals, implicit values).

## Problem framing
Prior conversational-memory benchmarks capped at ~5 sessions. LoCoMo targets **very long-term** conversation: average **300 turns**, up to **35 sessions**, ~**9 000 tokens** of history per dialogue. The intent is to expose whether state-of-the-art systems can maintain conversational coherence over weeks/months of interaction, not minutes.

Notably **multi-modal**: agents can share and react to images inside the dialogue. That lifts it out of pure-text benchmarking and forces the memory system to track image-referenced facts.

## Architecture — the pipeline
Conversations are **synthesized via a machine-human pipeline**:

1. LLM agents are instantiated with **grounded personas** and **temporal event graphs** (scripted life-events over a long period).
2. Agents converse over the scripted timeline, producing long multi-session transcripts.
3. **Human annotators verify and edit** for realism and consistency.

The evaluation harness is three tasks:
- **Question answering** — over the long history.
- **Event summarization** — condense what happened.
- **Multi-modal dialogue generation** — produce plausible next-turn output consistent with history (including images).

## Scoring / retrieval math
Not applicable — LoCoMo defines tasks, not retrieval functions. Scoring:
- QA: accuracy against gold answers.
- Summarization: ROUGE / BERTScore-class metrics + human comparison.
- Generation: human preference against baselines.

## API surface
Dataset + reference eval harness in `snap-research/locomo`. No long-lived API. Dataset format: JSON dialogues with persona metadata, event-graph timestamps, image URIs, gold QA pairs.

## Scale claims + evidence
- Avg **300 turns / dialogue**, up to **35 sessions**, ~9 K tokens of history.
- Multi-modal: images interleaved with text.
- Evaluated: **latest LLMs with RAG and long-context configurations**.
- Finding: **all tested systems lag human performance substantially on long-term coherence**; neither longer context windows nor naive RAG closes the gap.
- LoCoMo-Plus (2026) pushes further into **non-factual** memory (user goals, implicit preferences, latent constraints) — not covered by original LongMemEval or DMR.

## Documented limits
- **Synthesized conversations with human editing.** Richer than pure-synthetic, but still not organic production traffic.
- **Persona / event-graph scripting** biases toward structured life-events. May over-represent biographical fact and under-represent agent-task memory.
- **9 K tokens / 35 sessions** is *long* for chat but **short compared to LongMemEval's 1.5 M-token examples**. Complementary, not redundant.
- **Multi-modality ties evaluation to a specific image-handling stack**; vision-incapable memory systems need wrappers.
- **Non-factual memory only addressed by LoCoMo-Plus**, not the original.
- **Human evaluation component** limits reproducibility / automation.

## Relation to Lethe
LoCoMo is the **second** WS4 benchmark after LongMemEval. Specific ways it shapes Lethe:

1. **Long-term conversational coherence** is a distinct capability from fact-recall. LoCoMo tests whether the memory surface produces *consistent-sounding* agent behavior across sessions, not just correct facts. Lethe's `recall` must return enough persona/preference context for coherence, not only factual hits.
2. **Multi-modality is coming.** SCNS is text-only; Lethe should not bake in text-only assumptions. Image-referenced facts need a content-addressed-blob story (URI + provenance, dereferenced lazily at recall). Graphiti episodes (brief 12) support arbitrary payload → reuse.
3. **Persona + event-graph scripting ≈ agent lifecycle.** Lethe's dream-daemon can be validated against LoCoMo by treating each session boundary as a consolidation trigger and comparing pre/post recall quality.
4. **Complementary scale profile.** LongMemEval = 1.5 M-token haystack; LoCoMo = 35-session multi-modal coherence. Together they pin down two different failure modes. Lethe needs both in WS4.
5. **LoCoMo-Plus raises the bar for WS3.** Non-factual memory (goals, implicit preferences) is not something Graphiti models. This is a concrete gap — likely a gap-brief topic in the next phase.
6. **Human-eval component tempers our own eval design.** LongMemEval can be fully automated; LoCoMo cannot. Lethe should budget human-eval runs for coherence claims rather than skipping them.

## Gaps / hand-waves it introduces
- **Non-organic data.** Despite human editing, conversations are scripted; real user drift and fatigue patterns are under-represented.
- **Short-haystack-long-sessions vs LongMemEval's long-haystack-short-sessions.** Neither benchmark tests the fully extreme case (millions of tokens *and* months of time *and* multi-modality).
- **Persona adherence is entangled with memory.** A system can do well by strong persona prompting without actually retrieving past facts — makes causal attribution hard.
- **Multi-modal baseline is moving.** Image models change rapidly; benchmark numbers age fast.
- **No cost / latency dimension.** Same gap as LongMemEval.
- **Gold answers for open-ended generation are weak.** Human preference is noisy; ROUGE-class scores on generation are known to underweight semantic correctness.
- **Non-factual memory only partially addressed** even in LoCoMo-Plus — the space of "user goals" is large and under-defined.
