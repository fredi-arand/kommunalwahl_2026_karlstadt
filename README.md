# Karlstadt 2026 Local Election Dashboard

**Live Website:** https://kommunalwahl-2026-karlstadt.vercel.app

A lightweight, mobile-first dashboard for displaying live election results for the Karlstadt 2026 local elections.

## Architecture
- **Shared parser/fetch layer**: `election_source.py` contains the 2026 source URLs and parsing helpers.
- **Vercel API**: `api/results.py` is a serverless proxy endpoint (`/api/results`) that fetches the official source, parses it, and returns frontend-ready JSON.
- **Frontend**: `index.html` reads `/api/results`, caches the last payload in `localStorage`, auto-refreshes every 30 seconds, and shows a tappable sticky `Stand` line with detected data-change timestamps.

### Official Data Sources (2026)
- **Mayor election**: `.../buergermeisterwahl_gemeinde/ergebnisse.html`
- **Council election (parties + candidates)**: `.../gemeinderatswahl_gemeinde/ergebnisse.html`
- `presse.html` is no longer used for council candidate parsing.

## Setup Instructions

### Prerequisites
Make sure you have Python 3 installed. This project uses a virtual environment to manage dependencies.

1. **Initialize the Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

### Running the Application

Run the app with Vercel so the `/api/results` serverless endpoint is available:

1. **Install Vercel CLI (once)**:
    ```bash
    npm install -g vercel
    ```

2. **Run locally with Vercel dev server**:
    ```bash
    vercel dev
    ```

3. **Open the dashboard**:
    ```bash
    http://localhost:3000
    ```

## Development & Contribution
Please read `CONTRIBUTING.md` before making any changes. This project enforces `black` for formatting and `flake8` for linting.

### Testing
Run all tests:
```bash
pytest
```

## Vercel Deployment Notes

- Static hosting works with a built-in serverless endpoint at `/api/results` (file: `api/results.py`).
- No browser CORS access to `wahlen.osrz-akdb.de` is required, because the fetch happens server-side inside Vercel.
- API-side caching uses a 60-second TTL to avoid frequent upstream fetches from official election sources.
- Optional server-side persisted stale fallback is supported via Vercel KV (recommended for cold-start outage resilience).
- Shared HTTP caching headers are set to 60 seconds (`max-age=60`, `s-maxage=60`).
- Client-side caching is handled in the browser (`localStorage`) with automatic refresh polling every 30 seconds.
- Health/debug check is available via `/api/results?debug=1` (includes fetch duration and source metadata).

### Optional: Persisted stale fallback with Vercel KV

To survive cold starts while official pages are temporarily unreachable, configure Vercel KV and set:

- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `KV_SNAPSHOT_KEY` (optional, defaults to `kommunalwahl:karlstadt:results`)

Behavior:

- On successful refresh, `/api/results` writes the latest payload as a snapshot to KV.
- If upstream fetch fails and in-memory cache is empty, API serves the persisted KV snapshot with `stale: true`.
- If KV is not configured, the API keeps current behavior (runtime cache + client `localStorage` fallback).
