"""
admin/routes.py — URL Routes
==============================
This file defines every URL endpoint the app responds to.
There are two categories:

  1. Public API endpoints (/api/events, /api/rsvp)
     — Called by the frontend JavaScript, return JSON

  2. Admin panel routes (/admin, /admin/events, /admin/rsvps)
     — Only accessible after logging in, return HTML pages

We use a Flask Blueprint to group all these routes together.
A Blueprint is like a mini app that gets registered onto the main app
in __init__.py. It helps keep the code organized.
"""

from datetime import datetime

from flask import (
    Blueprint,       # Groups routes into a reusable component
    abort,           # Returns HTTP error responses (404, 403, etc.)
    jsonify,         # Converts Python dicts/lists to JSON responses
    redirect,        # Sends the browser to a different URL
    render_template, # Renders an HTML template file
    request,         # Gives access to incoming request data (form, JSON, args)
    session,         # Server-side session storage (persists across requests)
    url_for,         # Generates a URL from a route function name
)
from werkzeug.security import check_password_hash  # Verifies hashed passwords

from . import db
from .gmail_service import send_rsvp_confirmation, send_rsvp_notification
from .models import Event, RSVP, Resource, PrayerRequest
from .sheets_service import log_rsvp

# Create the Blueprint — 'main' is its name, used internally by Flask
bp = Blueprint('main', __name__)

# This will be set by the app factory in __init__.py.
# We can't set it here because the env var isn't available at import time.
ADMIN_PASSWORD_HASH = None


# ── Auth Helper ────────────────────────────────────────────────────────────────

def admin_required(f):
    """
    A decorator that protects admin routes from unauthenticated access.

    A decorator wraps a function to add behaviour before/after it runs.
    Usage: put @admin_required above any route that needs login protection.

    How it works:
      1. When someone visits a protected route, this runs first
      2. It checks if 'admin' is set in their session (set at login)
      3. If not logged in → redirect to login page
      4. If logged in → run the original route function normally

    The session is a secure cookie stored in the browser.
    Flask signs it with SECRET_KEY so it can't be tampered with.
    """
    from functools import wraps

    @wraps(f)  # Preserves the original function's name and docstring
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            # Not logged in — send them to the login page
            return redirect(url_for('main.admin_login'))
        # Logged in — run the actual route function
        return f(*args, **kwargs)
    return decorated


# ── Public API ─────────────────────────────────────────────────────────────────

@bp.route('/api/events')
def api_events():
    """
    GET /api/events?lang=es

    Returns a JSON list of all active events.
    The frontend JavaScript calls this on page load to populate the events section.

    Query parameter:
      ?lang=es  — returns Spanish titles/descriptions (default)
      ?lang=en  — returns English titles/descriptions

    Example response:
      [
        {
          "id": 1,
          "title": "Noche de Convivencia",
          "desc": "Una noche relajada...",
          "date": "11",
          "month": "ABR",
          "time": "6:30 PM",
          "tag": "social"
        },
        ...
      ]
    """
    # Read the ?lang= query parameter, default to 'es' if not provided
    lang = request.args.get('lang', 'es')

    # Query the database for active events, sorted by date (soonest first)
    from datetime import date
    events = Event.query.filter(
        Event.active == True,
        Event.date >= date.today()
    ).order_by(Event.date.asc()).all()

    # Convert each Event object to a dict, then return as JSON
    # jsonify() automatically sets the Content-Type header to application/json
    return jsonify([e.to_dict(lang) for e in events])


