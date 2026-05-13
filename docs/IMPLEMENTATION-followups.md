# IMPLEMENTATION — Followups / Errata

This file is the additive errata surface for `docs/IMPLEMENTATION.md` (binding
revision: `git show 698488b:docs/IMPLEMENTATION.md`; deleted from working tree
by `93eb8ad docs(cleanup): remove planning-phase ephemera` per HANDOFF §17).

The IMPL doc rev `698488b` remains the binding source of truth for the v1
phase plan (P1–P10 surface, exit gates, file lists, traceability matrix,
risk register, cutover gate). Errata below clarify or correct specific lines
without re-opening the planning closure.

Pattern precedent: `e7afbc2 docs(impl-followups): apply non-gating doc-hygiene
from GO-NO-GO §6.3` (which made non-IMPL doc-hygiene edits under the same
`docs(impl-followups):` umbrella; the IMPL.md edit it would have applied was
collapsed into N/A by the §17 cleanup).

---

## Erratum E1 — Embedding-pipeline phase reassignment (P3 → P4)

**Lines affected**

- IMPL §2.1 P1 OOS list: *"All verbs (P2+); embedding generation pipeline (P3); consolidation scheduler (P4); review queue actions (P7)."*
- IMPL §2.3 P3 file-list and exit-gate sections (silent on the embedder).
- IMPL §2.4 P4 file-list (silent on the embedder; implicit in `runtime/consolidate/extract.py`).

**Correction**

The write-side embedding pipeline (composition §4.1 line 6 — *"embed new
nodes/edges into S3"*) is hereby **reassigned from P3 to P4**, where it lives
inside (or alongside) `src/lethe/runtime/consolidate/extract.py` as part of
the dream-daemon async chain.

P1 OOS list line should be read as if it said:

> All verbs (P2+); embedding generation pipeline **(P4)**; consolidation
> scheduler (P4); review queue actions (P7).

P3's `recall` exit gates remain as written in IMPL §2.3 — including the DMR
sanity-replay smoke test — which is satisfied by **pre-seeded S3 fixtures**
(e.g. `tests/fixtures/dmr_corpus/{episodes.jsonl, embeddings.json}`) shipped
as part of the P3 commit set. The DMR adapter therefore exercises the full
recall algorithm (bi-temporal filter → parallel S1+S2+S3 retrieve → RRF →
post-rerank → ledger write → `recall` event emission) over a corpus whose
embeddings were computed offline at fixture-generation time.

**Rationale**

1. **Architectural alignment with composition §4.1.** The §4.1 design
   commits to a "fast synchronous + async consolidation" split. Lines 1–3
   are the synchronous ACID T1 (validate provenance, write episode to S1,
   write episode-arrival event to S2 ledger). Lines 4–8 — including line 6
   "embed new nodes/edges into S3" — are explicitly the async portion,
   "*dream-daemon or eager-extract worker*". Putting the embedder on the
   synchronous P3 path would invert this commitment and add model-bound
   latency to the hot write path, contradicting the synthesis §1.3
   "fast synchronous" property the design rests on.

2. **Test fidelity is preserved.** DMR is a known-task replay benchmark
   over a fixed corpus; embeddings can be pre-computed at fixture build
   time and committed to the test tree. The recall algorithm — which is
   what P3 actually owns — is exercised end-to-end against real vectors.
   The adapter-level decision (skip-marker vs wired-executable) remains
   the P3 facilitator's to lock.

3. **Scope discipline at P3.** P3 already lands a substantial surface
   (RRF combiner, three retrievers, bi-temporal filter, per-class scoring
   formulas, preferences-prepend, deterministic `recall_id`, two read
   verbs, ledger write, `recall` event). Adding an embedder seam — model
   choice, dep-injection plumbing, fake-vs-real fixture split, latency
   budget reconciliation against gap-09 — is real risk for a dev-UX gain
   (live `remember(); recall()` smoke in dev sandboxes), not a correctness
   gap.

4. **Cross-references already align with the reassignment.**
   - IMPL §2.2 P2 OOS list: "`recall` (P3); promote / forget (P5)" — no
     mention of embedder, consistent with embedder-not-at-P2.
   - IMPL §2.3 P3 file list: includes `runtime/retrievers/{semantic,…}` (the
     consumer of S3 vectors) but no producer/embedder seam.
   - IMPL §2.4 P4 file list: includes `runtime/consolidate/extract.py`
     ("extraction from new episodes (calls extraction-confidence log in
     S2)") — the natural call-site for the embedder, since extraction and
     embedding share the per-episode lifecycle and the dream-daemon's
     per-tenant lock.

5. **Reversibility.** If P4's facilitator/dev session finds a need to
   sketch a synchronous embed-on-remember bridge earlier (e.g. for a P-N
   phase-specific reason), nothing in this erratum forbids it. The
   erratum only commits to *not* requiring the embedder at P3.

**Cross-refs.** composition §4.1 (sync/async split); IMPL §2.1 (P1 OOS),
§2.3 (P3 file list + exit gates), §2.4 (P4 file list); gap-09 §write-budget
(if/when it gets re-examined under a sync-bridge alternative); QA-P2 §G.3
(events bus already extensible for the recall events P3 emits).

**Discovered.** 2026-05-12 facilitator bearings session
(`~/.copilot/session-state/7ac32d73-4366-42c0-bcb8-7afd378ffc51/files/BEARINGS.md`).
