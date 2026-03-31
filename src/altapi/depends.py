"""
Dependency Injection system for AltAPI.

Fast and lightweight DI with support for:
- Generator-based dependencies (with cleanup)
- Nested dependencies
- Async and sync dependencies
- Auto-injection of Request
"""
import inspect
from typing import Any, Callable, Dict, List, Optional, AsyncIterator, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from .http.request import Request


class Depends:
    """
    Marker class for dependency injection.

    Usage:
        def get_db():
            db = Database()
            try:
                yield db
            finally:
                db.close()

        @app.get("/users/{id:int}")
        async def get_user(request, id: int, db=Depends(get_db)):
            user = await db.get_user(id)
            return JSONResponse(user)
    """
    __slots__ = ('dependency', 'use_cache')

    def __init__(self, dependency: Callable, use_cache: bool = True):
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self):
        dep_name = getattr(self.dependency, '__name__', repr(self.dependency))
        return f"Depends({dep_name})"


class DependencyCache:
    """Per-request cache for dependencies."""
    __slots__ = ('_cache',)

    def __init__(self):
        self._cache: Dict[Callable, Any] = {}

    def get(self, dependency: Callable) -> Optional[Any]:
        return self._cache.get(dependency)

    def set(self, dependency: Callable, value: Any):
        self._cache[dependency] = value

    def clear(self):
        self._cache.clear()


async def solve_dependency(
    dependency: Callable,
    cache: Optional[DependencyCache] = None,
    solved_deps: Optional[Dict[Callable, Any]] = None,
    request: Any = None,
) -> Any:
    """
    Solve a single dependency (recursively handles nested dependencies).

    Args:
        dependency: The dependency callable
        cache: Per-request cache (for use_cache=True)
        solved_deps: Dict of already solved dependencies
        request: Request object (passed automatically to dependencies)

    Returns:
        The resolved dependency value
    """
    if solved_deps is None:
        solved_deps = {}

    # Check cache first
    if cache is not None:
        cached = cache.get(dependency)
        if cached is not None:
            return cached

    # Get signature
    sig = inspect.signature(dependency)
    params = sig.parameters

    # Solve nested dependencies and auto-inject request
    kwargs = {}
    for name, param in params.items():
        default = param.default
        if isinstance(default, Depends):
            # Nested dependency
            value = await solve_dependency(
                default.dependency,
                cache=cache,
                solved_deps=solved_deps,
                request=request,
            )
            kwargs[name] = value
        elif param.annotation is not inspect.Parameter.empty:
            # Check if parameter is Request type
            if hasattr(param.annotation, '__name__') and param.annotation.__name__ == 'Request':
                if request is not None:
                    kwargs[name] = request
            elif default is not inspect.Parameter.empty:
                kwargs[name] = default
        # Skip required parameters without default (they should be provided)

    # Call dependency
    if inspect.iscoroutinefunction(dependency):
        # Async dependency
        if inspect.isgeneratorfunction(dependency):
            # Async generator - get value, store cleanup
            gen = dependency(**kwargs)
            value = await gen.__anext__()
            # Store cleanup callback
            solved_deps[dependency] = gen
        else:
            # Regular async function
            value = await dependency(**kwargs)
            solved_deps[dependency] = value
    else:
        # Sync dependency
        if inspect.isgeneratorfunction(dependency):
            # Sync generator - get value, store cleanup
            gen = dependency(**kwargs)
            value = next(gen)
            # Store cleanup callback
            solved_deps[dependency] = gen
        else:
            # Regular sync function
            value = dependency(**kwargs)
            solved_deps[dependency] = value

    # Cache if enabled
    if cache is not None:
        cache.set(dependency, value)

    return value


async def cleanup_dependencies(solved_deps: Dict[Callable, Any]):
    """
    Cleanup generator-based dependencies.

    Args:
        solved_deps: Dict mapping dependencies to their values/generators
    """
    for dep, value in solved_deps.items():
        # Check if it's a generator (needs cleanup)
        if inspect.isasyncgen(value):
            try:
                await value.asend(None)
            except StopAsyncIteration:
                pass
        elif inspect.isgenerator(value):
            try:
                next(value)
            except StopIteration:
                pass
        # Regular values don't need cleanup


def get_dependencies_from_signature(sig: inspect.Signature) -> Dict[str, Depends]:
    """
    Extract Depends markers from function signature.

    Args:
        sig: Function signature

    Returns:
        Dict mapping parameter names to Depends objects
    """
    deps = {}
    for name, param in sig.parameters.items():
        if isinstance(param.default, Depends):
            deps[name] = param.default
    return deps


class DependencyInjector:
    """
    Per-request dependency injector.

    Manages dependency resolution and cleanup for a single request.
    """
    __slots__ = ('_cache', '_solved_deps', '_request')

    def __init__(self, request: Any = None):
        self._cache = DependencyCache()
        self._solved_deps: Dict[Callable, Any] = {}
        self._request = request

    async def solve(self, dependency: Callable) -> Any:
        """Solve a dependency and track for cleanup."""
        return await solve_dependency(
            dependency,
            cache=self._cache,
            solved_deps=self._solved_deps,
            request=self._request,
        )

    async def cleanup(self):
        """Cleanup all generator-based dependencies."""
        await cleanup_dependencies(self._solved_deps)

    def clear(self):
        """Clear cache and solved deps."""
        self._cache.clear()
        self._solved_deps.clear()
