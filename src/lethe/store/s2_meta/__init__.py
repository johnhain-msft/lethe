"""S2 — SQLite metadata store (per-tenant, WAL).

Per composition §2 row 2, S2 owns the recall ledger, utility-feedback events,
promotion/demotion flags, consolidation scheduler state, extraction-confidence
log, tenant config, and scoring-weight overrides. Per facilitator-locked plan
§(g), the S5 consolidation log table also lives in this same SQLite file so
that ``T2 = (S2 flag write + S5 audit write)`` is a single-DB transaction
(composition §3.4).
"""

from lethe.store.s2_meta.schema import (
    S2_TABLE_NAMES,
    S5_LOG_TABLE_NAME,
    S2Schema,
    open_connection,
)

__all__ = [
    "S2_TABLE_NAMES",
    "S2Schema",
    "S5_LOG_TABLE_NAME",
    "open_connection",
]
