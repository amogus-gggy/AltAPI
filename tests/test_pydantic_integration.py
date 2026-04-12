"""
Tests for Pydantic model integration with OpenAPI.

Tests Pydantic model support in route decorators and OpenAPI schema generation.
"""

import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic import BaseModel, Field
from typing import Optional, List

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.openapi_spec import OpenAPIGenerator
from altapi.pydantic_schemas import (
    is_pydantic_model,
    model_to_openapi_ref,
    model_to_request_body_schema,
    model_to_response_schema,
    extract_pydantic_schemas,
)


# Test Pydantic models
class UserCreate(BaseModel):
    """User creation request model."""
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="User email")
    age: Optional[int] = Field(None, ge=0, le=150)


class UserResponse(BaseModel):
    """User response model."""
    id: int
    name: str
    email: str
    age: Optional[int]


class UserUpdate(BaseModel):
    """User update request model."""
    name: Optional[str] = None
    email: Optional[str] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


class ItemCreate(BaseModel):
    """Item creation request model."""
    title: str
    price: float
    tags: List[str] = []


class ItemResponse(BaseModel):
    """Item response model."""
    id: int
    title: str
    price: float
    tags: List[str]


def test_is_pydantic_model():
    """Test is_pydantic_model function."""
    assert is_pydantic_model(UserCreate) is True
    assert is_pydantic_model(UserResponse) is True
    assert is_pydantic_model(dict) is False
    assert is_pydantic_model(str) is False
    assert is_pydantic_model(None) is False
    print("✓ is_pydantic_model tests passed")


def test_model_to_openapi_ref():
    """Test model_to_openapi_ref function."""
    ref = model_to_openapi_ref(UserCreate)
    assert ref == {"$ref": "#/components/schemas/UserCreate"}
    
    ref = model_to_openapi_ref(UserResponse, prefix="definitions")
    assert ref == {"$ref": "#/components/definitions/UserResponse"}
    print("✓ model_to_openapi_ref tests passed")


def test_model_to_request_body_schema():
    """Test model_to_request_body_schema function."""
    schema = model_to_request_body_schema(UserCreate, description="Create user")
    
    assert "description" in schema
    assert schema["description"] == "Create user"
    assert "content" in schema
    assert "application/json" in schema["content"]
    assert schema["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserCreate"
    }
    assert schema["required"] is True
    print("✓ model_to_request_body_schema tests passed")


def test_model_to_response_schema():
    """Test model_to_response_schema function."""
    schema = model_to_response_schema(UserResponse, status_code="200", description="User found")
    
    assert "200" in schema
    assert schema["200"]["description"] == "User found"
    assert schema["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserResponse"
    }
    print("✓ model_to_response_schema tests passed")


def test_extract_pydantic_schemas():
    """Test extract_pydantic_schemas function."""
    schemas = extract_pydantic_schemas([UserCreate, UserResponse])
    
    assert "UserCreate" in schemas
    assert "UserResponse" in schemas
    
    # Check UserCreate schema structure
    user_create_schema = schemas["UserCreate"]
    assert "properties" in user_create_schema
    assert "name" in user_create_schema["properties"]
    assert "email" in user_create_schema["properties"]
    
    print("✓ extract_pydantic_schemas tests passed")


def test_app_route_with_pydantic_models():
    """Test app.route() with Pydantic models."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        description="Test API description",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,  # Disable docs to avoid template issues
    )
    
    @app.post(
        "/api/users",
        request_model=UserCreate,
        response_model=UserResponse,
        summary="Create user",
        description="Creates a new user",
        tags=["users"],
    )
    async def create_user(request):
        data = await request.json()
        return JSONResponse({"id": 1, **data})
    
    # Generate OpenAPI spec
    spec = app._openapi_generator.generate()
    
    # Check OpenAPI spec structure
    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["title"] == "Test API"
    assert "/api/users" in spec["paths"]
    
    # Check POST operation
    post_op = spec["paths"]["/api/users"]["post"]
    assert post_op["summary"] == "Create user"
    assert post_op["description"] == "Creates a new user"
    assert post_op["tags"] == ["users"]
    
    # Check request body
    assert "requestBody" in post_op
    assert post_op["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserCreate"
    }
    
    # Check responses
    assert "200" in post_op["responses"]
    assert post_op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserResponse"
    }
    
    # Check components/schemas
    assert "components" in spec
    assert "schemas" in spec["components"]
    assert "UserCreate" in spec["components"]["schemas"]
    assert "UserResponse" in spec["components"]["schemas"]
    
    print("✓ app.route() with Pydantic models tests passed")


def test_app_get_with_response_model():
    """Test app.get() with response_model only."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,
    )
    
    @app.get(
        "/api/users/{id:int}",
        response_model=UserResponse,
        summary="Get user",
        tags=["users"],
    )
    async def get_user(request):
        user_id = request.path_params["id"]
        return JSONResponse({
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
            "age": 25,
        })
    
    spec = app._openapi_generator.generate()
    
    # Check GET operation
    get_op = spec["paths"]["/api/users/{id}"]["get"]
    assert get_op["summary"] == "Get user"
    assert get_op["tags"] == ["users"]
    
    # Should have path parameters
    assert "parameters" in get_op
    assert get_op["parameters"][0]["name"] == "id"
    assert get_op["parameters"][0]["in"] == "path"
    
    # Check response
    assert "200" in get_op["responses"]
    assert get_op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserResponse"
    }
    
    # No request body for GET
    assert "requestBody" not in get_op
    
    print("✓ app.get() with response_model tests passed")


