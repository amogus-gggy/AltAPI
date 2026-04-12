"""
OpenAPI 3.0 specification generator for AltAPI.

Automatically generates OpenAPI specifications from registered routes.
Supports Pydantic models for request/response schema generation.
"""

import inspect
import re
from typing import Any, Dict, List, Optional

from .depends import Depends
from .pydantic_schemas import is_pydantic_model, extract_pydantic_schemas


# Type mapping for path parameters
PATH_PARAM_TYPES = {
    "int": {"type": "integer", "format": "int64"},
    "str": {"type": "string"},
    "float": {"type": "number", "format": "float"},
    "uuid": {"type": "string", "format": "uuid"},
    "path": {"type": "string", "format": "path"},
}

# Default response schema for common status codes
DEFAULT_RESPONSES = {
    "200": {"description": "Successful Response"},
    "404": {"description": "Not Found"},
    "500": {"description": "Internal Server Error"},
}


def _convert_path_to_openapi(path: str) -> tuple:
    """
    Convert AltAPI path pattern to OpenAPI path template.

    Args:
        path: Route path (e.g., "/api/users/{id:int}")

    Returns:
        Tuple of (openapi_path, parameters)
    """
    parameters = []

    # Pattern to match {param:type} or {param}
    pattern = r"\{(\w+)(?::(\w+))?\}"

    def replace_param(match):
        param_name = match.group(1)
        param_type = match.group(2) or "str"

        # Build parameter schema
        param_schema = PATH_PARAM_TYPES.get(param_type, {"type": "string"})

        parameters.append(
            {
                "name": param_name,
                "in": "path",
                "required": True,
                "schema": param_schema,
            }
        )

        return f"{{{param_name}}}"

    openapi_path = re.sub(pattern, replace_param, path)

    return openapi_path, parameters


def _extract_handler_info(handler) -> Dict[str, Any]:
    """
    Extract documentation and parameter info from handler function.

    Args:
        handler: Route handler function

    Returns:
        Dictionary with handler metadata
    """
    info = {
        "summary": handler.__name__.replace("_", " ").title(),
        "description": "",
        "tags": [],
    }

    # Extract docstring
    docstring = inspect.getdoc(handler)
    if docstring:
        lines = docstring.strip().split("\n")
        info["summary"] = lines[0].strip()
        if len(lines) > 1:
            info["description"] = "\n".join(lines[1:]).strip()

    # Extract tags from handler name or module
    if hasattr(handler, "__module__") and handler.__module__:
        module_parts = handler.__module__.split(".")
        if len(module_parts) > 1:
            info["tags"] = [module_parts[-1].title()]

    # Check for custom metadata from decorators
    if hasattr(handler, "_openapi_metadata"):
        info.update(handler._openapi_metadata)

    return info


