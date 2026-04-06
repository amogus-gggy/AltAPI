import warnings
from typing import Any

# Import all with underscore prefix to hide them from direct access
from .app import AltAPI
from .http import Request as _Request
from .http import (
    Response as _Response,
    JSONResponse as _JSONResponse,
    HTMLResponse as _HTMLResponse,
    PlainTextResponse as _PlainTextResponse,
    StreamingResponse as _StreamingResponse,
    FileResponse as _FileResponse,
    RedirectResponse as _RedirectResponse,
)
from .middleware import (
    BaseMiddleware as _BaseMiddleware,
    Middleware as _Middleware,
    ASGIApp as _ASGIApp,
)
from .websocket import WebSocket as _WebSocket, WebSocketState as _WebSocketState
from .templating import (
    Jinja2Templates as _Jinja2Templates,
    TemplateResponse as _TemplateResponse,
    render_template as _render_template,
    set_default_templates_directory as _set_default_templates_directory,
    get_default_templates_directory as _get_default_templates_directory,
)
from .caching import (
    CacheBackend as _CacheBackend,
    InMemoryCache as _InMemoryCache,
    CacheManager as _CacheManager,
    CacheMiddleware as _CacheMiddleware,
    cache as _cache,
)
from .ratelimit import (
    rate_limit as _rate_limit,
    rate_limit_batch as _rate_limit_batch,
    BaseRateLimitStorage as _BaseRateLimitStorage,
    InMemoryRateLimitStorage as _InMemoryRateLimitStorage,
    SharedMemoryRateLimitStorage as _SharedMemoryRateLimitStorage,
    RateLimitResult as _RateLimitResult,
)
from .depends import Depends as _Depends
from .openapi_spec import OpenAPIGenerator as _OpenAPIGenerator
from .openapi_decorators import (
    openapi as _openapi,
    tag as _tag,
    deprecated as _deprecated,
    describe_responses as _describe_responses,
    describe_request_body as _describe_request_body,
)
from .swagger import (
    SwaggerUI as _SwaggerUI,
    get_swagger_ui_html as _get_swagger_ui_html,
)


# Mapping of attribute names to their correct import paths and actual objects
_IMPORT_MAPPING = {
    "Request": ("altapi.http", _Request),
    "Response": ("altapi.http", _Response),
    "JSONResponse": ("altapi.http", _JSONResponse),
    "HTMLResponse": ("altapi.http", _HTMLResponse),
    "PlainTextResponse": ("altapi.http", _PlainTextResponse),
    "StreamingResponse": ("altapi.http", _StreamingResponse),
    "FileResponse": ("altapi.http", _FileResponse),
    "RedirectResponse": ("altapi.http", _RedirectResponse),
    "BaseMiddleware": ("altapi.middleware", _BaseMiddleware),
    "Middleware": ("altapi.middleware", _Middleware),
    "ASGIApp": ("altapi.middleware", _ASGIApp),
    "WebSocket": ("altapi.websocket", _WebSocket),
    "WebSocketState": ("altapi.websocket", _WebSocketState),
    "Jinja2Templates": ("altapi.templating", _Jinja2Templates),
    "TemplateResponse": ("altapi.templating", _TemplateResponse),
    "render_template": ("altapi.templating", _render_template),
    "set_default_templates_directory": (
        "altapi.templating",
        _set_default_templates_directory,
    ),
    "get_default_templates_directory": (
        "altapi.templating",
        _get_default_templates_directory,
    ),
    "CacheBackend": ("altapi.caching", _CacheBackend),
    "InMemoryCache": ("altapi.caching", _InMemoryCache),
    "CacheManager": ("altapi.caching", _CacheManager),
    "CacheMiddleware": ("altapi.caching", _CacheMiddleware),
    "cache": ("altapi.caching", _cache),
    "rate_limit": ("altapi.ratelimit", _rate_limit),
    "rate_limit_batch": ("altapi.ratelimit", _rate_limit_batch),
    "BaseRateLimitStorage": ("altapi.ratelimit", _BaseRateLimitStorage),
    "InMemoryRateLimitStorage": ("altapi.ratelimit", _InMemoryRateLimitStorage),
    "SharedMemoryRateLimitStorage": ("altapi.ratelimit", _SharedMemoryRateLimitStorage),
    "RateLimitResult": ("altapi.ratelimit", _RateLimitResult),
    "Depends": ("altapi.depends", _Depends),
    "OpenAPIGenerator": ("altapi.openapi_spec", _OpenAPIGenerator),
    "openapi": ("altapi.openapi_decorators", _openapi),
    "tag": ("altapi.openapi_decorators", _tag),
    "deprecated": ("altapi.openapi_decorators", _deprecated),
    "describe_responses": ("altapi.openapi_decorators", _describe_responses),
    "describe_request_body": ("altapi.openapi_decorators", _describe_request_body),
    "SwaggerUI": ("altapi.swagger", _SwaggerUI),
    "get_swagger_ui_html": ("altapi.swagger", _get_swagger_ui_html),
}


def __getattr__(name: str) -> Any:
    if name in _IMPORT_MAPPING:
        module_path, obj = _IMPORT_MAPPING[name]
        warnings.warn(
            f"Importing '{name}' directly from 'altapi' is deprecated. "
            f"Use 'from {module_path} import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return obj

    if name == "__version__":
        return "0.1.0"

    raise AttributeError(f"module 'altapi' has no attribute '{name}'")


__all__ = [
    "AltAPI",
    "Request",
    "Response",
    "JSONResponse",
    "HTMLResponse",
    "PlainTextResponse",
    "StreamingResponse",
    "FileResponse",
    "RedirectResponse",
    "WebSocket",
    "WebSocketState",
    "BaseMiddleware",
    "Middleware",
    "ASGIApp",
    "Jinja2Templates",
    "TemplateResponse",
    "render_template",
    "set_default_templates_directory",
    "get_default_templates_directory",
    "CacheBackend",
    "InMemoryCache",
    "CacheManager",
    "CacheMiddleware",
    "cache",
    "rate_limit",
    "rate_limit_batch",
    "BaseRateLimitStorage",
    "InMemoryRateLimitStorage",
    "SharedMemoryRateLimitStorage",
    "RateLimitResult",
    "Depends",
    "OpenAPIGenerator",
    "openapi",
    "tag",
    "deprecated",
    "describe_responses",
    "describe_request_body",
    "SwaggerUI",
    "get_swagger_ui_html",
]
