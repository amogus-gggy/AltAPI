"""
Module for working with Jinja2 templates.
"""
import os
from typing import Any, Dict, Optional, Union

from ..http.responses import HTMLResponse


# Global variable for storing default templates_directory
_default_templates_directory: Union[str, os.PathLike] = "templates"


def set_default_templates_directory(directory: Union[str, os.PathLike]) -> None:
    """
    Set the default templates directory for the render_template function.

    Args:
        directory: Path to the templates directory
    """
    global _default_templates_directory
    _default_templates_directory = str(directory)


def get_default_templates_directory() -> str:
    """
    Return the default templates directory.

    Returns:
        Path to the templates directory
    """
    return _default_templates_directory


class Jinja2Templates:
    """
    Class for managing Jinja2 templates.

    Example usage:
        templates = Jinja2Templates(directory="templates")

        @app.get("/")
        async def home(request):
            return templates.TemplateResponse("index.html", {"request": request, "title": "Home"})
    """

    def __init__(self, directory: Union[str, os.PathLike], **env_options):
        """
        Initialize Jinja2 templates.

        Args:
            directory: Path to the templates directory
            **env_options: Additional options for Jinja2 Environment
        """
        try:
            from jinja2 import Environment, FileSystemLoader
        except ImportError:
            raise ImportError("Jinja2 is not installed. Installation: pip install jinja2")
        
        self.directory = str(directory)

        # Default settings
        default_options = {
            "loader": FileSystemLoader(self.directory),
            "autoescape": True,
        }

        default_options.update(env_options)
        
        self.env = Environment(**default_options)
    
    def TemplateResponse(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> "TemplateResponse":
        """
        Render a template and return a TemplateResponse.

        Args:
            name: Template file name
            context: Context for rendering
            status_code: HTTP status code
            headers: HTTP headers

        Returns:
            TemplateResponse object
        """
        return TemplateResponse(
            name=name,
            context=context or {},
            templates=self,
            status_code=status_code,
            headers=headers,
        )


class TemplateResponse(HTMLResponse):
    """
    Response with a rendered HTML template.
    """

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        templates: Optional[Jinja2Templates] = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.context = context or {}
        self.templates = templates

        # Render the template
        template = templates.env.get_template(name)
        content = template.render(**self.context)

        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
        )


def render_template(
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
    templates_directory: Optional[Union[str, os.PathLike]] = None,
    **jinja_options: Any,
) -> HTMLResponse:
    """
    Function for rendering a Jinja2 template.

    Args:
        template_name: Template file name
        context: Context for rendering
        templates_directory: Path to templates directory (uses global setting by default)
        **jinja_options: Additional options for Jinja2

    Returns:
        HTMLResponse with the rendered template

    Example:
        @app.get("/")
        async def home(request):
            return render_template("index.html", {"title": "Home"})
    """
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        raise ImportError("Jinja2 is not installed. Install with: pip install jinja2")

    # Use the provided directory or the default directory
    if templates_directory is None:
        templates_directory = get_default_templates_directory()

    templates = Environment(
        loader=FileSystemLoader(str(templates_directory)),
        autoescape=True
    )

    template = templates.get_template(template_name)
    return HTMLResponse(template.render(context or {}, **jinja_options))
