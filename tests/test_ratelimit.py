"""Tests for altapi.ratelimit."""

import uuid

import pytest

from altapi.ratelimit import (
    rate_limit,
    rate_limit_batch,
    set_storage,
    use_shared_memory,
)
from altapi.ratelimit.storage import (
    InMemoryRateLimitStorage,
    RateLimitResult,
    SharedMemoryRateLimitStorage,
)
from altapi.http.responses import JSONResponse


@pytest.mark.asyncio
async def test_in_memory_storage_check_and_increment():
    s = InMemoryRateLimitStorage()
    r = await s.check_rate_limit("k", limit=2, period=60.0)
    assert r.allowed is True
    assert r.remaining == 2
    await s.increment("k", 60.0)
    r2 = await s.check_rate_limit("k", limit=2, period=60.0)
    assert r2.remaining == 1


@pytest.mark.asyncio
async def test_shared_memory_storage(tmp_path_factory):
    name = f"altapi_test_{uuid.uuid4().hex}"
    storage = SharedMemoryRateLimitStorage(name=name, max_keys=100, max_timestamps=20)
    try:
        r = await storage.check_rate_limit("key1", limit=3, period=10.0)
        assert isinstance(r, RateLimitResult)
        assert r.allowed
        await storage.increment("key1", 10.0)
        r2 = await storage.check_rate_limit("key1", limit=3, period=10.0)
        assert r2.remaining == 2
    finally:
        storage.cleanup()


@pytest.mark.asyncio
async def test_rate_limit_allows_then_blocks(reset_rate_limit_storage):
    @rate_limit(limit=2, period=60)
    async def handler(request):
        return JSONResponse({"ok": True})

    scope = {"type": "http", "client": ("127.0.0.1", 1234), "headers": []}

    class Req:
        def __init__(self):
            self.scope = scope

    req = Req()
    await handler(req)
    await handler(req)
    r3 = await handler(req)
    from altapi.http.responses import JSONResponse as JR

    assert isinstance(r3, JR)
    assert r3.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_skip_when(reset_rate_limit_storage):
    @rate_limit(limit=0, period=60, skip_when=lambda r: True)
    async def handler(request):
        return JSONResponse({"skipped": True})

    class Req:
        scope = {"client": ("1.2.3.4", 0), "headers": []}

    r = await handler(Req())
    import orjson

    body = r.content if isinstance(r.content, (bytes, str)) else r._encoded_body
    if isinstance(body, str):
        body = body.encode()
    data = orjson.loads(body)
    assert data["skipped"] is True


@pytest.mark.asyncio
async def test_rate_limit_batch(reset_rate_limit_storage):
    @rate_limit_batch([(2, 60), (5, 60)])
    async def handler(request):
        return JSONResponse({"ok": True})

    class Req:
        scope = {"client": ("10.0.0.1", 0), "headers": []}

    req = Req()
    await handler(req)
    await handler(req)
    r3 = await handler(req)
    assert r3.status_code == 429


def test_set_storage_and_use_shared_memory():
    use_shared_memory(False)
    set_storage(InMemoryRateLimitStorage())
    import altapi.ratelimit.limit as lm

    assert isinstance(lm._get_storage(), InMemoryRateLimitStorage)
    use_shared_memory(True)
    set_storage(None)
