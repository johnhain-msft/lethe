# HANDOFF — Lethe planning foundation complete

**Date:** 2026-04-23
**Repo:** https://github.com/johnhain-msft/lethe (private)
**Branch:** `main` — all work pushed.
**Prior DEV sessions:** two (WS0/WS1/WS2-A-B in session `db264ce8`; WS2-C + synthesis + this handoff in session `fc2c1115`).

Written for the **WS3 agent** (human or AI) who inherits this and executes the gap deep-dives + composition design.

---

## 1. What's done

### 1.1 Workstreams completed

| WS | Artifact | Location | Status |
|---|---|---|---|
| 0 | Project charter | `docs/00-charter.md` | ✅ committed |
| 1 | SCNS memory audit | `docs/01-scns-memory-audit.md` | ✅ committed |
| 1 | Dream-daemon design note | `docs/01b-dream-daemon-design-note.md` | ✅ committed |
| 2 | 21 lit-review briefs | `docs/02-lit-review/01-*.md` … `21-*.md` (skipping gap at 14-20 = Batch C; 21 is Karpathy) | ✅ committed |
| 2 | Cross-cutting synthesis | `docs/02-synthesis.md` | ✅ committed |

### 1.2 Commits on `main`

```
31d2f24  docs(ws2): synthesis across 21-brief lit review
288cc47  docs(ws2): lit briefs batch C (lifecycle gap + letta + ms-af + qmd + benchmarks)
8c93189  docs(ws2): lit briefs batch B (paper-list + graphiti)
75e73b9  docs(ws2): lit briefs batch A (foundational papers + karpathy)
d46f60b  docs(ws1): scns memory audit + dream-daemon design note
96dbdc3  docs(ws0): add project charter
24e1f9d  chore: initial repo scaffold
```

### 1.3 Brief inventory (21/21)

```
docs/02-lit-review/
├── 01-zep.md                        Zep / Rasmussen 2025, arXiv:2501.13956
├── 02-magma.md                      MAGMA / Jiang, arXiv:2601.03236
├── 03-shibui-magma-guide.md         UNREACHABLE — Medium 403 (noted in synthesis §4)
├── 04-memory-as-metabolism.md       Miteski 2026, arXiv:2604.12034
├── 05-cognitive-weave.md            Lee et al., arXiv:2506.08098
├── 06-paper-list.md                 Shichun-Liu agent-memory survey index
├── 07-memos.md                      MemOS / Li et al., arXiv:2505.22101
├── 08-hipporag.md                   HippoRAG / NeurIPS 2024, arXiv:2405.14831
├── 09-a-mem.md                      A-MEM / Xu, arXiv:2502.12110
├── 10-memevolve.md                  MemEvolve / Zhang, arXiv:2512.18746 (EvolveLab)
├── 11-memgpt.md                     MemGPT / Packer, arXiv:2310.08560
├── 12-graphiti.md                   getzep/graphiti (leading substrate)
├── 13-graphiti-mcp.md               Graphiti MCP server
├── 14-graphiti-issue-1300.md        Open issue confirming missing lifecycle
├── 15-letta.md                      Letta (productionized MemGPT + sleep-time)
├── 16-ms-agent-framework.md         microsoft/agent-framework
├── 17-qmd.md                        tobi/qmd (on-device hybrid retrieval)
├── 18-longmemeval.md                Benchmark — primary WS4 metric
├── 19-locomo.md                     Benchmark — secondary WS4, coherence + multi-modal
├── 20-dmr.md                        Benchmark — sanity check only (saturated)
└── 21-karpathy-wiki.md              Wiki-as-KB pattern reference
```

All briefs follow the uniform template (problem framing / architecture / scoring-or-retrieval math / API surface / scale claims + evidence / documented limits / how it relates to Lethe / gaps-or-hand-waves). Empty sections = explicit "not applicable: <why>"; nothing fabricated.

---

## 2. Where WS3 starts

### 2.1 Read these first (in order)

1. **`PLAN.md`** — north star, particularly §WS3 and §WS4.
2. **`docs/00-charter.md`** — problem framing + non-goals.
3. **`docs/02-synthesis.md`** — where the field hand-waves and what Lethe commits to owning. **This is the WS3 kickoff document.**
4. **`docs/02-lit-review/12-graphiti.md`** — leading substrate, most heavily annotated brief.
5. **`docs/02-lit-review/14-graphiti-issue-1300.md`** — the WS3 anchor issue. The single-sentence justification for why Lethe exists.
6. **`docs/02-lit-review/15-letta.md`** — closest living precedent; read operationally.
7. **`docs/02-lit-review/10-memevolve.md`** — cleanest four-verb API vocabulary (`encode / store / retrieve / manage`) to align Lethe with.
8. **`docs/01-scns-memory-audit.md`** + **`docs/01b-dream-daemon-design-note.md`** — the existing-system baseline the runtime layer evolves from.

