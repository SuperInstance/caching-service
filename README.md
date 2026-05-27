# caching-service

Intelligent in-memory cache with TTL, eviction policies, namespaces, and cache-aside patterns.

**Zero dependencies** — uses only the Python standard library.

## Installation

```bash
pip install caching-service
```

## Quick Start

```python
from caching_service import Cache

cache = Cache(max_size=1000, default_ttl=300)

# Basic operations
cache.set("user:42", {"name": "Alice", "age": 30})
user = cache.get("user:42")

# Delete
cache.delete("user:42")
```

## TTL (Time-To-Live)

```python
# Per-entry TTL
cache.set("token", "abc123", ttl=60)          # expires in 60s
cache = Cache(default_ttl=300)                 # default for all entries
cache.set("key", "value", ttl=None)            # override: no expiry

# Expired entries are lazily removed on access, or eagerly:
purged = cache.purge_expired()
```

## Eviction Policies

```python
from caching_service import Cache, LRUPolicy, LFUPolicy, FIFOPolicy, TTLPolicy

# LRU — evict least recently used (default)
cache = Cache(max_size=100, policy=LRUPolicy())

# LFU — evict least frequently used
cache = Cache(max_size=100, policy=LFUPolicy())

# FIFO — evict oldest entry
cache = Cache(max_size=100, policy=FIFOPolicy())

# TTL — evict entry closest to expiry
cache = Cache(max_size=100, policy=TTLPolicy())
```

## Cache-Aside Pattern

```python
def expensive_lookup(user_id):
    # ... database call ...
    return {"name": "Alice"}

# Returns cached value or calls factory and caches the result
user = cache.get_or_set("user:42", lambda: expensive_lookup(42), ttl=300)
```

## Namespaces

Isolated cache regions sharing a single Cache instance:

```python
cache = Cache()
users = cache.namespace("users", max_size=50, default_ttl=600)
posts = cache.namespace("posts", max_size=200, default_ttl=120)

users.set("42", {"name": "Alice"})
posts.set("99", {"title": "Hello"})

# Keys are isolated — same key, different values
users.set("featured", True)
posts.set("featured", "Welcome!")
assert users.get("featured") is True
assert posts.get("featured") == "Welcome!"
```

## Bulk Operations

```python
cache.set_many({"a": 1, "b": 2, "c": 3})
result = cache.get_many(["a", "b", "z"])       # {"a": 1, "b": 2}
removed = cache.delete_many(["a", "b"])        # 2
```

## Statistics

```python
stats = cache.stats()
print(f"Hits: {stats.hits}")
print(f"Misses: {stats.misses}")
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Evictions: {stats.evictions}")
print(f"Size: {stats.size}")
print(f"Memory: {stats.memory_bytes} bytes")
```

## Thread Safety

The `Cache` class uses a `threading.Lock` for all operations, making it safe for concurrent use.

## API Reference

### `Cache(max_size=None, default_ttl=None, policy=None)`

| Method | Description |
|--------|-------------|
| `get(key)` | Retrieve value (returns `None` on miss/expiry) |
| `set(key, value, ttl=None, metadata=None)` | Store a value |
| `delete(key)` | Remove a key, returns `bool` |
| `has(key)` | Check if key exists and is not expired |
| `clear()` | Remove all entries, returns count |
| `keys()` | List all non-expired keys |
| `size()` | Number of non-expired entries |
| `get_many(keys)` | Bulk get |
| `set_many(mapping, ttl=None)` | Bulk set |
| `delete_many(keys)` | Bulk delete |
| `get_or_set(key, factory, ttl=None)` | Cache-aside pattern |
| `namespace(name, **kwargs)` | Create/get isolated namespace |
| `stats()` | `CacheStats` object |
| `purge_expired()` | Remove expired entries |

### `CacheEntry`

Dataclass with: `key`, `value`, `ttl`, `created_at`, `last_accessed`, `access_count`, `metadata`, and properties `is_expired`, `remaining_ttl`, `size_bytes`.

### Eviction Policies

- `LRUPolicy` — Least Recently Used
- `LFUPolicy` — Least Frequently Used
- `FIFOPolicy` — First In, First Out
- `TTLPolicy` — Closest to expiry

## License

MIT
