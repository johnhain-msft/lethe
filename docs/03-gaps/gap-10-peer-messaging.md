# gap-10 — Cross-agent peer messaging

**PLAN.md §WS3 Track B #5** — first-class.
**Tier:** first-class (≥80 lines).
**Status:** active. Charter §4.1 commits to multi-agent + peer messaging in v1. Synthesis §3.5 (restored slot — synthesis disposed it but PLAN re-mandates).
**Substrate:** brief 02 MAGMA (multi-agent message routing in cognitive workspace; §3.2 message-typed buses); brief 04 memory-as-metabolism (signaling sub-system as a metabolic operator); brief 14 GitHub issue #1300 (cross-thread context request — closest prior art for "agent A's question reaches agent B's context"); brief 15 Letta (shared blocks, no message semantics); brief 16 MS Agent Framework (handoff via OpenAI handoffs API — handoff ≠ peer message); SCNS audit §4 (broker-mediated cross-agent state, implicit); composition §3 + §4 verbs (`peer_message` defined); gap-04 (concurrency); gap-05 (provenance).
**Cross-refs:** Pairs with gap-04 (concurrent recipient writes); gap-05 (peer-message provenance distinct from `remember` provenance); gap-12 (peer-message intent classification — does this peer-message imply a `remember`?).

---

## 1. The gap

PLAN.md §WS3 Track B #5: "Cross-agent peer messaging — semantics, addressing, attribution." Charter §4.1: multi-agent v1. Issue #1300 (brief 14) is the user-facing demand: "agent A asks a question that requires context from agent B's history." Today, no reviewed substrate exposes this as a typed verb.

The hazards if Lethe ships without it:

1. **Implicit cross-agent leakage.** Agents share via global memory, violating tenant + role isolation (composition §5.2).
2. **No attribution.** Recipient can't tell whether a fact came from peer-A or peer-B (gap-05 problem).
3. **Stamp confusion.** A peer-message may look indistinguishable from an external `remember`, so contradiction-resolution (gap-13) treats peers as authoritative when they're not.
4. **Unbounded inbox.** Without an addressing primitive, peer-messages accumulate without ack/read semantics.

Peer messaging is the multi-agent version of the substrate "agents talking past each other." Lethe's proposition is that this is a first-class verb, not a side effect of shared state.

## 2. State of the art

- **Brief 02 MAGMA §3.2.** Cognitive workspace exposes message-typed buses (perceptual, motor, episodic). Peer routing happens by subscribing to bus types. Useful primitive: messages have *type*, not just payload.
- **Brief 04 memory-as-metabolism §2.3.** Treats signaling as a metabolic operator with TTL-like decay; peer messages should not persist forever.
- **Brief 14 issue #1300.** Frames the user requirement: "context from another agent's run reaches this agent." Substrate is silent on how.
- **Brief 15 Letta.** Shared blocks: any agent can read/write a shared block. No addressing, no ack, no provenance separation.
- **Brief 16 MS AF.** "Handoffs" pass control + state from agent A to agent B (one-shot transfer). Distinct from peer messaging (concurrent agents communicate without handing off).
- **SCNS audit §4.** Cross-agent state via broker DB tables. No typed peer-message verb; conventions are implicit.

## 3. The verb (specification)

`peer_message(from_agent, to_agent_or_role, type, payload, ttl, requires_ack)` — write into recipient's inbox; recipient pulls on next `recall` cycle.

### 3.1 Addressing model

Three address shapes:
- **Direct (`to_agent=agent-id`).** Targeted to a single recipient agent.
- **Role (`to_role=role-name`).** Targeted to whichever agent currently fulfills `role-name` in the swarm (composition §5.2 tenant scope).
- **Broadcast within tenant (`to_role=*`).** Rare; explicitly opt-in; gated by RBAC (composition §10 open seam).

Cross-tenant peer messaging is **forbidden** (composition §5.2 invariant). Enforced at the dispatcher layer with a unit test (gap-04 §5).

### 3.2 Message typing

Mandatory `type` field, drawn from a small enum:
- `query` — peer is asking a question; reply expected within TTL.
- `info` — peer is sharing context; no reply expected.
- `claim` — peer is asserting a fact intended for the recipient's memory (recipient runs gap-12 intent classification on this).
- `handoff` — control transfer (subsumed; bridges to MS-AF-style handoffs).

The type drives recipient handling: a `claim` is a candidate `remember`, an `info` is just observable in the recipient's recall context, a `query` triggers a reply path.

### 3.3 Provenance

Peer-messages are stored with provenance distinct from `remember` (gap-05): `source = peer_message:from_agent:msg_id`. The recipient deciding whether to materialize a `claim` into its own memory creates a *new* episode with `source = self, derived_from = peer_message:...`. Two-step provenance.

