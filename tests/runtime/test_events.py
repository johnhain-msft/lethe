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


@pytest.mark.parametrize(
    "missing_field", ["fact_ids", "decision", "provenance"]
)
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
    """Per-type extras are only enforced for event types whose owning verb has landed."""
    env = _remember_envelope()
    env["event_type"] = "promote"
    # Strip the remember-specific extras; promote has no per-type extras at P2.
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
