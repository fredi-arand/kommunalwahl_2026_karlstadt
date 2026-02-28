# Karlstadt 2026 Local Election Dashboard

A lightweight, mobile-first dashboard for displaying live election results for the Karlstadt 2026 local elections. The system comprises a Python data fetcher that scrapes the official AKDB/Votemanager election results and an Alpine.js/Tailwind CSS frontend for real-time visualization.

## Architecture
- **Backend**: `fetcher.py` polls the AKDB HTML page, uses BeautifulSoup to parse the complex tables containing candidate names and votes, and saves the extracted data as a clean JSON file (`live_data.json`).
- **Frontend**: `index.html` serves a responsive, mobile-first UI using Tailwind CSS for styling, Alpine.js for real-time reactivity (fuzzy search and party filters), and Chart.js for visualizing party strengths.

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
    Open a terminal, activate the environment, and run the fetcher script. This will update `live_data.json` every 60 seconds with the latest election results.
    ```bash
    source .venv/bin/activate
    python fetcher.py
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

For historical data structure details and fallback strategies involving the CSV files, refer to `Observations.md`.
