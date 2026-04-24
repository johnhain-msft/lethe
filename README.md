# Lethe

A memory-runtime service for agent systems. Named for the river of forgetting: retention is a first-class operation, not an afterthought.

> **Status:** planning phase. No runtime code yet. See [`PLAN.md`](./PLAN.md) for the north-star doc and [`docs/`](./docs) for workstream artifacts as they land.

## Positioning

Lethe is the **runtime layer** — scoring, promotion/demotion, consolidation, intent-aware retrieval routing, MCP surface — that sits on top of proven substrates (Graphiti, etc.), not a new storage engine or a wrapper.

## Audience

Any MCP-speaking client. General-purpose service, not an SCNS-internal module.

## Layout

```
PLAN.md                    north-star planning doc
docs/
  00-charter.md            mission, scope, non-goals, license
  01-scns-memory-audit.md  current-state audit of SCNS memory
  01b-dream-daemon-design-note.md
  02-lit-review/           21 literature briefs
  02-synthesis.md          cross-cut of the 21 briefs
  ...                      WS3-WS8 land in later phases
scripts/eval/              eval harness (skeleton, later)
```

## License

TBD — see `docs/00-charter.md`.
