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
    Represents a single RSVP submitted through the public site.

    Split into first_name and last_name so leaders can identify
    members more easily — full name is reconstructed as needed
    by combining both fields.
    """
    __tablename__ = 'rsvps'

    id         = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name  = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(200), nullable=False)
    event_id   = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    first_time = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def name(self):
        """
        Reconstructs the full name from first and last name.
        Used everywhere the old 'name' field was used so we don't
        have to update every single template reference.
        """
        return f'{self.first_name} {self.last_name}'


class Resource(db.Model):
    """
    Represents a resource (prayer guide, reading, video link, etc.)
    that leaders can share with the group through the admin panel.

    Resources are bilingual — each has a Spanish and English title
    and description. The URL field links to external content.
    Category helps organize resources into groups on the public page.
    """
    __tablename__ = 'resources'

    id             = db.Column(db.Integer, primary_key=True)
    title_es       = db.Column(db.String(200), nullable=False)
    title_en       = db.Column(db.String(200), nullable=False)
    desc_es        = db.Column(db.Text, nullable=False)
    desc_en        = db.Column(db.Text, nullable=False)
    # Category groups resources e.g. 'oracion', 'lecturas', 'videos', 'otro'
    category       = db.Column(db.String(50), nullable=False, default='otro')
    # Optional URL linking to external content (YouTube, PDF, website, etc.)
    url            = db.Column(db.String(500), nullable=True)
    # Whether this resource is visible on the public page
    active         = db.Column(db.Boolean, nullable=False, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, lang='es'):
        """
        Returns a dictionary representation of the resource for the API.
        Uses Spanish or English fields based on the lang parameter.
        """
        return {
            'id':       self.id,
            'title':    self.title_es if lang == 'es' else self.title_en,
            'desc':     self.desc_es  if lang == 'es' else self.desc_en,
            'category': self.category,
            'url':      self.url,
        }