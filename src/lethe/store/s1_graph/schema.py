"""S1 schema definitions: entity-type registry, episode shape, bi-temporal stamps.

Backend-agnostic. The :class:`GraphBackend` adapters in :mod:`.client` consume
these declarations to materialize whatever the underlying graph store needs.

Source: ``docs/03-composition-design.md`` §2 row 1 — "typed entity nodes,
typed edges with (valid_from, valid_to, recorded_at), episodes (raw observation
payloads), provenance edges from fact → episode."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BiTemporalStamp:
    """Bi-temporal stamp carried by every fact edge.

    ``valid_from`` / ``valid_to`` mark domain time (when the fact held in the
    world). ``recorded_at`` marks system time (when Lethe learned of the fact).
    The ``valid_to is None`` case denotes an open interval ("still valid").
    """

    valid_from: datetime
    recorded_at: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError(
                f"valid_to ({self.valid_to.isoformat()}) precedes "
                f"valid_from ({self.valid_from.isoformat()})"
            )


@dataclass(frozen=True)
class EpisodeShape:
    """Raw observation payload as recorded into S1.

    P1 scope: the structural envelope only. Concrete write-path validation
    (provenance enforcement, idempotency-key handling) lands in P2 (gap-05 +
    invariant I-5).
    """

    episode_id: str
    payload: str
    source_uri: str
    agent_id: str
    recorded_at: datetime


# Baseline entity-type registry. Derived directly from composition §2 row 1
# ("typed entity nodes, ... episodes, ... provenance edges"). Adapters
# (e.g. Graphiti) translate these into backend-native type declarations.
BASELINE_ENTITY_TYPES: tuple[str, ...] = (
    "Entity",
    "Episode",
    "ProvenanceEdge",
)


def now_recorded_at() -> datetime:
    """Return a UTC ``datetime`` suitable for the ``recorded_at`` slot.

    Centralized so test code can monkey-patch one symbol when it needs
    deterministic timestamps.
    """
    return datetime.now(UTC)


def stamp(
    valid_from: datetime,
    valid_to: datetime | None = None,
    recorded_at: datetime | None = None,
) -> BiTemporalStamp:
    """Construct a :class:`BiTemporalStamp`, defaulting ``recorded_at`` to now."""
    return BiTemporalStamp(
        valid_from=valid_from,
        valid_to=valid_to,
        recorded_at=recorded_at if recorded_at is not None else now_recorded_at(),
    )


__all__ = [
    "BASELINE_ENTITY_TYPES",
    "BiTemporalStamp",
    "EpisodeShape",
    "now_recorded_at",
    "stamp",
]
