"""S5 — append-only consolidation log.

Per composition §2 row 5, S5 is the audit trail for every dream-daemon
decision: promotions, demotions, merges, invalidations, peer-message
deliveries, with rationale + input/output fact-ids.

Default backing per facilitator-locked plan §(g): a SQLite table inside
the per-tenant S2 file (yields ``T2 = (S2 flag + S5 audit)`` as a single-DB
transaction per composition §3.4). The :class:`MarkdownLogWriter` alternative
backing per dream-daemon precedent is defined here but not exercised at P1.
"""

from lethe.store.s5_log.writer import (
    ConsolidationLogWriter,
    LogEntry,
    MarkdownLogWriter,
    SqliteLogWriter,
)

__all__ = [
    "ConsolidationLogWriter",
    "LogEntry",
    "MarkdownLogWriter",
    "SqliteLogWriter",
]
