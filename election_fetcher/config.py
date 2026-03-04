from pathlib import Path

# fmt: off
ELECTION_URL_2020 = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
MAYOR_URL_2020 = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Buergermeisterwahl_Bayern_108_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
ELECTION_URL_2026 = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2026-03-08/09677148/html5/Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
MAYOR_URL_2026 = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2026-03-08/09677148/html5/Buergermeisterwahl_Bayern_108_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501

COUNCIL_CSV_URLS_2020 = (
    "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Open-Data-Gemeinderatswahl-Bayern1103.csv",  # noqa: E501
    "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Open-Data-Gemeinderatswahl-Bayern1106.csv",  # noqa: E501
)
COUNCIL_CSV_URLS_2026 = (
    "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2026-03-08/09677148/html5/Open-Data-Gemeinderatswahl-Bayern1103.csv",  # noqa: E501
    "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2026-03-08/09677148/html5/Open-Data-Gemeinderatswahl-Bayern1106.csv",  # noqa: E501
)
# fmt: on

URLS = {
    "2020": (ELECTION_URL_2020, MAYOR_URL_2020),
    "2026": (ELECTION_URL_2026, MAYOR_URL_2026),
}

COUNCIL_CSV_URLS = {
    "2020": COUNCIL_CSV_URLS_2020,
    "2026": COUNCIL_CSV_URLS_2026,
}

COUNCIL_CSV_FILENAMES = (
    "Open-Data-Gemeinderatswahl-Bayern1103.csv",
    "Open-Data-Gemeinderatswahl-Bayern1106.csv",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_ARCHIVE_DIR = PROJECT_ROOT / "data" / "csv"
CSV_MAPPING_DIR = PROJECT_ROOT / "data" / "mappings"