def test_app_put_with_both_models():
    """Test app.put() with request_model and response_model."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,
    )
    
    @app.put(
        "/api/users/{id:int}",
        request_model=UserUpdate,
        response_model=UserResponse,
        summary="Update user",
        tags=["users"],
    )
    async def update_user(request):
        user_id = request.path_params["id"]
        data = await request.json()
        return JSONResponse({"id": user_id, **data})
    
    spec = app._openapi_generator.generate()
    
    # Check PUT operation
    put_op = spec["paths"]["/api/users/{id}"]["put"]
    assert put_op["summary"] == "Update user"
    
    # Check request body
    assert "requestBody" in put_op
    assert put_op["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserUpdate"
    }
    
    # Check response
    assert "200" in put_op["responses"]
    assert put_op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/UserResponse"
    }
    
    print("✓ app.put() with both models tests passed")


def test_app_delete_with_response_model():
    """Test app.delete() with response_model."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,
    )
    
    @app.delete(
        "/api/users/{id:int}",
        response_model=MessageResponse,
        summary="Delete user",
        tags=["users"],
    )
    async def delete_user(request):
        user_id = request.path_params["id"]
        return JSONResponse({"message": f"User {user_id} deleted"})
    
    spec = app._openapi_generator.generate()
    
    # Check DELETE operation
    delete_op = spec["paths"]["/api/users/{id}"]["delete"]
    assert delete_op["summary"] == "Delete user"
    
    # Check response
    assert "200" in delete_op["responses"]
    assert delete_op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MessageResponse"
    }
    
    print("✓ app.delete() with response_model tests passed")


def test_multiple_routes_schemas():
    """Test that multiple routes with different models generate all schemas."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,
    )
    
    @app.post("/api/users", request_model=UserCreate, response_model=UserResponse)
    async def create_user(request):
        return JSONResponse({"id": 1})
    
    @app.post("/api/items", request_model=ItemCreate, response_model=ItemResponse)
    async def create_item(request):
        return JSONResponse({"id": 1})
    
    spec = app._openapi_generator.generate()
    
    # Check all schemas are present
    schemas = spec["components"]["schemas"]
    assert "UserCreate" in schemas
    assert "UserResponse" in schemas
    assert "ItemCreate" in schemas
    assert "ItemResponse" in schemas
    
    # Check both paths exist
    assert "/api/users" in spec["paths"]
    assert "/api/items" in spec["paths"]
    
    print("✓ Multiple routes schemas tests passed")


def test_openapi_spec_json_output():
    """Test OpenAPIGenerator.get_json() method."""
    generator = OpenAPIGenerator(
        title="Test API",
        version="1.0.0",
        description="Test description",
    )
    
    # Add a route with Pydantic models
    def dummy_handler(request):
        return JSONResponse({})
    
    generator.add_route(
        path="/api/test",
        method="post",
        handler=dummy_handler,
        request_model=UserCreate,
        response_model=UserResponse,
    )
    
    # Get JSON output
    json_str = generator.get_json()
    spec = json.loads(json_str)
    
    # Verify structure
    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["title"] == "Test API"
    assert "/api/test" in spec["paths"]
    assert "components" in spec
    assert "schemas" in spec["components"]
    assert "UserCreate" in spec["components"]["schemas"]
    assert "UserResponse" in spec["components"]["schemas"]
    
    print("✓ OpenAPI JSON output tests passed")


def test_route_without_pydantic_models():
    """Test that routes without Pydantic models still work."""
    app = AltAPI(
        title="Test API",
        version="1.0.0",
        enable_openapi=True,
        openapi_url="/openapi.json",
        docs_url=None,
    )
    
    @app.get("/api/health")
    async def health(request):
        return JSONResponse({"status": "ok"})
    
    spec = app._openapi_generator.generate()
    
    # Should still have the route
    assert "/api/health" in spec["paths"]
    
    # But no components/schemas
    assert "components" not in spec or "schemas" not in spec.get("components", {})
    
    print("✓ Route without Pydantic models tests passed")


def run_all_tests():
    """Run all tests."""
    print("Running Pydantic integration tests...\n")
    
    test_is_pydantic_model()
    test_model_to_openapi_ref()
    test_model_to_request_body_schema()
    test_model_to_response_schema()
    test_extract_pydantic_schemas()
    test_app_route_with_pydantic_models()
    test_app_get_with_response_model()
    test_app_put_with_both_models()
    test_app_delete_with_response_model()
    test_multiple_routes_schemas()
    test_openapi_spec_json_output()
    test_route_without_pydantic_models()
    
    print("\n✅ All Pydantic integration tests passed!")


if __name__ == "__main__":
    run_all_tests()
