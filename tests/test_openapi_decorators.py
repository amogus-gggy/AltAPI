"""Tests for altapi.openapi_decorators."""

from altapi.openapi_decorators import (
    deprecated,
    describe_request_body,
    describe_responses,
    openapi,
    tag,
)


def test_openapi_decorator_merges_metadata():
    @openapi(summary="S", tags=["a"], deprecated=True)
    async def f(request):
        """ignored"""
        pass

    assert f._openapi_metadata["summary"] == "S"
    assert f._openapi_metadata["tags"] == ["a"]
    assert f._openapi_metadata["deprecated"] is True


def test_tag_decorator():
    @tag("one", "two")
    async def g(request):
        pass

    assert g._openapi_metadata["tags"] == ["one", "two"]


def test_deprecated_decorator():
    @deprecated
    async def h(request):
        pass

    assert h._openapi_metadata["deprecated"] is True


def test_describe_responses():
    @describe_responses({"200": {"description": "OK"}})
    async def i(request):
        pass

    assert "200" in i._openapi_metadata["responses"]


def test_describe_request_body_with_content():
    schema = {
        "content": {
            "application/json": {"schema": {"type": "object"}},
        }
    }

    @describe_request_body(schema)
    async def j(request):
        pass

    rb = j._openapi_metadata["request_body"]
    assert "application/json" in rb["content"]
