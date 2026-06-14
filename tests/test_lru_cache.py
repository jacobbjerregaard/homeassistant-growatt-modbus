"""Tests for the small ``LRUCache`` used to memoise register sequences."""
from growatt_api.utils import LRUCache


def test_stores_and_retrieves_values():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    cache["a"] = 1
    assert cache["a"] == 1
    assert "a" in cache
    assert len(cache) == 1


def test_evicts_least_recently_used():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3  # exceeds capacity -> "a" (oldest) is evicted
    assert "a" not in cache
    assert "b" in cache
    assert "c" in cache


def test_access_refreshes_recency():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    cache["a"] = 1
    cache["b"] = 2
    assert cache["a"] == 1  # touching "a" makes "b" the oldest
    cache["c"] = 3  # evicts "b", not "a"
    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache


def test_unlimited_capacity_never_evicts():
    cache: LRUCache[int, int] = LRUCache(capacity=None)
    for i in range(100):
        cache[i] = i
    assert len(cache) == 100


def test_missing_key_raises():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    try:
        _ = cache["missing"]
    except KeyError:
        return
    raise AssertionError("expected KeyError for missing key")


def test_clear_empties_cache():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    cache["a"] = 1
    cache.clear()
    assert len(cache) == 0
