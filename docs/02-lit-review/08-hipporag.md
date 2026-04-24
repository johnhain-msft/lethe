# 08 — HippoRAG: Hippocampus-Inspired Long-Term Memory for LLMs

**URL:** https://arxiv.org/abs/2405.14831  **Type:** paper (NeurIPS 2024)  **Fetched:** 2026-04-23
**Authors:** Jimenez Gutierrez et al. (OSU-NLP-Group). arXiv:2405.14831v3.
**Code:** github.com/OSU-NLP-Group/HippoRAG

## Problem framing
LLMs + RAG still struggle to integrate a large amount of new experience after pre-training — no deep-knowledge-integration analog to mammalian memory. Inspired by the **hippocampal indexing theory** of human long-term memory, which frames the hippocampus as an index into neocortical episodic traces.

## Architecture
HippoRAG synergistically orchestrates three components in roles that map to the hippocampus / neocortex / parahippocampal region division:
1. **LLM** — plays the neocortex role (knowledge + reasoning substrate).
2. **Knowledge graph** — plays the hippocampus role (index of experiences).
3. **Personalized PageRank (PPR)** — plays the parahippocampal region role (cue-driven activation routing over the graph).

Ingestion: LLM extracts entities / relations from each new document and adds them to the graph. Retrieval: query's entities become PPR seeds; PPR walks the graph and selects top passages by aggregated node activation.

## Scoring / retrieval math
**Personalized PageRank** is the scoring primitive. Query nodes seed the PPR distribution; neighbors get activated by link weight; passages are ranked by summed PPR mass over their constituent entity nodes. Single-step retrieval — no iterative reasoning needed.

## API surface
Open-source reference implementation at `OSU-NLP-Group/HippoRAG`. Exact Python API lives in the repo; abstract does not enumerate.

## Scale claims + evidence
- Multi-hop QA benchmarks: **up to +20 %** over SOTA.
- **Single-step HippoRAG is comparable-or-better than iterative retrieval (IRCoT)**, while being **10–30× cheaper** and **6–13× faster**.
- Combining HippoRAG *with* IRCoT yields further gains.
- Claims ability to tackle "new types of scenarios out of reach of existing methods" (abstract-level claim).

## Documented limits
Not enumerated in the abstract. Implicit: the extracted graph is only as good as the entity-extraction LLM call. Pre-extraction cost is up-front (vs. query-time iterative retrieval), shifting compute to ingest.

## Relation to Lethe
Three contributions feed Lethe:
1. **PPR as a retrieval primitive.** When Lethe needs "activation spreading" over a graph substrate (Graphiti in the leading path), PPR is a battle-tested default over the generic "graph walk" handwave.
2. **Pre-extract, query-cheap trade-off.** HippoRAG spends compute at ingest so retrieval is single-step. This is the opposite of iterative-retrieval approaches (IRCoT) and aligns with Lethe's async-consolidation-does-the-hard-work stance (MAGMA dual-stream, SCNS dream-daemon).
3. **Biological grounding.** Pairs with Memory-as-Metabolism (brief 04) — multiple 2024–26 papers converge on biological analogies. Lethe's scoring function (WS5) can cite hippocampal indexing as motivation for recency-weighted-by-access.

## Gaps / hand-waves it introduces
- **Extraction quality is silent.** Graph is built by an LLM call. Errors propagate without correction.
- **No consolidation / forgetting.** HippoRAG adds; it does not subtract. Over time the graph grows unboundedly; no demotion signal.
- **PPR hyperparameters** (damping, iteration count) not surfaced in the abstract.
- **Static graph topology after ingest.** Later ingestion doesn't re-weight old edges based on new evidence.
- **Multi-hop benchmarks only** — claims don't clearly translate to agent-workflow memory where retrieval is not a Q&A.
- **No utility feedback** — same field-wide gap.
