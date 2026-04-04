# MyProject

A full-featured AltAPI application with templates and static files.

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Or with altapi CLI
altapi run
```

## Features

- ✅ Jinja2 templates
- ✅ Static file serving
- ✅ Response caching
- ✅ JSON and HTML responses
- ✅ Multi-worker support

## Project Structure

```
myproject/
├── app.py                 # Main application
├── requirements.txt       # Dependencies
├── templates/             # Jinja2 templates
│   ├── base.html
│   └── index.html
└── static/                # Static files
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```
