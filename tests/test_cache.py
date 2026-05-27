"""
Comprehensive tests for caching-service.
"""

import time
import threading
from dataclasses import asdict

import pytest

from caching_service import (
    Cache,
    CacheEntry,
    CacheNamespace,
    CacheStats,
    EvictionPolicy,
    LRUPolicy,
    LFUPolicy,
    FIFOPolicy,
    TTLPolicy,
)


# ---------------------------------------------------------------------------
# CacheEntry
# ---------------------------------------------------------------------------

class TestCacheEntry:
    def test_basic_creation(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.ttl is None
        assert entry.access_count == 0

    def test_ttl_not_expired(self):
        entry = CacheEntry(key="k", value="v", ttl=10.0)
        assert not entry.is_expired

    def test_ttl_expired(self):
        entry = CacheEntry(key="k", value="v", ttl=0.0)
        # ttl=0 means it expires immediately (created_at + 0 <= now)
        time.sleep(0.01)
        assert entry.is_expired

    def test_no_ttl_never_expires(self):
        entry = CacheEntry(key="k", value="v", ttl=None)
        assert not entry.is_expired
        assert entry.expires_at is None

    def test_expires_at(self):
        entry = CacheEntry(key="k", value="v", ttl=60.0)
        assert entry.expires_at is not None
        assert entry.expires_at > entry.created_at

    def test_remaining_ttl(self):
        entry = CacheEntry(key="k", value="v", ttl=10.0)
        rem = entry.remaining_ttl
        assert rem is not None
        assert 9 < rem <= 10

    def test_remaining_ttl_no_expiry(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.remaining_ttl is None

    def test_touch(self):
        entry = CacheEntry(key="k", value="v")
        old_access = entry.last_accessed
        time.sleep(0.01)
        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed > old_access

    def test_refresh_ttl(self):
        entry = CacheEntry(key="k", value="v", ttl=0.0)
        time.sleep(0.01)
        assert entry.is_expired
        entry.refresh_ttl(10.0)
        assert not entry.is_expired
        assert entry.ttl == 10.0

    def test_refresh_ttl_reuses_existing(self):
        entry = CacheEntry(key="k", value="v", ttl=10.0)
        old_created = entry.created_at
        time.sleep(0.01)
        entry.refresh_ttl()
        assert entry.created_at > old_created
        assert entry.ttl == 10.0

    def test_size_bytes(self):
        entry = CacheEntry(key="k", value="hello world")
        assert entry.size_bytes > 0

    def test_metadata(self):
        entry = CacheEntry(key="k", value="v", metadata={"source": "test"})
        assert entry.metadata["source"] == "test"


# ---------------------------------------------------------------------------
# CacheStats
# ---------------------------------------------------------------------------

class TestCacheStats:
    def test_initial_state(self):
        s = CacheStats()
        assert s.hits == 0
        assert s.misses == 0
        assert s.evictions == 0
        assert s.hit_rate == 0.0
        assert s.total_requests == 0

    def test_hit_rate(self):
        s = CacheStats(hits=7, misses=3)
        assert s.hit_rate == 0.7
        assert s.miss_rate == pytest.approx(0.3)

    def test_record_methods(self):
        s = CacheStats()
        s.record_hit()
        s.record_hit()
        s.record_miss()
        s.record_eviction()
        assert s.hits == 2
        assert s.misses == 1
        assert s.evictions == 1

    def test_update_size(self):
        s = CacheStats()
        s.update_size(42, 1024)
        assert s.size == 42
        assert s.memory_bytes == 1024

    def test_reset(self):
        s = CacheStats(hits=10, misses=5, evictions=2, size=3, memory_bytes=100)
        s.reset()
        assert s.hits == 0
        assert s.misses == 0

    def test_to_dict(self):
        s = CacheStats(hits=8, misses=2)
        d = s.to_dict()
        assert d["hit_rate"] == 0.8
        assert d["total_requests"] == 10

    def test_zero_requests_hit_rate(self):
        s = CacheStats()
        assert s.hit_rate == 0.0


# ---------------------------------------------------------------------------
# Eviction Policies
# ---------------------------------------------------------------------------

def _make_entries(count: int) -> dict[str, CacheEntry]:
    entries: dict[str, CacheEntry] = {}
    for i in range(count):
        entries[f"k{i}"] = CacheEntry(key=f"k{i}", value=f"v{i}")
    return entries


class TestLRUPolicy:
    def test_selects_least_recently_accessed(self):
        entries = _make_entries(3)
        # Touch in order with small sleeps to guarantee ordering
        entries["k0"].touch()
        time.sleep(0.01)
        entries["k1"].touch()
        time.sleep(0.01)
        entries["k2"].touch()
        policy = LRUPolicy()
        assert policy.select_victim(entries) == "k0"

    def test_empty_returns_none(self):
        assert LRUPolicy().select_victim({}) is None


class TestLFUPolicy:
    def test_selects_least_frequently_used(self):
        entries = _make_entries(3)
        entries["k0"].touch()
        entries["k0"].touch()  # access_count=2
        entries["k1"].touch()  # access_count=1
        # k2 has access_count=0
        policy = LFUPolicy()
        assert policy.select_victim(entries) == "k2"

    def test_empty_returns_none(self):
        assert LFUPolicy().select_victim({}) is None


class TestFIFOPolicy:
    def test_selects_oldest(self):
        entries = _make_entries(3)
        # k0 was created first
        entries["k0"].created_at = 1.0
        entries["k1"].created_at = 2.0
        entries["k2"].created_at = 3.0
        policy = FIFOPolicy()
        assert policy.select_victim(entries) == "k0"


class TestTTLPolicy:
    def test_prefers_soonest_expiry(self):
        now = time.monotonic()
        e1 = CacheEntry(key="k1", value="v1", ttl=100.0)
        e1.created_at = now - 100  # expires in 0s
        e2 = CacheEntry(key="k2", value="v2", ttl=200.0)
        e2.created_at = now - 100  # expires in 100s
        entries = {"k1": e1, "k2": e2}
        assert TTLPolicy().select_victim(entries) == "k1"

    def test_falls_back_to_lru_when_no_ttl(self):
        entries = _make_entries(2)
        entries["k0"].touch()
        time.sleep(0.01)
        entries["k1"].touch()
        assert TTLPolicy().select_victim(entries) == "k0"

    def test_should_evict(self):
        entries = _make_entries(5)
        policy = TTLPolicy()
        assert policy.should_evict(entries, max_size=3)
        assert not policy.should_evict(entries, max_size=10)


# ---------------------------------------------------------------------------
# Cache — core operations
# ---------------------------------------------------------------------------

class TestCacheCore:
    def test_set_and_get(self):
        c = Cache()
        c.set("name", "Alice")
        assert c.get("name") == "Alice"

    def test_get_missing_returns_none(self):
        assert Cache().get("nope") is None

    def test_delete(self):
        c = Cache()
        c.set("k", "v")
        assert c.delete("k") is True
        assert c.get("k") is None
        assert c.delete("k") is False

    def test_has(self):
        c = Cache()
        assert not c.has("k")
        c.set("k", "v")
        assert c.has("k")

    def test_clear(self):
        c = Cache()
        c.set("a", 1)
        c.set("b", 2)
        count = c.clear()
        assert count == 2
        assert c.size() == 0

    def test_keys(self):
        c = Cache()
        c.set("x", 1)
        c.set("y", 2)
        assert sorted(c.keys()) == ["x", "y"]

    def test_size(self):
        c = Cache()
        assert c.size() == 0
        c.set("a", 1)
        c.set("b", 2)
        assert c.size() == 2

    def test_overwrite_key(self):
        c = Cache()
        c.set("k", "old")
        c.set("k", "new")
        assert c.get("k") == "new"

    def test_metadata(self):
        c = Cache()
        c.set("k", "v", metadata={"src": "test"})
        entry = c._store["k"]
        assert entry.metadata == {"src": "test"}


class TestCacheTTL:
    def test_entry_expires(self):
        c = Cache()
        c.set("k", "v", ttl=0.0)
        time.sleep(0.01)
        assert c.get("k") is None

    def test_default_ttl(self):
        c = Cache(default_ttl=0.0)
        c.set("k", "v")
        time.sleep(0.01)
        assert c.get("k") is None

    def test_ttl_override(self):
        c = Cache(default_ttl=0.0)
        c.set("k", "v", ttl=60.0)
        time.sleep(0.01)
        assert c.get("k") == "v"

    def test_purge_expired(self):
        c = Cache()
        c.set("a", 1, ttl=0.0)
        c.set("b", 2, ttl=60.0)
        time.sleep(0.01)
        purged = c.purge_expired()
        assert purged == 1
        assert c.size() == 1


class TestCacheBulk:
    def test_get_many(self):
        c = Cache()
        c.set("a", 1)
        c.set("b", 2)
        result = c.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2}

    def test_set_many(self):
        c = Cache()
        c.set_many({"a": 1, "b": 2})
        assert c.get("a") == 1
        assert c.get("b") == 2

    def test_delete_many(self):
        c = Cache()
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        removed = c.delete_many(["a", "c", "z"])
        assert removed == 2


class TestCacheEviction:
    def test_lru_eviction(self):
        c = Cache(max_size=2, policy=LRUPolicy())
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # touch a
        c.set("c", 3)  # should evict b (LRU)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_lfu_eviction(self):
        c = Cache(max_size=2, policy=LFUPolicy())
        c.set("a", 1)
        c.get("a")
        c.get("a")  # a: access_count=2
        c.set("b", 2)  # b: access_count=0
        c.set("c", 3)  # evict b (LFU, access_count=0)
        assert c.has("a")
        assert not c.has("b")

    def test_fifo_eviction(self):
        c = Cache(max_size=2, policy=FIFOPolicy())
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)  # evict a (first in)
        assert not c.has("a")
        assert c.has("b")
        assert c.has("c")

    def test_eviction_increments_stats(self):
        c = Cache(max_size=1, policy=LRUPolicy())
        c.set("a", 1)
        c.set("b", 2)
        assert c.stats().evictions == 1


