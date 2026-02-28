import urllib.request

url = "https://okvote.osrz-akdb.de/OK.VOTE_UF/Wahl-2020-03-15/09677148/html5/Gemeinderatswahl_Bayern_110_Gemeinde_Stadt_Karlstadt.html"  # noqa: E501

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as response:
    html = response.read().decode("utf-8")

with open("dump.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Dumped.")
