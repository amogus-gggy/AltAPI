# MyProject

A simple AltAPI application with OpenAPI/SwaggerUI documentation.

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

## API Endpoints

- `GET /` - Welcome message
- `GET /api/health` - Health check
- `GET /api/users/{id:int}` - Get user by ID
- `POST /api/echo` - Echo JSON data
