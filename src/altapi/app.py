import asyncio
import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any, Union, Type

from .http.responses import HTMLResponse

from .router import Router
from .websocket.ws import WebSocket
from .http.request import Request
from .http.responses import FileResponse, JSONResponse
from .middleware.middleware import Middleware, ASGIApp
from .templating.default_templates import DEFAULT_404_BODY, DEFAULT_500_BODY
from .templating.templates import Jinja2Templates, set_default_templates_directory
from .caching.cache import CacheMiddleware, CacheManager, InMemoryCache
from .depends import DependencyInjector, get_dependencies_from_signature
from .openapi_spec import OpenAPIGenerator
from .pydantic_schemas import (
    is_pydantic_model,
    model_to_openapi_ref,
    model_to_request_body_schema,
    model_to_response_schema,
    extract_pydantic_schemas,
)
# Rate limiting now uses shared memory - no network overhead

_sync_executor = ThreadPoolExecutor(max_workers=10)


def _run_gc_optimize():
    """
    Garbage collector optimization.

    Applies the following optimizations:
    - Forced garbage collection
    - Object freezing
    - Increased GC thresholds
    """
    import gc

    gc.collect(2)
    gc.freeze()
    allocs, gen1, gen2 = gc.get_threshold()
    allocs = 50000
    gen1 = gen1 * 2
    gen2 = gen2 * 2
    gc.set_threshold(allocs, gen1, gen2)


