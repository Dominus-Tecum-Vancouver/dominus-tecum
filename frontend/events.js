/**
 * frontend/events.js — Live Event Loading + RSVP Submission
 * ===========================================================
 * This file does two things:
 *
 *  1. FETCHES events from the Flask API when the page loads
 *     and dynamically renders them into the events grid.
 *     This replaces any static placeholder cards in the HTML
 *     with real event data from the database.
 *
 *  2. HANDLES RSVP form submission — sends the form data to
 *     the Flask API as JSON instead of a plain HTML form POST.
 *     This lets us show a nice confirmation message without
 *     reloading the page.
 *
 * Include this file in index.html with:
 *   <script src="events.js" defer></script>
 *
 * The `defer` attribute makes it load after the HTML is parsed,
 * so document.querySelector() can find elements reliably.
 */

// ── Configuration ────────────────────────────────────────────────────────────

/**
 * The base URL of your deployed Flask admin app on Render.
 * Change this to your actual Render URL once deployed.
 * During local development, change it to 'http://localhost:5000'.
 */
const API_BASE = 'https://your-render-app.onrender.com';


// ── Event Loading ─────────────────────────────────────────────────────────────

/**
 * Fetches events from the API and renders them into the .events-grid element.
 *
 * @param {string} lang - 'es' for Spanish, 'en' for English
 *
 * This is an async function, which means it can use `await` to pause
 * execution while waiting for the network request to complete, without
 * blocking the rest of the page from loading.
 */
async function loadEvents(lang = 'es') {
  // Find the events grid container in the HTML.
  // If it doesn't exist on this page, exit early.
  const grid = document.querySelector('.events-grid');
  if (!grid) return;

  try {
    /**
     * fetch() makes an HTTP GET request to our API.
     * The backtick syntax (`...`) is a template literal — it lets us
     * embed variables inside strings using ${variable}.
     *
     * ?lang=es is a query parameter — the API uses it to decide whether
     * to return Spanish or English titles and descriptions.
     */
    const res = await fetch(`${API_BASE}/api/events?lang=${lang}`);

    // If the server returned an error status (4xx, 5xx), throw an error
    // so our catch block handles it gracefully.
    if (!res.ok) throw new Error('API error');

    // res.json() parses the JSON response body into a JavaScript array.
    // Each item in the array is an event object like:
    // { id: 1, title: "Noche de Convivencia", date: "11", month: "ABR", ... }
    const events = await res.json();

    // If there are no upcoming events, show a friendly message
    if (events.length === 0) {
      grid.innerHTML = `
        <div style="padding:40px;text-align:center;color:var(--muted);
                    font-family:'Crimson Text',serif;font-size:16px">
          ${lang === 'es' ? 'No hay eventos próximos.' : 'No upcoming events.'}
        </div>`;
      return;
    }

    /**
     * .map() transforms each event object into an HTML string.
     * .join('') concatenates all the strings together with no separator.
     * Setting grid.innerHTML replaces all existing content in the grid.
     *
     * This is sometimes called "rendering" — taking data and turning it
     * into visual HTML that the user can see and interact with.
     */
    grid.innerHTML = events.map(e => `
      <div class="event-card">

        <!-- Date display: large day number + month/time stacked -->
        <div class="event-date-row">
          <div class="event-day">${e.date}</div>
          <div class="event-meta">
            <span class="event-month">${e.month}</span>
            <span class="event-time">${e.time}</span>
          </div>
        </div>

        <!-- Event info -->
        <div class="event-title">${e.title}</div>
        <div class="event-desc">${e.desc}</div>

        <!-- Tag badge + RSVP button -->
        <div class="event-footer">
          <span class="event-tag tag-${e.tag}">
            ${tagLabel(e.tag, lang)}
          </span>
          <!--
            onclick calls openModal() with this event's ID and title.
            We pass the ID so the RSVP submission knows which event to attach to.
          -->
          <span class="event-rsvp" onclick="openModal(${e.id}, '${e.title}')">
            RSVP →
          </span>
        </div>

      </div>
    `).join('');

  } catch (err) {
    /**
     * If the API is unreachable (e.g. Render is spinning up from sleep,
     * or there's a network error), we silently fall back to whatever
     * static placeholder cards are already in the HTML.
     * The user still sees something, and we log the error for debugging.
     */
    console.warn('Could not load events from API — showing static fallback:', err);
  }
}


// ── Helper: Tag Labels ────────────────────────────────────────────────────────

/**
 * Returns the display label for an event tag in the correct language.
 *
 * @param {string} tag  - 'social', 'faith', or 'service'
 * @param {string} lang - 'es' or 'en'
 * @returns {string}    - e.g. 'FE' or 'FAITH'
 *
 * The ?. (optional chaining) and ?? (nullish coalescing) operators
 * handle cases where the tag value isn't in our labels object —
 * they prevent errors and fall back to the uppercase tag name.
 */
