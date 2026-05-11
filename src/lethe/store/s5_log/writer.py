"""S5 append-only consolidation log writer + Markdown-backed alternative.

The ``ConsolidationLogWriter`` Protocol decouples the log surface from the
backing medium so the operator-config knob (composition §2 row 5: SQLite
table vs ``log.md``) is one swap, not a rewrite.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from lethe.store.s2_meta.schema import S5_LOG_TABLE_NAME, S2Schema


@dataclass(frozen=True)
class LogEntry:
    """One append-only consolidation log entry.

    ``kind`` names the dream-daemon decision class (e.g. ``"promotion"``,
    ``"invalidation"``); ``payload`` is the rationale + fact-id linkage.
    Concrete kind/payload contracts land at P4 (consolidate loop).
    """

    kind: str
    payload: dict[str, Any]
    appended_at: datetime | None = None


class ConsolidationLogWriter(Protocol):
    """Append-only log surface; both backings must satisfy this contract."""

    def append(self, entry: LogEntry) -> None: ...

    def replay(self) -> Iterator[LogEntry]: ...


class SqliteLogWriter:
    """Default S5 backing: a table inside the per-tenant S2 SQLite file."""

    def __init__(self, tenant_root: Path) -> None:
        self._tenant_root = tenant_root
        self._db_path = S2Schema(tenant_root=tenant_root).db_path

    def _connect(self) -> sqlite3.Connection:
        # We open a fresh connection per call; SQLite handles concurrent
        # connections via WAL (already enabled by S2Schema.create()). This
        # keeps the writer stateless and safe to construct repeatedly.
        return sqlite3.connect(str(self._db_path), isolation_level=None)

    def append(self, entry: LogEntry) -> None:
        appended_at = (entry.appended_at or datetime.now(UTC)).isoformat()
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {S5_LOG_TABLE_NAME}(kind, payload_json, appended_at) "
                f"VALUES (?, ?, ?)",
                (entry.kind, json.dumps(entry.payload, sort_keys=True), appended_at),
            )

    def replay(self) -> Iterator[LogEntry]:
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT kind, payload_json, appended_at FROM {S5_LOG_TABLE_NAME} "
                f"ORDER BY seq ASC"
            )
            for kind, payload_json, appended_at in cur.fetchall():
                yield LogEntry(
                    kind=kind,
                    payload=json.loads(payload_json),
                    appended_at=datetime.fromisoformat(appended_at),
                )


class MarkdownLogWriter:
    """Alternative S5 backing: a ``log.md`` per dream-daemon precedent.

    Defined at P1 so the protocol seam is honest; not exercised by the P1
    smoke (operator-config wiring lands in P3+ per plan.md §B3). All methods
    raise :class:`NotImplementedError` until that wiring lands.
    """

    def __init__(self, tenant_root: Path) -> None:
        self._tenant_root = tenant_root
        self._log_path = tenant_root / "s5_log" / "log.md"

    @property
    def log_path(self) -> Path:
        return self._log_path

    def append(self, entry: LogEntry) -> None:  # pragma: no cover - P3+
        raise NotImplementedError(
            "MarkdownLogWriter is defined-only at P1; operator-config wiring lands in P3+"
        )

    def replay(self) -> Iterator[LogEntry]:  # pragma: no cover - P3+
        raise NotImplementedError(
            "MarkdownLogWriter is defined-only at P1; operator-config wiring lands in P3+"
        )