class TestCacheAside:
    def test_get_or_set_factory_called_on_miss(self):
        c = Cache()
        calls = 0

        def factory():
            nonlocal calls
            calls += 1
            return 42

        result = c.get_or_set("k", factory)
        assert result == 42
        assert calls == 1

    def test_get_or_set_uses_cache(self):
        c = Cache()
        calls = 0

        def factory():
            nonlocal calls
            calls += 1
            return "computed"

        c.get_or_set("k", factory)
        c.get_or_set("k", factory)
        assert calls == 1  # factory called only once


class TestCacheStats:
    def test_hit_and_miss_tracking(self):
        c = Cache()
        c.set("k", "v")
        c.get("k")   # hit
        c.get("k")   # hit
        c.get("x")   # miss
        s = c.stats()
        assert s.hits == 2
        assert s.misses == 1

    def test_stats_memory_estimate(self):
        c = Cache()
        c.set("k", "a" * 1000)
        assert c.stats().memory_bytes > 0


class TestCacheNamespaces:
    def test_basic_namespace(self):
        c = Cache()
        ns = c.namespace("users")
        ns.set("alice", {"age": 30})
        assert ns.get("alice") == {"age": 30}

    def test_namespace_isolation(self):
        c = Cache()
        ns1 = c.namespace("ns1")
        ns2 = c.namespace("ns2")
        ns1.set("key", "from-ns1")
        ns2.set("key", "from-ns2")
        assert ns1.get("key") == "from-ns1"
        assert ns2.get("key") == "from-ns2"

    def test_namespace_same_instance(self):
        c = Cache()
        ns_a = c.namespace("x")
        ns_b = c.namespace("x")
        assert ns_a is ns_b

    def test_namespace_delete(self):
        c = Cache()
        ns = c.namespace("test")
        ns.set("k", "v")
        assert ns.delete("k") is True
        assert ns.get("k") is None

    def test_namespace_clear(self):
        c = Cache()
        ns = c.namespace("test")
        ns.set("a", 1)
        ns.set("b", 2)
        removed = ns.clear()
        assert removed == 2
        assert ns.get("a") is None

    def test_namespace_keys(self):
        c = Cache()
        ns = c.namespace("test")
        ns.set("x", 1)
        ns.set("y", 2)
        assert sorted(ns.keys()) == ["x", "y"]

    def test_namespace_has(self):
        c = Cache()
        ns = c.namespace("test")
        assert not ns.has("k")
        ns.set("k", "v")
        assert ns.has("k")

    def test_namespace_ttl(self):
        c = Cache()
        ns = c.namespace("test", default_ttl=0.0)
        ns.set("k", "v")
        time.sleep(0.01)
        assert ns.get("k") is None

    def test_namespace_stats(self):
        c = Cache()
        ns = c.namespace("test")
        ns.set("k", "v")
        ns.get("k")
        ns.get("miss")
        s = ns.stats()
        assert s.hits == 1
        assert s.misses == 1

    def test_namespace_eviction(self):
        c = Cache()
        ns = c.namespace("test", max_size=2, policy=FIFOPolicy())
        ns.set("a", 1)
        ns.set("b", 2)
        ns.set("c", 3)
        assert not ns.has("a")
        assert ns.has("b")
        assert ns.has("c")


class TestCacheThreadSafety:
    def test_concurrent_writes(self):
        c = Cache()
        errors: list[str] = []

        def writer(start: int):
            try:
                for i in range(100):
                    c.set(f"key-{start}-{i}", i)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert c.size() == 400


class TestCacheNoneValues:
    def test_storing_none(self):
        """None is a valid cached value — stored entry exists even though get returns None."""
        c = Cache()
        c.set("k", None)
        assert "k" in c._store
        assert c._store["k"].value is None
        assert c._store["k"].is_expired is False

    def test_has_distinguishes_missing(self):
        c = Cache()
        assert not c.has("missing")
