"""
Модуль для кеширования запросов.
"""
import time
import asyncio
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Type, Union
from functools import wraps

from ..middleware.middleware import BaseMiddleware
from ..http.request import Request


class CacheBackend(ABC):
    """
    Базовый абстрактный класс для бекендов кеширования.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кеша по ключу.

        Args:
            key: Кэш-ключ

        Returns:
            Значение или None, если ключ не найден или истёк
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """
        Установить значение в кеш.

        Args:
            key: Кэш-ключ
            value: Значение для сохранения
            expires: Время жизни в секундах (None = без ограничения)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Удалить значение из кеша.

        Args:
            key: Кэш-ключ
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """
        Очистить весь кеш.
        """
        pass


class InMemoryCache(CacheBackend):
    """
    Простой бекенд кеширования в памяти.
    """

    def __init__(self, max_size: int = 1000):
        """
        Инициализация InMemoryCache.

        Args:
            max_size: Максимальное количество записей в кеше
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кеша."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Проверка времени жизни
        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            # Истёк срок жизни
            await self.delete(key)
            return None

        return entry["value"]

    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Установить значение в кеш."""
        # Удаляем oldest entry если достигнут лимит
        if len(self._cache) >= self._max_size and key not in self._cache:
            # Простая стратегия: удаляем первый попавшийся (можно улучшить до LRU)
            oldest_key = next(iter(self._cache))
            await self.delete(oldest_key)

        expires_at = None
        if expires is not None:
            expires_at = time.time() + expires

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
        }

    async def delete(self, key: str) -> None:
        """Удалить значение из кеша."""
        self._cache.pop(key, None)

    async def clear(self) -> None:
        """Очистить весь кеш."""
        self._cache.clear()

    async def cleanup_expired(self) -> int:
        """
        Очистить истёкшие записи.

        Returns:
            Количество удалённых записей
        """
        now = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if entry.get("expires_at") is not None and now > entry["expires_at"]
        ]
        for key in expired_keys:
            await self.delete(key)
        return len(expired_keys)


class CacheManager:
    """
    Менеджер для управления бекендами кеширования.
    """

    _default_backend: Optional[CacheBackend] = None
    _backends: Dict[str, CacheBackend] = {}

    @classmethod
    def set_default_backend(cls, backend: CacheBackend) -> None:
        """
        Установить бекенд по умолчанию.

        Args:
            backend: Экземпляр бекенда
        """
        cls._default_backend = backend

    @classmethod
    def get_default_backend(cls) -> CacheBackend:
        """
        Получить бекенд по умолчанию.

        Returns:
            Бекенд кеширования
        """
        if cls._default_backend is None:
            # Создаём InMemoryCache по умолчанию
            cls._default_backend = InMemoryCache()
        return cls._default_backend

    @classmethod
    def register_backend(cls, name: str, backend: CacheBackend) -> None:
        """
        Зарегистрировать именованный бекенд.

        Args:
            name: Имя бекенда
            backend: Экземпляр бекенда
        """
        cls._backends[name] = backend

    @classmethod
    def get_backend(cls, name: Optional[str] = None) -> CacheBackend:
        """
        Получить бекенд по имени или по умолчанию.

        Args:
            name: Имя бекенда (None = использовать бекенд по умолчанию)

        Returns:
            Бекенд кеширования
        """
        if name is None:
            return cls.get_default_backend()
        if name not in cls._backends:
            raise ValueError(f"Backend '{name}' not found")
        return cls._backends[name]


