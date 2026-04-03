"""CLI for AltAPI framework."""

import argparse
import ast
import importlib
import os
import sys
from importlib.metadata import version


def _import_app(app_path: str):
    """Import and return the ASGI application from dotted path."""
    try:
        module_str, app_str = app_path.split(":", 1)
    except ValueError:
        print(f"Error: APP_PATH must be in format module:app (e.g. myapp.app:app)", file=sys.stderr)
        sys.exit(1)

    # Add current working directory to sys.path
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        module = importlib.import_module(module_str)
    except ModuleNotFoundError as exc:
        print(f"Error: Module '{module_str}' not found", file=sys.stderr)
        sys.exit(1)

    app = getattr(module, app_str, None)
    if app is None:
        print(f"Error: No attribute '{app_str}' found in module '{module_str}'", file=sys.stderr)
        sys.exit(1)

    return app


def _parse_app_run_config(module_str: str) -> dict:
    """Parse module source to extract app.run() call arguments."""
    try:
        module = importlib.import_module(module_str)
    except ModuleNotFoundError:
        return {}

    module_file = getattr(module, "__file__", None)
    if not module_file or not os.path.exists(module_file):
        return {}

    try:
        with open(module_file, "r", encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return {}

    try:
        tree = ast.parse(source, filename=module_file)
    except SyntaxError:
        return {}

    run_config = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue

        expr = node.value
        if not isinstance(expr, ast.Call):
            continue

        func = expr.func
        is_app_run = False

        # Check for app.run()
        if isinstance(func, ast.Attribute) and func.attr == "run":
            if isinstance(func.value, ast.Name) and func.value.id == "app":
                is_app_run = True

        if not is_app_run:
            continue

        # Extract keyword arguments
        for keyword in expr.keywords:
            if keyword.arg == "host" and isinstance(keyword.value, ast.Constant):
                run_config["host"] = keyword.value.value
            elif keyword.arg == "port" and isinstance(keyword.value, ast.Constant):
                run_config["port"] = keyword.value.value
            elif keyword.arg == "workers" and isinstance(keyword.value, ast.Constant):
                run_config["workers"] = keyword.value.value
            elif keyword.arg == "access_log" and isinstance(keyword.value, ast.Constant):
                run_config["access_log"] = keyword.value.value

    return run_config


def _run_server(args: argparse.Namespace) -> None:
    """Run the development server using uvicorn."""
    import uvicorn

    # Parse module source for app.run() configuration
    module_str = args.app.split(":")[0]
    app_run_config = _parse_app_run_config(module_str)

    # Use CLI args if explicitly provided, otherwise fallback to app.run() config
    cli_host_provided = args.host is not None
    cli_port_provided = args.port is not None
    cli_workers_provided = args.workers is not None

    host = args.host if cli_host_provided else app_run_config.get("host", "127.0.0.1")
    port = args.port if cli_port_provided else app_run_config.get("port", 8000)
    workers = args.workers if cli_workers_provided else app_run_config.get("workers", 1)
    reload = args.reload

    # Reload forces single worker
    if reload:
        workers = 1

    # Convert module:app to proper import string for uvicorn
    app_import_str = args.app.replace("/", ".").replace("\\", ".")
    # Remove trailing .py if present
    if app_import_str.endswith(".py"):
        app_import_str = app_import_str[:-3]


    # Needed because of weird uvicorn routing
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    uvicorn.run(
        app_import_str,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=args.log_level,
    )


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="altapi",
        description="AltAPI CLI"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"altapi {version('AltAPI')}"
    )

    subparsers = parser.add_subparsers(dest="command")

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Start the development server"
    )
    run_parser.add_argument(
        "app",
        metavar="APP",
        help="Application path in format module:app (e.g. examples.app:app)"
    )
    run_parser.add_argument(
        "--host",
        default=None,
        help="Host to bind (default: from app.run() or 127.0.0.1)"
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind (default: from app.run() or 8000)"
    )
    run_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes"
    )
    run_parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: from app.run() or 1)"
    )
    run_parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)"
    )
    run_parser.set_defaults(func=_run_server)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)
