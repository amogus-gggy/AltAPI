# MyProject

A full-featured AltAPI application with templates, static files, and OpenAPI/SwaggerUI documentation.

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Or with altapi CLI
altapi run
```

## API Documentation

Once the server is running:
- **SwaggerUI**: http://localhost:8000/docs
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Features

- ✅ OpenAPI 3.0 & SwaggerUI
- ✅ Jinja2 templates
- ✅ Static file serving
- ✅ Response caching
- ✅ JSON and HTML responses
- ✅ Multi-worker support
- ✅ Modular routing

## Project Structure

```
myproject/
├── app.py                 # Main application
├── requirements.txt       # Dependencies
├── routes/                # Route modules
│   ├── __init__.py
│   ├── api.py             # API routes
│   └── pages.py           # Page routes
├── templates/             # Jinja2 templates
│   ├── base.html
│   └── index.html
└── static/                # Static files
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```
