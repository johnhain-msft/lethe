"""Intent classifier implementation (gap-12 §5 + §6; api §3.1 step 3).

Heuristic-first, LLM-residual classifier for the ``remember`` write
path. The 7-class taxonomy (§3) and the §6 decision-boundary table are
the contract; this module is the implementation.

Dispatch order (gap-12 §5 + §6; api §3.1 step 3 + line 502):

1. ``force_skip_classifier=True`` — honor the caller's tag directly. The
   caller MUST supply a ``caller_tag`` in this case (the audit row for
   the bypass is written by ``remember.py`` at commit 4 — this module
   does not touch ``audit_log``). Returns
   ``path="caller_tagged"``, ``audit_detail="force_skip"``.
2. **Sensitive-regex hit** (gap-12 §6 row 5; gap-11 §3.3): payload
   matches a sensitive-class pattern → ``escalate`` with confidence
   1.0. Cannot be overridden by ``caller_tag``; the LLM is not invoked.
3. **Heuristic layer** (gap-12 §6 rows 1-4 + row 7 default): rule-based
   scoring on length, source kind, and source subtype. If the top class
   is ≥ 0.8 confidence the heuristic verdict is returned with
   ``path="heuristic"``.
4. **LLM-residual** with ``llm_timeout_s`` deadline (gap-12 §7 names 200
   ms median): the injected :class:`LLMClassifier` is invoked in a
   single-worker thread executor; ``result(timeout=…)`` enforces the
   deadline. On success:
     - If ``caller_tag`` is set and the LLM verdict differs with
       confidence < 0.8: honor ``caller_tag`` (api §3.1 line 502 —
       "Caller-supplied intent is honored only if classifier audit
       confidence is < 0.8 *against* the caller's tag"). Returns
       ``path="caller_tagged"``.
     - Else: return the LLM verdict with ``path="llm"``.
5. **LLM timeout or NotImplementedError**: if ``caller_tag`` is set,
   honor it (best fallback); else return the heuristic's top class as
   ``path="heuristic"`` with ``audit_detail="llm_unavailable"``.

The public response shape (api §3.1 line 486) names exactly three
``path`` values: ``"heuristic" | "llm" | "caller_tagged"``. The richer
``audit_detail`` field on :class:`ClassificationResult` is for the audit
trail only — ``remember.py`` collapses it for the public response.

The LLM seam is a stdlib-only ``concurrent.futures.ThreadPoolExecutor``
(plan §4). Per-call executor instantiation is a known trade-off (P7
transport-surface refactor is the canonical home for a long-lived loop);
``shutdown(wait=False)`` avoids blocking on a hung LLM call.
"""

from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass
from typing import Final, Literal, Protocol, TypedDict, get_args

IntentClass = Literal[
    "drop",
    "reply_only",
    "peer_route",
    "escalate",
    "remember:fact",
    "remember:preference",
    "remember:procedure",
]

VALID_INTENT_CLASSES: Final[frozenset[str]] = frozenset(get_args(IntentClass))

SourceKind = Literal["utterance", "peer_message", "tool_call_result"]

ClassificationPath = Literal["heuristic", "llm", "caller_tagged"]

# Confidence floor above which a verdict is treated as "unambiguous"
# (gap-12 §6 row 7 + line 502 in api §3.1).
_DECISION_THRESHOLD: Final[float] = 0.8

# Default LLM-residual deadline (gap-12 §7 v1 budget).
DEFAULT_LLM_TIMEOUT_S: Final[float] = 0.2

# Short-utterance length threshold (gap-12 §6 row 1).
_SHORT_UTTERANCE_LEN: Final[int] = 16

