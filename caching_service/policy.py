"""
Eviction policies — strategies for deciding which entries to evict.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entry import CacheEntry


class EvictionPolicy(ABC):
    """Base class for eviction policies."""

    @abstractmethod
    def select_victim(self, entries: dict[str, "CacheEntry"]) -> str | None:
        """Return the key of the entry to evict, or ``None`` if the pool is empty."""

    def should_evict(self, entries: dict[str, "CacheEntry"], max_size: int) -> bool:
        """Return ``True`` when eviction is needed (default: over capacity)."""
        return len(entries) > max_size


class LRUPolicy(EvictionPolicy):
    """Evict the **Least Recently Used** entry."""

    def select_victim(self, entries: dict[str, "CacheEntry"]) -> str | None:
        if not entries:
            return None
        return min(entries, key=lambda k: entries[k].last_accessed)


class LFUPolicy(EvictionPolicy):
    """Evict the **Least Frequently Used** entry (ties broken by LRU)."""

    def select_victim(self, entries: dict[str, "CacheEntry"]) -> str | None:
        if not entries:
            return None
        return min(
            entries,
            key=lambda k: (entries[k].access_count, entries[k].last_accessed),
        )


class FIFOPolicy(EvictionPolicy):
    """Evict the **First In, First Out** (oldest creation time)."""

    def select_victim(self, entries: dict[str, "CacheEntry"]) -> str | None:
        if not entries:
            return None
        return min(entries, key=lambda k: entries[k].created_at)


class TTLPolicy(EvictionPolicy):
    """Evict the entry closest to expiry.

    This is a *passive* policy — it picks the soonest-expiring entry
    when eviction is required.  Active TTL expiry is handled by the
    Cache itself on every ``get``.
    """

    def select_victim(self, entries: dict[str, "CacheEntry"]) -> str | None:
        if not entries:
            return None
        # Filter to entries that *have* a TTL first; fall back to LRU.
        ttl_entries = {k: e for k, e in entries.items() if e.ttl is not None}
        if ttl_entries:
            return min(
                ttl_entries,
                key=lambda k: ttl_entries[k].created_at + ttl_entries[k].ttl,  # type: ignore[operator]
            )
        # No TTL entries — fall back to LRU among the rest.
        return min(entries, key=lambda k: entries[k].last_accessed)
