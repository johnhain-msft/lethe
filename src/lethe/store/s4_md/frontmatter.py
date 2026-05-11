"""S4 YAML frontmatter parse/serialize + stable-URI minting.

The on-disk format is the standard ``---\\nyaml\\n---\\nbody`` envelope used by
Jekyll, Hugo, qmd, and many static-site tools. We use PyYAML rather than
``python-frontmatter`` because the latter is a thin wrapper that adds version
churn for ~30 LOC of work (per plan.md §B2 rejection rationale).

Stable URI minting derives a deterministic ``s4a://<tenant_id>/<relpath>``
identifier from ``(tenant_id, path-relative-to-s4a-dir)``. Determinism is
required so the graph (S1) can cite the same page across consolidations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# The frontmatter envelope: opening `---`, YAML body, closing `---`, then
# the markdown body. We accept either LF or CRLF line endings on read; we
# write LF.
_ENVELOPE_RE = re.compile(
    r"\A---\s*\r?\n(?P<yaml>.*?)\r?\n---\s*\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass(frozen=True)
class Frontmatter:
    """Parsed frontmatter document."""

    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""


def load(path: Path) -> Frontmatter:
    """Parse a markdown file with optional YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    match = _ENVELOPE_RE.match(text)
    if match is None:
        # No frontmatter present — entire file is body.
        return Frontmatter(metadata={}, body=text)
    raw_yaml = match.group("yaml")
    body = match.group("body")
    parsed = yaml.safe_load(raw_yaml) if raw_yaml.strip() else {}
    if parsed is not None and not isinstance(parsed, dict):
        raise ValueError(
            f"Frontmatter YAML must be a mapping, got {type(parsed).__name__}"
        )
    return Frontmatter(metadata=parsed or {}, body=body)


def dump(path: Path, fm: Frontmatter) -> None:
    """Write a frontmatter document to ``path`` (creates parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fm.metadata:
        # `sort_keys=True` is essential for deterministic on-disk output.
        yaml_text = yaml.safe_dump(
            dict(fm.metadata),
            sort_keys=True,
            default_flow_style=False,
        ).rstrip()
        rendered = f"---\n{yaml_text}\n---\n{fm.body}"
    else:
        rendered = fm.body
    path.write_text(rendered, encoding="utf-8")


def mint_uri(tenant_id: str, s4a_dir: Path, page_path: Path) -> str:
    """Mint a stable ``s4a://<tenant_id>/<relpath>`` URI for a synthesis page.

    Deterministic: same ``(tenant_id, page_path)`` always yields the same URI.
    Raises ``ValueError`` if ``page_path`` is not under ``s4a_dir``.
    """
    if not tenant_id:
        raise ValueError("tenant_id must be a non-empty string")
    rel = page_path.resolve().relative_to(s4a_dir.resolve())
    # Always forward-slash separators, even on Windows; URIs aren't OS paths.
    rel_posix = rel.as_posix()
    return f"s4a://{tenant_id}/{rel_posix}"
