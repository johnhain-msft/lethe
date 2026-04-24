# 10 — MemEvolve: Meta-Evolution of Agent Memory Systems

**URL:** https://arxiv.org/abs/2512.18746  **Type:** paper  **Fetched:** 2026-04-23
**Authors:** Zhang et al. arXiv:2512.18746v1, Dec 2025.
**Code:** `github.com/bingreeky/MemEvolve` (MemEvolve + **EvolveLab**).

> Note: PLAN.md's source-10 entry names "MemEvolve — Lifecycle/consolidation focus." This paper at 2512.18746 is the best-matching canonical MemEvolve. Brief was directed via web_search; abstract fetched from arXiv directly.

## Problem framing
Prior self-evolving memory systems let agents *accumulate experience* via manually engineered memory architectures (trajectory stores, experience distillation, reusable tools). But the **memory architecture itself is static** — it cannot meta-adapt to diverse tasks. Agents evolve their knowledge; they do not evolve *how they know*.

## Architecture — meta-evolutionary
MemEvolve **jointly evolves the agent's experiential knowledge and its memory architecture**. Contribution is the outer loop: memory-system-design becomes another search dimension that gradient over task feedback.

**EvolveLab** is the accompanying unified codebase that distills **twelve representative memory systems** into a modular design space with **four core operations**:
- **encode** — how new experiences become memories.
- **store** — representation / indexing.
- **retrieve** — access pattern (`provide_memory`).
- **manage** — lifecycle / consolidation / optimization (`take_in_memory`, persistence, init).

Each component becomes a pluggable module; MemEvolve searches over combinations for task performance.

## Scoring / retrieval math
The meta-learner's scoring is downstream task performance, not an intrinsic memory signal. The individual component implementations inherit their scoring from the twelve systems EvolveLab subsumes.

## API surface
**EvolveLab's four-phase lifecycle (per DeepWiki summary):**
1. **Initialization.**
2. **Retrieval** — `provide_memory`.
3. **Ingestion** — `take_in_memory`.
4. **Persistence.**

Plus a `manage` module that oversees lifecycle + optimization. This is the cleanest four-verb interface in the reviewed literature.

## Scale claims + evidence
- **Up to +17.06 % performance** over frameworks including SmolAgent and Flash-Searcher across four agentic benchmarks.
- Cross-task and cross-LLM generalization demonstrated.
- PDF is 10.7 MB → substantial experimental section.

## Documented limits
Not surfaced in the abstract. Meta-search is implicitly compute-intensive. Generalization claims are empirical on a fixed benchmark suite — external validity on agent-workflow tasks is an open question.

## Relation to Lethe
**Most directly useful paper for lifecycle modeling.** Concrete contributions:

1. **The `encode / store / retrieve / manage` decomposition is a clean template for Lethe's API surface** (WS6). Lethe's `remember` / `recall` / `promote` / `forget` from `00-charter.md` §4.1 maps onto this 1:1:
   - `remember` ≈ encode + store.
   - `recall` ≈ retrieve.
   - `promote` / `forget` ≈ manage.
   Adopting EvolveLab's vocabulary would align Lethe with a 12-system-unifying taxonomy.
2. **The four-phase lifecycle (init / retrieve / ingest / persist)** maps to SCNS's dream-daemon phase structure (§`01b-dream-daemon-design-note.md`). Concretely:
   - `init` ≈ dream-schema / dream-state bootstrap.
   - `retrieve` ≈ hybrid search in `memory/search.ts`.
   - `ingest` ≈ extraction + consolidation phases.
   - `persist` ≈ vault write-back + core-file-generator.
   Cross-validation: two independent projects converged on the same four-phase shape.
3. **Meta-evolution is v2+ territory for Lethe.** v1 ships a fixed architecture (per non-goals in charter). But logging the right signals in v1 lets a future Lethe do MemEvolve-style meta-search over its own components. Worth biasing the v1 telemetry toward this future.

## Gaps / hand-waves it introduces
- **Compute cost of meta-search** not quantified in abstract.
- **Which of the 12 systems** does MemEvolve's search converge on, and does the answer depend on the task? Core question for WS3.
- **No utility feedback story specific to MemEvolve.** The outer loop uses task reward; but how individual memories get utility signal is inherited from whichever component is in play.
- **Memory persistence across meta-architecture changes** is the obvious risk — if you evolve the architecture, what happens to memories written under the old one? Not clear from the abstract.
- **Twelve-system unification requires interface compromises.** The modular API may be least-common-denominator rather than best-per-component.
- **Not yet battle-tested beyond the paper.** arXiv preprint, Dec 2025.
