"""Provenance envelope + dropped-counter coverage (api §1.5; gap-05).

Covers:

- Envelope round-trip via ``to_dict`` / ``from_dict`` preserves every
  field including the optional ``derived_from`` and ``edit_history_id``.
- ``make`` and ``from_dict`` refuse missing ``source_uri`` with the
  dedicated :class:`ProvenanceRequired` (api §1.6 → 400).
- Other mandatory fields (``episode_id``, ``agent_id``, ``recorded_at``)
  raise the generic :class:`ProvenanceError`.
- :func:`materialize_from_peer` preserves the peer's ``episode_id`` as
  ``derived_from`` and points ``source_uri`` at ``self_observation``.
- The ``provenance_drop_count`` counter seeds, increments, and reads
  back through the existing ``tenant_config`` key-value table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lethe.runtime.provenance import (
    PROVENANCE_DROPPED_COUNT_KEY,
    ProvenanceEnvelope,
    ProvenanceError,
    ProvenanceRequired,
    increment_dropped_counter,
    make,
    materialize_from_peer,
    read_dropped_counter,
)
from lethe.store.s2_meta import S2Schema


@pytest.fixture
def s2_conn(tenant_root: Path) -> sqlite3.Connection:
    schema = S2Schema(tenant_root=tenant_root)
    conn = schema.create()
    yield conn
    conn.close()


def _full_envelope() -> ProvenanceEnvelope:
    return make(
        episode_id="01890af0-0000-7000-8000-000000000001",
        source_uri="ext://docs/example.md#L1",
        agent_id="principal-x",
        recorded_at="2026-05-12T17:00:00Z",
        derived_from="01890af0-0000-7000-8000-00000000aaaa",
        edit_history_id="01890af0-0000-7000-8000-00000000bbbb",
    )


# ---------------------------------------------------------------------------
# Envelope construction + validation
# ---------------------------------------------------------------------------


def test_make_accepts_full_envelope() -> None:
    env = _full_envelope()
    assert env.source_uri == "ext://docs/example.md#L1"
    assert env.derived_from == "01890af0-0000-7000-8000-00000000aaaa"
    assert env.edit_history_id == "01890af0-0000-7000-8000-00000000bbbb"


def test_make_accepts_minimal_envelope() -> None:
    env = make(
        episode_id="ep-1",
        source_uri="ext://x",
        agent_id="agent-a",
        recorded_at="2026-05-12T17:00:00Z",
    )
    assert env.derived_from is None
    assert env.edit_history_id is None


def test_make_refuses_missing_source_uri() -> None:
    with pytest.raises(ProvenanceRequired):
        make(
            episode_id="ep-1",
            source_uri="",
            agent_id="agent-a",
            recorded_at="2026-05-12T17:00:00Z",
        )


@pytest.mark.parametrize(
    "missing_field", ["episode_id", "agent_id", "recorded_at"]
)
def test_make_refuses_other_missing_required_fields(missing_field: str) -> None:
    fields: dict[str, str] = {
        "episode_id": "ep-1",
        "source_uri": "ext://x",
        "agent_id": "agent-a",
        "recorded_at": "2026-05-12T17:00:00Z",
    }
    fields[missing_field] = ""
    with pytest.raises(ProvenanceError) as excinfo:
        make(**fields)
    # source_uri specifically maps to ProvenanceRequired; the others land
    # on the generic base. We assert only the specific subclass behavior
    # in the dedicated test above; here the parametrized inputs all
    # exclude source_uri so the generic ProvenanceError is the expected
    # type (and ProvenanceRequired would be a stricter subclass we did
    # NOT request).
    assert not isinstance(excinfo.value, ProvenanceRequired)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_envelope_round_trip_full() -> None:
    env = _full_envelope()
    again = ProvenanceEnvelope.from_dict(env.to_dict())
    assert again == env


def test_envelope_round_trip_minimal_omits_optional_keys() -> None:
    env = make(
        episode_id="ep-1",
        source_uri="ext://x",
        agent_id="agent-a",
        recorded_at="2026-05-12T17:00:00Z",
    )
    payload = env.to_dict()
    assert "derived_from" not in payload
    assert "edit_history_id" not in payload
    again = ProvenanceEnvelope.from_dict(payload)
    assert again == env


def test_from_dict_refuses_missing_source_uri() -> None:
    with pytest.raises(ProvenanceRequired):
        ProvenanceEnvelope.from_dict(
            {
                "episode_id": "ep-1",
                "source_uri": "",
                "agent_id": "agent-a",
                "recorded_at": "2026-05-12T17:00:00Z",
            }
        )


def test_from_dict_refuses_other_missing_required_fields() -> None:
    with pytest.raises(ProvenanceError):
        ProvenanceEnvelope.from_dict(
            {
                "episode_id": "",
                "source_uri": "ext://x",
                "agent_id": "agent-a",
                "recorded_at": "2026-05-12T17:00:00Z",
            }
        )


# ---------------------------------------------------------------------------
# Two-step materialization (gap-05 §3.3 + gap-10 §3.3)
# ---------------------------------------------------------------------------


def test_materialize_from_peer_sets_derived_from_to_peer_episode_id() -> None:
    peer = make(
        episode_id="01890af0-0000-7000-8000-0000000000aa",
        source_uri="peer_message:agent-b:msg-1",
        agent_id="agent-b",
        recorded_at="2026-05-12T16:59:00Z",
    )
    new = materialize_from_peer(
        peer,
        new_episode_id="01890af0-0000-7000-8000-0000000000bb",
        recipient_agent_id="agent-a",
        recorded_at="2026-05-12T17:00:00Z",
    )
    assert new.episode_id == "01890af0-0000-7000-8000-0000000000bb"
    assert new.agent_id == "agent-a"
    assert new.source_uri == "self_observation:agent-a"
    # Peer identity reachable via derived_from, NOT laundered into source_uri.
    assert new.derived_from == peer.episode_id
    assert new.edit_history_id is None


# ---------------------------------------------------------------------------
# provenance_drop_count counter
# ---------------------------------------------------------------------------


def test_read_dropped_counter_returns_zero_on_unseeded(
    s2_conn: sqlite3.Connection,
) -> None:
    assert read_dropped_counter(s2_conn) == 0


def test_increment_dropped_counter_seeds_then_increments(
    s2_conn: sqlite3.Connection,
) -> None:
    assert increment_dropped_counter(s2_conn) == 1
    assert increment_dropped_counter(s2_conn) == 2
    assert increment_dropped_counter(s2_conn) == 3
    assert read_dropped_counter(s2_conn) == 3


def test_dropped_counter_uses_canonical_tenant_config_key(
    s2_conn: sqlite3.Connection,
) -> None:
    """api §1.5 line 128 names the counter ``provenance_drop_count``."""
    increment_dropped_counter(s2_conn)
    row = s2_conn.execute(
        "SELECT value FROM tenant_config WHERE key = ?",
        (PROVENANCE_DROPPED_COUNT_KEY,),
    ).fetchone()
    assert row == ("1",)
    assert PROVENANCE_DROPPED_COUNT_KEY == "provenance_drop_count"
