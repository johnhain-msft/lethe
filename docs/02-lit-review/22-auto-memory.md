# 22 — auto-memory (`session-recall`)

**URL:** https://github.com/dezgit2025/auto-memory  **Type:** open-source CLI (thin adapter over a host session store)  **Fetched:** 2026-05-01
**Author:** Desi Villanueva (`dezgit2025`) — personal tool, sibling-product / pattern-reference quality.
**Install:** `pip install auto-memory` (also `uv tool install` / `pipx`). Python 3.10+. MIT. v0.3.0 (2026-04-30).

## Problem framing
> "Zero-dependency CLI that turns Copilot CLI's local SQLite into instant recall — no MCP server, no hooks, read-only, schema-checked. ~50 tokens per prompt." (README, header)

The framing is the **single-user coding-agent compaction tax**. The README quantifies the symptom: a nominal 200K-token context window degrades past ~60% ("lost in the middle"); subtracting MCP tools (~65K) and instruction files (~10K) leaves ~45K of usable working context before quality drops; the author measured "**68 minutes per day** lost to re-orientation after compactions and new sessions" (README §"The Problem"). Compaction itself is the failure mode: every 20–30 turns the agent must either ignore the warning or run `/compact` and "lobotomize itself into a tidy two-paragraph summary" (README §"The Compaction Tax").

auto-memory's response is narrow on purpose: don't fix memory, just give the agent a **read verb over its own host's session store** so it can re-orient in ~50 tokens instead of re-asking the user.

## Architecture
Adapter pattern, not a memory system. ~1,900 lines of Python, **zero runtime dependencies** (stdlib only — README badge + CHANGELOG v0.1.0 "Zero runtime dependencies (stdlib only)").

- **What it reads.** Copilot CLI's local SQLite at `~/.copilot/session-store.db` (the same store the host CLI already maintains for cross-session history). Read-only.
- **Schema-checking.** Every CLI entry point validates the schema before querying (CHANGELOG v0.1.0: "Schema validation on every CLI entry point"). This is the cost of being pinned to a host's private schema: when the host bumps it, auto-memory must follow. The repo ships a separate `UPGRADE-COPILOT-CLI.md` for that case (README "Files an agent should read in order").
- **WAL-safe access** with exponential backoff (CHANGELOG v0.1.0) — the host may be writing concurrently; the adapter must not block or corrupt.
- **Multi-backend (opt-in).** v0.2.0 added a pluggable `providers/` layer: Copilot CLI is the default and trusted-first-party; VS Code, JetBrains, Neovim are opt-in via `SESSION_RECALL_ENABLE_FILE_BACKENDS=1`, tagged `_trust_level: untrusted_third_party`, and wrapped in **sentinel fences** to defang prompt injection from third-party JSONL (CHANGELOG v0.2.0).
- **Symlink-escape and JSONL-bomb hardening** (CHANGELOG v0.2.0): `is_under_root` guard at every glob site; `iter_jsonl_bounded` caps line size and count.

The architectural bet: every coding agent already maintains a session log; the **adapter** is the cheapest possible path to recall. No MCP server. No hooks. No daemon.

## Scoring / retrieval math — N/A
auto-memory **does no scoring**. It is a query layer over an already-ordered SQLite store. There are no embeddings, no BM25 weights, no graph distance, no rerank pass, no fusion constants. This is a deliberate scope choice: scoring belongs to whatever indexed the source data (Copilot CLI's own FTS5 in this case — v0.1.0 CHANGELOG mentions "FTS5 query sanitization (7 crash bugs fixed)", confirming search delegates to the host's FTS5).

The retrieval primitives surfaced are flat enumeration verbs over the host store:
- `list` — recent sessions, default limit 10 (CHANGELOG v0.2.0: limit reverted from 50 to 10 to "preserve ~50 token Tier-1 budget").
- `search` — FTS5 over session content, returning a 250-char `excerpt` field (CHANGELOG v0.2.0: down from 500-char `content` to "restore Tier-2 ~200 token budget").
- `show`, `files`, `checkpoints` — dereference a single session.
- Filters: `--days N` lookback (default 30 for SQLite, 5 for file backends), `--provider <name>` to scope to a backend.

Token-budget discipline is enforced in CI (CHANGELOG v0.2.0: "Token budget regression tests — list/search/files byte budgets enforced in CI"). This is the most interesting math-adjacent claim: the retrieval surface is **engineered to a token budget**, not to a relevance score.

## API surface
**CLI** (single binary, agent-invoked):
```
session-recall list [--limit N] [--days N] [--json]
session-recall search "<query>" [--days N] [--json]
session-recall show <session-id>
session-recall files <session-id>
session-recall checkpoints <session-id>
session-recall repos                      # v0.2.0
session-recall health [--provider <name>] # v0.3.0: per-provider dimensions
session-recall schema-check
session-recall --version                  # v0.3.0
```

The intended invoker is the agent itself, not the human. The README's headline example is a prompt block to paste into agent instructions: *"Use `session-recall list --json --limit 10` to show my last 10 sessions. Display: date, time, full session_id, summary, branch, turns count, project folder."* (README §"Example: Remember Your Last 10 Sessions"). Output: a 10-row table the agent reads in ~50 tokens.

