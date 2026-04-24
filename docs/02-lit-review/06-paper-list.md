# 06 — Agent Memory Paper List (Shichun-Liu)

**URL:** https://github.com/Shichun-Liu/Agent-Memory-Paper-List  **Type:** survey repo (paper index + associated survey paper)  **Fetched:** 2026-04-23

## Problem framing
The agent-memory field is fragmented — loose terminology, inconsistent taxonomies. Repo aims to unify the literature under one taxonomy and curate a running index of papers. The associated survey is published as arXiv:2512.13564 ("Memory in the Age of AI Agents: A Survey").

## Architecture (of the taxonomy itself)
Three orthogonal lenses:
1. **Forms — what carries memory?**
   - **Token-level** — explicit, discrete memory (stored text).
   - **Parametric** — implicit, in-weights.
   - **Latent** — hidden states.
2. **Functions — why agents need memory?**
   - **Factual** — knowledge.
   - **Experiential** — insights / skills.
   - **Working memory** — active context management.
3. **Dynamics — how memory evolves?**
   - **Formation** — extraction.
   - **Evolution** — consolidation + forgetting.
   - **Retrieval** — access strategies.

Distinguished from RAG and Context Engineering as a first-class primitive.

## Scoring / retrieval math
N/A — this is an index, not an algorithm. The survey paper itself (2512.13564) presumably carries synthesis math, but that is a separate fetch.

## API surface
N/A — browsable paper list on GitHub with papers organized under Factual / Experiential / Working with Token-level / Parametric / Latent sub-buckets.

## Scale claims + evidence
- Repo has 1 k+ stars (as of 2026/01/29 per repo news).
- Survey featured on HuggingFace Daily Papers (#1 on 2025/12/16).
- Paper list spans from Oct 2023 through Jan 2026; dense — roughly 80+ papers indexed in the Factual Memory / Token-level section alone.

## Documented limits
- The taxonomy is the contribution; the repo does **not** synthesize each paper — it catalogs.
- Paper inclusion is contributor-driven; coverage is best-effort.
- No cross-paper gap analysis in the repo itself (that lives in the arXiv survey).

## Relation to Lethe
**Standing subscription** per PLAN.md WS2 mandate ("re-check before the implementation plan lands"). Two concrete uses:
1. **Taxonomic vocabulary.** Lethe's charter and API should speak in Form / Function / Dynamics terms where natural. "Agent-workflow memory" maps cleanly to *Experiential* function + *Token-level* form; this gives Lethe a defensible positioning in the field.
2. **Gap-hunting.** Papers the PDF missed but the repo catalogues (a partial list of directly-relevant ones surfaced in the fetched section):
   - **O-Mem** (2511.13593) — self-evolving agents.
   - **Mem-α** (2509.25911) — RL-learned memory construction.
   - **Nemori** (2508.03341) — self-organizing memory inspired by cognitive science.
   - **LightMem** (2510.18866) — lightweight memory-augmented gen (explicit sleep-time consolidation).
   - **HippoRAG** (2405.14831) — neurobiologically inspired long-term memory.
   - **AriGraph** (2407.04363) — knowledge-graph world model.
   - **MIRIX** (2507.07957) — multi-agent memory system.
   - **RGMem** (2510.16392) — renormalization-group-based memory evolution.
   - **Hindsight is 20/20** (2512.12818) — agents that retain, recall, reflect.
   - **Memory-R1** (2508.19828) — RL for memory management.
   
   Several overlap with PLAN.md gap deep-dives. WS3 should harvest this list when evaluating specific gaps.

## Gaps / hand-waves it introduces
- **Temporal drift of the list.** A pointer-to-papers is only as current as the last PR. PLAN.md treats this as a *feed*, re-checked before implementation lands.
- **No quality filter.** The index is inclusive; Lethe must do its own relevance triage.
- **Survey paper 2512.13564 not fetched** in this brief. If WS3 needs the unified survey's own gap analysis, that's a separate read.
- **Taxonomy vs. architecture.** The Form/Function/Dynamics cut is orthogonal to the PDF's substrate/runtime cut. Lethe lives at the *runtime* layer but must serve all three Functions — useful cross-check but the two taxonomies don't merge.