class AltAPI:
    """
    Main AltAPI application class.

    ASGI framework for building web applications with support for:
    - HTTP routes (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE, CONNECT)
    - WebSocket connections
    - Middleware
    - Jinja2 templates
    - Static files
    - Caching
    """

    def __init__(
        self,
        middleware: List[Middleware] = None,
        templates_directory: Union[str, os.PathLike] = "templates",
        static_directory: Optional[Union[str, os.PathLike]] = None,
        cache_timeout: int = 300,
        # OpenAPI/Swagger settings
        enable_openapi: bool = True,
        openapi_url: Optional[str] = "/openapi.json",
        docs_url: Optional[str] = "/docs",
        title: str = "AltAPI",
        version: str = "0.1.0",
        description: str = "",
    ):
        """
        Initialize AltAPI application.

        Args:
            middleware: List of middleware for the application
            templates_directory: Directory with Jinja2 templates
            static_directory: Directory with static files (optional)
            cache_timeout: Default cache lifetime in seconds
            enable_openapi: Enable OpenAPI/SwaggerUI (set False for production)
            openapi_url: URL for OpenAPI JSON specification (None to disable)
            docs_url: URL for SwaggerUI documentation (None to disable)
            title: API title for OpenAPI spec
            version: API version for OpenAPI spec
            description: API description for OpenAPI spec
        """
        self._router = Router()
        self._middlewares = middleware or []
        self._mounted_apps: Dict[str, Any] = {}
        self._static_dirs: Dict[str, str] = {}
        self._manager_process = None
        self._app_built = False

        self._core = self._build_core()
        self._app = self._core  # Will be built with middlewares in run()
        self._sync_executor = _sync_executor

        # Initialize Jinja2 templates with optimized settings
        self._templates_directory = str(templates_directory)
        self._templates = Jinja2Templates(
            self._templates_directory,
            auto_reload=False,  # Disable auto-reload for production
            cache_size=4096,  # Cache compiled templates
        )

        # Set global templates directory for render_template
        set_default_templates_directory(self._templates_directory)

        # Initialize static directory (if specified)
        if static_directory is not None:
            self._static_directory = str(static_directory)
            self.mount("/static", directory=self._static_directory)
        else:
            self._static_directory = None

        # Initialize per-worker in-memory cache (fast, no IPC overhead)
        # Each worker has its own cache - no sharing between workers
        self._cache_backend: Optional[InMemoryCache] = None
        self._cache_timeout = cache_timeout
        self._cache_middleware: Optional[CacheMiddleware] = None
        # CacheMiddleware is NOT added by default - only added when @cache routes are registered
        self._cache_middleware_needed = False

        # Initialize OpenAPI generator
        self._openapi_generator = OpenAPIGenerator(
            title=title,
            version=version,
            description=description,
        )

        # Handle OpenAPI settings
        if not enable_openapi:
            self._openapi_url = None
            self._docs_url = None
        else:
            self._openapi_url = openapi_url
            self._docs_url = docs_url

        # Store route metadata for OpenAPI generation
        self._registered_routes: List[Dict[str, Any]] = []
        self._openapi_routes_registered = False

        # Mount /openapi.json and /docs only; HTTP routes are added to the spec in
        # route() after @app.get etc. run (decorators execute after AltAPI.__init__).
        if self._openapi_url or self._docs_url:
            self._register_openapi_routes()

    async def _init_shared_resources(self):
        """Initialize shared resources (called in lifespan)."""
        # Initialize per-worker in-memory cache backend (fast, no IPC)
        self._cache_backend = InMemoryCache()
        CacheManager.set_default_backend(self._cache_backend)

        # Rebuild app with middlewares and register cache routes
        if not self._app_built:
            self._app = self._build_middlewares(self._core)
            self._app_built = True

    @property
    def templates(self) -> Jinja2Templates:
        """Return Jinja2Templates object for template rendering."""
        return self._templates

    @property
    def static_directory(self) -> Optional[str]:
        """Return path to static files directory (if configured)."""
        return self._static_directory

    @property
    def cache_backend(self) -> Optional[InMemoryCache]:
        """Return per-worker in-memory cache backend."""
        return self._cache_backend

    def route(
        self,
        path,
        methods=None,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering HTTP routes.

        Args:
            path: Route path
            methods: List of HTTP methods (default ["GET"])
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated

        Returns:
            Decorator for registering handler function

        Example:
            class UserCreate(BaseModel):
                name: str
                email: str

            class UserResponse(BaseModel):
                id: int
                name: str
                email: str

            @app.post("/api/users", request_model=UserCreate, response_model=UserResponse)
            async def create_user(request):
                data = await request.json()
                return JSONResponse({"id": 1, **data})
        """
        methods = methods or ["GET"]

        def decorator(func):
            # Pre-compute handler metadata at registration time (performance optimization)
            sig = inspect.signature(func)
            is_async = inspect.iscoroutinefunction(func)
            depends_map = get_dependencies_from_signature(sig)
            handler_params = list(sig.parameters.keys())
            has_request = "request" in handler_params

            # Store metadata on the function for fast access during requests
            func._handler_meta = {
                "sig": sig,
                "is_async": is_async,
                "depends_map": depends_map,
                "handler_params": handler_params,
                "has_request": has_request,
            }

            # Build OpenAPI metadata from Pydantic models
            openapi_request_body = None
            openapi_responses = None

            if request_model is not None and is_pydantic_model(request_model):
                openapi_request_body = model_to_request_body_schema(
                    request_model,
                    description=f"{func.__name__} request body",
                )

            if response_model is not None and is_pydantic_model(response_model):
                openapi_responses = model_to_response_schema(
                    response_model,
                    status_code="200",
                    description="Successful Response",
                )

            # Store Pydantic models on function for OpenAPI generation
            func._openapi_pydantic_models = {
                "request_model": request_model,
                "response_model": response_model,
            }

            for m in methods:
                self._router.add_route(path, m.upper(), func)
                # Register route for OpenAPI
                self._registered_routes.append(
                    {
                        "path": path,
                        "method": m.upper(),
                        "handler": func,
                        "request_model": request_model,
                        "response_model": response_model,
                        "summary": summary,
                        "description": description,
                        "tags": tags,
                        "deprecated": deprecated,
                    }
                )
                self._add_route_to_openapi(
                    path,
                    m.upper(),
                    func,
                    request_model=request_model,
                    response_model=response_model,
                    summary=summary,
                    description=description,
                    tags=tags,
                    deprecated=deprecated,
                )

            # Register for caching if @cache decorator was applied
            # Check the function itself first, then unwrap to find _cache_expires
            check_func = func
            cache_expires = None

            # Check current function and wrapped chain for _cache_expires
            while check_func is not None:
                if hasattr(check_func, "_cache_expires"):
                    cache_expires = check_func._cache_expires
                    break
                if hasattr(check_func, "__wrapped__"):
                    check_func = check_func.__wrapped__
                else:
                    break

            if cache_expires is not None:
                if not hasattr(self, "_cache_routes"):
                    self._cache_routes = []
                self._cache_routes.append((path, cache_expires))
                # Only add CacheMiddleware when we actually have cached routes
                if not self._cache_middleware_needed:
                    self._cache_middleware_needed = True
                    self._middlewares.append(
                        Middleware(CacheMiddleware, cache_timeout=self._cache_timeout)
                    )

            return func

        return decorator

    def get(
        self,
        path,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering GET routes.

        Args:
            path: Route path
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated
        """
        return self.route(
            path,
            ["GET"],
            request_model=request_model,
            response_model=response_model,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
        )

    def post(
        self,
        path,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering POST routes.

        Args:
            path: Route path
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated
        """
        return self.route(
            path,
            ["POST"],
            request_model=request_model,
            response_model=response_model,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
        )

    def put(
        self,
        path,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering PUT routes.

        Args:
            path: Route path
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated
        """
        return self.route(
            path,
            ["PUT"],
            request_model=request_model,
            response_model=response_model,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
        )

    def delete(
        self,
        path,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering DELETE routes.

        Args:
            path: Route path
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated
        """
        return self.route(
            path,
            ["DELETE"],
            request_model=request_model,
            response_model=response_model,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
        )

    def patch(
        self,
        path,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Decorator for registering PATCH routes.

        Args:
            path: Route path
            request_model: Pydantic model for request body schema (JSON only)
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated
        """
        return self.route(
            path,
            ["PATCH"],
            request_model=request_model,
            response_model=response_model,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
        )

    def head(self, path):
        """
        Decorator for registering HEAD routes.

        Args:
            path: Route path
        """
        return self.route(path, ["HEAD"])

    def options(self, path):
        """
        Decorator for registering OPTIONS routes.

        Args:
            path: Route path
        """
        return self.route(path, ["OPTIONS"])

    def trace(self, path):
        """
        Decorator for registering TRACE routes.

        Args:
            path: Route path
        """
        return self.route(path, ["TRACE"])

    def connect(self, path):
        """
        Decorator for registering CONNECT routes.

        Args:
            path: Route path
        """
        return self.route(path, ["CONNECT"])

    def websocket(self, path):
        """
        Decorator for registering WebSocket routes.

        Args:
            path: Route path for WebSocket connections
        """

        def decorator(func):
            self._router.add_websocket_route(path, func)
            return func

        return decorator

    def enable_openapi(
        self,
        openapi_url: Optional[str] = "/openapi.json",
        docs_url: Optional[str] = "/docs",
    ):
        """
        Enable OpenAPI specification and SwaggerUI documentation.

        Args:
            openapi_url: URL for OpenAPI JSON specification (None to disable)
            docs_url: URL for SwaggerUI documentation (None to disable)
        """
        self._openapi_url = openapi_url
        self._docs_url = docs_url
        if (
            self._openapi_url or self._docs_url
        ) and not self._openapi_routes_registered:
            self._register_openapi_routes()

    def cache(
        self,
        path: str,
        expires: int = 300,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ):
        """
        Register a route for caching.

        Args:
            path: Route path
            expires: Cache lifetime in seconds
            response_model: Pydantic model for response body schema (JSONResponse only)
            summary: Operation summary for OpenAPI
            description: Operation description for OpenAPI
            tags: Operation tags for OpenAPI
            deprecated: Mark operation as deprecated

        Example:
            app.cache("/api/data", expires=3600)

            @app.get("/api/data")
            async def get_data(request):
                return JSONResponse({"data": "cached"})
        """
        # Store for later registration
        if not hasattr(self, "_cache_routes"):
            self._cache_routes = []
        self._cache_routes.append((path, expires))
        # Enable CacheMiddleware
        if not self._cache_middleware_needed:
            self._cache_middleware_needed = True
            self._middlewares.append(
                Middleware(CacheMiddleware, cache_timeout=self._cache_timeout)
            )

        def decorator(func):
            # Add route as usual
            for m in ["GET"]:
                self._router.add_route(path, m.upper(), func)
                self._registered_routes.append(
                    {
                        "path": path,
                        "method": m.upper(),
                        "handler": func,
                        "response_model": response_model,
                        "summary": summary,
                        "description": description,
                        "tags": tags,
                        "deprecated": deprecated,
                    }
                )
                self._add_route_to_openapi(
                    path,
                    m.upper(),
                    func,
                    response_model=response_model,
                    summary=summary,
                    description=description,
                    tags=tags,
                    deprecated=deprecated,
                )
            return func

        return decorator

    def mount(
        self, path: str, app: Any = None, directory: Union[str, os.PathLike] = None
    ):
        """
        Mount an external ASGI application or static files directory.

        Args:
            path: Path prefix (e.g., "/static" or "/api")
            app: ASGI application to mount
            directory: Path to static files directory
        """
        if app is not None:
            self._mounted_apps[path] = app
        elif directory is not None:
            self._static_dirs[path] = str(directory)

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = 1,
        access_log: bool = True,
    ):
        """
        Run uvicorn server.

        Args:
            host: Host to listen on
            port: Port to listen on
            workers: Number of worker processes
            access_log: Whether to enable request logging
        """
        import sys
        import uvicorn

        # Build middlewares with registered cache routes before starting
        if not self._app_built:
            self._app = self._build_middlewares(self._core)
            self._app_built = True

        try:
            # Generate import string for workers support
            if workers > 1:
                main_module = sys.modules.get("__main__")
                if (
                    main_module
                    and hasattr(main_module, "__file__")
                    and main_module.__file__
                ):
                    file_path = os.path.realpath(os.path.abspath(main_module.__file__))
                    module_name = os.path.splitext(os.path.basename(file_path))[0]

                    if module_name == "__main__":
                        package_name = os.path.basename(os.path.dirname(file_path))
                        app_str = f"{package_name}:app"
                    else:
                        app_str = f"{module_name}:app"
                else:
                    app_str = "app:app"
            else:
                app_str = self

            uvicorn.run(
                app_str,
                host=host,
                port=port,
                workers=workers,
                access_log=access_log,
                http="httptools",
                lifespan="on",
            )
        except Exception:
            raise

    def _build_core(self):
        # Apply GC optimizations when creating the app (for each worker)
        _run_gc_optimize()

        async def app(scope, receive, send):
            if scope["type"] == "lifespan":
                # Handle lifespan protocol
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        # Run GC optimization
                        _run_gc_optimize()
                        # Initialize shared resources
                        await self._init_shared_resources()
                        await send({"type": "lifespan.startup.complete"})
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            elif scope["type"] == "http":
                return await self._handle_http(scope, receive, send)
            elif scope["type"] == "websocket":
                return await self._handle_ws(scope, receive, send)

        return app

    def _build_middlewares(self, app: ASGIApp) -> ASGIApp:
        # Register cache routes before building middlewares
        cache_middleware_instance = None

        for mw in reversed(self._middlewares):
            built = mw.build(app)
            # Save cache middleware instance for later registration
            if mw.middleware_cls == CacheMiddleware:
                cache_middleware_instance = built
            app = built

        # Register cache routes after creating middleware
        if hasattr(self, "_cache_routes") and cache_middleware_instance is not None:
            for path, expires in self._cache_routes:
                cache_middleware_instance.register_handler(path, expires)

        return app

    def _register_openapi_routes(self):
        """
        Register OpenAPI specification and SwaggerUI routes directly to router.
        """
        # Prevent double registration
        if self._openapi_routes_registered:
            return
        self._openapi_routes_registered = True

        from altapi.http.responses import JSONResponse, HTMLResponse
        from altapi.swagger import get_swagger_ui_html

        # HTTP routes are added to the generator incrementally in route() via
        # _add_route_to_openapi — __init__ runs before @app.get decorators, so we
        # must not rely on building the spec from _registered_routes only here.

        # Register OpenAPI JSON endpoint directly to router (not via decorator to avoid _registered_routes pollution)
        if self._openapi_url:
            generator = self._openapi_generator
            openapi_url = self._openapi_url

            async def openapi_json_handler(request):
                spec = generator.generate()
                return JSONResponse(spec)

            self._router.add_route(openapi_url, "GET", openapi_json_handler)

        # Register SwaggerUI endpoint directly to router
        if self._docs_url:
            openapi_url = self._openapi_url
            generator = self._openapi_generator

            async def swagger_ui_handler(request):
                html = get_swagger_ui_html(
                    openapi_url=openapi_url,
                    title=f"{generator.title} - Swagger UI",
                )
                return HTMLResponse(html)

            self._router.add_route(self._docs_url, "GET", swagger_ui_handler)

    async def _handle_http(self, scope, receive, send):
        path = scope["path"]
        method = scope["method"]

        # Check mounted applications
        for mount_path, mounted_app in self._mounted_apps.items():
            if path.startswith(mount_path):
                new_scope = dict(scope)  # shallow copy to avoid mutation
                new_scope["path"] = path[len(mount_path) :] or "/"
                return await mounted_app(new_scope, receive, send)

        # Check static directories
        for mount_path, directory in self._static_dirs.items():
            if path.startswith(mount_path):
                relative_path = path[len(mount_path) :].lstrip("/")
                file_path = os.path.join(directory, relative_path)

                # Protect against directory traversal (use realpath for symlink resolution)
                abs_directory = os.path.realpath(directory)
                abs_file = os.path.realpath(file_path)

                if abs_file.startswith(abs_directory) and os.path.isfile(abs_file):
                    response = FileResponse(file_path)
                    return await response(scope, receive, send)
                else:
                    # TODO: add logging
                    response = HTMLResponse(DEFAULT_404_BODY, 404)
                    return await response(scope, receive, send)

        handler, params = self._router.find_handler(path, method)

        if not handler:
            return await HTMLResponse(DEFAULT_404_BODY, 404)(scope, receive, send)

        # Use pre-computed handler metadata (performance optimization)
        handler_meta = getattr(handler, "_handler_meta", None)
        if handler_meta is None:
            # Fallback for handlers registered without decorator
            sig = inspect.signature(handler)
            is_async = inspect.iscoroutinefunction(handler)
            depends_map = get_dependencies_from_signature(sig)
            handler_params = list(sig.parameters.keys())
            has_request = "request" in handler_params
        else:
            sig = handler_meta["sig"]
            is_async = handler_meta["is_async"]
            depends_map = handler_meta["depends_map"]
            handler_params = handler_meta["handler_params"]
            has_request = handler_meta["has_request"]

        request = Request(scope, receive, params)

        # Fast path: no dependencies (most common case) - no try/finally overhead
        if not depends_map:
            if is_async:
                response = await handler(request)
            else:
                response = await asyncio.get_running_loop().run_in_executor(
                    self._sync_executor,
                    handler,
                    request,
                )
            return await response(scope, receive, send)

        # Slow path: with dependencies
        injector = DependencyInjector(request=request)

        try:
            # Solve all dependencies
            solved_values = {}
            for param_name, depends in depends_map.items():
                solved_values[param_name] = await injector.solve(depends.dependency)

            # Call handler with solved dependencies
            call_kwargs = {**solved_values}

            # Add path_params to kwargs only if not already provided by DI
            for param_name in handler_params:
                if param_name == "request":
                    continue
                # Skip if already in solved_values (from DI)
                if param_name not in call_kwargs and param_name in params:
                    call_kwargs[param_name] = params[param_name]

            # Check if handler expects 'request' as first argument
            if has_request:
                call_args = (request,)
            else:
                call_args = ()

            if is_async:
                response = await handler(*call_args, **call_kwargs)
            else:
                response = await asyncio.get_running_loop().run_in_executor(
                    self._sync_executor,
                    handler,
                    *call_args,
                    **call_kwargs,
                )

            return await response(scope, receive, send)
        except Exception:
            await HTMLResponse(DEFAULT_500_BODY, 500)(scope, receive, send)
            raise
        finally:
            # Cleanup generator-based dependencies
            await injector.cleanup()

    def _collect_openapi_metadata(self, handler):
        """Walk handler wrappers (e.g. @cache) and take innermost OpenAPI metadata."""
        meta = None
        h = handler
        while h is not None:
            if hasattr(h, "_openapi_metadata"):
                meta = h._openapi_metadata
            h = getattr(h, "__wrapped__", None)
        if not meta:
            return None, None, None, None, None, False
        return (
            meta.get("summary"),
            meta.get("description"),
            meta.get("tags"),
            meta.get("request_body"),
            meta.get("responses"),
            meta.get("deprecated", False),
        )

    def _add_route_to_openapi(
        self,
        path: str,
        method: str,
        handler,
        request_model: Optional[Type] = None,
        response_model: Optional[Type] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: bool = False,
    ) -> None:
        """Register a single HTTP route with the OpenAPI generator (call from route())."""
        # Collect metadata from decorators
        dec_summary, dec_description, dec_tags, dec_request_body, dec_responses, dec_deprecated = (
            self._collect_openapi_metadata(handler)
            if handler is not None
            else (None, None, None, None, None, False)
        )

        # Use Pydantic models if provided
        openapi_request_body = None
        openapi_responses = None

        if request_model is not None and is_pydantic_model(request_model):
            openapi_request_body = model_to_request_body_schema(
                request_model,
                description=f"{handler.__name__} request body",
            )

        if response_model is not None and is_pydantic_model(response_model):
            openapi_responses = model_to_response_schema(
                response_model,
                status_code="200",
                description="Successful Response",
            )

        # Merge: explicit params > decorator metadata > defaults
        final_request_body = openapi_request_body or dec_request_body
        final_responses = openapi_responses or dec_responses

        self._openapi_generator.add_route(
            path=path,
            method=method,
            handler=handler,
            summary=summary or dec_summary,
            description=description or dec_description,
            tags=tags or dec_tags,
            request_body=final_request_body,
            responses=final_responses,
            deprecated=deprecated or dec_deprecated,
            request_model=request_model,
            response_model=response_model,
        )

    async def _handle_ws(self, scope, receive, send):
        path = scope["path"]

        handler, params = self._router.find_websocket_handler(path)
        websocket = WebSocket(scope, receive, send, params)

        if not handler:
            await websocket.close(1000)
            return

        try:
            if inspect.iscoroutinefunction(handler):
                await handler(websocket)
            else:
                await asyncio.get_running_loop().run_in_executor(
                    self._sync_executor,
                    handler,
                    websocket,
                )

        except Exception as e:
            try:
                await websocket.close(1011, str(e))
            except Exception:
                pass

    async def __call__(self, scope, receive, send):
        return await self._app(scope, receive, send)
