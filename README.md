# Karlstadt 2026 Local Election Dashboard

**Live Website:** https://kommunalwahl-2026-karlstadt.vercel.app

A lightweight, mobile-first dashboard for displaying live election results for the Karlstadt 2026 local elections. The system uses a small Python downloader for CSV collection and a static frontend for visualization.

## Architecture
- **Backend**: `download_csv.py` contains the complete 2026 scraping/downloading logic. `fetcher.py` is a compatibility CLI wrapper around it.
- **Frontend**: `index.html` reads `meta.json`, `candidates.json`, and `mayor.json` (JSON-first, 2026-only). Tailwind CSS is used for styling, Alpine.js for reactivity, and Chart.js for visualizations.

## Setup Instructions

### Prerequisites
Make sure you have Python 3 installed. This project uses a virtual environment to manage dependencies.

1. **Initialize the Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

### Running the Application (LAN Serving for the Pub)

To serve the dashboard to guests in the pub via the local Wi-Fi, follow these steps:

1. **Start the Data Fetcher**:
    Open a terminal, activate the environment, and run the 2026 downloader.
    ```bash
    source .venv/bin/activate
    python download_csv.py --attempts 1
    ```

    For election night polling (wait until council CSV becomes available):
    ```bash
    python download_csv.py --attempts 60 --interval 30 --timeout 20
    ```

    If you prefer compatibility with old commands, this also works:
    ```bash
    python fetcher.py --attempts 60 --interval 30 --timeout 20
    ```

2. **Start the Local Web Server**:
    Open a *second* terminal window in the project directory, and start Python's built-in HTTP server on all interfaces (`0.0.0.0`) so it's accessible over the network.
    ```bash
    python -m http.server 8000 --bind 0.0.0.0
    ```

3. **Access the Dashboard**:
    - **On the host laptop**: Open a web browser and go to `http://localhost:8000`
    - **For guests in the pub**: Find your laptop's local IP address (e.g., `192.168.178.50`). Guests can connect their smartphones to the same Wi-Fi network and navigate to `http://192.168.178.50:8000` to view the live results.

## Development & Contribution
Please read `CONTRIBUTING.md` before making any changes. This project enforces `black` for formatting and `flake8` for linting.

### Testing
Run all tests:
```bash
pytest
```

### Smoke Test
Quick end-to-end check (downloader + generated files):
```bash
python download_csv.py --attempts 1 --timeout 20 && ls -1 meta.json mayor.json candidates.json data/csv/Stimmenanteile_tabellarisch.csv
```

## 2026 CSV Automation (`wahlen.osrz-akdb.de`)

For the 2026 site, mayor CSV export is generated from the displayed table and council CSVs are listed on the press page. You can automate both with:

```bash
python download_csv.py --attempts 60 --interval 30
```

- Writes files into `data/csv/` by default.
- Always refreshes the mayor table CSV (`Stimmenanteile_tabellarisch.csv`).
- Polls for council CSV publication (e.g. `gesamtergebnis.csv`) and saves it as soon as it is publicly reachable.
- Also writes frontend JSON files (`meta.json`, `candidates.json`, `mayor.json`) in the project root by default (`--json-dir` to change).
