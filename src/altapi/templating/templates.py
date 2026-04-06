"""
Module for working with Jinja2 templates.
"""

import os
from typing import Any, Dict, Optional, Union

from ..http.responses import HTMLResponse

# Import Jinja2 Undefined for subclass check
try:
    from jinja2 import Undefined

    class _SilentUndefined(Undefined):
        """Silent undefined handler for faster template rendering."""

        __slots__ = ()

        def __str__(self) -> str:
            return ""

        def __iter__(self):
            return iter(())

        def __bool__(self) -> bool:
            return False
except ImportError:

    class _SilentUndefined:  # type: ignore
        __slots__ = ()

        def __str__(self) -> str:
            return ""

        def __iter__(self):
            return iter(())

        def __bool__(self) -> bool:
            return False


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
    Optimized Jinja2 templates with compiled template cache.

    Uses auto_reload=False and precompiled templates for maximum performance.
    """

    __slots__ = ("env", "directory")

    def __init__(
        self,
        directory: Union[str, os.PathLike],
        auto_reload: bool = False,
        **env_options,
    ):
        """
        Initialize Jinja2 templates.

        Args:
            directory: Path to the templates directory
            auto_reload: Auto-reload templates on change (disable for production)
            **env_options: Additional options for Jinja2 Environment
        """
        try:
            from jinja2 import Environment, FileSystemLoader
        except ImportError:
            raise ImportError(
                "Jinja2 is not installed. Installation: pip install jinja2"
            )

        self.directory = str(directory)

        # Optimized default settings for production
        default_options = {
            "loader": FileSystemLoader(self.directory),
            "autoescape": True,
            "auto_reload": auto_reload,
            "cache_size": 4096,  # Cache up to 4096 compiled templates
            "undefined": _SilentUndefined,
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

    def render(self, name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Fast template rendering without response object.

        Args:
            name: Template file name
            context: Context for rendering

        Returns:
            Rendered template string
        """
        template = self.env.get_template(name)
        return template.render(**(context or {}))


class TemplateResponse(HTMLResponse):
    """
    Optimized response with a rendered HTML template.

    Renders template at initialization (eager loading) for caching compatibility.
    """

    __slots__ = ()

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        templates: Optional[Jinja2Templates] = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ):
        # Render the template immediately
        template = templates.env.get_template(name)
        content = template.render(**(context or {}))

        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
        )


# Global cache for Jinja2 environments
_template_env_cache: Dict[str, Any] = {}


def render_template(
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
    templates_directory: Optional[Union[str, os.PathLike]] = None,
    **jinja_options: Any,
) -> HTMLResponse:
    """
    Optimized function for rendering a Jinja2 template.

    Uses cached Environment for better performance.

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

    dir_str = str(templates_directory)

    # Get or create cached environment
    env = _template_env_cache.get(dir_str)
    if env is None:
        env = Environment(
            loader=FileSystemLoader(dir_str),
            autoescape=True,
            cache_size=4096,
            auto_reload=False,
            **jinja_options,
        )
        _template_env_cache[dir_str] = env

    template = env.get_template(template_name)
    return HTMLResponse(template.render(**(context or {})))