# Sensitive-class regex seed set (gap-11 §3.3 owns the canonical
# taxonomy; WS8/P7 ships the production list — this is the P2 starter
# set sufficient for the classifier-escape exit gate). Each pattern is
# case-insensitive substring; a single hit escalates the whole payload.
_SENSITIVE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # Long numeric strings (SSN-like / credit-card-like; ≥9 consecutive digits).
    re.compile(r"\d{9,}"),
    # Common API-key prefixes (GitHub, OpenAI-style, Slack, AWS).
    re.compile(r"\b(sk-|ghp_|gho_|ghs_|xoxb-|xoxp-|AKIA)[A-Za-z0-9]{8,}\b"),
    # Sensitive keyword stems.
    re.compile(
        r"\b(password|passwd|secret|api[_\- ]?key|private[_\- ]?key|"
        r"ssn|social[_\- ]?security|credit[_\- ]?card)\b",
        re.IGNORECASE,
    ),
)

_PROPER_NOUN_OR_DIGIT_RE: Final[re.Pattern[str]] = re.compile(
    r"\d|\b[A-Z][a-z]+",
)


class LLMClassification(TypedDict):
    """LLM-classifier verdict (plan §4).

    ``intent`` MUST be a member of :data:`VALID_INTENT_CLASSES`. ``score``
    is the classifier's self-reported confidence in [0.0, 1.0].
    ``rationale`` is a short freeform string used only for the audit
    trail — it is NEVER surfaced to the api §3.1 response envelope.
    """

    intent: IntentClass
    score: float
    rationale: str


class LLMClassifier(Protocol):
    """Injectable LLM callable for the residual layer (plan §4).

    Implementations MUST return within the deadline that the dispatcher
    enforces. Implementations MUST be pure with respect to the input —
    same ``(tenant_id, payload, caller_tag)`` triple yields the same
    output, so deterministic test fakes are usable verbatim as
    production-shape callables.
    """

    def __call__(
        self,
        *,
        tenant_id: str,
        payload: str,
        caller_tag: IntentClass | None,
    ) -> LLMClassification: ...


class NullLLMClassifier:
    """Default production LLM classifier — raises until P7 wires the host.

    Locked decision #2 in the facilitator P2 plan: the production LLM
    callable is the host-runtime model channel, wired in at P7. Until
    then this stub raises :class:`NotImplementedError`, which the
    dispatcher treats the same as a timeout (fall back to the heuristic
    verdict and tag ``audit_detail="llm_unavailable"``).
    """

    def __call__(
        self,
        *,
        tenant_id: str,
        payload: str,
        caller_tag: IntentClass | None,
    ) -> LLMClassification:
        raise NotImplementedError(
            "LLM classifier not configured; host-runtime wiring lands at P7 "
            "transport surface (gap-12 §5)"
        )


@dataclass(frozen=True)
class ClassificationRequest:
    """Input envelope for :func:`classify`.

    ``payload`` is the raw write content; the classifier consumes it as
    a string. ``caller_tag`` is the optional caller-declared intent
    (api §3.1 ``intent?`` parameter). ``source_kind`` /
    ``source_subtype`` carry the gap-12 §6 decision-table dimensions
    (peer-message ``info``/``claim`` distinction, tool-call ``idempotent``
    flag). ``force_skip_classifier`` is the api §3.1 / deployment §6.3
    bypass; when True the caller's tag is honored verbatim.
    """

    tenant_id: str
    payload: str
    caller_tag: IntentClass | None = None
    source_kind: SourceKind = "utterance"
    source_subtype: str | None = None
    force_skip_classifier: bool = False


@dataclass(frozen=True)
class ClassificationResult:
    """Output envelope from :func:`classify`.

    ``path`` is the api §3.1 line 486 enum surfaced in
    ``RememberResponse.classified_intent.path``. ``audit_detail`` is an
    internal-only string that ``remember.py`` may log to ``audit_log``
    but never include in the api response envelope — values include
    ``""`` (no extra context), ``"force_skip"``, ``"llm_unavailable"``,
    and ``"caller_override"`` (LLM disagreed but with confidence < 0.8).
    """

    intent: IntentClass
    confidence: float
    path: ClassificationPath
    rationale: str
    audit_detail: str = ""


