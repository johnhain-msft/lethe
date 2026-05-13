"""Lethe MCP verb surface.

P2 lands :func:`remember` (api §3.1); P3 lands :func:`recall` (api §2.1)
and :func:`recall_synthesis` (api §2.2; commit 4). P5 lands
``promote`` / ``forget``; P6 the peer-messaging + admin/ops verbs.
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
from lethe.api.recall_synthesis import (
    S4aOutage,
    SynthesisError,
    SynthesisNotFoundError,
    SynthesisPage,
    SynthesisRequest,
    SynthesisResponse,
    SynthesisSource,
    SynthesisValidationError,
    recall_synthesis,
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
    "S4aOutage",
    "ScoredFact",
    "SynthesisError",
    "SynthesisNotFoundError",
    "SynthesisPage",
    "SynthesisRequest",
    "SynthesisResponse",
    "SynthesisSource",
    "SynthesisValidationError",
    "recall",
    "recall_synthesis",
    "remember",
]
