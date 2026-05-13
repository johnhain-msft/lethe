"""Emit-point library (scoring §8.1, §8.2, §8.4, §8.5).

P2 ships the ``remember`` event emit point. P3 adds ``recall`` (api §1.4
deterministic recall_id + path dispatch). P4 adds the four consolidate-
side event types from scoring §8.1: ``promote``, ``demote``,
``invalidate``, and ``consolidate_phase``. ``recall_outcome`` stays
common-only at P4 (D5-P3 — emission deferred to P9).

Common envelope contract (scoring §8.2): every event MUST carry
``event_id``, ``event_type``, ``tenant_id``, ``ts_recorded``,
``ts_valid``, ``model_version``, ``weights_version``, and
``contamination_protected``. Per-event-type extras are enforced by
:func:`validate` via the :data:`_PER_TYPE_REQUIRED` map; for ``remember``
that means ``fact_ids`` (non-empty), ``decision``, and ``provenance``
(gap-05 §3.5: provenance is mandatory on ``remember``). For ``promote``
and ``demote`` that means ``fact_ids`` + ``decision`` + ``score_output``
(scoring §8.1 "Decision + score-at-decision"). For ``invalidate`` that
means ``fact_ids`` + ``decision`` (the gap-13 §3 reason enum) +
``superseded_by`` (the §8.1 supersession pointer; key required, value
may be ``None`` for hard invalidate). For ``consolidate_phase`` that
means ``phase_name`` (one of the six values in
:data:`_VALID_CONSOLIDATE_PHASES`) + ``consolidate_run_id`` (joins all
six §8.1 phase events from one cycle for replay context).

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


#: Allowed values for the ``consolidate_phase`` event's ``phase_name``
#: per-type field. The six dream-daemon phases run in canonical order on
#: every consolidate cycle (scoring §0 process row + IMPL §2.4 invariant
#: I-11): extract → score → promote → demote → consolidate → invalidate.
ConsolidatePhase = Literal[
    "extract",
    "score",
    "promote",
    "demote",
    "consolidate",
    "invalidate",
]

_VALID_CONSOLIDATE_PHASES: Final[frozenset[str]] = frozenset(
    {
        "extract",
        "score",
        "promote",
        "demote",
        "consolidate",
        "invalidate",
    }
)


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
    # P4 (scoring §8.1 + §8.2):
    #
    # promote / demote each carry the subject ``fact_ids`` (per-write
    # cardinality per §8.1; envelope plural matches the §8.2 shape and
    # the existing ``remember`` / ``recall`` precedent), the per-type
    # ``decision`` enum (e.g. ``"promoted_to_S3"`` / ``"demoted"`` /
    # ``"purge_pending"`` — string locked by the consolidate-phase verb
    # at P5+, not here), and ``score_output`` — the §8.1 "score-at-
    # decision" — so the v2 trainer (§8.6) can pair the decision with
    # the score that drove it without re-deriving features at replay
    # time.
    "promote": frozenset({"fact_ids", "decision", "score_output"}),
    "demote": frozenset({"fact_ids", "decision", "score_output"}),
    # invalidate carries ``fact_ids`` + ``decision`` (= reason enum;
    # gap-13 §3 invalidate-reason taxonomy, locked at the verb layer)
    # + ``superseded_by`` — the §8.1 "supersession pointer". The pointer
    # is REQUIRED as a key (so the envelope shape is uniform across all
    # invalidate events), but its value MAY be ``None`` for a hard
    # invalidate that has no supersessor (gap-13 hard-vs-soft split).
    "invalidate": frozenset({"fact_ids", "decision", "superseded_by"}),
    # consolidate_phase: per dream-daemon phase boundary (§8.1; IMPL
    # §2.4 invariant I-11 fires six in canonical order per cycle).
    # ``phase_name`` is one of the six values in
    # :data:`_VALID_CONSOLIDATE_PHASES`; ``consolidate_run_id`` joins
    # all six phase events from one cycle for replay context (§8.1
    # purpose row).
    "consolidate_phase": frozenset({"phase_name", "consolidate_run_id"}),
}


SinkCallable = Callable[[Mapping[str, Any]], None]


# Sentinel for the invalidate ``superseded_by`` defensive check: ``None``
# is a legitimate value for the field (hard invalidate with no successor),
# so :func:`Mapping.get` with a None default cannot disambiguate
# "missing key" from "key present, value is None". A unique sentinel does.
_MISSING: Final[object] = object()


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
        raise ContaminationGateFailure("contamination_protected must be True (scoring §8.5)")

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
                "event envelope (event_type='remember') requires non-empty fact_ids: list[str]"
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
                "event envelope (event_type='recall') requires non-empty fact_ids: list[str]"
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
                "event envelope (event_type='recall') requires non-empty recall_id: str"
            )

    # P4 emit-side surfaces (scoring §8.1 + §8.2). The four branches below
    # mirror the ``remember`` / ``recall`` shape: the per-type ``required``
    # set above guarantees the keys are PRESENT; the branch enforces
    # intra-field shape constraints.

    # promote / demote: identical envelope shape per §8.1 row "Decision +
    # score-at-decision". fact_ids must be a non-empty list[str]; decision
    # must be a non-empty str (the per-tier enum is locked by the verb at
    # consume-time, not here); score_output must be a real number — bool
    # is rejected because Python's ``True is 1`` makes ``isinstance(True,
    # int)`` truthy, and a boolean score is not a valid §8.2 ``score_output``.
    if event_type in ("promote", "demote"):
        fact_ids = event.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            raise EventValidationError(
                f"event envelope (event_type={event_type!r}) requires non-empty fact_ids: list[str]"
            )
        if not all(isinstance(f, str) for f in fact_ids):
            raise EventValidationError(
                f"event envelope (event_type={event_type!r}) fact_ids must be list[str]"
            )
        decision = event.get("decision")
        if not isinstance(decision, str) or not decision:
            raise EventValidationError(
                f"event envelope (event_type={event_type!r}) requires non-empty decision: str"
            )
        score_output = event.get("score_output")
        if isinstance(score_output, bool) or not isinstance(score_output, (int, float)):
            raise EventValidationError(
                f"event envelope (event_type={event_type!r}) requires "
                f"score_output: int | float (bool rejected; got {type(score_output).__name__})"
            )

    # invalidate: §8.1 "Reason + supersession pointer" — fact_ids + decision
    # (reason enum, gap-13 §3) + superseded_by (the pointer; MAY be None
    # for hard invalidate with no successor, but the key MUST be present
    # so the envelope shape is uniform).
    if event_type == "invalidate":
        fact_ids = event.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            raise EventValidationError(
                "event envelope (event_type='invalidate') requires non-empty fact_ids: list[str]"
            )
        if not all(isinstance(f, str) for f in fact_ids):
            raise EventValidationError(
                "event envelope (event_type='invalidate') fact_ids must be list[str]"
            )
        decision = event.get("decision")
        if not isinstance(decision, str) or not decision:
            raise EventValidationError(
                "event envelope (event_type='invalidate') requires non-empty "
                "decision: str (the gap-13 §3 invalidate-reason enum)"
            )
        superseded_by = event.get("superseded_by", _MISSING)
        if superseded_by is _MISSING:
            # Belt-and-suspenders: the per-type required check above
            # already rejects a missing key, but defending the branch
            # against future refactors that might bypass it.
            raise EventValidationError(
                "event envelope (event_type='invalidate') requires "
                "superseded_by key (value may be None for hard invalidate)"
            )
        if superseded_by is not None and (not isinstance(superseded_by, str) or not superseded_by):
            raise EventValidationError(
                "event envelope (event_type='invalidate') superseded_by must "
                "be None or non-empty str"
            )

    # consolidate_phase: phase_name must be one of the six canonical
    # dream-daemon phases (IMPL §2.4 invariant I-11); consolidate_run_id
    # is the join key that gathers all six events from one cycle.
    if event_type == "consolidate_phase":
        phase_name = event.get("phase_name")
        if phase_name not in _VALID_CONSOLIDATE_PHASES:
            raise EventValidationError(
                f"event envelope (event_type='consolidate_phase') phase_name "
                f"{phase_name!r} not in {sorted(_VALID_CONSOLIDATE_PHASES)}"
            )
        consolidate_run_id = event.get("consolidate_run_id")
        if not isinstance(consolidate_run_id, str) or not consolidate_run_id:
            raise EventValidationError(
                "event envelope (event_type='consolidate_phase') requires "
                "non-empty consolidate_run_id: str"
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