### 2.2 WS3 scope (per PLAN §WS3)

Two tracks, both committed-to by synthesis §5:

**Track A — Composition design.**
Convert the settled shape (Graphiti substrate + Lethe runtime + MCP surface) into a layered architecture document + interface contracts. Deliverable: `docs/03-composition.md` (or similar).

**Track B — Gap deep-dives.**
Reconciled against PLAN.md §WS3 Track B (all 9 PLAN items accounted for — see synthesis §5 for the full mapping table). Each active slot becomes its own research + recommendation brief under `docs/03-gaps/`:

| Slot | Topic | PLAN #WS3 source | Synthesis anchor |
|---|---|---|---|
| gap-01 | Retention engine (utility-weighted promotion + demotion) | PLAN #4 | §3.1 |
| gap-02 | Utility-feedback loop | PLAN #1 | §3.2 |
| gap-03 | Hybrid scoring weights + tuning methodology | PLAN #2 | §3.3 |
| gap-04 | Multi-agent concurrency + merge policy (graph layer) | synthesis-extension | §3.4 |
| gap-05 | Enforced provenance (type-system invariant) | synthesis-extension | §3.5 |
| gap-06 | Extraction-quality instrumentation | synthesis-extension | §3.7 |
| gap-07 | Markdown-as-view vs graph-as-source + **scale envelope** (write-amp, concurrent-writes-from-swarm on the markdown surface, retrieval >10k) | PLAN #3 (broadened) | §3.8 |
| gap-08 | Crash-safety + durability contract | synthesis-extension | §3.10 |
| gap-09 (optional) | Non-factual memory scoping | synthesis-extension | §3.9 |
| **gap-10** | **Cross-agent peer messaging** | **PLAN #5 (restored)** | synthesis §5 substrate notes |
| **gap-11** | **Forgetting-as-safety** | **PLAN #6 (restored)** | synthesis §5 substrate notes |
| **gap-12** | **Intent classifier design** | **PLAN #8 (restored)** | synthesis §5 substrate notes |

**PLAN items already dispositioned (not WS3 slots):**

| PLAN # | Topic | Disposition |
|---|---|---|
| 7 | contradiction resolution beyond timestamp-invalidation | committed by WS2: bi-temporal invalidate, don't delete (§2.3 below; synthesis §1.2) |
| 9 | eval-set construction without confirmation bias | deferred to WS4 (`docs/04-eval-plan.md`) |

Each gap-brief should follow a per-gap template: **what the gap is / why it matters for Lethe / state of the art (cite lit-review briefs) / candidate v1 approaches with trade-offs / recommendation + residual unknowns.** For gap-10 / gap-11 / gap-12 the WS3 author should start from the substrate pointers and v1 heuristic seeds in synthesis §5 rather than re-hunting sources.

Cost/latency evaluation (synthesis §2.6) is a WS4 concern, not WS3.

### 2.3 Committed design decisions from WS0–WS2

WS3 does **not** need to re-litigate:

- **Substrate = Graphiti.** Apache-2.0, bi-temporal, MCP-exposed. Not Zep (managed service), not MAGMA (research-only), not Cognitive Weave (research-only). Justification: synthesis §5 "Canonical substrate recommendation."
- **Surface = MCP.** Cross-paper consensus (briefs 11/13/15/17). Not REST-first.
- **Write path = fast+async dual-stream.** Consensus (MAGMA, Letta, SCNS, Memory-as-Metabolism, Cognitive Weave, HippoRAG). Not per-query LLM-scheduled.
- **Contradiction handling = bi-temporal invalidate, don't delete.** Graphiti primitive; replaces SCNS name-keyed LWW.
- **API verbs** align with EvolveLab: `encode/store/retrieve/manage` → Lethe `remember / recall / promote / forget`.
- **Primary benchmark = LongMemEval.** Secondary = LoCoMo. DMR = sanity check. Justified in briefs 18/19/20.
- **Human surface = markdown.** Charter commitment; reconciled with graph-authoritative model in gap-07.
- **v1 non-goals (cite synthesis §2.10, §2.11):** parametric memory governance; ontology evolution. Charter addendum recommended.

