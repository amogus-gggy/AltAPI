"""
SwaggerUI integration for AltAPI.

Provides SwaggerUI HTML page and helper functions.
"""
from typing import Optional


# SwaggerUI HTML template
SWAGGER_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <link rel="icon" type="image/png" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32">
    <link rel="icon" type="image/png" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/favicon-16x16.png" sizes="16x16">
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *,
        *:before,
        *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin: 0;
            background: #fafafa;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                url: "{openapi_url}",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                {display_request_duration}
                {default_models_expand_depth}
                {default_model_expand_depth}
                {doc_expansion}
            }});
            window.ui = ui;
        }};
    </script>
</body>
</html>
"""


def get_swagger_ui_html(
    *,
    openapi_url: str,
    title: str = "Swagger UI - AltAPI",
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    display_request_duration: bool = True,
    default_models_expand_depth: int = 1,
    default_model_expand_depth: int = 1,
    doc_expansion: str = "list",
) -> str:
    """
    Generate SwaggerUI HTML page.
    
    Args:
        openapi_url: URL path to OpenAPI JSON specification
        title: Page title
        swagger_js_url: SwaggerUI JS CDN URL
        swagger_css_url: SwaggerUI CSS CDN URL
        display_request_duration: Show request duration in UI
        default_models_expand_depth: Default expansion depth for models
        default_model_expand_depth: Default expansion depth for model
        doc_expansion: Controls the default expansion setting of the operations and tags
        
    Returns:
        HTML string for SwaggerUI page
    """
    display_request_duration_str = f'displayRequestDuration: {"true" if display_request_duration else "false"},'
    default_models_expand_depth_str = f'defaultModelsExpandDepth: {default_models_expand_depth},'
    default_model_expand_depth_str = f'defaultModelExpandDepth: {default_model_expand_depth},'
    doc_expansion_str = f'docExpansion: "{doc_expansion}",'
    
    html = SWAGGER_UI_TEMPLATE.format(
        title=title,
        openapi_url=openapi_url,
        display_request_duration=display_request_duration_str,
        default_models_expand_depth=default_models_expand_depth_str,
        default_model_expand_depth=default_model_expand_depth_str,
        doc_expansion=doc_expansion_str,
    )
    
    return html.strip()


class SwaggerUI:
    """
    SwaggerUI helper for AltAPI applications.
    
    Provides easy integration of SwaggerUI documentation.
    """
    
    def __init__(
        self,
        openapi_url: str = "/openapi.json",
        swagger_ui_url: str = "/docs",
        title: str = "Swagger UI - AltAPI",
        display_request_duration: bool = True,
        default_models_expand_depth: int = 1,
        default_model_expand_depth: int = 1,
        doc_expansion: str = "list",
    ):
        """
        Initialize SwaggerUI.
        
        Args:
            openapi_url: URL path to OpenAPI JSON specification
            swagger_ui_url: URL path to SwaggerUI page
            title: Page title
            display_request_duration: Show request duration in UI
            default_models_expand_depth: Default expansion depth for models
            default_model_expand_depth: Default expansion depth for model
            doc_expansion: Controls the default expansion setting
        """
        self.openapi_url = openapi_url
        self.swagger_ui_url = swagger_ui_url
        self.title = title
        self.display_request_duration = display_request_duration
        self.default_models_expand_depth = default_models_expand_depth
        self.default_model_expand_depth = default_model_expand_depth
        self.doc_expansion = doc_expansion
    
    def get_html(self) -> str:
        """
        Get SwaggerUI HTML page.
        
        Returns:
            HTML string for SwaggerUI page
        """
        return get_swagger_ui_html(
            openapi_url=self.openapi_url,
            title=self.title,
            display_request_duration=self.display_request_duration,
            default_models_expand_depth=self.default_models_expand_depth,
            default_model_expand_depth=self.default_model_expand_depth,
            doc_expansion=self.doc_expansion,
        )
    
    def register(self, app):
        """
        Register SwaggerUI routes with AltAPI application.
        
        Args:
            app: AltAPI application instance
        """
        from altapi.http.responses import HTMLResponse, JSONResponse
        
        # Store reference to generator
        swagger = self
        
        @app.get(self.swagger_ui_url)
        async def swagger_ui(request):
            """Serve SwaggerUI page."""
            html = swagger.get_html()
            return HTMLResponse(html)
        
        @app.get(self.openapi_url)
        async def openapi_json(request):
            """Serve OpenAPI specification as JSON."""
            # Access the generator from app
            if hasattr(app, '_openapi_generator'):
                spec = app._openapi_generator.generate()
            else:
                spec = {"openapi": "3.0.3", "info": {"title": "AltAPI", "version": "0.1.0"}, "paths": {}}
            return JSONResponse(spec)
