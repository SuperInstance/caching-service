"""
Caching Service
Redis-based response caching with TTL management
"""

__version__ = "0.1.0"

from .cache import CacheManager

__all__ = ["CacheManager"]
