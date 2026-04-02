"""
run.py — Local Development Entry Point
========================================
This is the file you run locally to start the Flask development server.

Usage:
    python3 run.py

The development server:
  - Runs on http://localhost:5000
  - Auto-reloads when you save changes to Python files (debug=True)
  - Shows detailed error pages in the browser if something crashes
  - Should NEVER be used in production (it's single-threaded and unsecured)

In production on Render, gunicorn is used instead:
  gunicorn run:app
  This means "from run.py, use the `app` variable as the WSGI application."
  Gunicorn handles multiple simultaneous requests properly.
"""

# Import the app factory function from our admin package (__init__.py)
from admin import create_app

# Call the factory to build the configured Flask app.
# This runs all the setup in create_app():
#   - loads .env variables
#   - configures the database
#   - registers routes
#   - creates database tables
app = create_app()

# This block only runs when you execute this file directly with Python.
# It does NOT run when gunicorn imports this file in production —
# gunicorn uses its own server startup logic.
if __name__ == '__main__':
    app.run(
        debug=True,   # Enable auto-reload + detailed error pages
        port=5000,    # Run on port 5000 → http://localhost:5000
    )
