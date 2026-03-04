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
        "2026", output_dir=tmp_path, fetch_html_fn=fake_fetch, log_fn=lambda _msg: None
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
        "2026", output_dir=tmp_path, fetch_html_fn=fake_fetch, log_fn=lambda _msg: None
    )

    assert ok is True
    assert (tmp_path / "candidates_2026.json").exists()
    assert (tmp_path / "mayor_2026.json").exists()
    assert (tmp_path / "meta_2026.json").exists()
