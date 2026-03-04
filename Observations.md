# Observations & Data Structure

## Overview
This document contains crucial information about the data structure of the Karlstadt local election results (from AKDB/Votemanager) to aid future development or fallback implementations.

## HTML vs CSV Correlation
While `fetcher.py` scrapes the main HTML page (`Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html`), there are downloadable CSVs (e.g., `Open-Data-Gemeinderatswahl-Bayern1103.csv`) that contain raw vote counts.

Archived CSVs are stored under `data/csv/<year>/`.

### Key Finding:
The order of parties and candidates in the CSV headers directly matches the order of parties and candidates in the HTML JSON `data-array`.

**Example Mapping (2020 Data):**
- **D5**: Represents the SPD party.
- **D5_1**: Stefan Rümmer
- **D5_2**: Martha Bolkart-Mühlrath
- **D5_3**: Marco Netrval
- **D5_4**: Anja Hartung
- **D5_5**: Frederick Arand
...and so forth up to `D5_20` (as there were only 20 candidates).
Note that typically, parties have 24 candidates.

### Fallback Strategy
If the HTML structure changes or scraping fails during election night, we use a persisted mapping in `data/mappings/council_csv_mapping_<year>.json`.

Workflow:
- Scrape council HTML once while available.
- Match party/candidate order to CSV `D*` columns and persist the mapping JSON.
- If council HTML later fails, populate `candidates_<year>.json` directly from CSV + mapping.

## Candidate Visibility in HTML
- The top-level `Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html` file contains `<abbr>` tags for all candidates (both elected and non-elected) across multiple tables, making it an excellent target for BeautifulSoup scraping to get all names and votes simultaneously.
- Be aware that some candidates might be listed multiple times (e.g., once under "gewählte Kandidaten" and once under "Ersatzpersonen" or their specific party lists). `fetcher.py` uses logic to avoid duplicating them in `live_data.json` by checking if the candidate's name already exists in the party's list.
