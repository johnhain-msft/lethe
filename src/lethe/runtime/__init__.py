"""Lethe runtime — non-store services that compose stores into product surface.

P1 ships only :mod:`.tenant_init`; the verb runtime, dream-daemon, intent
classifier, and health endpoint land at P2-P7.
"""

from lethe.runtime.tenant_init import (
    TenantBootstrap,
    bootstrap,
    preferences_prepend,
)

__all__ = ["TenantBootstrap", "bootstrap", "preferences_prepend"]
