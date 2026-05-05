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
| 2 | 22 lit-review briefs | `docs/02-lit-review/01-*.md` … `22-*.md` (21 = Karpathy; 22 = auto-memory, added post-WS3) | ✅ committed |
| 2 | Cross-cutting synthesis | `docs/02-synthesis.md` | ✅ committed |
| 2 | QA review of WS0–WS2 foundation | `docs/QA-WS0-WS2.md` | ✅ APPROVE-WITH-NITS, all nits fixed in `88f8865` |
| 3 | Composition design (Track A) | `docs/03-composition-design.md` | ✅ committed |
| 3 | 14 gap briefs (Track B) | `docs/03-gaps/gap-01-*.md` … `gap-14-*.md` | ✅ committed |
| 3 | QA review of WS3 | `docs/QA-WS3.md` | ✅ APPROVE-WITH-NITS, all nits fixed in `558f830` |

### 1.2 Commits on `main`

```
72a89d9  docs(lit-review): add auto-memory brief (#22) + cite in synthesis §1 and gap-09
558f830  docs(ws3): apply WS3 QA nits (recall_synthesis, tenant-init bootstrap, latency stratification, ...)
de6a525  docs(qa): WS3 review (APPROVE-WITH-NITS, 4.7/5)
df20592  docs(ws3): handoff update for WS4/WS5/WS6/WS7/WS8
db427aa  docs(ws3): quality+eval briefs (14 eval-set-bias, 06 extraction-quality, 09 non-factual-memory)
5a7d934  docs(ws3): multi-agent briefs (10 peer-messaging, 12 intent-classifier, 05 provenance-enforcement)
15a91b4  docs(ws3): surface/scale briefs (07 markdown-scale, 04 multi-agent-concurrency, 08 crash-safety)
7fde808  docs(ws3): forgetting + contradiction briefs (gap-11, gap-13)
c07f515  docs(ws3): lifecycle gap briefs (01 retention, 02 utility-feedback, 03 scoring-weights)
6996f73  docs(ws3): composition design (track A)
88f8865  docs: reconcile WS3 gap list with PLAN.md §WS3 Track B (fix WS0-WS2 QA MAJORs)
b9965de  docs(qa): WS0-WS2 foundation QA review (APPROVE-WITH-NITS)
efa2069  docs: add HANDOFF.md for WS3 entry
31d2f24  docs(ws2): synthesis across 21-brief lit review
288cc47  docs(ws2): lit briefs batch C (lifecycle gap + letta + ms-af + qmd + benchmarks)
8c93189  docs(ws2): lit briefs batch B (paper-list + graphiti)
75e73b9  docs(ws2): lit briefs batch A (foundational papers + karpathy)
d46f60b  docs(ws1): scns memory audit + dream-daemon design note
96dbdc3  docs(ws0): add project charter
24e1f9d  chore: initial repo scaffold
```

**HEAD = `72a89d9`.** WS0–WS3 + QA + nits + auto-memory addition all on `origin/main`.

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
├── 21-karpathy-wiki.md              Wiki-as-KB pattern reference
└── 22-auto-memory.md                dezgit2025/auto-memory — sibling product (single-user CLI shim over host session-store; validates recall verb demand; not a substrate)
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

---

# Post-WS3 — gap deep-dives + composition design landed

**Date:** 2026-04-25
**Branch:** `main` — all WS3 work pushed.
**Session:** `f0f31342` (this DEV session).

WS3 is complete. WS4 (eval), WS5 (scoring formalism), WS6 (API), WS7 (migration), and WS8 (deployment) authors should read this section + the linked artifacts before starting.

## 7. WS3 deliverables

### 7.1 Composition design (Track A)

`docs/03-composition-design.md` — 423 lines. Reference architecture for the runtime. Read this *before* any gap brief.

Key commitments:
- **Five named stores** (§2): Graphiti (S1, fact-canonical), SQLite metadata + ledger + log (S2/S5), vector index (S3, rebuildable), markdown synthesis pages (S4a, authored), markdown projections (S4b, derived).
- **ACID boundaries** (§5): T1 = `remember` synchronous (S1 episode + S2 arrival event); T2 = `promote/forget` synchronous (S2 flag + S5 audit). Everything else eventual-consistent + reconcilable.
- **Failure-mode matrix** (§7): 13-row table + 2-stores-down combinations. WS6 + WS7 lean on this most.
- **Recommended topology** (§8): hybrid layered. Dividing line at *factual claim vs. authored synthesis*.
- **Open seams handed to gap briefs** (§10).

### 7.2 Gap briefs (Track B)

`docs/03-gaps/gap-01..gap-14.md` — 14 briefs, 1742 lines total.

| Gap | Slug | Tier | Lines | PLAN # |
|---|---|---|---|---|
| gap-01 | retention-engine | first-class | 149 | #4 unattended consolidation |
| gap-02 | utility-feedback | first-class | 136 | #1 |
| gap-03 | scoring-weights | first-class | 169 | #2 |
| gap-04 | multi-agent-concurrency | extension | 65 | (synthesis-extension) |
| gap-05 | provenance-enforcement | extension | 100 | (synthesis-extension) |
| gap-06 | extraction-quality | extension | 73 | (synthesis-extension) |
| gap-07 | markdown-scale | first-class | 170 | #3 (broadened) |
| gap-08 | crash-safety | extension | 103 | (synthesis-extension) |
| gap-09 | non-factual-memory | extension | 75 | (synthesis-extension) |
| gap-10 | peer-messaging | first-class | 111 | #5 |
| gap-11 | forgetting-as-safety | first-class | 171 | #6 |
| gap-12 | intent-classifier | first-class | 100 | #8 |
| gap-13 | contradiction-resolution | first-class | 202 | #7 |
| gap-14 | eval-set-bias | first-class | 95 | #9 |

All 9 PLAN-mandated gaps are first-class with ≥80 lines.

**Scope-expansion vs. §2.2 disposition.** §2.2 (pre-WS3) listed PLAN #7 as "committed by WS2" and PLAN #9 as "deferred to WS4," excluding both from WS3 slots; WS3 deliberately upgraded these to first-class briefs — gap-13 became "monitored stress regimes" (not re-litigation of bi-temporal invalidate) and gap-14 became the first-class WS4 input-constraint document. The §2.2 dispositions are superseded for these two items only.

### 7.3 Commits

```
db427aa  docs(ws3): quality+eval briefs (14 eval-set-bias, 06 extraction-quality, 09 non-factual-memory)
5a7d934  docs(ws3): multi-agent briefs (10 peer-messaging, 12 intent-classifier, 05 provenance-enforcement)
15a91b4  docs(ws3): surface/scale briefs (07 markdown-scale, 04 multi-agent-concurrency, 08 crash-safety)
7fde808  docs(ws3): forgetting + contradiction briefs (11, 13)
c07f515  docs(ws3): lifecycle gap briefs (01-03)
6996f73  docs(ws3): composition design (track A)
```

## 8. Pointers for downstream workstreams

### 8.1 WS4 — eval plan author

Read first:
1. `docs/03-gaps/gap-14-eval-set-bias.md` — **your input constraints**. WS4 must satisfy §5(1)–(5) (multi-source eval set, capped author-share, contamination defenses, drift signals, two-strata reporting).
2. `docs/03-gaps/gap-12-intent-classifier.md` — classifier accuracy is your headline metric.
3. `docs/03-gaps/gap-06-extraction-quality.md` §3 — extraction F1 + per-domain calibration.
4. `docs/03-gaps/gap-01-retention-engine.md` §6 — eval signals that decide keep/replace/extend on the dream-daemon (per-phase).
5. `docs/03-gaps/gap-02-utility-feedback.md` — utility signals are *not* the eval set; relationship clarified there.
6. `docs/03-composition-design.md` §7 — failure-modes you must inject (chaos/fault eval).

**Reporting epochs.** v1.0 eval reports will be tagged **"preliminary, author-share above threshold"** until operator data accumulates (per `gap-14 §5(1)` and §5 step "If WS4 cannot meet (1) at launch"); plan for two reporting epochs (v1.0 launch / v1.x once operator-derived slice fills in) from day one.

### 8.2 WS5 — scoring formalism author

Read first:
1. `docs/03-gaps/gap-03-scoring-weights.md` — your starting point; defines weight categories, calibration loop, defaults to publish.
2. `docs/03-gaps/gap-02-utility-feedback.md` — signal taxonomy that feeds scoring.
3. `docs/03-gaps/gap-09-non-factual-memory.md` §7 — different memory shapes score differently.
4. `docs/03-gaps/gap-12-intent-classifier.md` §8 touch-point — classifier output drives per-class scoring.
5. `docs/03-composition-design.md` §3 — what's stored where; scoring metadata lives in S2.

### 8.3 WS6 — API author

Read first:
1. `docs/03-composition-design.md` §3 (ownership matrix) + §4 (read/write paths) + §5 (consistency model). This is your contract.
2. `docs/03-composition-design.md` §7 (failure-mode table) — error semantics per verb.
3. `docs/03-gaps/gap-04-multi-agent-concurrency.md` §5 — version-CAS contract on writes; `409` retry semantics.
4. `docs/03-gaps/gap-08-crash-safety.md` §3 — idempotency-key contract on every write verb.
5. `docs/03-gaps/gap-10-peer-messaging.md` §3 — `peer_message`, `peer_message_pull`, `peer_message_status` verbs.
6. `docs/03-composition-design.md` §3.2 — `recall_synthesis(uri | query)` verb for S4a-targeted (markdown synthesis) retrieval; distinct from fact-path `recall`. Plus §3.5 — implicit `preferences[]` prepend on every `recall` response (always-load path).
7. `docs/03-gaps/gap-11-forgetting-as-safety.md` §3 — `forget(soft|purge|deny)` semantics, retention proofs.
8. `docs/03-gaps/gap-12-intent-classifier.md` — `remember(intent=...)` API shape.
9. `docs/03-gaps/gap-05-provenance-enforcement.md` §3 — `recall` response shape includes provenance.

### 8.4 WS7 — migration author

Read first:
1. `docs/03-composition-design.md` §7 (failure modes) + §5 (consistency model) — what an in-place migration must preserve.
2. `docs/03-gaps/gap-08-crash-safety.md` §3.5 — `lethe-audit lint --integrity` is a phase-gate in WS7.
3. `docs/03-gaps/gap-05-provenance-enforcement.md` §6 — episode-id stability is a migration invariant.
4. `docs/03-gaps/gap-09-non-factual-memory.md` §7 — SCNS `~/.claude/CLAUDE.md` → preference pages; SCNS synthesis pages → narrative pages.
5. `docs/03-gaps/gap-04-multi-agent-concurrency.md` §6 — SCNS broker-DB row-locking translates to CAS contracts.

### 8.5 WS8 — deployment author

Read first:
1. `docs/03-composition-design.md` §7 — degraded modes are deploy-cadence aware.
2. `docs/03-gaps/gap-01-retention-engine.md` §3.2 — dream-daemon scheduler config (gate interval, lock heartbeat).
3. `docs/03-gaps/gap-08-crash-safety.md` §3.4 + §3.5 — startup integrity check + lock recovery.
4. `docs/03-gaps/gap-14-eval-set-bias.md` §5(3) — drift detector + monthly re-eval cadence.

