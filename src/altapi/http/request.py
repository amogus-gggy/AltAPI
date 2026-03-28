import json
from typing import Callable, Any, Dict, Optional, List, Tuple


class Request:
    __slots__ = ('scope', 'receive', 'method', 'path', 'query_string',
                 'headers', 'path_params', '_body', '_headers_dict')

    def __init__(self, scope: Dict[str, Any], receive: Callable, path_params=None):
        self.scope = scope
        self.receive = receive
        self.method = scope.get("method", "GET")
        self.path = scope.get("path", "/")
        self.query_string = scope.get("query_string", b"").decode()
        self.headers = scope.get("headers", [])  # Храним как список кортежей
        self.path_params = path_params or {}
        self._body: Optional[bytes] = None
        self._headers_dict: Optional[Dict[str, str]] = None

    @property
    def headers_dict(self) -> Dict[str, str]:
        """Ленивое получение заголовков как dict."""
        if self._headers_dict is None:
            self._headers_dict = {
                k.decode(): v.decode()
                for k, v in self.headers
            }
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
        return json.loads(body)

    async def text(self):
        body = await self._get_body()
        return body.decode()
