"""Tests for altapi.http.responses."""

import pytest
import httpx

from altapi.http.responses import (
    Response,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
    FileResponse,
)


async def _collect_asgi_response(response, scope):
    messages = []

    async def send(m):
        messages.append(m)

    async def receive():
        return {"type": "http.disconnect"}

    await response(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_response_plain_text():
    r = Response("hello", status_code=201, media_type="text/plain")
    scope = {"type": "http", "headers": []}
    msgs = await _collect_asgi_response(r, scope)
    assert msgs[0]["status"] == 201
    assert msgs[1]["body"] == b"hello"


@pytest.mark.asyncio
async def test_json_response():
    r = JSONResponse({"a": True})
    scope = {"type": "http"}
    msgs = await _collect_asgi_response(r, scope)
    assert b"true" in msgs[1]["body"]


@pytest.mark.asyncio
async def test_redirect_response_location():
    r = RedirectResponse("https://example.com", status_code=302)
    assert r.headers["location"] == "https://example.com"
    scope = {"type": "http"}
    msgs = await _collect_asgi_response(r, scope)
    hdrs = dict(msgs[0]["headers"])
    assert hdrs[b"location"] == b"https://example.com"


@pytest.mark.asyncio
async def test_streaming_response_async_gen():
    async def gen():
        yield b"a"
        yield b"b"

    r = StreamingResponse(gen(), media_type="text/plain")
    scope = {"type": "http"}
    msgs = await _collect_asgi_response(r, scope)
    bodies = [m["body"] for m in msgs if m["type"] == "http.response.body"]
    assert b"".join(bodies) == b"ab"


@pytest.mark.asyncio
async def test_file_response_missing_file(tmp_path):
    p = tmp_path / "missing.bin"
    r = FileResponse(str(p))
    scope = {"type": "http", "headers": []}
    msgs = await _collect_asgi_response(r, scope)
    assert msgs[0]["status"] == 404


@pytest.mark.asyncio
async def test_file_response_serves_file(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("hello", encoding="utf-8")
    r = FileResponse(str(f))
    transport = httpx.ASGITransport(app=r)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("http://test/")
        assert resp.status_code == 200
        assert resp.text == "hello"
        assert "text/plain" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_file_response_range(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"0123456789")
    r = FileResponse(str(f))
    scope = {
        "type": "http",
        "headers": [(b"range", b"bytes=2-5")],
    }
    msgs = await _collect_asgi_response(r, scope)
    assert msgs[0]["status"] == 206
    body = b"".join(m["body"] for m in msgs if m["type"] == "http.response.body")
    assert body == b"2345"


def test_file_response_guess_type():
    r = FileResponse("/x/file.css")
    assert "css" in r._guess_media_type()
