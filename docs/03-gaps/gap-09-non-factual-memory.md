# gap-09 — Non-factual memory shapes (preferences, procedures, narratives)

**Synthesis-extension slot** (synthesis §3.8 + §2.10).
**Tier:** extension (target 50–80 lines).
**Status:** active. Composition §3 commits to Graphiti as fact-canonical store; preferences/procedures/narratives don't fit a fact-edge cleanly. This brief specifies the storage shape.
**Substrate:** brief 11 MemGPT (`core memory` for persistent identity/preferences distinct from archival); brief 15 Letta (typed memory blocks: persona, scratchpad, shared); brief 16 MS Agent Framework (preference templates per agent); brief 21 Karpathy (synthesis pages = narrative shape); brief 02 MAGMA (procedural memory as a distinct module); SCNS audit §3 (synthesis pages serve preferences + procedures via author convention); composition §3 (S4a markdown synthesis pages own this).
**Cross-refs:** gap-03 scoring weights (preferences shouldn't decay like episodic facts); gap-12 intent classifier (`remember:preference` and `remember:procedure` are classifier outputs); gap-07 markdown-scale (S4a synthesis pages are the storage substrate).

---

## 1. The gap

Not all memory is a fact-edge. A user's preference ("prefer concise answers") is durable, doesn't decay, and isn't a graph relation. A procedure ("steps to deploy") is a sequence, not a fact-set. A narrative (a project's design history) is authored prose. Shoving these into Graphiti as edges either fails the modeling (a sequence isn't a graph) or pollutes recall (a preference returned as a "fact" looks weird).

If Lethe ships without an answer:

1. **Modeling abuse.** Preferences encoded as fact-edges decay or contradict spuriously.
2. **Recall noise.** Prose narratives chunked into edges return as graph-traversal soup.
3. **Authoring loss.** No clean home for "this is a knowledge page I wrote, treat it as authored."
4. **Karpathy's wiki problem reappears** — synthesis pages with no opinion about how they relate to the fact graph.

## 2. State of the art

- **Brief 11 MemGPT.** Distinct stores: `core memory` (persona/preferences, always in context) vs. `archival memory` (recall-on-demand). The cleanest taxonomy in the literature.
- **Brief 15 Letta.** Typed memory blocks: `persona`, `scratchpad`, `shared`. Implementation-specific; semantics overlap MemGPT.
- **Brief 16 MS AF.** Per-agent preference templates; opaque to other agents.
- **Brief 21 Karpathy.** Synthesis pages = authored prose; canonical form for narratives.
- **Brief 02 MAGMA.** Procedural memory is a separate module from declarative.
- **SCNS audit §3.** Synthesis pages serve all three by author convention (preferences in `~/.claude/CLAUDE.md`, procedures in synthesis pages, narratives in design notes); no system-level distinction.

## 3. Storage shapes (specification)

| Memory shape | Storage | Durability | Recall path |
|---|---|---|---|
| **Episodic fact** | S1 fact-edge | bi-temporal | graph + vector + BM25 hybrid |
| **Preference** | S4a markdown synthesis page tagged `kind=preference` | non-decaying; explicit revision events | always-load on tenant init (MemGPT-style "core memory") |
| **Procedure** | S4a markdown synthesis page tagged `kind=procedure` | versioned; supersession via gap-13 timestamps | recall-on-demand; cite preference for procedural retrieval |
| **Narrative** | S4a markdown synthesis page tagged `kind=narrative` | append-mostly; rarely revised | recall-on-demand; treated as authored, not derived |

S4a's role (composition §3) was always "human-authored synthesis"; this brief sharpens the kinds.

## 4. Candidate v1 approaches

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) S4a-typed pages (above spec)** | Each non-factual memory is a markdown page with `kind=` frontmatter; runtime treats `kind=preference` as always-load. | Reuses existing substrate; auditable; human-editable. |
| **(b) Distinct store per shape** | Separate stores for preferences/procedures/narratives. | Cleaner taxonomy; more substrate to operate. |
| **(c) Encode in S1 with shape-tags** | Force preferences/etc. into S1 with metadata distinguishing kind. | Single store; modeling abuse risk per §1.1. |

## 5. Recommendation

**Candidate (a) — typed S4a pages.** Justification:

1. Composition §3 already gave S4a as the home for authored synthesis; this brief sharpens "authored synthesis" with three sub-kinds.
2. MemGPT's "core memory always loaded" maps to "preference pages always loaded into tenant init context"; cheap.
3. Procedures benefit from human revision + git history (composition §3 row S4a notes git as recommended for S4a).
4. Narratives are exactly the existing synthesis page; no new substrate needed.

**Stop-gap.** v0 = preferences-only; defer procedures and narratives until usage demands them.

## 6. Residual unknowns

- **Preference contradiction.** Two preferences contradict ("verbose" vs. "concise"); resolution policy = most-recent-revision-wins, with the prior preserved by git history. Bridges to gap-13 (contradiction) at the markdown layer.
- **Always-load bandwidth.** How many preference pages can a tenant accumulate before they crowd context budgets? Bet: cap preference-page total length at 10 KB per tenant; instrument.
- **Procedural execution.** Is a stored procedure executable, or just human-readable? v1: human-readable only; agents read and follow. Bridges to a v2 "tool definition" shape.
- **Narrative-to-fact lift.** A narrative might describe a fact ("we decided to use Graphiti"). Should the runtime extract that fact into S1? Bet: yes, lazily, via the same extraction pipeline (gap-06); narrative is the source episode; provenance points back.

## 7. Touch-points

- **gap-03 scoring weights** — preferences score at 1.0 always; procedures decay slowly; narratives somewhere in between.
- **gap-07 markdown-scale** — S4a write-amp budget includes preferences + procedures + narratives.
- **gap-12 intent classifier** — `remember:preference` / `remember:procedure` outputs route here.
- **gap-13 contradiction resolution** — preference contradictions resolve via revision-wins.
- **WS6 (API)** — `remember(payload, kind=preference|procedure|narrative)`; `recall` returns kind-tagged results.
- **WS7 (migration)** — SCNS `~/.claude/CLAUDE.md` → preference pages; SCNS synthesis pages → narrative pages by default.
