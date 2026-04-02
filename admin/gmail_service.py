"""
admin/gmail_service.py — Gmail API Integration
================================================
This file handles all email sending for the app using the Gmail API.

Why use the Gmail API instead of simple SMTP?
  - More reliable delivery (Google's infrastructure)
  - Emails come FROM the group's actual Gmail address
  - No need to enable "Less secure app access" or manage SMTP passwords
  - The same OAuth2 credentials also work for Google Sheets

How Gmail API authentication works:
  1. You run setup_gmail.py once — it opens a browser to log in with
     the group Gmail account and generates a token.json file
  2. token.json contains an access token (short-lived) and a refresh
     token (long-lived) — we store it in the GMAIL_TOKEN env variable
  3. Every time we send an email, we load these credentials and
     auto-refresh the access token if it's expired
  4. The Gmail API then accepts our request and sends the email
"""

import base64   # Used to encode email content for the API
import json     # Used to parse the token stored in env vars
import os       # Used to read environment variables
from email.mime.multipart import MIMEMultipart  # Builds multi-part email (HTML + text)
from email.mime.text import MIMEText            # Builds the HTML part of the email

from google.oauth2.credentials import Credentials          # Loads OAuth2 token
from google.auth.transport.requests import Request         # Used to refresh expired tokens
from googleapiclient.discovery import build                # Builds the Gmail API client

# SCOPES define what permissions we're requesting from Google.
# 'gmail.send' means we can only SEND emails — we can't read the inbox,
# delete messages, or do anything else. Least-privilege is good practice.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Read the group's Gmail address from environment variables.
# os.environ.get() returns the second argument if the key doesn't exist,
# so this won't crash if GMAIL_ADDRESS isn't set yet during development.
GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS', 'dominustecum@gmail.com')


def get_gmail_service():
    """
    Builds and returns an authenticated Gmail API client.

    This is called every time we want to send an email. It:
      1. Loads the OAuth2 token from the environment variable
      2. Checks if the access token has expired
      3. Refreshes it automatically if needed
      4. Returns a ready-to-use Gmail API service object

    The service object is what we call .send() on to actually send emails.
    """
    # GMAIL_TOKEN is the contents of token.json stored as a JSON string
    # in your environment variables. json.loads() parses it back into a dict.
    token_data = json.loads(os.environ['GMAIL_TOKEN'])

    # Credentials.from_authorized_user_info() reconstructs the credentials
    # object from the dictionary. This includes both the access token
    # (used to make API calls) and the refresh token (used to get a new
    # access token when the current one expires after ~1 hour).
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Access tokens expire after about 1 hour. If ours has expired
    # and we have a refresh token, automatically get a new access token.
    # This means the app never needs manual re-authorization after setup.
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # build() creates the API client for the 'gmail' service, version 'v1'.
    # Think of this like importing a library tailored specifically for
    # interacting with Gmail's API endpoints.
    return build('gmail', 'v1', credentials=creds)


