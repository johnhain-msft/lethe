# 06 — API Design (WS6)

**Status:** v1 design, awaiting WS6-QA fresh-eyes pass.
**Substrate:** composition §3 (ownership matrix), §4 (read/write paths), §5 (consistency model), §7 (failure-mode table); scoring §4 (recall-time formula), §6 (bi-temporal invalidation), §8 (v2 log-signal contract); gap-04 (version-CAS), gap-05 (provenance), gap-08 (idempotency), gap-09 (preference always-load), gap-10 (peer messaging), gap-11 (forget modes), gap-12 (intent classifier); eval-plan §4.6 (opt-in audit-log capture); HANDOFF §8.3 + §10 + §11.5 (binding constraints).
**Cross-refs:** Gates WS6-QA (this is the input contract); gates WS7 (migration sees the verb surface as the import target — not a SCNS shim); WS8 owns transport, wire format, auth scheme, RBAC, deployment shape — none of those are decided here.

This document specifies **the verbs Lethe exposes, their request/response shapes, error semantics, idempotency + CAS contracts, provenance envelopes, and the emit-points each verb fires.** It does *not* specify scoring math (WS5), eval cases (WS4), retention engine internals (gap-01), or the substrate's transport/wire/auth layer (WS8).

The headline question every WS6 artifact answers: **given a verb name and a stated intent, what does a caller send, what does Lethe return, what events does the call leak into the v2 training-signal pipeline, and what can fail?**

---

## §0 Frame

### §0.1 What WS6 owns

- The **verb set** — `recall`, `recall_synthesis`, `remember`, `promote`, `forget`, `peer_message`, `peer_message_pull`, `peer_message_status`, `capture_opt_in_trace`, `consolidate`, `health`, `audit`.
- The **request and response schemas** for each verb (field names, types, optionality, default semantics).
- The **error taxonomy** — status codes, retry semantics, and the verb-side handling of CAS conflicts, idempotency replays, and `forget(purge)` denials.
- The **idempotency-key contract** on every write verb (gap-08 §3.1).
- The **version-CAS contract** on every mutating verb (gap-04 §4).
- The **`recall_id` derivation rule** (deterministic uuidv7; HANDOFF §11.5 binding).
- The **provenance envelope shape** in recall responses (gap-05 §3).
- The **emit-point hooks** — which §8.x events fire, in what order, on each verb.
- The **multi-tenant invariants** at the verb surface (composition §5.2).
- The **opt-in audit-log capture verb** that powers v1.x operator-trace ingest (eval-plan §4.6; HANDOFF §11.5).

### §0.2 What WS6 does NOT own

Listed up-front so the rest of the doc can stay verb-focused without continuously disclaiming. Cross-ref §8 (anti-checklist) for the closing restatement.

- **Transport / RPC choice** — REST, gRPC, MCP, JSON-RPC, in-process. WS8.
- **Wire format** — JSON, protobuf, msgpack. WS8.
- **Auth scheme** — OAuth, JWT, mTLS, API keys. WS8.
- **RBAC roles** — admin / agent / operator role definitions. WS8.
- **Rate-limit numbers** — per-tenant QPS caps. WS8 (this doc names *where* limits attach but does not set values).
- **Deployment shape** — single-binary, sidecar, hosted service, embedded library. WS8.
- **Scoring math** — WS5 (`docs/05-scoring-design.md`).
- **Eval-set composition** — WS4 (`docs/04-eval-plan.md`).
- **Retention engine internals** — gap-01.

### §0.3 Binding constraints (HANDOFF §10 + §11.5)

These are non-negotiable. Every verb spec below is verifiable against them.

1. **No SCNS compatibility shim.** No verb reads from `~/.scns/`, no verb imports from the SCNS repo, no verb-side data source is SCNS. SCNS is a design-pattern reference only (WS1 audit, gap-01) — not a substrate, not a dependency, not a data source. The §7 grep audit confirms this in-doc.
2. **Bi-temporal validity filter is applied BEFORE any retriever** on the recall path. Score-then-filter is rejected (cost). Skip-filter-on-small-stores is rejected (correctness). See §2.1 and scoring §4.1.
3. **Preference always-load is unconditional up to 10 KB.** Recall-time scoring orders preferences inside the cap; it does not gate inclusion. This doc adopts **recency-of-revision** as the in-cap ordering (gap-09 §6 does not pin an ordering; §2.1 step 10 is the implementation site).
4. **Every write verb carries an `idempotency_key`.** Replays inside the 24 h TTL window return the original response with status 200; they do not re-execute the write. See §1.2 and gap-08 §3.1.
5. **Every mutating verb carries `expected_version`.** Conflicts return 409 with the current version and a retry hint. See §1.3 and gap-04 §4.
6. **`recall_id` is deterministic** — uuidv7 keyed on `tenant_id + ts_recorded + query_hash`. This is the join key for `recall ↔ recall_outcome` and the replay invariant for emit-point reproducibility. See §1.4 and scoring §8.3.
7. **Six `consolidate_phase` emit-points fire around `remember()`** (extract / score / promote / demote / consolidate / invalidate). See §3.1 and §5.
8. **Cross-tenant reads are forbidden** at every read verb. See §1.8 and composition §5.2.

### §0.4 Notation

Schemas are written as type-annotated field lists. `?` suffix = optional. `[]` = list. `|` = union. `RFC3339` = ISO-8601-with-timezone timestamp string. `uuidv7` = uuid v7 string. `bytes` = base64-encoded blob in transport but a logical byte-string. Types are abstract; the wire-format mapping is WS8's call.

---

## §1 Cross-cutting contracts

Single source of truth for the contracts that every verb references. Each verb section below cites these by §-number and does not restate them.

### §1.1 Tenant scope and auth surface

Every verb takes an implicit `tenant_id` and an implicit `principal` (caller identity). Both are presumed extracted from the transport layer (WS8) and surfaced to the verb body before request validation. A verb spec written as `recall(query, ...)` is shorthand for `recall(tenant_id, principal, query, ...)`.

The tenant scope is the privacy boundary (composition §5.2; scoring §8.5). Every read filters by `tenant_id`; every write stamps `tenant_id`. **Cross-tenant reads return 403, not "empty."** Empty would silently mask a misrouted call. See §1.8.

The principal is named on every emit-point and every audit-log entry; it is the auth-side identity stamped onto provenance (`provenance.agent_id`; gap-05 §3) and onto the §8.2 envelope's implicit caller field. The actual auth scheme (OAuth, JWT, mTLS) is WS8.

### §1.2 Idempotency-key contract

Every **write verb** carries `idempotency_key: uuidv7` (caller-supplied). Contract per gap-08 §3.1:

- The key is recorded in S2 alongside the resulting episode-id / flag-id / message-id.
- A retry of the same verb with the same `idempotency_key` within the **24 h TTL window** returns the original response unchanged with HTTP-equivalent status **200** (replay), not re-executing the write.
- A retry **after** the 24 h window with a key that has rolled out of S2 retention is treated as a fresh call; callers should regenerate keys past 24 h.
- A retry within the window with the same key but a *different* request body returns **409 idempotency_conflict** with the original body's hash and the retried body's hash; the second body is not written.
- Keys are scoped per `(tenant_id, verb)`. A `remember` key and a `forget` key with the same uuid value do not collide.