@bp.route('/api/rsvp', methods=['POST'])
def api_rsvp():
    """
    POST /api/rsvp

    Accepts an RSVP submission from the frontend form.
    Expects a JSON body with: first_name, last_name, email, event_id, first_time

    On success:
      1. Saves the RSVP to the database
      2. Logs it to Google Sheets as a backup
      3. Sends a confirmation email to the attendee
      4. Sends a notification email to the group inbox

    Returns JSON: { "status": "ok", "message": "¡Gracias, Alberto!" }
    """
    # request.get_json() parses the incoming JSON body.
    # silent=True means it returns None instead of raising an error
    # if the body isn't valid JSON.
    data = request.get_json(silent=True)
    if not data:
        # 400 Bad Request — the request body wasn't valid JSON
        return jsonify({'error': 'Invalid JSON'}), 400

    # Extract fields from the JSON body, with safe defaults
    first_name = data.get('first_name', '').strip()
    last_name  = data.get('last_name', '').strip()
    email      = data.get('email', '').strip()
    event_id   = data.get('event_id')
    first_time = bool(data.get('first_time', False))  # Convert to bool safely

    # Validate that all required fields are present
    if not first_name or not last_name or not email or not event_id:
        # 422 Unprocessable Entity — the data is there but incomplete
        return jsonify({'error': 'Missing required fields'}), 422

    # Look up the event in the database
    event = Event.query.get(event_id)
    if not event or not event.active:
        # 404 Not Found — event doesn't exist or has been archived
        return jsonify({'error': 'Event not found'}), 404

    # Full name used for emails and display
    full_name = f'{first_name} {last_name}'

    # Check for duplicate RSVP — same email can't RSVP twice for the same event
    existing = RSVP.query.filter_by(email=email, event_id=event_id).first()
    if existing:
        return jsonify({
            'status': 'duplicate',
            'message': f'¡{first_name}, ya tienes un lugar reservado para este evento!'
        }), 200

    # ── Step 1: Save to database ───────────────────────────────────────────
    rsvp = RSVP(
        first_name = first_name,
        last_name  = last_name,
        email      = email,
        event_id   = event_id,
        first_time = first_time
    )
    db.session.add(rsvp)
    db.session.commit()

    # Use Spanish event title for emails (the group's primary language)
    event_title = event.title_es

    # ── Step 2: Log to Google Sheets ───────────────────────────────────────
    log_rsvp(full_name, email, event_title, first_time)

    # ── Step 3: Confirmation email to the person who RSVPed ────────────────
    send_rsvp_confirmation(full_name, email, event_title, event.location, event.time, event.date)

    # ── Step 4: Notification email to the group Gmail inbox ────────────────
    send_rsvp_notification(full_name, email, event_title, first_time, event.location, event.date, event.time)

    # Return success — the frontend will show a thank-you message
    return jsonify({'status': 'ok', 'message': f'¡Gracias, {first_name}!'})

# ── Admin Panel ────────────────────────────────────────────────────────────────

