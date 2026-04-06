import orjson
import os
from typing import Dict, List, Optional, Union, AsyncIterator, Callable

import anyio

# Pre-encoded headers for commonly used media types
_PRE_ENCODED_MEDIA_TYPES = {
    "application/json": [(b"content-type", b"application/json")],
    "text/plain; charset=utf-8": [(b"content-type", b"text/plain; charset=utf-8")],
    "text/html; charset=utf-8": [(b"content-type", b"text/html; charset=utf-8")],
}


class _HeadersMixin:
    """Mixin for encoding HTTP headers."""

    def _encode_headers(self, media_type: str, headers: dict) -> List[tuple]:
        # Use pre-encoded headers if possible
        if not headers and media_type in _PRE_ENCODED_MEDIA_TYPES:
            return _PRE_ENCODED_MEDIA_TYPES[media_type]

        result = [(b"content-type", media_type.encode())]
        for k, v in headers.items():
            result.append((k.encode(), v.encode()))
        return result


class Response(_HeadersMixin):
    __slots__ = ('status_code', 'headers', 'media_type', '_encoded_headers', '_encoded_body', 'content')

    def __init__(self, content="", status_code=200, headers=None, media_type="text/plain"):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self._encoded_headers: Optional[List[tuple]] = None
        self._encoded_body: Optional[bytes] = None
        # Pre-encode body if it's bytes or str
        if isinstance(content, bytes):
            self._encoded_body = content
        elif isinstance(content, str):
            # UTF-8 for text, latin-1 for compatibility
            self._encoded_body = content.encode('utf-8')

    async def __call__(self, scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_encoded_headers(),
        })

        await send({
            "type": "http.response.body",
            "body": self._encoded_body,
            "more_body": False,  # CRITICAL for ASGI
        })

    def _get_encoded_headers(self):
        if self._encoded_headers is None:
            self._encoded_headers = self._encode_headers(self.media_type, self.headers)
        return self._encoded_headers


class JSONResponse(Response):
    def __init__(self, content, status_code=200, headers=None):
        # orjson.dumps returns bytes directly — no encoding needed
        json_bytes = orjson.dumps(content)
        super().__init__(
            json_bytes,
            status_code=status_code,
            headers=headers,
            media_type="application/json",
        )


class HTMLResponse(Response):
    def __init__(self, content, status_code=200, headers=None):
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/html; charset=utf-8",
        )


class PlainTextResponse(Response):
    """Response with plain text (text/plain)."""

    def __init__(self, content, status_code=200, headers=None):
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/plain; charset=utf-8",
        )


class RedirectResponse(Response):
    """Redirect to another URL.
    
    Uses status code 303 (See Other) by default to redirect POST requests to GET.
    """

    def __init__(self, url, status_code=303, headers=None):
        headers = headers or {}
        headers["location"] = url
        super().__init__(
            "",
            status_code=status_code,
            headers=headers,
            media_type="text/plain",
        )


class StreamingResponse(_HeadersMixin):
    """Streaming response for sending data in chunks."""

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
    """Response with file content (with support for range requests)."""
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

        # Get file size and information
        try:
            stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
        except FileNotFoundError:
            # File not found - return 404
            response = PlainTextResponse("Not Found", status_code=404)
            return await response(scope, receive, send)
        except PermissionError:
            # Access denied - return 403
            response = PlainTextResponse("Forbidden", status_code=403)
            return await response(scope, receive, send)

        file_size = stat_result.st_size
        last_modified = stat_result.st_mtime

        # Parse Range header
        start = 0
        end = None
        range_header = None

        for key, value in scope.get("headers", []):
            if key.decode().lower() == "range":
                range_header = value.decode()
                break

        if range_header and range_header.startswith("bytes="):
            try:
                range_val = range_header[6:]  # Remove "bytes="
                start_str, end_str = range_val.split("-", 1)
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                # Normalize end
                if end >= file_size:
                    end = file_size - 1
                if start > end:
                    # Invalid range - ignore
                    start = 0
                    end = None
                else:
                    self.status_code = 206
            except (ValueError, IndexError):
                # Invalid Range - ignore
                pass

        # Build headers
        headers = dict(self.headers)
        headers["content-type"] = self._media_type
        headers["content-disposition"] = f'attachment; filename="{self.filename}"'
        headers["accept-ranges"] = "bytes"
        headers["last-modified"] = email.utils.formatdate(last_modified, usegmt=True)

        # Calculate content length
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

        # Read and send the file
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
            # File was deleted or access denied during read
            pass

        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
