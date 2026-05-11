"""Lethe MCP verb surface — locked at P1.

No api verb is exposed at P1 (per ``docs/IMPLEMENTATION.md`` §2.1 exit gate).
Importing this package raises ``NotImplementedError`` by design; the verbs
land in P2 (``remember``), P3 (``recall``, ``recall_synthesis``), P5
(``promote``, ``forget``), and P6 (peer-messaging + admin/ops).
"""

raise NotImplementedError(
    "lethe.api verbs land in P2+; importing this package at P1 is "
    "intentionally an error (see docs/IMPLEMENTATION.md §2.1 exit gates)."
)