def cache(
    expires: int = 300,
    key_prefix: str = "",
    backend: Optional[Union[str, CacheBackend]] = None,
):
    """
    Декоратор для кеширования результатов функции.

    Args:
        expires: Время жизни кеша в секундах
        key_prefix: Префикс для ключа кеша
        backend: Бекенд для кеширования (строка-имя или экземпляр CacheBackend)

    Пример:
        @cache(expires=3600)
        async def get_data(request):
            return JSONResponse({"data": "expensive computation"})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем бекенд
            if isinstance(backend, CacheBackend):
                cache_backend = backend
            else:
                cache_backend = CacheManager.get_backend(backend)

            # Генерируем ключ кеша из аргументов
            request = None
            for arg in args:
                if hasattr(arg, "path"):  # Request-like object
                    request = arg
                    break

            if request is not None:
                cache_key = f"{key_prefix}{func.__name__}:{request.path}"
            else:
                # Для функций без request используем хеш аргументов
                import hashlib

                args_key = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_key.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}{func.__name__}:{args_hash}"

            # Пробуем получить из кеша
            cached = await cache_backend.get(cache_key)
            if cached is not None:
                return cached

            # Вызываем функцию
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result

            # Сохраняем в кеш
            await cache_backend.set(cache_key, result, expires=expires)

            return result

        return wrapper

    return decorator


class CacheMiddleware(BaseMiddleware):
    """
    Middleware для автоматического кеширования HTTP-запросов.

    Пример использования:
        app = Nebula(middleware=[
            Middleware(CacheMiddleware, cache_timeout=300)
        ])

        @app.get("/api/data")
        @cache(expires=3600)
        async def get_data(request):
            return JSONResponse({"data": "expensive"})
    """

    def __init__(self, app, cache_timeout: int = 300, backend: Optional[CacheBackend] = None):
        """
        Инициализация CacheMiddleware.

        Args:
            app: ASGI приложение
            cache_timeout: Время жизни кеша по умолчанию в секундах
            backend: Бекенд для кеширования (по умолчанию InMemoryCache)
        """
        super().__init__(app)
        self.cache_timeout = cache_timeout
        self.backend = backend or CacheManager.get_default_backend()
        self._cached_handlers: Dict[str, int] = {}  # path -> expires

    def register_handler(self, path: str, expires: int) -> None:
        """
        Зарегистрировать хендлер для кеширования.

        Args:
            path: Путь хендлера
            expires: Время жизни кеша в секундах
        """
        self._cached_handlers[path] = expires

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Проверяем, есть ли хендлер в списке кешируемых
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Кешируем только GET запросы
        if method != "GET":
            return await self.app(scope, receive, send)

        # Проверяем точное совпадение пути
        expires = self._cached_handlers.get(path)

        # Если нет точного совпадения, проверяем паттерны
        if expires is None:
            for handler_path, handler_expires in self._cached_handlers.items():
                if self._match_path(path, handler_path):
                    expires = handler_expires
                    break

        if expires is None:
            # Хендлер не зарегистрирован для кеширования
            return await self.app(scope, receive, send)

        # Генерируем ключ кеша
        query_string = scope.get("query_string", b"").decode()
        cache_key = f"http:{path}:{query_string}"

        # Пробуем получить из кеша
        cached_response = await self.backend.get(cache_key)
        if cached_response is not None:
            # Отправляем кешированный ответ
            await send({
                "type": "http.response.start",
                "status": cached_response["status"],
                "headers": cached_response["headers"],
            })
            await send({
                "type": "http.response.body",
                "body": cached_response["body"],
                "more_body": False,
            })
            return

        # Перехватываем ответ
        response_data = {
            "status": None,
            "headers": [],
            "body": b"",
        }

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_data["status"] = message["status"]
                response_data["headers"] = message["headers"]
            elif message["type"] == "http.response.body":
                response_data["body"] = message.get("body", b"")
                # Если это последний блок, сохраняем в кеш
                if not message.get("more_body", False):
                    await self.backend.set(cache_key, response_data, expires=expires)

        await self.app(scope, receive, send_wrapper)

    def _match_path(self, path: str, pattern: str) -> bool:
        """
        Проверить соответствие пути паттерну.

        Поддерживает простые паттерны с параметрами:
        - /api/users/{id:int}
        - /api/items/{name:str}
        """
        if pattern == path:
            return True

        # Разбиваем на части
        path_parts = path.strip("/").split("/")
        pattern_parts = pattern.strip("/").split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for path_part, pattern_part in zip(path_parts, pattern_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                # Это параметр, пропускаем
                continue
            if path_part != pattern_part:
                return False

        return True
