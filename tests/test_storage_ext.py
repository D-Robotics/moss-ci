import pytest
from moss_ci.storage.object_store import ObjectStore
from moss_ci.storage.cache import CacheManager


class TestObjectStore:
    def test_put_and_get(self, tmp_path):
        store = ObjectStore(backend="local", local_dir=str(tmp_path))
        store.put("test/key", b"hello world")
        assert store.get("test/key") == b"hello world"

    def test_get_missing(self, tmp_path):
        store = ObjectStore(backend="local", local_dir=str(tmp_path))
        assert store.get("nonexistent") is None


class TestCacheManager:
    def test_set_and_get(self):
        cache = CacheManager(backend="memory")
        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_get_missing(self):
        cache = CacheManager(backend="memory")
        assert cache.get("missing") is None

    def test_ttl_expiry(self):
        cache = CacheManager(backend="memory")
        cache.set("key1", "value1", ttl=-1)  # immediate expiry
        assert cache.get("key1") is None
