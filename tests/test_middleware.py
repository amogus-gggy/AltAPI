"""Tests for altapi.middleware."""

import pytest

from altapi.middleware.middleware import BaseMiddleware, Middleware


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
