"""
CacheEntry — a single cached item with TTL, access tracking, and metadata.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional


def _estimate_size(value: Any) -> int:
    """Rough byte-size estimate for a cached value."""
    return sys.getsizeof(value)


@dataclass
class CacheEntry:
    """Represents a single entry in the cache.

    Attributes:
        key: The cache key.
        value: The cached value.
        ttl: Time-to-live in seconds. ``None`` means no expiry.
        created_at: Epoch timestamp when the entry was created.
        last_accessed: Epoch timestamp of the most recent access.
        access_count: Number of times the entry has been read.
        metadata: Optional arbitrary metadata dict.
    """

    key: str
    value: Any
    ttl: Optional[float] = None
    created_at: float = field(default_factory=time.monotonic)
    last_accessed: float = field(default_factory=time.monotonic)
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- derived properties --------------------------------------------------

    @property
    def expires_at(self) -> Optional[float]:
        """Epoch time at which this entry expires, or ``None``."""
        if self.ttl is None:
            return None
        return self.created_at + self.ttl

    @property
    def is_expired(self) -> bool:
        """Return ``True`` if the TTL has elapsed."""
        if self.ttl is None:
            return False
        return time.monotonic() > self.created_at + self.ttl

    @property
    def remaining_ttl(self) -> Optional[float]:
        """Seconds remaining before expiry, or ``None`` if no TTL."""
        if self.ttl is None:
            return None
        remaining = (self.created_at + self.ttl) - time.monotonic()
        return max(remaining, 0.0)

    @property
    def size_bytes(self) -> int:
        """Approximate memory footprint of the stored value."""
        return _estimate_size(self.value)

    # -- mutation helpers ----------------------------------------------------

    def touch(self) -> None:
        """Mark this entry as accessed (update stats)."""
        self.access_count += 1
        self.last_accessed = time.monotonic()

    def refresh_ttl(self, new_ttl: Optional[float] = None) -> None:
        """Reset the expiry timer.

        If *new_ttl* is provided it replaces the current TTL.
        Otherwise the existing TTL is reused (no-op if there was none).
        """
        if new_ttl is not None:
            self.ttl = new_ttl
        if self.ttl is not None:
            self.created_at = time.monotonic()