@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    GET  /admin/login — Shows the login form
    POST /admin/login — Processes the submitted password

    We use a single password (no usernames) for simplicity.
    The password is stored hashed in ADMIN_PASSWORD_HASH — we never
    store or compare plain text passwords.
    """
    error = None

    if request.method == 'POST':
        # request.form is a dictionary of submitted HTML form fields
        password = request.form.get('password', '')

        # check_password_hash compares the submitted password against
        # the stored hash. Returns True if they match.
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            # Set 'admin': True in the session cookie.
            # This persists across requests until logout or browser close.
            session['admin'] = True
            # Redirect to the dashboard after successful login
            return redirect(url_for('main.admin_dashboard'))

        # Wrong password — set error message to display on the form
        error = 'Contraseña incorrecta.'

    # GET request (first visit) or failed POST — show the login form
    # Pass `error` to the template so it can display it if needed
    return render_template('admin/login.html', error=error)


@bp.route('/admin/logout')
def admin_logout():
    """
    GET /admin/logout

    Clears the admin session (logs out) and redirects to login.
    session.pop() removes the 'admin' key if it exists, or does
    nothing if it doesn't (the None default prevents a KeyError).
    """
    session.pop('admin', None)
    return redirect(url_for('main.admin_login'))


@bp.route('/admin')
@admin_required  # ← This decorator runs first, checking login before the function
def admin_dashboard():
    """
    GET /admin

    The main admin dashboard — shows all events and recent RSVPs.
    Only accessible when logged in (enforced by @admin_required).
    """
    # Get all events, most recent first
    events = Event.query.order_by(Event.date.desc()).all()
    # Get the 50 most recent RSVPs — enough for the dashboard summary
    rsvps = RSVP.query.order_by(RSVP.created_at.desc()).limit(50).all()

    # render_template() finds the file in the templates/ folder,
    # fills in the variables we pass, and returns the resulting HTML.
    from datetime import date
    return render_template('admin/dashboard.html', events=events, rsvps=rsvps, today=date.today())


@bp.route('/admin/events/new', methods=['GET', 'POST'])
@admin_required
def admin_event_new():
    """
    GET  /admin/events/new — Shows the blank event creation form
    POST /admin/events/new — Creates a new event from the form data
    """
    if request.method == 'POST':
        # request.form contains all the HTML form fields by name
        f = request.form

        # Build a new Event object from the submitted form data
        event = Event(
            title_es = f['title_es'],
            title_en = f['title_en'],
            desc_es  = f['desc_es'],
            desc_en  = f['desc_en'],
            # strptime parses a date string into a Python date object.
            # '%Y-%m-%d' matches the format HTML date inputs produce (e.g. "2026-04-11")
            # .date() strips the time part since we only need the date.
            date     = datetime.strptime(f['date'], '%Y-%m-%d').date(),
            time     = f['time'],
            tag      = f['tag'],
            active   = True,  # New events are active by default
            # Use None if left blank so the frontend knows to show the default location
            location     = f.get('location') or None,
            location_url = f.get('location_url') or None,
        )
        db.session.add(event)
        db.session.commit()

        # After creating the event, redirect back to the dashboard
        return redirect(url_for('main.admin_dashboard'))

    # GET — show the empty form (event=None tells the template it's a new event)
    return render_template('admin/event_form.html', event=None)


@bp.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_event_edit(event_id):
    """
    GET  /admin/events/3/edit — Shows the form pre-filled with event 3's data
    POST /admin/events/3/edit — Saves changes to event 3

    <int:event_id> in the URL is a path parameter — Flask extracts the
    number and passes it as the event_id argument to this function.
    """
    # get_or_404() fetches the event by ID, or automatically returns
    # a 404 Not Found response if no event with that ID exists.
    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        f = request.form
        # Update each field on the existing event object
        event.title_es = f['title_es']
        event.title_en = f['title_en']
        event.desc_es  = f['desc_es']
        event.desc_en  = f['desc_en']
        event.date     = datetime.strptime(f['date'], '%Y-%m-%d').date()
        event.time     = f['time']
        event.tag      = f['tag']
        # The 'active' checkbox is only in the form data when it's checked.
        # 'active' in f checks whether the key exists in the form submission.
        event.active = f.get('active') == 'active'
        event.location     = f.get('location') or None
        event.location_url = f.get('location_url') or None
        # No need to db.session.add() — SQLAlchemy already tracks this object.
        # Just commit to save the changes.
        db.session.commit()
        return redirect(url_for('main.admin_dashboard'))

    # GET — show the form pre-filled with the event's current data
    return render_template('admin/event_form.html', event=event)


@bp.route('/admin/events/<int:event_id>/delete', methods=['POST'])
@admin_required
def admin_event_delete(event_id):
    """
    POST /admin/events/3/delete

    Deletes event 3 from the database.
    We use POST (not GET) for destructive actions as a safety measure —
    browsers can pre-fetch GET links, which could accidentally delete things.
    The form in the template includes a JS confirm() dialog as a second check.
    """
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))


@bp.route('/admin/rsvps')
@admin_required
def admin_rsvps():
    """
    GET /admin/rsvps
    GET /admin/rsvps?event_id=3  — Filter to show only RSVPs for event 3

    Full RSVP list page with optional filtering by event.
    """
    # request.args reads URL query parameters (?event_id=3)
    # type=int automatically converts the string "3" to integer 3
    event_id = request.args.get('event_id', type=int)

    # Start building the query — will add a filter if event_id is provided
    query = RSVP.query.order_by(RSVP.created_at.desc())

    if event_id:
        # Add a WHERE event_id = ? clause to the query
        query = query.filter_by(event_id=event_id)

    rsvps  = query.all()
    # Also fetch all events for the filter dropdown in the template
    events = Event.query.order_by(Event.date.desc()).all()

    return render_template(
        'admin/rsvps.html',
        rsvps=rsvps,
        events=events,
        selected_event=event_id,  # So the template can highlight the active filter
    )

# ── Resource Routes ────────────────────────────────────────────────────────────

@bp.route('/api/recursos')
def api_recursos():
    """
    GET /api/recursos?lang=es

    Public API endpoint — returns all active resources as JSON.
    Called by the frontend recursos.html page to load resources dynamically.
    Accepts an optional ?lang= query parameter (defaults to 'es').
    """
    lang      = request.args.get('lang', 'es')
    recursos  = Resource.query.filter_by(active=True).order_by(Resource.category).all()
    return jsonify([r.to_dict(lang) for r in recursos])


@bp.route('/admin/recursos')
@admin_required
def admin_recursos():
    """
    GET /admin/recursos

    Admin list of all resources — shows both active and inactive.
    Leaders can see everything and manage visibility from here.
    """
    recursos = Resource.query.order_by(Resource.category, Resource.id).all()
    return render_template('admin/recursos.html', recursos=recursos)


@bp.route('/admin/recursos/new', methods=['GET', 'POST'])
@admin_required
def admin_recurso_new():
    """
    GET  /admin/recursos/new — Show the create resource form
    POST /admin/recursos/new — Process the form and save the new resource
    """
    if request.method == 'POST':
        f = request.form
        recurso = Resource(
            title_es = f['title_es'],
            title_en = f['title_en'],
            desc_es  = f['desc_es'],
            desc_en  = f['desc_en'],
            category = f['category'],
            # URL is optional — use None if left blank
            url      = f.get('url') or None,
            active   = True,
        )
        db.session.add(recurso)
        db.session.commit()
        return redirect(url_for('main.admin_recursos'))
    return render_template('admin/recurso_form.html', recurso=None)


@bp.route('/admin/recursos/<int:recurso_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_recurso_edit(recurso_id):
    """
    GET  /admin/recursos/<id>/edit — Show the edit form pre-filled with current values
    POST /admin/recursos/<id>/edit — Save the updated resource
    """
    recurso = Resource.query.get_or_404(recurso_id)
    if request.method == 'POST':
        f = request.form
        recurso.title_es = f['title_es']
        recurso.title_en = f['title_en']
        recurso.desc_es  = f['desc_es']
        recurso.desc_en  = f['desc_en']
        recurso.category = f['category']
        recurso.url      = f.get('url') or None
        recurso.active   = f.get('active') == 'active'
        db.session.commit()
        return redirect(url_for('main.admin_recursos'))
    return render_template('admin/recurso_form.html', recurso=recurso)


@bp.route('/admin/recursos/<int:recurso_id>/delete', methods=['POST'])
@admin_required
def admin_recurso_delete(recurso_id):
    """
    POST /admin/recursos/<id>/delete

    Deletes a resource permanently. No cascade needed since resources
    have no related models.
    """
    recurso = Resource.query.get_or_404(recurso_id)
    db.session.delete(recurso)
    db.session.commit()
    return redirect(url_for('main.admin_recursos'))

# ── Prayer Request Routes ──────────────────────────────────────────────────────

@bp.route('/api/prayer', methods=['POST'])
def api_prayer():
    """
    POST /api/prayer

    Accepts a prayer intention submitted through the public site form.
    Name is optional — members can submit anonymously.

    Expects a JSON body with: name (optional), intention (required)
    Returns JSON: { "status": "ok" }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    # Strip whitespace and default to empty string
    name      = (data.get('name', '') or '').strip()
    intention = (data.get('intention', '') or '').strip()

    # Intention is required — name is optional
    if not intention:
        return jsonify({'error': 'Intention is required'}), 422

    # Save to database — use None for name if left blank (anonymous)
    prayer = PrayerRequest(
        name      = name or None,
        intention = intention,
    )
    db.session.add(prayer)
    db.session.commit()

    return jsonify({'status': 'ok'})