---

## 3. Operating conventions (inherited, do not change without reason)

### 3.1 Commit style

- Conventional prefixes: `docs(ws0):`, `docs(ws1):`, `docs(ws2):`, `docs(ws3):`, `chore:`.
- **Mandatory trailer on every commit:**
  ```
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```
- Git identity:
  ```
  git -c user.name="John Hain" -c user.email="johnhain@users.noreply.github.com" commit …
  ```
- **Push after every commit.** User has authorized this.

### 3.2 Brief template (enforced — empty sections = fail)

Every lit-review-class brief uses exactly:
1. Problem framing
2. Architecture
3. Scoring / retrieval math
4. API surface
5. Scale claims + evidence
6. Documented limits
7. Relation to Lethe
8. Gaps / hand-waves it introduces

Header: `**URL:** … **Type:** … **Fetched:** YYYY-MM-DD`.
When a section has no data in the source: "not applicable: \<why\>" — never fabricate.

Gap-briefs (WS3 Track B) may adopt a different template (see §2.2 above), but the "never fabricate" rule carries over.

### 3.3 Unreachable sources

Running list lives in **`docs/02-synthesis.md` §4**. Currently only #03 (Shibui Medium, HTTP 403). If WS3 hits new unreachables, append to that table with source / reason / mitigation — do not fabricate content.

### 3.4 Environmental boundaries

- **`/Users/johnhain/Coding_Projects/scns`** — **read-only** for this project. Never modify.
- **`/Users/johnhain/Coding_Projects/lethe`** — this repo; docs-only so far.
- **No `npm`** — no package.json, no node tooling in scope.
- **No new lint/build/test infra** for docs-only work.

### 3.5 Session artifacts (not in repo)

Session `db264ce8` and `fc2c1115` workspace files under `~/.copilot/session-state/` hold:
- SCNS inventory raw output (`db264ce8/files/scns-audit-raw.md`) — useful if WS3 needs SCNS cross-references.
- Prior session plan + prior handoff (`db264ce8/handoff.md`).

WS3 session should start its own session-state directory.

---

## 4. Open items / known debts

Carried forward from WS0–WS2 that WS3 may want to address:

1. **Charter addendum** for v1 non-goals with synthesis citations (§2.10 parametric, §2.11 ontology evolution). ~1 page.
2. **WS4 evaluation plan** — gated on WS3 but can be sketched in parallel once gap briefs are ≈ half done. Three-benchmark harness (LongMemEval / LoCoMo / DMR) with cost dimension is the shape.
3. **Letta operational study** — synthesis §5 recommends *running* Letta with `enable_sleeptime=true` and measuring cost envelope before finalizing Lethe's dream-daemon design. This is an experiment, not a brief.
4. **Graphiti `mcp_server/README.md`** was not fetched in batch B (brief 13 noted this). WS6 needs it for tool-naming; cheap fetch.
5. **Survey paper arXiv:2512.13564** (parent of brief 06 paper list) was not fetched. Its own gap analysis could cross-check §2 of the synthesis. Optional, but low-effort.
6. **MemEvolve paper body** (brief 10) was abstract-only. Full paper would refine the four-verb API mapping.

None of the above is blocking; all are additive.

---

## 5. Fast verification after inheriting

Run these to confirm your starting state:

```bash
cd /Users/johnhain/Coding_Projects/lethe
git status                             # expect: clean, on main
git log --oneline -10                  # expect: 7 commits starting at 24e1f9d
ls docs/02-lit-review/ | wc -l         # expect: 21
wc -l docs/02-synthesis.md             # expect: ~180 lines
```

If any of those fails, read this handoff and the prior session handoff (`~/.copilot/session-state/db264ce8-83ef-4634-86b9-b1932e887a3e/handoff.md`) before proceeding.

---

## 6. One-paragraph north star, restated

Lethe is the **retention runtime layer** over Graphiti's bi-temporal graph substrate, exposed via MCP, that **closes the utility-feedback loop** no reviewed system closes today. Its distinctive v1 commitments are utility-weighted promotion/demotion, enforced provenance, multi-agent concurrency, and published scoring defaults — each justified by a specific cross-paper gap documented in `docs/02-synthesis.md` §2. Everything else — substrate choice, write-path shape, contradiction policy, API vocabulary, benchmark set — is inherited from cross-paper consensus and does not need to be re-invented.

Good luck.
