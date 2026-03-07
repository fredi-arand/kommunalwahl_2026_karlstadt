from election_source import (
    mayor_json_from_rows,
    normalize_filename,
    parse_mayor_table_csv,
)


MAYOR_HTML = """
<table class="tablesaw table-stimmen"
       data-tablejigsaw-downloadable
       data-tablejigsaw-downloadable-filename="Stimmenanteile tabellarisch">
  <thead>
    <tr><th>Partei</th><th>Stimmen</th></tr>
  </thead>
  <tbody>
    <tr><td>CSU</td><td>123</td></tr>
  </tbody>
</table>
"""


def test_normalize_filename_replaces_spaces_with_underscores():
    assert (
        normalize_filename("Stimmenanteile tabellarisch")
        == "Stimmenanteile_tabellarisch.csv"
    )


def test_parse_mayor_table_csv_uses_sanitized_filename_and_semicolon_csv():
    filename, csv_payload, rows = parse_mayor_table_csv(MAYOR_HTML)

    assert filename == "Stimmenanteile_tabellarisch.csv"
    assert csv_payload.splitlines()[0] == "Partei;Stimmen"
    assert csv_payload.splitlines()[1] == "CSU;123"
    assert rows[1] == ["CSU", "123"]


def test_mayor_json_from_rows_parses_and_sorts_candidates():
    rows = [
        ["Partei", "Direktkandidat", "Stimmen"],
        ["CSU", "Muster Max", "1.234"],
        ["SPD", "Beispiel Eva", "888"],
        ["Wähler", "", "2000"],
    ]

    payload = mayor_json_from_rows(rows)

    assert [candidate["name"] for candidate in payload] == [
        "Muster Max",
        "Beispiel Eva",
    ]
    assert payload[0]["votes"] == 1234
    assert payload[0]["id"] == 1
