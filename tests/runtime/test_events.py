"""Event emit-point coverage (scoring §8.1, §8.2, §8.4, §8.5).

Covers:

- ``validate`` accepts a fully-populated ``remember`` envelope.
- Each common-required field (scoring §8.2) being absent raises
  :class:`EventValidationError`.
- An event_type outside the scoring §8.1 taxonomy raises.
- ``contamination_protected`` missing or False (or a truthy non-True
  sentinel) raises :class:`ContaminationGateFailure` (defense in depth).
- ``remember`` requires ``fact_ids`` (non-empty list), ``decision``,
  and ``provenance``.
- ``emit`` with an injected sink dispatches the (validated) envelope.
- ``emit`` does not dispatch invalid events.
- The default sink is a silent no-op when ``emit_score_event`` raises
  :class:`NotImplementedError` (the WS5 forward-spec stub).
- Unrelated sink exceptions propagate.
"""

from __future__ import annotations

from typing import Any

import pytest

from lethe.runtime import events
from lethe.runtime.events import (
    ContaminationGateFailure,
    EventValidationError,
    emit,
    validate,
)


def _remember_envelope() -> dict[str, Any]:
    """A complete ``remember`` envelope per scoring §8.2 + §8.5."""
    return {
        "event_id": "01890af0-0000-7000-8000-00000000ee01",
        "event_type": "remember",
        "tenant_id": "tenant-a",
        "ts_recorded": "2026-05-12T17:00:00Z",
        "ts_valid": "2026-05-12T17:00:00Z",
        "model_version": "v1.0.0",
        "weights_version": "sha256:0000000000000000",
        "contamination_protected": True,
        "fact_ids": ["fact-1"],
        "decision": "accepted",
        "provenance": {"source_uri": "ext://docs/x.md", "edit_history_id": None},
    }


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_accepts_full_remember_envelope() -> None:
    validate(_remember_envelope())


@pytest.mark.parametrize(
    "missing_field",
    [
        "event_id",
        "event_type",
        "tenant_id",
        "ts_recorded",
        "ts_valid",
        "model_version",
        "weights_version",
        "contamination_protected",
    ],
)
def test_validate_rejects_missing_common_field(missing_field: str) -> None:
    env = _remember_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


def test_validate_rejects_unknown_event_type() -> None:
    env = _remember_envelope()
    env["event_type"] = "synthesize"  # not in scoring §8.1 taxonomy
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert "synthesize" in str(excinfo.value)


def test_validate_rejects_contamination_protected_false() -> None:
    env = _remember_envelope()
    env["contamination_protected"] = False
    with pytest.raises(ContaminationGateFailure):
        validate(env)


def test_validate_rejects_contamination_protected_truthy_non_bool() -> None:
    """Defense in depth: only literal ``True`` passes (§8.5)."""
    env = _remember_envelope()
    env["contamination_protected"] = "true"  # truthy but not True
    with pytest.raises(ContaminationGateFailure):
        validate(env)


@pytest.mark.parametrize("missing_field", ["fact_ids", "decision", "provenance"])
def test_validate_rejects_remember_missing_per_type_extras(
    missing_field: str,
) -> None:
    env = _remember_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


def test_validate_rejects_remember_with_empty_fact_ids() -> None:
    env = _remember_envelope()
    env["fact_ids"] = []
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_remember_with_non_list_fact_ids() -> None:
    env = _remember_envelope()
    env["fact_ids"] = "fact-1"
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_does_not_require_per_type_extras_for_other_event_types() -> None:
    """Per-type extras are only enforced for event types whose owning verb has landed.

    ``recall_outcome`` is the only event type that stays common-only after
    P4 (D5-P3 — emission deferred to P9; only the recall_id join-key is
    plumbed earlier). All other §8.1 types now have per-type required sets.
    """
    env = _remember_envelope()
    env["event_type"] = "recall_outcome"
    # Strip the remember-specific extras; recall_outcome has no per-type extras.
    for key in ("fact_ids", "decision", "provenance"):
        env.pop(key, None)
    validate(env)  # no raise


# ---------------------------------------------------------------------------
# emit + sink injection
# ---------------------------------------------------------------------------


def test_emit_dispatches_validated_event_to_injected_sink() -> None:
    captured: list[dict[str, Any]] = []

    def sink(event: Any) -> None:
        captured.append(dict(event))

    env = _remember_envelope()
    emit(env, sink=sink)

    assert len(captured) == 1
    assert captured[0]["event_id"] == env["event_id"]
    assert captured[0]["event_type"] == "remember"
    assert captured[0]["contamination_protected"] is True


def test_emit_does_not_dispatch_invalid_event() -> None:
    captured: list[dict[str, Any]] = []

    def sink(event: Any) -> None:
        captured.append(dict(event))

    env = _remember_envelope()
    env["contamination_protected"] = False

    with pytest.raises(ContaminationGateFailure):
        emit(env, sink=sink)
    assert captured == []


