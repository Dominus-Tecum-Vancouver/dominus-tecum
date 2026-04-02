# Dominus Tecum — Project Setup

## Stack
- **Frontend**: Static HTML hosted on GitHub Pages
- **Admin + API**: Flask on Render (free tier)
- **Emails**: Gmail API (group Gmail account)
- **Database**: SQLite (dev) / Postgres (prod optional)
- **RSVP log**: Google Sheets backup

---

## Local Development

### 1. Clone and set up Python env
```bash
git clone https://github.com/your-username/dominus-tecum.git
cd dominus-tecum/admin
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Set up Gmail API (one time)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project → Enable **Gmail API** and **Google Sheets API**
3. Create OAuth2 credentials → Desktop app → Download `credentials.json`
4. Run the auth script once to generate `token.json`:
```bash
python3 setup_gmail.py
# This opens a browser — log in with the group Gmail account
```
5. Copy the contents of `token.json` into your `.env` as `GMAIL_TOKEN`

### 4. Run locally
```bash
cd ..   # back to project root
python3 run.py
```
- Site API: http://localhost:5000/api/events
- Admin panel: http://localhost:5000/admin

---

## Deployment (Render)

1. Push to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Set build command: `pip install -r admin/requirements.txt`
4. Set start command: `gunicorn run:app`
5. Add environment variables in Render dashboard:
   - `FLASK_SECRET_KEY` — any long random string
   - `ADMIN_PASSWORD` — your chosen admin password
   - `GMAIL_TOKEN` — contents of token.json (one line)
   - `GMAIL_ADDRESS` — dominustecum@gmail.com
   - `SHEETS_ID` — your Google Sheet ID

---

## Frontend (GitHub Pages)

1. Edit `frontend/events.js` → set `API_BASE` to your Render URL
2. Push `frontend/` to your GitHub repo
3. Enable GitHub Pages in repo settings → set source to `frontend/` folder
4. Done — the site is live and pulling events from your Flask API

---

## Admin Panel

Visit `https://your-render-app.onrender.com/admin`

- **Dashboard** — see all events + recent RSVPs at a glance
- **Events** — create, edit, archive events (bilingual ES/EN)
- **RSVPs** — filter by event, see who's coming, spot first-timers

---

## File Structure

```
dominus-tecum/
├── frontend/
│   ├── index.html          ← the site (already built!)
│   └── events.js           ← fetches events + handles RSVPs
├── admin/
│   ├── __init__.py         ← Flask app factory
│   ├── models.py           ← Event + RSVP database models
│   ├── routes.py           ← API endpoints + admin routes
│   ├── gmail_service.py    ← Gmail API send helpers
│   ├── sheets_service.py   ← Google Sheets logging
│   ├── requirements.txt
│   ├── .env.example
│   └── templates/
│       └── admin/
│           ├── base.html
│           ├── login.html
│           ├── dashboard.html
│           ├── event_form.html
│           └── rsvps.html
├── run.py                  ← local dev entry point
└── .gitignore
```
