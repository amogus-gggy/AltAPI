import orjson
from urllib.parse import parse_qs
from typing import Callable, Any, Dict, Optional


class RequestState:
    """Per-request state storage for passing data between middleware and handlers."""

    __slots__ = ("_data",)

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"'RequestState' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name == "_data":
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __delattr__(self, name: str):
        try:
            del self._data[name]
        except KeyError:
            raise AttributeError(f"'RequestState' object has no attribute '{name}'")

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def set(self, name: str, value: Any):
        self._data[name] = value

    def clear(self):
        self._data.clear()


class Request:
    __slots__ = (
        "scope",
        "receive",
        "method",
        "path",
        "query_string_bytes",
        "headers",
        "path_params",
        "_body",
        "_headers_dict",
        "_state",
        "_query_string",
    )

    def __init__(self, scope: Dict[str, Any], receive: Callable, path_params=None):
        self.scope = scope
        self.receive = receive
        self.method = scope["method"]
        self.path = scope["path"]
        self.query_string_bytes = scope.get("query_string", b"")
        self.headers = scope.get("headers", [])  # Store as list of tuples
        self.path_params = path_params or {}
        self._body: Optional[bytes] = None
        self._headers_dict: Optional[Dict[str, str]] = None
        self._state: Optional[RequestState] = None  # Lazy initialization
        self._query_string: Optional[str] = None  # Lazy decode

    @property
    def query_string(self) -> str:
        """Lazy decode of query string."""
        if self._query_string is None:
            self._query_string = self.query_string_bytes.decode()
        return self._query_string

    @property
    def state(self) -> RequestState:
        """Lazy initialization of RequestState."""
        if self._state is None:
            self._state = RequestState()
        return self._state

    @property
    def headers_dict(self) -> Dict[str, str]:
        """Lazy conversion of headers to dict."""
        if self._headers_dict is None:
            self._headers_dict = {k.decode(): v.decode() for k, v in self.headers}
        return self._headers_dict

    async def _get_body(self) -> bytes:
        if self._body is not None:
            return self._body

        messages = []
        while True:
            message = await self.receive()
            messages.append(message)
            if not message.get("more_body", False):
                break

        self._body = b"".join(m.get("body", b"") for m in messages)
        return self._body

    async def json(self):
        body = await self._get_body()
        return orjson.loads(body)

    async def text(self):
        body = await self._get_body()
        return body.decode()

    async def form(self) -> Dict[str, str]:
        """Parse form data from request body."""
        body = await self._get_body()
        content_type = self.headers_dict.get("content-type", "")

        if "application/x-www-form-urlencoded" in content_type:
            # Parse URL-encoded form data
            parsed = parse_qs(body.decode())
            # parse_qs returns lists, we want single values
            return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        elif "multipart/form-data" in content_type:
            # Simple multipart parsing (for basic cases)
            # For full multipart support with files, use a library
            return self._parse_multipart(body)
        else:
            return {}

    def _parse_multipart(self, body: bytes) -> Dict[str, str]:
        """Simple multipart form data parser."""
        content_type = self.headers_dict.get("content-type", "")
        boundary = None

        # Extract boundary from content-type
        if "boundary=" in content_type:
            boundary = "--" + content_type.split("boundary=")[1].split(";")[0].strip()

        if not boundary:
            return {}

        result = {}
        parts = body.split(boundary.encode())[1:-1]  # Skip first and last empty

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Find header end
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers = part[:header_end].decode()
            value = part[header_end + 4 :]  # Skip \r\n\r\n

            # Extract field name
            if 'name="' in headers:
                name_start = headers.find('name="') + 6
                name_end = headers.find('"', name_start)
                field_name = headers[name_start:name_end]

                # Remove trailing \r\n from value
                value_str = value.rstrip(b"\r\n").decode()
                result[field_name] = value_str

        return result
