"""Tests for altapi.swagger."""

from altapi.swagger import SwaggerUI, get_swagger_ui_html


def test_get_swagger_ui_html_contains_url_and_bundle():
    html = get_swagger_ui_html(openapi_url="/openapi.json", title="My API")
    assert "/openapi.json" in html
    assert "swagger-ui-bundle" in html
    assert "My API" in html


def test_get_swagger_ui_html_false_display_duration():
    html = get_swagger_ui_html(openapi_url="/o.json", display_request_duration=False)
    assert "displayRequestDuration: false" in html


def test_swagger_ui_class():
    ui = SwaggerUI(openapi_url="/api/openapi.json", swagger_ui_url="/ui", title="T")
    html = ui.get_html()
    assert "/api/openapi.json" in html


def test_swagger_ui_register_adds_routes(tmp_path):
    from altapi import AltAPI

    app = AltAPI(enable_openapi=False, templates_directory=str(tmp_path))
    ui = SwaggerUI(openapi_url="/spec.json", swagger_ui_url="/swagger")
    ui.register(app)
    paths = app._router.get_routes()
    assert "/spec.json" in paths
    assert "/swagger" in paths
