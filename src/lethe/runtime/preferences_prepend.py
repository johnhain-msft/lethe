"""Always-load preference prepend (composition §3.5; gap-09 §6).

Every successful ``recall`` response carries a ``preferences[]`` array
distinct from ``facts[]`` so that callers cannot confuse a user-asserted
preference with a graph-derived fact (composition §3.5 step 2).
gap-09 §6 caps the total preference payload at 10 KB per tenant
(``PREFERENCES_CAP_BYTES``) and resolves over-cap by **recency-of-
revision** truncation: the most-recently-revised pages are kept; older
pages drop out and the response surfaces ``preferences_truncated=True``
so the caller knows context is incomplete.

The recall verb consumes a :class:`PreferenceSource` Protocol; the
production S4a wiring (qmd-class index over ``kind=preference|prohibition``
markdown pages) lands at the S4a phase. Tenants without an S4a store
get :data:`EMPTY_PREFERENCE_SOURCE`, which yields a zero-page envelope
on every call.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal, Protocol

#: gap-09 §6 "always-load bandwidth" cap. 10 KB = 10 240 bytes.
PREFERENCES_CAP_BYTES: Final[int] = 10240

PreferenceKind = Literal["preference", "prohibition"]


@dataclass(frozen=True)
class PreferencePage:
    """A single S4a preference page (composition §3.5).

    ``revised_at`` is an ISO-8601 timestamp string (UTC, ``Z`` suffix);
    string comparison is well-defined for sort because ISO-8601 sorts
    chronologically lexicographically when zone-normalized.

    ``bytes`` is the page's contribution to the ``PREFERENCES_CAP_BYTES``
    budget — the source-of-truth for cap accounting; the caller computes
    it once at fetch time so the envelope builder doesn't have to choose
    an encoding (UTF-8 byte length is the convention).
    """

    page_uri: str
    content: str
    kind: PreferenceKind
    revision_id: str
    revised_at: str
    bytes: int


@dataclass(frozen=True)
class PreferencesEnvelope:
    """The composition §3.5 ``preferences[]`` payload + cap accounting.

    ``total_bytes`` is the sum of kept page byte counts (always
    ``<= PREFERENCES_CAP_BYTES``); ``truncated`` is ``True`` iff at
    least one page was dropped — either because it would have busted
    the cap or because a less-recently-revised page came after the
    first cap overflow.
    """

    pages: list[PreferencePage]
    total_bytes: int
    truncated: bool


class PreferenceSource(Protocol):
    """The substrate the recall verb consumes for preference pages."""

    def list_preferences(self, *, tenant_id: str) -> list[PreferencePage]: ...


class _EmptyPreferenceSource:
    """The default source for tenants without an S4a substrate."""

    def list_preferences(self, *, tenant_id: str) -> list[PreferencePage]:
        return []


EMPTY_PREFERENCE_SOURCE: Final[PreferenceSource] = _EmptyPreferenceSource()


def build_envelope(
    pages: Iterable[PreferencePage],
    *,
    cap_bytes: int = PREFERENCES_CAP_BYTES,
) -> PreferencesEnvelope:
    """Pack ``pages`` greedily by descending ``revised_at`` until the cap.

    Semantics:

    - Sort by ``revised_at`` **descending** (most recent revision first).
    - Walk the sorted list and keep each page whose addition would not
      exceed ``cap_bytes``. Stop at the first page that would bust the
      cap; mark ``truncated=True`` and drop that page **and all
      subsequent (less-recently-revised) pages**.
    - This preserves recency-of-revision ordering: if two preferences
      contradict, the more recent one wins (gap-09 §6 first bullet —
      "most-recent-revision-wins").
    - If a single page is itself larger than ``cap_bytes`` it gets
      dropped and ``truncated=True``; subsequent (older) pages are also
      dropped because we stop at the first overflow.

    Stable across ties on ``revised_at`` via ``page_uri`` lexicographic
    fallback so the envelope is deterministic across invocations.

    Raises:
        ValueError: ``cap_bytes`` is non-positive.
    """
    if cap_bytes <= 0:
        raise ValueError(f"build_envelope: cap_bytes must be positive, got {cap_bytes}")

    sorted_pages = sorted(pages, key=lambda p: (p.revised_at, p.page_uri), reverse=True)
    kept: list[PreferencePage] = []
    running = 0
    truncated = False
    for page in sorted_pages:
        if page.bytes < 0:
            raise ValueError(
                f"build_envelope: page {page.page_uri!r} has negative bytes={page.bytes}"
            )
        if running + page.bytes > cap_bytes:
            truncated = True
            break
        kept.append(page)
        running += page.bytes
    return PreferencesEnvelope(pages=kept, total_bytes=running, truncated=truncated)


__all__ = [
    "EMPTY_PREFERENCE_SOURCE",
    "PREFERENCES_CAP_BYTES",
    "PreferenceKind",
    "PreferencePage",
    "PreferenceSource",
    "PreferencesEnvelope",
    "build_envelope",
]
