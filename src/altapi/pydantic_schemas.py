"""
Pydantic model integration for OpenAPI schema generation.

Provides utilities to convert Pydantic models to OpenAPI JSON Schema references.
"""

from typing import Any, Dict, Optional, Type


def model_to_openapi_ref(model: Type, prefix: str = "schemas") -> Dict[str, Any]:
    """
    Convert a Pydantic model to an OpenAPI $ref schema reference.

    Args:
        model: Pydantic model class
        prefix: Schema reference prefix (default: "schemas")

    Returns:
        OpenAPI schema with $ref to the model

    Example:
        from pydantic import BaseModel

        class UserResponse(BaseModel):
            id: int
            name: str

        schema_ref = model_to_openapi_ref(UserResponse)
        # Returns: {"$ref": "#/components/schemas/UserResponse"}
    """
    model_name = model.__name__
    return {"$ref": f"#/components/{prefix}/{model_name}"}


def extract_pydantic_schemas(
    models: list, prefix: str = "schemas"
) -> Dict[str, Any]:
    """
    Extract JSON Schema definitions from Pydantic models.

    Args:
        models: List of Pydantic model classes
        prefix: Schema prefix (default: "schemas")

    Returns:
        Dictionary of schema definitions keyed by model name

    Example:
        from pydantic import BaseModel

        class UserCreate(BaseModel):
            name: str
            email: str

        class UserResponse(BaseModel):
            id: int
            name: str
            email: str

        schemas = extract_pydantic_schemas([UserCreate, UserResponse])
        # Returns dict with "UserCreate" and "UserResponse" schemas
    """
    schemas = {}

    for model in models:
        # Get schema from Pydantic model
        if hasattr(model, "model_json_schema"):
            # Pydantic v2
            schema = model.model_json_schema()
        elif hasattr(model, "schema"):
            # Pydantic v1
            schema = model.schema()
        else:
            continue

        model_name = model.__name__
        schemas[model_name] = schema

    return schemas


def get_model_schema(model: Type) -> Optional[Dict[str, Any]]:
    """
    Get JSON Schema from a Pydantic model.

    Args:
        model: Pydantic model class

    Returns:
        JSON Schema dict or None if not a Pydantic model
    """
    # Check if it's a Pydantic model
    if not hasattr(model, "model_fields") and not hasattr(model, "__fields__"):
        return None

    if hasattr(model, "model_json_schema"):
        # Pydantic v2
        return model.model_json_schema()
    elif hasattr(model, "schema"):
        # Pydantic v1
        return model.schema()

    return None


def is_pydantic_model(obj: Any) -> bool:
    """
    Check if an object is a Pydantic model class.

    Args:
        obj: Object to check

    Returns:
        True if object is a Pydantic model class
    """
    # Check for Pydantic v2
    if hasattr(obj, "model_fields"):
        return True
    # Check for Pydantic v1
    if hasattr(obj, "__fields__"):
        return True
    return False


def model_to_request_body_schema(
    model: Type, description: str = "Request body"
) -> Dict[str, Any]:
    """
    Convert a Pydantic model to OpenAPI request body schema.

    Args:
        model: Pydantic model class
        description: Description of the request body

    Returns:
        OpenAPI request body schema dict
    """
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": model_to_openapi_ref(model)
            }
        },
        "required": True,
    }


def model_to_response_schema(
    model: Type,
    status_code: str = "200",
    description: str = "Successful Response",
) -> Dict[str, Any]:
    """
    Convert a Pydantic model to OpenAPI response schema.

    Args:
        model: Pydantic model class
        status_code: HTTP status code
        description: Description of the response

    Returns:
        OpenAPI response schema dict
    """
    return {
        status_code: {
            "description": description,
            "content": {
                "application/json": {
                    "schema": model_to_openapi_ref(model)
                }
            },
        }
    }
