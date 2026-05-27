"""
Cache — the main in-memory cache with TTL, eviction, namespaces, and cache-aside support.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Callable, Optional

from .entry import CacheEntry
from .namespace import CacheNamespace
from .policy import EvictionPolicy, LRUPolicy
from .stats import CacheStats


class Cache:
    """In-memory cache with configurable eviction, TTL, and namespace support.

    Parameters:
        max_size: Maximum number of entries (``None`` = unlimited).
        default_ttl: Default TTL in seconds (``None`` = no expiry).
        policy: Eviction policy (defaults to :class:`LRUPolicy`).
    """

    def __init__(
        self,
        max_size: Optional[int] = None,
        default_ttl: Optional[float] = None,
        policy: Optional[EvictionPolicy] = None,
    ) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._policy: EvictionPolicy = policy or LRUPolicy()
        self._store: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._namespaces: dict[str, CacheNamespace] = {}
        self._lock = threading.Lock()

    # -- core operations -----------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Retrieve a value. Returns ``None`` on miss or expiry."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats.record_miss()
                return None
            if entry.is_expired:
                del self._store[key]
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
        """Store a key–value pair."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=effective_ttl,
                metadata=metadata or {},
            )
            self._store[key] = entry
            self._evict_if_needed()
            self._refresh_stats()

    def delete(self, key: str) -> bool:
        """Remove a key. Returns ``True`` if it existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._refresh_stats()
                return True
            return False

    def has(self, key: str) -> bool:
        """Check if a non-expired key exists."""
        return self.get(key) is not None

    # -- bulk operations -----------------------------------------------------

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Retrieve multiple keys. Missing/expired keys are absent from the result."""
        return {k: v for k in (keys) if (v := self.get(k)) is not None}

    def set_many(self, mapping: dict[str, Any], ttl: Optional[float] = None) -> None:
        """Store multiple key–value pairs."""
        for k, v in mapping.items():
            self.set(k, v, ttl=ttl)

    def delete_many(self, keys: list[str]) -> int:
        """Delete multiple keys. Returns count actually removed."""
        count = 0
        for k in keys:
            if self.delete(k):
                count += 1
        return count

    def clear(self) -> int:
        """Remove all entries. Returns count removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._refresh_stats()
            return count

    def keys(self) -> list[str]:
        """Return all non-expired keys."""
        self._purge_expired()
        with self._lock:
            return list(self._store.keys())

    def size(self) -> int:
        """Number of non-expired entries."""
        self._purge_expired()
        with self._lock:
            return len(self._store)

    # -- cache-aside pattern -------------------------------------------------

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[float] = None,
    ) -> Any:
        """Cache-aside: return cached value or compute, store, and return it."""
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    # -- namespaces ----------------------------------------------------------

    def namespace(
        self,
        name: str,
        *,
        max_size: Optional[int] = None,
        default_ttl: Optional[float] = None,
        policy: Optional[EvictionPolicy] = None,
    ) -> CacheNamespace:
        """Create or retrieve a namespace.

        Namespaces partition keys by prefix and can have independent
        max-size / TTL / policy settings.
        """
        if name not in self._namespaces:
            ns = CacheNamespace(
                prefix=f"__ns:{name}",
                max_size=max_size if max_size is not None else self._max_size,
                default_ttl=default_ttl if default_ttl is not None else self._default_ttl,
                policy=policy or self._policy,
                _store=self._store,
            )
            self._namespaces[name] = ns
        return self._namespaces[name]

    # -- stats & maintenance -------------------------------------------------

    def stats(self) -> CacheStats:
        """Return the cumulative stats object."""
        return self._stats

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns count purged."""
        return self._purge_expired()

    # -- internals -----------------------------------------------------------

    def _evict_if_needed(self) -> None:
        if self._max_size is None:
            return
        while len(self._store) > self._max_size:
            victim = self._policy.select_victim(self._store)
            if victim is None:
                break
            del self._store[victim]
            self._stats.record_eviction()

    def _purge_expired(self) -> int:
        with self._lock:
            expired = [k for k, e in self._store.items() if e.is_expired]
            for k in expired:
                del self._store[k]
            if expired:
                self._refresh_stats()
            return len(expired)

    def _refresh_stats(self) -> None:
        mem = sum(e.size_bytes for e in self._store.values())
        self._stats.update_size(len(self._store), mem)
