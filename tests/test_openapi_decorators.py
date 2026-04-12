"""Tests for altapi.openapi_decorators."""

from altapi.openapi_decorators import (
    deprecated,
    openapi_summary,
    openapi_description,
    tag,
)


def test_openapi_summary_decorator():
    @openapi_summary("Test Summary")
    async def f(request):
        """ignored"""
        pass

    assert f._openapi_metadata["summary"] == "Test Summary"


def test_openapi_description_decorator():
    @openapi_description("Test Description")
    async def f(request):
        pass

    assert f._openapi_metadata["description"] == "Test Description"


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


def test_multiple_decorators_merge():
    @openapi_summary("Summary")
    @openapi_description("Description")
    @tag("tag1", "tag2")
    async def i(request):
        pass

    meta = i._openapi_metadata
    assert meta["summary"] == "Summary"
    assert meta["description"] == "Description"
    assert meta["tags"] == ["tag1", "tag2"]
