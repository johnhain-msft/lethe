"""Emit-point library (scoring §8.1, §8.2, §8.4, §8.5).

P2 ships the ``remember`` event emit point. The other six event types
from scoring §8.1 (``recall``, ``recall_outcome``, ``promote``,
``demote``, ``invalidate``, ``consolidate_phase``) wire in at P3+ as
their owning verbs land.

Common envelope contract (scoring §8.2): every event MUST carry
``event_id``, ``event_type``, ``tenant_id``, ``ts_recorded``,
``ts_valid``, ``model_version``, ``weights_version``, and
``contamination_protected``. Per-event-type extras are enforced by
:func:`validate` via the :data:`_PER_TYPE_REQUIRED` map; for ``remember``
that means ``fact_ids`` (non-empty), ``decision``, and ``provenance``
(gap-05 §3.5: provenance is mandatory on ``remember``).

Privacy invariant (§8.5): every envelope MUST carry
``contamination_protected = True``; events that fail the gate are
dropped at the emitter (defense in depth). Public-benchmark replays that
must emit with ``contamination_protected=False`` use a separate
``bench/`` shard wired in at WS4 — not at P2.

Sink contract (§8.4): the canonical sink is
``scripts.eval.metrics.emitter.emit_score_event``. That function is
forward-spec — WS5 emitter.py declares the surface but leaves it
unimplemented (it raises :class:`NotImplementedError` if invoked). The
default sink in this module imports it lazily and treats both
``ImportError`` (sink module absent in some test layouts) and
``NotImplementedError`` (sink defined but not implemented) as a no-op so
production code can begin emitting today without a hard dependency on
the WS4 work landing first. Tests inject a deterministic recording sink.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any, Final, Literal

#: Allowed values for the ``recall`` event's ``path`` per-type field.
#: ``"recall"`` events are emitted by the ``recall`` verb (api §2.1);
#: ``"synthesis"`` events are emitted by the ``recall_synthesis`` verb
#: (api §2.2). Both share the same envelope shape and event_type.
RecallPath = Literal["recall", "synthesis"]

_VALID_RECALL_PATHS: Final[frozenset[str]] = frozenset({"recall", "synthesis"})


EventType = Literal[
    "remember",
    "recall",
    "recall_outcome",
    "promote",
    "demote",
    "invalidate",
    "consolidate_phase",
]

_VALID_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "remember",
        "recall",
        "recall_outcome",
        "promote",
        "demote",
        "invalidate",
        "consolidate_phase",
    }
)

# Common envelope (scoring §8.2). Every event must have these.
_COMMON_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        "event_id",
        "event_type",
        "tenant_id",
        "ts_recorded",
        "ts_valid",
        "model_version",
        "weights_version",
        "contamination_protected",
    }
)

# Per-type extras layered on top of _COMMON_REQUIRED. Only event types
# whose owning verb has fully landed appear here; the rest get the looser
# common-only check until their phase locks the shape.
_PER_TYPE_REQUIRED: Final[dict[str, frozenset[str]]] = {
    "remember": frozenset({"fact_ids", "decision", "provenance"}),
    # P3: recall events carry the deterministic recall_id (api §1.4),
    # the top-k fact_ids surfaced to the caller, and the dispatch path
    # ("recall" vs "synthesis"). recall_outcome stays common-only at
    # P3 (D5 — emission deferred to P9; only the recall_id join-key
    # is plumbed at P3).
    "recall": frozenset({"recall_id", "fact_ids", "path"}),
}


SinkCallable = Callable[[Mapping[str, Any]], None]


class EventValidationError(Exception):
    """Raised when an event envelope fails §8.2 / per-type validation."""


class ContaminationGateFailure(EventValidationError):
    """Raised when ``contamination_protected`` is missing or not literally ``True`` (§8.5)."""


def validate(event: Mapping[str, object]) -> None:
    """Enforce the §8.2 common envelope, the §8.5 contamination gate, and
    any per-event-type extras from :data:`_PER_TYPE_REQUIRED`.

    Argument type is :class:`Mapping[str, object]` (not the
    :class:`TypedDict` envelope) so callers can pass deliberately
    malformed dicts in tests without fighting mypy --strict.
    """
    missing_common = _COMMON_REQUIRED - event.keys()
    if missing_common:
        raise EventValidationError(
            f"event envelope missing required fields: {sorted(missing_common)}"
        )

    event_type = event["event_type"]
    if event_type not in _VALID_EVENT_TYPES:
        raise EventValidationError(
            f"event envelope event_type {event_type!r} not in scoring §8.1 taxonomy"
        )

    # The contamination gate is an explicit identity check on True; a
    # truthy sentinel like the string "true" must not pass (§8.5
    # defense-in-depth).
    if event["contamination_protected"] is not True:
        raise ContaminationGateFailure(
            "contamination_protected must be True (scoring §8.5)"
        )

    extras_required = _PER_TYPE_REQUIRED.get(str(event_type), frozenset())
    missing_extras = extras_required - event.keys()
    if missing_extras:
        raise EventValidationError(
            f"event envelope (event_type={event_type!r}) missing required "
            f"per-type fields: {sorted(missing_extras)}"
        )

    # remember: fact_ids must be a non-empty sequence (a remember with
    # zero fact_ids is a contradiction in terms — gap-05 §3.5).
    if event_type == "remember":
        fact_ids = event.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            raise EventValidationError(
                "event envelope (event_type='remember') requires non-empty "
                "fact_ids: list[str]"
            )

    # recall: fact_ids may be empty (k=0 preferences-only response is a
    # legitimate zero-event recall — see api §2.1.1 — but a recall event
    # that *is* emitted MUST carry a non-empty fact_ids list, otherwise
    # the §8.4 emit-pipeline cannot join it back to scoring outcomes).
    # path must be one of the documented dispatch values.
    if event_type == "recall":
        fact_ids = event.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            raise EventValidationError(
                "event envelope (event_type='recall') requires non-empty "
                "fact_ids: list[str]"
            )
        if not all(isinstance(f, str) for f in fact_ids):
            raise EventValidationError(
                "event envelope (event_type='recall') fact_ids must be list[str]"
            )
        path = event.get("path")
        if path not in _VALID_RECALL_PATHS:
            raise EventValidationError(
                f"event envelope (event_type='recall') path {path!r} not in "
                f"{sorted(_VALID_RECALL_PATHS)}"
            )
        recall_id_value = event.get("recall_id")
        if not isinstance(recall_id_value, str) or not recall_id_value:
            raise EventValidationError(
                "event envelope (event_type='recall') requires non-empty "
                "recall_id: str"
            )


def _default_sink(event: Mapping[str, Any]) -> None:
    """Forward to ``scripts.eval.metrics.emitter.emit_score_event`` lazily.

    Two failure modes are silently no-op'd:

    - :class:`ImportError` / :class:`AttributeError` resolving the symbol
      (sink module absent or symbol not yet exported in some test layouts).
    - :class:`NotImplementedError` raised by ``emit_score_event`` itself
      (the WS4 emitter ships the symbol as a forward-spec stub).

    Any other exception from the sink propagates (the sink owns its own
    durability story; surfacing real errors is more important than
    silencing them).
    """
    # Resolved dynamically (importlib + getattr) so mypy --strict does
    # not transitively analyze the scripts/ tree, which is not on the
    # type-checked surface.
    try:
        emitter = importlib.import_module("scripts.eval.metrics.emitter")
    except ImportError:
        return
    sink = getattr(emitter, "emit_score_event", None)
    if sink is None:
        return
    try:
        sink(event)
    except NotImplementedError:
        return


def emit(event: Mapping[str, object], *, sink: SinkCallable | None = None) -> None:
    """Validate + dispatch an event envelope to the configured sink.

    Validation failures raise; arbitrary sink errors propagate. The
    default sink is the WS5 forward-spec ``emit_score_event``; tests
    inject a deterministic recording sink via the keyword argument.
    """
    validate(event)
    chosen: SinkCallable = sink if sink is not None else _default_sink
    # The validated mapping is dispatched as-is; no defensive copy.
    chosen(dict(event))
