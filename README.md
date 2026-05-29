# caching-service

**Intelligent in-memory cache** — TTL, eviction policies, namespaces, and cache-aside patterns. Pure Python, zero dependencies.

## What This Gives You

- **TTL (Time-To-Live)** — per-entry or default expiration with lazy + eager eviction
- **Eviction policies** — LRU, LFU, FIFO, TTL-based
- **Namespaces** — partition cache into isolated key spaces
- **Cache-aside** — built-in `get_or_set` pattern for automatic population
- **Statistics** — hit/miss rates, eviction counts, memory tracking
- **Zero dependencies** — stdlib only

## Installation

```bash
pip install caching-service
```

## Quick Start

```python
from caching_service import Cache, LRUPolicy

cache = Cache(max_size=1000, default_ttl=300, policy=LRUPolicy())

cache.set("user:42", {"name": "Alice", "age": 30})
user = cache.get("user:42")

# Cache-aside pattern
data = cache.get_or_set("expensive-key", lambda: compute_expensive_thing(), ttl=60)

# Statistics
print(cache.stats())  # CacheStats(hits=42, misses=3, evictions=1)
```

## Testing

```bash
pip install -e .
pytest
```

## License

MIT
