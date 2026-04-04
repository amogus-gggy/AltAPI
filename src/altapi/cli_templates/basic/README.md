# MyProject

A simple AltAPI application.

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Or with altapi CLI
altapi run
```

## API Endpoints

- `GET /` - Welcome message
- `GET /api/health` - Health check
- `GET /api/users/{id:int}` - Get user by ID
- `POST /api/echo` - Echo JSON data
