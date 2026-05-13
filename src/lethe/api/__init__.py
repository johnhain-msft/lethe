"""Lethe MCP verb surface.

P2 lands :func:`remember` (api §3.1); P3 lands :func:`recall` (api §2.1).
Other verbs land in later phases: P3 also adds ``recall_synthesis``
(commit 4); P5 (``promote``, ``forget``); P6 (peer-messaging + admin/ops).
Importing this package no longer raises; the IMPL §2.1 P1 exit gate is
satisfied by the runtime tenant-init smoke landing at P1, not by
import-time NotImplementedError.
"""

from __future__ import annotations

from lethe.api.recall import (
    FactRecord,
    FactStore,
    RecallError,
    RecallLedgerCorruption,
    RecallRequest,
    RecallResponse,
    RecallValidationError,
    ScoredFact,
    recall,
)
from lethe.api.remember import (
    RememberAuthError,
    RememberConflictError,
    RememberError,
    RememberPeerRouteError,
    RememberRequest,
    RememberResponse,
    RememberValidationError,
    remember,
)

__all__ = [
    "FactRecord",
    "FactStore",
    "RecallError",
    "RecallLedgerCorruption",
    "RecallRequest",
    "RecallResponse",
    "RecallValidationError",
    "RememberAuthError",
    "RememberConflictError",
    "RememberError",
    "RememberPeerRouteError",
    "RememberRequest",
    "RememberResponse",
    "RememberValidationError",
    "ScoredFact",
    "recall",
    "remember",
]
