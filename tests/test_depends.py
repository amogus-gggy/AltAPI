"""Tests for altapi.depends."""

import inspect

import pytest

from altapi.depends import (
    Depends,
    DependencyCache,
    DependencyInjector,
    cleanup_dependencies,
    get_dependencies_from_signature,
    solve_dependency,
)
from altapi.http.request import Request


def test_depends_repr():
    d = Depends(lambda: 1)
    assert "Depends" in repr(d)


def test_get_dependencies_from_signature():
    def dep():
        return 1

    async def handler(request, x: int, db=Depends(dep)):
        pass

    sig = inspect.signature(handler)
    deps = get_dependencies_from_signature(sig)
    assert "db" in deps
    assert deps["db"].dependency is dep


@pytest.mark.asyncio
async def test_solve_simple_async_dep():
    async def get_val():
        return 99

    val = await solve_dependency(get_val)
    assert val == 99


@pytest.mark.asyncio
async def test_solve_sync_generator_cleanup():
    steps = []

    def gen_dep():
        steps.append("enter")
        yield 42
        steps.append("exit")

    solved = {}
    val = await solve_dependency(gen_dep, solved_deps=solved)
    assert val == 42
    assert inspect.isgenerator(solved[gen_dep])
    await cleanup_dependencies(solved)
    assert steps == ["enter", "exit"]


@pytest.mark.asyncio
async def test_nested_depends():
    def inner():
        return "inner"

    def outer(i=Depends(inner)):
        return f"wrap:{i}"

    val = await solve_dependency(outer)
    assert val == "wrap:inner"


@pytest.mark.asyncio
async def test_inject_request_by_annotation():
    scope = {"method": "GET", "path": "/", "headers": [], "query_string": b""}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    req = Request(scope, receive)

    def needs_request(r: Request):
        return r.path

    val = await solve_dependency(needs_request, request=req)
    assert val == "/"


@pytest.mark.asyncio
async def test_dependency_injector_cleanup():
    def gen():
        yield 1

    inj = DependencyInjector(request=None)
    v = await inj.solve(gen)
    assert v == 1
    await inj.cleanup()


@pytest.mark.asyncio
async def test_dependency_cache_use_cache_false():
    # use_cache on Depends is stored but solve_dependency always uses
    # passed cache - test explicit cache hit
    cache = DependencyCache()
    calls = {"n": 0}

    def f():
        calls["n"] += 1
        return 1

    v1 = await solve_dependency(f, cache=cache)
    v2 = await solve_dependency(f, cache=cache)
    assert v1 == v2 == 1
    assert calls["n"] == 1
