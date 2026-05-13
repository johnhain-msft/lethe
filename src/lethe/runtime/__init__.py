"""Lethe runtime — non-store services that compose stores into product surface.

P1 ships :mod:`.tenant_init`; P2 lands the verb runtime + intent classifier;
P3 lands the read-side substrate (:mod:`.bitemporal_filter`,
:mod:`.recall_id`, :mod:`.retrievers`, :mod:`.scoring`,
:mod:`.preferences_prepend`); subsequent phases land the dream-daemon and
health endpoints.
"""

from lethe.runtime.tenant_init import TenantBootstrap, bootstrap

__all__ = ["TenantBootstrap", "bootstrap"]
