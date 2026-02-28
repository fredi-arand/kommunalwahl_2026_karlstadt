import urllib.request
from bs4 import BeautifulSoup
import json
import time

# fmt: off
ELECTION_URL = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
# fmt: on
OUTPUT_FILE = "live_data.json"


def fetch_data():
    print(f"Fetching data from {ELECTION_URL}...")
    try:
        req = urllib.request.Request(
            ELECTION_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode("utf-8")

        soup = BeautifulSoup(html, "html.parser")

        # 1. Fetch Party Strengths (Overall percentages)
        parties = {}
        chart_div = soup.find("div", class_="darstellung-balkendiagramm")
        if not chart_div:
            chart_div = soup.find("div", class_="darstellung-saeulendiagramm")

        if chart_div and chart_div.has_attr("data-array"):
            data_str = chart_div["data-array"]
            try:
                data_json = json.loads(data_str)
                # Initialize party list from chart data
                for item in data_json:
                    if "balken" in item:
                        # Handle "Sonstige" grouping
                        for sub_item in item["balken"]:
                            party_name = sub_item["name"]
                            parties[party_name] = {
                                "id": party_name,
                                "name": party_name,
                                "color": sub_item.get("color", "#CCCCCC"),
                                "totalVotesPercent": sub_item.get("y", 0.0),
                                "candidates": [],
                            }
                    else:
                        party_name = item["name"]
                        parties[party_name] = {
                            "id": party_name,
                            "name": party_name,
                            "color": item.get("color", "#CCCCCC"),
                            "totalVotesPercent": item.get("y", 0.0),
                            "candidates": [],
                        }
            except json.JSONDecodeError:
                print("Could not parse chart data JSON.")

        # 2. Fetch Candidates
        # Candidates are found in tables where columns contain Candidate Name and Votes.
        # Typically the cells have <abbr title="Candidate Name, Party"> and <nobr> for votes.
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3:
                    # Look for abbr tag inside a td
                    abbr = row.find("abbr")
                    if abbr and abbr.has_attr("title"):
                        # The text inside abbr is like "Dr. Frederick Arand, SPD"
                        name_and_party = abbr.text.strip()
                        if ", " in name_and_party:
                            cand_name, party_short = name_and_party.rsplit(", ", 1)
                        else:
                            cand_name = name_and_party
                            party_short = "Unknown"

                        # Find votes (usually in a td with class 'text-right' and nobr)
                        # Let's iterate over cols to find the one with a plain number.
                        votes_str = "0"
                        for col in cols:
                            nobr = col.find("nobr")
                            if nobr:
                                val = nobr.text.strip()
                                # Check if it's a vote count (integer formatting, e.g., "1.154" without '%')
                                if "%" not in val and any(c.isdigit() for c in val):
                                    votes_str = val
                                    break

                        votes_int = int(votes_str.replace(".", ""))

                        # Assign to party
                        # Note: The party abbreviation in the chart might not match exactly.
                        # Try to match or create a new one.
                        matched_party_key = None
                        for p_key in parties.keys():
                            if p_key in party_short or party_short in p_key:
                                matched_party_key = p_key
                                break

                        if not matched_party_key:
                            matched_party_key = party_short
                            if matched_party_key not in parties:
                                parties[matched_party_key] = {
                                    "id": matched_party_key,
                                    "name": matched_party_key,
                                    "color": "#CCCCCC",
                                    "totalVotesPercent": 0.0,
                                    "candidates": [],
                                }

                        # Check if candidate already exists in the list (since they appear in "gewählte" and maybe another list)  # noqa: E501
                        cand_exists = False
                        for c in parties[matched_party_key]["candidates"]:
                            if c["name"] == cand_name:
                                cand_exists = True
                                break

                        if not cand_exists:
                            parties[matched_party_key]["candidates"].append(
                                {
                                    "id": len(parties[matched_party_key]["candidates"])
                                    + 1,
                                    "name": cand_name,
                                    "votes": votes_int,
                                }
                            )

        # Save to file
        final_data = list(parties.values())
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        print(
            f"Successfully saved {len(final_data)} parties with candidate data to {OUTPUT_FILE}"
        )
        return True

    except Exception as e:
        print(f"Error fetching or parsing data: {e}")
        return False


if __name__ == "__main__":
    print("Starting election data fetcher...")
    while True:
        fetch_data()
        print("Waiting 60 seconds before next poll...")
        time.sleep(60)
