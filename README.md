# Caching Service

**Priority**: 7/10
**Status**: Production-Ready

## Overview

A production-ready caching service for AI API responses with Redis backing. Provides automatic cache key generation, TTL management, request deduplication, and graceful degradation.

## Features

- **Automatic Cache Key Generation**: SHA256-based hashing for consistent keys
- **TTL Management**: Configurable time-to-live for cached responses
- **Request Deduplication**: Automatically detect and return cached responses
- **Metadata Tracking**: Track cache metadata alongside responses
- **Metrics Caching**: Cache analytics and performance metrics
- **Graceful Degradation**: Cache failures don't break your system
- **Redis-backed**: Distributed caching support
- **Async/Await**: Full async/await support
- **Automatic Cleanup**: Expired entries automatically cleaned

## Installation

```bash
# With Redis support
pip install caching-service[redis]
```

## Quick Start

```python
from cache_service import CacheManager

# Create cache manager
cache = CacheManager(redis_url="redis://localhost:6379")
await cache.connect()

# Check for cached response
cached_response = await cache.get_cached_response(request)

if cached_response:
    print("Using cached response")
    return cached_response

# Make API request
response = await make_api_request(request)

# Cache the response
await cache.cache_response(request, response, ttl_seconds=3600)

# Clean up
await cache.disconnect()
```

## Advanced Usage

### Custom TTL

```python
# Cache for 1 hour
await cache.cache_response(request, response, ttl_seconds=3600)

# Cache for 24 hours
await cache.cache_response(request, response, ttl_seconds=86400)

# Cache for 1 week
await cache.cache_response(request, response, ttl_seconds=604800)
```

### Cache Statistics

```python
stats = await cache.get_cache_stats()

print(f"Memory used: {stats['memory_human']}")
print(f"Cached responses: {stats['cached_responses']}")
print(f"Total keys: {stats['total_keys']}")
```

### Cache Invalidation

```python
# Invalidate all cache entries
count = await cache.invalidate_cache("*")

# Invalidate specific pattern
count = await cache.invalidate_cache("cache:response:abc*")
```

### Metrics Caching

```python
# Cache metrics for analytics
await cache.cache_request_metrics(
    request_id="req-123",
    provider="openai",
    response_time_ms=1250,
    cost_usd=0.0045,
    ttl_seconds=86400
)

# Retrieve metrics for time period
metrics = await cache.get_metrics_for_period(hours=24)

for metric in metrics:
    print(f"{metric['provider']}: {metric['cost_usd']}")
```

### Cleanup

```python
# Clean up cache entries without TTL
expired_count = await cache.cleanup_expired_cache()
print(f"Cleaned up {expired_count} entries")
```

## API Reference

### CacheManager

Main caching class.

**Constructor**:
- `redis_url: str = "redis://localhost:6379"`: Redis connection URL
- `max_connections: int = 50`: Maximum Redis connections

**Methods**:
- `async connect()`: Connect to Redis
- `async disconnect()`: Disconnect from Redis
- `async get_cached_response(request: GenerationRequest) -> Optional[GenerationResponse]`: Get cached response
- `async cache_response(request, response, ttl_seconds=3600)`: Cache a response
- `async invalidate_cache(pattern="*") -> int`: Invalidate cache entries
- `async get_cache_stats() -> Dict`: Get cache statistics
- `async cleanup_expired_cache() -> int`: Clean up expired entries
- `async cache_request_metrics(request_id, provider, response_time_ms, cost_usd, ttl_seconds)`: Cache metrics
- `async get_metrics_for_period(hours=24) -> List[Dict]`: Get metrics for period

## Cache Key Generation

The service automatically generates cache keys based on:
- Messages (role and content)
- Temperature
- Top-p
- Max tokens

This ensures that semantically identical requests get the same cache key.

```python
# These two requests will have the same cache key:
request1 = GenerationRequest(
    messages=[ChatMessage(role="user", content="Hello")],
    temperature=0.7
)

request2 = GenerationRequest(
    messages=[ChatMessage(role="user", content="Hello")],
    temperature=0.7
)
```

## Best Practices

1. **Set Appropriate TTLs**: Balance freshness with cache hit rate
2. **Monitor Cache Stats**: Track memory usage and hit rates
3. **Handle Cache Misses**: Always handle cases where cache is empty
4. **Use Patterns for Invalidation**: Use specific patterns when invalidating
5. **Graceful Degradation**: Design your system to work even if cache fails

## Configuration

### Redis Connection

```python
# Default
cache = CacheManager()

# Custom Redis URL
cache = CacheManager(redis_url="redis://localhost:6379/1")

# With connection pool
cache = CacheManager(
    redis_url="redis://localhost:6379",
    max_connections=100
)
```

## Examples

### Complete API Caching Flow

```python
async def make_cached_request(provider, request):
    cache = CacheManager(redis_url="redis://localhost:6379")
    await cache.connect()

    try:
        # Check cache
        cached_response = await cache.get_cached_response(request)
        if cached_response:
            return cached_response

        # Make API request
        response = await provider.generate(request)

        # Cache response
        await cache.cache_response(request, response, ttl_seconds=3600)

        # Cache metrics
        await cache.cache_request_metrics(
            request_id=response.request_id,
            provider=provider.name,
            response_time_ms=response.processing_time_ms,
            cost_usd=response.cost_usd
        )

        return response

    finally:
        await cache.disconnect()
```

### Analytics Dashboard

```python
async def get_cache_analytics():
    cache = CacheManager(redis_url="redis://localhost:6379")
    await cache.connect()

    try:
        # Get cache stats
        stats = await cache.get_cache_stats()

        # Get metrics for last 24 hours
        metrics = await cache.get_metrics_for_period(hours=24)

        # Calculate totals
        total_cost = sum(m['cost_usd'] for m in metrics)
        avg_response_time = sum(m['response_time_ms'] for m in metrics) / len(metrics)

        return {
            'cache_stats': stats,
            'total_requests': len(metrics),
            'total_cost': total_cost,
            'avg_response_time': avg_response_time
        }

    finally:
        await cache.disconnect()
```

## Dependencies

**Required**: None

**Optional**:
- `redis>=4.5.0` for Redis support

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.
