import sys
import urllib.request


def main(argv):
    if len(argv) < 1:
        print("Usage: python dump.py <url>")
        return 2
    url = argv[0]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode("utf-8")

    with open("dump.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Dumped to dump.html")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