@bp.route('/admin/prayer')
@admin_required
def admin_prayer():
    """
    GET /admin/prayer

    Admin list of all prayer requests — newest first.
    Leaders can see all intentions and mark them as prayed for.
    """
    requests = PrayerRequest.query.order_by(
        PrayerRequest.prayed_for.asc(),   # Unprayed first
        PrayerRequest.created_at.desc()   # Newest first within each group
    ).all()
    return render_template('admin/prayer.html', requests=requests)


@bp.route('/admin/prayer/<int:request_id>/toggle', methods=['POST'])
@admin_required
def admin_prayer_toggle(request_id):
    """
    POST /admin/prayer/<id>/toggle

    Toggles the 'prayed_for' status of a prayer request.
    Called when a leader clicks the checkmark button in the admin panel.
    """
    prayer = PrayerRequest.query.get_or_404(request_id)
    # Toggle — if it was prayed for, mark as not; if not, mark as prayed
    prayer.prayed_for = not prayer.prayed_for
    db.session.commit()
    return redirect(url_for('main.admin_prayer'))


@bp.route('/admin/prayer/<int:request_id>/delete', methods=['POST'])
@admin_required
def admin_prayer_delete(request_id):
    """
    POST /admin/prayer/<id>/delete

    Permanently deletes a prayer request.
    Leaders can clean up old or resolved intentions.
    """
    prayer = PrayerRequest.query.get_or_404(request_id)
    db.session.delete(prayer)
    db.session.commit()
    return redirect(url_for('main.admin_prayer'))

