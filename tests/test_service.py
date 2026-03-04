import json
import urllib.error
from datetime import datetime, timezone

from election_fetcher.network import NetworkFetchError
from election_fetcher.service import fetch_data


COUNCIL_HTML = """
<div class="darstellung-balkendiagramm" data-array='[
  {"name": "CSU", "color": "#000000", "y": 34.2}
]'></div>
<table>
  <tr>
    <td><abbr>Max Mustermann, CSU</abbr></td>
    <td><nobr>1.234</nobr></td>
    <td>row</td>
  </tr>
</table>
"""


MAYOR_HTML = """
<table>
  <tr>
    <td><abbr>Alex Alpha, CSU</abbr></td>
    <td><nobr>2.345</nobr></td>
  </tr>
</table>
"""


def test_fetch_data_continues_when_mayor_request_fails(tmp_path):
    def fake_fetch(url, **kwargs):
        if "Gemeinderatswahl" in url:
            return COUNCIL_HTML
        raise NetworkFetchError(url, urllib.error.URLError("overloaded"), attempts=4)

    messages = []
    now = datetime(2026, 3, 4, 18, 30, 0, tzinfo=timezone.utc)

    ok = fetch_data(
        "2026",
        output_dir=tmp_path,
        csv_dir=tmp_path / "csv",
        mapping_dir=tmp_path / "mappings",
        fetch_html_fn=fake_fetch,
        now_fn=lambda: now,
        log_fn=messages.append,
    )

    assert ok is True
    assert (tmp_path / "candidates_2026.json").exists()
    assert not (tmp_path / "mayor_2026.json").exists()
    assert (tmp_path / "meta_2026.json").exists()

    metadata = json.loads((tmp_path / "meta_2026.json").read_text(encoding="utf-8"))
    assert metadata["year"] == "2026"
    assert metadata["mayor_ok"] is False
    assert metadata["timestamp"] == "2026-03-04T18:30:00+00:00"


def test_fetch_data_fails_when_council_request_fails(tmp_path):
    def fake_fetch(url, **kwargs):
        raise NetworkFetchError(url, urllib.error.URLError("overloaded"), attempts=4)

    ok = fetch_data(
        "2026",
        output_dir=tmp_path,
        csv_dir=tmp_path / "csv",
        mapping_dir=tmp_path / "mappings",
        fetch_html_fn=fake_fetch,
        log_fn=lambda _msg: None,
    )

    assert ok is False
    assert not (tmp_path / "candidates_2026.json").exists()
    assert not (tmp_path / "meta_2026.json").exists()


def test_fetch_data_writes_all_files_on_success(tmp_path):
    def fake_fetch(url, **kwargs):
        if "Buergermeisterwahl" in url:
            return MAYOR_HTML
        return COUNCIL_HTML

    ok = fetch_data(
        "2026",
        output_dir=tmp_path,
        csv_dir=tmp_path / "csv",
        mapping_dir=tmp_path / "mappings",
        fetch_html_fn=fake_fetch,
        log_fn=lambda _msg: None,
    )

    assert ok is True
    assert (tmp_path / "candidates_2026.json").exists()
    assert (tmp_path / "mayor_2026.json").exists()
    assert (tmp_path / "meta_2026.json").exists()


def test_fetch_data_uses_csv_fallback_when_council_request_fails(tmp_path):
    csv_dir = tmp_path / "csv"
    year_csv_dir = csv_dir / "2026"
    year_csv_dir.mkdir(parents=True)
    csv_payload = (
        "datum;wahl;gebiet-nr;D1;D1_1;D2;D2_1\n"
        "08.03.2026;Wahl des Stadtrats;0;1200;1200;800;800\n"
    )
    (year_csv_dir / "Open-Data-Gemeinderatswahl-Bayern1103.csv").write_text(
        csv_payload,
        encoding="utf-8",
    )

    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir(parents=True)
    mapping_payload = {
        "year": "2026",
        "parties": [
            {
                "csvCode": "D1",
                "id": "CSU",
                "name": "CSU",
                "color": "#000000",
                "totalVotesPercent": 60.0,
                "candidates": [{"csvCode": "D1_1", "name": "Max Mustermann"}],
            },
            {
                "csvCode": "D2",
                "id": "SPD",
                "name": "SPD",
                "color": "#FF0000",
                "totalVotesPercent": 40.0,
                "candidates": [{"csvCode": "D2_1", "name": "Erika Beispiel"}],
            },
        ],
    }
    (mapping_dir / "council_csv_mapping_2026.json").write_text(
        json.dumps(mapping_payload),
        encoding="utf-8",
    )

    def fake_fetch(url, **kwargs):
        if "Gemeinderatswahl" in url:
            raise NetworkFetchError(
                url, urllib.error.URLError("overloaded"), attempts=4
            )
        if "Buergermeisterwahl" in url:
            return MAYOR_HTML
        raise AssertionError(f"Unexpected URL fetched in test: {url}")

    ok = fetch_data(
        "2026",
        output_dir=tmp_path,
        csv_dir=csv_dir,
        mapping_dir=mapping_dir,
        fetch_html_fn=fake_fetch,
        log_fn=lambda _msg: None,
    )

    assert ok is True

    council_payload = json.loads(
        (tmp_path / "candidates_2026.json").read_text(encoding="utf-8")
    )
    assert council_payload[0]["name"] == "CSU"
    assert council_payload[0]["candidates"][0]["name"] == "Max Mustermann"
    assert council_payload[0]["candidates"][0]["votes"] == 1200

    metadata = json.loads((tmp_path / "meta_2026.json").read_text(encoding="utf-8"))
    assert metadata["council_source"].startswith("csv")
