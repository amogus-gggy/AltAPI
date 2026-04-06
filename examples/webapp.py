"""
AltAPI Example: User Management App with SQLite + Web UI

Full-featured example with:
- Dependency Injection
- SQLite database
- HTML templates with Bootstrap
- CRUD operations with web interface
- API endpoints

Run: python examples/webapp.py
Open: http://localhost:8000
"""

import sqlite3
from altapi import AltAPI
from altapi.http import JSONResponse, HTMLResponse, RedirectResponse
from altapi.depends import Depends
from altapi.templating import Jinja2Templates

# =============================================================================
# Configuration
# =============================================================================

DATABASE_PATH = "users.db"
templates = Jinja2Templates(directory="examples/templates")

# =============================================================================
# Database Setup
# =============================================================================


def get_db_connection():
    """Create database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with tables and sample data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            age INTEGER,
            city TEXT
        )
    """)

    # Check if we need to add sample data
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        sample_users = [
            ("John Doe", "john@example.com", 28, "New York"),
            ("Jane Smith", "jane@example.com", 34, "Los Angeles"),
            ("Bob Wilson", "bob@example.com", 22, "Chicago"),
            ("Alice Brown", "alice@example.com", 45, "Houston"),
            ("Charlie Davis", "charlie@example.com", 31, "Phoenix"),
        ]
        cursor.executemany(
            "INSERT INTO users (name, email, age, city) VALUES (?, ?, ?, ?)",
            sample_users,
        )
        print(f"Added {len(sample_users)} sample users")

    conn.commit()
    conn.close()
    print("Database initialized")


# =============================================================================
# Dependencies
# =============================================================================


def get_db():
    """Database dependency - provides connection with automatic cleanup."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


# =============================================================================
# Application
# =============================================================================

app = AltAPI(templates_directory="examples/templates")


# =============================================================================
# Web Pages (HTML)
# =============================================================================


@app.get("/")
async def home(request, db=Depends(get_db)):
    """Home page - list all users."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users = [dict(row) for row in cursor.fetchall()]

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "title": "Users",
        },
    )


@app.get("/users/new")
async def new_user_form(request):
    """Show create user form."""
    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "title": "New User",
            "action": "/users",
            "user": None,
        },
    )


@app.post("/users")
async def create_user(request, db=Depends(get_db)):
    """Create new user."""
    data = await request.form()

    name = data.get("name")
    email = data.get("email")
    age = data.get("age")
    city = data.get("city")

    if not name or not email:
        return HTMLResponse("Name and email are required", status_code=400)

    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, age, city) VALUES (?, ?, ?, ?)",
            (name, email, int(age) if age else None, city),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return HTMLResponse("Email already exists", status_code=400)

    return RedirectResponse("/", status_code=303)


@app.get("/users/{id:int}/edit")
async def edit_user_form(request, id: int, db=Depends(get_db)):
    """Show edit user form."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        return HTMLResponse("User not found", status_code=404)

    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "title": f"Edit: {user['name']}",
            "action": f"/users/{id}",
            "user": dict(user),
        },
    )


@app.post("/users/{id:int}")
async def update_user(request, id: int, db=Depends(get_db)):
    """Update user."""
    data = await request.form()

    cursor = db.cursor()
    cursor.execute(
        "UPDATE users SET name=?, email=?, age=?, city=? WHERE id=?",
        (
            data.get("name"),
            data.get("email"),
            int(data.get("age")) if data.get("age") else None,
            data.get("city"),
            id,
        ),
    )
    db.commit()

    return RedirectResponse("/", status_code=303)


@app.post("/users/{id:int}/delete")
async def delete_user(request, id: int, db=Depends(get_db)):
    """Delete user."""
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    db.commit()

    return RedirectResponse("/", status_code=303)


# =============================================================================
# API Endpoints (JSON)
# =============================================================================


@app.get("/api/users")
async def api_list_users(db=Depends(get_db)):
    """API: List all users."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users = [dict(row) for row in cursor.fetchall()]
    return JSONResponse({"users": users})


@app.get("/api/users/{id:int}")
async def api_get_user(id: int, db=Depends(get_db)):
    """API: Get single user."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)

    return JSONResponse({"user": dict(user)})


@app.post("/api/users")
async def api_create_user(request, db=Depends(get_db)):
    """API: Create user."""
    data = await request.json()

    name = data.get("name")
    email = data.get("email")
    age = data.get("age")
    city = data.get("city")

    if not name or not email:
        return JSONResponse({"error": "name and email required"}, status_code=400)

    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, age, city) VALUES (?, ?, ?, ?)",
            (name, email, age, city),
        )
        db.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return JSONResponse({"error": "email already exists"}, status_code=400)

    return JSONResponse(
        {"id": user_id, "name": name, "email": email, "age": age, "city": city},
        status_code=201,
    )


@app.delete("/api/users/{id:int}")
async def api_delete_user(id: int, db=Depends(get_db)):
    """API: Delete user."""
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    db.commit()

    if cursor.rowcount == 0:
        return JSONResponse({"error": "User not found"}, status_code=404)

    return JSONResponse({"status": "ok"})


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    init_db()
    print("\n" + "=" * 50)
    print("🚀 Starting server...")
    print("📱 Web UI: http://localhost:8000")
    print("🔧 API:    http://localhost:8000/api/users")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=8000)
