"""``provenance-resolvable`` lint — gap-05 §6.

Every ``source_uri`` recorded on an S1 episode must either:

1. **Resolve to a real S4 artifact** — the URI's scheme is ``s4a:`` or
   ``s4b:`` and the named relative path exists under the tenant's
   :class:`lethe.store.s4_md.S4Layout` (``tenant_root/s4a/`` or
   ``tenant_root/s4b/``); or
2. **Be an accepted non-S4 source** under the tenant's
   ``provenance_drop_count`` policy — gap-05 §6 explicitly allows
   external identifiers (``remember(source='external:rfc-1234')`` —
   "v1: yes, with a warning logged") and the recipient-side
   ``self_observation:`` / ``peer_message:`` / ``derived_from:`` URIs
   produced by gap-05 §3.3 + gap-10 §3.3 are likewise legitimate. Per
   the dev sub-plan §8 Q5 answer the existence of any
   ``provenance_drop_count`` row in ``tenant_config`` is the tenant's
   acknowledgment that "non-S4 provenance URIs are an accepted state
   here"; without the counter row, a non-S4 URI is a finding.

The lint also surfaces ``s4a:`` / ``s4b:`` URIs that point at paths
which do not exist on disk — the most common manifestation of the
gap-05 §1.2 "provenance drift" failure mode (artifact deleted out from
under the episode).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

from lethe.runtime.provenance import PROVENANCE_DROPPED_COUNT_KEY

__all__ = ["check_provenance_resolvable", "lint_provenance_resolvable"]


# Schemes the lint resolves against on-disk S4 artifacts. Anything else
# is treated as a non-S4 source URI (subject to the
# ``provenance_drop_count`` policy gate).
_S4A_PREFIX = "s4a:"
_S4B_PREFIX = "s4b:"


def _provenance_drops_accepted(s2_conn: sqlite3.Connection) -> bool:
    """Return ``True`` if the tenant has a ``provenance_drop_count`` row.

    The presence of the row (any value) is the tenant's policy signal
    that non-S4 source URIs are an accepted state. The value itself is
    forward-only telemetry per api §1.5 and is not consulted here.
    """
    cur = s2_conn.execute(
        "SELECT 1 FROM tenant_config WHERE key = ? LIMIT 1",
        (PROVENANCE_DROPPED_COUNT_KEY,),
    )
    return cur.fetchone() is not None


def _resolves_to_s4_artifact(
    source_uri: str, *, tenant_root: Path
) -> bool:
    """Resolve ``s4a:`` / ``s4b:`` URIs against the tenant's S4 layout.

    Returns ``False`` for any URI whose scheme is not ``s4a:`` /
    ``s4b:`` — non-S4 schemes are handled by the caller's
    ``provenance_drop_count`` gate, not by file-resolution.
    """
    if source_uri.startswith(_S4A_PREFIX):
        rel = source_uri[len(_S4A_PREFIX) :]
        if not rel:
            return False
        return (tenant_root / "s4a" / rel).exists()
    if source_uri.startswith(_S4B_PREFIX):
        rel = source_uri[len(_S4B_PREFIX) :]
        if not rel:
            return False
        return (tenant_root / "s4b" / rel).exists()
    return False


def check_provenance_resolvable(
    *,
    tenant_id: str,
    episodes: Iterable[Mapping[str, str]],
    tenant_root: Path,
    s2_conn: sqlite3.Connection,
) -> list[str]:
    """Return a finding for every episode whose ``source_uri`` cannot resolve.

    Arguments:
        tenant_id: tenant whose episodes are being checked.
        episodes: iterable of episode records (``episode_id`` +
            ``source_uri`` keys at minimum).
        tenant_root: path to ``<storage_root>/tenants/<tenant_id>/``;
            used to resolve ``s4a:`` / ``s4b:`` artifacts.
        s2_conn: open S2 SQLite connection (used to read
            ``tenant_config.provenance_drop_count``).

    Returns:
        Findings list — empty when every episode's source_uri either
        resolves to an S4 artifact or is accepted under the tenant's
        ``provenance_drop_count`` policy. Episodes whose ``source_uri``
        is empty are NOT flagged here — that case is the
        ``provenance-required`` lint's responsibility, and double-
        reporting would muddy the finding stream.
    """
    drops_accepted: bool | None = None
    findings: list[str] = []
    for episode in episodes:
        episode_id = str(episode.get("episode_id", "<unknown>"))
        source_uri = episode.get("source_uri")
        if not source_uri:
            continue  # handled by provenance-required.

        if source_uri.startswith((_S4A_PREFIX, _S4B_PREFIX)):
            if not _resolves_to_s4_artifact(
                source_uri, tenant_root=tenant_root
            ):
                findings.append(
                    f"tenant={tenant_id!r} episode={episode_id!r} "
                    f"source_uri={source_uri!r} points at a missing S4 "
                    "artifact (gap-05 §6)"
                )
            continue

        # Non-S4 scheme: accepted only if the tenant has opted into the
        # provenance_drop_count policy row (sub-plan §8 Q5).
        if drops_accepted is None:
            drops_accepted = _provenance_drops_accepted(s2_conn)
        if not drops_accepted:
            findings.append(
                f"tenant={tenant_id!r} episode={episode_id!r} "
                f"source_uri={source_uri!r} is a non-S4 URI without "
                f"a {PROVENANCE_DROPPED_COUNT_KEY!r} policy row in "
                "tenant_config (gap-05 §6)"
            )
    return findings


def lint_provenance_resolvable(tenant_root: Path) -> list[str]:
    """Registry wrapper conforming to :data:`lethe.audit.integrity.LintFn`.

    P2 has no production wiring that hands a live ``GraphitiBackend``
    into the audit CLI (sub-plan §8 Q1 defers live Neo4j/FalkorDB smoke
    to P7), so this wrapper enumerates an empty episode set and returns
    no findings. The workhorse :func:`check_provenance_resolvable` is
    what tests exercise directly with an in-memory backend.

    ``tenant_root`` is accepted for protocol-shape parity; the wrapper
    short-circuits before opening any S2 connection or touching
    ``tenant_root`` on disk.
    """
    del tenant_root  # P2: no on-disk episode source; P7 wires graphiti.
    return []
