import urllib.request
from bs4 import BeautifulSoup
import json
import sys

# fmt: off
ELECTION_URL = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
MAYOR_URL = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Buergermeisterwahl_Bayern_108_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501
# fmt: on
OUTPUT_FILE = "candidates_2020.json"
MAYOR_OUTPUT = "mayor_2020.json"


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

                        # If the "candidate name" equals a known party name, this row
                        # likely represents an aggregated party total (not a person).
                        # Skip such rows to avoid creating an 'Unknown' party with
                        # names like 'CSU', 'SPD' as candidates.
                        if cand_name.strip() in parties:
                            continue

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
                        # Try exact or case-insensitive match first
                        for p_key in parties.keys():
                            if (
                                p_key.lower() == party_short.lower()
                                or party_short.lower() == p_key.lower()
                            ):
                                matched_party_key = p_key
                                break
                        # Fallback: substring match
                        if not matched_party_key:
                            for p_key in parties.keys():
                                try:
                                    if (
                                        p_key.lower().find(party_short.lower()) != -1
                                        or party_short.lower().find(p_key.lower()) != -1
                                    ):
                                        matched_party_key = p_key
                                        break
                                except Exception:
                                    continue

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

        # Save council candidates to file
        final_data = list(parties.values())
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        print(f"Saved {len(final_data)} parties with candidate data to {OUTPUT_FILE}")

        # 3. Fetch mayor page and extract mayor candidates (separate vote)
        try:
            mreq = urllib.request.Request(
                MAYOR_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(mreq) as mresp:
                mhtml = mresp.read().decode("utf-8")

            msoup = BeautifulSoup(mhtml, "html.parser")
            mayor_candidates = []

            # Similar parsing: look for rows with <abbr> and vote counts
            tables = msoup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    abbr = row.find("abbr")
                    if not abbr:
                        continue

                    name_and_party = abbr.get_text(strip=True)
                    if ", " in name_and_party:
                        cand_name, party_short = name_and_party.rsplit(", ", 1)
                    else:
                        cand_name = name_and_party
                        party_short = None

                    # Skip aggregated rows where name equals party
                    if party_short and cand_name.strip() == party_short.strip():
                        continue

                    # find votes
                    votes = 0
                    nobr = row.find("nobr")
                    if nobr and nobr.get_text(strip=True):
                        val = nobr.get_text(strip=True)
                        votes = (
                            int(val.replace(".", ""))
                            if any(c.isdigit() for c in val)
                            else 0
                        )
                    else:
                        cols = row.find_all(["td", "th"])
                        for col in reversed(cols):
                            txt = col.get_text(" ", strip=True)
                            if any(c.isdigit() for c in txt):
                                cleaned = "".join(ch for ch in txt if ch.isdigit())
                                votes = int(cleaned) if cleaned else 0
                                break

                    mayor_candidates.append(
                        {
                            "name": cand_name.strip(),
                            "party": party_short.strip() if party_short else None,
                            "votes": votes,
                        }
                    )

            # dedupe and sort
            seen = {}
            for c in mayor_candidates:
                key = (c["name"], c["party"])
                if key in seen:
                    if c["votes"] > seen[key]["votes"]:
                        seen[key] = c
                else:
                    seen[key] = c

            mayor_list = list(seen.values())
            mayor_list.sort(key=lambda x: x["votes"], reverse=True)
            # assign ids
            for idx, r in enumerate(mayor_list, start=1):
                r["id"] = idx

            with open(MAYOR_OUTPUT, "w", encoding="utf-8") as f:
                json.dump(mayor_list, f, ensure_ascii=False, indent=2)
                f.write("\n")

            print(f"Saved {len(mayor_list)} mayor candidates to {MAYOR_OUTPUT}")
        except Exception as me:
            print(f"Error fetching/parsing mayor page: {me}")

        return True

    except Exception as e:
        print(f"Error fetching or parsing data: {e}")
        return False


if __name__ == "__main__":
    print("Running fetcher once...")
    ok = fetch_data()
    if not ok:
        sys.exit(1)
