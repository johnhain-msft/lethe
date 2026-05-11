"""S4 filesystem layout: per-tenant ``s4a/`` (synthesis) + ``s4b/`` (projections)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class S4Layout:
    """Per-tenant S4 layout under ``<storage_root>/<tenant_id>/``.

    ``tenant_root`` here is already ``<storage_root>/<tenant_id>``; the s4a/
    and s4b/ subdirectories are created beneath it.
    """

    tenant_root: Path

    @property
    def s4a_dir(self) -> Path:
        return self.tenant_root / "s4a"

    @property
    def s4b_dir(self) -> Path:
        return self.tenant_root / "s4b"

    def create(self) -> None:
        """Create the s4a/ and s4b/ directories. Idempotent."""
        self.s4a_dir.mkdir(parents=True, exist_ok=True)
        self.s4b_dir.mkdir(parents=True, exist_ok=True)

    def is_ready(self) -> bool:
        return self.s4a_dir.is_dir() and self.s4b_dir.is_dir()
