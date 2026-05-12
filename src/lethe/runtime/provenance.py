"""Provenance envelope (api §1.5; gap-05).

Every fact returned by ``recall`` carries a provenance object whose
``source_uri`` is mandatory (api §1.6 → 400 ``provenance_required``).
This module owns:

- The :class:`ProvenanceEnvelope` dataclass + ``to_dict`` / ``from_dict``
  round-trip used by ``remember.py`` (commit 4) and the recall path
  (P3+).
- :func:`make` — refuses missing ``source_uri`` with
  :class:`ProvenanceRequired`.
- :func:`materialize_from_peer` — gap-05 §3.3 + gap-10 §3.3 helper that
  builds a recipient-side envelope from a peer-message envelope. The
  peer's ``episode_id`` is preserved as ``derived_from`` so the peer's
  identity is reachable but not laundered into the recipient's
  ``source_uri``.
- :func:`increment_dropped_counter` / :func:`read_dropped_counter` — the
  ``provenance_drop_count`` telemetry hook that api §1.5 names. Per
  facilitator dev sub-plan §8 open-question 5 the counter lives in the
  existing ``tenant_config`` key-value table (a dedicated metrics table
  is gap-06 / WS9 territory, not P2).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Final

# api §1.5 line 128: "provenance_drop_count counter incremented in S2 telemetry".
PROVENANCE_DROPPED_COUNT_KEY: Final[str] = "provenance_drop_count"


class ProvenanceError(Exception):
    """Base class for provenance-envelope errors."""


class ProvenanceRequired(ProvenanceError):
    """Raised when ``source_uri`` is missing (api §1.6 → 400 ``provenance_required``)."""


@dataclass(frozen=True)
class ProvenanceEnvelope:
    """Per-fact provenance object (api §1.5).

    Four mandatory fields (``episode_id``, ``source_uri``, ``agent_id``,
    ``recorded_at``) and two optional fields (``derived_from``,
    ``edit_history_id``). Construction goes through :func:`make` so the
    non-empty checks are centralized.
    """

    episode_id: str
    source_uri: str
    agent_id: str
    recorded_at: str
    derived_from: str | None = None
    edit_history_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "episode_id": self.episode_id,
            "source_uri": self.source_uri,
            "agent_id": self.agent_id,
            "recorded_at": self.recorded_at,
        }
        if self.derived_from is not None:
            out["derived_from"] = self.derived_from
        if self.edit_history_id is not None:
            out["edit_history_id"] = self.edit_history_id
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProvenanceEnvelope:
        # source_uri gets the dedicated error class so the caller can map
        # to api §1.6 400 ``provenance_required``; the other mandatory
        # fields collapse into the generic ProvenanceError.
        if not payload.get("source_uri"):
            raise ProvenanceRequired(
                "provenance.source_uri is mandatory (api §1.6)"
            )
        for required in ("episode_id", "agent_id", "recorded_at"):
            if not payload.get(required):
                raise ProvenanceError(f"provenance.{required} is mandatory")
        return cls(
            episode_id=str(payload["episode_id"]),
            source_uri=str(payload["source_uri"]),
            agent_id=str(payload["agent_id"]),
            recorded_at=str(payload["recorded_at"]),
            derived_from=(
                str(payload["derived_from"])
                if payload.get("derived_from") is not None
                else None
            ),
            edit_history_id=(
                str(payload["edit_history_id"])
                if payload.get("edit_history_id") is not None
                else None
            ),
        )


def make(
    *,
    episode_id: str,
    source_uri: str,
    agent_id: str,
    recorded_at: str,
    derived_from: str | None = None,
    edit_history_id: str | None = None,
) -> ProvenanceEnvelope:
    """Construct a validated envelope. Refuses missing ``source_uri``.

    Raises:
        ProvenanceRequired: ``source_uri`` is empty.
        ProvenanceError: any of ``episode_id``, ``agent_id``,
            ``recorded_at`` is empty.
    """
    if not source_uri:
        raise ProvenanceRequired(
            "provenance.source_uri is mandatory (api §1.6)"
        )
    if not episode_id or not agent_id or not recorded_at:
        raise ProvenanceError(
            "provenance episode_id / agent_id / recorded_at are all mandatory"
        )
    return ProvenanceEnvelope(
        episode_id=episode_id,
        source_uri=source_uri,
        agent_id=agent_id,
        recorded_at=recorded_at,
        derived_from=derived_from,
        edit_history_id=edit_history_id,
    )


def materialize_from_peer(
    peer: ProvenanceEnvelope,
    *,
    new_episode_id: str,
    recipient_agent_id: str,
    recorded_at: str,
) -> ProvenanceEnvelope:
    """Build a recipient-side envelope from a peer-message envelope.

    Per gap-05 §3.3 + gap-10 §3.3 the new envelope's ``episode_id``
    points at the recipient's *new* episode and ``derived_from`` carries
    the peer's episode-id. ``source_uri`` is set to
    ``"self_observation:{recipient_agent_id}"`` so the recipient's own
    identity owns the new fact while the peer-message linkage remains
    reachable through ``derived_from``.
    """
    return ProvenanceEnvelope(
        episode_id=new_episode_id,
        source_uri=f"self_observation:{recipient_agent_id}",
        agent_id=recipient_agent_id,
        recorded_at=recorded_at,
        derived_from=peer.episode_id,
        edit_history_id=None,
    )


def increment_dropped_counter(conn: sqlite3.Connection) -> int:
    """Bump the ``provenance_drop_count`` counter in ``tenant_config``.

    Returns the new value. Per api §1.5 the counter is incremented when a
    fact-edge with null provenance is dropped from a recall response; the
    storage location is the existing ``tenant_config`` key-value table
    (facilitator dev sub-plan §8 open-question 5).
    """
    cur = conn.execute(
        "SELECT value FROM tenant_config WHERE key = ?",
        (PROVENANCE_DROPPED_COUNT_KEY,),
    )
    row = cur.fetchone()
    current = int(row[0]) if row else 0
    new_value = current + 1
    conn.execute(
        "INSERT INTO tenant_config (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
        " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')",
        (PROVENANCE_DROPPED_COUNT_KEY, str(new_value)),
    )
    return new_value


def read_dropped_counter(conn: sqlite3.Connection) -> int:
    """Read the current ``provenance_drop_count``; ``0`` if unseeded."""
    cur = conn.execute(
        "SELECT value FROM tenant_config WHERE key = ?",
        (PROVENANCE_DROPPED_COUNT_KEY,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0
