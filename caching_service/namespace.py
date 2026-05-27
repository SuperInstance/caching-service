"""
CacheNamespace — an isolated region within a Cache.

Namespaces partition the key-space so different subsystems can share a
single Cache instance without collisions.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .entry import CacheEntry
from .policy import EvictionPolicy
from .stats import CacheStats


class CacheNamespace:
    """A namespaced view over a shared Cache.

    Users should create namespaces via ``Cache.namespace("name")``
    rather than constructing this directly.
    """

    def __init__(
        self,
        prefix: str,
        *,
        max_size: Optional[int] = None,
        default_ttl: Optional[float] = None,
        policy: Optional[EvictionPolicy] = None,
        _store: Optional[dict[str, CacheEntry]] = None,
        _parent_stats: Optional[CacheStats] = None,
    ) -> None:
        self._prefix = prefix
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._policy = policy
        # Namespaces share the parent's store; keys are prefixed.
        self._store: dict[str, CacheEntry] = _store if _store is not None else {}
        self._stats = CacheStats()
        # If a parent stats object is provided we mirror into it.
        self._parent_stats = _parent_stats

    # -- internal key helpers ------------------------------------------------

    def _prefixed(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def _own_entries(self) -> dict[str, CacheEntry]:
        """Return only entries that belong to this namespace."""
        prefix = f"{self._prefix}:"
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}

    # -- public API ----------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Retrieve a value by key within this namespace."""
        full_key = self._prefixed(key)
        entry = self._store.get(full_key)
        if entry is None:
            self._stats.record_miss()
            return None
        if entry.is_expired:
            del self._store[full_key]
            self._stats.record_miss()
            self._refresh_stats()
            return None
        entry.touch()
        self._stats.record_hit()
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store a value in this namespace."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        full_key = self._prefixed(key)
        entry = CacheEntry(
            key=full_key,
            value=value,
            ttl=effective_ttl,
            metadata=metadata or {},
        )
        self._store[full_key] = entry
        self._enforce_max_size()
        self._refresh_stats()

    def delete(self, key: str) -> bool:
        """Remove a key. Returns ``True`` if the key existed."""
        full_key = self._prefixed(key)
        if full_key in self._store:
            del self._store[full_key]
            self._refresh_stats()
            return True
        return False

    def clear(self) -> int:
        """Clear all entries in this namespace. Returns count removed."""
        own = self._own_entries()
        for k in list(own):
            del self._store[k]
        self._refresh_stats()
        return len(own)

    def keys(self) -> list[str]:
        """List keys (without the namespace prefix)."""
        prefix = f"{self._prefix}:"
        return [k[len(prefix):] for k, e in self._own_entries().items() if not e.is_expired]

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def stats(self) -> CacheStats:
        return self._stats

    # -- eviction ------------------------------------------------------------

    def _enforce_max_size(self) -> None:
        if self._max_size is None or self._policy is None:
            return
        own = self._own_entries()
        while len(own) > self._max_size:
            victim_key = self._policy.select_victim(own)
            if victim_key is None:
                break
            del self._store[victim_key]
            self._stats.record_eviction()
            own = self._own_entries()

    def _refresh_stats(self) -> None:
        own = self._own_entries()
        mem = sum(e.size_bytes for e in own.values())
        self._stats.update_size(len(own), mem)
