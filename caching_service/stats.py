"""
CacheStats — hit/miss/eviction counters and memory estimation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheStats:
    """Running statistics for a cache (or namespace).

    Updated by the cache internals; safe to snapshot via ``dataclasses.asdict``.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    memory_bytes: int = 0

    # -- derived metrics -----------------------------------------------------

    @property
    def hit_rate(self) -> float:
        """Fraction of lookups that were cache hits (0.0–1.0)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    # -- mutation helpers (used internally) ----------------------------------

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_eviction(self) -> None:
        self.evictions += 1

    def update_size(self, count: int, memory_bytes: int) -> None:
        self.size = count
        self.memory_bytes = memory_bytes

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.size = 0
        self.memory_bytes = 0

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "memory_bytes": self.memory_bytes,
            "hit_rate": round(self.hit_rate, 4),
            "total_requests": self.total_requests,
        }
