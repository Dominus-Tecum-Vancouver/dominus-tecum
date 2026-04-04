"""
admin/__init__.py — Flask App Factory
======================================
This is the entry point for the Flask application.
It uses the "app factory" pattern, which means instead of creating
the app at module level, we wrap it in a function (create_app).

Why use a factory? It makes the app easier to test and configure
for different environments (development, production, testing).
"""

import os

from flask_cors import CORS
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# load_dotenv() reads your .env file and loads all variables into
# os.environ so we can access them with os.environ['KEY'].
# This only runs in local development — on Render, env vars are
# set directly in the dashboard and don't need a .env file.
load_dotenv()

# Create the SQLAlchemy database object here at module level,
# but DON'T attach it to an app yet. We'll do that inside create_app().
# This is important because it lets us import `db` from other files
# (like models.py) without causing circular import errors.
db = SQLAlchemy()


def create_app():
    """
    App factory function — builds and returns the configured Flask app.
    Called once at startup from run.py (local) or gunicorn (Render).
    """

    # Create the Flask app instance.
    # __name__ tells Flask where to look for templates and static files
    # relative to this file's location.
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────────────────

    # SECRET_KEY is used by Flask to cryptographically sign session cookies.
    # If someone gets this key they can forge session data, so it must be
    # a long random string stored securely in your .env / Render env vars.
    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

    # Tell SQLAlchemy where the database file lives.
    # sqlite:/// means a local file — Flask will create it automatically
    # the first time the app runs.
    # On Render, the file resets on each deploy, which is fine because
    # Google Sheets is our permanent backup for RSVPs.
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///dominus_tecum.db')
# psycopg3 requires postgresql+psycopg:// prefix instead of postgresql://
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

    # Disables a Flask-SQLAlchemy feature we don't need
    # (tracking every model modification). Keeps things clean and fast.
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Initialize extensions ──────────────────────────────────────────────

    # Attach the SQLAlchemy db object to our app.
    # After this call, db knows which database to talk to.
    db.init_app(app)
    CORS(app)

    # ── Register routes (Blueprint) ────────────────────────────────────────

    # Import the Blueprint (group of routes) from routes.py.
    # We import inside the function to avoid circular imports —
    # routes.py imports `db` from this file, so if we imported routes
    # at the top, Python would try to read routes.py before db was defined.
    from .routes import bp

    # The admin password is stored hashed — never in plain text.
    # generate_password_hash() turns "mypassword" into something like
    # "pbkdf2:sha256:260000$..." — a one-way hash that can be verified
    # but never reversed back to the original password.
    # We store the hash in the routes module so the login route can
    # check submitted passwords against it.
    import admin.routes as routes_module
    routes_module.ADMIN_PASSWORD_HASH = generate_password_hash(
        os.environ['ADMIN_PASSWORD']
    )

    # Register the blueprint with the app.
    # This tells Flask about all our URL routes defined in routes.py.
    app.register_blueprint(bp)

    # ── Create database tables ─────────────────────────────────────────────

    # db.create_all() looks at all our Model classes (Event, RSVP in models.py)
    # and creates the corresponding SQL tables if they don't already exist.
    # The `with app.app_context()` block is required because Flask-SQLAlchemy
    # needs an active app context to interact with the database.
    with app.app_context():
        db.create_all()

    # Return the fully configured app object.
    # run.py assigns this to `app` and either runs it locally
    # or hands it to gunicorn for production on Render.
    return app