The key is **mandatory**; missing-key requests return 400 `missing_idempotency_key`. This is stricter than gap-08 names but follows from "every write verb carries an idempotency_key" being a binding constraint (§0.3 #4).

### §1.3 Version-CAS contract

Every **mutating verb** that targets a pre-existing fact-edge or flag carries `expected_version: int` (caller-supplied; obtained from a prior `recall` response). Contract per gap-04 §4:

- The verb compares `expected_version` to the current version of the target.
- On match: increment version, apply the mutation, return new version in the response.
- On mismatch: return **409 version_conflict** with the current version and a retry hint (`retry_after_ms` advisory; WS8 picks the value).
- Idempotency-replay (§1.2) takes precedence over CAS: a replay returns the original response, including the original new-version, even if the live version has moved on.

`remember` is **not** a mutating verb against a pre-existing target — it creates a new episode — so it does not carry `expected_version`. It does carry `idempotency_key` (§1.2). Net contract: `remember` is idempotent-but-not-CAS; `promote`, `forget`, `peer_message` (when targeting a specific msg) are both.

### §1.4 `recall_id` derivation

`recall_id = uuidv7(tenant_id, ts_recorded, query_hash)`

where `query_hash = sha256(canonical_json({query, intent, k, scope}))[:16]` and `ts_recorded` is the request-arrival timestamp at millisecond resolution.

The derivation is **deterministic on its three inputs**. This means:

- A replay of the same query at the same instant produces the same `recall_id` (rare in practice but trivially consistent).
- Two queries from different tenants with otherwise-identical content produce different `recall_id`s (the tenant_id input separates them).
- The §8.4 emit-pipeline can **reproduce** `recall_id` from logged inputs without round-tripping to the live runtime — this is the replay invariant scoring §8.3 commits to.
- `recall_outcome` events join back to `recall` events via this id (scoring §8.4).

Implementation note: the uuidv7 timestamp prefix is the 48-bit `ts_recorded` in milliseconds per RFC 9562. The version (4 bits, `0111`) and variant (2 bits, `10`) fields are fixed by RFC 9562. The remaining 74 bits (`rand_a` ‖ `rand_b`) are filled deterministically from the leading 74 bits of `sha256(tenant_id ‖ query_hash)` rather than from a CSPRNG, so the value is fully reproducible and RFC-conformant. WS8 owns the byte-packing details but cannot alter this derivation.

### §1.5 Provenance envelope

Every fact returned by `recall` carries a provenance object (gap-05 §3):

```
provenance: {
  episode_id:    uuidv7,
  source_uri:    string,             // caller-supplied at remember-time
  agent_id:      string,             // principal of the original remember
  recorded_at:   RFC3339,
  derived_from?: string,             // present iff this fact derives from a peer_message
  edit_history_id?: uuidv7           // S5 entry id if this fact has been touched by promote/forget
}
```

Two-step provenance (peer-message materialization, gap-10 §3.3): when a `claim`-typed peer-message is materialized into recipient memory, the new fact's `provenance.episode_id` points at the recipient's *new* episode (source = `self_observation`); `provenance.derived_from` points at the peer-message episode. The peer's identity is reachable but not laundered.

Provenance is **mandatory on every recall response**. A fact-edge with null provenance fails the §3.5 step-5 enforcement (composition §3.1) and is dropped from the response with a `provenance_drop_count` counter incremented in S2 telemetry. Recall does not return un-justified facts.

### §1.6 Error taxonomy

Status codes are HTTP-equivalent semantics; the actual transport is WS8.

| Code | Symbol | When | Retry? |
|---|---|---|---|
| 200 | `ok` | Success. | n/a |
| 200 | `idempotency_replay` | Same `idempotency_key` within TTL; original response returned. | n/a (already succeeded) |
| 400 | `missing_idempotency_key` | Write verb without `idempotency_key`. | After fix; not retried verbatim. |
| 400 | `invalid_request` | Schema violation, unknown enum value, etc. | After fix. |
| 400 | `provenance_required` | `remember` without `provenance.source_uri`. | After fix. |
| 401 | `unauthenticated` | Auth missing/invalid. | After auth refresh (WS8). |
| 403 | `forbidden` | Cross-tenant read attempted; `forget(purge)` from non-admin principal; quarantine cascade exceeds tenant cap. | No (auth-class). |
| 403 | `forget_denied` | `forget(purge)` denied by retention policy or rate-limit. | Out-of-band escalation. |
| 404 | `not_found` | Target id (fact, episode, msg) does not exist or is in another tenant. | No. |
| 409 | `version_conflict` | CAS mismatch (§1.3). | Yes — re-fetch current version; re-attempt. Includes `retry_after_ms` hint. |
| 409 | `idempotency_conflict` | Same key, different body, within TTL (§1.2). | After regenerating key with the intended body. |
| 410 | `purged` | Target was purged (gap-11 §3.3); only the retention proof in S5 remains. | No. |
| 412 | `precondition_failed` | Quarantine cascade exceeds per-cycle budget; caller must split. | After narrowing target. |
| 422 | `classifier_escalate` | `remember` classified `escalate` (gap-12); human review required before write commits. | After review (out-of-band). |
| 429 | `rate_limited` | Per-tenant QPS cap (WS8 sets value). | Yes after `retry_after_ms`. |
| 5xx | `store_unavailable` | S1, S2, or S3 down per composition §7. Includes degraded-mode hint in body (which stores are up). | Yes; also exposed via `health()`. |

The `forget(purge)` deny path is **explicit** (`403 forget_denied`) per gap-11 §3.3 — purge is admin-only-by-default and rate-limited; the verb must surface the deny without silently downgrading to `invalidate`.

### §1.7 Emit-point taxonomy summary

Cross-link to scoring §8.1; this is a verb-side index.

| Event | Emitted by which verb(s) | Cardinality per call |
|---|---|---|
| `remember` | `remember` | 1 (synchronous) + 0..N from async extract |
| `recall` | `recall`, `recall_synthesis` | 1 per top-k candidate |
| `recall_outcome` | None directly — emitted by *downstream* verbs (`forget` referencing a recalled fact, citation telemetry) | 1 per outcome observed |
| `promote` | `promote`, async dream-daemon promote phase | 1 per promote |
| `demote` | async dream-daemon demote phase | 1 per demote |
| `invalidate` | `forget(invalidate)`, `forget(quarantine)` cascade, async contradiction handling | 1 per invalidate |
| `consolidate_phase` | `remember` (the six surrounding phases per §3.1), `consolidate` (admin trigger) | 6 per remember + 6 per consolidate cycle |

§5 is the per-verb authoritative emit-point matrix.

### §1.8 Multi-tenant invariants

- Every read verb filters on `tenant_id`. A read targeting an id from a different tenant returns **404** (`not_found`), not 403 — the existence of the cross-tenant id must not leak. *Exception:* if the principal lacks any tenant scope at all, return **403** (`forbidden`); that's auth, not isolation.
- Every write verb stamps `tenant_id` from the principal's scope; callers cannot impersonate another tenant by passing a different `tenant_id` in the body.
- `peer_message` accepts `recipient_scope` *within the same tenant* only. Cross-tenant peer messaging returns **403** (`forbidden`) per gap-10 §3.1.
- `capture_opt_in_trace` is **per-tenant** and revocable by the tenant (or by a delegated admin); revocation triggers retirement of previously-ingested cases on next snapshot per eval-plan §4.6.
- Audit / lint reads (`audit()`, `health()`) may aggregate across tenants for *operational* metrics (counts, error rates), but **never** return tenant-identifying content (no tenant_id, no fact_id, no episode_id) in cross-tenant aggregates.

---

## §2 Read verbs

### §2.1 `recall(query, intent?, k?, scope?)`

The hot-path fact retrieval verb. Composition §3.1; scoring §4.

**Signature**

```
recall(
  query:   string,
  intent?: string,           // gap-12 class label; if absent, classifier-derived
  k?:      int = 10,
  scope?:  ScopeFilter,      // optional fact-class / kind / source filter
  budget_tokens?: int        // §5.3 eval-plan; advisory cap
) -> RecallResponse
```

**Request schema**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `query` | string | yes | — | Natural-language query text. |
| `intent` | enum | no | classifier-derived | One of the gap-12 §3 persistent classes (`update_preference`, `state_fact`, `procedure_lookup`, `narrative_recall`); if absent, the classifier (gap-12 §6) runs synchronously. |
| `k` | int | no | 10 | `k=0` is legal; see §2.1.1. Max 100 (WS8 sets ceiling). |
| `scope` | object | no | unfiltered | Optional `{kind?: enum, source?: string, valid_at?: RFC3339}` — `valid_at` lets callers run as-of queries against the bi-temporal stamps; default is `now`. |
| `budget_tokens` | int | no | unset | Advisory; recall response tries to fit but is not gated on it. |

**Response schema (`RecallResponse`)**

```
{
  recall_id:               uuidv7,            // deterministic; §1.4
  facts: [                                    // top-k after rerank; may be empty
    {
      fact_id:             uuidv7,
      version:             int,               // for CAS on subsequent promote/forget
      kind:                enum,              // gap-09 §3 shape; one of {user_fact, project_fact, feedback, reference, preference, prohibition, procedure, narrative}
      content:             string,            // canonical text rendering of the fact-edge
      score:               float,             // post-rerank composed score; scoring §4.5
      score_inputs:        ScoreInputs,       // type, recency, connectedness, utility, contradiction, gravity (scoring §3.x)
      valid_from:          RFC3339,
      valid_to:            RFC3339 | null,    // null = currently valid
      provenance:          ProvenanceEnvelope // §1.5
    }
  ],
  preferences: [                              // always-load; §3.5 composition; gap-09 §6
    {
      page_uri:            string,            // S4a stable uri
      content:             string,            // page body, capped per-page
      kind:                "preference" | "prohibition",
      revision_id:         string,            // git sha or revision token
      bytes:               int                // size contribution to the 10 KB cap
    }
  ],
  preferences_truncated:   bool,              // true iff cap forced truncation
  preferences_total_bytes: int,               // ≤ 10240
  classified_intent:       {
    class:                 enum,              // gap-12 §3 emitted class
    confidence:            float,             // 0..1
    path:                  "heuristic" | "llm" | "caller_tagged"
  } | null,                                   // null only if `intent` was caller-supplied AND classifier audit was skipped
  applied_filters: {
    bi_temporal_at:        RFC3339,           // the t_now used for §4.1 filter
    pre_filter_excluded:   int,               // count of facts dropped by §4.1; exposed for observability
    provenance_dropped:    int                // count of facts dropped by §1.5 enforcement
  },
  store_health: {
    s3_used:               bool,              // false iff lexical-only fallback ran (composition §7)
    degraded:              bool
  }
}
```

**Algorithm (composition §3.1 + scoring §4)**

Order is binding. Step 1 runs **before** any retriever (binding §0.3 #2).

1. **Bi-temporal validity filter** (scoring §4.1): exclude any fact where `valid_to ≤ t_now` or `valid_from > t_now` from the candidate set entirely. This is the pre-RRF gate; not a post-score filter.
2. **Intent classify** (gap-12; synchronous, ≤ 200 ms residual budget). Caller-supplied `intent` is honored only if classifier audit confidence is < 0.8 *against* the caller's tag (gap-12 §6 row 6).
3. **Weight-tuple select** (gap-03; reads tenant scoring config from S2).
4. **Parallel retrieve**: graph-walk on S1 ∥ vector ANN on S3 ∥ lexical-only on S1 episode text (the lexical fallback survives S3 outage; composition §7).
5. **RRF combine** (scoring §4.2; `k_rrf = 60`).
6. **Post-rerank**: apply intent-routed multiplicative bonus (scoring §4.3) + utility prior (§4.4) → composed score (§4.5).
7. **Truncate to top-k**.
8. **Provenance enforcement** (§1.5): drop any candidate without an `episode_id`; increment `provenance_dropped`.
9. **Write recall ledger entry** to S2 (synchronous; this is the utility-feedback hook).
10. **Prepend preferences** (composition §3.5; gap-09 §6): fetch tenant's `kind=preference|prohibition` S4a pages via qmd-class index; concatenate up to 10 KB; truncate by recency-of-revision; set `preferences_truncated`.
11. **Emit one `recall` event per top-k candidate** (scoring §8.1; §1.4 derives `recall_id`).
12. **Return** `RecallResponse`.

**Errors**

- `400 invalid_request` — schema violation.
- `403 forbidden` — cross-tenant scope.
- `429 rate_limited` — WS8 cap.
- `5xx store_unavailable` — S1 down (hard fail; composition §7 row 1). S3 down → degraded-not-fail (`store_health.s3_used=false`).

**Emit-points** (per §5 matrix)

- `recall` × top-k (one per returned fact, after step 11).
- No `recall_outcome` — that fires asynchronously when downstream telemetry observes citation/correction/no-op (scoring §8.1).

#### §2.1.1 The `k=0` shape

Legal and useful: caller wants only the always-load preference context. Behavior:

- The bi-temporal filter, retrievers, RRF, rerank are skipped (top-0 has no candidates).
- `recall_id` is **still** computed and returned (eval-plan §4.6 ingest path needs it; scoring §8.3 replay invariant requires the join key for the empty case too).
- `facts: []`, `preferences: [...]`, `preferences_truncated`, `preferences_total_bytes`.
- `classified_intent` is still populated (the classifier may have run; the response is what the caller sees).
- **Zero `recall` events emitted** — the per-top-k loop has zero iterations. The recall-ledger row in S2 is still written (records the fact that a k=0 recall happened; useful for v1.x operator-trace ingest).

This makes "preferences-only context refresh" a first-class call without minting a separate verb.

#### §2.1.2 Tenant / auth / rate-limit notes

Hot-path read; rate-limit per `(tenant_id, principal)` (WS8 sets value). Tenant scope filter is applied at every retriever (composition §5.2 invariant); cross-tenant facts are unreachable by construction.

### §2.2 `recall_synthesis(uri | query)`

The S4a-targeted markdown synthesis path. Composition §3.2. **Distinct from `recall`** — synthesis pages are S4a-canonical (authored prose, not facts), and conflating them with the fact path corrupts both surfaces.

**Signature**

```
recall_synthesis(
  uri?:   string,    // mutually exclusive with `query`
  query?: string,    // mutually exclusive with `uri`
  k?:     int = 5
) -> SynthesisResponse
```

Exactly one of `uri` or `query` is required. URI form is direct fetch; query form is qmd-class hybrid retrieval (BM25 + vector + LLM rerank) over the markdown corpus.

**Response schema (`SynthesisResponse`)**

```
{
  recall_id:    uuidv7,                       // §1.4; same derivation rule
  pages: [
    {
      page_uri:    string,
      title:       string,                    // from frontmatter
      kind:        enum,                      // gap-09 §3: preference | procedure | narrative
      frontmatter: object,                    // YAML frontmatter, parsed
      content:     string,                    // markdown body
      revision_id: string,                    // git sha
      score:       float,                     // qmd-class score
      provenance:  {                          // synthesis-page provenance differs from fact-path
        page_uri:           string,
        revision_id:        string,
        author_principal:   string,
        last_modified_at:   RFC3339
      }
    }
  ],
  store_health: { s4a_available: bool }
}
```

**Algorithm**

1. If `uri` form: direct fetch by S4a stable uri; bypass index.
2. If `query` form: qmd-class hybrid retrieve over S4a (gap-07).
3. **No bi-temporal filter** — synthesis pages are authored, not bi-temporally stamped (composition §3 row S4a). Revision history is git-based.
4. Emit `recall` event per returned page with `path=synthesis` marker (see below).
5. Return.

**Emit-points**

Per the §5 decision: `recall_synthesis` emits the standard scoring §8.2 `recall` event envelope, with two differences:

- `score_inputs.path = "synthesis"` (a distinguished marker; v2 trainers can split or unify by their own preference).
- `fact_ids` is set to the S4a page-ids returned (stable URIs hashed to uuidv7), not S1 fact-edge ids.

**Errors**

- `400 invalid_request` — both `uri` and `query` provided, or neither.
- `404 not_found` — `uri` form with unknown URI.
- `5xx` — S4a corruption (composition §7 row "S4a corrupted"); `recall_synthesis` is the *only* read path that goes hard-fail on S4a outage; the fact `recall` path is unaffected.

### §2.3 `peer_message_pull(recipient_scope, mark_read?, max?)`

Pull-based inbox read. gap-10 §3.4.

**Signature**

```
peer_message_pull(
  recipient_scope: string,        // direct (agent-id) or role (role-name)
  mark_read?:      bool = true,
  max?:            int = 100
) -> PeerMessagePullResponse
```

**Response schema**

```
{
  messages: [
    {
      msg_id:        uuidv7,
      from_agent:    string,
      to:            string,                  // recipient_scope echoed
      type:          "query" | "info" | "claim" | "handoff",
      payload:       object,                  // type-dependent
      sent_at:       RFC3339,
      ttl_expires_at: RFC3339,
      requires_ack:  bool,
      in_reply_to?:  uuidv7,                  // gap-10 §6 threading
      provenance: {
        source:      "peer_message",
        from_agent:  string,
        msg_id:      uuidv7,
        sent_at:     RFC3339
      }
    }
  ],
  inbox_unread_remaining: int,                // after this pull
  cap_dropped_since_last_pull: int            // gap-04 §5 cap; gap-10 §3.4
}
```

**Behavior**

- Returns up to `max` unread messages. If `mark_read=true`, marks them as read in S2 inbox table and writes ack events (for `requires_ack=true` messages).
- Cap (100 unread per recipient; gap-10 §3.4): if exceeded between pulls, oldest non-`query` messages are dropped server-side; the count surfaces in `cap_dropped_since_last_pull` so the caller can alarm.

**Errors**

- `403 forbidden` — recipient_scope not under principal's tenant.
- `404 not_found` — role-name does not resolve to any agent.

**Emit-points**

None on the v2 contract. Inbox reads are operational; they do not feed the scoring training signal. (If a `claim` is later materialized into memory by `remember`, that `remember` call emits its own events.)

### §2.4 `peer_message_status(msg_id)`

Sender-side delivery polling. gap-10 §3.5.

**Signature**

```
peer_message_status(msg_id: uuidv7) -> PeerMessageStatusResponse
```

**Response schema**

```
{
  msg_id:         uuidv7,
  status:         "pending" | "delivered" | "acked" | "expired" | "dropped_cap",
  sent_at:        RFC3339,
  delivered_at?:  RFC3339,
  acked_at?:      RFC3339,
  expired_at?:    RFC3339,
  recipient:      string                       // resolved recipient (for role-addressed; the agent that received)
}
```

**Errors**

- `404 not_found` — unknown msg_id (or in another tenant).
- `403 forbidden` — caller is neither sender nor recipient.

**Emit-points**

None.

---

## §3 Write verbs

### §3.1 `remember(content, intent?, idempotency_key, provenance, kind?)`

The canonical write. Composition §4.1; gap-12 (intent classifier integration); gap-08 (idempotency); gap-05 (provenance required).

**Signature**

```
remember(
  content:                 string,
  intent?:                 enum,                    // caller-tagged; honored unless classifier objects ≥0.8
  kind?:                   enum,                    // gap-09 §3 shape hint; if absent classifier picks
  idempotency_key:         uuidv7,                  // mandatory; §1.2
  provenance: {
    source_uri:            string,                  // mandatory; §1.5
    agent_id?:             string,                  // defaults to principal
    derived_from?:         string                   // optional; e.g. peer_message:msg_id
  },
  force_skip_classifier?:  bool                     // default false; tenant_admin-gated; bypasses step 3 on the escalate-review approval path. Ground truth: deployment §6.3.
) -> RememberResponse
```

**Response schema (`RememberResponse`) — the full envelope, decision (a)**

```
{
  episode_id:           uuidv7,
  idempotency_key:      uuidv7,              // echoed for caller correlation
  classified_intent: {
    class:              enum,                // gap-12 §3 (one of 7 classes)
    confidence:         float,               // 0..1
    path:               "heuristic" | "llm" | "caller_tagged"
  },
  retention_class:      enum,                // gap-09 §3 shape: episodic_fact | preference | procedure | narrative — derived from class+kind
  accepted:             bool,                // false iff class ∈ {drop, reply_only}; episode is then NOT durably stored
  escalated:            bool,                // true iff class = escalate; episode is staged but pending human review
  ack:                  "synchronous_durable" | "staged_for_review" | "dropped",
  applied_at:           RFC3339,
  next_consolidate_at?: RFC3339              // estimate; the async extraction phase runs ≥ this
}
```

**Algorithm (composition §4.1 synchronous portion)**

1. **Validate idempotency** (§1.2) — replay returns 200 with the original response.
2. **Validate provenance** (§1.5) — refuse if `source_uri` missing.
3. **Run intent classifier** (gap-12 §6) — heuristic-first; LLM-residual within the 200 ms budget.
   - Caller-supplied `intent` is honored only if classifier audit confidence is < 0.8 *against* the caller's tag (gap-12 §6 row 6).
   - **Skip this step entirely if `force_skip_classifier=true`** — only callable by principals holding the `tenant_admin` capability; refuse with `403 forbidden` otherwise. The bypass is the escalate-review approval path (deployment §6.3) so a payload that previously escalated does not re-escalate on re-submission; an S5 `force_skip_classifier_used{episode_id, principal, staged_id?}` audit row is emitted.
4. **Branch on class**:
   - `drop` / `reply_only` → `accepted=false`; **return immediately** with `ack="dropped"`. No S1/S2 write; the idempotency_key is recorded so retries are stable.
   - `escalate` → stage episode in S2 quarantine table; **return** with `ack="staged_for_review"`, status **422 classifier_escalate**.
   - `peer_route` → caller is hinted to use `peer_message`; episode is NOT written; status **400 invalid_request** with hint `use_peer_message`.
   - `remember:fact` / `remember:preference` / `remember:procedure` (or shape-equivalents) → continue.
5. **Begin transaction T1** (composition §5 row T1; gap-08 §3.1):
   - Insert episode into S1 with `tenant_id`, `agent_id`, `source_uri`, `derived_from?`, `kind`, `content`, `recorded_at`.
   - Insert episode-arrival event into S2 ledger (idempotency-key recorded; dream-daemon wake-signal).
6. **Commit T1**.
7. **Emit `remember` event** (scoring §8.1) capturing features-at-creation.
8. **Return `RememberResponse`** with `ack="synchronous_durable"`.

The async portion (extract → merge → embed → projection-regen) does NOT block the response. It runs on the dream-daemon's next gate. Each phase emits one of the six `consolidate_phase` events:

**The six `consolidate_phase` emit-points around `remember()`** (binding §0.3 #7):

| Order | Phase | Triggered by | What it emits |
|---|---|---|---|
| 1 | `extract` | dream-daemon picks up unextracted episode | `consolidate_phase {phase:"extract", run_id, episode_id}` start + done |
| 2 | `score` | post-extract, per fact | `consolidate_phase {phase:"score", run_id, fact_ids}` start + done |
| 3 | `promote` | per fact crossing promote threshold | `consolidate_phase {phase:"promote", run_id, fact_ids}` start + done; one `promote` event per promoted fact |
| 4 | `demote` | per fact crossing demote threshold | `consolidate_phase {phase:"demote", run_id, fact_ids}` start + done; one `demote` event per demoted fact |
| 5 | `consolidate` | merge contradictions; regenerate projections | `consolidate_phase {phase:"consolidate", run_id}` start + done |
| 6 | `invalidate` | per fact whose `valid_to` set during contradiction handling | `consolidate_phase {phase:"invalidate", run_id, fact_ids}` start + done; one `invalidate` event per invalidated fact |

Phases run **in order**; each is checkpointed in S5 (gap-08 §3.3) so a daemon crash resumes from the last `done`. The `consolidate_phase` event with `status: "in_progress"` is the resumption marker.

**Errors**

- `400 missing_idempotency_key`, `400 provenance_required`.
- `409 idempotency_conflict` — same key, different body (§1.2).
- `422 classifier_escalate` — sensitive-class hit; staged for review.
- `5xx store_unavailable` — S1 down → hard fail (composition §7 row 1).

**Emit-points**

- 1 × `remember` (synchronous; step 7).
- 6 × `consolidate_phase` (asynchronous, surrounding the post-remember consolidation cycle; §0.3 #7).
- 0..N × `promote` / `demote` / `invalidate` (within the corresponding phases).

**Tenant / auth / rate-limit**

Per-tenant write rate limit (WS8). `escalate`-class writes additionally count against a sensitive-class quota (gap-10 §6 primary; gap-11 §3.3 auxiliary).

### §3.2 `promote(fact_id, reason?, idempotency_key, expected_version)`

Composition §4.2; gap-04 (CAS).

**Signature**

```
promote(
  fact_id:           uuidv7,
  reason?:           string,
  idempotency_key:   uuidv7,
  expected_version:  int
) -> PromoteResponse
```

**Response schema (decision #9)**

```
{
  flag_id:                       uuidv7,             // S2 flag row id
  fact_id:                       uuidv7,
  expected_version_consumed:     int,                // the version this call CAS-matched against
  applies_at_next_consolidate:   RFC3339,            // estimate
  ack:                           "intended_not_applied"
}
```

The synchronous body **records intent only** (composition §4.2). The S1 mutation runs at the next consolidation cycle; the response makes that explicit so callers don't assume immediate visibility.

**Algorithm**

1. Validate idempotency (§1.2).
2. Validate fact exists in S1 under tenant.
3. CAS on `expected_version` (§1.3). On mismatch → 409 `version_conflict`.
4. Begin transaction T2 (composition §5 row T2):
   - Write promotion-flag to S2 (with `flag_id`, `fact_id`, `principal`, `reason`, `idempotency_key`).
   - Append entry to S5 (rationale + caller).
5. Commit T2.
6. Return.

The actual `promote` scoring event fires at consolidation phase 3 (§3.1), not synchronously here.

**Errors**

- `400 missing_idempotency_key`.
- `404 not_found` — unknown `fact_id`.
- `409 version_conflict` — CAS mismatch.
- `409 idempotency_conflict` — same key, different body.
- `410 purged` — fact was purged; only retention proof remains.
- `5xx store_unavailable` — S2 down (composition §7 row 2).

**Emit-points**

- None synchronously. The async dream-daemon's promote phase emits one `promote` event (§3.1 phase 3).

### §3.3 `forget(target, mode, reason, idempotency_key, expected_version)`

Composition §4.2; gap-11 §3 (modes). The most expressive write verb in the surface.

**Signature**

```
forget(
  target: {
    fact_id?:    uuidv7,                    // mode=invalidate → fact-edge target
    episode_id?: uuidv7                     // mode=quarantine → episode target
  },
  mode:              "invalidate" | "quarantine" | "purge",
  reason:            string,                // mandatory; lands in S5 audit
  idempotency_key:   uuidv7,
  expected_version:  int                    // version of fact_id (mode=invalidate, or mode=purge with fact_id target) or episode_id (mode=quarantine, or mode=purge with episode_id target)
) -> ForgetResponse
```

**Mode aliases** (binding mapping; HANDOFF §8.3 wording → gap-11 canonical):

| Caller passes | Canonical mode | Notes |
|---|---|---|
| `"soft"` | `"invalidate"` | Accepted alias. |
| `"deny"` | `"quarantine"` | Accepted alias. |
| `"invalidate"` / `"quarantine"` / `"purge"` | as-is | Canonical. |

The doc uses the canonical names; either form is accepted on the wire.

**Response schema**

```
{
  flag_id:                       uuidv7,
  target:                        { fact_id? | episode_id? },
  mode_applied:                  "invalidate" | "quarantine" | "purge",
  expected_version_consumed:     int,
  applies_at_next_consolidate:   RFC3339,           // estimate; for purge, this is when the delete fires (sync? see below)
  cascade_count?:                int,               // present for mode=quarantine; gap-11 §3.2; estimated, finalized async
  retention_proof_id?:           uuidv7,            // present for mode=purge; S5 retention proof row id
  ack:                           "intended_not_applied" | "purge_committed"
}
```

**Mode-specific algorithms**

- **`mode="invalidate"`** (default; gap-11 §3.1):
  1. CAS on fact's `expected_version`.
  2. T2: write forget-flag(`mode=invalidate`) to S2; entry to S5.
  3. Async at next consolidate: set `valid_to = now()` on the fact-edge.
  4. Response `ack="intended_not_applied"`.
  5. Emit `invalidate` event at consolidation phase 6 (§3.1).

- **`mode="quarantine"`** (gap-11 §3.2):
  1. CAS on episode's `expected_version`.
  2. T2: write forget-flag(`mode=quarantine`) + estimate `cascade_count` (count of facts derived from episode); entry to S5.
  3. If `cascade_count > tenant_quarantine_budget` → return **412 precondition_failed**; caller must split.
  4. Async at next consolidate: cascade-invalidate every derived fact; set quarantine flag on episode (excludes from re-extraction).
  5. Response includes `cascade_count` (estimated; final value visible via `audit()`).
  6. `ack="intended_not_applied"`.
  7. Emit one `invalidate` event per cascaded fact at consolidation phase 6.

- **`mode="purge"`** (gap-11 §3.3; auth-class):
  1. **Auth check**: principal must hold the `forget_purge` capability. Otherwise → **403 forget_denied**.
  2. **Rate-limit check** (per-tenant purge cap; WS8 sets value). Excess → **403 forget_denied** with `retry_after_ms`.
  3. CAS on target's `expected_version`.
  4. T2 with **retention-proof-before-delete ordering** (gap-08 §3.6):
     - Write retention proof to S5: `(target_id, requested_by, reason, deleted_at, content_hash, retention_proof_id)`.
     - Hard-delete fact-edge or episode from S1; embeddings from S3; projections from S4b.
     - Commit T2 (atomic; if delete fails, proof rolls back per gap-08 §3.6).
  5. Response `ack="purge_committed"` — purge is **synchronous**, distinguishing it from invalidate/quarantine.
  6. Emit `invalidate` event for the purged fact (with a `purge=true` marker on score_inputs) so the v2 trainer sees the terminal transition.

**Errors**

- `400 missing_idempotency_key` / `400 invalid_request` (e.g., mode=invalidate but only `episode_id` supplied).
- `403 forget_denied` — purge auth or rate-limit (gap-11 §3.3).
- `403 forbidden` — cross-tenant target.
- `404 not_found`.
- `409 version_conflict` — CAS mismatch.
- `409 idempotency_conflict`.
- `410 purged` — already purged.
- `412 precondition_failed` — quarantine cascade exceeds budget.

**Emit-points**

| Mode | Synchronous | Asynchronous |
|---|---|---|
| `invalidate` | none | 1 × `invalidate` (consolidate phase 6) |
| `quarantine` | none | N × `invalidate` (one per cascaded fact, consolidate phase 6) |
| `purge` | 1 × `invalidate` with `purge=true` marker | none |

### §3.4 `peer_message(payload, recipient_scope, type, idempotency_key, ttl?, requires_ack?, in_reply_to?)`

Cross-agent peer messaging within tenant. gap-10 §3.

**Signature**

```
peer_message(
  recipient_scope:  string,                          // direct agent-id or role-name; * forbidden in v1 except by RBAC opt-in
  type:             "query" | "info" | "claim" | "handoff",
  payload:          object,                          // type-dependent; classifier may inspect for claim
  idempotency_key:  uuidv7,
  ttl?:             string  = "P7D",                 // ISO-8601 duration; default 7 days (gap-10 §3.4)
  requires_ack?:    bool    = false,
  in_reply_to?:     uuidv7                            // gap-10 §6 threading
) -> PeerMessageResponse
```

**Response schema**

```
{
  msg_id:            uuidv7,
  recipient:         string,                          // resolved recipient (for role-addressed)
  status:            "pending",                       // always pending at synchronous return; poll via peer_message_status
  ttl_expires_at:    RFC3339,
  inbox_size_after:  int                              // recipient's unread count post-write
}
```

**Behavior**

- Synchronous request/response. Verb returns when the message is durably written to S2 inbox table; **delivery is async** — recipient pulls on its own cadence.
- Cross-tenant: **403 forbidden** (composition §5.2 invariant).
- Sensitive-class scan at **send time** (gap-10 §6 primary; gap-11 §3.3 auxiliary): claim payloads are scanned by the sensitive-class taxonomy *before* write. Hits → **422 classifier_escalate** with hint to revise.
- Inbox cap (100 unread; gap-04 §5 / gap-10 §3.4): on cap, oldest non-`query` messages are dropped server-side; counter exposed via `peer_message_pull` response.

**Errors**

- `400 missing_idempotency_key`.
- `403 forbidden` — cross-tenant or RBAC-blocked broadcast.
- `404 not_found` — `recipient_scope` resolves to nothing.
- `409 idempotency_conflict`.
- `422 classifier_escalate` — sensitive-class hit on `claim` payload.

**Emit-points**

None synchronously. If the recipient later materializes a `claim` via `remember`, that call emits its own event chain.

---

## §4 Operator / admin verbs

### §4.1 `capture_opt_in_trace(scope, action, idempotency_key)`

The v1.x operator-trace ingest enablement verb. eval-plan §4.6; HANDOFF §11.5; pairs with `scripts/eval/lethe_native/loader.py::capture_opt_in_trace` (the loader-side function; this verb is the API surface that toggles capture per tenant).

**Signature**

```
capture_opt_in_trace(
  scope:            "all" | "recall" | "remember" | "forget" | "peer_message",
  action:           "enable" | "revoke",
  idempotency_key:  uuidv7,
  consent_record?:  string          // tenant-supplied reference to their consent artifact
) -> CaptureOptInResponse
```

**Response schema**

```
{
  tenant_id:           string,
  scope:               string,
  action:              string,
  effective_at:        RFC3339,
  prior_state:         "enabled" | "disabled",
  retire_jobs_queued?: int           // present iff action="revoke"; count of previously-ingested cases scheduled for retirement (eval-plan §4.6 step 1)
}
```

**Behavior**

- **Idempotent**: re-enabling an already-enabled scope is a no-op (returns 200 with `prior_state="enabled"`); same for re-revoking.
- **Per-tenant**: a tenant cannot enable capture on another tenant.
- **Revocation triggers retirement**: previously-ingested cases for the revoked scope are scheduled for retirement on the next eval-set snapshot (eval-plan §4.6 step 1). The verb does not block on retirement completion; the queued-job count is exposed for caller observability.
- **Auth**: tenant-admin-only (WS8 maps the role).

**Errors**

- `400 missing_idempotency_key` / `400 invalid_request`.
- `403 forbidden` — non-admin principal.
- `409 idempotency_conflict`.

**Emit-points**

None on the scoring training-signal pipeline. The verb itself is logged to S5 as an audit event (consent change is auditable).

**Binding constraints (HANDOFF §10):**
- This verb does NOT import traces from any foreign system. SCNS `session_store` is not a source. All ingest is from Lethe's own trace store, gated by this verb.
- This verb does NOT capture from tenants without an active `enable` action.
- Revocation retires previously-ingested cases; opt-out is honored.

### §4.2 `emit_score_event(event)` — internal sink, not external verb

Per decision #7, this is **specced here for clarity but is NOT an external verb**. It is the per-event sink in `scripts/eval/metrics/emitter.py` (scoring §8.4). Documented here so the binding from each verb's emit-points to the sink is unambiguous.

**Internal signature**

```python
def emit_score_event(event: ScoreEvent) -> None:
    """Append a v2-learned-scorer training signal to the per-tenant audit log.

    Validates against §8.2 envelope schema, gates on contamination_protected,
    writes append-only to <run_dir>/score_events/<tenant_id>/<yyyy>/<mm>/<dd>.jsonl.
    """
```

**Event envelope (mirrors scoring §8.2; binding fields)**

```
{
  event_id:                uuidv7,
  event_type:              "remember" | "recall" | "recall_outcome"
                         | "promote" | "demote" | "invalidate" | "consolidate_phase",
  tenant_id:               string,
  ts_recorded:             RFC3339,
  ts_valid:                RFC3339,
  model_version:           string,    // semver of scorer package
  weights_version:         string,    // sha256 of the §7 knob table snapshot
  contamination_protected: bool,      // mandatory; drop on emit if false
  fact_ids:                [uuidv7],
  recall_id?:              uuidv7,    // present on recall, recall_outcome
  score_inputs:            { ... },   // scoring §3
  score_output:            float,
  decision:                string,
  outcome?:                string,    // recall_outcome only
  provenance: {
    source_uri:      string,
    edit_history_id: string
  }
}
```

**Verb → sink wiring**

Each verb in §2/§3 calls `emit_score_event()` at the points named in §1.7 and §5. The sink validates the envelope (drop on schema violation; drop on `contamination_protected=false` outside the bench shard; alarm on missing `provenance`). The drop counter feeds `health()`.

This is the contract WS6 owns; the implementation lands in WS6's commit set as part of `metrics/emitter.py`.

### §4.3 `consolidate(force?, scope?)`

Admin trigger for the dream-daemon. Composition §4.4. Normally consolidation runs gated; this verb is for ops + tests.

**Signature**

```
consolidate(force?: bool = false, scope?: { tenant_id?: string }) -> ConsolidateResponse
```

**Response schema**

```
{
  run_id:           uuidv7,
  triggered:        bool,                       // false if a run is already in progress and force=false
  current_phase?:   "extract" | "score" | "promote" | "demote" | "consolidate" | "invalidate",
  acquired_lock:    bool
}
```

**Behavior**

- Returns immediately. The cycle runs asynchronously.
- `force=true`: bypass gate-interval check (admin-only; rate-limited).
- Emits the six `consolidate_phase` events as the daemon progresses (same as the post-`remember` async chain; §3.1).

**Errors**

- `403 forbidden` — non-admin.
- `409` — lock held and `force=false`.

### §4.4 `health()` and `audit(query)`

Operational reads. Cross-link composition §7 (degraded modes) and §7.1 (two-stores-down matrix).

**`health()` signature + response**

```
health() -> {
  overall:   "healthy" | "degraded" | "down",
  stores: {
    s1: "up" | "down",
    s2: "up" | "down",
    s3: "up" | "stale" | "down",
    s4a: "up" | "down",
    s4b: "up" | "stale",
    s5: "up" | "down"
  },
  degraded_modes: [ string ],         // e.g. ["s3_unavailable_lexical_only", "two_stores_down: s2+s5"]
  daemon: {
    last_successful_consolidate_at:  RFC3339,
    current_run_id?:                 uuidv7,
    current_phase?:                  string,
    backoff_until?:                  RFC3339
  },
  emitter: {
    drop_count_24h: int,              // §4.2 sink drops (provenance missing, schema violation, contamination flag)
    last_drop_reason?: string
  }
}
```

**`audit(query)` signature**

```
audit(
  query: {
    fact_id?:        uuidv7,
    episode_id?:     uuidv7,
    recall_id?:      uuidv7,
    forget_proof_id?: uuidv7,
    since?:          RFC3339,
    until?:          RFC3339
  }
) -> AuditResponse
```

Returns S5 entries matching the filter, joined with S1 provenance edges. Slow-path; no latency budget; intended for operators and CI lint hooks (composition §3.4).

**Errors / Emit-points**

- `health()`: never errors above transport layer. No emit-points.
- `audit()`: `403` on cross-tenant query (unless principal holds an `audit_global` capability for ops). No emit-points.

---

## §5 Emit-point matrix (authoritative)

For each verb, the events that fire and in what order. Cross-link to scoring §8.1 for event semantics.

| Verb | Synchronous emits | Asynchronous emits (post-return) | Order constraint |
|---|---|---|---|
| `recall` | `recall` × top-k (after step 11) | `recall_outcome` × N (when downstream telemetry observes citation/correction/no-op) | Sync emits before response return |
| `recall_synthesis` | `recall` × pages (with `path=synthesis`) | `recall_outcome` × N | Same |
| `remember` (accepted) | `remember` × 1 | `consolidate_phase` × 6 (extract → score → promote → demote → consolidate → invalidate); 0..N of `promote`/`demote`/`invalidate` within phases 3/4/6 | Phase order is binding; checkpoints in S5 |
| `remember` (drop / reply_only) | none | none | n/a |
| `remember` (escalate) | none until human-review path; on accept, same as accepted-path | same | Reviewer action triggers the chain |
| `promote` | none | `promote` × 1 (consolidate phase 3) | Async at next consolidate |
| `forget(invalidate)` | none | `invalidate` × 1 (consolidate phase 6) | Async |
| `forget(quarantine)` | none | `invalidate` × N (one per cascaded fact, phase 6) | Async; cascade serialized within phase |
| `forget(purge)` | `invalidate` × 1 with `purge=true` marker | none | Sync (purge is synchronous; §3.3) |
| `peer_message` | none | none directly; if recipient `remember`s a claim, that path emits | n/a |
| `peer_message_pull` | none | none | n/a |
| `peer_message_status` | none | none | n/a |
| `capture_opt_in_trace` | none on score-event sink; S5 audit row written | none | n/a |
| `emit_score_event` | n/a (this IS the sink) | n/a | n/a |
| `consolidate` | none (returns immediately) | `consolidate_phase` × 6; `promote`/`demote`/`invalidate` within phases | Same as the async chain after `remember` |
| `health` / `audit` | none | none | n/a |

**Replayability invariant** (scoring §8.3, restated): given the audit log up to time `t` and a frozen snapshot of S1/S2/S3 at `t`, replaying the log reproduces every score the system computed. The `recall_id` derivation (§1.4) is deterministic so replays produce identical join keys.

---

## §6 Traceability matrix

Every verb maps to (composition §, gap §, scoring §). No `TBD` rows.

| Verb | Composition § | Gap brief(s) § | Scoring § |
|---|---|---|---|
| `recall` | §3.1 (read path), §3.5 (preferences prepend), §5 (consistency), §6 (provenance) | gap-05 §3 (provenance enforcement), gap-09 §6 (always-load 10 KB), gap-12 §3+§6 (intent classifier) | §4.1 (bi-temporal filter), §4.2 (RRF), §4.3 (intent bonus), §4.4 (utility prior), §4.5 (composed), §8.1+§8.2 (`recall` event) |
| `recall_synthesis` | §3.2 (S4a path) | gap-07 (markdown-scale, qmd-class index), gap-09 §3 (kind taxonomy) | §8.1+§8.2 (`recall` event with `path=synthesis`) |
| `peer_message_pull` | §3.3 (inbox read) | gap-10 §3.4 (inbox semantics) | n/a (no scoring event) |
| `peer_message_status` | §3.3 | gap-10 §3.5 (ack contract) | n/a |
| `remember` | §4.1 (write path), §5 (T1 ACID), §6 (provenance) | gap-05 §3 (provenance required), gap-08 §3.1 (idempotency), gap-12 §3+§6 (classifier branches), gap-11 §3.3 (escalate-class) | §3 (consolidate-time scoring), §8.1 (`remember` event), §8.1 (`consolidate_phase` × 6) |
| `promote` | §4.2 (synchronous flag, async apply) | gap-04 §4 (CAS), gap-08 §3.2 (T2), gap-01 §6 (promotion threshold) | §3 (consolidate-time threshold), §8.1 (`promote` event) |
| `forget(invalidate)` | §4.2, §6 (provenance survives) | gap-11 §3.1 (mode), gap-04 §4 (CAS), gap-08 §3.2 (T2) | §6.1 (recall floor), §6.4 (utility freeze), §8.1 (`invalidate` event) |
| `forget(quarantine)` | §4.2, §7 (peer-corruption mitigation) | gap-11 §3.2 (cascade), gap-10 §6 (peer-message episode poisoning) | §6.1, §8.1 |
| `forget(purge)` | §4.2, §6 (provenance broken; retention-proof remains) | gap-11 §3.3 (auth-class), gap-08 §3.6 (proof-before-delete) | §6.3 (post-grace purge), §8.1 |
| `peer_message` | §4.3 (write variant), §5.2 (tenant boundary), §6 (two-step provenance) | gap-10 §3 (verb spec), gap-11 §3.3 (sensitive scan at send) | n/a sync; downstream `remember` if claim-materialized |
| `capture_opt_in_trace` | §10 (open seam: opt-in for v1.x ingest) | (cross-ref eval-plan §4.6) | §8.5 (privacy boundary; `contamination_protected` flag) |
| `emit_score_event` (sink) | n/a (cross-cutting) | gap-05 §3.4 (provenance mandatory), gap-08 §3.1 (idempotency persists) | §8.2 (envelope), §8.4 (sink contract), §8.5 (privacy invariants) |
| `consolidate` (admin) | §4.4 (dream-daemon main loop) | gap-01 §3 (gate logic), gap-08 §3.3 (resumability) | §3 (consolidate-time scoring), §8.1 (`consolidate_phase` × 6) |
| `health` / `audit` | §3.4 (audit reads), §7.1 (degraded states) | gap-08 §3.5 (startup integrity) | §8.4 (emitter drop count) |

---

## §7 Verification audits

### §7.1 SCNS-independence audit

Mirroring the scoring §7 audit pattern (HANDOFF §10 binding constraint).

**Audit:** `grep -i scns docs/06-api-design.md`

**Expected result:** zero hits that name SCNS as a verb, type, schema, or data source. Allowed hits: only boundary-clauses that disclaim SCNS dependency.

**Result (transcribed at commit time):**

- All `scns`/`SCNS` mentions in this doc are in §0.3 (binding constraint #1 disclaimer), §4.1 (`capture_opt_in_trace` binding constraint disclaimer), and this §7.1 (the audit itself).
- **Zero verb signatures, zero schema fields, zero data sources reference SCNS.**
- The verb `capture_opt_in_trace` ingests **only Lethe's own trace store**, gated by the verb's own opt-in action. SCNS `session_store` is explicitly excluded.

This audit is verifiable: run `grep -in scns docs/06-api-design.md`; every hit should be a disclaimer or boundary clause, not a dependency.

### §7.2 Idempotency-key coverage audit

**Claim:** every write verb carries `idempotency_key`.

| Verb | `idempotency_key` in signature? | §-ref |
|---|---|---|
| `recall` | n/a (read) | §2.1 |
| `recall_synthesis` | n/a (read) | §2.2 |
| `peer_message_pull` | n/a (read; `mark_read` is the side-effect, but pull is conceptually idempotent on its own snapshot) | §2.3 |
| `peer_message_status` | n/a (read) | §2.4 |
| **`remember`** | **yes** | §3.1 |
| **`promote`** | **yes** | §3.2 |
| **`forget`** | **yes** | §3.3 |
| **`peer_message`** | **yes** | §3.4 |
| **`capture_opt_in_trace`** | **yes** | §4.1 |
| `emit_score_event` (sink) | n/a (internal append-only) | §4.2 |
| `consolidate` | n/a (admin trigger; idempotent via `current_phase` short-circuit) | §4.3 |
| `health` / `audit` | n/a (read) | §4.4 |

**Coverage: 5/5 write verbs carry mandatory `idempotency_key` (`remember`, `promote`, `forget`, `peer_message`, `capture_opt_in_trace`). PASS.**

### §7.3 Emit-point coverage audit

**Claim:** every scoring §8.1 event type is emitted by at least one verb in this doc.

| Event | Emitted by | §-ref |
|---|---|---|
| `remember` | `remember` (sync) | §3.1 |
| `recall` | `recall` (sync × top-k), `recall_synthesis` (sync × pages, with `path=synthesis`) | §2.1, §2.2 |
| `recall_outcome` | downstream telemetry tied to a prior `recall_id` | §1.7 (asynchronous; not directly emitted by a write verb in this doc) |
| `promote` | `promote` (async, consolidate phase 3) | §3.2 |
| `demote` | async dream-daemon (consolidate phase 4); not surfaced as a verb | §3.1, §4.3 |
| `invalidate` | `forget(invalidate)`, `forget(quarantine)` cascade, `forget(purge)` (with marker), async contradiction handling | §3.3 |
| `consolidate_phase` | `remember` (×6 around the post-write cycle), `consolidate` (admin trigger) | §3.1, §4.3 |

**Coverage: 7/7 event types covered. PASS.**

---

## §8 Anti-checklist — what WS6 is NOT

Closing section. Restated for visibility; mirrors §0.2 with explicit denials.

WS6 **does not** commit to:

- **A transport / RPC choice.** No claim is made about REST vs. gRPC vs. MCP vs. JSON-RPC vs. in-process. Any such choice is WS8.
- **A wire format.** Schemas in this doc are abstract type-annotated field lists; the JSON / protobuf / msgpack encoding is WS8.
- **An auth scheme.** No claim about OAuth vs. JWT vs. mTLS vs. API keys. The doc references `principal` and `tenant_id` as logically-extracted-from-transport; WS8 picks the mechanism.
- **RBAC role definitions.** The doc names capabilities (`forget_purge`, `audit_global`, `tenant_admin`) abstractly; mapping capabilities to roles, and roles to principals, is WS8.
- **Rate-limit numerical caps.** The doc names *where* limits attach (per `(tenant, principal)` for hot-path; per-tenant for `forget(purge)`; per-tenant for sensitive-class `escalate`); the values are WS8.
- **Deployment shape.** No claim about single-binary vs. sidecar vs. hosted service vs. embedded library. WS8.
- **A SCNS compatibility shim.** SCNS is a design-pattern reference only (HANDOFF §10 binding constraint #1). No verb in this surface reads from `~/.scns/`, imports from the SCNS repo, or accepts SCNS schemas/types/data sources as input. The §7.1 audit is the proof.
- **SCNS-shaped verbs.** No verb in this surface mirrors a SCNS verb signature for compatibility. `remember`, `recall`, `forget` exist on their own merits per the gap-brief decisions; their shape is independent.
- **Scoring math.** WS5. This doc references scoring formulas only by §-number.
- **Eval-set composition.** WS4. This doc references eval signals only via the §4.2 sink contract.
- **Retention engine internals.** gap-01. This doc names dream-daemon phase boundaries as emit-points; the daemon's gating, locking, and backoff behavior is gap-01 / composition §4.4.
- **Schema migration policy.** WS7 owns SCNS-data → Lethe-store migration (a one-way ingest into the verb surface, not a dependency). The verbs in this doc are the migration target, not the migration mechanism.

---

## §9 Change log

- **(this commit)** Initial WS6 design — verb set, schemas, error taxonomy, emit-point matrix, traceability matrix, audits, anti-checklist. Awaiting WS6-QA fresh-eyes pass.
