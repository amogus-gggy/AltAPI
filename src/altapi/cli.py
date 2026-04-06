"""
AltAPI CLI - Command Line Interface for AltAPI Framework

Provides commands for:
- Creating new projects from templates
- Running AltAPI applications
- Managing project structure
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

import click


# Default templates directory inside the package
TEMPLATES_DIR = Path(__file__).parent / "cli_templates"


def _copy_template(template_name: str, target_dir: Path, project_name: str):
    """Copy template files to target directory with project name replacement."""
    template_dir = TEMPLATES_DIR / template_name

    if not template_dir.exists():
        click.echo(f"Error: Template '{template_name}' not found.", err=True)
        click.echo(f"Available templates: {', '.join(_get_available_templates())}", err=True)
        sys.exit(1)

    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Recursively copy all files and directories
    for item in template_dir.rglob("*"):
        relative_path = item.relative_to(template_dir)
        target_path = target_dir / relative_path

        if item.is_file():
            # Ensure parent directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            content = item.read_text(encoding="utf-8")
            # Replace placeholder project name
            content = content.replace("myproject", project_name.lower().replace(" ", "_").replace("-", "_"))
            content = content.replace("MyProject", project_name.title().replace(" ", ""))
            target_path.write_text(content, encoding="utf-8")

    click.echo(f"✓ Created project '{project_name}' in {target_dir}")


def _get_available_templates() -> list[str]:
    """Get list of available template names."""
    if not TEMPLATES_DIR.exists():
        return []
    return [d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()]


def _find_app_directory(app_path: str) -> Optional[Path]:
    """Find the directory containing the app module."""
    # Extract module name from app_path (e.g., "examples.app:app" -> "examples/app")
    module_part = app_path.split(":")[0]
    module_path = module_part.replace(".", "/")

    # Try multiple strategies
    candidates = []

    # Strategy 1: Use module path directly (e.g., examples/app.py)
    candidates.append(Path(f"{module_path}.py").parent)

    # Strategy 2: Just the module name (e.g., app.py in current dir)
    module_name = module_part.split(".")[-1]
    candidates.append(Path.cwd())

    # Strategy 3: Parent directories if using dotted notation
    if "." in module_part:
        # For "examples.app:app", try "examples" directory
        parts = module_part.split(".")
        if len(parts) >= 2:
            candidates.append(Path(parts[0]))

    # Check each candidate
    for candidate_dir in candidates:
        if candidate_dir.exists() and candidate_dir.is_dir():
            # Check if app module exists in this directory
            module_name = module_part.split(".")[-1]
            app_file = candidate_dir / f"{module_name}.py"
            if app_file.exists():
                return candidate_dir

    return None


def _find_app_file(directory: Path, app_path: str) -> Optional[Path]:
    """Find the main application file in directory."""
    module_part = app_path.split(":")[0]
    module_name = module_part.split(".")[-1]

    # Try the specific module name first
    app_file = directory / f"{module_name}.py"
    if app_file.exists():
        return app_file

    # Fallback to common filenames
    candidates = ["app.py", "main.py", "server.py", "api.py"]
    for name in candidates:
        filepath = directory / name
        if filepath.exists():
            return filepath
    return None


@click.group()
@click.version_option(version="2.0.0", prog_name="AltAPI CLI")
def cli():
    """
    AltAPI CLI - Command Line Interface for AltAPI Framework

    Create new projects from templates, run applications, and manage your AltAPI projects.
    """
    pass


@cli.command()
@click.argument("name", required=True)
@click.option("--template", "-t", default="basic", help="Template name to use (default: basic)")
@click.option("--dir", "-d", "target_dir", default=None, help="Target directory (default: current directory / project name)")
def create(name: str, template: str, target_dir: Optional[str]):
    """
    Create a new AltAPI project from template.

    NAME is the project name.

    Examples:

    \b
        # Create basic project
        altapi create myapi

    \b
        # Create project in specific directory
        altapi create myapi -d /path/to/projects

    \b
        # Create with different template
        altapi create myapi -t full
    """
    project_name = name
    target_path = Path(target_dir) / project_name if target_dir else Path.cwd() / project_name

    click.echo(f"Creating AltAPI project '{project_name}'...")
    click.echo(f"Template: {template}")
    click.echo(f"Location: {target_path}")
    click.echo("")

    # Copy template
    _copy_template(template, target_path, project_name)

    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {project_name}")
    click.echo("  pip install -e .  # or: pip install altapi")
    click.echo("  python app.py     # or: altapi run")
    click.echo("  Open http://localhost:8000/docs for SwaggerUI")
    click.echo("")


@cli.command()
@click.argument("app_path", default="app:app")
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
@click.option("--port", "-p", default=8000, help="Port to bind to (default: 8000)")
@click.option("--workers", "-w", default=1, help="Number of worker processes (default: 1)")
@click.option("--reload", "-r", is_flag=True, help="Enable auto-reload on code changes")
@click.option("--log-level", default="info", type=click.Choice(["critical", "error", "warning", "info", "debug"]), help="Log level (default: info)")
@click.option("--app-dir", default=None, help="Directory containing app module (default: auto-detect)")
def run(app_path: str, host: str, port: int, workers: int, reload: bool, log_level: str, app_dir: Optional[str]):
    """
    Run an AltAPI application.

    APP_PATH is the module:attribute specifier (default: app:app).

    Examples:

    \b
        # Run default app (app:app)
        altapi run

    \b
        # Run with specific app path
        altapi run main:app

    \b
        # Run with auto-reload on specific port
        altapi run -p 8080 --reload

    \b
        # Run with multiple workers
        altapi run -w 4

    \b
        # Run from examples directory
        altapi run examples.app:app
    """
    # Auto-detect app directory if not specified
    if app_dir is None:
        detected_dir = _find_app_directory(app_path)
        if detected_dir and detected_dir.exists():
            app_dir = str(detected_dir)
            click.echo(f"Auto-detected app directory: {app_dir}")
        else:
            app_dir = "."
    else:
        # Change to app directory
        if not Path(app_dir).exists():
            click.echo(f"Error: Directory '{app_dir}' not found.", err=True)
            sys.exit(1)

    # Check if app file exists
    module_name = app_path.split(":")[0]
    module_base_name = module_name.split(".")[-1]
    app_file = Path(app_dir) / f"{module_base_name}.py"

    if not app_file.exists():
        # Try searching for the full module path
        module_path = module_name.replace(".", "/")
        app_file = Path(app_dir) / f"{module_path}.py"

        if not app_file.exists():
            click.echo(f"Error: App file '{module_base_name}.py' not found in '{app_dir}'.", err=True)
            click.echo("Make sure you're in the correct directory or use --app-dir.", err=True)
            sys.exit(1)

    click.echo(f"Starting AltAPI server...")
    click.echo(f"  App: {app_path}")
    click.echo(f"  Host: {host}")
    click.echo(f"  Port: {port}")
    click.echo(f"  Workers: {workers}")
    click.echo(f"  Reload: {reload}")
    click.echo(f"  Log Level: {log_level}")
    click.echo(f"  App Dir: {app_dir}")
    click.echo("")

    # Change to app directory
    original_dir = os.getcwd()
    
    # If we changed directory, add the original directory to PYTHONPATH
    # so that dotted module paths like "examples.app:app" can be found
    env = os.environ.copy()
    if Path(app_dir).resolve() != Path(original_dir).resolve():
        # Add parent directory to PYTHONPATH for module resolution
        parent_dir = str(Path(app_dir).parent.resolve())
        if parent_dir not in env.get("PYTHONPATH", ""):
            current_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{parent_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else parent_dir

    os.chdir(app_dir)

    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        app_path,
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--log-level", log_level,
        "--http", "httptools",
    ]

    if reload:
        cmd.append("--reload")

    try:
        # Run uvicorn with updated environment
        subprocess.run(cmd, check=True, env=env)
    except KeyboardInterrupt:
        click.echo("\nServer stopped.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: Server exited with code {e.returncode}", err=True)
        sys.exit(e.returncode)
    finally:
        # Restore original directory
        os.chdir(original_dir)


@cli.command("list-templates")
def list_templates():
    """List available project templates."""
    templates = _get_available_templates()

    if not templates:
        click.echo("No templates found.")
        return

    click.echo("Available templates:")
    click.echo("")
    for template in sorted(templates):
        template_dir = TEMPLATES_DIR / template
        desc_file = template_dir / "DESCRIPTION"
        if desc_file.exists():
            desc = desc_file.read_text(encoding="utf-8").strip()
            click.echo(f"  {template:15s} {desc}")
        else:
            click.echo(f"  {template}")
    click.echo("")


@cli.command()
@click.argument("template_name", required=True)
def show_template(template_name: str):
    """
    Show contents of a template.

    TEMPLATE_NAME is the name of the template to show.
    """
    template_dir = TEMPLATES_DIR / template_name

    if not template_dir.exists():
        click.echo(f"Error: Template '{template_name}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Template: {template_name}")
    click.echo(f"Location: {template_dir}")
    click.echo("")
    click.echo("Files:")

    for item in sorted(template_dir.iterdir()):
        if item.is_file():
            size = item.stat().st_size
            click.echo(f"  {item.name:30s} {size:>8d} bytes")

    click.echo("")


@cli.command()
def init():
    """
    Initialize AltAPI in current directory (quick setup).

    Creates minimal app.py and requirements.txt in current directory.
    """
    current_dir = Path.cwd()

    # Check if already initialized
    app_file = current_dir / "app.py"
    if app_file.exists():
        click.echo(f"Warning: {app_file} already exists.", err=True)
        if not click.confirm("Overwrite?", default=False):
            click.echo("Aborted.")
            return

    # Create app.py
    app_content = '''"""AltAPI Application"""
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.openapi_decorators import openapi

app = AltAPI(
    title="MyAPI",
    version="0.1.0",
    description="My API built with AltAPI",
)


@app.get("/")
@openapi(summary="Home", description="Welcome endpoint", tags=["general"])
async def home(request):
    return JSONResponse({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
'''
    app_file.write_text(app_content, encoding="utf-8")
    click.echo("✓ Created app.py")

    # Create requirements.txt
    req_file = current_dir / "requirements.txt"
    if not req_file.exists():
        req_file.write_text("altapi\n", encoding="utf-8")
        click.echo("✓ Created requirements.txt")
    else:
        click.echo("  requirements.txt already exists")

    click.echo("")
    click.echo("Next steps:")
    click.echo("  pip install -r requirements.txt")
    click.echo("  python app.py  # or: altapi run")
    click.echo("  Open http://localhost:8000/docs for SwaggerUI")
    click.echo("")


@cli.command()
@click.argument("name", default="myproject")
@click.option("--dir", "-d", "target_dir", default=None, help="Target directory")
def scaffold(name: str, target_dir: Optional[str]):
    """
    Scaffold a full-featured AltAPI project.

    Creates project with templates, static files, and example routes.

    NAME is the project name (default: myproject).
    """
    project_name = name
    target_path = Path(target_dir) / project_name if target_dir else Path.cwd() / project_name

    click.echo(f"Scaffolding full AltAPI project '{project_name}'...")
    click.echo(f"Location: {target_path}")
    click.echo("")

    # Create directory structure
    dirs = [
        target_path,
        target_path / "templates",
        target_path / "static" / "css",
        target_path / "static" / "js",
        target_path / "routes",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"✓ Created {d.relative_to(target_path)}")

    # Create main app.py
    app_content = f'''"""{project_name} - Main Application"""
from altapi import AltAPI
from altapi.templating import render_template
import os

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

# Create app with OpenAPI/SwaggerUI enabled
app = AltAPI(
    templates_directory=templates_dir,
    static_directory=static_dir,
    cache_timeout=300,
    # OpenAPI settings
    title="{project_name} API",
    version="0.1.0",
    description="Full-featured API built with AltAPI",
    # For production, disable OpenAPI:
    # enable_openapi=False,
    # Custom URLs:
    # openapi_url="/api/openapi.json",
    # docs_url="/api/docs",
)


@app.get("/")
async def home(request):
    return render_template("index.html", {{"request": request, "title": "Home"}})


# Import and register routes from modules
from routes.api import register_routes as register_api_routes
from routes.pages import register_routes as register_pages_routes

register_api_routes(app)
register_pages_routes(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=2)
'''
    (target_path / "app.py").write_text(app_content, encoding="utf-8")
    click.echo("✓ Created app.py")

    # Create routes/__init__.py
    (target_path / "routes" / "__init__.py").write_text("", encoding="utf-8")

    # Create routes/api.py
    api_content = '''"""API Routes"""
from altapi.http import JSONResponse
from altapi.openapi_decorators import openapi


def register_routes(app):
    """Register API routes."""

    @app.get("/api/health")
    @openapi(summary="Health Check", description="API health status", tags=["system"])
    async def health_check(request):
        return JSONResponse({"status": "ok"})

    @app.get("/api/version")
    @openapi(summary="Version", description="API version info", tags=["system"])
    async def version(request):
        return JSONResponse({"version": "1.0.0"})
'''
    (target_path / "routes" / "api.py").write_text(api_content, encoding="utf-8")
    click.echo("✓ Created routes/api.py")

    # Create routes/pages.py
    pages_content = '''"""Page Routes"""
from altapi.http import HTMLResponse
from altapi.openapi_decorators import openapi


def register_routes(app):
    """Register page routes."""

    @app.get("/about")
    @openapi(summary="About Page", description="About information page", tags=["pages"])
    async def about_page(request):
        return HTMLResponse("<h1>About Page</h1>")
'''
    (target_path / "routes" / "pages.py").write_text(pages_content, encoding="utf-8")
    click.echo("✓ Created routes/pages.py")

    # Create base.html template
    template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}MyProject{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <header>
        <h1>{% block header %}MyProject{% endblock %}</h1>
        <nav>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="/docs">Docs</a>
        </nav>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
    <footer>
        <p>&copy; 2026 MyProject | <a href="/docs">API Docs</a> | <a href="/openapi.json">OpenAPI JSON</a></p>
    </footer>
    <script src="/static/js/main.js"></script>
</body>
</html>
'''
    (target_path / "templates" / "base.html").write_text(template_content, encoding="utf-8")
    click.echo("✓ Created templates/base.html")

    # Create index.html template
    index_content = '''{% extends "base.html" %}

{% block title %}Home - MyProject{% endblock %}

{% block header %}MyProject{% endblock %}

{% block content %}
<div class="container">
    <div class="hero">
        <h1>Welcome to MyProject</h1>
        <p>A full-featured AltAPI application with templates, static files, and modular routing.</p>
    </div>

    <div class="features">
        <div class="feature-card">
            <h3>🚀 Fast</h3>
            <p>Built on uvicorn with optimized Cython router.</p>
        </div>
        <div class="feature-card">
            <h3>📦 Modular</h3>
            <p>Organize routes in separate modules with <code>register_routes(app)</code>.</p>
        </div>
        <div class="feature-card">
            <h3>🎨 Templates</h3>
            <p>Jinja2 templating with inheritance and blocks.</p>
        </div>
        <div class="feature-card">
            <h3>💾 Caching</h3>
            <p>Built-in per-worker in-memory caching.</p>
        </div>
        <div class="feature-card">
            <h3>🔌 WebSocket</h3>
            <p>Full WebSocket support out of the box.</p>
        </div>
        <div class="feature-card">
            <h3>📖 OpenAPI</h3>
            <p>Auto-generated OpenAPI spec with SwaggerUI docs.</p>
        </div>
        <div class="feature-card">
            <h3>🔧 Middleware</h3>
            <p>ASGI-compatible middleware system.</p>
        </div>
    </div>

    <div class="getting-started">
        <h2>Getting Started</h2>
        <p>Edit <code>templates/index.html</code> to customize this page.</p>
        <p>Check <code>routes/</code> directory for API and page routes.</p>
    </div>

    <div class="api-links">
        <a href="/docs" class="api-link">📖 SwaggerUI Docs</a>
        <a href="/openapi.json" class="api-link">📄 OpenAPI JSON</a>
        <a href="/api/health" class="api-link">GET /api/health</a>
        <a href="/api/version" class="api-link">GET /api/version</a>
        <a href="/about" class="api-link">GET /about</a>
    </div>
</div>
{% endblock %}
'''
    (target_path / "templates" / "index.html").write_text(index_content, encoding="utf-8")
    click.echo("✓ Created templates/index.html")

    # Create style.css
    css_content = '''/* Main Styles */
* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0;
    padding: 0;
    line-height: 1.6;
    color: #333;
}

header {
    background: #333;
    color: white;
    padding: 1rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

header h1 {
    margin: 0;
    font-size: 1.5rem;
}

header nav a {
    color: white;
    margin-left: 1.5rem;
    text-decoration: none;
    transition: opacity 0.2s;
}

header nav a:hover {
    opacity: 0.8;
}

main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

footer {
    background: #f4f4f4;
    text-align: center;
    padding: 1rem;
    margin-top: 3rem;
    color: #666;
}

/* Hero Section */
.hero {
    text-align: center;
    padding: 3rem 1rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.hero h1 {
    font-size: 2.5rem;
    margin: 0 0 1rem 0;
}

.hero p {
    font-size: 1.2rem;
    opacity: 0.9;
}

/* Features Grid */
.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.feature-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1.5rem;
    transition: box-shadow 0.2s, transform 0.2s;
}

.feature-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}

.feature-card h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.2rem;
}

.feature-card p {
    margin: 0;
    color: #666;
}

.feature-card code {
    background: #f5f5f5;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.9em;
}

/* Getting Started */
.getting-started {
    background: #f9f9f9;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.getting-started h2 {
    margin: 0 0 1rem 0;
}

.getting-started p {
    margin: 0.5rem 0;
}

.getting-started code {
    background: #e0e0e0;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.9em;
}

/* API Links */
.api-links {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}

.api-link {
    display: inline-block;
    background: #667eea;
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    text-decoration: none;
    font-family: monospace;
    transition: background 0.2s;
}

.api-link:hover {
    background: #5568d3;
}
'''
    (target_path / "static" / "css" / "style.css").write_text(css_content, encoding="utf-8")
    click.echo("✓ Created static/css/style.css")

    # Create main.js
    js_content = '''// Main JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('Application loaded');
});
'''
    (target_path / "static" / "js" / "main.js").write_text(js_content, encoding="utf-8")
    click.echo("✓ Created static/js/main.js")

    # Create requirements.txt
    req_file = target_path / "requirements.txt"
    if not req_file.exists():
        req_file.write_text("altapi\n", encoding="utf-8")
        click.echo("✓ Created requirements.txt")

    click.echo("")
    click.echo("✓ Project scaffolded successfully!")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {project_name}")
    click.echo("  pip install -r requirements.txt")
    click.echo("  python app.py")
    click.echo("  Open http://localhost:8000/docs for SwaggerUI")
    click.echo("")


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
