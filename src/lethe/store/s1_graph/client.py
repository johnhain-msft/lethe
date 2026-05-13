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
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Eager import per facilitator note: a broken or missing graphiti-core must
# fail at `uv sync` rather than ship a no-Graphiti substrate that nobody
# notices until P2.
import graphiti_core  # noqa: F401  (eagerness is the point; symbol is unused)

from lethe.store.s1_graph.schema import BASELINE_ENTITY_TYPES


@dataclass(frozen=True)
class EpisodeRecord:
    """One episode as surfaced to the consolidate-loop extract phase (P4 C5).

    Fields verbatim-mirror :meth:`GraphBackend.add_episode` kwargs so
    materializing one from the backend's stored shape is a 5-field copy.

    Frozen dataclass at the Protocol layer mirrors the
    :class:`~lethe.runtime.classifier.intent_classifier.LLMClassification`
    posture (Protocol-return frozen dataclasses; immutable + mypy-strict
    friendly + ``dataclasses.FrozenInstanceError`` semantics on accidental
    mutation).
    """

    episode_id: str
    body: str
    source_uri: str
    ts_recorded: str
    intent: str


@dataclass(frozen=True)
class FactRecord:
    """One fact as surfaced to the consolidate-loop demote/invalidate +
    reconciler phases (P4 C6 — sub-plan §k.2 + IMPLEMENT 6 amendment A1).

    Bi-temporal stamps live here on S1; ``valid_to`` is ``None`` while the
    fact is current and gets set to the demote/invalidate timestamp via
    :meth:`GraphBackend.set_fact_valid_to`. The reconciler reads facts
    via :meth:`GraphBackend.iter_facts_with_valid_to` to find S1
    ``valid_to ≠ NULL`` rows that have no covering ``promotion_flags``
    entry (composition §5 row 7 — A2 orphan definition includes
    ``backfilled`` to avoid infinite re-backfill).

    Frozen dataclass mirrors :class:`EpisodeRecord` (same Protocol-layer
    posture, same mypy-strict + ``FrozenInstanceError`` semantics).
    Public — re-exported from :mod:`lethe.runtime.consolidate` for the
    phase modules to type their reconciler return values without
    reaching into the store layer.
    """

    fact_id: str
    group_id: str
    valid_from: str
    valid_to: str | None


class GraphBackend(Protocol):
    """Minimum surface S1 needs from any backing graph store.

    Episode insert lands at P2 (write path). Episode read for the
    consolidate extract phase lands at P4 commit 5 via
    :meth:`episodes_since`. Fact extraction lands at P5 with the
    dream-daemon.
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

    def episodes_since(
        self,
        *,
        group_id: str,
        since_cursor: str | None,
    ) -> Iterable[EpisodeRecord]:
        """Yield episodes stored after ``since_cursor`` (P4 commit 5 — extract).

        ``since_cursor`` is the **composite cursor** persisted in
        ``consolidation_state.last_run_cursor`` of the form
        ``f"{ts_recorded}\\t{episode_id}"`` (tab-separated). When ``None``
        every episode in the tenant is yielded (first run after migration).
        Otherwise the boundary semantics are STRICT inequality: an episode
        is yielded iff
        ``f"{episode.ts_recorded}\\t{episode.episode_id}" > since_cursor``
        in lexicographic compare. The composite key disambiguates episodes
        that share a ``ts_recorded`` value (otherwise the second of two
        same-timestamp episodes would be permanently skipped).

        Returned episodes are sorted ASC by
        ``(ts_recorded, episode_id)`` tuple — the same order the cursor
        compares against. The caller (``runtime.consolidate.extract``)
        relies on this ordering to compute the next cursor as the LAST
        materialized element after the loop, not ``max()`` over the list.
        """
        ...

    def set_fact_valid_to(
        self,
        *,
        group_id: str,
        fact_id: str,
        valid_to: str,
    ) -> None:
        """Set ``valid_to`` on one S1 fact (P4 C6 — demote / invalidate phases).

        ``valid_to`` is an RFC 3339 timestamp string (the bi-temporal
        end-of-validity stamp; composition §1 row 48 + scoring §6).
        Calling on an already-invalidated fact OVERWRITES the prior
        ``valid_to`` (re-invalidate semantics; the audit trail of the
        prior stamp lives in the S5 consolidation log, not S1).

        Per IMPLEMENT 6 amendment A10: raises :class:`KeyError` for an
        unbootstrapped ``group_id`` AND for a missing ``fact_id`` within
        a bootstrapped tenant. The write surface is STRICT (callers must
        seed facts before invalidating them); contrast
        :meth:`iter_facts_with_valid_to` which returns an empty
        iterable for an unbootstrapped tenant.
        """
        ...

    def iter_facts_with_valid_to(
        self,
        *,
        group_id: str,
    ) -> Iterable[FactRecord]:
        """Yield S1 facts under ``group_id`` whose ``valid_to`` is non-NULL.

        Used by the consolidate-loop reconciler (composition §5 row 7 +
        IMPLEMENT 6 A2) to find S1 facts that have been invalidated but
        lack a covering ``promotion_flags`` row (tier ∈ {demoted,
        invalidated, backfilled}). The reconciler backfills a
        ``tier='backfilled'`` row + S5 entry for each such orphan.

        Per IMPLEMENT 6 amendment A10: returns an empty iterable for an
        unbootstrapped ``group_id`` (the read surface is permissive —
        only :meth:`set_fact_valid_to` raises). Yields records sorted by
        ``fact_id`` ASC for determinism.
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
        # P4 C6 (sub-plan §k.2 + IMPLEMENT 6 A1 + B-4): per-tenant facts
        # store so set_fact_valid_to + iter_facts_with_valid_to mutate
        # real state (not just record-the-call). Mirrors _episodes
        # invariant: keyed by group_id, populated lazily on bootstrap +
        # on _seed_fact (test-only helper).
        self._facts: dict[str, dict[str, FactRecord]] = {}

    def bootstrap_tenant(self, group_id: str) -> None:
        self._tenants.add(group_id)
        self._entity_types.setdefault(group_id, set())
        self._episodes.setdefault(group_id, [])
        self._facts.setdefault(group_id, {})

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
                f"_InMemoryGraphBackend.add_episode: tenant {group_id!r} has not been bootstrapped"
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

    def episodes_since(
        self,
        *,
        group_id: str,
        since_cursor: str | None,
    ) -> Iterable[EpisodeRecord]:
        """Materialize :class:`EpisodeRecord` instances strictly after ``since_cursor``.

        Sort key + cursor compare are
        ``f"{ts_recorded}\\t{episode_id}"`` (composite cursor — see
        :meth:`GraphBackend.episodes_since`). Returns a list (eagerly
        materialized) so callers can compute ``len()`` and ``[-1]``
        without re-iterating.
        """
        records = [
            EpisodeRecord(
                episode_id=ep["episode_id"],
                body=ep["body"],
                source_uri=ep["source_uri"],
                ts_recorded=ep["ts_recorded"],
                intent=ep["intent"],
            )
            for ep in self._episodes.get(group_id, [])
        ]
        records.sort(key=lambda r: (r.ts_recorded, r.episode_id))
        if since_cursor is None:
            return records
        return [r for r in records if f"{r.ts_recorded}\t{r.episode_id}" > since_cursor]

    # P4 C6 — fact surface for demote / invalidate / reconciler.

    def _seed_fact(
        self,
        *,
        group_id: str,
        fact_id: str,
        valid_from: str,
        valid_to: str | None = None,
    ) -> None:
        """Test-only helper to populate the per-tenant facts dict (P4 C6).

        Mirrors :meth:`_episodes_for` and :meth:`_registered_types_for` —
        leading-underscore signals "not on the GraphBackend Protocol;
        unit-test substrate only". Callers must bootstrap the tenant
        first (raises :class:`ValueError` otherwise — same loud-fail
        posture as :meth:`add_episode`).
        """
        if group_id not in self._tenants:
            raise ValueError(
                f"_InMemoryGraphBackend._seed_fact: tenant {group_id!r} has not been bootstrapped"
            )
        self._facts.setdefault(group_id, {})[fact_id] = FactRecord(
            fact_id=fact_id,
            group_id=group_id,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def set_fact_valid_to(
        self,
        *,
        group_id: str,
        fact_id: str,
        valid_to: str,
    ) -> None:
        """Set ``valid_to`` on a seeded fact; raises :class:`KeyError` otherwise.

        Per IMPLEMENT 6 amendment A10: KeyError for an unbootstrapped
        ``group_id`` AND for a missing ``fact_id`` within a bootstrapped
        tenant. Re-invalidate (calling on an already-stamped fact)
        OVERWRITES the prior ``valid_to``; the audit trail of the prior
        stamp lives in the S5 consolidation log, not S1.

        Frozen-dataclass replacement: builds a new :class:`FactRecord`
        with the updated ``valid_to`` and swaps it into the dict.
        """
        if group_id not in self._facts:
            raise KeyError(
                f"_InMemoryGraphBackend.set_fact_valid_to: group_id {group_id!r} not bootstrapped"
            )
        if fact_id not in self._facts[group_id]:
            raise KeyError(
                f"_InMemoryGraphBackend.set_fact_valid_to: fact_id "
                f"{fact_id!r} not seeded for group_id {group_id!r}"
            )
        old = self._facts[group_id][fact_id]
        self._facts[group_id][fact_id] = FactRecord(
            fact_id=old.fact_id,
            group_id=old.group_id,
            valid_from=old.valid_from,
            valid_to=valid_to,
        )

    def iter_facts_with_valid_to(
        self,
        *,
        group_id: str,
    ) -> Iterable[FactRecord]:
        """Yield facts under ``group_id`` whose ``valid_to`` is non-NULL.

        Per IMPLEMENT 6 amendment A10: returns an empty list for an
        unbootstrapped ``group_id`` (read surface is permissive).
        Sorted by ``fact_id`` ASC for deterministic reconciler output.
        """
        records = [r for r in self._facts.get(group_id, {}).values() if r.valid_to is not None]
        records.sort(key=lambda r: r.fact_id)
        return records


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
            self._client = graphiti_core.Graphiti(self._uri, self._user, self._password)
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

    def episodes_since(  # pragma: no cover - P7
        self,
        *,
        group_id: str,
        since_cursor: str | None,
    ) -> Iterable[EpisodeRecord]:
        raise NotImplementedError(
            "GraphitiBackend.episodes_since wires in at P7 alongside the "
            "live Neo4j/FalkorDB read path (P4 commit 5 — sub-plan §j.1)"
        )

    def set_fact_valid_to(  # pragma: no cover - P7
        self,
        *,
        group_id: str,
        fact_id: str,
        valid_to: str,
    ) -> None:
        raise NotImplementedError(
            "GraphitiBackend.set_fact_valid_to wires in at P7 alongside the "
            "live Neo4j/FalkorDB write path (P4 commit 6 — sub-plan §k.1)"
        )

    def iter_facts_with_valid_to(  # pragma: no cover - P7
        self,
        *,
        group_id: str,
    ) -> Iterable[FactRecord]:
        raise NotImplementedError(
            "GraphitiBackend.iter_facts_with_valid_to wires in at P7 alongside "
            "the live Neo4j/FalkorDB read path (P4 commit 6 — IMPLEMENT 6 A1)"
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

    def episodes_since(
        self,
        *,
        since_cursor: str | None,
    ) -> Iterable[EpisodeRecord]:
        """Yield this tenant's episodes strictly after ``since_cursor``.

        Façade over :meth:`GraphBackend.episodes_since` that pins
        ``group_id`` to ``self._tenant_id``. Per A3 (P4 C5 amendment),
        this exists so callers don't need to thread the
        tenant_id/group_id consistency by hand.
        """
        return self._backend.episodes_since(
            group_id=self._tenant_id,
            since_cursor=since_cursor,
        )

    def set_fact_valid_to(
        self,
        *,
        fact_id: str,
        valid_to: str,
    ) -> None:
        """Set ``valid_to`` on one of this tenant's S1 facts (P4 C6).

        Façade over :meth:`GraphBackend.set_fact_valid_to` that pins
        ``group_id`` to ``self._tenant_id``. Mirrors the C5 façade
        pattern (sub-plan §k.1 + IMPLEMENT 6 A1) so phase code
        (``runtime.consolidate.demote`` / ``invalidate``) doesn't thread
        the tenant_id/group_id consistency by hand.
        """
        self._backend.set_fact_valid_to(
            group_id=self._tenant_id,
            fact_id=fact_id,
            valid_to=valid_to,
        )

    def iter_facts_with_valid_to(self) -> Iterable[FactRecord]:
        """Yield this tenant's S1 facts whose ``valid_to`` is non-NULL.

        Façade over :meth:`GraphBackend.iter_facts_with_valid_to` that
        pins ``group_id`` to ``self._tenant_id``. Used by the
        consolidate-loop reconciler (sub-plan §k.6 + IMPLEMENT 6 A1+A2)
        to find S1 facts that have been invalidated but lack a covering
        ``promotion_flags`` row of tier ∈ {demoted, invalidated,
        backfilled}.
        """
        return self._backend.iter_facts_with_valid_to(group_id=self._tenant_id)