class OpenAPIGenerator:
    """
    Generates OpenAPI 3.0 specification from AltAPI routes.
    """

    def __init__(
        self,
        title: str = "AltAPI",
        version: str = "0.1.0",
        description: str = "",
        contact: Optional[Dict[str, str]] = None,
        license_info: Optional[Dict[str, str]] = None,
        servers: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Initialize OpenAPI generator.

        Args:
            title: API title
            version: API version
            description: API description
            contact: Contact information dict
            license_info: License information dict
            servers: List of server dicts with url and description
        """
        self.title = title
        self.version = version
        self.description = description
        self.contact = contact
        self.license_info = license_info
        self.servers = servers or [
            {"url": "http://localhost:8000", "description": "Local development"}
        ]

        # Store routes manually
        self._routes: List[Dict[str, Any]] = []
        self._cached_schema: Optional[Dict[str, Any]] = None

    def add_route(
        self,
        path: str,
        method: str,
        handler,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        request_body: Optional[Dict[str, Any]] = None,
        responses: Optional[Dict[str, Any]] = None,
        deprecated: bool = False,
        request_model: Optional[type] = None,
        response_model: Optional[type] = None,
    ):
        """
        Add a route to the OpenAPI specification.

        Args:
            path: Route path
            method: HTTP method
            handler: Route handler function
            summary: Operation summary
            description: Operation description
            tags: Operation tags
            request_body: Request body schema
            responses: Response schemas
            deprecated: Whether this endpoint is deprecated
            request_model: Pydantic model for request body
            response_model: Pydantic model for response body
        """
        self._routes.append(
            {
                "path": path,
                "method": method.lower(),
                "handler": handler,
                "summary": summary,
                "description": description,
                "tags": tags,
                "request_body": request_body,
                "responses": responses,
                "deprecated": deprecated,
                "request_model": request_model,
                "response_model": response_model,
            }
        )
        # Invalidate cache when new routes are added
        self._cached_schema = None

    def generate(self) -> Dict[str, Any]:
        """
        Generate OpenAPI 3.0 specification.

        Returns:
            OpenAPI specification as dictionary (cached)
        """
        if self._cached_schema is not None:
            return self._cached_schema

        # Collect all Pydantic models from routes
        all_models = []
        for route in self._routes:
            if route.get("request_model") and is_pydantic_model(route["request_model"]):
                all_models.append(route["request_model"])
            if route.get("response_model") and is_pydantic_model(route["response_model"]):
                all_models.append(route["response_model"])

        # Extract schemas
        schemas = extract_pydantic_schemas(all_models) if all_models else {}

        spec: Dict[str, Any] = {
            "openapi": "3.0.3",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "servers": self.servers,
            "paths": {},
        }

        # Add components with schemas if any
        if schemas:
            spec["components"] = {
                "schemas": schemas
            }

        # Add contact info
        if self.contact:
            spec["info"]["contact"] = self.contact

        # Add license info
        if self.license_info:
            spec["info"]["license"] = self.license_info

        # Build paths
        for route in self._routes:
            path = route["path"]
            method = route["method"]
            handler = route["handler"]

            # Convert path pattern
            openapi_path, path_params = _convert_path_to_openapi(path)

            # Initialize path if not exists
            if openapi_path not in spec["paths"]:
                spec["paths"][openapi_path] = {}

            # Extract handler info
            handler_info = _extract_handler_info(handler)

            # Build operation
            operation = {
                "summary": route["summary"] or handler_info["summary"],
                "operationId": f"{method}_{openapi_path.replace('/', '_').replace('{', '').replace('}', '')}",
                "tags": route["tags"] or handler_info["tags"] or ["default"],
                "responses": route["responses"] or DEFAULT_RESPONSES.copy(),
            }

            # Add description
            if route["description"] or handler_info["description"]:
                operation["description"] = (
                    route["description"] or handler_info["description"]
                )

            # Add path parameters
            if path_params:
                operation["parameters"] = path_params

            # Add query parameters from handler signature
            query_params = self._extract_query_params(handler)
            if query_params:
                operation.setdefault("parameters", []).extend(query_params)

            # Add request body for POST/PUT/PATCH
            if method in ("post", "put", "patch"):
                if route["request_body"]:
                    operation["requestBody"] = route["request_body"]
                else:
                    # Default JSON body
                    operation["requestBody"] = {
                        "content": {"application/json": {"schema": {"type": "object"}}}
                    }

            # Add deprecated flag
            if route["deprecated"]:
                operation["deprecated"] = True

            spec["paths"][openapi_path][method] = operation

        self._cached_schema = spec
        return spec

    def _extract_query_params(self, handler) -> List[Dict[str, Any]]:
        """
        Extract query parameters from handler function signature.

        Args:
            handler: Route handler function

        Returns:
            List of query parameter schemas
        """
        params = []

        try:
            sig = inspect.signature(handler)
            for name, param in sig.parameters.items():
                # Skip 'request' parameter
                if name == "request":
                    continue

                # Skip Depends parameters — they are DI, not query params
                if isinstance(param.default, Depends):
                    continue

                # Check if parameter has type annotation
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    param_type = self._map_python_type(param.annotation)

                params.append(
                    {
                        "name": name,
                        "in": "query",
                        "required": param.default == inspect.Parameter.empty,
                        "schema": {"type": param_type},
                    }
                )
        except (ValueError, TypeError):
            # Cannot inspect signature
            pass

        return params

    def _map_python_type(self, annotation) -> str:
        """Map Python type annotation to OpenAPI type."""
        type_map = {
            int: "integer",
            float: "number",
            str: "string",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        # Handle string annotations
        if isinstance(annotation, str):
            annotation = annotation.lower()
            if annotation in ("int", "integer"):
                return "integer"
            elif annotation in ("float", "number"):
                return "number"
            elif annotation in ("str", "string"):
                return "string"
            elif annotation in ("bool", "boolean"):
                return "boolean"
            elif annotation in ("list", "array"):
                return "array"
            elif annotation in ("dict", "object"):
                return "object"
            return "string"

        return type_map.get(annotation, "string")

    def get_json(self) -> str:
        """
        Get OpenAPI specification as JSON string.

        Returns:
            JSON string of OpenAPI specification
        """
        import json

        return json.dumps(self.generate(), indent=2, ensure_ascii=False)
