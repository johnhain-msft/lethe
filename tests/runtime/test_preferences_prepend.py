"""Preferences-prepend coverage (gap-09 §6 "always-load bandwidth" cap).

Covers:

- 10 KB cap honored: pages whose cumulative byte total exceeds
  :data:`PREFERENCES_CAP_BYTES` cause :attr:`PreferencesEnvelope.truncated`
  to flip to ``True``.
- Recency-of-revision ordering: the most-recently-revised pages survive
  the cap; older pages drop out (gap-09 §6 "most-recent-revision-wins").
- Empty-source default returns a zero-page envelope without raising.
- Cap override via ``cap_bytes=...`` (deployment §249 tenant_config seam).
- Stable ``page_uri`` tie-breaker on identical ``revised_at`` so the
  envelope is deterministic across invocations.
- Defensive validation: zero/negative cap raises; negative page bytes
  raise.
"""

from __future__ import annotations

import pytest

from lethe.runtime.preferences_prepend import (
    EMPTY_PREFERENCE_SOURCE,
    PREFERENCES_CAP_BYTES,
    PreferencePage,
    build_envelope,
)


def _page(uri: str, revised_at: str, content: str = "x") -> PreferencePage:
    """Compact factory; ``bytes`` defaults to UTF-8 length of ``content``."""
    return PreferencePage(
        page_uri=uri,
        content=content,
        kind="preference",
        revision_id=f"rev-{uri}",
        revised_at=revised_at,
        bytes=len(content.encode("utf-8")),
    )


def test_empty_input_returns_empty_envelope() -> None:
    env = build_envelope([])
    assert env.pages == []
    assert env.total_bytes == 0
    assert env.truncated is False


def test_under_cap_keeps_all_pages_in_recency_order() -> None:
    pages = [
        _page("a", "2025-01-01T00:00:00.000Z", "alpha"),
        _page("b", "2025-03-01T00:00:00.000Z", "beta"),
        _page("c", "2025-02-01T00:00:00.000Z", "gamma"),
    ]
    env = build_envelope(pages)
    assert env.truncated is False
    assert [p.page_uri for p in env.pages] == ["b", "c", "a"]
    assert env.total_bytes == sum(p.bytes for p in pages)


def test_truncates_on_cap_overflow_and_drops_older_pages() -> None:
    big_a = _page("a", "2025-03-01T00:00:00.000Z", content="A" * 6000)
    big_b = _page("b", "2025-02-01T00:00:00.000Z", content="B" * 6000)
    older = _page("c", "2025-01-01T00:00:00.000Z", content="C" * 100)

    env = build_envelope([big_a, big_b, older])

    # Recency order: a (Mar) kept; b (Feb) would push past 10 KB → break.
    # c (Jan) is older than b so it's also dropped (greedy by recency).
    assert [p.page_uri for p in env.pages] == ["a"]
    assert env.truncated is True
    assert env.total_bytes == 6000


def test_truncated_is_false_only_when_every_page_kept() -> None:
    page = _page("a", "2025-01-01T00:00:00.000Z", content="x" * 100)
    env = build_envelope([page])
    assert env.truncated is False
    assert env.total_bytes == 100


def test_recency_ordering_is_descending_by_revised_at() -> None:
    pages = [
        _page("oldest", "2024-06-01T00:00:00.000Z"),
        _page("newest", "2025-12-31T23:59:59.999Z"),
        _page("middle", "2025-01-01T12:00:00.000Z"),
    ]
    env = build_envelope(pages)
    assert [p.page_uri for p in env.pages] == ["newest", "middle", "oldest"]


def test_revised_at_tie_broken_by_page_uri_descending() -> None:
    """Equal ``revised_at`` → ``page_uri`` lex-desc tiebreak (deterministic).

    The envelope must be byte-identical across invocations even when two
    pages share a revision timestamp, so the order is fully specified.
    """
    pages = [
        _page("a", "2025-01-01T00:00:00.000Z"),
        _page("b", "2025-01-01T00:00:00.000Z"),
        _page("c", "2025-01-01T00:00:00.000Z"),
    ]
    env_first = build_envelope(pages)
    env_second = build_envelope(list(reversed(pages)))
    assert [p.page_uri for p in env_first.pages] == ["c", "b", "a"]
    assert [p.page_uri for p in env_second.pages] == ["c", "b", "a"]


def test_cap_override_honored() -> None:
    """Tenant-config ``preference_cap_bytes`` override (deployment §249)."""
    pages = [
        _page("a", "2025-03-01T00:00:00.000Z", content="A" * 200),
        _page("b", "2025-02-01T00:00:00.000Z", content="B" * 200),
    ]
    env = build_envelope(pages, cap_bytes=300)
    # 200 fits, second 200 would total 400 > 300 → break.
    assert [p.page_uri for p in env.pages] == ["a"]
    assert env.truncated is True
    assert env.total_bytes == 200


def test_single_oversized_page_drops_with_truncated_flag() -> None:
    """A single page bigger than the cap is dropped and flagged."""
    pages = [_page("huge", "2025-01-01T00:00:00.000Z", content="x" * 99999)]
    env = build_envelope(pages, cap_bytes=PREFERENCES_CAP_BYTES)
    assert env.pages == []
    assert env.truncated is True
    assert env.total_bytes == 0


def test_invalid_cap_raises() -> None:
    with pytest.raises(ValueError, match="cap_bytes must be positive"):
        build_envelope([], cap_bytes=0)
    with pytest.raises(ValueError, match="cap_bytes must be positive"):
        build_envelope([], cap_bytes=-1)


def test_negative_page_bytes_raises() -> None:
    bad = PreferencePage(
        page_uri="x",
        content="",
        kind="preference",
        revision_id="rev-x",
        revised_at="2025-01-01T00:00:00.000Z",
        bytes=-1,
    )
    with pytest.raises(ValueError, match="negative bytes"):
        build_envelope([bad])


def test_empty_preference_source_yields_empty_list() -> None:
    """The default no-S4a tenant gets a deterministic zero-page result."""
    pages = EMPTY_PREFERENCE_SOURCE.list_preferences(tenant_id="tenant-a")
    assert pages == []
    env = build_envelope(pages)
    assert env.pages == []
    assert env.truncated is False
    assert env.total_bytes == 0


def test_cap_constant_is_10_kb() -> None:
    """Lock the gap-09 §6 cap value so a future drift causes a test failure."""
    assert PREFERENCES_CAP_BYTES == 10240
