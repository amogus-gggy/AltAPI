"""Tests for altapi.openapi_spec."""

from altapi.depends import Depends
from altapi.openapi_spec import (
    OpenAPIGenerator,
    _convert_path_to_openapi,
    _extract_handler_info,
)


def test_convert_path_to_openapi():
    path, params = _convert_path_to_openapi("/items/{id:int}")
    assert path == "/items/{id}"
    assert params[0]["name"] == "id"
    assert params[0]["schema"]["type"] == "integer"


def test_extract_handler_info_docstring():
    def sample():
        """First line summary.

        Longer description.
        """
        pass

    info = _extract_handler_info(sample)
    assert info["summary"] == "First line summary."
    assert "Longer description" in info["description"]


def test_openapi_generator_generate_and_cache():
    g = OpenAPIGenerator(title="T", version="1", description="D")

    def handler(request):
        pass

    g.add_route("/x", "GET", handler)
    spec1 = g.generate()
    spec2 = g.generate()
    assert spec1 is spec2
    assert spec1["openapi"] == "3.0.3"
    assert "/x" in spec1["paths"]


def test_openapi_generator_post_default_body():
    g = OpenAPIGenerator()

    async def create(request):
        pass

    g.add_route("/create", "POST", create)
    spec = g.generate()
    assert "requestBody" in spec["paths"]["/create"]["post"]


def test_openapi_generator_query_params_skips_depends():
    g = OpenAPIGenerator()

    def dep():
        return 1

    async def q(request, page: int = 1, db=Depends(dep)):
        pass

    params = g._extract_query_params(q)
    names = [p["name"] for p in params]
    assert "page" in names
    assert "db" not in names


def test_map_python_type_string_annotation():
    g = OpenAPIGenerator()
    assert g._map_python_type("int") == "integer"
    assert g._map_python_type("str") == "string"


def test_get_json():
    g = OpenAPIGenerator()
    g.add_route("/a", "GET", lambda r: None)
    s = g.get_json()
    assert '"openapi"' in s