## 9. Stopping criteria — evidence

1. ✅ `docs/03-composition-design.md` — committed `6996f73`, pushed.
2. ✅ `docs/03-gaps/` — 14 briefs; 9 first-class ≥80 lines; all template sections substantive.
3. ✅ Incremental commits (6 batches: composition + 5 brief batches) on `main`; all pushed.
4. ✅ This Post-WS3 section appended to HANDOFF.md.

WS3 is closed. The next QA pass should ask: **"Does WS3 give a WS4 (eval) author and a WS5 (scoring) author enough substrate to start without re-doing research?"** §8.1 + §8.2 above are the explicit reading orders.

---

## 10. Post-WS4 — what the WS4 author produced

### 10.1 Workstream completed

- ✅ **WS4 — Eval & Benchmark plan** (per PLAN §WS4). Two-epoch design (v1.0 preliminary / v1.x post-operator-data) baked in throughout. Headline metrics, Lethe-native eval set with capped author-share, contamination defenses, drift signals, two-strata reporting all present and traceable to gap-14 §5(1)–(5).

### 10.2 Commits on `main` (post-WS3)

- `499f8c8` — `docs(ws4): add eval & benchmark plan`
- `1c38670` — `feat(ws4): scripts/eval skeleton stubs`
- (this commit) — `docs(handoff): post-WS4 update for WS4-QA + WS5`

### 10.3 Architectural correction landed during WS4 — Lethe stands on its own

A mid-WS4 course correction revoked an earlier assumption that SCNS `session_store` would be the v1.0 operator-trace source. The corrected position, encoded in `docs/04-eval-plan.md` and binding on all downstream WS:

- **Lethe is independent.** No Lethe artifact reads from `~/.scns/`. No Lethe code imports from the SCNS repo. No Lethe eval input comes from `session_store`. The SCNS dream-daemon remains a **design-pattern reference only** (per WS1 audit and gap-01); it is not a substrate, dependency, or data source.
- **The v1.0 operator slice is empty (0%).** gap-14 §5(1)'s 30% operator-derived target is a **v1.x target, not a v1.0 launch target**. v1.0 reports are tagged `preliminary — operator slice empty (0%); author + adversarial + ablation + synthetic only; v1.x target 30% operator-derived` (mandatory headline-tag, rendered by `metrics/emitter.py`, non-removable at the harness layer).
- **The v1.x operator slice comes from Lethe's own opt-in audit-log capture.** `docs/04-eval-plan.md` §4.6 specifies the pipeline; `scripts/eval/lethe_native/loader.py::capture_opt_in_trace` defines the contract surface; WS6 owns the opt-in verb implementation.

**Binding on WS5, WS6, WS7:**
- **WS5 (scoring)** — do not plan calibration data sourced from SCNS or any foreign system. Use the eval-set output as ground truth (per `docs/04-eval-plan.md` §6 per-phase signals).
- **WS6 (API)** — do not plan a SCNS compatibility shim that reads SCNS data into Lethe stores. Do plan the opt-in audit-log capture verb that powers v1.x operator-trace ingest (`docs/04-eval-plan.md` §4.6 contract).
- **WS7 (migration)** — eval-set ingest is **not** a WS7 concern. WS7 should not plan against SCNS or any foreign system as a Lethe substrate or data source.

### 10.4 Reading order for **WS4-QA** (fresh-eyes pass)

The WS4-QA author should approach this cold and answer one question: **does this give a WS5/WS6 author enough substrate to start without re-doing eval-design research?**

Read in this order:

1. `docs/04-eval-plan.md` start to finish. Pay particular attention to §2 (epochs), §4 (Lethe-native eval set including §4.6 self-collection), §5 (headline metrics), §6 (per-phase dream-daemon signals — WS5's input contract), §7 (chaos eval coverage), §9 (shadow-retrieval), §10 (harness layout), Appendix A (gap-14 §5(1)–(5) traceability matrix — required by stopping criteria).
2. `scripts/eval/README.md`. Verify the layout described matches the layout in §10.
3. `scripts/eval/run_eval.py` and one stub from each subdirectory (`adapters/longmemeval.py`, `lethe_native/loader.py`, `metrics/emitter.py`, `shadow/harness.py`, `chaos/faults.py`, `contamination/guard.py`). Verify each names its contract via docstring + cross-ref, and that the stub exits 2 with `"<module>: not implemented (WS4 stub)"` on the inert path.
4. `docs/03-gaps/gap-14-eval-set-bias.md` §5(1)–(5) cross-checked against `docs/04-eval-plan.md` Appendix A. Are all five constraints addressed §-by-§? Constraint §5(1) is the one to scrutinize: it must be marked **acknowledged-and-deferred** at v1.0 (operator slice = 0%), with the v1.x migration plan explicit.
5. `docs/03-gaps/gap-12-intent-classifier.md` and `docs/03-gaps/gap-06-extraction-quality.md` cross-checked against §5.6 and §5.7 of the eval plan. Are macro-F1 (gap-12 headline) and per-domain extraction calibration (gap-06 §3) both first-class metrics?
6. `docs/03-gaps/gap-01-retention-engine.md` §6 cross-checked against §6 of the eval plan. Are the per-phase signals (extract / score / promote / demote / consolidate / invalidate) named with measurable signals and stratification?
7. `docs/03-composition-design.md` §7 + §7.1 cross-checked against §7 of the eval plan. Is every named failure mode covered by the chaos harness, including the two-stores-down matrix?

**Anti-checklist (things that should NOT be present):**
- Any WS4 artifact that reads from `~/.scns/` or imports from the SCNS repo.
- Any v1.0 report path that emits a headline number without the preliminary-tag wording.
- Any public-benchmark report path that emits accuracy without an accompanying cost row (§3.4 invariant).
- Any case-set build that bypasses the §4.1 floors/caps or the §4.3 symmetry policy.

A QA failure on any of the above is a P0; a QA failure on a missing or weak cross-ref is a P1.

### 10.5 Reading order for **WS5** (scoring formalism author)

WS5 inherits an explicit input contract from WS4: the per-phase eval signals in `docs/04-eval-plan.md` §6 are the keep/replace/extend criteria for the scoring function modules.

Read in this order:

1. `docs/03-gaps/gap-03-scoring-weights.md` — your starting point, unchanged.
2. `docs/03-gaps/gap-02-utility-feedback.md` — signal taxonomy that feeds scoring; the `δ·utility_signal` term.
3. **`docs/04-eval-plan.md` §6** — per-phase signals; this is what your scoring math will be calibrated against. WS5's keep/replace/extend decisions on extract / score / promote / demote / consolidate / invalidate are gated by the metrics named in §6.
4. **`docs/04-eval-plan.md` §5.5** — promotion precision **and** demotion recall (gap-01 §6 needs both). Your scoring-side promotion/demotion threshold tuning targets these.
5. `docs/03-gaps/gap-09-non-factual-memory.md` §7 — different memory shapes score differently; per-class scoring must accommodate `remember:preference` separately from `remember:fact`.
6. `docs/03-gaps/gap-12-intent-classifier.md` §8 touch-point — classifier output drives per-class scoring.
7. `docs/03-composition-design.md` §3 — what's stored where; scoring metadata lives in S2.

**Binding constraints from WS4 (do not work around):**
- Do not source calibration data from SCNS or any foreign system. Use Lethe's own eval-set ground truth.
- The two-strata reporting requirement (eval plan §5.9) means scoring weights should be tuned against the **strict stratum** (operator + adversarial + ablation + replay-only), not the all-cases stratum, when those diverge. At v1.0 the strict stratum has no operator share; tune against adversarial + ablation + replay-only and accept the deferral cost.
- The mandatory headline-tag wording at v1.0 means any scoring-related public report must render the tag; `metrics/emitter.py::render_headline_tag` is the single rendering point.

### 10.6 Open items / follow-throughs WS4 left for downstream

- **Adversarial reviewer pipeline (v1.0 35% slice).** WS4 specifies "internal-but-different-team reviewer"; the reviewer-recruitment and review-tracking workflow is a v1.0 schedule risk. Owner: WS8 (deployment) / project lead.
- **Opt-in audit-log capture verb (WS6).** v1.x operator-trace ingest depends on this verb. Contract is set in `scripts/eval/lethe_native/loader.py::capture_opt_in_trace`; implementation owner is WS6.
- **Chaos eval CI integration (WS8).** The chaos harness is wired (`scripts/eval/chaos/faults.py`) but the deploy-cadence integration (when the chaos run executes against a candidate build) is WS8's call.
- **Drift detector (gap-14 §5(3) / eval plan §8).** WS4 specifies the cadence (monthly held-set re-eval; quarterly fresh adversarial slice; annual eval-set version bump). WS8 schedules.

WS4 is closed. The next QA pass should ask: **"Does WS4 give a WS5 (scoring) author and a WS6 (API) author enough substrate to start without re-doing eval-design research?"** §10.4 (QA reading order) and §10.5 (WS5 reading order) are the explicit answers.

## §11 Post-WS5 update — scoring formalism shipped

### 11.1 What WS5 produced

`docs/05-scoring-design.md` (600 lines, single commit). Scope:

- **Two scoring surfaces** formalized with explicit math: consolidate-time additive `score(f) = gravity_mult(f) · [α·type + β·recency + γ·connectedness + δ·utility − ε_eff·contradiction]`; recall-time `rerank(f, q) = rrf(f, q) · (1 + w_intent · intent_match · classifier_conf) + w_utility(t) · utility(f)` after a bi-temporal validity filter. Defaults align with gap-03 §5 candidate (a).
- **Per-term derivations** carry explicit named formulas, units, value ranges, and lit-review provenance: Cognitive Weave (recency residual + decay), HippoRAG (PPR connectedness with 2-hop subgraph cap and degree-percentile fallback), gap-02 (utility weighted aggregate), MaM (gravity as demotion-floor multiplier — Q1), MAGMA (intent-routed multiplicative bonus — Q2), gap-13 (log-dampened ε for contradiction oscillation control).
- **Per-class dispatch** exhaustive over the four persistent shapes from gap-09 §3 (episodic-fact, preference, procedure, narrative) — explicit per-class formulas and a dispatch table indexed by `kind` frontmatter and intent (Q3). Non-persistent classifier outputs (`reply_only`, `peer_route`, `drop`, `escalate`) are noted out-of-scope for scoring.
- **Bi-temporal invalidation semantics** specified end-to-end: recall floor, gravity zeroed, `T_purge=90 d` grace window, utility-tally freeze on invalidate (and replay-on-revalidate), log-dampened ε amplification.
- **Tuning-knob table** comprehensive: every weight, threshold, and decay constant with default, range, calibration source (LongMemEval / LoCoMo / DMR + Lethe opt-in trace; **no SCNS sources**), eval signal cross-ref to eval-plan §5/§6, and keep/replace/extend trigger.
- **v2 learned-scorer log-signal contract**: 7 event types (`remember`, `recall`, `recall_outcome`, `promote`, `demote`, `invalidate`, `consolidate_phase`), common JSON envelope, replayability invariant `(log + S1/S2/S3 snapshot at t) → score(t)`, sink contract extending `scripts/eval/metrics/emitter.py` with `emit_score_event(event)` (Q4 — pairs with `lethe_native/loader.py::capture_opt_in_trace`), privacy invariants, two-gate v2 entry criteria (≥20% strict-stratum operator share AND ≥10k labeled `(recall, outcome)` pairs).
- **Worked numerical example** in Appendix A — preference, episodic fact, procedure (with active contradiction) — through both surfaces.

### 11.2 Commits on `main`

- `e0f0705` — `docs(ws5): scoring formalism (v1 heuristic + v2 log-signal contract)`.

### 11.3 Architectural notes

**No new architectural corrections.** The §10 binding constraint (Lethe stands on its own; no SCNS data source, no SCNS substrate) is reaffirmed:

- Calibration sources in §7 are exclusively LongMemEval, LoCoMo, DMR (public benchmark replays) and Lethe's own opt-in audit-log capture (`scripts/eval/lethe_native/loader.py::capture_opt_in_trace`).
- Verifiable: `grep -i scns docs/05-scoring-design.md` returns four hits, each restating the constraint or its verifiable absence — none source calibration data from SCNS.
- The v1.0 strict stratum has no operator share (per §10.5). WS5 accepts the deferral cost: v1.0 tunes against adversarial + ablation + replay-only; v1.1 BO sweep (gap-03 candidate b) and v1.x per-tenant retune both follow once `lethe_native::capture_opt_in_trace` (WS6) ships.

**Forward-spec on `metrics/emitter.py`.** WS5 names `emit_score_event(event)` as a v2 signal-sink extension to the existing batch-report emitter. The function is **not** implemented in WS5 (math doc, not code); its contract surface is specified in `docs/05-scoring-design.md` §8.4 with input schema, validation gates (`contamination_protected`), and on-disk layout (`<run_dir>/score_events/<tenant_id>/<yyyy>/<mm>/<dd>.jsonl`). WS6 owns the implementation alongside the opt-in capture verb.

### 11.4 Reading order for **WS5-QA** (fresh-eyes pass)

The WS5-QA author should approach this cold and answer one question: **does this give a WS6 (API) author and a WS7 (migration) author enough scoring substrate to start without re-research?**

Read in this order:

1. `docs/05-scoring-design.md` start to finish. Pay particular attention to §3 (consolidate-time per-term derivations), §4 (recall-time RRF + post-rerank), §5 (per-class dispatch — verify exhaustiveness over gap-09 §3 four shapes), §6 (bi-temporal invalidation — verify utility-tally freeze and revalidate-replay semantics), §7 (tuning-knob table — verify every row has both a calibration source and an eval signal), §8 (v2 log-signal contract — verify replayability invariant is sufficient for offline `(features, outcome)` derivation).
2. `docs/03-gaps/gap-03-scoring-weights.md` cross-checked against §3, §4, §7 of `05-scoring-design.md`. Are the v1 defaults (`α=0.2, β=0.3, γ=0.2, δ=0.4, ε=0.5`; RRF `k=60`; `w_intent=0.15`; `w_utility` ramp 0→0.2) faithful to gap-03 §5 candidate (a)?
3. `docs/03-gaps/gap-09-non-factual-memory.md` §3 + §7 cross-checked against §5 of `05-scoring-design.md`. Are all four persistent shapes covered with explicit per-class formulas (not "generic + adjust per class")? Are the non-persistent classes noted as out-of-scope?
4. `docs/03-gaps/gap-13-contradiction-resolution.md` §3.1 + §7 cross-checked against §3.5 + §6 of `05-scoring-design.md`. Is the log-dampened ε amplification present? Are revalidate replay semantics specified?
5. `docs/04-eval-plan.md` §5 + §6 cross-checked against the §7 tuning-knob table. Does every knob cite a per-phase signal (§6) and a headline metric (§5)? Are the keep/replace/extend triggers stated?
6. `docs/04-eval-plan.md` §4.6 + §10 + `scripts/eval/metrics/emitter.py` + `scripts/eval/lethe_native/loader.py::capture_opt_in_trace` cross-checked against §8.4 of `05-scoring-design.md`. Is the `emit_score_event` sink contract precise enough (input schema, validation gates, on-disk layout) that a WS6 implementer would not need to re-research the contract?
7. `docs/HANDOFF.md` §10 binding constraint cross-checked against `docs/05-scoring-design.md` §7. Run `grep -i scns docs/05-scoring-design.md` and confirm no calibration source row points at SCNS or any foreign system. Same audit pattern as WS4-QA §10.4.

**Anti-checklist (things that should NOT be present):**
- Any §7 row that names SCNS, `~/.scns/`, or any foreign system as a calibration source.
- A generic per-class formula with "adjust per class" hand-waving — §5 must be exhaustive over the four shapes.
- A v2 log-signal envelope missing `contamination_protected`, `tenant_id`, `model_version`, or `weights_version`.
- A consolidate-time formula that places gravity as a 6th additive term (Q1 chose demotion-floor; an additive form would re-open gap-03's weight tuple).
- A recall-time formula that uses weighted-sum over sem/lex/graph (Q2 chose RRF + post-rerank per gap-03 §5).
- A v1.0 calibration plan that assumes operator-trace data exists (the v1.0 strict stratum operator share is empty; WS5 must be tunable against the adversarial + ablation + replay-only stratum).

A QA failure on any anti-checklist item is P0. A QA failure on a missing cross-ref or under-specified emit-point is P1.

### 11.5 Reading order for **WS6** (API author)

WS6 inherits two binding deliverables from WS5:

- **`emit_score_event(event)`** — a per-event signal sink to be added to `scripts/eval/metrics/emitter.py`, contract in `docs/05-scoring-design.md` §8.4. Pairs with `capture_opt_in_trace`.
- **`capture_opt_in_trace`** — the v1.x operator-trace ingest contract specified in `scripts/eval/lethe_native/loader.py` (line 77) and bound in HANDOFF §10.6 as a WS6 deliverable.

Read in this order:

1. `docs/05-scoring-design.md` §8 (v2 log-signal contract) — your input contract for the emit-point side.
2. `docs/05-scoring-design.md` §4 + §6 — the recall-time scoring path and the bi-temporal validity filter; both surface at the API as request-time concerns (`recall(query)` must apply §4.1 before any retriever is consulted).
3. `docs/03-composition-design.md` §3 — what's stored where; the API surface delineates S1/S2/S3 read paths.
4. `docs/04-eval-plan.md` §4.6 — the opt-in audit-log capture pipeline. WS6 owns the verb implementation; the eval-plan owns the downstream ingest path.
5. `docs/HANDOFF.md` §10 (binding constraint) — no SCNS compatibility shim; no foreign-system data sources.
6. `docs/03-gaps/gap-12-intent-classifier.md` §8 — classifier touch-points at the API surface (intent attaches to a query before recall).
7. `docs/03-gaps/gap-09-non-factual-memory.md` §6 — the per-class always-load semantics for preferences (10 KB cap) interacts with the recall API's response shape.

**Binding constraints from WS5:**
- Every recall-time response must emit a `recall` event per §8.2 envelope (one per top-k candidate). Outcomes flow back via `recall_outcome` events with a `recall_id` join key. Implement the join-key generation deterministically (uuidv7 keyed on `tenant_id + ts_recorded + query_hash`).
- Every consolidate-phase boundary must emit a `consolidate_phase` event. WS5 names six phases (extract / score / promote / demote / consolidate / invalidate); WS6 wires the emit-points around each.
- The bi-temporal validity filter (§4.1) is **applied before** any retriever; do not score-then-filter (cost) and do not skip the filter on "small" stores (correctness).
- The preference always-load path (§5.2) is not a scoring decision at request-time; it is an unconditional include up to 10 KB. Recall-time scoring orders preferences inside the cap; it does not gate inclusion.

### 11.6 Open items / follow-throughs WS5 left for downstream

- **`emit_score_event` implementation (WS6).** Contract is set; implementation pairs with `capture_opt_in_trace`. WS6 also owns the per-tenant audit-log table layout in S2 referenced in §8.4.
- **`procedure` `type_priority` value.** §3.4 table does not list `procedure`; Appendix A treats it as `feedback` tier (0.55) as a residual unknown. v1.1 BO sweep should fit it explicitly. Owner: WS5 v1.1 / scoring-tuning task.
- **Gravity computation cost at scale (§10 residual unknown #2).** `cascade_cost` is `O(|N_2hop|)` per fact per consolidate. May need batched / cached reformulation if S3 grows beyond ~10⁶ edges per tenant. Owner: composition / WS6 implementation.
- **Utility-half-life vs recency-half-life decoupling (§10 residual unknown #4).** Both default `30 d`; v1.1 BO sweep should treat them as independent dimensions.
- **v2 entry-criteria gate.** v2 unblocks at ≥20% strict-stratum operator share **and** ≥10k labeled `(recall, outcome)` pairs (§8.6). Tracking owner: WS8 (deployment / cadence).

WS5 is closed. The next QA pass should ask: **"Does WS5 give a WS6 (API) author and a WS7 (migration) author enough scoring substrate to start without re-doing scoring research?"** §11.4 (WS5-QA reading order) and §11.5 (WS6 reading order) are the explicit answers.

## §12 Post-WS6 update — canonical API surface shipped

### 12.1 What WS6 produced

`docs/06-api-design.md` (1060 lines, single commit). Scope:

- **§0 Frame** — what WS6 owns (verb set, schemas, error taxonomy, idempotency + CAS, recall_id derivation, provenance envelope, emit-points, multi-tenant invariants, opt-in capture verb), what it does NOT own (transport, wire format, auth scheme, RBAC, deployment shape, scoring math, eval cases, retention internals — those are WS5/WS7/WS8). Eight binding constraints from HANDOFF §10 + §11.5 enumerated.
- **§1 Cross-cutting contracts** — tenant/auth surface boundary; idempotency-key contract (24 h TTL, replay→200, conflict→409, mandatory on every write); version-CAS contract (409 + retry hint, idempotency-replay precedence); deterministic `recall_id` derivation (uuidv7 keyed on `tenant_id + ts_recorded + query_hash`, sha256-derived suffix bits for full reproducibility); provenance envelope shape (two-step for peer-message materialization); error taxonomy (200 ok / 200 idempotency_replay / 400 / 401 / 403 forbidden + forget_denied / 404 / 409 version_conflict + idempotency_conflict / 410 purged / 412 precondition_failed / 422 classifier_escalate / 429 / 5xx); emit-point taxonomy summary; multi-tenant invariants (cross-tenant reads → 404, not "empty"; auth missing → 403).
- **§2 Read verbs** — `recall(query, intent?, k?, scope?, budget_tokens?)` with full algorithm (bi-temporal filter pre-RRF; classify; weight-tuple; parallel retrieve; RRF; rerank; truncate; provenance enforcement; ledger write; preferences prepend; emit `recall` × top-k); `recall(k=0)` shape (preferences-only with recall_id, zero recall events); `recall_synthesis(uri | query)` distinct from fact path, emits `recall` with `path=synthesis` marker; `peer_message_pull(recipient_scope, mark_read?, max?)`; `peer_message_status(msg_id)`.
- **§3 Write verbs** — `remember(content, intent?, idempotency_key, provenance, kind?)` with full envelope response (a) including `classified_intent`, `retention_class`, `accepted`, `escalated`, `ack`, `next_consolidate_at`; six `consolidate_phase` emit-points around the post-remember async chain (extract → score → promote → demote → consolidate → invalidate); `promote(fact_id, reason?, idempotency_key, expected_version)` with response `{flag_id, expected_version_consumed, applies_at_next_consolidate, ack="intended_not_applied"}`; `forget(target, mode, reason, idempotency_key, expected_version)` with gap-11 canonical modes (`invalidate|quarantine|purge`) and accepted aliases (`soft→invalidate, deny→quarantine`), purge synchronous with retention-proof-before-delete, quarantine returns estimated `cascade_count`; `peer_message(recipient_scope, type, payload, idempotency_key, ttl?, requires_ack?, in_reply_to?)` synchronous with async pull-based delivery.
- **§4 Operator / admin verbs** — `capture_opt_in_trace(scope, action ∈ {enable, revoke}, idempotency_key)` admin verb (idempotent, per-tenant, revocation triggers retirement of previously-ingested cases); `emit_score_event(event)` documented as **internal sink** in `scripts/eval/metrics/emitter.py` per scoring §8.4 (NOT an external verb, per decision #7); `consolidate(force?, scope?)` admin trigger; `health()` and `audit(query)` operational reads.
- **§5 Emit-point matrix** — authoritative per-verb table; replayability invariant restated.
- **§6 Traceability matrix** — every verb mapped to (composition §, gap §, scoring §); no TBD rows.
- **§7 Verification audits** — three audits transcribed in-doc: (1) SCNS-independence grep audit (mirrors scoring §7); (2) idempotency-key coverage audit (5/5 write verbs PASS); (3) emit-point coverage audit (7/7 event types PASS).
- **§8 Anti-checklist** — explicit denials of transport/wire/auth/RBAC/deployment commitments and SCNS coupling/shim/verb mirroring.

### 12.2 Commits on `main`

- (this commit) — `docs(ws6): canonical API surface (verbs, schemas, error taxonomy, emit-points)`.

### 12.3 Architectural notes

**No new architectural corrections.** The §10 binding constraint (Lethe stands on its own; no SCNS data source, no SCNS substrate, no SCNS shim) is reaffirmed at the API surface:

- The §7.1 grep audit confirms zero verb signatures, zero schema fields, and zero data sources reference SCNS. All 14 `scns`/`SCNS` mentions in `docs/06-api-design.md` are disclaimer or boundary clauses (§0.3 binding constraint #1 restatement, §4.1 `capture_opt_in_trace` boundary clause, §7.1 audit transcript, §8 anti-checklist denial).
- `capture_opt_in_trace` ingests **only Lethe's own trace store**, gated by per-tenant opt-in. SCNS `session_store` is explicitly excluded.
- The verb surface has no SCNS-mirroring shapes; `remember`, `recall`, `forget` shapes follow gap-brief decisions independent of any prior system.

**Forward-spec on `metrics/emitter.py`.** WS5 §8.4 named `emit_score_event(event)` as a v2 signal-sink extension. WS6 commits to it as an **internal sink** (decision #7), not an external verb. The contract surface from scoring §8.2 (envelope), §8.4 (sink contract), §8.5 (privacy invariants) is restated in API §4.2 with the verb→sink wiring made explicit. WS6 owns the implementation alongside the `capture_opt_in_trace` external verb.

**Decisions locked in WS6** (each documented in API design, traceable in plan-mode dialogue):

1. `forget` mode vocabulary — gap-11 canonical (`invalidate|quarantine|purge`); HANDOFF §8.3 wording (`soft|deny`) accepted as aliases (§3.3 alias table).
2. `remember()` returns the **full envelope** (`episode_id, idempotency_key, classified_intent, retention_class, accepted, escalated, ack, next_consolidate_at`) — synchronous classifier per gap-12 §6, async extraction.
3. `peer_message_*` are **synchronous request/response verbs** with **asynchronous pull-based delivery** per gap-10 §3.4–§3.5.
4. `recall(k=0)` is legal: preferences-only response with `recall_id`, zero `recall` events emitted.
5. `recall_synthesis` emits standard `recall` events with `path=synthesis` marker; `fact_ids` set to S4a page-ids (uuidv7-hashed stable URIs).
6. `capture_opt_in_trace` is admin-class, idempotent, per-tenant, revocable; revocation queues retirement of previously-ingested cases per eval-plan §4.6 step 1.
7. `emit_score_event` is **internal sink**, not external verb; documented in §4.2 for unambiguous verb→sink wiring.
8. `forget(quarantine)` response includes estimated `cascade_count`; final value visible via `audit()` after async cascade.
9. `promote` and `forget` synchronous bodies return `{flag_id, expected_version_consumed, applies_at_next_consolidate, ack="intended_not_applied"}` — explicit "intended-not-applied" ack so callers don't assume immediate visibility.

### 12.4 Reading order for **WS6-QA** (fresh-eyes pass)

The WS6-QA author should approach this cold and answer one question: **does this give a WS7 (migration) author enough verb-surface substrate to plan an in-place SCNS-data → Lethe-store migration without re-researching API contracts?**

Read in this order:

1. `docs/06-api-design.md` start to finish. Pay particular attention to §1 (cross-cutting contracts — verify idempotency-key, version-CAS, recall_id derivation, provenance envelope, error taxonomy are all internally consistent and consistent with gap-04/gap-05/gap-08), §2.1 + §2.1.1 (verify bi-temporal filter is **pre-retriever** and that `k=0` shape is sound), §3.1 (verify the six `consolidate_phase` emit-points are named in the right order: extract → score → promote → demote → consolidate → invalidate), §3.3 (verify gap-11 canonical mode vocabulary is the wire-side primary, with `soft|deny` accepted as aliases), §4.2 (verify `emit_score_event` is an internal sink, not an external verb), §5 (verify emit-point matrix is consistent with §3.1 and scoring §8.1), §6 (verify traceability has no TBD rows), §7 (verify the three audits all pass — re-run the grep audit fresh).
2. `docs/05-scoring-design.md` §8 cross-checked against `docs/06-api-design.md` §1.4 (recall_id derivation), §1.7 (event taxonomy summary), §3.1 (six `consolidate_phase` phases), §4.2 (`emit_score_event` sink). Are the §8.1 event types each emitted by ≥1 verb? Is the `recall_id` derivation sufficient for the §8.3 replay invariant?
3. `docs/03-composition-design.md` §3 + §4 + §5 + §7 cross-checked against §2 + §3 of `docs/06-api-design.md`. Are the read paths in §3 reflected in `recall` / `recall_synthesis` / `peer_message_pull`? Are the write paths in §4 reflected in `remember` / `promote` / `forget` / `peer_message`? Are the consistency-model rows in §5 reflected in the error taxonomy (T1/T2 ACID → 5xx on store outage)? Are the failure-modes in §7 reflected in `health()` degraded-mode signaling?
4. `docs/03-gaps/gap-04-multi-agent-concurrency.md` §4 cross-checked against §1.3 (version-CAS) and the per-verb `expected_version` parameter on `promote` / `forget` / `peer_message` (when targeting a specific msg). Is the 409 retry semantics consistent?
5. `docs/03-gaps/gap-08-crash-safety.md` §3 cross-checked against §1.2 (idempotency-key contract). Is the 24 h TTL consistent? Is the §3.6 retention-proof-before-delete ordering consistent with `forget(purge)` synchronous semantics in §3.3?
6. `docs/03-gaps/gap-10-peer-messaging.md` §3 cross-checked against §2.3 + §2.4 + §3.4. Are the four message types (`query|info|claim|handoff`) all on the wire? Is the inbox cap (100 unread, oldest non-`query` dropped) surfaced via `cap_dropped_since_last_pull`? Is the sensitive-class send-time scan (gap-10 §6 / gap-11 §3.3) implemented via `422 classifier_escalate`?
7. `docs/03-gaps/gap-11-forgetting-as-safety.md` §3 cross-checked against §3.3 of `docs/06-api-design.md`. Are all three modes implemented? Is the alias mapping (`soft→invalidate, deny→quarantine`) explicit? Is purge admin-only-by-default and rate-limited? Does the retention proof land in S5 *before* the delete commits?
8. `docs/03-gaps/gap-12-intent-classifier.md` §3 + §6 cross-checked against §3.1 (remember classifier branches). Are all 7 classes accounted for in the branching (`drop`, `reply_only`, `peer_route`, `escalate`, plus the three persistent `remember:*` paths)? Is caller-tagged intent honored unless classifier objects ≥0.8?
9. `docs/03-gaps/gap-09-non-factual-memory.md` §6 cross-checked against §2.1 (preferences prepend). Is the 10 KB cap unconditional? Is `preferences_truncated` exposed? Are preferences a separate field from `facts[]` in the response (so callers cannot conflate)?
10. `docs/03-gaps/gap-05-provenance-enforcement.md` §3 cross-checked against §1.5 (provenance envelope) and the per-fact `provenance` field in `recall` response. Is `episode_id` non-null on every returned fact? Is `derived_from` set for peer-materialized facts? Is `provenance_dropped` surfaced in `applied_filters`?
11. `docs/04-eval-plan.md` §4.6 cross-checked against §4.1 (`capture_opt_in_trace`). Are all seven pipeline steps (opt-in capture / signal selection / sensitivity classification / scrub / review / signal-loss check / audit log) reachable from this verb's contract? Is revocation-triggered retirement honored?
12. `docs/HANDOFF.md` §10 + §11.5 binding constraints cross-checked against §0.3 of `docs/06-api-design.md`. Run `grep -in scns docs/06-api-design.md` and confirm every hit is a disclaimer or boundary clause. Same audit pattern as WS4-QA §10.4 and WS5-QA §11.4.

**Anti-checklist (things that should NOT be present):**

- Any verb whose request schema names SCNS, `~/.scns/`, `session_store`, or any foreign-system data source.
- Any verb whose response schema mirrors a SCNS verb's response shape for compatibility.
- A `remember` path that bypasses the gap-12 classifier or accepts caller-tagged intent without the ≥0.8 classifier-audit gate.
- A `recall` path that runs any retriever **before** the §4.1 bi-temporal filter, or that conditionally skips the filter on small stores.
- A preferences-prepend implementation that gates inclusion on score (the cap is ordering, not gating).
- A write verb without a mandatory `idempotency_key`.
- A mutating verb without an `expected_version` parameter (other than `remember`, which creates new rather than mutating).
- A `forget(purge)` path that deletes content before writing the retention proof to S5 (gap-08 §3.6 ordering).
- A `recall_id` derivation that uses a non-deterministic CSPRNG suffix (would break the §8.3 replay invariant).
- An external `emit_score_event` verb (it must be an internal sink per decision #7).
- A transport/RPC commitment, wire-format commitment, auth-scheme commitment, RBAC role table, or deployment-shape commitment (those are WS8).

A QA failure on any anti-checklist item is a P0; a QA failure on a missing or weak cross-ref is a P1.

### 12.5 Reading order for **WS7** (migration author)

WS7 inherits from WS6 the canonical verb surface as the **migration target**. WS7 plans how SCNS data lands in Lethe stores by *calling these verbs*, not by introducing a SCNS-shaped shim into the verb surface.

Read in this order:

1. `docs/06-api-design.md` §0.2 + §0.3 — what WS6 does NOT own (auth, transport, deployment) and the binding constraints (no SCNS shim; `capture_opt_in_trace` is the only opt-in verb).
2. `docs/06-api-design.md` §3.1 (`remember`) — every migrated SCNS observation lands as a `remember` call. Idempotency-key + provenance are mandatory; SCNS migration must mint stable idempotency keys (e.g., `uuidv7(tenant_id, scns_observation_id)`) so partial migration runs are restartable.
3. `docs/06-api-design.md` §3.3 (`forget`) — SCNS archive-store entries map to `forget(invalidate)` per gap-11 §8 / WS7 mapping; SCNS has no analog of quarantine or purge, so those modes are not exercised by migration.
4. `docs/06-api-design.md` §1.4 (`recall_id` derivation) + §1.5 (provenance envelope) — episode-id stability is a migration invariant (gap-05 §6); migration must preserve SCNS observation-ids as `provenance.source_uri` so audits can trace pre-migration evidence.
5. `docs/03-composition-design.md` §5 (consistency model) + §7 (failure modes) — what an in-place migration must preserve (T1/T2 ACID windows; degraded-mode handling).
6. `docs/03-gaps/gap-08-crash-safety.md` §3.5 — `lethe-audit lint --integrity` is a phase-gate in WS7.
7. `docs/03-gaps/gap-09-non-factual-memory.md` §7 — SCNS `~/.claude/CLAUDE.md` → preference S4a pages; SCNS synthesis pages → narrative S4a pages.
8. `docs/HANDOFF.md` §10 — Lethe stands on its own; migration is a one-way ingest, not an ongoing dependency.

**Binding constraints from WS6:**

- Migration does not introduce SCNS-shaped verbs into the API surface. SCNS data lands by calling the existing verbs.
- Migration does not bypass `capture_opt_in_trace`; per-tenant opt-in is the only path for trace data into the eval candidate pool.
- Migration mints stable, deterministic `idempotency_key`s so partial runs are restartable per §1.2.
- Migration preserves SCNS observation-ids as `provenance.source_uri` so audit trails survive the cutover (gap-05 §6 episode-id stability invariant; the source-uri carries the SCNS-side identifier even though the episode-id is freshly minted).

### 12.6 Open items / follow-throughs WS6 left for downstream

- **`emit_score_event` implementation in `scripts/eval/metrics/emitter.py`.** Contract is set in API §4.2 (mirroring scoring §8.4). Implementation pairs with `capture_opt_in_trace` (the external verb that gates which tenant traces flow into the sink). Owner: WS6 implementation pass (this is a docs-only commit; the code lands in a follow-up).
- **`capture_opt_in_trace` external verb implementation.** Contract surface is set in API §4.1; the loader-side function is in `scripts/eval/lethe_native/loader.py::capture_opt_in_trace` (already stubbed by WS4). Owner: WS6 implementation pass.
- **Per-tenant rate-limit values.** API §1.6 + §2.1.2 + §3.4 name *where* limits attach but not the values. Owner: WS8.
- **Capability-to-role mapping.** API §8 names capabilities (`forget_purge`, `audit_global`, `tenant_admin`) abstractly. Owner: WS8.
- **Wire-format and transport choice.** API schemas are abstract type-annotated. Owner: WS8.
- **`recall_synthesis` event split decision.** API §2.2 emits standard `recall` events with `path=synthesis` marker; v2 trainer can split or unify by its own preference (WS5 §8 is silent on this). Owner: v2 scorer / WS5 v1.1 if revisited.
- **`escalate`-class human-review pipeline.** API §3.1 returns 422 with `staged_for_review` ack but does not specify the review workflow (who reviews, on what cadence, how the staged episode lands as durable on accept). Owner: WS8 / project ops.

WS6 is closed. The next QA pass should ask: **"Does WS6 give a WS7 (migration) author and a WS8 (deployment) author enough API-surface substrate to start without re-doing API-contract research?"** §12.4 (WS6-QA reading order) and §12.5 (WS7 reading order) are the explicit answers.

---

## §13 Post-WS6 framing correction — markdown audience

Single-commit docs correction to `docs/03-composition-design.md`. Earlier drafts framed markdown as "for humans only" in four places (§3.1 L77, §5 consistency table S4b row, §7 failure-mode table S4b-diverged row, §8.3 Candidate C ingest tradeoff). This was wrong on principle and internally inconsistent with the design itself, which has `recall_synthesis` (§3.2) returning S4a markdown to LLM agents.

**Corrected principle:** markdown is a **dual-audience** surface. LLMs parse markdown natively — that is *why* markdown is the right substrate for synthesis pages. The real design constraints are:

1. **Canonicality.** S1 is source of truth; the API does not read S4b back because doing so would either duplicate S1 (bloat) or surface stale views (correctness).
2. **Context bloat.** `recall_synthesis` is the gated entry-point limiting agent exposure to relevant S4a pages.
3. **Authored vs derived.** S4a authored / S4b derived. The dividing line is *who wrote it*, not *who reads it*.

**Edits landed:**
- New §1.1 sidebar ("Markdown audience and the real constraint") making the dual-audience principle explicit.
- §3.1 L77, §5 S4b row, §7 S4b-diverged row, §8.3 ingest tradeoff — all rewritten in canonicality + bloat terms.
- §2.1 already partitioned S4a/S4b by *authored vs derived* (not by audience); no edits needed there.
- Charter quote at §8.2 ("markdown remains the human-readable surface for trackpad and synthesized knowledge pages") left intact — "human-readable surface" is a *property*, not an *exclusion*; the bad framing was the inferred "*only*", not the charter text itself.

**Cascade:** WS4 / WS5 / WS6 docs already audited clean for the bad framing — zero hits. No downstream edits required.

**For WS7-QA (fresh-eyes context):** when you read §3.1 / §5 / §7 / §8.3 of the composition design, the language is now consistent with `recall_synthesis` returning markdown to agents. If you find any residual "for humans only" framing in WS7 artifacts, flag it — it would be a regression of this correction.

---

## §14 Post-WS7 update — migration plan shipped

### 14.1 What WS7 produced

`docs/07-migration-design.md` (single commit). Scope:

- **§0 Frame** — what WS7 owns (source inventory, mapping rules, phase plan, phase-gates, concurrency contract, failure-recovery, verification, stopping criteria), what it does NOT own (migration-tool source code, transport/wire/auth/RBAC/deployment, verb internals — those are WS8 / WS6 / gap-01). Eight binding constraints from HANDOFF §10 + §11.5 + §12.5 enumerated, plus the §0.4 vocabulary cross-walk that absorbs the kickoff prompt's "three-tier" shorthand into composition's canonical S1–S5.
- **§1 Source inventory** — read-only audit of `~/.scns/memory/` + `~/.claude/CLAUDE.md`. Top-level shapes table partitions every path glob into in-scope / out-of-scope: in (CLAUDE.md, lessons, negative, sessions, daily, weekly, monthly, archive, .legacy-lessons); out (MEMORY.md/SOUL.md/USER.md as S4b-shape, regenerated post-cutover; vault.db as out-of-scope per api §0.3 #1; SCNS runtime/ops surfaces as not-memory-corpus). Volume sketch and frontmatter conventions.
- **§2 Mapping rules** — 9-row table mapping every in-scope source shape to a verb call: CLAUDE.md → preference (per-section split); lessons → prohibition / procedure / narrative depending on §3.4 heuristic + frontmatter; negative → prohibition; sessions → episode (state_fact); daily → episode (reference) per timestamped block; weekly/monthly → narrative; archive / .legacy-lessons → `forget(invalidate)` after a corresponding `remember`; `criticStatus=suppress` → `remember` then immediate `forget(invalidate)` to preserve audit trail. Authored-vs-derived rule (composition §2.1 + §8.3 Candidate C) and identifier rules — idempotency-key and episode-id derivations are uuidv7-shaped and parallel to api §1.4: 48-bit ts prefix + fixed 4-bit version + 12-bit deterministic rand_a tail + fixed 2-bit variant + 62-bit deterministic rand_b, with discriminant strings (`"idem"`, `"epi"`) separating the two derivations over the same source bytes.
- **§3 Phase plan** — 14 ordered phases with three hard phase-gates: A (pre-flight integrity-lint per gap-08 §3.5), B (episode-id round-trip per gap-05 §6), C (post-import provenance + integrity lint per gap-05 §3.5 + gap-08 §3.5). Per-phase: inputs, output, idempotency mechanism, exit gate, S5 entry. Resumability mechanism (manifest as source of truth; per-row idempotency keys; `audit(provenance.source_uri=...)` lookup as TTL-fallback). Section-split rule for CLAUDE.md (one preference page per `##` heading). Procedure-vs-narrative classification heuristic (3-test conjunction; favors narrative on ambiguity). Explicit list of verbs migration does NOT call (`promote`, `peer_message`, `capture_opt_in_trace`, `emit_score_event`).
- **§4 Concurrency contract** — cold-start case (recommended); warm-tenant case via api §1.3 `expected_version` CAS (gap-04 §3 candidate (a)); recall-determinism preservation (api §1.4 derivation depends only on request inputs, so migration-time writes do not perturb in-flight recall_ids); tenant-scope invariant (api §1.8); per-phase locking via `health()` polling, not direct lock acquisition.
- **§5 Failure modes & recovery** — per-phase table mapped to composition §7 rows. Escalation handling (`422 classifier_escalate` is a first-class outcome, manifest row marked `escalated`, not a halt). Explicit list of what is NOT a migration failure (heuristic outcome correctable post-cutover, archive orphan logged not halted, suppress-then-invalidate by design).
- **§6 Verification** — phase-gate outputs in S5; provenance round-trip on a 5% sample (source_uri lookup, episode-id match, content_hash match); recall-determinism probe (~50 queries, drift tolerance, fact-id-set diff); preference-cap honoring (`recall(k=0)` slice ≤10 KB, recency-ordered, `preferences_truncated` flag); anti-checklist verification; **§6.6 four audit transcripts in-doc**: SCNS-independence (80 hits all in allowed categories — corpus refs / `scns:<shape>:<id>` literals / boundary disclaimers / audit transcript / HANDOFF citations); idempotency-key coverage (9/9 mapping-row write paths PASS); phase-gate coverage (14/14 phases gated, 3/3 hard gates present); markdown-audience audit (zero "for humans only" framing).
- **§7 Stopping criteria** — for one tenant (S5 phase-gate entries; provenance round-trip; recall-determinism within tolerance; preference-cap honored; operator-signed `migration_run_complete`) and for WS7 deliverable (doc + HANDOFF §14 + audits in-doc + §10 residuals).
- **§8 Anti-checklist** — explicit denials of migration-tool source-code spec, `migrate_*` verb, SCNS shim, vault.db consumption, MEMORY.md copying, capture_opt_in_trace bypass, transport/wire/auth/RBAC/deployment commitments, cross-deployment Lethe→Lethe spec, synchronous fact-extraction of authored synthesis, dream-daemon throughput guarantee.
- **§9 Traceability matrix** — every WS7 decision mapped to its composition / scoring / api / gap-NN / HANDOFF source.
- **§10 Residual unknowns** — daily-block source-id collision under multi-snapshot migration (mitigation: include snapshot_hash in source-id formula if collisions observed); §3.4 heuristic accuracy floor (swap to LLM classifier if precision drops below 80%); Phase 9 async-drain volume thresholds; sensitive-content escalation review workflow at scale (HANDOFF §12.6 inheritance); cross-deployment Lethe→Lethe migration deferred; vault.db consumption deferred; operator-tooling UX punted; idempotency-key TTL extension instrumented; Phase 11 S3 backfill duration.

### 14.2 Commits on `main`

- `11e6366` — `docs(ws7): migration design (in-place SCNS corpus → Lethe stores)`.
- (this commit) — `docs(handoff): WS7 post-update — migration plan shipped`.

### 14.3 Architectural notes

**No new architectural corrections.** The §10 binding constraint (Lethe stands on its own) and the §11.5 / §12.5 derivative bindings (no SCNS shim in the runtime; migration is a one-way ingest that calls api verbs and stops) are reaffirmed at the migration surface:

- The §6.6.1 audit confirms **zero verb signatures, zero schema fields, zero post-cutover read paths** reference SCNS. All 80 `scns`/`SCNS` mentions in `docs/07-migration-design.md` fall into five allowed categories: source-corpus references (the migration target is, by definition, SCNS); `provenance.source_uri = scns:<shape>:<id>` literals (audit-trail format, internal to Lethe's own provenance store after import); HANDOFF §10 / api §0.3 #1 boundary citations; the §8 anti-checklist denial; the §6.6.1 audit itself.
- After cutover (§3.1 phase 13), the runtime has no SCNS dependency. The migration tool stops; Lethe operates on its own substrate.
- No `migrate_*` verb is introduced into the api surface. Migration calls only the existing api §2–§4 verbs.

**Forward-spec on the migration tool itself.** This doc is verb-call-shaped; the implementation (CLI, manifest format, snapshot mechanism, S3 backfill orchestration, phase-gate runners) is a follow-up pass. WS7 commits to the **plan**, not the **tool**.

**Identifier-derivation parallelism.** The §2.3 idempotency-key and episode-id derivations are uuidv7-shaped, RFC 9562-conformant, and visually parallel to api §1.4 — same 48 + 4 + 12 + 2 + 62 bit layout; same sha256-derived deterministic-suffix pattern. Discriminant strings (`"idem"` for the idempotency-key, `"epi"` for the episode-id; `recall_id` in api §1.4 has no discriminant because its inputs already differ) prevent collision-by-construction over the same source bytes.

**Decisions locked in WS7** (each documented in `docs/07-migration-design.md`, traceable in plan-mode dialogue):

1. Five-store vocabulary (composition §2 S1–S5) used throughout; the kickoff prompt's "three-tier" shorthand is absorbed into the §0.4 vocabulary cross-walk.
2. Corpus-only migration; `vault.db` is out-of-scope for v1 (would require SCNS schema dependency or a side-channel translator that is effectively a shim).
3. SCNS S4b-shape projections (`MEMORY.md` / `SOUL.md` / `USER.md`) are **not** copied; Lethe regenerates S4b post-cutover from S1.
4. CLAUDE.md splits per top-level `##` heading into separate preference pages; the 10 KB always-load cap (gap-09 §6) is enforced at recall as an *ordering* constraint, not at migration as a *gating* constraint.
5. Authored synthesis migrates with `lethe.extract: false` (composition §8.3 Candidate C); operator opts in per-page if desired post-cutover.
6. Idempotency-key = `uuidv7(tenant_id, scns_observation_id)` with discriminant `"idem"`, RFC 9562 layout per §2.3 — independent of `ts_recorded` so cross-day resumes still replay.
7. Episode-id = `uuidv7(tenant_id, ts_recorded_scns, scns_observation_id)` with discriminant `"epi"`, RFC 9562 layout per §2.3 — `ts_recorded_scns` is the SCNS-side observation timestamp (not migration host wall-clock), making episode-id deterministic across resumes (gap-05 §6).
8. Cold-start migration is the recommended v1 path; warm-tenant migration is supported with api §1.3 `expected_version` CAS retry (gap-04 §3 candidate (a)).
9. `criticStatus=suppress` rows migrate as `remember` then immediate `forget(invalidate)` to preserve the audit trail (gap-05 §3.4); they are not silently dropped.
10. Phase 11 (S3 backfill) is non-blocking on the api surface (composition §3.1 lexical fallback survives S3 outage); operator chooses wait or defer.

### 14.4 Reading order for **WS7-QA** (fresh-eyes pass)

The WS7-QA author should approach this cold and answer one question: **does this give an operator (or migration-tool implementer) enough substrate to plan and execute an in-place SCNS-corpus → Lethe-tenant migration without re-researching upstream contracts, and does every binding invariant from upstream WS survive intact?**

Read in this order:

1. `docs/07-migration-design.md` start to finish. Pay particular attention to §0.3 (eight binding constraints — verify each cites an upstream §-ref correctly), §0.4 (five-store vocabulary cross-walk — verify it does not contradict composition §2), §2.1 (mapping table — verify every SCNS source shape from §1.1 has an in-scope or out-of-scope row), §2.3 (identifier rules — verify the uuidv7 layout matches api §1.4 and that the idempotency-key/episode-id discriminants prevent collision), §3.1 (14-phase plan — verify the three hard phase-gates are present and gated correctly), §6.6 (four audit transcripts — re-run each fresh).
2. **`docs/03-composition-design.md` §1.1** — the **dual-audience markdown principle**. Per HANDOFF §13 (cascade record), this is canonical and any "for humans only" framing in WS7 artifacts would be a regression. Verify §6.6.4 of `docs/07-migration-design.md` audits cleanly and that §3.3 (CLAUDE.md split), §2.1 (S4a synthesis pages), and §6.4 (preference-cap verification) all use dual-audience language.
3. `docs/03-composition-design.md` §2 + §5 + §6 + §7 cross-checked against §0.4 + §3 + §4 + §5 of `docs/07-migration-design.md`. Are the five-store vocabulary uses faithful (no S4b-shape copy; S4a authored vs S4b derived split honored)? Are the T1/T2 ACID windows preserved by the phase plan (Phase 6 = T1 boundary; Phase 8 = T2 boundary)? Is the §6 provenance propagation chain (caller → episode → fact-edge → recall) preserved by the §2.3 `provenance.source_uri` and `episode_id` rules? Are the §7 failure-mode rows mapped onto the §5 per-phase recovery table?
4. `docs/03-gaps/gap-08-crash-safety.md` §3.5 cross-checked against §3.1 phases 4 and 10 of `docs/07-migration-design.md`. Is `lethe-audit lint --integrity` invoked as a hard gate at both pre-flight (Phase-gate A) and post-import (Phase-gate C)? Are the §6.6.3 phase-gate audit transcript's hard-gate counts (3/3) correct?
5. `docs/03-gaps/gap-05-provenance-enforcement.md` §3 + §6 cross-checked against §2.3 + §3.1 phase 7 of `docs/07-migration-design.md`. Is episode-id stability enforced by Phase-gate B's sample round-trip? Does every imported episode carry a non-null `episode_id` and a `provenance.source_uri` of the `scns:<shape>:<id>` form? Are the post-import lints (`provenance-required`, `provenance-resolvable`, `forget-proof-resolves`) all run at Phase-gate C?
6. `docs/03-gaps/gap-09-non-factual-memory.md` §3 + §6 + §7 cross-checked against §2.1 + §3.3 + §3.4 of `docs/07-migration-design.md`. Are the four persistent shapes (preference, prohibition, procedure, narrative) all present in the mapping table? Is the SCNS `~/.claude/CLAUDE.md` → preference and SCNS synthesis pages → narrative pages mapping (gap-09 §7) faithful? Is the 10 KB always-load cap (gap-09 §6) honored as an ordering constraint at recall, not a gating constraint at migration?
7. `docs/03-gaps/gap-04-multi-agent-concurrency.md` §3 + §4 + §6 cross-checked against §4 of `docs/07-migration-design.md`. Is the warm-tenant CAS-retry path (candidate (a)) faithful? Is the cold-start case (candidate (b)) named as the recommended v1 path? Is the per-tenant lock interaction (via `health()` polling, not direct acquisition) consistent with composition §4.4?
8. `docs/03-gaps/gap-11-forgetting-as-safety.md` §3 cross-checked against §2.1 + §3.1 phase 8 of `docs/07-migration-design.md`. Are archive entries mapped to `forget(invalidate)` (not `quarantine` or `purge`)? Is the `criticStatus=suppress` → `remember` then `forget(invalidate)` design (preserving audit trail) consistent with gap-05 §3.4?
9. `docs/06-api-design.md` §1.2 + §1.3 + §1.4 + §1.5 + §3.1 + §3.3 + §4.1 cross-checked against §0.3 + §2.3 + §3.1 + §3.5 of `docs/07-migration-design.md`. Is every migration write a valid `remember` / `forget` call (all required fields present)? Is the idempotency-key TTL (24 h) handled correctly with the `audit(provenance.source_uri=...)` fallback for >24 h runs? Does the migration explicitly NOT call `capture_opt_in_trace` (per HANDOFF §12.5 binding)?
10. `docs/04-eval-plan.md` §4.6 cross-checked against §3.5 + §8 of `docs/07-migration-design.md`. Is `capture_opt_in_trace` correctly excluded from the migration path? If the operator wants to opt the destination tenant into eval-trace ingest, is that documented as a separate, post-cutover api §4.1 call?
11. `docs/HANDOFF.md` §10 + §11.5 + §12.5 binding constraints cross-checked against §0.3 + §6.6.1 of `docs/07-migration-design.md`. Run `grep -in scns docs/07-migration-design.md` and confirm every hit falls into the five allowed categories (source-corpus reference / `scns:<shape>:<id>` literal / boundary citation / anti-checklist denial / audit transcript itself). Same audit pattern as WS4-QA §10.4, WS5-QA §11.4, WS6-QA §12.4.

**Anti-checklist (things that should NOT be present):**

- Any verb signature in `docs/07-migration-design.md` that names `migrate_*` or extends the api surface.
- Any post-cutover read path from the runtime to `~/.scns/` or `vault.db`.
- A migration row that writes without `idempotency_key` or without `provenance.source_uri`.
- An idempotency-key or episode-id derivation that uses a non-deterministic CSPRNG suffix (would break Phase-gate B).
- An idempotency-key derivation that omits the discriminant separator (`"idem"`) and would collide with the episode-id derivation over the same source bytes.
- A phase that lacks both an exit gate and a justified "no gate" notation.
- A pre-flight Phase-gate A or post-import Phase-gate C that is not a *hard* halt.
- An "S4b copy from SCNS" path (regeneration must be from S1 post-cutover, per composition §2 row S4b).
- A migration call to `capture_opt_in_trace` (per HANDOFF §12.5; eval-trace ingest is post-cutover, separate, opt-in).
- A migration call to `promote`, `peer_message`, or `emit_score_event` (none are appropriate to the migration path).
- Any "for humans only" framing for markdown surfaces (HANDOFF §13 cascade; composition §1.1 binding).
- A transport / wire / auth / RBAC / deployment-shape commitment (those are WS8).

A QA failure on any anti-checklist item is a P0; a QA failure on a missing or weak cross-ref is a P1.

### 14.5 Reading order for **WS8** (deployment author)

WS8 inherits the operator-knob surface and the deployment-shape decisions WS7 deferred. Read in this order:

1. `docs/07-migration-design.md` §3 — the 14-phase plan names every operator action point (snapshot creation, capability checks, manifest inspection, phase-gate halts, drift-tolerance configuration, cutover trigger, S4b regeneration wait). WS8 builds the operator UX around these.
2. `docs/07-migration-design.md` §4 — the cold-start vs. warm-tenant decision is operator-configured per migration; WS8 owns whether `single_writer_per_tenant=true` (gap-04 §4 stop-gap) is the default for migrations.
3. `docs/07-migration-design.md` §10 — residual unknowns name several instrumentation hooks WS8 should expose: idempotency-key TTL extension instrumentation; Phase 9 async-drain operator alarm (`time-since-last-successful-consolidation > N × gate_interval`); Phase 11 S3 backfill progress via `health()`; manifest UX (CLI / JSON / HTML).
4. `docs/03-composition-design.md` §7 — degraded modes are deploy-cadence aware. WS8 sets the actual gate intervals and lock heartbeats.
5. `docs/03-gaps/gap-01-retention-engine.md` §3.2 — dream-daemon scheduler config (gate interval, lock heartbeat); migration's Phase 9 async-drain timing depends on these values.
6. `docs/03-gaps/gap-08-crash-safety.md` §3.4 + §3.5 — startup integrity check + lock recovery; WS8 owns the operator-facing `lethe-audit lint --integrity` invocation surface that migration's Phase-gates A and C call.
7. `docs/03-gaps/gap-14-eval-set-bias.md` §5(3) — drift detector + monthly re-eval cadence; migration's §6.3 recall-determinism probe is a one-shot version of the same idea.
8. `docs/06-api-design.md` §0.2 + §1.6 — the rate-limit numerical caps, capability-to-role mapping, and wire-format choice are all WS6-deferred and WS8-owned; migration's §3.1 Phase 1 capability check depends on the WS8 capability mapping.
9. `docs/HANDOFF.md` §12.6 — the `escalate`-class human-review pipeline is HANDOFF §12.6 deferred; migration's §5.1 marks rows `escalated` but the review workflow is WS8 / project-ops territory.

### 14.6 Open items / follow-throughs WS7 left for downstream

- **Migration-tool implementation.** The doc is verb-call-shaped; CLI, manifest format, snapshot mechanism, S3 backfill orchestration, phase-gate runners, and operator UX are an implementation pass. Owner: operator-tooling pass (post-WS8).
- **Daily-block source-id collision under multi-snapshot migration** (§10). If observed, augment source-id formula with `@<snapshot_hash[:8]>`. Owner: operator-tooling pass (instrumented at first multi-snapshot run).
- **§3.4 procedure-vs-narrative heuristic accuracy floor** (§10). Swap to LLM classifier if precision drops below 80% on a labeled sample. Owner: operator-tooling pass (instrumented post-cutover via `forget` + `remember` re-import frequency).
- **Phase 9 async-drain operator alarm threshold** (§10). Bounded by dream-daemon gate cadence × episode count; WS8 sets the alarm threshold value.
- **Cross-deployment Lethe→Lethe migration spec** (§10). Same shape as SCNS→Lethe with `provenance.source_uri = lethe:<src_tenant>:<episode_id>`; deferred to v1.x. Owner: future migration spec.
- **`vault.db` consumption** (§10). Out of scope for v1; if a future operator policy requires SCNS broker metadata in Lethe, the path is a one-time exporter that emits SCNS-corpus-shaped markdown for migration to consume — keeping the §0.3 #1 boundary intact. Owner: future migration spec or v1.x if demanded.
- **Idempotency-key TTL extension** (§10). api §1.2 sets 24 h; gap-08 §5 names it as a guess. For very large corpora exceeding 24 h to drain, §3.2 falls back to `audit(provenance.source_uri=...)` lookup; instrument the fallback rate. Owner: WS8 (operational metric) + WS6 implementation (TTL config).
- **Phase 11 S3 backfill duration & progress** (§10). Volume-sensitive; non-blocking but operator-visible. WS8 may want to expose progress via `health()`. Owner: WS8.
- **Sensitive-content escalation review workflow** (§5.1; HANDOFF §12.6 inheritance). Migration marks rows `escalated`; the post-migration review workflow is WS8 / project ops. Owner: WS8.
- **Manifest UX surface** (§10). CLI / JSON / HTML; punted to operator-tooling pass. Owner: operator-tooling pass.

WS7 is closed. The next QA pass should ask: **"Does WS7 give an operator (and migration-tool implementer) enough substrate to plan and execute an in-place SCNS-corpus → Lethe-tenant migration without re-doing migration research, and does every binding invariant from upstream WS survive intact?"** §14.4 (WS7-QA reading order) and §14.5 (WS8 reading order) are the explicit answers.

---

## §15 Post-WS8 update — deployment design shipped

### 15.1 What WS8 produced

`docs/08-deployment-design.md` (single commit, 793 lines). Scope:

- **§0 Frame** — what WS8 owns (RBAC + capability map; rate-limit numerical caps; wire-format choice; operator knobs; `health()` extensions; alarm thresholds; escalate-review pipeline; migration runtime contract; backup posture; v2 entry-criteria gate; single-tenant-per-deployment posture), what it does NOT own (verb semantics, migration phase order, scoring math, eval-set composition, retention engine internals, migration-tool implementation bytes, auth-mechanism implementation, cross-deployment Lethe→Lethe, multi-tenant runtime). Six binding constraints enumerated. §0.4 operator-vocabulary index (19 terms defined for non-engineer reader on first use).
- **§1 Deployment topology** — single-tenant-per-deployment v1 baseline (composition §1.1 + §5.2); recommended single-host physical layout per store (S1–S5 colocation table); `single_writer_per_tenant=true` migration default (gap-04 §4 stop-gap); v2 multi-tenant gate forward-ref to §10.
- **§2 RBAC + auth + wire-format** — three roles (`agent` / `tenant_admin` / `operator`); capability-to-verb matrix (every api verb mapped to required capability); principal-extraction contract; **decision: JSON over HTTP/1.1 with optional MCP framing** (rationale table; protobuf/gRPC rejected for v1).
- **§3 Rate-limit + quota table** — 11 rows; numerical caps for every api hook (`recall` 30/s; `remember` 10/s; `forget(invalidate|quarantine)` 5/s; `forget(purge)` 10/h-100/d per tenant; `peer_message` 20/s; `consolidate(force)` 6/h; `capture_opt_in_trace` 10/h; escalate-staging cap 50/d; `audit()` 10/s; `health()` unbounded). Rationale per row.
- **§4 Operator knobs** — gate interval (15 min default w/ range table; gap-01 §3.2 Q3); lock heartbeat (30 s / 60 s break; gap-01 §3.2 Q3 + gap-08 §3.4 lifted to defaults); idempotency-key TTL (24 h default; **7-day enforced ceiling** — config validator rejects values >7d at startup; above-ceiling guidance: chunk by snapshot); preference-cap (10 KB recency-of-revision); drift cadence (continuous 5%/hour sample, monthly re-eval, quarterly fresh-adversarial-slice); recall-determinism drift tolerance (5% default); escalate cap reaffirmed; mid-migration async-drain alarm (1.5× gate, stricter than steady-state 2×).
- **§5 Health + observability** — additive `health()` extensions (migration progress, idempotency-key TTL fallback rate, escalation queue depth, drift state, v2-gate state) — non-breaking on api §4.4; `audit()` operator query patterns; 18 must-emit metrics signals; **8 must-wire alarms** (`consolidation_stalled`, `escalation_queue_depth`, `idempotency_fallback_high`, `s3_backfill_stalled`, `drift_high`, `degraded_mode_active`, `forget_purge_rate_spike`, `tenant_isolation_breach` P0).
- **§6 Escalate-review pipeline** — review-queue substrate in S2; review actions (`approve` / `reject` / `expire-now`); **`force_skip_classifier=true` parameter** introduced as a v1 api §3.1 surface extension (auth-gated to `tenant_admin`; WS6 implementation pass adds it to api §3.1); 24-hour review SLA, 30-day queue TTL; migration `escalated`-row drain workflow (post-cutover; introduces `escalated_rejected` terminal status).
- **§7 Migration runtime contract** — `lethe-migrate` CLI subcommand surface (12 subcommands mapping 1:1 to migration §3.1 phases / phase-gates); manifest UX (`manifest.jsonl` shape, HTML status surface, JSON dump); capability-check ordering for Phase 1; snapshot UX methods (`git-tag` / `fs-copy` / `zfs-snapshot`); rollback scope (pre-cutover only; post-cutover deferred to cross-deployment migration spec).
- **§8 Backup / restore + crash recovery** — per-store backup posture table (SQLite online-backup on quiesce; native procedures for Graphiti backing DB; git for S4a; cross-deployment restore deferred); `lethe-audit lint --integrity` operator invocation surface; `lethe-admin lock` recovery commands; disk-full thresholds (1 GB / 100 MB) with `5xx store_unavailable` hint.
- **§9 Degraded modes operator playbook** — full cross-walk to composition §7 + §7.1; for every degraded mode (15 rows including the two-stores-down combinations), operator-action column, and silent-by-design column.
- **§10 v1 → v2 entry-criteria gate** — scoring §8.6 two conditions (strict-stratum operator share ≥20%; ≥10 000 labeled `(recall, outcome)` pairs) lifted to `health().v2_gate` gauges; **3-month soak rule** for cutover (composition §1.1 single-tenant baseline is irreversible-shaped); v2 readiness checklist (7 items).
- **§11 Verification audits** — five audit transcripts in-doc: (a) operator-readability (all 19 §0.4 terms defined); (b) citation coverage (every numeric default has §-ref or named v1 bet); (c) anti-checklist (§12 self-check); (d) **SCNS-independence** (11 hits, all in allowed categories — HANDOFF citations, migration/dream-daemon cross-refs as design-pattern reference, anti-checklist denial, audit transcript itself); (e) **markdown-audience** (2 hits, both meta-references forbidding the framing; zero hits as actual assertions).
- **§12 Anti-checklist** — 12 explicit denials (no transport-layer implementation, no migration-tool source code, no scoring weight values, no eval-set composition, no SCNS runtime path, no cross-deployment Lethe→Lethe, no `vault.db` consumption, no auth-mechanism implementation, no multi-tenant runtime, no v2 design, no schema-migration policy, no Lethe distribution artifact).
- **§13 Traceability matrix** — every WS8 decision mapped to its composition / scoring / api / migration / gap / HANDOFF source.
- **§14 Residual unknowns** — metrics-pipeline implementation; review-surface HTML implementation; `lethe-migrate` / `lethe-admin` CLI implementations; `force_skip_classifier=true` formal addition to api §3.1 (WS6 implementation pass); cross-deployment restore (v1.x); 2PC for cross-host T1 (v2); v2 multi-tenant runtime design; wire-format re-evaluation at v2 fleet scale; backup quiesce automation; disk thresholds at fleet scale; "3 consecutive months" reset semantics under partial-month outages; RBAC management API.

### 15.2 Commits on `main`

- `e20736a` — `docs(ws8): deployment design (operator knobs, RBAC, rate-limits, observability, escalate-review pipeline)`.
- (this commit) — `docs(handoff): WS8 post-update — deployment design shipped`.

### 15.3 Architectural notes

**No new architectural corrections.** The §0.3 binding constraints (single-tenant-per-deployment v1 baseline; no SCNS runtime dependency; cross-tenant reads forbidden; markdown dual-audience; numeric defaults cite or are named-as-bet; operator-facing terms defined inline) are reaffirmations of upstream commitments at the deployment surface:

- The §11.4 SCNS-independence audit confirms **zero verb signatures, zero schema fields, zero runtime read paths** reference SCNS. All 11 SCNS mentions fall into allowed categories: HANDOFF §10 citations; the §12 anti-checklist denial; design-pattern cross-references where the upstream doc itself cites SCNS (gap-01 dream-daemon evaluation; migration-corpus naming); the audit transcript itself.
- The §11.5 markdown-audience audit confirms **zero framing assertions** of "for humans only"; both grep hits are meta-references forbidding the framing.

**Decisions locked in WS8** (each documented in `docs/08-deployment-design.md`, traceable in plan-mode dialogue):

1. **Three RBAC roles** — `agent` (no capabilities; verb-level access only), `tenant_admin` (`tenant_admin` + `forget_purge`), `operator` (all three including `audit_global`). `forget_purge` lives on `tenant_admin` not `operator` because hard-delete is data-sovereignty, not ops-fleet.
2. **JSON over HTTP/1.1 + optional MCP framing.** Protobuf / gRPC rejected for v1 on tooling cost; revisitable at v2 fleet scale.
3. **Rate-limit caps per verb table** (§3) — every cap cites its api §-ref attach point.
4. **Gate interval 15 min default; lock heartbeat 30 s / 60 s break.** gap-01 §3.2 Q3 + gap-08 §3.4 lifted to defaults.
5. **Idempotency-key TTL: 24 h default; 7-day hard ceiling enforced** at runtime startup (config validator rejects >7d). Above-ceiling escape: chunk by snapshot. The 7-day ceiling is the WS8 commitment that closes HANDOFF §14.6's TTL-extension residual.
6. **Mid-migration async-drain alarm at 1.5× gate** (steady-state stays 2×). Closes the HANDOFF §14.6 Phase-9 drain-alarm-threshold residual.
7. **`health()` extensions are additive only** to api §4.4 — no breaking change to the published api surface.
8. **8 must-wire alarms with explicit thresholds** — `tenant_isolation_breach` is **P0** (composition §5.2 invariant violation; should be impossible by construction).
9. **`force_skip_classifier=true` parameter on `remember`** — WS8 introduces the contract; gated to `tenant_admin`; auditable in S5; WS6 implementation pass adds it to api §3.1.
10. **Migration `escalated`-row drain is post-cutover.** Phase-gate C lints applied rows; staged rows have no S1 episodes to lint. Introduces `escalated_rejected` as a new terminal manifest status.
11. **`lethe-migrate` CLI subcommand surface** — 12 subcommands; the bytes are operator-tooling pass; this doc names the contract.
12. **Manifest format: `manifest.jsonl`** — one row per line, append-only with status-update rewrite via atomic-rename.
13. **Backup posture: SQLite online-backup API for S2/S5 on quiesce; native procedures for Graphiti backing DB.** Cross-deployment restore deferred to v1.x.
14. **v2 cutover decision rule: both scoring §8.6 gates GREEN for 3 consecutive months.** Composition §1.1 single-tenant-per-deployment is irreversible-shaped; soak prevents flap.

### 15.4 Reading order for **WS8-QA** (fresh-eyes pass)

The WS8-QA author should approach this cold and answer one question: **does this give an operator enough substrate to deploy, monitor, and operate a single-tenant Lethe deployment without re-researching upstream contracts, and does every binding invariant from upstream WS survive intact at the operator surface?**

Read in this order:

1. `docs/08-deployment-design.md` start to finish. Pay particular attention to §0.3 (six binding constraints — verify each cites an upstream §-ref correctly), §0.4 (operator-vocabulary index — verify each term is defined inline OR via §0.4 cross-link on first body occurrence), §2 (RBAC roles + capability map — verify every api capability from api §0.2 + §3.3 + §4.1 + §4.4 is covered), §3 (rate-limit table — verify every "rate-limit" attach point in api §1.6 + §2.1.2 + §3.3 + §3.4 + §4.3 has a row), §4.3 (idempotency-key TTL ceiling — verify the rejection rule is enforced, not advisory), §5.2 (`health()` extensions — verify additive, non-breaking on api §4.4), §11 (five audit transcripts — re-run each fresh).
2. **`docs/03-composition-design.md` §1.1** — the **dual-audience markdown principle**. Per HANDOFF §13 (cascade record), this is canonical and any "for humans only" framing in WS8 artifacts would be a regression. Verify §11.5 audits cleanly and that §6.2 (review-surface HTML), §7.2 (manifest HTML), §9 (degraded-mode playbook prose) all use dual-audience language.
3. `docs/06-api-design.md` §0.2 + §1.6 + §2.1.2 + §3.3 + §3.4 + §4.1 + §4.3 + §4.4 + §8 cross-checked against §2 + §3 + §5 of `docs/08-deployment-design.md`. Are all WS6-deferred items (rate-limit numerical caps, capability-to-role mapping, wire-format choice) committed by WS8? Are the `health()` additions strictly additive (no field renamed, no field removed, no semantic change to existing fields)? Is the `force_skip_classifier=true` extension flagged as a WS6 implementation-pass follow-through?
4. `docs/07-migration-design.md` §3 + §4 + §5.1 + §10 cross-checked against §6 + §7 + §4.8 of `docs/08-deployment-design.md`. Is the migration §3.1 phase plan covered 1:1 by `lethe-migrate` subcommands (§7.1)? Is the migration §5.1 escalation-handling row resolved by §6's review pipeline? Is migration §10's residual list (Phase 9 drain alarm, idempotency TTL extension instrumentation, Phase 11 backfill progress, sensitive-content review workflow, manifest UX) all closed or explicitly forwarded?
5. `docs/03-composition-design.md` §7 + §7.1 cross-checked against §9 of `docs/08-deployment-design.md`. Does the §9 playbook cover every composition §7 row in operator-action terms? Are the two-stores-down §7.1 cases all named?
6. `docs/03-gaps/gap-01-retention-engine.md` §3.2 cross-checked against §4.1 + §4.2 of `docs/08-deployment-design.md`. Are the gate-interval and lock-heartbeat defaults faithful to the gap-01 commitments (per-tenant lock + 30 s heartbeat)? Is the 15-min gate-interval default named as a v1 bet (not as a derivation)?
7. `docs/03-gaps/gap-08-crash-safety.md` §3.4 + §3.5 + §3.6 cross-checked against §4.2 + §8.2 + §8.3 + §8.4 of `docs/08-deployment-design.md`. Is `lethe-audit lint --integrity` named as the operator surface for both startup integrity (gap-08 §3.5) and migration phase-gates A + C? Is the lock-recovery surface (§8.3) consistent with gap-08 §3.4? Are disk thresholds (§8.4) consistent with gap-08 §3.6 retention-proof-before-delete ordering?
8. `docs/03-gaps/gap-14-eval-set-bias.md` §5(3) cross-checked against §4.5 + §5.5 (`drift_high` alarm) of `docs/08-deployment-design.md`. Is the continuous-drift cadence (5%/hour sample) faithful? Is monthly re-eval scheduled? Is the 10% drift threshold explicit?
9. `docs/05-scoring-design.md` §8.6 cross-checked against §10 of `docs/08-deployment-design.md`. Are the two gates exposed verbatim via `health().v2_gate`? Is the 3-month soak rule clearly an addition (not a contradiction) to scoring §8.6's two gates?
10. `docs/HANDOFF.md` §12.6 + §14.6 binding constraints cross-checked against §13 (traceability matrix) of `docs/08-deployment-design.md`. Run `grep -in scns docs/08-deployment-design.md` and confirm every hit falls into the allowed categories listed in §11.4 of that doc. Same audit pattern as WS4-QA §10.4, WS5-QA §11.4, WS6-QA §12.4, WS7-QA §14.4.

**Anti-checklist (things that should NOT be present):**

- Any verb signature in `docs/08-deployment-design.md` that adds to the api surface, except `force_skip_classifier=true` on `remember` (which IS a documented WS8 extension; flagged for WS6 implementation pass).
- Any change to api §4.4 `health()` schema that removes or renames a field (additions only).
- Any rate-limit cap that lacks an api §-ref attach point.
- Any operator knob default that lacks a citation OR an explicit "v1 bet" naming.
- Any operator-vocabulary term used in the body without a §0.4 entry or inline definition.
- Any "for humans only" framing for markdown surfaces (HANDOFF §13 cascade; composition §1.1 binding) — except as a meta-reference forbidding the framing in §0.3 / §11.5.
- Any commitment to a specific auth provider (OAuth, JWT, mTLS) — §2.3 specifies the contract, not the mechanism.
- Any cross-deployment Lethe→Lethe restore path in v1 (deferred per §8.1 + gap-08 §5).
- Any `vault.db` consumption (out of scope per migration §1.1 + §8).
- A v2 multi-tenant cutover triggerable by configuration (§10 requires runtime upgrade + 3-month soak).
- A `forget(purge)` cap that is per-principal rather than per-tenant (§3 specifies per-tenant; multiple admins must not aggregate to bypass).

A QA failure on any anti-checklist item is a P0; a QA failure on a missing or weak cross-ref is a P1.

### 15.5 Open items / follow-throughs WS8 left for downstream

- **Metrics-pipeline implementation.** §5.4 names the must-emit signals; the actual exporter (Prometheus, OTLP, log-scraper, etc.) is deployment-specific. Owner: operator-tooling pass / per-deployment.
- **Review-surface HTML implementation** (§6.2). Static-rendered shape specified; renderer is operator-tooling pass.
- **`lethe-migrate` CLI implementation** (§7). Contract specified; bytes are operator-tooling pass.
- **`lethe-admin` CLI for lock recovery** (§8.3). Same as above.
- **`force_skip_classifier=true` formal addition to api §3.1.** Owner: WS6 implementation pass. Single-line addition to api §3.1 inputs with `tenant_admin` auth check; until then, `docs/08-deployment-design.md` §6.3 is the contract reference.
- **Cross-deployment Lethe→Lethe restore** (§8.1). Deferred to v1.x; same shape as the cross-deployment migration spec WS7 §10 deferred.
- **2PC for cross-host T1.** Deferred to v2 (gap-08 §5).
- **v2 multi-tenant runtime design.** §10 names the gate; the v2 design itself is a future workstream (gap-04 v2 multi-writer concurrency; RBAC fleet role; cross-tenant routing).
- **Backup quiesce automation.** §8.1 names the windows; orchestration (consolidate-lock acquire → backup → release) is operator-tooling pass.
- **"3 consecutive months" reset semantics under partial-month outages.** §10 specifies the rule; exact reset behavior under intra-month flap is operator-tunable but undefined here. v1.x refinement.
- **RBAC management API.** §2.1 has roles edited via S2 config + restart; a v1.x administrative API verb is a future surface.

WS8 is closed. The next QA pass should ask: **"Does WS8 give an operator enough substrate to deploy, monitor, and operate a single-tenant v1 Lethe deployment without re-doing deployment research, and does every binding invariant from upstream WS survive intact at the operator surface?"** §15.4 (WS8-QA reading order) is the explicit answer.
