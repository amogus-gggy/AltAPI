import asyncio
import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any, Union

from .http.responses import HTMLResponse

from .router import Router
from .websocket.ws import WebSocket
from .http.request import Request
from .http.responses import FileResponse
from .middleware.middleware import Middleware, ASGIApp
from .templating.default_templates import DEFAULT_404_BODY, DEFAULT_500_BODY
from .templating.templates import Jinja2Templates, set_default_templates_directory
from .caching.cache import CacheMiddleware, CacheManager, cache as cache_decorator, CacheBackend, InMemoryCache
from .shared import start_manager, stop_manager, ManagerConnection, SharedCacheBackend, SharedRateLimitStorage

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
        shared_host: str = "127.0.0.1",
        shared_port: int = 58000,
    ):
        """
        Initialize AltAPI application.

        Args:
            middleware: List of middleware for the application
            templates_directory: Directory with Jinja2 templates
            static_directory: Directory with static files (optional)
            cache_timeout: Default cache lifetime in seconds
            shared_host: Host for shared manager (default: 127.0.0.1)
            shared_port: Port for shared manager (default: 58000)
        """
        self._router = Router()
        self._middlewares = middleware or []
        self._mounted_apps: Dict[str, Any] = {}
        self._static_dirs: Dict[str, str] = {}
        self._shared_host = shared_host
        self._shared_port = shared_port
        self._manager_process = None
        self._manager_connection: Optional[ManagerConnection] = None
        self._app_built = False

        self._core = self._build_core()
        self._app = self._core  # Will be built with middlewares in run()
        self._sync_executor = _sync_executor

        # Initialize Jinja2 templates with optimized settings
        self._templates_directory = str(templates_directory)
        self._templates = Jinja2Templates(
            self._templates_directory,
            auto_reload=False,  # Disable auto-reload for production
            cache_size=4096,    # Cache compiled templates
        )

        # Set global templates directory for render_template
        set_default_templates_directory(self._templates_directory)

        # Initialize static directory (if specified)
        if static_directory is not None:
            self._static_directory = str(static_directory)
            self.mount("/static", directory=self._static_directory)
        else:
            self._static_directory = None

        # Initialize shared caching (always enabled) - lazy initialization in lifespan
        self._cache_backend = None
        self._cache_timeout = cache_timeout
        self._cache_middleware: Optional[CacheMiddleware] = None
        # Add CacheMiddleware to list (will be initialized in lifespan)
        self._middlewares.append(Middleware(CacheMiddleware, cache_timeout=cache_timeout))

    async def _init_shared_resources(self):
        """Initialize shared resources (called in lifespan)."""
        # Initialize cache backend
        self._cache_backend = SharedCacheBackend(self._get_manager_connection())

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
    def cache_backend(self) -> Optional[CacheBackend]:
        """Return cache backend (if configured)."""
        return self._cache_backend

    @property
    def manager_connection(self) -> Optional[ManagerConnection]:
        """Return shared manager connection (if in shared mode)."""
        return self._manager_connection

    def get_rate_limit_storage(self):
        """Get rate limit storage for use with @rate_limit decorator."""
        return SharedRateLimitStorage(self._get_manager_connection())

    def route(self, path, methods=None):
        """
        Decorator for registering HTTP routes.

        Args:
            path: Route path
            methods: List of HTTP methods (default ["GET"])

        Returns:
            Decorator for registering handler function
        """
        methods = methods or ["GET"]

        def decorator(func):
            for m in methods:
                self._router.add_route(path, m.upper(), func)

            # Register for caching if @cache decorator was applied
            # Check the original function (unwrap if needed)
            original_func = func
            while hasattr(original_func, '__wrapped__'):
                original_func = original_func.__wrapped__
            
            if hasattr(original_func, "_cache_expires"):
                if not hasattr(self, "_cache_routes"):
                    self._cache_routes = []
                self._cache_routes.append((path, original_func._cache_expires))

            return func

        return decorator

    def get(self, path):
        """
        Decorator for registering GET routes.

        Args:
            path: Route path
        """
        return self.route(path, ["GET"])

    def post(self, path):
        """
        Decorator for registering POST routes.

        Args:
            path: Route path
        """
        return self.route(path, ["POST"])

    def put(self, path):
        """
        Decorator for registering PUT routes.

        Args:
            path: Route path
        """
        return self.route(path, ["PUT"])

    def delete(self, path):
        """
        Decorator for registering DELETE routes.

        Args:
            path: Route path
        """
        return self.route(path, ["DELETE"])

    def patch(self, path):
        """
        Decorator for registering PATCH routes.

        Args:
            path: Route path
        """
        return self.route(path, ["PATCH"])

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

    def cache(self, path: str, expires: int = 300):
        """
        Register a route for caching.

        Args:
            path: Route path
            expires: Cache lifetime in seconds

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

        def decorator(func):
            # Add route as usual
            for m in ["GET"]:
                self._router.add_route(path, m.upper(), func)
            return func

        return decorator

    def mount(self, path: str, app: Any = None, directory: Union[str, os.PathLike] = None):
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

    def _get_manager_connection(self) -> ManagerConnection:
        """Get or create manager connection."""
        if self._manager_connection is None:
            self._manager_connection = ManagerConnection(
                host=self._shared_host,
                port=self._shared_port,
            )
        return self._manager_connection

    def start_manager_process(self) -> None:
        """Start the shared manager process (for single-process mode with workers)."""
        if self._manager_process is None:
            self._manager_process = start_manager(
                host=self._shared_host,
                port=self._shared_port,
            )

    def stop_manager_process(self) -> None:
        """Stop the shared manager process."""
        if self._manager_process is not None:
            stop_manager(self._manager_process)
            self._manager_process = None

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = 1,
        access_log: bool = True,
    ):
        """
        Run uvicorn server.

        Automatically starts the shared manager process for cache and rate limiting.

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

        # Start shared manager process (always enabled)
        self.start_manager_process()

        try:
            # Generate import string for workers support
            if workers > 1:
                main_module = sys.modules.get("__main__")
                if main_module and hasattr(main_module, "__file__") and main_module.__file__:
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
        finally:
            self.stop_manager_process()

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

    async def _handle_http(self, scope, receive, send):
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Check mounted applications
        for mount_path, mounted_app in self._mounted_apps.items():
            if path.startswith(mount_path):
                new_scope = dict(scope)  # shallow copy to avoid mutation
                new_scope["path"] = path[len(mount_path):] or "/"
                return await mounted_app(new_scope, receive, send)

        # Check static directories
        for mount_path, directory in self._static_dirs.items():
            if path.startswith(mount_path):
                relative_path = path[len(mount_path):].lstrip("/")
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

        request = Request(scope, receive, params)

        try:
            if inspect.iscoroutinefunction(handler):
                response = await handler(request)
            else:
                response = await asyncio.get_running_loop().run_in_executor(
                    self._sync_executor,
                    handler,
                    request,
                )

            await response(scope, receive, send)
        except Exception as e:
            await HTMLResponse(DEFAULT_500_BODY, 500)(scope, receive, send)

    async def _handle_ws(self, scope, receive, send):
        path = scope.get("path", "/")

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
