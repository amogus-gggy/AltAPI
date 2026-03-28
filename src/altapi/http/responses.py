import ujson
import os
import stat
import typing
from typing import Any, Dict, List, Optional, Union, AsyncIterator, Callable

import anyio

# Предварительно закодированные заголовки для часто используемых media types
_PRE_ENCODED_MEDIA_TYPES = {
    "application/json": [(b"content-type", b"application/json")],
    "text/plain; charset=utf-8": [(b"content-type", b"text/plain; charset=utf-8")],
    "text/html; charset=utf-8": [(b"content-type", b"text/html; charset=utf-8")],
}


class _HeadersMixin:
    """Mixin for encoding HTTP headers."""

    def _encode_headers(self, media_type: str, headers: dict) -> List[tuple]:
        # Используем предзакодированные заголовки если возможно
        if not headers and media_type in _PRE_ENCODED_MEDIA_TYPES:
            return _PRE_ENCODED_MEDIA_TYPES[media_type]

        result = [(b"content-type", media_type.encode())]
        for k, v in headers.items():
            result.append((k.encode(), v.encode()))
        return result


class Response(_HeadersMixin):
    def __init__(self, content="", status_code=200, headers=None, media_type="text/plain"):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self._encoded_headers: Optional[List[tuple]] = None
        self._encoded_body: Optional[bytes] = None
        # Предварительно кодируем тело если это bytes или str
        if isinstance(content, bytes):
            self._encoded_body = content
        elif isinstance(content, str):
            # UTF-8 для текста, latin-1 для совместимости
            self._encoded_body = content.encode('utf-8')

    async def __call__(self, scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_encoded_headers(),
        })

        await send({
            "type": "http.response.body",
            "body": self._get_encoded_body(),
            "more_body": False,  # КРИТИЧНО для ASGI
        })

    def _get_encoded_headers(self):
        if self._encoded_headers is None:
            self._encoded_headers = self._encode_headers(self.media_type, self.headers)
        return self._encoded_headers

    def _get_encoded_body(self):
        if self._encoded_body is None:
            self._encoded_body = self.content.encode('utf-8') if isinstance(self.content, str) else self.content
        return self._encoded_body


class JSONResponse(Response):
    def __init__(self, content, status_code=200, headers=None):
        # Сериализуем в JSON и сразу кодируем в bytes (JSON всегда ASCII-safe)
        json_bytes = ujson.dumps(content).encode('latin-1')
        super().__init__(
            json_bytes,
            status_code=status_code,
            headers=headers,
            media_type="application/json",
        )
        # _encoded_body уже установлен в суперклассе


class HTMLResponse(Response):
    def __init__(self, content, status_code=200, headers=None):
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/html; charset=utf-8",
        )


class PlainTextResponse(Response):
    """Ответ с обычным текстом (text/plain)."""

    def __init__(self, content, status_code=200, headers=None):
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/plain; charset=utf-8",
        )


class RedirectResponse(Response):
    """Перенаправление на другой URL."""

    def __init__(self, url, status_code=307, headers=None):
        headers = headers or {}
        headers["location"] = url
        super().__init__(
            "",
            status_code=status_code,
            headers=headers,
            media_type="text/plain",
        )


class StreamingResponse(_HeadersMixin):
    """Потоковый ответ для передачи данных частями."""

    def __init__(
            self,
            content: Union[AsyncIterator[bytes], AsyncIterator[str], Callable],
            status_code: int = 200,
            headers: Optional[Dict[str, str]] = None,
            media_type: str = "text/plain",
    ):
        self.content_iterator = content
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self._encoded_headers: Optional[List[tuple]] = None

    async def __call__(self, scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_encoded_headers(),
        })

        if callable(self.content_iterator):
            iterator = self.content_iterator()
        else:
            iterator = self.content_iterator

        async for chunk in iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode()
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            })

        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })

    def _get_encoded_headers(self):
        if self._encoded_headers is None:
            self._encoded_headers = self._encode_headers(self.media_type, self.headers)
        return self._encoded_headers


class FileResponse(Response):
    """Ответ с содержимым файла (с поддержкой range-запросов)."""
    chunk_size = 64 * 1024

    def __init__(
            self,
            path: Union[str, os.PathLike],
            status_code: int = 200,
            headers: Optional[Dict[str, str]] = None,
            media_type: Optional[str] = None,
            filename: Optional[str] = None,
    ):
        self.path = path
        self.filename = filename or os.path.basename(path)
        self.status_code = status_code
        self.headers = headers or {}
        self._media_type = media_type

        if self._media_type is None:
            self._media_type = self._guess_media_type()

        self._file_size: Optional[int] = None

    def _guess_media_type(self) -> str:
        ext = os.path.splitext(self.path)[1].lower()
        media_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/vnd.microsoft.icon",
            ".txt": "text/plain; charset=utf-8",
            ".pdf": "application/pdf",
            ".xml": "application/xml",
            ".zip": "application/zip",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".eot": "application/vnd.ms-fontobject",
        }
        return media_types.get(ext, "application/octet-stream")

    async def __call__(self, scope, receive, send):
        import email.utils

        # Получаем размер файла и информацию о нём
        try:
            stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
        except FileNotFoundError:
            # Файл не найден - возвращаем 404
            response = PlainTextResponse("Not Found", status_code=404)
            return await response(scope, receive, send)
        except PermissionError:
            # Нет доступа - возвращаем 403
            response = PlainTextResponse("Forbidden", status_code=403)
            return await response(scope, receive, send)

        file_size = stat_result.st_size
        last_modified = stat_result.st_mtime

        # Парсинг Range заголовка
        start = 0
        end = None
        range_header = None

        for key, value in scope.get("headers", []):
            if key.decode().lower() == "range":
                range_header = value.decode()
                break

        if range_header and range_header.startswith("bytes="):
            try:
                range_val = range_header[6:]  # убираем "bytes="
                start_str, end_str = range_val.split("-", 1)
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                # Нормализуем end
                if end >= file_size:
                    end = file_size - 1
                if start > end:
                    # Невалидный диапазон - игнорируем
                    start = 0
                    end = None
                else:
                    self.status_code = 206
            except (ValueError, IndexError):
                # Невалидный Range - игнорируем
                pass

        # Формируем заголовки
        headers = dict(self.headers)
        headers["content-type"] = self._media_type
        headers["content-disposition"] = f'attachment; filename="{self.filename}"'
        headers["accept-ranges"] = "bytes"
        headers["last-modified"] = email.utils.formatdate(last_modified, usegmt=True)

        # Вычисляем длину контента
        if end is not None:
            content_length = end - start + 1
            headers["content-range"] = f"bytes {start}-{end}/{file_size}"
        else:
            content_length = file_size - start

        headers["content-length"] = str(content_length)

        encoded_headers = [(k.encode(), v.encode()) for k, v in headers.items()]

        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": encoded_headers,
        })

        # Читаем и отправляем файл
        try:
            async with await anyio.open_file(self.path, "rb") as f:
                if start > 0:
                    await f.seek(start)

                remaining = content_length
                while remaining > 0:
                    chunk_size = min(self.chunk_size, remaining)
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    await send({
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": True,
                    })
                    remaining -= len(chunk)
        except (FileNotFoundError, PermissionError):
            # Файл был удалён или доступ запрещён во время чтения
            pass

        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
