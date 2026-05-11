"""S1 client wrapper + backend protocol.

The :class:`GraphBackend` Protocol decouples the S1 surface from any one
backing graph store. Two implementations are provided:

- :class:`GraphitiBackend` — the production adapter, wraps
  :class:`graphiti_core.Graphiti`. Requires a Neo4j or FalkorDB instance to
  actually exercise; the import of ``graphiti_core`` is *eager* (module-level)
  so a broken or missing dependency fails at install time, never silently.
- :class:`_InMemoryGraphBackend` — a private, dependency-free stub used by
  the P1 smoke test (per facilitator-approved B1 in plan.md). Not part of
  the public API.

P1 scope: ``S1Client.bootstrap()`` registers the baseline entity types from
:data:`BASELINE_ENTITY_TYPES` on the backend. Episode insert / fact extraction
land in P2 (write path).
"""

from __future__ import annotations

from typing import Protocol

# Eager import per facilitator note: a broken or missing graphiti-core must
# fail at `uv sync` rather than ship a no-Graphiti substrate that nobody
# notices until P2.
import graphiti_core  # noqa: F401  (eagerness is the point; symbol is unused)

from lethe.store.s1_graph.schema import BASELINE_ENTITY_TYPES


class GraphBackend(Protocol):
    """Minimum surface S1 needs from any backing graph store.

    Episode / fact / edge writes are out of scope for P1 — they land in P2
    when the write path is wired. P1 needs only bootstrap + type registration.
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


class _InMemoryGraphBackend:
    """Private in-memory backend — used by the P1 schema smoke test only.

    Not exported as part of the public API (leading underscore). Keeps the
    P1 substrate exercisable without standing up Neo4j / FalkorDB.
    """

    def __init__(self) -> None:
        self._tenants: set[str] = set()
        self._entity_types: dict[str, set[str]] = {}

    def bootstrap_tenant(self, group_id: str) -> None:
        self._tenants.add(group_id)
        self._entity_types.setdefault(group_id, set())

    def register_entity_type(self, type_name: str) -> None:
        for group_id in self._tenants:
            self._entity_types[group_id].add(type_name)

    def health(self) -> bool:
        return True

    # Test helpers (private; not part of GraphBackend protocol).
    def _registered_types_for(self, group_id: str) -> frozenset[str]:
        return frozenset(self._entity_types.get(group_id, set()))


class GraphitiBackend:
    """Production adapter wrapping :class:`graphiti_core.Graphiti`.

    Defined at P1 (so import-time failures surface during ``uv sync``); not
    exercised by the P1 unit test suite. An integration test marked
    ``@pytest.mark.integration`` will land alongside the P2 write path and
    is skipped by default (see ``pyproject.toml`` ``addopts``).
    """

    def __init__(self, *, uri: str, user: str, password: str) -> None:
        # Defer construction of the live client to the integration phase;
        # storing the connection params is enough for the P1 surface contract.
        self._uri = uri
        self._user = user
        self._password = password
        self._client: object | None = None

    def bootstrap_tenant(self, group_id: str) -> None:  # pragma: no cover - P2
        raise NotImplementedError("GraphitiBackend.bootstrap_tenant lands in P2")

    def register_entity_type(self, type_name: str) -> None:  # pragma: no cover - P2
        raise NotImplementedError("GraphitiBackend.register_entity_type lands in P2")

    def health(self) -> bool:  # pragma: no cover - P2
        raise NotImplementedError("GraphitiBackend.health lands in P2")


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