@dataclass(frozen=True)
class _HeuristicVerdict:
    intent: IntentClass
    confidence: float
    rationale: str


def _sensitive_hit(payload: str) -> bool:
    return any(pattern.search(payload) for pattern in _SENSITIVE_PATTERNS)


def _has_digit_or_proper_noun(payload: str) -> bool:
    return bool(_PROPER_NOUN_OR_DIGIT_RE.search(payload))


def _heuristic(req: ClassificationRequest) -> _HeuristicVerdict:
    """Apply gap-12 §6 boundary rules and return a scored verdict.

    Confidence semantics:

    - 0.9 - 1.0: deterministic rule (sensitive-regex, peer info,
      tool-call ``idempotent`` — caller does not need to consult LLM).
    - 0.4 - 0.5: ambiguous; LLM-residual should be invoked.
    """
    payload = req.payload

    # gap-12 §6 row 1: short utterance with no digit / proper noun → drop.
    if (
        req.source_kind == "utterance"
        and len(payload.strip()) < _SHORT_UTTERANCE_LEN
        and not _has_digit_or_proper_noun(payload)
    ):
        return _HeuristicVerdict(
            intent="drop",
            confidence=0.95,
            rationale="utterance shorter than 16 chars with no digit/proper noun",
        )

    # gap-12 §6 row 2: peer_message info → reply_only.
    if req.source_kind == "peer_message" and req.source_subtype == "info":
        return _HeuristicVerdict(
            intent="reply_only",
            confidence=0.9,
            rationale="peer_message subtype=info — recipient observes, does not store",
        )

    # gap-12 §6 row 4: tool-call result marked idempotent → remember:procedure.
    if (
        req.source_kind == "tool_call_result"
        and req.source_subtype == "idempotent"
    ):
        return _HeuristicVerdict(
            intent="remember:procedure",
            confidence=0.9,
            rationale="tool_call_result marked idempotent",
        )

    # gap-12 §6 row 3: peer_message claim → LLM (heuristic is ambiguous).
    if req.source_kind == "peer_message" and req.source_subtype == "claim":
        return _HeuristicVerdict(
            intent="remember:fact",
            confidence=0.4,
            rationale="peer_message subtype=claim — ambiguous, awaiting LLM verdict",
        )

    # gap-12 §6 row 4 default: non-idempotent tool-call result → LLM.
    if req.source_kind == "tool_call_result":
        return _HeuristicVerdict(
            intent="reply_only",
            confidence=0.5,
            rationale="tool_call_result without idempotent marker — ambiguous",
        )

    # gap-12 §6 row 7 default: ambiguous utterance — favor remember:fact at
    # low confidence so the LLM-residual is consulted.
    return _HeuristicVerdict(
        intent="remember:fact",
        confidence=0.5,
        rationale="utterance default — awaiting LLM verdict",
    )


def _validate_llm_verdict(verdict: LLMClassification) -> None:
    intent = verdict.get("intent")
    score = verdict.get("score")
    if intent not in VALID_INTENT_CLASSES:
        raise ValueError(
            f"LLM verdict intent {intent!r} is not in the gap-12 §3 taxonomy"
        )
    if not isinstance(score, int | float) or not 0.0 <= float(score) <= 1.0:
        raise ValueError(
            f"LLM verdict score {score!r} must be a float in [0.0, 1.0]"
        )


def _call_llm_with_timeout(
    llm: LLMClassifier,
    *,
    tenant_id: str,
    payload: str,
    caller_tag: IntentClass | None,
    timeout_s: float,
) -> LLMClassification | None:
    """Run the LLM call under a hard deadline.

    Returns the verdict on success, or None on
    :class:`concurrent.futures.TimeoutError` / :class:`NotImplementedError`.
    The executor is shut down non-blocking so a hung LLM thread cannot
    stall the caller; the thread is leaked deliberately (P7
    transport-surface refactor is the canonical home for a long-lived
    executor).
    """
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="lethe-llm-classifier"
    )
    try:
        future = executor.submit(
            llm,
            tenant_id=tenant_id,
            payload=payload,
            caller_tag=caller_tag,
        )
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            return None
        except NotImplementedError:
            return None
    finally:
        executor.shutdown(wait=False)