def test_default_sink_is_noop_when_emit_score_event_unimplemented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The WS5 forward-spec stub raises NotImplementedError; emit must no-op."""
    from scripts.eval.metrics import emitter

    def _stub(event: Any) -> None:
        raise NotImplementedError("WS5 forward-spec stub")

    monkeypatch.setattr(emitter, "emit_score_event", _stub, raising=False)
    # No sink kwarg → the default sink is exercised; should not raise.
    emit(_remember_envelope())


def test_default_sink_propagates_unrelated_sink_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real bugs inside emit_score_event must surface, not be silently swallowed."""
    from scripts.eval.metrics import emitter

    def _broken(event: Any) -> None:
        raise RuntimeError("boom — sink internal failure")

    monkeypatch.setattr(emitter, "emit_score_event", _broken, raising=False)
    with pytest.raises(RuntimeError, match="boom"):
        emit(_remember_envelope())


def test_default_sink_handles_missing_emitter_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the emitter module is unimportable the default sink no-ops."""

    def _fail_import(name: str) -> Any:
        raise ImportError(f"simulated absence of {name}")

    monkeypatch.setattr(events.importlib, "import_module", _fail_import)
    # Should not raise.
    emit(_remember_envelope())


def test_default_sink_handles_missing_emit_score_event_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the emitter module exists but lacks ``emit_score_event``, no-op."""
    from scripts.eval.metrics import emitter

    monkeypatch.delattr(emitter, "emit_score_event", raising=False)
    # Should not raise.
    emit(_remember_envelope())


def test_emit_module_exposes_public_surface() -> None:
    """Sanity that the public symbols are importable via the package alias."""
    assert events.emit is emit
    assert events.validate is validate


# ---------------------------------------------------------------------------
# recall envelopes (P3)
# ---------------------------------------------------------------------------


def _recall_envelope() -> dict[str, Any]:
    """A complete ``recall`` envelope per scoring §8.2 + §8.5 + P3 per-type extras."""
    return {
        "event_id": "01890af0-0000-7000-8000-00000000ff01",
        "event_type": "recall",
        "tenant_id": "tenant-a",
        "ts_recorded": "2026-05-12T17:00:00Z",
        "ts_valid": "2026-05-12T17:00:00Z",
        "model_version": "v1.0.0",
        "weights_version": "sha256:0000000000000000",
        "contamination_protected": True,
        "recall_id": "01890af0-0000-7000-8000-00000000ee99",
        "fact_ids": ["fact-1", "fact-2"],
        "path": "recall",
    }


def test_validate_accepts_full_recall_envelope() -> None:
    validate(_recall_envelope())


def test_validate_accepts_recall_path_synthesis() -> None:
    env = _recall_envelope()
    env["path"] = "synthesis"
    validate(env)


@pytest.mark.parametrize("missing_field", ["recall_id", "fact_ids", "path"])
def test_validate_rejects_recall_missing_per_type_extras(
    missing_field: str,
) -> None:
    env = _recall_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


def test_validate_rejects_recall_with_empty_fact_ids() -> None:
    env = _recall_envelope()
    env["fact_ids"] = []
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_recall_with_non_str_fact_ids() -> None:
    env = _recall_envelope()
    env["fact_ids"] = ["fact-1", 42]
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_recall_with_unknown_path() -> None:
    env = _recall_envelope()
    env["path"] = "synthesize"  # near miss for "synthesis"
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_recall_with_empty_recall_id() -> None:
    env = _recall_envelope()
    env["recall_id"] = ""
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_recall_with_non_str_recall_id() -> None:
    env = _recall_envelope()
    env["recall_id"] = 12345
    with pytest.raises(EventValidationError):
        validate(env)


def test_emit_dispatches_validated_recall_event() -> None:
    captured: list[dict[str, Any]] = []
    emit(_recall_envelope(), sink=lambda e: captured.append(dict(e)))
    assert len(captured) == 1
    assert captured[0]["event_type"] == "recall"
    assert captured[0]["path"] == "recall"


# ---------------------------------------------------------------------------
# promote / demote envelopes (P4)
# ---------------------------------------------------------------------------


def _promote_envelope() -> dict[str, Any]:
    """A complete ``promote`` envelope per scoring §8.1 + §8.2 + P4 per-type extras."""
    return {
        "event_id": "01890af0-0000-7000-8000-000000000001",
        "event_type": "promote",
        "tenant_id": "tenant-a",
        "ts_recorded": "2026-05-12T17:00:00Z",
        "ts_valid": "2026-05-12T17:00:00Z",
        "model_version": "v1.0.0",
        "weights_version": "sha256:0000000000000000",
        "contamination_protected": True,
        "fact_ids": ["fact-1"],
        "decision": "promoted_to_S3",
        "score_output": 0.87,
    }


