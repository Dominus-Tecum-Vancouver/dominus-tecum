"""
admin/sheets_service.py — Google Sheets Integration
=====================================================
This file logs every RSVP to a Google Sheet as a human-readable backup.

Why Google Sheets if we already have SQLite?
  - SQLite on Render resets on each deploy (free tier limitation).
    Google Sheets is permanent cloud storage.
  - Non-technical leaders can open the Sheet directly to see RSVPs
    without needing access to the admin panel.
  - Easy to export to Excel, share with the priest, etc.

The Sheet should have a tab named "RSVPs" with these column headers:
  Timestamp | Nombre | Email | Evento | Primera vez

We reuse the same OAuth2 token as gmail_service.py — one set of
credentials for both Gmail and Sheets.
"""

import json
import os
from datetime import datetime

import gspread  # A Python library that wraps the Google Sheets API
from google.oauth2.credentials import Credentials

# We need both scopes because the same token is used for
# both Gmail (sending emails) and Sheets (logging RSVPs).
# Both permissions were requested during the setup_gmail.py auth flow.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets',
]

# The Google Sheet ID is found in the sheet's URL:
# https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
# Store it in your .env as SHEETS_ID.
SHEETS_ID = os.environ.get('SHEETS_ID', '')


def get_sheet():
    """
    Authenticates with Google and returns the 'RSVPs' worksheet object.

    gspread is a friendly Python wrapper around the Google Sheets API.
    Once we have the worksheet object, we can call .append_row() to
    add a new row of data, just like typing into a spreadsheet.
    """
    # Load and reconstruct credentials from the env variable
    # (same token.json contents we use for Gmail)
    token_data = json.loads(os.environ['GMAIL_TOKEN'])
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Authorize gspread with our credentials
    client = gspread.authorize(creds)

    # Open the spreadsheet by its ID, then select the 'RSVPs' tab.
    # The sheet must exist and have a tab named exactly 'RSVPs'.
    sheet = client.open_by_key(SHEETS_ID)
    return sheet.worksheet('RSVPs')


def log_rsvp(name: str, email: str, event_title: str, first_time: bool):
    """
    Appends a new row to the RSVPs Google Sheet.

    This is called after every successful RSVP submission.
    If the Sheet is unavailable (network issue, expired token, etc.),
    we catch the error and print it — but we DON'T raise it, because:

      - SQLite is the source of truth (already saved before this runs)
      - We don't want a Sheets outage to break the RSVP flow for users

    Parameters:
      name        — person's name ("Alberto García")
      email       — person's email ("alberto@example.com")
      event_title — Spanish title of the event ("Noche de Convivencia")
      first_time  — whether this is their first group event
    """
    try:
        ws = get_sheet()

        # append_row() adds a new row at the bottom of the sheet.
        # We pass a list where each item maps to a column:
        # [Timestamp, Nombre, Email, Evento, Primera vez]
        ws.append_row([
            # UTC timestamp — consistent across timezones
            datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            name,
            email,
            event_title,
            # Human-readable bilingual string for the first_time boolean
            'Sí / Yes' if first_time else 'No',
        ])

    except Exception as e:
        # Non-fatal: log the error for debugging but don't crash.
        # The RSVP is safely in SQLite regardless.
        print(f'[sheets_service] Could not log to Sheets: {e}')
