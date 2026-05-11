"""S5 smoke: append-only writer; replay determinism; lives inside the S2 file."""

from __future__ import annotations

from pathlib import Path

from lethe.store.s2_meta import S2Schema
from lethe.store.s5_log import LogEntry, SqliteLogWriter


def test_s5_append_then_replay_in_order(tenant_root: Path) -> None:
    # S5 lives inside the S2 file (facilitator §(g) lock); S2Schema.create()
    # is the prerequisite for the log table to exist.
    S2Schema(tenant_root=tenant_root).create().close()

    writer = SqliteLogWriter(tenant_root=tenant_root)
    writer.append(LogEntry(kind="promotion", payload={"fact_id": "f1"}))
    writer.append(LogEntry(kind="invalidation", payload={"fact_id": "f2"}))
    writer.append(LogEntry(kind="merge", payload={"facts": ["f3", "f4"]}))

    entries = list(writer.replay())
    assert [e.kind for e in entries] == ["promotion", "invalidation", "merge"]
    assert entries[0].payload == {"fact_id": "f1"}
    assert entries[2].payload == {"facts": ["f3", "f4"]}


def test_s5_payload_json_serialized_deterministically(tenant_root: Path) -> None:
    S2Schema(tenant_root=tenant_root).create().close()
    writer = SqliteLogWriter(tenant_root=tenant_root)
    writer.append(LogEntry(kind="x", payload={"b": 2, "a": 1}))
    [e] = list(writer.replay())
    assert e.payload == {"a": 1, "b": 2}


def test_s5_writer_db_path_is_s2_file(tenant_root: Path) -> None:
    """Confirms the facilitator §(g) lock: S5 backing = SQLite-in-S2."""
    s2_path = S2Schema(tenant_root=tenant_root).db_path
    writer = SqliteLogWriter(tenant_root=tenant_root)
    assert writer._db_path == s2_path  # noqa: SLF001 - intentional invariant check
