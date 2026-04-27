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
const API_BASE = 'https://dominus-tecum.onrender.com';


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

    updateCountdown(events);

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

        <!-- Custom location — only shown if different from default Cathedral Hall -->
        ${e.location ? `
        <div class="event-location">
          📍 ${e.location}
          ${e.location_url ? `<a href="${e.location_url}" target="_blank" 
            style="margin-left:6px;font-size:10px;color:var(--steel);text-decoration:none;
                   font-family:'Montserrat',sans-serif;letter-spacing:.08em">
            ${lang === 'es' ? 'VER MAPA' : 'VIEW MAP'} →
          </a>` : ''}
        </div>` : ''}

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
    social: { es: 'SOCIAL', en: 'SOCIAL' },
    faith: { es: 'FE', en: 'FAITH' },
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
let currentEventId = null;
let currentEventTitle = '';

/**
 * Opens the RSVP modal and records which event it's for.
 * Called by the "RSVP →" button on each event card.
 *
 * @param {number} eventId    - The database ID of the event
 * @param {string} eventTitle - The event's title (for display)
 */
function openModal(eventId, eventTitle) {
  currentEventId = eventId;
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
  const firstName = document.getElementById('rsvp-first-name').value.trim();
  const lastName = document.getElementById('rsvp-last-name').value.trim();
  const email = document.getElementById('rsvp-email').value.trim();

  // Check if the selected option text contains 'primera' (Spanish) or 'first' (English)
  // to determine if this person is attending for the first time
  const firstTime = document.getElementById('rsvp-first').value.includes('primera') ||
    document.getElementById('rsvp-first').value.includes('first');

  // window.__lang is set by the language toggle in index.html's <script>
  // It tells us which language the user is currently viewing
  const lang = window.__lang || 'es';

  // Client-side validation — check both name fields before sending to the server
  if (!firstName || !lastName) {
    alert(lang === 'es'
      ? 'Por favor ingresa tu nombre y apellido.'
      : 'Please enter your first and last name.');
    return; // Stop here — don't submit the form
  }

  try {
    /**
     * fetch() with method: 'POST' sends an HTTP POST request.
     *
     * headers tells the server we're sending JSON data.
     *
     * JSON.stringify() converts our JavaScript object into a JSON string:
     *   { first_name: "Alberto", last_name: "Urquidi", email: "...", ... }
     *
     * The Flask route reads this with request.get_json().
     */
    const res = await fetch(`${API_BASE}/api/rsvp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
        event_id: currentEventId,
        first_time: firstTime,
      }),
    });

    // Parse the JSON response from Flask
    const data = await res.json();

    // Close the modal first
    closeModal();
    if (data.status === 'duplicate') {
      showDuplicate(firstName, lang);
    } else {
      showSuccess(firstName, lang);
    }

  } catch (err) {
    // Network error or server crash — show a friendly error message.
    // The user can try again; nothing was lost since we failed before saving.
    console.error('RSVP submission failed:', err);
    alert(lang === 'es'
      ? 'Hubo un error. Por favor intenta de nuevo.'
      : 'Something went wrong. Please try again.');
  }
}

async function updateCountdown(events) {
  // Find the countdown container in the DOM
  // If it doesn't exist on this page, exit early
  const container = document.getElementById('countdown-container');
  if (!container) return;

  // Find the next upcoming event from the API results
  // We look for the first event whose date is today or in the future
  const now = new Date();

  // Month abbreviations from the API map to JavaScript month indices (0-based)
  const months = {
    'JAN': 0, 'FEB': 1, 'MAR': 2, 'APR': 3, 'MAY': 4, 'JUN': 5,
    'JUL': 6, 'AUG': 7, 'SEP': 8, 'OCT': 9, 'NOV': 10, 'DEC': 11
  };

  // Build a Date object for each event and find the first one that hasn't passed
  const upcoming = events.find(e => {
    const eventDate = new Date(
      now.getFullYear(),
      months[e.month],
      parseInt(e.date),
      19, 0, 0  // Events start at 7:00 PM
    );
    return eventDate >= now;
  });

  // If no upcoming events exist, hide the countdown entirely
  if (!upcoming) {
    container.style.display = 'none';
    return;
  }

  // Build the full Date object for the next event at 7:00 PM
  const eventDate = new Date(
    now.getFullYear(),
    months[upcoming.month],
    parseInt(upcoming.date),
    19, 0, 0
  );

  // If the calculated date is somehow in the past (edge case), try next year
  if (eventDate < now) {
    eventDate.setFullYear(now.getFullYear() + 1);
  }

  /**
   * tick() runs every second via setInterval below.
   * It calculates the remaining time by subtracting the current time
   * from the event time, then breaks it down into days/hours/minutes/seconds.
   *
   * Math breakdown:
   *   diff = milliseconds remaining
   *   days    = whole days remaining
   *   hours   = remaining hours after removing whole days
   *   minutes = remaining minutes after removing whole hours
   *   seconds = remaining seconds after removing whole minutes
   */
  function tick() {
    const diff = eventDate - new Date();

    // If the countdown has reached zero, hide the container
    if (diff <= 0) {
      container.style.display = 'none';
      return;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    // padStart(2,'0') ensures single digits show as e.g. "05" instead of "5"
    document.getElementById('cd-days').textContent = String(days).padStart(2, '0');
    document.getElementById('cd-hours').textContent = String(hours).padStart(2, '0');
    document.getElementById('cd-minutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('cd-seconds').textContent = String(seconds).padStart(2, '0');

    // Update labels and event title based on current language
    const lang = window.__lang || 'es';
    document.getElementById('cd-label-days').textContent = lang === 'es' ? 'DÍAS' : 'DAYS';
    document.getElementById('cd-label-hours').textContent = lang === 'es' ? 'HORAS' : 'HOURS';
    document.getElementById('cd-label-minutes').textContent = 'MIN';
    document.getElementById('cd-label-seconds').textContent = lang === 'es' ? 'SEG' : 'SEC';

    // Show the event title in the current language
    // Falls back to Spanish title if English title isn't available
    document.getElementById('cd-event-title').textContent = lang === 'es'
      ? upcoming.title
      : (upcoming.title_en || upcoming.title);
  }

  // Run immediately so there's no blank flash on page load
  tick();

  // Then update every second
  setInterval(tick, 1000);

  // Expose tick globally so setLang() can trigger a label refresh
  // when the user switches language without waiting for the next second
  window.__tickCountdown = tick;
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

function showSuccess(name, lang) {
  const msg = document.getElementById('success-msg');
  const text = document.getElementById('success-text');
  text.textContent = lang === 'es'
    ? `¡Gracias, ${name}! Te esperamos pronto. 🙏`
    : `Thanks, ${name}! We'll see you soon. 🙏`;
  msg.style.display = 'flex';
  setTimeout(() => msg.style.display = 'none', 5000);
}

function showDuplicate(name, lang) {
  const msg = document.getElementById('success-msg');
  const text = document.getElementById('success-text');
  text.textContent = lang === 'es'
    ? `¡${name}, ya tienes un lugar reservado para este evento! 🙏`
    : `${name}, you already have a spot for this event! 🙏`;
  msg.style.background = 'var(--burgundy)';
  msg.style.display = 'flex';
  setTimeout(() => {
    msg.style.display = 'none';
    msg.style.background = 'var(--steel)';
  }, 5000);
}

/**
 * Expose loadEvents globally so the language toggle button in index.html
 * can call window.__reloadEvents('en') when the user switches language.
 * This reloads the event cards with the new language without a page refresh.
 */
window.__reloadEvents = loadEvents;
