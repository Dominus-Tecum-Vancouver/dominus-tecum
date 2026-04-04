"""
admin/models.py — Database Models
===================================
This file defines the shape of our database using SQLAlchemy models.
Each class here becomes a table in SQLite. Each class attribute that
uses db.Column() becomes a column in that table.

Think of this like designing a spreadsheet:
  - Event is one sheet with columns for title, date, time, etc.
  - RSVP is another sheet with columns for name, email, which event, etc.

SQLAlchemy handles writing the actual SQL — we just work with Python objects.
"""

from datetime import datetime
from . import db  # Import the db object we created in __init__.py


class Event(db.Model):
    """
    Represents a single group event (Noche de Convivencia, Retiro, etc.)

    Each row in the 'events' table is one event. We store the title and
    description in both Spanish and English so the frontend can serve
    the right language without extra API calls.
    """

    # __tablename__ sets the actual SQL table name.
    # Without this, SQLAlchemy would just use the class name in lowercase.
    __tablename__ = 'events'

    # Primary key — SQLite auto-increments this for each new event.
    # Every table needs a unique identifier column.
    id = db.Column(db.Integer, primary_key=True)

    # Bilingual title — we store both so the API can return the right one.
    # nullable=False means this field is required (can't save an event without it).
    # String(120) limits to 120 characters, which is plenty for an event name.
    title_es = db.Column(db.String(120), nullable=False)  # Spanish title
    title_en = db.Column(db.String(120), nullable=False)  # English title

    # Bilingual descriptions — Text allows longer content than String.
    desc_es = db.Column(db.Text, nullable=False)  # Spanish description
    desc_en = db.Column(db.Text, nullable=False)  # English description

    # The date the event takes place. Stored as a proper Date type,
    # not a string, so we can sort and compare dates reliably.
    date = db.Column(db.Date, nullable=False)

    # Time stored as a string like "7:00 PM" — simple and human-readable.
    # We don't need a full DateTime here since the date is separate.
    time = db.Column(db.String(10), nullable=False)

    # Tag controls which color badge appears on the frontend.
    # Only three valid values: 'social', 'faith', or 'service'.
    tag = db.Column(db.String(20), nullable=False)

    # Active flag lets us hide old events without deleting them.
    # Default is True (visible). Set to False to archive.
    active = db.Column(db.Boolean, default=True)

    # Automatically records when the event was created.
    # datetime.utcnow (without parentheses!) means SQLAlchemy calls
    # this function at insert time, not when the class is defined.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # This defines a relationship between Event and RSVP.
    # It lets us write event.rsvps to get all RSVPs for that event,
    # and rsvp.event to get the event an RSVP belongs to (backref).
    # lazy=True means RSVPs are only loaded from the DB when accessed,
    # not eagerly fetched every time we load an event.
    rsvps = db.relationship('RSVP', backref='event', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, lang='es'):
        """
        Converts this Event object into a plain Python dictionary
        that can be serialized to JSON and sent to the frontend.

        The lang parameter controls which language to use for
        title and description. Everything else is language-neutral.

        Example output:
            {
                'id': 1,
                'title': 'Noche de Convivencia',
                'desc': 'Una noche relajada...',
                'date': '11',
                'month': 'ABR',
                'time': '6:30 PM',
                'tag': 'social'
            }
        """
        return {
            'id':    self.id,
            # Pick Spanish or English based on the lang argument
            'title': self.title_es if lang == 'es' else self.title_en,
            'desc':  self.desc_es  if lang == 'es' else self.desc_en,
            # strftime formats the date object as a string.
            # '%-d' gives just the day number without leading zeros (e.g. "11" not "011")
            'date':  str(self.date.day),
            # '%b' gives abbreviated month name ("Apr") — .upper() makes it "APR"
            'month': self.date.strftime('%b').upper(),
            'time':  self.time,
            'tag':   self.tag,
        }


class RSVP(db.Model):
    """
    Represents one person's RSVP for one event.

    Each row is one confirmation. If the same person RSVPs to three
    events, there will be three rows with their name and email.
    """

    __tablename__ = 'rsvps'

    # Auto-incrementing unique ID for each RSVP
    id = db.Column(db.Integer, primary_key=True)

    # The person's name — required
    name = db.Column(db.String(120), nullable=False)

    # Their email — required (used to send confirmation)
    email = db.Column(db.String(120), nullable=False)

    # Foreign key — links this RSVP to an event.
    # db.ForeignKey('events.id') means this must match an id in the events table.
    # nullable=False means every RSVP must belong to an event.
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    # Whether this is their first time attending any group event.
    # Useful for leaders to give extra attention to newcomers.
    # Defaults to False (not a first-timer).
    first_time = db.Column(db.Boolean, default=False)

    # Automatically records when the RSVP was submitted.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Converts this RSVP to a dictionary for JSON responses
        or the admin dashboard display.
        """
        return {
            'id':         self.id,
            'name':       self.name,
            'email':      self.email,
            'event_id':   self.event_id,
            'first_time': self.first_time,
            # Format the timestamp as a readable string for display
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }
