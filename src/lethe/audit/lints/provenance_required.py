"""``provenance-required`` lint — gap-05 §3.5.

Composition §6 commits Lethe to "every fact in S1 has a non-null
episode-id; every recall response carries the episode-id". The
:func:`check_provenance_required` workhorse enforces the write-time
component of that commitment as an audit invariant: every S1 episode
materialized under a tenant **must** carry a non-empty ``source_uri``.

The runtime API for ``remember`` already refuses missing provenance with
:class:`lethe.runtime.provenance.ProvenanceRequired` (api §1.6 → 400);
this lint is the post-hoc defense-in-depth catching the out-of-band
write cases gap-05 §1 names (extraction bug, manual SQL, migration
script).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

__all__ = ["check_provenance_required", "lint_provenance_required"]


def check_provenance_required(
    *,
    tenant_id: str,
    episodes: Iterable[Mapping[str, str]],
) -> list[str]:
    """Return a finding for every episode whose ``source_uri`` is empty.

    Arguments:
        tenant_id: tenant whose episodes are being checked (for the
            finding text — the caller is responsible for scoping the
            iterable to this tenant).
        episodes: iterable of episode records. Each record is a mapping
            with at minimum an ``episode_id`` and a ``source_uri`` key
            (matches the shape stored by
            :class:`lethe.store.s1_graph._InMemoryGraphBackend` and the
            equivalent fields graphiti-core records natively).

    Returns:
        List of human-readable finding strings — empty when every
        episode has a non-empty ``source_uri``.
    """
    findings: list[str] = []
    for episode in episodes:
        episode_id = str(episode.get("episode_id", "<unknown>"))
        source_uri = episode.get("source_uri")
        if not source_uri:
            findings.append(
                f"tenant={tenant_id!r} episode={episode_id!r} has "
                "empty or null source_uri (gap-05 §3.5)"
            )
    return findings


def lint_provenance_required(tenant_root: Path) -> list[str]:
    """Registry wrapper conforming to :data:`lethe.audit.integrity.LintFn`.

    P2 has no production wiring that hands a live ``GraphitiBackend``
    into the audit CLI (sub-plan §8 Q1 defers live Neo4j/FalkorDB smoke
    to P7), so this wrapper enumerates an empty episode set and returns
    no findings. The workhorse :func:`check_provenance_required` is what
    tests exercise directly with an in-memory backend.

    ``tenant_root`` is accepted for protocol-shape parity and to leave
    room for a future on-disk episode snapshot; it is intentionally
    unused at P2.
    """
    del tenant_root  # P2: no on-disk episode source; P7 wires graphiti.
    return []
