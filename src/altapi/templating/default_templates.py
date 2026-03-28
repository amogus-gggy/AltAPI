"""
Default HTML templates for error pages.
"""

DEFAULT_404_BODY = """<!DOCTYPE html>
<html>
<head>
    <title>404 Not Found</title>
</head>
<body>
    <h1>404 Not Found</h1>
    <p>The requested resource was not found.</p>
</body>
</html>"""

DEFAULT_405_BODY = """<!DOCTYPE html>
<html>
<head>
    <title>405 Method Not Allowed</title>
</head>
<body>
    <h1>405 Method Not Allowed</h1>
    <p>The requested method is not allowed for this resource.</p>
</body>
</html>"""

DEFAULT_500_BODY = """<!DOCTYPE html>
<html>
<head>
    <title>500 Internal Server Error</title>
</head>
<body>
    <h1>500 Internal Server Error</h1>
    <p>An internal server error occurred.</p>
</body>
</html>"""
