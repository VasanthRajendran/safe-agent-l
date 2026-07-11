import time

import pytest

from safeagentl.network import (
    PartitionTolerantCache,
    Priority,
    PriorityRouter,
    TimeoutToSafeDefault,
)


def test_priority_router_dispatches_critical_before_routine():
    router = PriorityRouter()
    router.submit("routine-1", Priority.ROUTINE)
    router.submit("critical-1", Priority.CRITICAL)
    router.submit("high-1", Priority.HIGH)
    assert list(router.drain()) == ["critical-1", "high-1", "routine-1"]


def test_priority_router_preserves_fifo_within_same_priority():
    router = PriorityRouter()
    router.submit("first", Priority.ROUTINE)
    router.submit("second", Priority.ROUTINE)
    assert list(router.drain()) == ["first", "second"]


def test_priority_router_len_and_empty_drain():
    router = PriorityRouter()
    assert len(router) == 0
    assert router.dispatch_next() is None


def test_timeout_to_safe_default_returns_result_when_fast_enough():
    guard = TimeoutToSafeDefault(timeout=1.0, safe_default=False)
    try:
        result, timed_out = guard.run(lambda: True)
        assert result is True
        assert timed_out is False
    finally:
        guard.shutdown()


def test_timeout_to_safe_default_falls_back_when_slow():
    guard = TimeoutToSafeDefault(timeout=0.05, safe_default="DENY")
    try:
        result, timed_out = guard.run(lambda: time.sleep(0.5))
        assert timed_out is True
        assert result == "DENY"
    finally:
        guard.shutdown()


def test_timeout_to_safe_default_rejects_nonpositive_timeout():
    with pytest.raises(ValueError):
        TimeoutToSafeDefault(timeout=0)


def test_partition_tolerant_cache_starts_stale():
    cache = PartitionTolerantCache(ttl_seconds=60)
    value, stale = cache.get()
    assert value is None
    assert stale is True


def test_partition_tolerant_cache_sync_success_updates_value():
    cache = PartitionTolerantCache(ttl_seconds=60)
    assert cache.sync(lambda: {"max_price": 100}) is True
    value, stale = cache.get()
    assert value == {"max_price": 100}
    assert stale is False


def test_partition_tolerant_cache_retains_last_known_good_on_sync_failure():
    cache = PartitionTolerantCache(ttl_seconds=60)
    cache.sync(lambda: {"max_price": 100})

    def failing_fetch():
        raise ConnectionError("partitioned")

    assert cache.sync(failing_fetch) is False
    value, _ = cache.get()
    assert value == {"max_price": 100}  # unchanged despite the failed sync


def test_partition_tolerant_cache_becomes_stale_after_ttl():
    cache = PartitionTolerantCache(ttl_seconds=0.05)
    cache.sync(lambda: {"max_price": 100})
    assert cache.get()[1] is False
    time.sleep(0.1)
    assert cache.get()[1] is True
