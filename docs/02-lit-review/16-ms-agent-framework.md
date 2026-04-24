# 16 — Microsoft Agent Framework

**URL:** https://github.com/microsoft/agent-framework  **Type:** open-source multi-language SDK (Python + .NET)  **Fetched:** 2026-04-23
**Docs:** https://learn.microsoft.com/agent-framework/
**Packages:** `agent-framework` (PyPI), `Microsoft.Agents.AI` (NuGet).
**Lineage:** successor to Semantic Kernel + AutoGen (migration guides exist for both).
**License:** MIT.

## Problem framing
Microsoft's unified SDK for building, orchestrating, and deploying AI agents — single-agent to graph-based multi-agent workflows. Memory, in this framing, is **not a first-class subsystem**; it is **context-provider plumbing** attached to an agent. The explicit Microsoft pattern: "RAG capabilities to agents easily by adding AI Context Providers to the agent." Memory, in other words, is solved by plugging in a `TextSearchProvider` or similar, with the store being external (Azure AI Search, vector store, etc.).

## Architecture
Three relevant constructs:

| Construct | Role |
|---|---|
| **Agent** (`ChatClientAgent` / `AIAgent`) | The addressable entity; built over an LLM chat client. |
| **AIContextProviders** | Pluggable RAG providers attached at agent-construction time. `TextSearchProvider` is the shipped implementation. |
| **Workflows** | Graph-based orchestration over agents + deterministic functions, with streaming, checkpointing, human-in-the-loop, time-travel. |

No "memory block", no "archival memory", no "core memory". The agent's **durable state is an external store**; the context provider is just the bridge.

## Scoring / retrieval math
`TextSearchProvider` is scoring-agnostic — it delegates to a developer-supplied `SearchAdapter(query, cancellationToken)` that returns `TextSearchResult[]` with optional `SourceName` and `SourceLink`. The provider then injects results as a context block with the pattern:

> `## Additional Context\nConsider the following information from source documents when responding to the user: {results}` + citations instruction.

So: **no built-in retrieval math.** MS provides the *shape of the insertion*, not the *ranking function*.

## API surface
```csharp
// .NET — attaching a context provider to an agent
AIAgent agent = azureOpenAIClient
    .GetChatClient(deploymentName)
    .AsAIAgent(new ChatClientAgentOptions {
        ChatOptions = new() { Instructions = "…" },
        AIContextProviders = [ new TextSearchProvider(SearchAdapter, textSearchOptions) ]
    });
```

`TextSearchProviderOptions` controls *when* search runs:
- `SearchTime = BeforeAIInvoke` — search prepended to every model invocation (default).
- `SearchTime = OnDemand` — agent exposes a `Search` function tool, calls it when it wants.
- `RecentMessageMemoryLimit` — how many recent user messages to use as the implicit search query.
- `RecentMessageRolesIncluded` — filter roles considered for query construction.

Python package `agent-framework` mirrors the same shape. Also integrates **Semantic Kernel's VectorStore collections** for richer RAG.

Graph workflows, DevUI, AF Labs (experimental benchmarking / RL) round out the framework, but are not memory-specific.

## Scale claims + evidence
Not applicable to memory specifically: the framework's scale story is orchestration (checkpointing, time-travel, multi-agent graphs) + Microsoft's platform story (Azure AI Search as the scale-out backing store). No documented limits on context-provider throughput — the bottleneck is the store the developer plugs in.

## Documented limits
- **No first-class memory model.** Context providers are RAG wrappers; no `memory_blocks`, no `promote/forget`, no lifecycle.
- **No consolidation / background agents.** No equivalent to Letta sleep-time (brief 15).
- **No temporal / bi-temporal model.** Unlike Graphiti (brief 12), MS Agent Framework has no concept of "as-of-when" retrieval.
- **`TextSearchProvider` is a single-shot RAG.** Either prepend-before-invoke or tool-call on demand. No multi-hop, no graph traversal built in.
- **Citations are optional** and the framework trusts the adapter to return them; no provenance enforcement.

## Relation to Lethe
Strategic rather than technical. MS Agent Framework is **the integration target** for enterprise Lethe deployments. Implications:

1. **Context-provider interface is Lethe's enterprise adapter surface.** Lethe should ship (or scope) an `AIContextProvider` implementation that calls Lethe's MCP search. That's how Lethe slots into MS-stack agents without asking developers to switch frameworks.
2. **MS's omission is Lethe's opportunity.** Memory as "a RAG plugin" is not the durable-agent-state model Letta and Graphiti have converged on. Lethe is the durable-state layer; MS Agent Framework gives us the agent-orchestration + workflow layer we don't need to build.
3. **Workflow checkpointing + time-travel align with bi-temporal retrieval.** Graphiti (brief 12) lets you ask "what did the graph know at time T"; MS workflows let you replay execution from checkpoint T. Composing the two supports strong debugging/auditing stories.
4. **Semantic Kernel's `IMemoryStore` is a legacy shape.** The migration guide from Semantic Kernel suggests the new path is VectorStore + context providers. Lethe shouldn't target `IMemoryStore`; target `AIContextProvider`.
5. **.NET + Python symmetry.** Lethe is TypeScript-primary (SCNS lineage). If Lethe wants .NET reach, going through MS Agent Framework is cheaper than publishing a .NET port of the whole system.
6. **Observability.** MS AF has "Built-in Open…" (OpenTelemetry) — Lethe's MCP surface should emit OTEL spans that MS AF can consume, not a bespoke format.

## Gaps / hand-waves it introduces
- **No memory-lifecycle vocabulary at all.** Remember / recall / promote / forget do not exist as concepts; it's all "search the store".
- **No cross-agent memory sharing primitive.** Contrast with Letta's shared blocks (brief 15).
- **No enforced provenance.** `SourceName` / `SourceLink` are optional strings on results; nothing guarantees traceability.
- **Opinionated about orchestration, unopinionated about memory.** The framework has strong opinions on graph workflows and weak ones on storage. Lethe must supply the missing opinions.
- **`RecentMessageMemoryLimit` is a crude proxy for conversation-window retrieval.** Literally "last N user messages" — ignores turn semantics, topic shifts, and tool-call intent.
- **No async / background jobs for memory maintenance.** Workflow time-travel is about execution, not about memory consolidation.
- **No benchmark story** (e.g., no LongMemEval numbers from MS AF itself).
