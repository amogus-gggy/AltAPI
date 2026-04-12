from .middleware import BaseMiddleware
from ..http.request import Request

class CORSMiddleware(BaseMiddleware):
    def __init__(
        self,
        app,
        allow_origins=None,
        allow_methods=None,
        allow_headers=None,
        allow_credentials=False,
    ):
        super().__init__(app)

        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        origin = request.headers_dict.get("origin")

        # Handle preflight request
        if scope["method"] == "OPTIONS":
            headers = self._build_headers(origin)

            await send({
                "type": "http.response.start",
                "status": 204,
                "headers": headers,
            })
            await send({
                "type": "http.response.body",
                "body": b"",
            })
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])

                cors_headers = self._build_headers(origin)

                # extend existing headers
                headers.extend(cors_headers)

            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _build_headers(self, origin):
        headers = []

        def add(name, value):
            headers.append((name.encode(), value.encode()))

        if "*" in self.allow_origins:
            add("access-control-allow-origin", "*")
        elif origin and origin in self.allow_origins:
            add("access-control-allow-origin", origin)

        add("access-control-allow-methods", ", ".join(self.allow_methods))
        add("access-control-allow-headers", ", ".join(self.allow_headers))

        if self.allow_credentials:
            add("access-control-allow-credentials", "true")

        return headers