**No MCP server. No SDK. No daemon.** The agent shells out, parses JSON, moves on.

## Scale claims + evidence
- **Token budget:** "~50 tokens per prompt" (README header) for the canonical `list --limit 10 --json` case; enforced by CI regression tests (CHANGELOG v0.2.0).
- **Tests:** "tests-90 passed" badge in README header; CHANGELOG v0.3.0 reports "26 new tests (13 unit + 7 integration + 6 E2E) — 197 total" — README badge appears stale relative to CHANGELOG.
- **Productivity claim:** "68 minutes per day" of re-orientation eliminated, self-measured over a week (README §"The Problem"). N=1; not a benchmark.
- **Scope ceiling:** single-user, single-host, single SQLite file. No clustering, no replication, no remote access. The README explicitly markets this as a feature ("zero dependencies", "no MCP server", "read-only").

No published latency numbers, no corpus-size benchmarks, no comparison against MemGPT/Letta/Graphiti — and the README is honest that this is not the same product class.

## Documented limits
- **Read-only.** No write path. The agent cannot tell auto-memory "remember this." Writes happen via the host CLI's existing turn logging.
- **Single-user / single-host.** SQLite + local filesystem; no tenancy model.
- **Backend-pinned to a specific session-store schema.** The Copilot CLI provider is trusted-first-party and breaks if Copilot CLI changes its schema; `UPGRADE-COPILOT-CLI.md` is a manual revalidation step.
- **No consolidation.** Sessions accumulate forever; pruning is the host's responsibility, not auto-memory's.
- **No cross-session graph.** You can list and full-text search sessions; you cannot ask "what entity links these three sessions" — there are no entities.
- **No provenance enforcement.** auto-memory inherits whatever the host store records; if the host doesn't record provenance, auto-memory can't synthesize it.
- **WSL2 setup gotcha.** On Windows 11 + WSL2, the user must run `/experimental` → enable `SESSION_STORE` inside Copilot CLI before `~/.copilot/session-store.db` exists (README §"Windows (WSL2) — Enable the Session Store").
- **File-backed providers are untrusted.** VS Code / JetBrains / Neovim JSONL is wrapped in sentinel fences (CHANGELOG v0.2.0); auto-memory assumes those streams may contain prompt injection.

## Relation to Lethe
auto-memory is a **different product class** from Lethe. It is not a substrate candidate, not a runtime-tier competitor, and not a comparable memory system. Reasons it still matters:

1. **Validates the recall verb as a product surface.** A standalone, single-purpose, ~1,900-line tool whose entire job is `recall` — and it ships, it has tests, it has a CHANGELOG with thoughtful security work — is evidence that **the recall verb alone is worth packaging**. Lethe's MCP `recall` tool serves a richer underlying model, but the demand signal is the same.
2. **Articulates the compaction tax.** The README's "compaction tax" framing — every `/compact` makes the agent dumber, which burns more tokens, which triggers the next compaction sooner — is the clearest articulation of the symptom Lethe is also addressing for the SCNS-class user. Worth borrowing the phrase.
3. **Adapter-over-host-store is a deployment pattern Lethe could re-front.** auto-memory's architecture (thin Python CLI over a single SQLite file) is exactly the shape that could, in a future world, be re-fronted onto Lethe's read API as a third-party client. Not a roadmap item; a hint that Lethe's read surface should be cheap to wrap.
4. **Token-budgeted CLI output is a discipline Lethe should match.** auto-memory enforces "~50 tokens per `list --json --limit 10`" via CI regression tests. Lethe's MCP tools should adopt the same per-tool token budget, with regression tests, before WS6 ships.
5. **Trust-tagging untrusted file sources** (`_trust_level: trusted_first_party | untrusted_third_party`, sentinel fences) is a small pattern worth lifting into Lethe's provenance layer (gap-05) when it ingests external JSONL.

## Gaps / hand-waves it introduces
- **Single-user assumption is hard-coded.** No tenancy, no isolation, no concurrent-write story (because there are no writes). Reinforces Lethe's gap-04 (multi-tenant) and gap-10 (concurrency) as the SCNS-lineage problems Lethe inherits and auto-memory does not solve.
- **No provenance enforcement.** auto-memory passes through whatever the host store records; this is fine for its scope but reinforces Lethe's gap-05 differentiation point.
- **Backend lock-in to a private schema.** Pinning to Copilot CLI's `~/.copilot/session-store.db` is brittle by design; the trade is "ships today, breaks on host upgrade." Lethe's read API should be the *opposite* contract (versioned, public, stable) so future thin clients don't carry this risk.
- **No write-side semantics at all.** auto-memory is silent on `remember`, promotion, demotion, contradiction, decay. This is correct for its scope; cited here only to prevent the temptation to read it as a memory system.
- **N=1 productivity evidence.** The "68 minutes/day" claim is self-measured over one week by the author; useful as motivation, not as evaluation.
