"""Tests for :mod:`lethe.runtime.classifier` (gap-12 §3 + §5 + §6).

Coverage map (dev sub-plan §7 exit gates 3 + 5):

- All 7 intent classes are returnable.
- gap-12 §6 decision-boundary table: one test per row.
- Caller-tag honored when LLM disagrees with confidence < 0.8.
- Caller-tag overridden when LLM objects with confidence ≥ 0.8.
- ``test_force_skip_bypasses_dispatch`` (gate 5).
- ``test_escalate_class_emitted_for_sensitive_payload`` (gate 3).
- LLM-residual via injected ``_FakeLLMClassifier`` (scripted dict).
- LLM timeout falls back to heuristic / caller-tag.
- :class:`NullLLMClassifier` raises ``NotImplementedError``.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any

import pytest

from lethe.runtime.classifier import (
    VALID_INTENT_CLASSES,
    ClassificationRequest,
    ClassificationResult,
    IntentClass,
    LLMClassification,
    NullLLMClassifier,
    classify,
)


class _FakeLLMClassifier:
    """Scripted LLM stand-in.

    ``script`` is the verdict returned on every call. ``delay_s`` is an
    artificial latency injected before returning, used to exercise the
    timeout path.
    """

    def __init__(
        self,
        script: LLMClassification,
        *,
        delay_s: float = 0.0,
    ) -> None:
        self.script = script
        self.delay_s = delay_s
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        *,
        tenant_id: str,
        payload: str,
        caller_tag: IntentClass | None,
    ) -> LLMClassification:
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "payload": payload,
                "caller_tag": caller_tag,
            }
        )
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        return self.script


def _req(
    payload: str,
    *,
    caller_tag: IntentClass | None = None,
    source_kind: str = "utterance",
    source_subtype: str | None = None,
    force_skip_classifier: bool = False,
) -> ClassificationRequest:
    return ClassificationRequest(
        tenant_id="t-test",
        payload=payload,
        caller_tag=caller_tag,
        source_kind=source_kind,  # type: ignore[arg-type]
        source_subtype=source_subtype,
        force_skip_classifier=force_skip_classifier,
    )


# ---------------------------------------------------------------------------
# Taxonomy surface
# ---------------------------------------------------------------------------


def test_valid_intent_classes_match_gap12_taxonomy() -> None:
    assert frozenset(
        {
            "drop",
            "reply_only",
            "peer_route",
            "escalate",
            "remember:fact",
            "remember:preference",
            "remember:procedure",
        }
    ) == VALID_INTENT_CLASSES


@pytest.mark.parametrize(
    "intent",
    [
        "drop",
        "reply_only",
        "peer_route",
        "escalate",
        "remember:fact",
        "remember:preference",
        "remember:procedure",
    ],
)
def test_all_seven_classes_are_returnable_via_llm(intent: IntentClass) -> None:
    fake = _FakeLLMClassifier(
        {"intent": intent, "score": 0.9, "rationale": "scripted"}
    )
    # Use a payload that defeats every heuristic short-circuit so the
    # LLM is consulted (long ambiguous utterance, no sensitive hit, no
    # peer/tool subtype).
    result = classify(
        _req("a sufficiently ambiguous payload to consult the LLM"),
        llm=fake,
    )
    assert result.intent == intent
    assert result.path == "llm"
    assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# Force-skip (exit gate 5)
# ---------------------------------------------------------------------------


def test_force_skip_bypasses_dispatch() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "drop", "score": 0.99, "rationale": "would-have-dropped"}
    )
    result = classify(
        _req(
            "Please remember this is important",
            caller_tag="remember:fact",
            force_skip_classifier=True,
        ),
        llm=fake,
    )
    assert result.intent == "remember:fact"
    assert result.path == "caller_tagged"
    assert result.audit_detail == "force_skip"
    assert fake.calls == [], "LLM must not be consulted when force_skip is set"


def test_force_skip_without_caller_tag_raises() -> None:
    with pytest.raises(ValueError, match="caller_tag"):
        classify(_req("anything", force_skip_classifier=True))


def test_force_skip_bypasses_even_sensitive_payload() -> None:
    # Locked decision: force_skip is the ONLY way to get past the
    # classifier; sensitive-regex would normally win but caller has
    # signed off (api §3.1 + deployment §6.3).
    result = classify(
        _req(
            "my password is hunter2",
            caller_tag="remember:fact",
            force_skip_classifier=True,
        )
    )
    assert result.intent == "remember:fact"
    assert result.path == "caller_tagged"
    assert result.audit_detail == "force_skip"


# ---------------------------------------------------------------------------
# Sensitive-regex escalate (exit gate 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "my SSN is 123456789",
        "credit card 4111111111111111 on file",
        "the password is hunter2",
        "use this api_key for the demo",
        "key prefix ghp_abcdef123456 leaked",
        "AKIAIOSFODNN7EXAMPLE was rotated",
    ],
)
def test_escalate_class_emitted_for_sensitive_payload(payload: str) -> None:
    result = classify(_req(payload))
    assert result.intent == "escalate"
    assert result.confidence == 1.0
    assert result.path == "heuristic"


def test_sensitive_payload_with_disagreeing_caller_tag_still_escalates() -> None:
    # gap-12 §6 row 5: escalate cannot be overridden by caller_tag.
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.9, "rationale": "scripted"}
    )
    result = classify(
        _req(
            "the password is rotated to hunter2",
            caller_tag="remember:fact",
        ),
        llm=fake,
    )
    assert result.intent == "escalate"
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Heuristic decision-boundary table (gap-12 §6)
# ---------------------------------------------------------------------------


def test_row1_short_utterance_drops() -> None:
    result = classify(_req("ok thanks"))
    assert result.intent == "drop"
    assert result.path == "heuristic"
    assert result.confidence >= 0.8


def test_row1_short_utterance_with_proper_noun_does_not_drop() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.85, "rationale": "name mentioned"}
    )
    result = classify(_req("Hi Alice", caller_tag=None), llm=fake)
    # Heuristic does NOT drop (has proper noun) → LLM consulted.
    assert fake.calls, "LLM must be consulted when proper-noun bypasses drop"
    assert result.intent == "remember:fact"


def test_row1_short_utterance_with_digit_does_not_drop() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.85, "rationale": "has digit"}
    )
    result = classify(_req("PIN 4271"), llm=fake)
    assert fake.calls, "LLM must be consulted when digit bypasses drop"
    assert result.intent == "remember:fact"


def test_row2_peer_message_info_replies_only() -> None:
    result = classify(
        _req(
            "Just letting you know we shipped the release",
            source_kind="peer_message",
            source_subtype="info",
        )
    )
    assert result.intent == "reply_only"
    assert result.path == "heuristic"
    assert result.confidence >= 0.8


def test_row3_peer_message_claim_consults_llm() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.9, "rationale": "valid claim"}
    )
    result = classify(
        _req(
            "Database X is owned by team Y",
            source_kind="peer_message",
            source_subtype="claim",
        ),
        llm=fake,
    )
    assert result.intent == "remember:fact"
    assert result.path == "llm"
    assert fake.calls, "claim subtype must invoke the LLM"


def test_row4_idempotent_tool_call_becomes_procedure() -> None:
    result = classify(
        _req(
            "Index rebuild completed in 3.2s",
            source_kind="tool_call_result",
            source_subtype="idempotent",
        )
    )
    assert result.intent == "remember:procedure"
    assert result.path == "heuristic"
    assert result.confidence >= 0.8


def test_row4_nonidempotent_tool_call_consults_llm() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "reply_only", "score": 0.85, "rationale": "log line"}
    )
    result = classify(
        _req(
            "POST /widgets returned 201 created",
            source_kind="tool_call_result",
            source_subtype=None,
        ),
        llm=fake,
    )
    assert result.path == "llm"
    assert fake.calls


def test_row7_ambiguous_utterance_consults_llm() -> None:
    fake = _FakeLLMClassifier(
        {
            "intent": "remember:preference",
            "score": 0.9,
            "rationale": "stated preference",
        }
    )
    result = classify(
        _req("I usually prefer dark mode in my IDE"),
        llm=fake,
    )
    assert result.intent == "remember:preference"
    assert result.path == "llm"


# ---------------------------------------------------------------------------
# Caller-tag honor rule (api §3.1 line 502)
# ---------------------------------------------------------------------------


def test_caller_tag_honored_when_llm_disagrees_below_threshold() -> None:
    fake = _FakeLLMClassifier(
        {
            "intent": "reply_only",
            "score": 0.6,
            "rationale": "borderline call",
        }
    )
    result = classify(
        _req(
            "The Q3 ARR target was set at 12.5M",
            caller_tag="remember:fact",
        ),
        llm=fake,
    )
    assert result.intent == "remember:fact"
    assert result.path == "caller_tagged"
    assert result.audit_detail == "caller_override"


def test_caller_tag_overridden_when_llm_objects_at_or_above_threshold() -> None:
    fake = _FakeLLMClassifier(
        {
            "intent": "reply_only",
            "score": 0.85,
            "rationale": "confidently disagrees",
        }
    )
    result = classify(
        _req(
            "Just a casual aside about the weather today",
            caller_tag="remember:fact",
        ),
        llm=fake,
    )
    assert result.intent == "reply_only"
    assert result.path == "llm"


def test_caller_tag_agrees_with_llm_returns_llm_path() -> None:
    fake = _FakeLLMClassifier(
        {
            "intent": "remember:fact",
            "score": 0.65,
            "rationale": "matches caller",
        }
    )
    result = classify(
        _req("The repo lives at github.com/acme/widgets", caller_tag="remember:fact"),
        llm=fake,
    )
    assert result.intent == "remember:fact"
    # Agreement → no caller_override; emit LLM path.
    assert result.path == "llm"
    assert result.audit_detail == ""


# ---------------------------------------------------------------------------
# LLM timeout / NotImplementedError fallback
# ---------------------------------------------------------------------------


def test_llm_timeout_falls_back_to_heuristic_when_no_caller_tag() -> None:
    slow = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.9, "rationale": "would-have-stored"},
        delay_s=0.5,
    )
    result = classify(
        _req("An ambiguous statement awaiting model arbitration"),
        llm=slow,
        llm_timeout_s=0.05,
    )
    assert result.path == "heuristic"
    assert result.audit_detail == "llm_unavailable"
    assert result.intent in VALID_INTENT_CLASSES


def test_llm_timeout_honors_caller_tag_when_present() -> None:
    slow = _FakeLLMClassifier(
        {"intent": "drop", "score": 0.9, "rationale": "would-drop"},
        delay_s=0.5,
    )
    result = classify(
        _req(
            "An ambiguous statement awaiting model arbitration",
            caller_tag="remember:preference",
        ),
        llm=slow,
        llm_timeout_s=0.05,
    )
    assert result.intent == "remember:preference"
    assert result.path == "caller_tagged"
    assert result.audit_detail == "llm_unavailable"


def test_null_llm_classifier_falls_back() -> None:
    # No `llm` injected → NullLLMClassifier used → NotImplementedError →
    # treated like timeout.
    result = classify(_req("An ambiguous statement awaiting model arbitration"))
    assert result.path == "heuristic"
    assert result.audit_detail == "llm_unavailable"


def test_null_llm_classifier_raises_directly() -> None:
    with pytest.raises(NotImplementedError, match="P7"):
        NullLLMClassifier()(
            tenant_id="t-test",
            payload="anything",
            caller_tag=None,
        )


# ---------------------------------------------------------------------------
# Result envelope shape
# ---------------------------------------------------------------------------


def test_result_is_frozen_dataclass() -> None:
    result = classify(_req("ok thanks"))
    assert isinstance(result, ClassificationResult)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.intent = "drop"  # type: ignore[misc]


def test_invalid_llm_intent_is_rejected() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:everything", "score": 0.9, "rationale": "bogus"}  # type: ignore[typeddict-item]
    )
    with pytest.raises(ValueError, match="taxonomy"):
        classify(
            _req("An ambiguous statement awaiting model arbitration"),
            llm=fake,
        )


def test_invalid_llm_score_is_rejected() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 1.5, "rationale": "bogus"}
    )
    with pytest.raises(ValueError, match="0.0, 1.0"):
        classify(
            _req("An ambiguous statement awaiting model arbitration"),
            llm=fake,
        )


def test_llm_call_receives_request_fields() -> None:
    fake = _FakeLLMClassifier(
        {"intent": "remember:fact", "score": 0.9, "rationale": "ok"}
    )
    classify(
        _req(
            "An ambiguous statement awaiting model arbitration",
            caller_tag="remember:fact",
        ),
        llm=fake,
    )
    assert fake.calls[0]["tenant_id"] == "t-test"
    assert "ambiguous" in fake.calls[0]["payload"]
    assert fake.calls[0]["caller_tag"] == "remember:fact"
