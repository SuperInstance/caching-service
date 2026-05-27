"""
caching-service — Intelligent in-memory cache with TTL, eviction policies, and namespaces.
"""

__version__ = "1.0.0"

from .entry import CacheEntry
from .policy import EvictionPolicy, LRUPolicy, LFUPolicy, FIFOPolicy, TTLPolicy
from .namespace import CacheNamespace
from .stats import CacheStats
from .cache import Cache

__all__ = [
    "Cache",
    "CacheEntry",
    "CacheNamespace",
    "CacheStats",
    "EvictionPolicy",
    "LRUPolicy",
    "LFUPolicy",
    "FIFOPolicy",
    "TTLPolicy",
]
