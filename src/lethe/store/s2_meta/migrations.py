"""S2 schema migrations registry.

P1 ships schema version 1 (see :mod:`lethe.store.s2_meta.schema`). Concrete
forward migrations land as each table's owning verb arrives:

- P2: ``recall_ledger`` columns; ``idempotency_keys`` index for replay lookup.
- P4: ``consolidation_state`` columns; ``scoring_weight_overrides`` defaults.
- P5: ``promotion_flags`` columns; ``audit_log`` columns for retention proofs.
- P7: ``review_queue`` indexes for the review surface.

The registry below is empty at P1 by design; ``current_version()`` returns the
``schema_version`` sentinel from the ``_lethe_meta`` row created by
:meth:`S2Schema.create`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

# Each migration is `(version, callable)` where callable mutates the DB to
# bring it from `version - 1` to `version`. P1 starts and stops at 1.
MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = ()


def current_version(conn: sqlite3.Connection) -> int:
    """Return the schema version recorded in ``_lethe_meta``.

    Returns ``0`` if the meta row is absent (pre-bootstrap database).
    """
    cur = conn.execute(
        "SELECT value FROM _lethe_meta WHERE key = 'schema_version'"
    )
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])
