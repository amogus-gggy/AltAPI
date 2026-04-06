"""Tests for altapi.caching.cache."""

import time

import pytest

from altapi.caching.cache import (
    CacheEntry,
    CacheManager,
    CacheMiddleware,
    InMemoryCache,
    cache as cache_decorator,
)


@pytest.mark.asyncio
async def test_in_memory_cache_set_get():
    c = InMemoryCache(max_size=10)
    await c.set(
        "k",
        {"status": 200, "headers": [(b"content-type", b"text/plain")], "body": b"hi"},
        expires=60,
    )
    entry = await c.get("k")
    assert entry is not None
    assert entry.body == b"hi"
    assert entry.status == 200


@pytest.mark.asyncio
async def test_in_memory_cache_expires_none_means_ttl_zero():
    c = InMemoryCache()
    await c.set(
        "k",
        {"status": 200, "headers": [], "body": b"x"},
        expires=None,
    )
    entry = await c.get("k")
    assert entry is None


@pytest.mark.asyncio
async def test_in_memory_cache_lru_eviction():
    c = InMemoryCache(max_size=2)
    for i in range(3):
        await c.set(
            f"k{i}",
            {"status": 200, "headers": [], "body": str(i).encode()},
            expires=3600,
        )
    assert await c.get("k0") is None
    assert (await c.get("k2")) is not None


@pytest.mark.asyncio
async def test_cache_manager_default():
    CacheManager._default_backend = None
    CacheManager._backends.clear()
    b1 = CacheManager.get_default_backend()
    b2 = CacheManager.get_default_backend()
    assert b1 is b2


@pytest.mark.asyncio
async def test_cache_manager_named_backend():
    CacheManager._backends.clear()
    c = InMemoryCache()
    CacheManager.register_backend("mine", c)
    assert CacheManager.get_backend("mine") is c
    with pytest.raises(ValueError, match="not found"):
        CacheManager.get_backend("missing")


def test_cache_decorator_metadata():
    @cache_decorator(expires=120, key_prefix="p")
    async def handler(request):
        return None

    assert handler._cache_expires == 120
    assert handler._cache_key_prefix == "p"


@pytest.mark.asyncio
async def test_cache_middleware_hit():
    backend = InMemoryCache()
    responses = []

    async def inner_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {"type": "http.response.body", "body": b"cached-body", "more_body": False}
        )

    mw = CacheMiddleware(inner_app, cache_timeout=300, backend=backend)
    mw.register_handler("/api/x", 3600)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": "/api/x", "query_string": b""}

    async def send(msg):
        responses.append(msg)

    await mw(scope, receive, send)

    responses.clear()
    await mw(scope, receive, send)
    assert responses[0]["type"] == "http.response.start"
    assert responses[0]["status"] == 200
    assert responses[1]["body"] == b"cached-body"


@pytest.mark.asyncio
async def test_cache_middleware_skips_non_get():
    backend = InMemoryCache()

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"x", "more_body": False})

    mw = CacheMiddleware(inner, backend=backend)
    mw.register_handler("/x", 60)

    out = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "POST", "path": "/x", "query_string": b""}

    async def send(msg):
        out.append(msg)

    await mw(scope, receive, send)
    assert len(out) == 2


def test_cache_middleware_match_path():
    mw = CacheMiddleware(lambda s, r, se: None, backend=InMemoryCache())
    assert mw._match_path("/users/1", "/users/{id:int}") is True
    assert mw._match_path("/other", "/users/{id:int}") is False


@pytest.mark.asyncio
async def test_cache_entry_direct_store():
    c = InMemoryCache()
    entry = CacheEntry(200, [(b"x", b"y")], b"data", time.monotonic() + 100)
    await c.set("k", entry)
    got = await c.get("k")
    assert got is entry