def _demote_envelope() -> dict[str, Any]:
    """A complete ``demote`` envelope per scoring §8.1 + §8.2 + P4 per-type extras."""
    env = _promote_envelope()
    env["event_id"] = "01890af0-0000-7000-8000-000000000002"
    env["event_type"] = "demote"
    env["decision"] = "demoted"
    env["score_output"] = 0.12
    return env


def test_validate_accepts_full_promote_envelope() -> None:
    validate(_promote_envelope())


def test_validate_accepts_full_demote_envelope() -> None:
    validate(_demote_envelope())


def test_validate_accepts_score_output_int_or_float() -> None:
    """``score_output`` may be int or float (just not bool)."""
    env = _promote_envelope()
    env["score_output"] = 1
    validate(env)
    env["score_output"] = 0
    validate(env)
    env["score_output"] = -3.14
    validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
@pytest.mark.parametrize("missing_field", ["fact_ids", "decision", "score_output"])
def test_validate_rejects_promote_demote_missing_per_type_extras(
    event_type: str, missing_field: str
) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_empty_fact_ids(event_type: str) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["fact_ids"] = []
    with pytest.raises(EventValidationError):
        validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_non_str_fact_ids(event_type: str) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["fact_ids"] = ["fact-1", 42]
    with pytest.raises(EventValidationError):
        validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_empty_decision(event_type: str) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["decision"] = ""
    with pytest.raises(EventValidationError):
        validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_non_str_decision(event_type: str) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["decision"] = 42
    with pytest.raises(EventValidationError):
        validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_non_numeric_score(event_type: str) -> None:
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["score_output"] = "0.87"
    with pytest.raises(EventValidationError):
        validate(env)


@pytest.mark.parametrize("event_type", ["promote", "demote"])
def test_validate_rejects_promote_demote_with_bool_score(event_type: str) -> None:
    """Defense in depth: ``True is 1`` so isinstance(True, int) is truthy.

    A boolean ``score_output`` is not a valid §8.2 score and must be rejected
    before the v2 trainer ingests a {True, False} signal as {1, 0}.
    """
    env = _promote_envelope() if event_type == "promote" else _demote_envelope()
    env["score_output"] = True
    with pytest.raises(EventValidationError):
        validate(env)


def test_emit_dispatches_validated_promote_event() -> None:
    captured: list[dict[str, Any]] = []
    emit(_promote_envelope(), sink=lambda e: captured.append(dict(e)))
    assert len(captured) == 1
    assert captured[0]["event_type"] == "promote"
    assert captured[0]["decision"] == "promoted_to_S3"


def test_emit_dispatches_validated_demote_event() -> None:
    captured: list[dict[str, Any]] = []
    emit(_demote_envelope(), sink=lambda e: captured.append(dict(e)))
    assert len(captured) == 1
    assert captured[0]["event_type"] == "demote"
    assert captured[0]["decision"] == "demoted"


# ---------------------------------------------------------------------------
# invalidate envelopes (P4)
# ---------------------------------------------------------------------------


def _invalidate_envelope() -> dict[str, Any]:
    """A complete ``invalidate`` envelope per scoring §8.1 + §8.2 + P4 per-type extras."""
    return {
        "event_id": "01890af0-0000-7000-8000-000000000003",
        "event_type": "invalidate",
        "tenant_id": "tenant-a",
        "ts_recorded": "2026-05-12T17:00:00Z",
        "ts_valid": "2026-05-12T17:00:00Z",
        "model_version": "v1.0.0",
        "weights_version": "sha256:0000000000000000",
        "contamination_protected": True,
        "fact_ids": ["fact-1"],
        "decision": "superseded",
        "superseded_by": "fact-2",
    }


def test_validate_accepts_full_invalidate_envelope() -> None:
    validate(_invalidate_envelope())


def test_validate_accepts_invalidate_with_null_superseded_by() -> None:
    """Hard invalidate (no successor): superseded_by may be None per gap-13."""
    env = _invalidate_envelope()
    env["superseded_by"] = None
    env["decision"] = "hard_invalidate"
    validate(env)


@pytest.mark.parametrize("missing_field", ["fact_ids", "decision", "superseded_by"])
def test_validate_rejects_invalidate_missing_per_type_extras(
    missing_field: str,
) -> None:
    env = _invalidate_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


def test_validate_rejects_invalidate_with_empty_fact_ids() -> None:
    env = _invalidate_envelope()
    env["fact_ids"] = []
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_invalidate_with_non_str_fact_ids() -> None:
    env = _invalidate_envelope()
    env["fact_ids"] = ["fact-1", 42]
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_invalidate_with_empty_decision() -> None:
    env = _invalidate_envelope()
    env["decision"] = ""
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_invalidate_with_empty_superseded_by_str() -> None:
    """superseded_by must be None OR a non-empty str — empty string is not legal."""
    env = _invalidate_envelope()
    env["superseded_by"] = ""
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_invalidate_with_non_str_superseded_by() -> None:
    env = _invalidate_envelope()
    env["superseded_by"] = 42
    with pytest.raises(EventValidationError):
        validate(env)


