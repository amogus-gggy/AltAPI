"""Tests for altapi.http.request."""

import pytest

from altapi.http.request import Request, RequestState


def test_request_state():
    s = RequestState()
    s.user_id = 1
    assert s.user_id == 1
    assert s.get("user_id") == 1
    assert s.get("missing", "d") == "d"
    s.clear()
    with pytest.raises(AttributeError):
        _ = s.user_id


def test_request_basic_scope():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/p",
        "query_string": b"a=1&b=2",
        "headers": [(b"Content-Type", b"application/json")],
    }

    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}

    req = Request(scope, receive, {"id": 5})
    assert req.method == "POST"
    assert req.path == "/p"
    assert "a=1" in req.query_string
    assert req.path_params["id"] == 5
    # Header keys preserve ASGI casing (e.g. Content-Type)
    assert req.headers_dict["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_request_json_body():
    scope = {"method": "GET", "path": "/", "headers": [], "query_string": b""}

    async def receive():
        return {"type": "http.request", "body": b'{"x": 1}', "more_body": False}

    req = Request(scope, receive)
    data = await req.json()
    assert data == {"x": 1}


@pytest.mark.asyncio
async def test_request_form_urlencoded():
    scope = {
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": b"name=test&age=2", "more_body": False}

    req = Request(scope, receive)
    form = await req.form()
    assert form["name"] == "test"
    assert form["age"] == "2"


@pytest.mark.asyncio
async def test_request_multipart_simple():
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="field1"\r\n\r\n'
        "value1\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    scope = {
        "method": "POST",
        "path": "/",
        "headers": [
            (b"content-type", f"multipart/form-data; boundary={boundary}".encode())
        ],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    req = Request(scope, receive)
    form = await req.form()
    assert form.get("field1") == "value1"