### 3.4 Inbox semantics

- Inbox is a queue per `(tenant, recipient_address)`.
- Read semantics: `peer_message_pull(recipient)` returns unread messages, optionally marks-as-read.
- Cap: 100 unread messages per recipient (gap-04 §5). Beyond cap, oldest-non-`query` messages are dropped with a logged warning.
- TTL: messages expire after `ttl` (default 7 days). Expired messages are purged; if `requires_ack` was set and never delivered, an alert fires.

### 3.5 Ack contract

- `requires_ack=true` on a message creates a pending-ack record in S2.
- Recipient's first `peer_message_pull` that returns this message also writes an `ack` event to S2.
- Sender can poll `peer_message_status(msg_id)` for delivery state.
- Failure modes: ack lost in transit (exactly-once delivery is not promised; the sender SHOULD use idempotency keys for retry-safe semantics — gap-08 §3.1).

## 4. Candidate v1 approaches

| Candidate | Mechanic | Trade-offs |
|---|---|---|
| **(a) Inbox table in S2 (above spec)** | SQLite-backed inbox; pull-based; ack-tracked. | Aligns with composition §3 (S2 owns ledger-shaped data). Cheap. Pull means recipient discovers messages on its next recall cycle — latency = recall cadence. |
| **(b) Push via webhook to recipient agent** | Sender hits recipient's webhook directly. | Lower latency. Couples sender to recipient lifecycle; brittle when recipient is offline. Loses the inbox audit trail. |
| **(c) Embed messages in Graphiti as edges** | Peer-message becomes a typed edge `(from_agent) -[peer_message]-> (to_agent)`. | Provenance native to S1 graph. Couples concurrent-write throughput on S1 to peer-message rate; gap-04 contention worsens. |

## 5. Recommendation

**Candidate (a) — inbox in S2 with pull-based delivery, addressed by direct/role, typed (query/info/claim/handoff), with provenance distinct from `remember`.** Justification:

1. Aligns with composition §3 store ownership: S2 owns ledger-shaped operational data; peer-message inbox is exactly that.
2. Pull-based decouples recipient lifecycle from sender; offline recipient gets messages on next session.
3. `claim` type cleanly bridges to gap-12 (intent classification) — recipient decides whether to `remember` peer-claimed facts.
4. Cheap. SQLite inbox table + a pull query is one afternoon of impl.

**Stop-gap.** Lower-functionality v0 = direct addressing only, no roles, no broadcast, no `claim` type. Charter still met (issue #1300 is `query`/`info`).

## 6. Residual unknowns

- **Latency budget.** Pull latency = recall cadence; if some swarm interaction needs sub-second peer-message turnaround, push (Candidate b) or cooperative-poll wakeups become necessary. v1 instrument latency; revisit if user complaints.
- **Role resolution.** When `to_role=qa-agent` and three agents claim that role, who gets the message? v1 commitment: round-robin across role members; alternative is broadcast — needs decision before WS6.
- **Claim acceptance heuristics.** Recipient deciding whether to materialize a `claim` is not specified here — bridges to gap-12 (intent classifier) + gap-13 (peer-claim conflicts with own memory).
- **DM-style threading.** Reply-to relationships: a `query` and its `info` reply share a thread-id? v1: yes, store `in_reply_to=msg_id`. Sufficient for issue #1300 user story.
- **Privacy.** Cross-agent within tenant is allowed; the role-resolution case may inadvertently expose a fact across roles that shouldn't share. Lint check: peer-message `claim` payloads are scanned by gap-11 §3.3 sensitive-class taxonomy *at send time*, not just at memory time.

## 7. Touch-points

- **gap-04 multi-agent concurrency** — recipient inbox concurrent-write throttling (§3.4 cap).
- **gap-05 provenance enforcement** — peer-message provenance shape (§3.3).
- **gap-08 crash safety** — idempotency keys make `peer_message` retries safe.
- **gap-11 forgetting-as-safety** — a peer-message `claim` triggers a `remember` triggers gap-11 sensitivity scan; do the scan at send-time too.
- **gap-12 intent classifier** — `claim` materialization decision.
- **gap-13 contradiction resolution** — peer-claim contradicts recipient's existing memory; gap-13 §3.3 applies; peer-claim never auto-overrides recipient memory (defer-to-recipient policy).
- **WS6 (API)** — `peer_message`, `peer_message_pull`, `peer_message_status` verbs in MCP.
- **WS7 (migration)** — SCNS broker-DB cross-agent reads → peer_message inbox.
- **WS4 (eval)** — issue #1300 scenario as a benchmark task: agent A queries B, gets useful context, doesn't pollute A's memory.