def test_emit_dispatches_validated_invalidate_event() -> None:
    captured: list[dict[str, Any]] = []
    emit(_invalidate_envelope(), sink=lambda e: captured.append(dict(e)))
    assert len(captured) == 1
    assert captured[0]["event_type"] == "invalidate"
    assert captured[0]["superseded_by"] == "fact-2"


# ---------------------------------------------------------------------------
# consolidate_phase envelopes (P4)
# ---------------------------------------------------------------------------


def _consolidate_phase_envelope() -> dict[str, Any]:
    """A complete ``consolidate_phase`` envelope per §8.1 + §8.2 + P4 per-type extras."""
    return {
        "event_id": "01890af0-0000-7000-8000-000000000004",
        "event_type": "consolidate_phase",
        "tenant_id": "tenant-a",
        "ts_recorded": "2026-05-12T17:00:00Z",
        "ts_valid": "2026-05-12T17:00:00Z",
        "model_version": "v1.0.0",
        "weights_version": "sha256:0000000000000000",
        "contamination_protected": True,
        "phase_name": "extract",
        "consolidate_run_id": "01890af0-0000-7000-8000-00000000aa01",
    }


def test_validate_accepts_full_consolidate_phase_envelope() -> None:
    validate(_consolidate_phase_envelope())


@pytest.mark.parametrize(
    "phase_name",
    ["extract", "score", "promote", "demote", "consolidate", "invalidate"],
)
def test_validate_accepts_all_six_canonical_phases(phase_name: str) -> None:
    """IMPL §2.4 invariant I-11: six canonical dream-daemon phases."""
    env = _consolidate_phase_envelope()
    env["phase_name"] = phase_name
    validate(env)


@pytest.mark.parametrize("missing_field", ["phase_name", "consolidate_run_id"])
def test_validate_rejects_consolidate_phase_missing_per_type_extras(
    missing_field: str,
) -> None:
    env = _consolidate_phase_envelope()
    del env[missing_field]
    with pytest.raises(EventValidationError) as excinfo:
        validate(env)
    assert missing_field in str(excinfo.value)


def test_validate_rejects_consolidate_phase_with_unknown_phase_name() -> None:
    env = _consolidate_phase_envelope()
    env["phase_name"] = "rerank"  # not one of the six §0 process row phases
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_consolidate_phase_with_non_str_phase_name() -> None:
    env = _consolidate_phase_envelope()
    env["phase_name"] = 42
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_consolidate_phase_with_empty_run_id() -> None:
    env = _consolidate_phase_envelope()
    env["consolidate_run_id"] = ""
    with pytest.raises(EventValidationError):
        validate(env)


def test_validate_rejects_consolidate_phase_with_non_str_run_id() -> None:
    env = _consolidate_phase_envelope()
    env["consolidate_run_id"] = 12345
    with pytest.raises(EventValidationError):
        validate(env)


def test_emit_dispatches_validated_consolidate_phase_event() -> None:
    captured: list[dict[str, Any]] = []
    emit(_consolidate_phase_envelope(), sink=lambda e: captured.append(dict(e)))
    assert len(captured) == 1
    assert captured[0]["event_type"] == "consolidate_phase"
    assert captured[0]["phase_name"] == "extract"


# ---------------------------------------------------------------------------
# Cross-cutting P4 invariants
# ---------------------------------------------------------------------------


def test_per_type_required_now_covers_six_of_seven_event_types() -> None:
    """Sanity-pin: at P4 only ``recall_outcome`` remains common-only."""
    from lethe.runtime.events import _PER_TYPE_REQUIRED, _VALID_EVENT_TYPES

    covered = set(_PER_TYPE_REQUIRED.keys())
    assert covered == _VALID_EVENT_TYPES - {"recall_outcome"}, (
        f"P4 contract: every §8.1 event type except recall_outcome has per-type extras; "
        f"got covered={sorted(covered)}, missing={sorted(_VALID_EVENT_TYPES - covered)}"
    )


def test_valid_consolidate_phases_pinned_to_six_canonical() -> None:
    """IMPL §2.4 invariant I-11: exactly the six dream-daemon phases."""
    from lethe.runtime.events import _VALID_CONSOLIDATE_PHASES

    expected = frozenset({"extract", "score", "promote", "demote", "consolidate", "invalidate"})
    assert expected == _VALID_CONSOLIDATE_PHASES
    assert len(_VALID_CONSOLIDATE_PHASES) == 6
