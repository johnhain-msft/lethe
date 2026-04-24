# 21 — Karpathy: Wiki-as-Knowledge-Base Pattern

**URL:** https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f  **Type:** pattern / design note  **Fetched:** 2026-04-23
**Author:** Andrej Karpathy. Gist.

## Problem framing
RAG **rediscovers knowledge from scratch on every question**. Nothing accumulates. Ask a subtle synthesis question, LLM has to re-piece 5 documents every time. Proposal: between the user and raw sources, put a **persistent, compounding wiki** — LLM-maintained, markdown, interlinked, with cross-refs, contradictions, synthesis *already done*.

## Architecture — three layers
1. **Raw sources** — articles, papers, images. Immutable. LLM reads, never writes.
2. **The wiki** — directory of LLM-generated markdown files: summaries, entity pages, concept pages, comparisons, an overview, a synthesis. LLM owns this layer entirely.
3. **The schema** — a document (`CLAUDE.md` / `AGENTS.md`) telling the LLM how the wiki is structured, conventions, workflows for ingest / query / lint. Co-evolved between user and LLM per domain.

Two navigation files:
- **`index.md`** — content-oriented catalog. Every page listed with a one-line summary. Updated on every ingest. LLM reads this first when answering.
- **`log.md`** — chronological, append-only. Entries with consistent prefix (e.g. `## [2026-04-02] ingest | Article Title`) → parseable with unix tools.

## Scoring / retrieval math
**No math.** Retrieval is LLM-driven over `index.md` first, then drilling into pages. At moderate scale (~100 sources, ~hundreds of pages) this works without embeddings. Past that threshold, the gist references **qmd** (brief 17) as the recommended local hybrid BM25/vector/LLM-rerank search engine.

## API surface — three operations (conceptual, no code)
- **Ingest** — drop source → LLM reads → discusses takeaways → writes summary page → updates index → updates relevant entity/concept pages → appends log entry. A single source can touch 10–15 wiki pages.
- **Query** — LLM searches relevant pages, synthesizes answer with citations. Answer format varies (page / table / slide deck / chart). **Good answers get filed back into the wiki** so explorations compound.
- **Lint** — periodic health check: contradictions, stale claims, orphan pages, missing cross-refs, data gaps. Not on every write.

## Scale claims + evidence
- **Claimed ceiling:** "moderate scale (~100 sources, ~hundreds of pages)" works without embeddings.
- **Anecdotal evidence only.** No benchmarks. Karpathy notes he uses Obsidian as IDE + LLM as programmer; ingestion is one-at-a-time with him in the loop.
- For larger scale, the gist punts to qmd.

## Documented limits (explicit)
- **No concurrency / merge / lock story** — single-user assumption. "I prefer to ingest sources one at a time and stay involved."
- **Consolidation is human-driven** — user guides emphasis during ingest.
- **Contradiction handling is informal** — "LLM flags it" via lint. No audit trail, no SLA.
- **Provenance implicit in frontmatter** — not mandated.
- **No privacy / secret sanitization.** Markdown is just files.
- **No ACID / durability story.** Crash mid-write = corrupt wiki. Git recovery is the only safety net.
- **Write amplification.** "A single source might touch 10–15 wiki pages." At agent-loop rates, this is a lot of churn.
- **LLMs can't natively read markdown with inline images in one pass** — requires workaround (read text then view images).

## Relation to Lethe
**This is the human-facing inspiration.** Markdown-as-surface is preserved in Lethe (per PLAN.md scope call #5). But every single explicit limit above is a problem Lethe must own:

| Karpathy limit | Lethe requirement |
|---|---|
| Single-user | Multi-agent by design (§00-charter §4.1) |
| Human-driven consolidation | Unattended consolidation — SCNS dream-daemon candidate |
| Informal contradiction flag | Timestamped invalidate-don't-delete (Zep/Graphiti pattern, WS3 gap #7) |
| Implicit provenance | Enforced provenance on every memory |
| No privacy | SCNS sanitize-pipeline ported (§audit §2) |
| No ACID | Service-grade durability; crash-safe writes |
| Write amplification | Rate-limited / batched updates; diff-aware merges |
| ~100 sources, ~hundreds of pages | 10 k+ sources target (PDF gap §scale) |

The **`index.md` + `log.md`** pattern maps cleanly onto SCNS's `MEMORY.md` (synthesized index) + `daily/*.md` (chronological trackpad). Lethe inherits this bifurcation.

## Gaps / hand-waves it introduces
- **Scale ceiling.** ~100 sources is explicitly the proven envelope; 10 k+ is unvalidated.
- **Agent-only operation.** "Agent swarms cannot [human-drive consolidation] — nobody's watching." The pattern as written does not survive removing the human.
- **No utility feedback.** The wiki gets richer but no signal tells the system which pages actually got used to answer queries well.
- **Schema is domain-specific.** `CLAUDE.md` / `AGENTS.md` is co-evolved per domain — there is no portable default.
- **Lint cadence unspecified** — "periodically."
- **"File good answers back into the wiki"** — who decides which answers? Humans in Karpathy's setup; no mechanism proposed for unattended operation.
- **No latency / storage ceiling** published.
- **No multi-wiki composition** — one user, one wiki.