def classify(
    request: ClassificationRequest,
    *,
    llm: LLMClassifier | None = None,
    llm_timeout_s: float = DEFAULT_LLM_TIMEOUT_S,
) -> ClassificationResult:
    """Classify intent for a ``remember`` candidate (gap-12 §5 + §6).

    See module docstring for the full dispatch order. The ``llm``
    keyword is optional; when ``None`` an internal
    :class:`NullLLMClassifier` is used, which means any path that would
    consult the LLM falls back to the heuristic verdict (``path``
    becomes ``"heuristic"`` and ``audit_detail`` is ``"llm_unavailable"``).
    """
    # Step 1: force_skip_classifier — honor the caller tag.
    if request.force_skip_classifier:
        if request.caller_tag is None:
            raise ValueError(
                "force_skip_classifier=True requires a caller_tag "
                "(api §3.1 + deployment §6.3)"
            )
        return ClassificationResult(
            intent=request.caller_tag,
            confidence=1.0,
            path="caller_tagged",
            rationale="force_skip_classifier=True; caller tag honored verbatim",
            audit_detail="force_skip",
        )

    # Step 2: sensitive-regex escalate (cannot be overridden).
    if _sensitive_hit(request.payload):
        return ClassificationResult(
            intent="escalate",
            confidence=1.0,
            path="heuristic",
            rationale="sensitive-class regex match (gap-11 §3.3)",
        )

    # Step 3: heuristic layer.
    heuristic = _heuristic(request)
    if heuristic.confidence >= _DECISION_THRESHOLD:
        return ClassificationResult(
            intent=heuristic.intent,
            confidence=heuristic.confidence,
            path="heuristic",
            rationale=heuristic.rationale,
        )

    # Step 4: LLM-residual.
    active_llm: LLMClassifier = llm if llm is not None else NullLLMClassifier()
    llm_verdict = _call_llm_with_timeout(
        active_llm,
        tenant_id=request.tenant_id,
        payload=request.payload,
        caller_tag=request.caller_tag,
        timeout_s=llm_timeout_s,
    )

    if llm_verdict is None:
        # Step 5: LLM unavailable (timeout or NotImplementedError).
        if request.caller_tag is not None:
            return ClassificationResult(
                intent=request.caller_tag,
                confidence=heuristic.confidence,
                path="caller_tagged",
                rationale="LLM unavailable; caller tag honored as best fallback",
                audit_detail="llm_unavailable",
            )
        return ClassificationResult(
            intent=heuristic.intent,
            confidence=heuristic.confidence,
            path="heuristic",
            rationale=heuristic.rationale,
            audit_detail="llm_unavailable",
        )

    _validate_llm_verdict(llm_verdict)
    llm_intent: IntentClass = llm_verdict["intent"]
    llm_score = float(llm_verdict["score"])
    llm_rationale = str(llm_verdict.get("rationale", ""))

    # api §3.1 line 502: caller_tag is honored UNLESS the classifier
    # objects with confidence ≥ 0.8 *against* the caller's tag.
    if (
        request.caller_tag is not None
        and llm_intent != request.caller_tag
        and llm_score < _DECISION_THRESHOLD
    ):
        return ClassificationResult(
            intent=request.caller_tag,
            confidence=llm_score,
            path="caller_tagged",
            rationale=(
                "LLM disagreed (intent="
                f"{llm_intent}, score={llm_score:.2f}) but below the 0.8 "
                "objection threshold; caller tag honored (api §3.1)"
            ),
            audit_detail="caller_override",
        )

    return ClassificationResult(
        intent=llm_intent,
        confidence=llm_score,
        path="llm",
        rationale=llm_rationale,
    )