def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Core email sending function — used by all the other functions below.

    Builds an RFC 2822 email message, encodes it in base64 (which is what
    the Gmail API expects), and sends it via the group Gmail account.

    Parameters:
      to        — recipient email address (e.g. "alberto@example.com")
      subject   — email subject line
      html_body — HTML string for the email body

    Returns True on success, False if sending failed (so the caller
    can decide whether to retry or log the failure).
    """
    try:
        # Get a fresh authenticated Gmail API client
        service = get_gmail_service()

        # MIMEMultipart('alternative') creates a container for the email.
        # 'alternative' means we're providing different versions of the
        # content (we're using just HTML here, but could add plain text too).
        msg = MIMEMultipart('alternative')
        msg['To']      = to
        msg['From']    = f'Dominus Tecum <{GMAIL_ADDRESS}>'  # Display name + address
        msg['Subject'] = subject

        # Attach the HTML content to the message.
        # MIMEText wraps the HTML string with the correct content-type headers.
        # 'utf-8' ensures accented characters (á, é, ñ) are handled correctly.
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # The Gmail API requires the email to be base64url-encoded.
        # msg.as_bytes() serializes the full MIME message to bytes,
        # then base64.urlsafe_b64encode() encodes it, and .decode()
        # converts the bytes back to a string for JSON serialization.
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        # Make the API call to send the email.
        # userId='me' means "the authenticated user" (our group Gmail).
        # .execute() actually sends the HTTP request to Google's API.
        service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()

        return True  # Email sent successfully

    except Exception as e:
        # Catch any error (network issues, API errors, expired token, etc.)
        # and print it for debugging, but don't crash the whole app.
        # The RSVP was already saved to the database, so the data isn't lost.
        print(f'[gmail_service] Failed to send email to {to}: {e}')
        return False


def send_rsvp_confirmation(name: str, email: str, event_title: str) -> bool:
    """
    Sends a branded confirmation email to the person who just RSVPed.

    This is the email the attendee receives — it confirms their spot,
    shows the event name, and includes the cathedral address.
    Both Spanish and English are included since the group is bilingual.

    Uses an f-string for the HTML body, which lets us embed Python
    variables directly inside the string using {curly braces}.
    """
    subject = f'¡Te esperamos, {name}! / See you there!'

    # The HTML email template — inline styles are used because
    # many email clients strip out <style> tags and external CSS.
    html = f"""
    <div style="font-family:'Georgia',serif;max-width:520px;margin:0 auto;color:#2A1810">

      <!-- Header banner with brand colors -->
      <div style="background:#5B8A9A;padding:28px 32px;text-align:center">
        <h1 style="color:#F2E8D5;font-size:22px;letter-spacing:3px;margin:0">
          DOMINUS TECUM
        </h1>
        <p style="color:rgba(255,255,255,0.65);font-size:13px;margin:6px 0 0;font-style:italic">
          Holy Rosary Cathedral · Vancouver
        </p>
      </div>

      <!-- Email body -->
      <div style="padding:32px;background:#FAF5EC">
        <!-- {name} is replaced with the actual person's name at send time -->
        <p style="font-size:18px;margin:0 0 12px">Hola {name} / Hi {name},</p>
        <p style="color:#5C3D2E;line-height:1.8">
          ¡Confirmamos tu asistencia a <strong>{event_title}</strong>!
          Te esperamos con mucho gusto.<br><br>
          We've confirmed your RSVP for <strong>{event_title}</strong>.
          We look forward to seeing you!
        </p>

        <!-- Location box -->
        <div style="margin:24px 0;padding:16px;background:#EBF4F7;
                    border-left:3px solid #7A1528;border-radius:4px">
          <p style="margin:0;font-size:13px;color:#2A5A6A">
            📍 Holy Rosary Cathedral<br>
            646 Richards St, Vancouver BC
          </p>
        </div>

        <!-- Contact info -->
        <p style="color:#7A6555;font-size:13px">
          ¿Preguntas? / Questions?<br>
          <a href="mailto:{GMAIL_ADDRESS}" style="color:#5B8A9A">{GMAIL_ADDRESS}</a>
        </p>
      </div>

      <!-- Footer -->
      <div style="background:#EDE3CF;padding:14px;text-align:center">
        <p style="margin:0;font-size:10px;letter-spacing:2px;color:#A08B72">
          © DOMINUS TECUM · HOLY ROSARY CATHEDRAL · VANCOUVER
        </p>
      </div>

    </div>
    """
    # send_email() handles the actual API call and returns True/False
    return send_email(email, subject, html)


def send_rsvp_notification(name: str, email: str,
                           event_title: str, first_time: bool) -> bool:
    """
    Sends a brief notification to the group Gmail inbox whenever
    someone RSVPs, so leaders know who's coming without checking
    the admin dashboard.

    If the person is attending for the first time, a star emoji
    is added so it stands out — helps leaders make sure newcomers
    feel especially welcomed.
    """
    # Build the "first time" flag string — empty if they're a regular
    first_tag = ' 🌟 <strong>Primera vez / First time!</strong>' if first_time else ''

    subject = f'Nueva RSVP: {name} — {event_title}'

    # Simple table layout — easy to scan in the Gmail inbox
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#7A1528">Nueva RSVP / New RSVP</h2>
      <table style="border-collapse:collapse;width:100%">
        <tr>
          <td style="padding:6px 12px;background:#EBF4F7;font-weight:600">Nombre</td>
          <td style="padding:6px 12px">{name}{first_tag}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;background:#EBF4F7;font-weight:600">Email</td>
          <td style="padding:6px 12px">{email}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;background:#EBF4F7;font-weight:600">Evento</td>
          <td style="padding:6px 12px">{event_title}</td>
        </tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:16px">
        Ver todas las RSVPs en el panel de administración.
      </p>
    </div>
    """
    # Send TO the group Gmail — leaders will see this in their inbox
    return send_email(GMAIL_ADDRESS, subject, html)
