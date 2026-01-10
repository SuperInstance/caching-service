"""
Tests for Cache Manager
"""

import pytest
import asyncio
from cache_service import CacheManager, GenerationRequest, GenerationResponse


class MockMessage:
    """Mock message for testing"""
    def __init__(self, role, content):
        self.role = role
        self.content = content


@pytest.fixture
async def cache_manager():
    """Create a cache manager instance"""
    manager = CacheManager(redis_url=None)  # No Redis for testing
    await manager.connect()
    yield manager
    await manager.disconnect()


def test_cache_manager_initialization():
    """Test cache manager initialization"""
    manager = CacheManager()
    assert manager.redis_url == "redis://localhost:6379"
    assert manager.max_connections == 50


def test_generate_cache_key():
    """Test cache key generation"""
    manager = CacheManager()

    request = GenerationRequest(
        messages=[
            MockMessage("user", "Hello"),
            MockMessage("assistant", "Hi there!")
        ],
        temperature=0.7,
        top_p=1.0
    )

    key1 = manager._generate_cache_key(request)
    key2 = manager._generate_cache_key(request)

    # Same request should generate same key
    assert key1 == key2

    # Different request should generate different key
    request2 = GenerationRequest(
        messages=[MockMessage("user", "Goodbye")],
        temperature=0.7
    )
    key3 = manager._generate_cache_key(request2)
    assert key1 != key3


@pytest.mark.asyncio
async def test_get_cached_response_no_redis(cache_manager):
    """Test getting cached response when Redis is not available"""
    request = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=0.7
    )

    result = await cache_manager.get_cached_response(request)
    assert result is None  # No Redis, so no cache


@pytest.mark.asyncio
async def test_cache_response_no_redis(cache_manager):
    """Test caching response when Redis is not available"""
    request = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=0.7
    )

    response = GenerationResponse(
        request_id="test-123",
        content="Hello!",
        provider_used="openai",
        model_used="gpt-4",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        processing_time_ms=100
    )

    # Should not raise error even without Redis
    await cache_manager.cache_response(request, response)


@pytest.mark.asyncio
async def test_invalidate_cache_no_redis(cache_manager):
    """Test cache invalidation when Redis is not available"""
    result = await cache_manager.invalidate_cache("*")
    assert result == 0  # No Redis, so nothing invalidated


@pytest.mark.asyncio
async def test_get_cache_stats_no_redis(cache_manager):
    """Test getting cache stats when Redis is not available"""
    stats = await cache_manager.get_cache_stats()
    assert stats == {}  # No Redis, so no stats


@pytest.mark.asyncio
async def test_cleanup_expired_cache_no_redis(cache_manager):
    """Test cleanup when Redis is not available"""
    result = await cache_manager.cleanup_expired_cache()
    assert result == 0  # No Redis, so nothing cleaned


@pytest.mark.asyncio
async def test_cache_request_metrics_no_redis(cache_manager):
    """Test caching request metrics when Redis is not available"""
    # Should not raise error even without Redis
    await cache_manager.cache_request_metrics(
        request_id="test-123",
        provider="openai",
        response_time_ms=100,
        cost_usd=0.001
    )


@pytest.mark.asyncio
async def test_get_metrics_for_period_no_redis(cache_manager):
    """Test getting metrics when Redis is not available"""
    metrics = await cache_manager.get_metrics_for_period(hours=24)
    assert metrics == []  # No Redis, so no metrics


def test_generation_request():
    """Test GenerationRequest creation"""
    request = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=0.7,
        top_p=1.0,
        max_tokens=100
    )

    assert len(request.messages) == 1
    assert request.temperature == 0.7
    assert request.top_p == 1.0
    assert request.max_tokens == 100


def test_generation_response():
    """Test GenerationResponse creation"""
    response = GenerationResponse(
        request_id="test-123",
        content="Hello!",
        provider_used="openai",
        model_used="gpt-4",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        processing_time_ms=100
    )

    assert response.request_id == "test-123"
    assert response.content == "Hello!"
    assert response.provider_used == "openai"
    assert response.model_used == "gpt-4"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.cost_usd == 0.0001
    assert response.processing_time_ms == 100


def test_generation_response_with_metadata():
    """Test GenerationResponse with metadata"""
    metadata = {"cache_hit": True, "provider": "openai"}
    response = GenerationResponse(
        request_id="test-123",
        content="Hello!",
        provider_used="openai",
        model_used="gpt-4",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        processing_time_ms=100,
        metadata=metadata
    )

    assert response.metadata == metadata


@pytest.mark.asyncio
async def test_cache_with_custom_ttl():
    """Test caching with custom TTL"""
    manager = CacheManager()

    request = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=0.7
    )

    response = GenerationResponse(
        request_id="test-123",
        content="Hello!",
        provider_used="openai",
        model_used="gpt-4",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        processing_time_ms=100
    )

    # Should not raise error even without Redis
    await manager.cache_response(request, response, ttl_seconds=7200)


@pytest.mark.asyncio
async def test_cache_key_consistency():
    """Test that cache keys are consistent for identical requests"""
    manager = CacheManager()

    request1 = GenerationRequest(
        messages=[
            MockMessage("user", "Hello"),
            MockMessage("assistant", "Hi")
        ],
        temperature=0.7,
        top_p=1.0
    )

    request2 = GenerationRequest(
        messages=[
            MockMessage("user", "Hello"),
            MockMessage("assistant", "Hi")
        ],
        temperature=0.7,
        top_p=1.0
    )

    key1 = manager._generate_cache_key(request1)
    key2 = manager._generate_cache_key(request2)

    assert key1 == key2


@pytest.mark.asyncio
async def test_cache_key_includes_temperature():
    """Test that cache key includes temperature"""
    manager = CacheManager()

    request1 = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=0.5
    )

    request2 = GenerationRequest(
        messages=[MockMessage("user", "Hello")],
        temperature=1.0
    )

    key1 = manager._generate_cache_key(request1)
    key2 = manager._generate_cache_key(request2)

    assert key1 != key2
