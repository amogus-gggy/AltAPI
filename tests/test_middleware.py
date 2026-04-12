"""Tests for altapi.middleware."""

import pytest

from altapi.middleware.middleware import BaseMiddleware, Middleware
from altapi.middleware.cors import CORSMiddleware


def test_middleware_build():
    calls = []

    class MW:
        def __init__(self, app, x=1):
            self.app = app
            self.x = x

        async def __call__(self, scope, receive, send):
            calls.append(self.x)
            await self.app(scope, receive, send)

    inner = lambda s, r, se: None
    m = Middleware(MW, x=42)
    built = m.build(inner)
    assert isinstance(built, MW)
    assert built.app is inner
    assert built.x == 42


@pytest.mark.asyncio
async def test_base_middleware_delegates():
    seen = []

    async def app(scope, receive, send):
        seen.append("inner")

    class Trailing(BaseMiddleware):
        async def __call__(self, scope, receive, send):
            seen.append("mw")
            await super().__call__(scope, receive, send)

    mw = Trailing(app)
    await mw({"type": "http"}, None, None)
    assert seen == ["mw", "inner"]

@pytest.mark.asyncio
async def test_cors_adds_headers_on_response_start():
    messages = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"ok",
        })

    mw = CORSMiddleware(app)

    async def send(msg):
        messages.append(msg)

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"origin", b"http://example.com")],
        "path": "/"
    }

    await mw(scope, None, send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = dict(start["headers"])

    assert b"access-control-allow-origin" in headers
    assert headers[b"access-control-allow-origin"] == b"*"


@pytest.mark.asyncio
async def test_cors_respects_allowed_origins():
    messages = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"ok",
        })

    mw = CORSMiddleware(app, allow_origins=["http://allowed.com"])

    async def send(msg):
        messages.append(msg)

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"origin", b"http://allowed.com")],
        "path": "/"
    }

    await mw(scope, None, send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = dict(start["headers"])

    assert headers[b"access-control-allow-origin"] == b"http://allowed.com"


@pytest.mark.asyncio
async def test_cors_blocks_disallowed_origin():
    messages = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"ok",
        })

    mw = CORSMiddleware(app, allow_origins=["http://allowed.com"])

    async def send(msg):
        messages.append(msg)

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"origin", b"http://evil.com")],
        "path": "/"
    }

    await mw(scope, None, send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = dict(start["headers"])

    assert b"access-control-allow-origin" not in headers


@pytest.mark.asyncio
async def test_cors_preflight_options():
    messages = []

    async def app(scope, receive, send):
        raise AssertionError("App should not be called for OPTIONS")

    mw = CORSMiddleware(app)

    async def send(msg):
        messages.append(msg)

    scope = {
        "type": "http",
        "method": "OPTIONS",
        "headers": [(b"origin", b"http://example.com")],
        "path": "/"
    }

    await mw(scope, None, send)

    start = next(m for m in messages if m["type"] == "http.response.start")

    assert start["status"] == 204

    headers = dict(start["headers"])
    assert b"access-control-allow-origin" in headers
    assert b"access-control-allow-methods" in headers
    assert b"access-control-allow-headers" in headers

@pytest.mark.asyncio
async def test_cors_credentials_header():
    messages = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"ok",
        })

    mw = CORSMiddleware(app, allow_credentials=True)

    async def send(msg):
        messages.append(msg)

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"origin", b"http://example.com")],
        "path": "/"
    }

    await mw(scope, None, send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = dict(start["headers"])

    assert headers[b"access-control-allow-credentials"] == b"true"
