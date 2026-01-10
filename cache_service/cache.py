"""
Caching system for request deduplication and response caching
"""

import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from dataclasses import asdict

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class GenerationRequest:
    """Mock GenerationRequest for caching"""
    def __init__(self, messages, temperature=0.7, top_p=1.0, max_tokens=None, **kwargs):
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.request_id = kwargs.get('request_id', '')
        self.metadata = kwargs.get('metadata', {})


class GenerationResponse:
    """Mock GenerationResponse for caching"""
    def __init__(self, request_id, content, provider_used, model_used,
                 input_tokens, output_tokens, cost_usd, processing_time_ms,
                 metadata=None, **kwargs):
        self.request_id = request_id
        self.content = content
        self.provider_used = provider_used
        self.model_used = model_used
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.processing_time_ms = processing_time_ms
        self.metadata = metadata or {}


class CacheManager:
    """Manages caching of requests and responses"""

    def __init__(self, redis_url: str = "redis://localhost:6379", max_connections: int = 50):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis"""
        if REDIS_AVAILABLE:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    max_connections=self.max_connections,
                    decode_responses=True
                )
                await self._redis.ping()
            except Exception:
                self._redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()

    def _generate_cache_key(self, request: GenerationRequest) -> str:
        """Generate a cache key for a request"""
        # Create a normalized representation of the request
        cache_data = {
            'messages': [
                {'role': msg.role, 'content': msg.content}
                for msg in request.messages
            ],
            'temperature': request.temperature,
            'top_p': request.top_p,
            'max_tokens': request.max_tokens
        }

        # Create hash
        cache_str = json.dumps(cache_data, sort_keys=True)
        return f"cache:response:{hashlib.sha256(cache_str.encode()).hexdigest()}"

    async def get_cached_response(self, request: GenerationRequest) -> Optional[GenerationResponse]:
        """Get cached response for a request"""
        if not self._redis:
            return None

        cache_key = self._generate_cache_key(request)
        try:
            cached_data = await self._redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return GenerationResponse(**data)
        except Exception:
            # Cache errors should not break the system
            pass

        return None

    async def cache_response(
        self,
        request: GenerationRequest,
        response: GenerationResponse,
        ttl_seconds: int = 3600
    ) -> None:
        """Cache a response"""
        if not self._redis:
            return

        cache_key = self._generate_cache_key(request)
        try:
            # Serialize response
            response_data = {
                'request_id': response.request_id,
                'content': response.content,
                'provider_used': str(response.provider_used),
                'model_used': response.model_used,
                'input_tokens': response.input_tokens,
                'output_tokens': response.output_tokens,
                'cost_usd': response.cost_usd,
                'processing_time_ms': response.processing_time_ms,
                'metadata': response.metadata or {}
            }
            cached_data = json.dumps(response_data)

            # Store with TTL
            await self._redis.setex(cache_key, ttl_seconds, cached_data)

            # Also store cache metadata
            metadata_key = f"{cache_key}:meta"
            metadata = {
                'request_id': request.request_id,
                'provider_used': str(response.provider_used),
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'ttl_seconds': ttl_seconds
            }
            await self._redis.setex(metadata_key, ttl_seconds, json.dumps(metadata))

        except Exception:
            # Cache errors should not break the system
            pass

    async def invalidate_cache(self, pattern: str = "*") -> int:
        """Invalidate cache entries matching pattern"""
        if not self._redis:
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
        except Exception:
            pass

        return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self._redis:
            return {}

        try:
            info = await self._redis.info('memory')
            keyspace = await self._redis.info('keyspace')

            # Count cache keys
            cache_keys = await self._redis.keys("cache:response:*")
            cache_count = len([k for k in cache_keys if not k.endswith(":meta")])

            return {
                'memory_used_bytes': info.get('used_memory', 0),
                'memory_human': info.get('used_memory_human', '0B'),
                'cached_responses': cache_count,
                'total_keys': sum(info.get('db', {}).values()),
                'hit_rate': 0.0  # Would need to track hits/misses separately
            }
        except Exception:
            return {}

    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        if not self._redis:
            return 0

        try:
            # Redis automatically handles TTL expiration
            # This method can be used for manual cleanup if needed
            cache_keys = await self._redis.keys("cache:response:*")
            expired_count = 0

            for key in cache_keys:
                ttl = await self._redis.ttl(key)
                if ttl == -1:  # No TTL set
                    # Set a default TTL for keys without expiration
                    await self._redis.expire(key, 3600)
                    expired_count += 1

            return expired_count
        except Exception:
            return 0

    async def cache_request_metrics(
        self,
        request_id: str,
        provider: str,
        response_time_ms: int,
        cost_usd: float,
        ttl_seconds: int = 86400  # 24 hours
    ) -> None:
        """Cache request metrics for analytics"""
        if not self._redis:
            return

        try:
            key = f"cache:metrics:{request_id}"
            metrics_data = {
                'request_id': request_id,
                'provider': provider,
                'response_time_ms': response_time_ms,
                'cost_usd': cost_usd,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await self._redis.setex(key, ttl_seconds, json.dumps(metrics_data))
        except Exception:
            pass

    async def get_metrics_for_period(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get cached metrics for a time period"""
        if not self._redis:
            return []

        try:
            pattern = "cache:metrics:*"
            keys = await self._redis.keys(pattern)

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            metrics = []

            for key in keys:
                data = await self._redis.get(key)
                if data:
                    metric_data = json.loads(data)
                    timestamp = datetime.fromisoformat(metric_data['timestamp'])
                    if timestamp >= cutoff_time:
                        metrics.append(metric_data)

            return metrics
        except Exception:
            return []