# ── Cron / Reminder Routes ─────────────────────────────────────────────────────

import os as _os
from .gmail_service import send_event_reminder as _send_reminder


def _check_cron_secret():
    """
    Verifies the Authorization header matches our CRON_SECRET env var.
    Prevents random people from triggering mass emails.
    """
    secret = _os.environ.get('CRON_SECRET', '')
    auth   = request.headers.get('Authorization', '')
    return auth in (secret, f'Bearer {secret}')


def _send_reminders_for_offset(day_offset: int, reminder_type: str) -> dict:
    """
    Finds events happening `day_offset` days from today and emails
    everyone who RSVPed.
      day_offset 1 = tomorrow (evening before reminder)
      day_offset 0 = today    (morning of reminder)
    """
    from datetime import date, timedelta

    target_date = date.today() + timedelta(days=day_offset)

    events = Event.query.filter_by(active=True, date=target_date).all()

    sent_count   = 0
    failed_count = 0

    for event in events:
        # Format date in Spanish e.g. "miércoles 15 de abril"
        day_names = {
            'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles',
            'Thursday': 'jueves', 'Friday': 'viernes',
            'Saturday': 'sábado', 'Sunday': 'domingo'
        }
        month_names = {
            'January': 'enero', 'February': 'febrero', 'March': 'marzo',
            'April': 'abril', 'May': 'mayo', 'June': 'junio',
            'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
            'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
        }
        # Spanish date e.g. "martes 7 de abril"
        day_name_es   = day_names.get(target_date.strftime('%A'), target_date.strftime('%A'))
        month_name_es = month_names.get(target_date.strftime('%B'), target_date.strftime('%B'))
        event_date_es = f"{day_name_es} {target_date.day} de {month_name_es}"

        # English date e.g. "Tuesday, April 7"
        event_date_en = target_date.strftime('%A, %B %-d') if hasattr(target_date, 'strftime') else str(target_date)

        for rsvp in event.rsvps:
            success = _send_reminder(
                name          = rsvp.name,
                email         = rsvp.email,
                event_title   = event.title_es,
                event_date_es = event_date_es,
                event_date_en = event_date_en,
                event_time    = event.time,
                reminder_type = reminder_type,
                location      = event.location,
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1

    return {
        'target_date':  str(target_date),
        'events_found': len(events),
        'sent':         sent_count,
        'failed':       failed_count,
    }


@bp.route('/cron/remind-day-before', methods=['POST'])
def cron_remind_day_before():
    """Called by cron-job.org every day at 6:00 PM Pacific."""
    if not _check_cron_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    result = _send_reminders_for_offset(day_offset=1, reminder_type='day_before')
    print(f'[cron] day-before reminders: {result}')
    return jsonify({'status': 'ok', **result})


@bp.route('/cron/remind-morning-of', methods=['POST'])
def cron_remind_morning_of():
    """Called by cron-job.org every day at 9:00 AM Pacific."""
    if not _check_cron_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    result = _send_reminders_for_offset(day_offset=0, reminder_type='morning_of')
    print(f'[cron] morning-of reminders: {result}')
    return jsonify({'status': 'ok', **result})


@bp.route('/admin/reminders', methods=['GET', 'POST'])
@admin_required
def admin_reminders():
    """Manual reminder trigger page — useful for testing."""
    message = None
    if request.method == 'POST':
        reminder_type = request.form.get('type', 'day_before')
        day_offset    = 1 if reminder_type == 'day_before' else 0
        result        = _send_reminders_for_offset(day_offset, reminder_type)
        if result['events_found'] == 0:
            message = {'type': 'info',
                       'text': f"No hay eventos {'mañana' if day_offset == 1 else 'hoy'}."}
        else:
            message = {'type': 'success',
                       'text': f"Enviados: {result['sent']} recordatorios. Fallidos: {result['failed']}."}
    return render_template('admin/reminders.html', message=message)