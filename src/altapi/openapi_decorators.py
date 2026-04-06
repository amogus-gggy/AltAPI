"""
OpenAPI decorators for AltAPI.

Decorators for adding OpenAPI metadata to route handlers.
"""
from typing import Any, Dict, List, Optional


def _merge_openapi_metadata(func, metadata: Dict[str, Any]) -> Any:
    """
    Merge OpenAPI metadata into function, preserving existing metadata.

    Returns the same function object (no wrapper created).
    """
    existing = getattr(func, '_openapi_metadata', {})
    merged = {**existing, **metadata}
    # Remove None values
    merged = {k: v for k, v in merged.items() if v is not None}
    func._openapi_metadata = merged
    func._openapi_decorated = True
    return func


def openapi(
    summary: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    responses: Optional[Dict[str, Any]] = None,
    deprecated: bool = False,
):
    """
    Decorator to add OpenAPI metadata to a route handler.

    Args:
        summary: Short summary of the operation
        description: Detailed description of the operation
        tags: List of tags for grouping operations
        request_body: Request body schema (OpenAPI 3.0 format)
        responses: Response schemas (OpenAPI 3.0 format)
        deprecated: Mark operation as deprecated

    Returns:
        Decorator function

    Example:
        @app.get("/api/users/{id:int}")
        @openapi(
            summary="Get user by ID",
            description="Returns a single user object",
            tags=["users"],
            responses={
                "200": {
                    "description": "User found",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "name": {"type": "string"},
                                }
                            }
                        }
                    }
                },
                "404": {"description": "User not found"}
            }
        )
        async def get_user(request):
            user_id = request.path_params["id"]
            return JSONResponse({"id": user_id, "name": f"User {user_id}"})
    """
    def decorator(func):
        metadata = {
            "summary": summary,
            "description": description,
            "tags": tags,
            "request_body": request_body,
            "responses": responses,
            "deprecated": deprecated,
        }
        return _merge_openapi_metadata(func, metadata)

    return decorator


def tag(*tag_names: str):
    """
    Decorator to add tags to a route handler.

    Args:
        *tag_names: Tags for the operation

    Returns:
        Decorator function

    Example:
        @app.get("/api/users")
        @tag("users", "api")
        async def list_users(request):
            return JSONResponse({"users": []})
    """
    def decorator(func):
        return _merge_openapi_metadata(func, {"tags": list(tag_names)})

    return decorator


def deprecated(func):
    """
    Decorator to mark a route handler as deprecated.

    Args:
        func: Route handler function

    Returns:
        Decorated function

    Example:
        @app.get("/api/old-endpoint")
        @deprecated
        async def old_endpoint(request):
            return JSONResponse({"message": "Use /api/new-endpoint instead"})
    """
    return _merge_openapi_metadata(func, {"deprecated": True})


def describe_responses(responses: Dict[str, Any]):
    """
    Decorator to add response schemas to a route handler.

    Args:
        responses: Response schemas in OpenAPI 3.0 format

    Returns:
        Decorator function

    Example:
        @app.get("/api/items/{id:int}")
        @describe_responses({
            "200": {
                "description": "Item found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Item"}
                    }
                }
            },
            "404": {"description": "Item not found"}
        })
        async def get_item(request):
            ...
    """
    def decorator(func):
        return _merge_openapi_metadata(func, {"responses": responses})

    return decorator


def describe_request_body(body_schema: Dict[str, Any], description: str = "Request body"):
    """
    Decorator to add request body schema to a route handler.

    Args:
        body_schema: Request body schema in OpenAPI 3.0 format
        description: Description of the request body

    Returns:
        Decorator function

    Example:
        @app.post("/api/users")
        @describe_request_body({
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["name", "email"],
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                        }
                    }
                }
            }
        })
        async def create_user(request):
            data = await request.json()
            return JSONResponse({"id": 1, **data})
    """
    def decorator(func):
        metadata = {
            "request_body": {
                "description": description,
                "content": body_schema.get("content", {"application/json": {"schema": body_schema}}),
                "required": body_schema.get("required", True),
            }
        }
        return _merge_openapi_metadata(func, metadata)

    return decorator
