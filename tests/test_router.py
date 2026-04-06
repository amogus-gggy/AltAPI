"""Tests for altapi.router (Cython)."""

import pytest

from altapi.router import Router


def test_static_route_exact_match():
    r = Router()
    r.add_route("/hello", "GET", "h1")
    h, params = r.find_handler("/hello", "get")
    assert h == "h1"
    assert params == {}


def test_static_route_wrong_method():
    r = Router()
    r.add_route("/hello", "GET", "h1")
    h, params = r.find_handler("/hello", "POST")
    assert h is None
    assert params is None


def test_dynamic_int_param():
    r = Router()
    r.add_route("/users/{id:int}", "GET", "user_handler")
    h, params = r.find_handler("/users/42", "GET")
    assert h == "user_handler"
    assert params == {"id": 42}


def test_dynamic_str_param():
    r = Router()
    r.add_route("/items/{name:str}", "GET", "item_handler")
    h, params = r.find_handler("/items/widget", "GET")
    assert params == {"name": "widget"}


def test_dynamic_float_param():
    r = Router()
    r.add_route("/score/{value:float}", "GET", "score_handler")
    h, params = r.find_handler("/score/3.14", "GET")
    assert params == {"value": pytest.approx(3.14)}


def test_dynamic_path_param():
    """`path` converter is identity; each `{...}` matches one URL segment."""
    r = Router()
    r.add_route("/files/{filepath:path}", "GET", "file_handler")
    h, params = r.find_handler("/files/a", "GET")
    assert h == "file_handler"
    assert params == {"filepath": "a"}


def test_invalid_int_returns_no_match():
    r = Router()
    r.add_route("/users/{id:int}", "GET", "h")
    h, params = r.find_handler("/users/notint", "GET")
    assert h is None


def test_unknown_converter_raises():
    r = Router()
    with pytest.raises(ValueError, match="Unknown path type"):
        r.add_route("/x/{y:unknown}", "GET", "h")


def test_websocket_static_and_dynamic():
    r = Router()
    r.add_websocket_route("/ws", "ws1")
    r.add_websocket_route("/room/{name:str}", "ws2")
    h, p = r.find_websocket_handler("/ws")
    assert h == "ws1" and p == {}
    h, p = r.find_websocket_handler("/room/general")
    assert h == "ws2" and p == {"name": "general"}


def test_get_routes():
    r = Router()
    r.add_route("/a", "GET", 1)
    r.add_route("/b", "POST", 2)
    assert set(r.get_routes()) == {"/a", "/b"}


def test_get_websocket_routes():
    r = Router()
    r.add_websocket_route("/ws1", 1)
    assert r.get_websocket_routes() == ["/ws1"]
