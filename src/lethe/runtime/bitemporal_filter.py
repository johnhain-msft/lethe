"""Bi-temporal validity filter (scoring §4.1; invariant I-4).

Applied **PRE-retriever**: facts whose validity window does not contain
``t_now`` are excluded from the candidate set entirely *before* any
ranker is consulted, so they cannot influence rank statistics or
absorb scoring budget. There is no "small store" shortcut — the filter
runs on every recall, regardless of candidate-set size.

The filter is a pure function over a candidate iterable. Order of
operations within the ``recall`` verb (commit 3) is asserted with a
recording-double test there; this module ships :func:`pre_retriever_apply`
as the documented invocation contract that the verb (and the verb's
test) consumes.

T_PURGE_DAYS = 90 is the documented retention grace — the window after
``valid_to`` during which an invalidated fact is kept in S2 for audit
and replay before a background sweeper hard-deletes it. The read-time
filter does NOT honor T_purge (an invalidated fact is invisible to
recall the moment ``valid_to <= t_now``); the constant is exposed here
so the future sweeper has a single source of truth.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any, Final, TypeVar

T_PURGE_DAYS: Final[int] = 90

#: Canonical key names the filter inspects on each fact mapping. Both
#: temporal columns are ISO-8601 strings (composition §5 — S2 stores
#: ts_recorded / valid_from / valid_to as UTC ISO-8601 with a trailing
#: ``Z``); ``valid_to`` may be ``None`` to indicate an open-ended fact.
_VALID_FROM: Final[str] = "valid_from"
_VALID_TO: Final[str] = "valid_to"

F = TypeVar("F", bound=Mapping[str, Any])


class BitemporalFilterError(Exception):
    """Raised when a fact is missing the temporal columns the filter requires."""


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp; Python 3.11+ accepts trailing ``Z``."""
    return datetime.fromisoformat(value)


def _is_valid(fact: Mapping[str, Any], *, t_now: datetime) -> bool:
    """Apply scoring §4.1: ``valid_from <= t_now AND (valid_to IS NULL OR valid_to > t_now)``.

    A missing ``valid_from`` raises (every persistent fact has one); a
    missing or ``None`` ``valid_to`` means "open-ended" and passes the
    upper-bound clause.
    """
    if _VALID_FROM not in fact:
        raise BitemporalFilterError(
            f"fact missing required column {_VALID_FROM!r}: {dict(fact)!r}"
        )
    valid_from = _parse_iso(str(fact[_VALID_FROM]))
    if valid_from > t_now:
        return False
    valid_to_raw = fact.get(_VALID_TO)
    if valid_to_raw is None:
        return True
    valid_to = _parse_iso(str(valid_to_raw))
    return valid_to > t_now


def filter_facts(facts: Iterable[F], *, t_now: datetime) -> list[F]:
    """Return the subset of ``facts`` whose validity window contains ``t_now``.

    The filter is total: every input is inspected; there is no
    early-exit for small inputs (invariant I-4 — the filter must run on
    every recall regardless of candidate-set size, so adversarial
    invalid-window facts cannot leak into the ranker by being part of a
    "trivially small" set).
    """
    return [f for f in facts if _is_valid(f, t_now=t_now)]


def is_purge_eligible(
    fact: Mapping[str, Any],
    *,
    t_now: datetime,
    t_purge_days: int = T_PURGE_DAYS,
) -> bool:
    """Return True iff ``fact`` is past the :data:`T_PURGE_DAYS` grace.

    Read-time recall ignores this; a future background sweeper will use
    it to decide which invalidated rows are safe to hard-delete from S2.
    Centralized here so the read filter and the sweeper share one
    definition of "old enough to purge".
    """
    valid_to_raw = fact.get(_VALID_TO)
    if valid_to_raw is None:
        return False
    valid_to = _parse_iso(str(valid_to_raw))
    return valid_to + timedelta(days=t_purge_days) <= t_now


def pre_retriever_apply(
    *,
    facts: Iterable[F],
    retriever: Callable[[list[F]], list[F]],
    t_now: datetime,
) -> list[F]:
    """Run the bi-temporal filter, then dispatch to ``retriever``.

    The contract this helper documents (and its test enforces) is:
    **the retriever callable is not invoked until** :func:`filter_facts`
    has fully returned. Recall-verb tests in commit 3 use this same
    helper or replicate the ordering with a recording double; this
    module's own test asserts the ordering directly.
    """
    filtered = filter_facts(facts, t_now=t_now)
    return retriever(filtered)


__all__ = [
    "BitemporalFilterError",
    "T_PURGE_DAYS",
    "filter_facts",
    "is_purge_eligible",
    "pre_retriever_apply",
]
