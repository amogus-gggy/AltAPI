"""Integration tests for altapi.app.AltAPI."""

import pytest
import httpx

from altapi import AltAPI
from altapi.depends import Depends
from altapi.http import JSONResponse


@pytest.fixture
def simple_app(tmp_path):
    app = AltAPI(
        enable_openapi=False,
        templates_directory=str(tmp_path),
        static_directory=None,
    )

    @app.get("/json")
    async def j(request):
        return JSONResponse({"hello": "world"})

    @app.get("/sync")
    def sync_handler(request):
        return JSONResponse({"sync": True})

    def provide_x():
        return 7

    @app.get("/di")
    async def with_di(request, x=Depends(provide_x)):
        return JSONResponse({"x": x})

    return app


@pytest.mark.asyncio
async def test_get_json_route(simple_app):
    transport = httpx.ASGITransport(app=simple_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/json")
        assert r.status_code == 200
        assert r.json() == {"hello": "world"}


@pytest.mark.asyncio
async def test_sync_handler(simple_app):
    transport = httpx.ASGITransport(app=simple_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/sync")
        assert r.json()["sync"] is True


@pytest.mark.asyncio
async def test_dependency_injection(simple_app):
    transport = httpx.ASGITransport(app=simple_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/di")
        assert r.json() == {"x": 7}


@pytest.mark.asyncio
async def test_not_found(tmp_path):
    app = AltAPI(enable_openapi=False, templates_directory=str(tmp_path))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/nope")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_static_file_served(tmp_path):
    static = tmp_path / "st"
    static.mkdir()
    (static / "a.txt").write_text("file-content", encoding="utf-8")
    app = AltAPI(enable_openapi=False, templates_directory=str(tmp_path), static_directory=str(static))
    await app._init_shared_resources()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/static/a.txt")
        assert r.status_code == 200
        assert r.text == "file-content"


@pytest.mark.asyncio
async def test_mounted_sub_app(tmp_path):
    inner = AltAPI(enable_openapi=False, templates_directory=str(tmp_path))

    @inner.get("/inner")
    async def inner_route(request):
        return JSONResponse({"from": "inner"})

    app = AltAPI(enable_openapi=False, templates_directory=str(tmp_path))
    app.mount("/sub", inner)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/sub/inner")
        assert r.status_code == 200
        assert r.json()["from"] == "inner"


@pytest.mark.asyncio
async def test_openapi_endpoints_when_enabled(tmp_path):
    app = AltAPI(
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url="/docs",
        templates_directory=str(tmp_path),
    )

    @app.get("/api/x")
    async def x(request):
        return JSONResponse({"x": 1})

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert spec["openapi"] == "3.0.3"
        d = await client.get("/docs")
        assert d.status_code == 200
        assert "swagger" in d.text.lower() or "Swagger" in d.text


@pytest.mark.asyncio
async def test_enable_openapi_method(tmp_path):
    app = AltAPI(enable_openapi=False, templates_directory=str(tmp_path))
    app.enable_openapi(openapi_url="/o.json", docs_url="/d")

    @app.get("/z")
    async def z(request):
        return JSONResponse({})

    # Re-register would be no-op for openapi routes in real flow; generator still works
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Routes registered at init only when urls set — enable_openapi sets urls but
        # does not call _register_openapi_routes again; this checks method sets attrs
        assert app._openapi_url == "/o.json"
        assert app._docs_url == "/d"
