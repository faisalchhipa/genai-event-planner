# Event Planning Assistant (INR)

A zero-dependency Python (standard library only) application designed to plan **weddings**, **birthdays**, and **community events** in the Indian market with **INR (₹)** budgeting.

The system combines **deterministic business logic** (validation, tiered budget calculations, countdown timelines, and security vendor checks) with a **hardened Gemini LLM REST integration** for personalized ideas, wrapped in a high-security standard library HTTP server and an accessible, mobile-first UI.

---

## 1. Vertical & Market Context

The application targets event planners, families, and community organizers in India coordinating three core categories:
- **Weddings (Shaadi / Reception)**: High-scale celebrations involving multi-tier venue rentals, catering, sangeet/mehendi entertainment, and extensive decor.
- **Birthdays**: Milestone and children's parties focusing on thematic staging, cakes, family entertainment, and return favors.
- **Community Events (Melas / Society Festivals / Public Drives)**: Neighborhood gatherings requiring municipal and police permissions, PA audio setups, crowd management, and emergency provisions.

All budgeting is performed strictly in **Indian National Rupees (INR ₹)**.

---

## 2. Architecture & Approach

- **Zero Third-Party Dependencies (Python stdlib only)**: Uses only built-in modules (`http.server`, `urllib.request`, `json`, `hashlib`, `datetime`, `unittest`, etc.). No `requests`, `fastapi`, `flask`, or `pydantic` required.
- **Deterministic Core First**: All critical financial, milestone, and vendor decisions are calculated using deterministic rules with unit test coverage across boundaries.
- **Enrichment via AI with Graceful Fallback**: Gemini LLM generates 5 creative, contextual ideas. If the API key is missing, network fails, rate limits trigger, or response format is invalid, the engine falls back seamlessly to rule-based recommendations.
- **Defense-in-Depth Security**:
  - **Prompt Isolation**: Untrusted user preferences are enclosed inside `<prefs>` tags, disarmed of injection tokens, and accompanied by explicit instructions directing the model to treat the content as data only.
  - **Network & Server Hardening**: Request body size limited to 64 KB, per-IP sliding window rate limiting (respecting `X-Forwarded-For` for reverse proxies/Cloud Run), strictly whitelisted static file routes, Content Security Policy (CSP), and generic error responses without stack trace leakage.
  - **Frontend XSS Immunity**: The frontend JavaScript uses `textContent` exclusively for DOM manipulation—zero use of `innerHTML`, `outerHTML`, or `insertAdjacentHTML`.
- **Accessibility by Design (WCAG 2.1 AA)**: Skip links, explicit label associations, live region announcements (`aria-live="polite"`), high-contrast focus rings (`:focus-visible`), AA color contrast ratios (≥ 4.5:1), and mobile touch targets (≥ 44px).

---

## 3. How It Works

### Deterministic Engine (`planner/logic.py`)
1. **Input Validation**:
   - `event_type`: Normalized to `weddings`, `birthdays`, or `community events`.
   - `guests`: Validated in range `1` to `5,000`.
   - `budget`: Positive float in INR (upper bound sanity check).
   - `event_date`: Must be strictly in the future relative to the reference date.
   - `preferences`: String capped at 300 characters.
2. **Budget Breakdown & Per-Guest Tiers**:
   - Computes `budget_per_guest = budget / guests`.
   - Evaluates tier thresholds:
     - **Weddings**: Tight (< ₹1,500), Comfortable (₹1,500 – ₹4,000), Premium (> ₹4,000).
     - **Birthdays**: Tight (< ₹500), Comfortable (₹500 – ₹1,500), Premium (> ₹1,500).
     - **Community Events**: Tight (< ₹250), Comfortable (₹250 – ₹800), Premium (> ₹800).
   - **Tight Tier Rule**: Decor is intentionally trimmed down to 5% and the contingency buffer is grown to 12% to protect against unexpected cost overruns.
3. **Countdown Timeline**:
   - Milestones are calculated backwards from the event date (T-180, T-120, T-90, T-60, T-30, T-14, T-7, T-3, T-0).
   - Tasks whose target date precedes the current date are flagged as `is_past_due = True`.
   - Each task includes an auto-generated **"Add to Google Calendar"** link.
4. **Vendor Checklist**:
   - Base vendors tailored to the event type.
   - **Large Gathering Rule (200+ Guests)**: Automatically injects mandatory **Dedicated Security Personnel & Bouncers** (crowd control, perimeter monitoring) and **Valet & Parking Marshals** (traffic flow, parking bays).
   - Each vendor row includes a direct **Google Maps Search** link.

### AI Idea Engine (`planner/ai.py`)
1. **REST Integration**: Calls Gemini via standard library `urllib.request`.
2. **Prompt Isolation**: Wraps user preferences inside `<prefs>` tags, disarming breakout attempts and instructing the model that `<prefs>` is untrusted data.
3. **Schema Validation & Capping**: Requires JSON matching `{"ideas": [{"title", "description", "category"}]}`, caps string lengths, and returns at most 5 ideas.
4. **Deterministic In-Memory Caching**: Hashes input parameters (`SHA-256`) to avoid repeated network calls for identical planning queries.
5. **Rule-Based Fallback**: Returns 5 curated recommendations if the API is unavailable or unconfigured.

### Hardened HTTP Server & UI (`server.py`, `static/`)
1. **POST /api/plan**: Reads JSON body up to 64 KB, validates client rate limits via `X-Forwarded-For`, computes the plan, and returns JSON.
2. **Static Whitelisting**: Only serves `/`, `/index.html`, `/static/style.css`, `/static/app.js`, and `/favicon.ico`. Directory traversal attempts are rejected.
3. **Security Headers**: Sends CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.

---

## 4. Run, Test & Deploy Commands

### Prerequisites
- Python 3.10+ (Standard library only; no virtual environment or `pip install` required).

### Local Execution
```bash
# Optional: Set your Gemini API key in environment or .env
cp .env.example .env

# Start server (default: port 8080)
python server.py
```
Open your browser at `http://localhost:8080`.

### Running Unit & Integration Tests
The project contains 35 unit and integration tests covering logic boundaries, budget tiers, prompt isolation, JSON schema validation, rate limiting, and security headers:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test modules
python -m unittest tests/test_logic.py
python -m unittest tests/test_ai.py
python -m unittest tests/test_server.py
```

### Docker Container
Build and run the lightweight container:

```bash
# Build Docker image
docker build -t event-planner .

# Run container locally
docker run -p 8080:8080 -e GEMINI_API_KEY="your_api_key_here" event-planner
```

### Google Cloud Run Deployment
Deploy directly using Google Cloud SDK:

```bash
# Deploy to Google Cloud Run
gcloud run deploy event-planner-service \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="your_gemini_api_key"
```

---

## 5. Assumptions

1. **Currency & Localization**: All currency inputs and allocations are assumed to be in Indian National Rupees (INR ₹) following Indian event traditions and market pricing benchmarks.
2. **Guest Limits**: Guest capacity is constrained between 1 and 5,000. Events exceeding 5,000 typically operate under public stadium/parade regulations requiring specialized civic authority clearance.
3. **Event Timing**: Events must be scheduled strictly in the future (tomorrow or later). Timeline milestones occurring before the current date are flagged as past-due.
4. **Proxy Networking**: Behind reverse proxies like Google Cloud Run, the client's actual IP address is forwarded in the first segment of the `X-Forwarded-For` HTTP header.
5. **AI Optionality**: An active internet connection and Gemini API key are optional. The application remains fully functional offline using rule-based recommendation fallbacks.
