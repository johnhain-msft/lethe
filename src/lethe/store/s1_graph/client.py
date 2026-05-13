"""S1 client wrapper + backend protocol.

The :class:`GraphBackend` Protocol decouples the S1 surface from any one
backing graph store. Two implementations are provided:

- :class:`GraphitiBackend` — the production adapter, wraps
  :class:`graphiti_core.Graphiti`. Requires a Neo4j or FalkorDB instance to
  actually exercise; the import of ``graphiti_core`` is *eager* (module-level)
  so a broken or missing dependency fails at install time, never silently.
- :class:`_InMemoryGraphBackend` — a private, dependency-free stub used by
  the P1 smoke test (per facilitator-approved B1 in plan.md) and by the
  P2 ``remember`` unit tests. Not part of the public API.

P1 scope: ``S1Client.bootstrap()`` registers the baseline entity types from
:data:`BASELINE_ENTITY_TYPES` on the backend.

P2 scope: ``GraphBackend.add_episode`` lands on both backends so the
:mod:`lethe.api.remember` verb can persist episodes. The production
:class:`GraphitiBackend` synchronously wraps the async
:meth:`graphiti_core.Graphiti.add_episode` via per-call ``asyncio.run``
(plan §5 + sub-plan §8 Q2; long-lived event-loop refactor is a P7
transport-surface concern).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Protocol

# Eager import per facilitator note: a broken or missing graphiti-core must
# fail at `uv sync` rather than ship a no-Graphiti substrate that nobody
# notices until P2.
import graphiti_core  # noqa: F401  (eagerness is the point; symbol is unused)

from lethe.store.s1_graph.schema import BASELINE_ENTITY_TYPES


class GraphBackend(Protocol):
    """Minimum surface S1 needs from any backing graph store.

    Episode insert lands at P2 (write path). Fact extraction lands at P5
    with the dream-daemon.
    """

    def bootstrap_tenant(self, group_id: str) -> None:
        """Idempotently create per-tenant scope on the backend (group_id partition)."""
        ...

    def register_entity_type(self, type_name: str) -> None:
        """Register a typed-node label with the backend."""
        ...

    def health(self) -> bool:
        """Return ``True`` if the backend is reachable and ready for writes."""
        ...

    def add_episode(
        self,
        *,
        group_id: str,
        episode_id: str,
        body: str,
        source_uri: str,
        ts_recorded: str,
        intent: str,
    ) -> None:
        """Insert one episode under ``group_id`` (api §3.1 step 5).

        ``ts_recorded`` is an RFC 3339 string; backends parse it.
        ``intent`` is the gap-12 §3 classification class — backends MAY
        ignore it (graphiti-core does not consume it natively) but the
        Lethe-side ledger needs it on the wire for §7 emit-point parity.
        """
        ...


class _InMemoryGraphBackend:
    """Private in-memory backend — used by unit tests only.

    Not exported as part of the public API (leading underscore). Keeps
    the P1+P2 substrate exercisable without standing up Neo4j /
    FalkorDB.

    **Tenant-blind entity-type registry (P1 QA nit#1).** The
    ``_entity_types`` map keys per-tenant *sets* whose union is fed
    every newly bootstrapped tenant by :meth:`register_entity_type`
    (see method docstring for the rationale and contract). The episode
    store is per-tenant; only the type registry is tenant-blind.
    """

    def __init__(self) -> None:
        self._tenants: set[str] = set()
        self._entity_types: dict[str, set[str]] = {}
        self._episodes: dict[str, list[dict[str, str]]] = {}

    def bootstrap_tenant(self, group_id: str) -> None:
        self._tenants.add(group_id)
        self._entity_types.setdefault(group_id, set())
        self._episodes.setdefault(group_id, [])

    def register_entity_type(self, type_name: str) -> None:
        """Register ``type_name`` on every currently-bootstrapped tenant.

        **Invariant (P1 QA nit#1, locked decision #5).** The in-memory
        backend's entity-type registry is intentionally
        process-global / tenant-blind: entity types are *schema*, not
        *data*. Per-tenant isolation lives in the episode/edge stores
        (``_episodes`` here; per-tenant graph partitions in production),
        not in the type registry. Registering a new type therefore
        applies it to every bootstrapped tenant in this process.

        The production :class:`GraphitiBackend` does **not** inherit
        this property: the live graphiti adapter must register types
        per ``group_id`` because graphiti's storage substrate scopes
        type metadata by group. This in-memory shim's tenant-blind
        broadcast is a test-only convenience that mirrors the
        "registered globally on the backend" mental model without
        replaying the per-group registration plumbing.
        """
        for group_id in self._tenants:
            self._entity_types[group_id].add(type_name)

    def health(self) -> bool:
        return True

    def add_episode(
        self,
        *,
        group_id: str,
        episode_id: str,
        body: str,
        source_uri: str,
        ts_recorded: str,
        intent: str,
    ) -> None:
        if group_id not in self._tenants:
            # Mirror graphiti's "group_id must exist" contract — fail
            # loudly rather than silently create a tenant.
            raise ValueError(
                f"_InMemoryGraphBackend.add_episode: tenant {group_id!r} "
                "has not been bootstrapped"
            )
        self._episodes.setdefault(group_id, []).append(
            {
                "episode_id": episode_id,
                "body": body,
                "source_uri": source_uri,
                "ts_recorded": ts_recorded,
                "intent": intent,
            }
        )

    # Test helpers (private; not part of GraphBackend protocol).
    def _registered_types_for(self, group_id: str) -> frozenset[str]:
        return frozenset(self._entity_types.get(group_id, set()))

    def _episodes_for(self, group_id: str) -> tuple[dict[str, str], ...]:
        return tuple(self._episodes.get(group_id, []))


class GraphitiBackend:
    """Production adapter wrapping :class:`graphiti_core.Graphiti`.

    Defined at P1 (so import-time failures surface during ``uv sync``).
    P2 lands :meth:`add_episode`; ``bootstrap_tenant`` /
    ``register_entity_type`` / ``health`` remain wired in at P7 alongside
    the transport surface (sub-plan §8 Q1: live Neo4j/FalkorDB smoke is
    deferred to P7). Construction of the live client is lazy: first call
    that needs it instantiates :class:`graphiti_core.Graphiti` with the
    stored credentials.

    The async-to-sync bridge is ``asyncio.run`` per call (sub-plan §8 Q2
    approved); a long-lived event loop is a P7 concern.
    """

    def __init__(self, *, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._client: graphiti_core.Graphiti | None = None

    def _live_client(self) -> graphiti_core.Graphiti:
        if self._client is None:
            self._client = graphiti_core.Graphiti(
                self._uri, self._user, self._password
            )
        return self._client

    def bootstrap_tenant(self, group_id: str) -> None:  # pragma: no cover - P7
        raise NotImplementedError(
            "GraphitiBackend.bootstrap_tenant wires in at P7 alongside the "
            "live Neo4j/FalkorDB smoke (sub-plan §8 Q1)"
        )

    def register_entity_type(self, type_name: str) -> None:  # pragma: no cover - P7
        raise NotImplementedError(
            "GraphitiBackend.register_entity_type wires in at P7 alongside "
            "the live Neo4j/FalkorDB smoke (sub-plan §8 Q1)"
        )

    def health(self) -> bool:  # pragma: no cover - P7
        raise NotImplementedError(
            "GraphitiBackend.health wires in at P7 alongside the live "
            "Neo4j/FalkorDB smoke (sub-plan §8 Q1)"
        )

    def add_episode(  # pragma: no cover - exercised by integration tests at P7
        self,
        *,
        group_id: str,
        episode_id: str,
        body: str,
        source_uri: str,
        ts_recorded: str,
        intent: str,
    ) -> None:
        """Synchronously dispatch to :meth:`graphiti_core.Graphiti.add_episode`.

        ``ts_recorded`` is parsed with :meth:`datetime.fromisoformat`
        (Python 3.11+ accepts the trailing ``Z``). The ``uuid`` kwarg is
        passed verbatim so callers can preserve their own episode ids.
        ``intent`` is recorded in the ``source_description`` for now
        (graphiti-core has no first-class intent field); a typed-node
        edge will replace this at the P5 extraction phase.
        """
        client = self._live_client()
        reference_time = datetime.fromisoformat(ts_recorded)
        asyncio.run(
            client.add_episode(
                name=f"episode:{episode_id}",
                episode_body=body,
                source_description=f"{source_uri} | intent={intent}",
                reference_time=reference_time,
                group_id=group_id,
                uuid=episode_id,
            )
        )


class S1Client:
    """Thin façade over a :class:`GraphBackend`, scoped to a single tenant.

    The tenant scope is enforced by passing the tenant id as Graphiti
    ``group_id`` (composition §5.2 — "Tenant scope is a top-level partition
    on every store").
    """

    def __init__(self, backend: GraphBackend, *, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        self._backend = backend
        self._tenant_id = tenant_id
        self._bootstrapped = False

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def bootstrap(self) -> None:
        """Create per-tenant scope and register baseline entity types.

        Idempotent: safe to call repeatedly.
        """
        self._backend.bootstrap_tenant(self._tenant_id)
        for type_name in BASELINE_ENTITY_TYPES:
            self._backend.register_entity_type(type_name)
        self._bootstrapped = True

    def is_ready(self) -> bool:
        return self._bootstrapped and self._backend.health()