function tagLabel(tag, lang) {
  const labels = {
    social:  { es: 'SOCIAL',   en: 'SOCIAL'  },
    faith:   { es: 'FE',       en: 'FAITH'   },
    service: { es: 'SERVICIO', en: 'SERVICE' },
  };
  // labels[tag] looks up the tag, ?.[lang] gets the language, ?? falls back
  return labels[tag]?.[lang] ?? tag.toUpperCase();
}


// ── RSVP Modal ────────────────────────────────────────────────────────────────

/**
 * Stores which event the user clicked RSVP for.
 * We need this so the form submission knows which event to attach the RSVP to.
 * These are module-level variables so both openModal() and submitRSVP()
 * can access them.
 */
let currentEventId    = null;
let currentEventTitle = '';

/**
 * Opens the RSVP modal and records which event it's for.
 * Called by the "RSVP →" button on each event card.
 *
 * @param {number} eventId    - The database ID of the event
 * @param {string} eventTitle - The event's title (for display)
 */
function openModal(eventId, eventTitle) {
  currentEventId    = eventId;
  currentEventTitle = eventTitle;
  // classList.add() adds a CSS class to the element.
  // The 'open' class in index.html's CSS changes display from 'none' to 'flex',
  // making the modal visible.
  document.getElementById('overlay').classList.add('open');
}

/**
 * Closes the RSVP modal.
 * Called by the ✕ button and by clicking the backdrop.
 */
function closeModal() {
  document.getElementById('overlay').classList.remove('open');
}


// ── RSVP Submission ───────────────────────────────────────────────────────────

/**
 * Handles the RSVP form submission.
 * Called when the user clicks "CONFIRMAR ASISTENCIA".
 *
 * Instead of a traditional form POST (which reloads the page),
 * this uses the Fetch API to send the data as JSON in the background.
 * This is called an AJAX request or "fetch request."
 *
 * The flow:
 *  1. Read form values
 *  2. Validate that name is filled in
 *  3. POST the data to /api/rsvp as JSON
 *  4. Show a thank-you message on success
 *  5. Show an error message on failure
 */
async function submitRSVP() {
  // Read the current values from the form inputs by their HTML id
  const name      = document.getElementById('rsvp-name').value.trim();
  const email     = document.getElementById('rsvp-email').value.trim();
  // Check if the selected option text contains 'primera' (Spanish) or 'first' (English)
  // to determine if this person is attending for the first time
  const firstTime = document.getElementById('rsvp-first').value.includes('primera') ||
                    document.getElementById('rsvp-first').value.includes('first');

  // window.__lang is set by the language toggle in index.html's <script>
  // It tells us which language the user is currently viewing
  const lang = window.__lang || 'es';

  // Client-side validation — check name before sending to the server
  if (!name) {
    alert(lang === 'es'
      ? 'Por favor ingresa tu nombre.'
      : 'Please enter your name.');
    return; // Stop here — don't submit the form
  }

  try {
    /**
     * fetch() with method: 'POST' sends an HTTP POST request.
     *
     * headers tells the server we're sending JSON data.
     *
     * JSON.stringify() converts our JavaScript object into a JSON string:
     *   { name: "Alberto", email: "...', event_id: 1, first_time: false }
     *   becomes '{"name":"Alberto","email":"...","event_id":1,"first_time":false}'
     *
     * The Flask route reads this with request.get_json().
     */
    const res = await fetch(`${API_BASE}/api/rsvp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        email,
        event_id:   currentEventId,
        first_time: firstTime,
      }),
    });

    // Parse the JSON response from Flask
    const data = await res.json();

    // Close the modal first
    closeModal();

    // Show the thank-you message after a short delay (200ms)
    // so the modal close animation finishes first
    setTimeout(() => alert(
      lang === 'es'
        ? `¡Gracias, ${name}! Te esperamos. 🙏`
        : `Thanks, ${name}! We'll see you there. 🙏`
    ), 200);

  } catch (err) {
    // Network error or server crash — show a friendly error message.
    // The user can try again; nothing was lost since we failed before saving.
    console.error('RSVP submission failed:', err);
    alert(lang === 'es'
      ? 'Hubo un error. Por favor intenta de nuevo.'
      : 'Something went wrong. Please try again.');
  }
}


// ── Initialization ────────────────────────────────────────────────────────────

/**
 * DOMContentLoaded fires when the HTML is fully parsed but before
 * images and stylesheets finish loading. This is the right moment
 * to start fetching events because the grid element exists in the DOM.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Load events in the user's current language on page load
  loadEvents(window.__lang || 'es');
});

/**
 * Expose loadEvents globally so the language toggle button in index.html
 * can call window.__reloadEvents('en') when the user switches language.
 * This reloads the event cards with the new language without a page refresh.
 */
window.__reloadEvents = loadEvents;
