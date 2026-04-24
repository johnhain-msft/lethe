# 07 — MemOS: A Memory Operating System for LLMs

**URL:** https://arxiv.org/abs/2505.22101  **Type:** paper  **Fetched:** 2026-04-23
**Authors:** Li, Song, Wang et al. (22 authors). arXiv:2505.22101v1, May 2025.

## Problem framing
LLMs lack a unified, structured architecture for handling memory. They operate on two primitives — **parametric** memory (knowledge in weights) and **ephemeral activation** memory (runtime context). Emerging RAG adds **plaintext** memory but has no lifecycle management and no multi-modal integration. Net: no cross-cutting memory abstraction, no memory-level governance.

## Architecture
**MemOS** elevates memory to a first-class operational resource. Unifies three memory types:
- **Parametric** — weights.
- **Activation** — runtime/context.
- **Plaintext** — external stores (RAG-style).

Core abstraction: the **MemCube** — standardized memory unit that enables tracking, fusion, migration of heterogeneous memory across the three types. Provides structured, traceable access across tasks and contexts.

The paper frames MemOS as analogous to an OS kernel: it gives representation, organization, and governance primitives over the underlying memory modalities.

## Scoring / retrieval math
Not in the fetched abstract. The paper positions MemOS as an *architecture* paper — the governance and lifecycle are the contribution, not specific scoring formulas.

## API surface
Implicit in the MemCube abstraction: `track`, `fuse`, `migrate`, plus cross-type addressing. Exact interface not surfaced in the abstract.

## Scale claims + evidence
Not in the fetched abstract. 1.6 MB PDF; substantive benchmarks live inside.

## Documented limits
Not surfaced in the abstract. The paper calls itself foundational work ("first to elevate memory as first-class"), implying the implementation is reference-grade rather than production-ready.

## Relation to Lethe
**Conceptual cousin, not substrate.** MemOS and Lethe share framing — "memory-centric execution framework," "runtime over the underlying memory primitives" — but attack different scopes:
- MemOS unifies *parametric + activation + plaintext*. Lethe v1 scopes to plaintext (+ external substrates like Graphiti) and does **not** touch parametric memory. The charter's non-goals explicitly exclude weight-level interventions.
- The **MemCube** abstraction is a useful naming anchor. Lethe's internal memory unit will be closer to MAGMA's Event-Node (brief 02) or Cognitive Weave's Insight Particle (brief 05), but the idea of a *tracked, migrateable, provenance-carrying unit* is the common denominator.
- MemOS's lifecycle / governance framing reinforces the "retention is first-class" stance in `00-charter.md` §1.

## Gaps / hand-waves it introduces
- **Parametric memory management is hard.** The paper names it as a memory type but "governance over weights" is a research frontier — what primitive does MemOS actually give you here? Not clear from the abstract.
- **Multi-modal integration claimed** but not spec'd in the abstract.
- **No utility-feedback mechanism** — same gap the field shares.
- **No concurrency / multi-tenant story** in the abstract.
- **OS analogy** can over-promise. Actual operating systems have decades of primitives (paging, virtual memory, process isolation, syscalls). A single paper can't deliver all of that; which primitives MemOS actually concretizes is the empirical question the rest of the paper must answer — not visible in the abstract.
