import asyncio
import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from .http.responses import HTMLResponse

from .router import Router
from .websocket.ws import WebSocket
from .http.request import Request
from .http.responses import JSONResponse, FileResponse, PlainTextResponse
from .middleware.middleware import Middleware, ASGIApp
from .templating.default_templates import DEFAULT_404_BODY, DEFAULT_405_BODY, DEFAULT_500_BODY
from .templating.templates import Jinja2Templates, set_default_templates_directory
from .caching.cache import CacheMiddleware, CacheManager, InMemoryCache, cache as cache_decorator, CacheBackend

_sync_executor = ThreadPoolExecutor(max_workers=10)


class Nebula:
    def __init__(
        self,
        middleware: List[Middleware] = None,
        templates_directory: Union[str, os.PathLike] = "templates",
        static_directory: Optional[Union[str, os.PathLike]] = None,
        cache_backend: Optional[CacheBackend] = None,
        cache_timeout: int = 300,
    ):
        self._router = Router()
        self._middlewares = middleware or []
        self._mounted_apps: Dict[str, Any] = {}
        self._static_dirs: Dict[str, str] = {}

        self._core = self._build_core()
        self._app = self._build_middlewares(self._core)
        self._sync_executor = _sync_executor

        # Инициализация шаблонов Jinja2
        self._templates_directory = str(templates_directory)
        self._templates = Jinja2Templates(self._templates_directory)

        # Устанавливаем глобальную директорию шаблонов для render_template
        set_default_templates_directory(self._templates_directory)

        # Инициализация статической директории (если указана)
        if static_directory is not None:
            self._static_directory = str(static_directory)
            self.mount("/static", directory=self._static_directory)
        else:
            self._static_directory = None

        # Инициализация кеширования (если указан бекенд)
        self._cache_backend = cache_backend
        if cache_backend is not None:
            # Устанавливаем как бекенд по умолчанию
            CacheManager.set_default_backend(cache_backend)
            # Добавляем CacheMiddleware автоматически
            self._middlewares.append(Middleware(CacheMiddleware, cache_timeout=cache_timeout))
        self._cache_timeout = cache_timeout

    @property
    def templates(self) -> Jinja2Templates:
        """Возвращает объект Jinja2Templates для рендеринга шаблонов."""
        return self._templates

    @property
    def static_directory(self) -> Optional[str]:
        """Возвращает путь к директории статических файлов (если настроена)."""
        return self._static_directory

    @property
    def cache_backend(self) -> Optional[CacheBackend]:
        """Возвращает бекенд кеширования (если настроен)."""
        return self._cache_backend

    def route(self, path, methods=None):
        methods = methods or ["GET"]

        def decorator(func):
            for m in methods:
                self._router.add_route(path, m.upper(), func)
            return func

        return decorator

    def get(self, path):
        return self.route(path, ["GET"])

    def post(self, path):
        return self.route(path, ["POST"])

    def put(self, path):
        return self.route(path, ["PUT"])

    def delete(self, path):
        return self.route(path, ["DELETE"])

    def websocket(self, path):
        def decorator(func):
            self._router.add_websocket_route(path, func)
            return func

        return decorator

    def cache(self, path: str, expires: int = 300):
        """
        Зарегистрировать маршрут для кеширования.

        Args:
            path: Путь маршрута
            expires: Время жизни кеша в секундах

        Пример:
            app.cache("/api/data", expires=3600)

            @app.get("/api/data")
            async def get_data(request):
                return JSONResponse({"data": "cached"})
        """
        # Находим CacheMiddleware и регистрируем хендлер
        for mw in self._middlewares:
            if mw.middleware_cls == CacheMiddleware:
                # Получаем экземпляр middleware после build
                pass

        # Сохраняем в отдельный список для последующей регистрации
        if not hasattr(self, "_cache_routes"):
            self._cache_routes = []
        self._cache_routes.append((path, expires))

        def decorator(func):
            # Добавляем маршрут как обычно
            for m in ["GET"]:
                self._router.add_route(path, m.upper(), func)

            # Оборачиваем функцию в кеш
            return cache_decorator(expires=expires)(func)

        return decorator

    def mount(self, path: str, app: Any = None, directory: Union[str, os.PathLike] = None):
        """
        Подключить внешнее ASGI-приложение или директорию со статическими файлами.
        
        Args:
            path: Префикс пути (например, "/static" или "/api")
            app: ASGI-приложение для монтирования
            directory: Путь к директории со статическими файлами
        """
        if app is not None:
            self._mounted_apps[path] = app
        elif directory is not None:
            self._static_dirs[path] = str(directory)

    def run(self, host: str = "0.0.0.0", port: int = 8000, gc_optimize=True):
        """
        Запустить сервер uvicorn.

        Args:
            host: Хост для прослушивания
            port: Порт для прослушивания
            gc_optimize: оптимизировать ли garbage collector
        """

        if gc_optimize:
            import gc
            gc.collect(2)
            gc.freeze()
            allocs, gen1, gen2 = gc.get_threshold()
            print(allocs, gen1, gen2)
            allocs = 50000
            gen1 = gen1 * 2
            gen2 = gen2 * 2
            gc.set_threshold(allocs, gen1, gen2)
        import uvicorn
        #TODO: add access log disabling
        uvicorn.run(self, host=host, port=port, http="httptools")

    def _build_core(self):
        async def app(scope, receive, send):
            if scope["type"] == "http":
                return await self._handle_http(scope, receive, send)
            elif scope["type"] == "websocket":
                return await self._handle_ws(scope, receive, send)

        return app

    def _build_middlewares(self, app: ASGIApp) -> ASGIApp:
        for mw in reversed(self._middlewares):
            app = mw.build(app)

        # Регистрируем cache routes после создания middleware
        if hasattr(self, "_cache_routes"):
            for mw in self._middlewares:
                if mw.middleware_cls == CacheMiddleware:
                    # Получаем экземпляр middleware
                    middleware_instance = mw.build(app)
                    for path, expires in self._cache_routes:
                        middleware_instance.register_handler(path, expires)
                    break

        return app

    async def _handle_http(self, scope, receive, send):
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Проверка смонтированных приложений
        for mount_path, mounted_app in self._mounted_apps.items():
            if path.startswith(mount_path):
                new_scope = dict(scope)  # shallow copy to avoid mutation
                new_scope["path"] = path[len(mount_path):] or "/"
                return await mounted_app(new_scope, receive, send)

        # Проверка статических директорий
        for mount_path, directory in self._static_dirs.items():
            if path.startswith(mount_path):
                relative_path = path[len(mount_path):].lstrip("/")
                file_path = os.path.join(directory, relative_path)

                # Защита от выхода за пределы директории (используем realpath для разрешения symlink)
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
            print(f"\033[31mERROR:\033[37m {str(e)}\033[0m")
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
